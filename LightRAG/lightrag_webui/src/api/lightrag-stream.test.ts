import { afterEach, beforeAll, describe, expect, mock, test } from 'bun:test'

// ---------------------------------------------------------------------------
// Mock dependencies BEFORE importing the module under test
// ---------------------------------------------------------------------------

const storageData = new Map<string, string>()
const storageMock = {
  getItem: (key: string) => storageData.get(key) ?? null,
  setItem: (key: string, value: string) => { storageData.set(key, value) },
  removeItem: (key: string) => { storageData.delete(key) },
  clear: () => { storageData.clear() },
}

Object.defineProperty(globalThis, 'localStorage', {
  value: storageMock,
  configurable: true,
})
Object.defineProperty(globalThis, 'sessionStorage', {
  value: storageMock,
  configurable: true,
})

// Mock zustand stores — both return a vanilla store-like object with getState()
let storeApiKey: string | null = null
let storeIsGuestMode = false
let storeWorkspace = ''
const fakeSettingsStore = {
  getState: () => ({ apiKey: storeApiKey, workspace: storeWorkspace }),
}
const fakeAuthStore = {
  getState: () => ({
    isGuestMode: storeIsGuestMode,
    login: () => {},
    setTokenRenewal: () => {},
  }),
}

mock.module('@/stores/settings', () => ({ useSettingsStore: fakeSettingsStore }))
mock.module('@/stores/state', () => ({ useAuthStore: fakeAuthStore }))
mock.module('@/services/navigation', () => ({
  navigationService: { navigateToLogin: () => {} },
}))
mock.module('@/lib/utils', () => ({
  errorMessage: (error: any) =>
    error instanceof Error ? error.message : `${error}`,
}))
mock.module('@/lib/constants', () => ({
  backendBaseUrl: 'http://localhost:9621',
  popularLabelsDefaultLimit: 300,
  searchLabelsDefaultLimit: 50,
}))

// Mock axios — the module calls axios.create() at top level and
// axios.get() in silentRefreshGuestToken
mock.module('axios', () => {
  const instance = {
    get: () =>
      Promise.resolve({
        data: {
          access_token: 'mock-guest-token',
          auth_configured: false,
          core_version: '1.0',
          api_version: '1.0',
        },
        headers: {},
      }),
    post: () => Promise.resolve({ data: {}, headers: {} }),
    interceptors: {
      request: { use: () => {} },
      response: { use: () => {} },
    },
  }
  // The default export from axios is the main axios function, which also has
  // .create, .get, .post, etc. as static methods.
  const axiosFn: any = () => Promise.resolve({ data: {}, headers: {} })
  axiosFn.create = () => instance
  axiosFn.get = instance.get
  axiosFn.post = instance.post
  axiosFn.interceptors = instance.interceptors
  return { default: axiosFn, __esModule: true }
})

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a minimal QueryRequest payload. */
const makeQueryRequest = (overrides = {}) => ({
  query: 'test query',
  mode: 'mix' as const,
  ...overrides,
})

/**
 * Create a ReadableStream from an array of Uint8Array chunks. Bun's Response
 * constructor accepts a ReadableStream directly.
 */
function makeNdjsonResponse(lines: string[], status = 200): Response {
  const encoder = new TextEncoder()
  const body = lines.map((l) => encoder.encode(l + '\n'))
  // Build a simple async iterable readable stream
  const stream = new ReadableStream({
    start(controller) {
      for (const chunk of body) {
        controller.enqueue(chunk)
      }
      controller.close()
    },
  })
  return new Response(stream, { status })
}

/** Build a non-streaming error response (text body). */
function makeTextResponse(body: string, status: number): Response {
  return new Response(body, { status })
}

/**
 * Install a mocked implementation onto globalThis.fetch. Bun's `mock()` returns
 * a `Mock` that lacks the DOM `fetch.preconnect` static, so the assignment is
 * cast through `unknown` to satisfy the `typeof fetch` type.
 */
