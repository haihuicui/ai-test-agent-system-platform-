const API_BASE_URL = "/api/v2";

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}
// eslint-disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y1VKc2JRPT06OGJiMjkzOTc=

class ApiError extends Error {
  status: number;
  data?: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}
// TODO  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y1VKc2JRPT06OGJiMjkzOTc=

async function handleResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type");
  const isJson = contentType?.includes("application/json");

  // Handle 204 No Content responses (empty body)
  if (response.status === 204) {
    if (!response.ok) {
      throw new ApiError(`HTTP error! status: ${response.status}`, response.status);
    }
    return undefined as T;
  }

  const data = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const message =
      (isJson && typeof data === 'object' && (data as any)?.message) || `HTTP error! status: ${response.status}`;
    throw new ApiError(message, response.status, data);
  }

  return data as T;
}

function buildUrl(
  path: string,
  params?: Record<string, string | number | boolean | undefined>
): string {
  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin);

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.append(key, String(value));
      }
    });
  }

  return url.toString();
}
// FIXME  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y1VKc2JRPT06OGJiMjkzOTc=

export const apiClient = {
  async get<T>(path: string, options?: RequestOptions): Promise<T> {
    const url = buildUrl(path, options?.params);
    const response = await fetch(url, {
      ...options,
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });
    return handleResponse<T>(response);
  },

  async post<T>(
    path: string,
    body?: unknown,
    options?: RequestOptions
  ): Promise<T> {
    const url = buildUrl(path, options?.params);
    const response = await fetch(url, {
      ...options,
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    return handleResponse<T>(response);
  },

  async put<T>(
    path: string,
    body?: unknown,
    options?: RequestOptions
  ): Promise<T> {
    const url = buildUrl(path, options?.params);
    const response = await fetch(url, {
      ...options,
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    return handleResponse<T>(response);
  },

  async patch<T>(
    path: string,
    body?: unknown,
    options?: RequestOptions
  ): Promise<T> {
    const url = buildUrl(path, options?.params);
    const response = await fetch(url, {
      ...options,
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    return handleResponse<T>(response);
  },

  async delete<T>(
    path: string,
    options?: RequestOptions & { data?: unknown }
  ): Promise<T> {
    const url = buildUrl(path, options?.params);
    const { data, ...restOptions } = options || {};
    const response = await fetch(url, {
      ...restOptions,
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
        ...restOptions?.headers,
      },
      body: data ? JSON.stringify(data) : undefined,
    });
    return handleResponse<T>(response);
  },
};

export { ApiError };
// WATERMARK  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y1VKc2JRPT06OGJiMjkzOTc=

