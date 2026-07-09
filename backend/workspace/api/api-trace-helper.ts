import { test as baseTest, APIRequestContext, APIResponse } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

function ensureDir(filePath: string): void {
  const dir = path.dirname(filePath);
  if (dir && dir !== '.' && !fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function appendTrace(traceFile: string, entry: any): void {
  try {
    ensureDir(traceFile);
    fs.appendFileSync(traceFile, JSON.stringify(entry) + '\n', 'utf-8');
  } catch (e) { /* ignore */ }
}

// ---------------------------------------------------------------------------
// 脱敏与大小配置（支持环境变量覆盖）
// ---------------------------------------------------------------------------
const DEFAULT_SENSITIVE_HEADERS = ['authorization', 'cookie', 'x-api-key', 'x-auth-token'];
const DEFAULT_SENSITIVE_BODY_FIELDS = [
  'password', 'token', 'secret', 'apikey', 'api_key',
  'accesstoken', 'refreshtoken', 'auth_token',
];
const DEFAULT_TRUNCATE_THRESHOLD = 50_000;
const DEFAULT_PREVIEW_LENGTH = 2_000;

function parseEnvList(name: string, defaults: string[]): string[] {
  const raw = process.env[name];
  if (!raw) return defaults;
  return raw.split(',').map((s) => s.trim().toLowerCase()).filter(Boolean);
}

function parseEnvInt(name: string, defaultValue: number): number {
  const raw = process.env[name];
  if (!raw) return defaultValue;
  const parsed = parseInt(raw, 10);
  return Number.isNaN(parsed) ? defaultValue : parsed;
}

const SENSITIVE_HEADERS = new Set(parseEnvList('API_TEST_SENSITIVE_HEADERS', DEFAULT_SENSITIVE_HEADERS));
const SENSITIVE_BODY_FIELDS = new Set(parseEnvList('API_TEST_SENSITIVE_BODY_FIELDS', DEFAULT_SENSITIVE_BODY_FIELDS));
const BODY_TRUNCATE_THRESHOLD = parseEnvInt('API_TEST_BODY_TRUNCATE_THRESHOLD', DEFAULT_TRUNCATE_THRESHOLD);
const BODY_PREVIEW_LENGTH = parseEnvInt('API_TEST_BODY_PREVIEW_LENGTH', DEFAULT_PREVIEW_LENGTH);

function sanitizeHeaders(headers: Record<string, string> | undefined): Record<string, string> | undefined {
  if (!headers) return headers;
  const result: Record<string, string> = {};
  for (const [key, value] of Object.entries(headers)) {
    result[key] = SENSITIVE_HEADERS.has(key.toLowerCase()) ? '***' : value;
  }
  return result;
}

function sanitizeBody(body: any): any {
  if (body === null || body === undefined) return body;
  if (typeof body === 'string') {
    try {
      const parsed = JSON.parse(body);
      const sanitized = sanitizeBody(parsed);
      return JSON.stringify(sanitized);
    } catch {
      return body;
    }
  }
  if (Array.isArray(body)) return body.map(sanitizeBody);
  if (typeof body !== 'object') return body;
  const result: any = {};
  for (const [key, value] of Object.entries(body)) {
    result[key] = SENSITIVE_BODY_FIELDS.has(key.toLowerCase()) ? '***' : sanitizeBody(value);
  }
  return result;
}

function getBodyMeta(body: any): { originalSize: number; truncated: boolean } {
  if (body === null || body === undefined) {
    return { originalSize: 0, truncated: false };
  }
  const serialized = typeof body === 'string' ? body : JSON.stringify(body);
  const originalSize = Buffer.byteLength(serialized, 'utf8');
  return { originalSize, truncated: originalSize > BODY_TRUNCATE_THRESHOLD };
}

function wrapResponse(response: APIResponse, testName: string, testTitle: string, traceFile: string, startTime: number, requestInfo: any): APIResponse {
  let bodyRecorded = false;
  const record = (responseBody?: any) => {
    if (bodyRecorded && responseBody === undefined) return;
    if (responseBody !== undefined) bodyRecorded = true;
    let body = responseBody;
    if (typeof body === 'string') { try { body = JSON.parse(body); } catch { /* keep text */ } }

    const sanitizedReqHeaders = sanitizeHeaders(requestInfo.headers);
    const sanitizedRespHeaders = sanitizeHeaders(response.headers());
    const sanitizedReqBody = sanitizeBody(requestInfo.body);
    const sanitizedRespBody = sanitizeBody(body);
    const reqBodyMeta = getBodyMeta(sanitizedReqBody);
    const respBodyMeta = getBodyMeta(sanitizedRespBody);

    appendTrace(traceFile, {
      testName, testTitle,
      method: requestInfo.method, url: requestInfo.url,
      requestHeaders: sanitizedReqHeaders,
      requestParams: requestInfo.params,
      requestBody: sanitizedReqBody,
      requestBodyOriginalSize: reqBodyMeta.originalSize,
      requestBodyTruncated: reqBodyMeta.truncated,
      status: response.status(), statusText: response.statusText(),
      responseHeaders: sanitizedRespHeaders,
      responseBody: sanitizedRespBody,
      responseBodyOriginalSize: respBodyMeta.originalSize,
      responseBodyTruncated: respBodyMeta.truncated,
      durationMs: Date.now() - startTime, timestamp: new Date().toISOString(),
    });
  };
  return new Proxy(response, {
    get(target, prop, receiver) {
      if (prop === 'json') return async () => { const body = await target.json(); record(body); return body; };
      if (prop === 'text') return async () => { const text = await target.text(); record(text); return text; };
      if (['status','statusText','headers','ok','url'].includes(prop as string)) record();
      return Reflect.get(target, prop, receiver);
    },
  });
}

function wrapContext(context: APIRequestContext, testName: string, testTitle: string, traceFile: string): APIRequestContext {
  const methods = ['get','post','put','delete','patch','head'];
  const recordRequest = (method: string, url: string, options: any, startTime: number, extra: any = {}) => {
    const sanitizedReqHeaders = sanitizeHeaders(options?.headers);
    const sanitizedReqBody = sanitizeBody(options?.data);
    const reqBodyMeta = getBodyMeta(sanitizedReqBody);

    appendTrace(traceFile, {
      testName, testTitle,
      method, url,
      requestHeaders: sanitizedReqHeaders,
      requestParams: options?.params,
      requestBody: sanitizedReqBody,
      requestBodyOriginalSize: reqBodyMeta.originalSize,
      requestBodyTruncated: reqBodyMeta.truncated,
      ...extra,
      durationMs: Date.now() - startTime, timestamp: new Date().toISOString(),
    });
  };
  return new Proxy(context, {
    get(target, prop, receiver) {
      if (typeof prop === 'string' && methods.includes(prop.toLowerCase())) {
        return async (url: string, options?: any) => {
          const startTime = Date.now();
          try {
            const response = await target[prop](url, options);
            return wrapResponse(response, testName, testTitle, traceFile, startTime, {
              method: prop.toUpperCase(), url,
              headers: options?.headers, params: options?.params, body: options?.data,
            });
          } catch (error) {
            recordRequest(prop.toUpperCase(), url, options, startTime, {
              status: null, statusText: String(error),
              responseHeaders: {}, responseBody: null,
              error: String(error),
            });
            throw error;
          }
        };
      }
      if (prop === 'fetch') {
        return async (urlOrRequest: string | Request, options?: any) => {
          const url = typeof urlOrRequest === 'string' ? urlOrRequest : urlOrRequest.url;
          const startTime = Date.now();
          try {
            const response = await target.fetch(urlOrRequest, options);
            return wrapResponse(response, testName, testTitle, traceFile, startTime, {
              method: options?.method?.toUpperCase() || 'GET', url,
              headers: options?.headers, params: options?.params, body: options?.data,
            });
          } catch (error) {
            recordRequest(options?.method?.toUpperCase() || 'GET', url, options, startTime, {
              status: null, statusText: String(error),
              responseHeaders: {}, responseBody: null,
              error: String(error),
            });
            throw error;
          }
        };
      }
      return Reflect.get(target, prop, receiver);
    },
  });
}

export const test = baseTest.extend({
  request: async ({ request }, use, testInfo) => {
    const traceFile = process.env.API_TRACE_OUTPUT_FILE;
    if (!traceFile) { await use(request); return; }
    const wrapped = wrapContext(request, testInfo.titlePath.join(' › '), testInfo.title, traceFile);
    await use(wrapped as APIRequestContext);
  },
});

export { expect } from '@playwright/test';
export { request, APIRequestContext, APIResponse, Page, BrowserContext, Browser, chromium, firefox, webkit, devices, defineConfig } from '@playwright/test';