function installFetchMock(
  impl: (url: string, init?: RequestInit) => Response | Promise<Response>
): void {
  globalThis.fetch = mock(impl) as unknown as typeof fetch
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

let apiModule: typeof import('./lightrag')

beforeAll(async () => {
  apiModule = await import('./lightrag')
})

afterEach(() => {
  storageData.clear()
  storeApiKey = null
  storeIsGuestMode = false
  storeWorkspace = ''
})

describe('queryTextStream — normal path', () => {
  test('parses NDJSON response chunks and calls onChunk', async () => {
    const chunks: string[] = []
    const errors: string[] = []

    installFetchMock(() =>
      makeNdjsonResponse([
        '{"response": "Hello"}',
        '{"response": " World"}',
        '{"response": "!"}',
      ])
    )

    await apiModule.queryTextStream(
      makeQueryRequest(),
      (c) => chunks.push(c),
      (e) => errors.push(e)
    )

    expect(chunks).toEqual(['Hello', ' World', '!'])
    expect(errors).toEqual([])
  })

  test('forwards error lines to onError', async () => {
    const chunks: string[] = []
    const errors: string[] = []

    installFetchMock(() =>
      makeNdjsonResponse([
        '{"response": "ok"}',
        '{"error": "Something went wrong"}',
        '{"response": "more"}',
      ])
    )

    await apiModule.queryTextStream(
      makeQueryRequest(),
      (c) => chunks.push(c),
      (e) => errors.push(e)
    )

    expect(chunks).toEqual(['ok', 'more'])
    expect(errors).toEqual(['Something went wrong'])
  })

  test('skips malformed JSON lines', async () => {
    const chunks: string[] = []

    installFetchMock(() =>
      makeNdjsonResponse([
        'not valid json',
        '{"response": "valid"}',
        '{broken',
      ])
    )

    await apiModule.queryTextStream(
      makeQueryRequest(),
      (c) => chunks.push(c),
      () => {}
    )

    expect(chunks).toEqual(['valid'])
  })

  test('handles multi-byte characters split across chunks', async () => {
    const chunks: string[] = []
    const encoder = new TextEncoder()
    // "Hello 😀🌍" — split the emoji bytes across chunks
    const fullJson = '{"response": "Hello 😀🌍"}\n'
    const fullBytes = encoder.encode(fullJson)
    // Split at an arbitrary point inside the emoji sequence
    const splitAt = 28
    const part1 = fullBytes.slice(0, splitAt)
    const part2 = fullBytes.slice(splitAt)

    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(part1)
        controller.enqueue(part2)
        controller.close()
      },
    })

    installFetchMock(() => new Response(stream, { status: 200 }))

    await apiModule.queryTextStream(
      makeQueryRequest(),
      (c) => chunks.push(c),
      () => {}
    )

    expect(chunks).toEqual(['Hello 😀🌍'])
  })

  test('calls onError when final buffer is unparseable (truncated stream)', async () => {
    // Simulate a stream cut off mid-line with no trailing newline.
    // The residual buffer after the stream ends will be an incomplete JSON
    // object that can't be parsed.
    const encoder = new TextEncoder()
    const jsonLine = '{"response": "ok"}\n'
    const truncatedLine = '{"response": "incom'
    const body = new Uint8Array([
      ...encoder.encode(jsonLine),
      ...encoder.encode(truncatedLine),
    ])

    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(body)
        controller.close()
      },
    })

    installFetchMock(() => new Response(stream, { status: 200 }))

    const chunks: string[] = []
    const errors: string[] = []

    await apiModule.queryTextStream(
      makeQueryRequest(),
      (c) => chunks.push(c),
      (e) => errors.push(e)
    )

    expect(chunks).toEqual(['ok'])
    expect(errors).toEqual([
      'Response stream ended with incomplete data — the response may be truncated.',
    ])
  })
})

describe('queryTextStream — abort / stop button', () => {
  test('exits silently on user abort (signal.aborted)', async () => {
    const controller = new AbortController()
    controller.abort()

    installFetchMock(() => {
      // fetch should reject since the signal is already aborted
      return Promise.reject(new DOMException('Aborted', 'AbortError'))
    })

    let errorCalled = false
    await apiModule.queryTextStream(
      makeQueryRequest(),
      () => {},
      () => { errorCalled = true },
      controller.signal
    )

    expect(errorCalled).toBe(false)
  })

  test('exits silently when AbortError is thrown without a signal', async () => {
    installFetchMock(() =>
      Promise.reject(new DOMException('Aborted', 'AbortError'))
    )

    let errorCalled = false
    await apiModule.queryTextStream(
      makeQueryRequest(),
      () => {},
      () => { errorCalled = true }
    )

    expect(errorCalled).toBe(false)
  })
})

describe('queryTextStream — HTTP errors', () => {
  const errorCases = [
    {
      status: 403,
      expectedMessage:
        'You do not have permission to access this resource (403 Forbidden)',
    },
    {
      status: 404,
      expectedMessage: 'The requested resource does not exist (404 Not Found)',
    },
    {
      status: 429,
      expectedMessage:
        'Too many requests, please try again later (429 Too Many Requests)',
    },
    {
      status: 500,
      expectedMessage:
        'Server error, please try again later (500)',
    },
    {
      status: 502,
      expectedMessage:
        'Server error, please try again later (502)',
    },
    {
      status: 503,
      expectedMessage:
        'Server error, please try again later (503)',
    },
  ]

  for (const { status, expectedMessage } of errorCases) {
    test(`shows friendly message for HTTP ${status}`, async () => {
      installFetchMock(() =>
        makeTextResponse('{"error":"details"}', status)
      )

      let capturedError = ''
      await apiModule.queryTextStream(
        makeQueryRequest(),
        () => {},
        (e) => { capturedError = e }
      )

      expect(capturedError).toBe(expectedMessage)
    })
  }
})

describe('queryTextStream — network errors', () => {
  test('shows network error for Failed to fetch', async () => {
    installFetchMock(() =>
      Promise.reject(new TypeError('Failed to fetch'))
    )

    let capturedError = ''
    await apiModule.queryTextStream(
      makeQueryRequest(),
      () => {},
      (e) => { capturedError = e }
    )

    expect(capturedError).toBe(
      'Network connection error, please check your internet connection'
    )
  })

  test('shows network error for NetworkError', async () => {
    installFetchMock(() =>
      Promise.reject(new Error('NetworkError: connection refused'))
    )

    let capturedError = ''
    await apiModule.queryTextStream(
      makeQueryRequest(),
      () => {},
      (e) => { capturedError = e }
    )

    expect(capturedError).toBe(
      'Network connection error, please check your internet connection'
    )
  })
})

describe('queryTextStream — auth headers', () => {
  test('includes Bearer token when stored', async () => {
    storageData.set('LIGHTRAG-API-TOKEN', 'test-jwt-token')

    let capturedHeaders: HeadersInit | undefined
    installFetchMock((_url: string, init?: RequestInit) => {
      capturedHeaders = init?.headers
      return makeNdjsonResponse(['{"response": "ok"}'])
    })

    await apiModule.queryTextStream(
      makeQueryRequest(),
      () => {},
      () => {}
    )

    // The module builds headers as a plain object literal, so the captured
    // RequestInit.headers is a Record we can assert against directly.
    const sentHeaders = capturedHeaders as Record<string, string>
    expect(sentHeaders).toBeDefined()
    expect(sentHeaders['Authorization']).toBe('Bearer test-jwt-token')
    expect(sentHeaders['Accept']).toBe('application/x-ndjson')
    expect(sentHeaders['Content-Type']).toBe('application/json')
  })

  test('omits Bearer token when none is stored', async () => {
    let capturedHeaders: HeadersInit | undefined
    installFetchMock((_url: string, init?: RequestInit) => {
      capturedHeaders = init?.headers
      return makeNdjsonResponse(['{"response": "ok"}'])
    })

    await apiModule.queryTextStream(
      makeQueryRequest(),
      () => {},
      () => {}
    )

    const sentHeaders = capturedHeaders as Record<string, string>
    expect(sentHeaders['Authorization']).toBeUndefined()
  })

  test('includes LIGHTRAG-WORKSPACE header when a workspace is selected', async () => {
    storeWorkspace = 'PR_1'

    let capturedHeaders: HeadersInit | undefined
    installFetchMock((_url: string, init?: RequestInit) => {
      capturedHeaders = init?.headers
      return makeNdjsonResponse(['{"response": "ok"}'])
    })

    await apiModule.queryTextStream(
      makeQueryRequest(),
      () => {},
      () => {}
    )

    const sentHeaders = capturedHeaders as Record<string, string>
    expect(sentHeaders['LIGHTRAG-WORKSPACE']).toBe('PR_1')
  })

  test('omits LIGHTRAG-WORKSPACE header for the default workspace', async () => {
    let capturedHeaders: HeadersInit | undefined
    installFetchMock((_url: string, init?: RequestInit) => {
      capturedHeaders = init?.headers
      return makeNdjsonResponse(['{"response": "ok"}'])
    })

    await apiModule.queryTextStream(
      makeQueryRequest(),
      () => {},
      () => {}
    )

    const sentHeaders = capturedHeaders as Record<string, string>
    expect(sentHeaders['LIGHTRAG-WORKSPACE']).toBeUndefined()
  })

  test('calls /query/stream endpoint', async () => {
    let capturedUrl = ''
    installFetchMock((url: string) => {
      capturedUrl = url
      return makeNdjsonResponse(['{"response": "ok"}'])
    })

    await apiModule.queryTextStream(
      makeQueryRequest(),
      () => {},
      () => {}
    )

    expect(capturedUrl).toBe('http://localhost:9621/query/stream')
  })
})

describe('queryTextStream — guest-token 401 retry', () => {
  test('retries with refreshed guest token on 401', async () => {
    storageData.set('LIGHTRAG-API-TOKEN', 'expired-guest-token')
    storeIsGuestMode = true

    let callCount = 0

    installFetchMock(() => {
      callCount++
      if (callCount === 1) {
        return makeTextResponse('{"error":"unauthorized"}', 401)
      }
      return makeNdjsonResponse(['{"response": "retry ok"}'])
    })

    const chunks: string[] = []
    await apiModule.queryTextStream(
      makeQueryRequest(),
      (c) => chunks.push(c),
      () => {}
    )

    expect(callCount).toBe(2)
    expect(chunks).toEqual(['retry ok'])
  })

  test('classifies a non-auth HTTP error on the retried stream (e.g. 429)', async () => {
    storageData.set('LIGHTRAG-API-TOKEN', 'expired-guest-token')
    storeIsGuestMode = true

    let callCount = 0

    installFetchMock(() => {
      callCount++
      if (callCount === 1) {
        return makeTextResponse('{"error":"unauthorized"}', 401)
      }
      // Refresh succeeded, but the retried request is rate-limited.
      return makeTextResponse('{"error":"rate limited"}', 429)
    })

    let capturedError = ''
    await apiModule.queryTextStream(
      makeQueryRequest(),
      () => {},
      (e) => {
        capturedError = e
      }
    )

    // The retry's 429 must be classified like any other HTTP error, NOT
    // reported as an auth-refresh failure.
    expect(callCount).toBe(2)
    expect(capturedError).toBe(
      'Too many requests, please try again later (429 Too Many Requests)'
    )
  })
})

describe('workspace namespacing of paginated document requests', () => {
  // The dedup key of in-flight paginated document requests is namespaced by
  // the active workspace: identical parameters under different workspaces
  // must NOT share a promise. The settings store is mocked in this file, so
  // the workspace is controlled via the `storeWorkspace` variable.
  const makeDocsRequest = (page = 1) => ({
    status_filter: null,
    page,
    page_size: 20,
    sort_field: 'updated_at' as const,
    sort_direction: 'desc' as const
  })

  const emptyPage = {
    documents: [],
    pagination: { page: 1, page_size: 20, total_count: 0, total_pages: 0, has_next: false, has_prev: false },
    status_counts: { all: 0 }
  }

  test('does not dedupe identical requests across workspaces', async () => {
    const request = makeDocsRequest()

    let callCount = 0
    const resolvers: Array<(value: any) => void> = []
    apiModule.__setPaginatedDocumentsPostForTests((_request, controller) => {
      callCount += 1
      return new Promise((resolve, reject) => {
        resolvers.push(resolve)
        controller.signal.addEventListener(
          'abort',
          () => reject(new DOMException('Aborted', 'AbortError')),
          { once: true }
        )
      })
    })

    storeWorkspace = 'ws_a'
    const reqA = apiModule.getDocumentsPaginated(request)
    storeWorkspace = 'ws_b'
    const reqB = apiModule.getDocumentsPaginated(request)

    expect(callCount).toBe(2)

    resolvers[0](emptyPage)
    resolvers[1](emptyPage)
    await expect(reqA).resolves.toEqual(emptyPage)
    await expect(reqB).resolves.toEqual(emptyPage)

    // Same workspace + same parameters still dedupes
    const reqB1 = apiModule.getDocumentsPaginated(request)
    const reqB2 = apiModule.getDocumentsPaginated(request)
    expect(callCount).toBe(3)
    resolvers[2](emptyPage)
    await expect(reqB1).resolves.toEqual(emptyPage)
    await expect(reqB2).resolves.toEqual(emptyPage)

    storeWorkspace = ''
    apiModule.__resetPaginatedDocumentRequestsForTests()
  })

  test('abortAllDocumentsPaginated aborts every in-flight request', async () => {
    let callCount = 0
    apiModule.__setPaginatedDocumentsPostForTests((_request, controller) => {
      callCount += 1
      return new Promise((_resolve, reject) => {
        controller.signal.addEventListener(
          'abort',
          () => reject(new DOMException('Aborted', 'AbortError')),
          { once: true }
        )
      })
    })

    const first = apiModule.getDocumentsPaginated(makeDocsRequest())
    const second = apiModule.getDocumentsPaginated(makeDocsRequest(2))
    expect(callCount).toBe(2)

    apiModule.abortAllDocumentsPaginated()

    const [r1, r2] = await Promise.allSettled([first, second])
    expect(r1.status).toBe('rejected')
    expect(r2.status).toBe('rejected')

    apiModule.__resetPaginatedDocumentRequestsForTests()
  })
})
