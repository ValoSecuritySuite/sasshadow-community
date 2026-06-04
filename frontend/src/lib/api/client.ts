/**
 * Centralized API client for SaaSShadow.ai frontend.
 * Safe JSON handling, blob download support, timeout-aware requests, normalized errors.
 * Use request functions from ./requests for typed endpoint calls.
 */

import { getApiBaseUrl } from "./config";

const DEFAULT_TIMEOUT_MS = 30_000;
const DEFAULT_HEADERS: Record<string, string> = {
  "Content-Type": "application/json",
  Accept: "application/json",
};

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function getBaseUrl(): string {
  return getApiBaseUrl();
}

function buildUrl(path: string, query?: Record<string, string>): string {
  const base = getBaseUrl().replace(/\/$/, "");
  const pathNorm = path.startsWith("/") ? path : `/${path}`;
  const url = `${base}${pathNorm}`;
  if (!query || Object.keys(query).length === 0) return url;
  const params = new URLSearchParams(query);
  return `${url}?${params.toString()}`;
}

/** Normalize HeadersInit to a plain object so we can merge and type as Record<string, string>. */
function headersToRecord(init: HeadersInit | undefined): Record<string, string> {
  if (init == null) return {};
  if (init instanceof Headers) {
    const r: Record<string, string> = {};
    init.forEach((v, k) => {
      r[k] = v;
    });
    return r;
  }
  if (Array.isArray(init)) {
    return Object.fromEntries(init) as Record<string, string>;
  }
  return { ...init };
}

export interface RequestConfig {
  signal?: AbortSignal;
  timeoutMs?: number;
  headers?: Record<string, string>;
}

/**
 * Safe JSON parse with typed error.
 */
function safeJson<T>(text: string): T {
  try {
    return JSON.parse(text) as T;
  } catch (e) {
    throw new ApiError(
      `Invalid JSON response: ${e instanceof Error ? e.message : String(e)}`,
      0,
      "PARSE_ERROR",
      e,
    );
  }
}

/**
 * Normalized error from response body (FastAPI error shape).
 */
function parseErrorBody(text: string): { code?: string; message?: string; detail?: unknown } {
  try {
    const data = JSON.parse(text) as Record<string, unknown>;
    const detail = data.detail;
    if (typeof detail === "object" && detail !== null && "error" in detail) {
      const err = (detail as { error: { code?: string; message?: string; detail?: unknown } }).error;
      return {
        code: typeof err?.code === "string" ? err.code : undefined,
        message: typeof err?.message === "string" ? err.message : undefined,
        detail: err?.detail,
      };
    }
    return {
      message: typeof data.message === "string" ? data.message : undefined,
      detail: detail !== undefined ? detail : (Object.keys(data).length > 0 ? data : undefined),
    };
  } catch {
    return { message: text || undefined };
  }
}

/**
 * Create an AbortSignal that fires after timeoutMs.
 */
function withTimeout(timeoutMs: number, signal?: AbortSignal): AbortSignal {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  if (signal) {
    signal.addEventListener(
      "abort",
      () => {
        clearTimeout(id);
        controller.abort();
      },
      { once: true },
    );
  }
  return controller.signal;
}

/**
 * Fetch JSON with timeout and normalized error handling.
 */
export async function requestJson<T>(
  path: string,
  init: RequestInit & { query?: Record<string, string>; config?: RequestConfig } = {},
): Promise<T> {
  const { query, config = {}, ...fetchInit } = init;
  const timeoutMs = config.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const signal = config.signal
    ? withTimeout(timeoutMs, config.signal)
    : undefined;
  const url = buildUrl(path, query);
  const headers: Record<string, string> = {
    ...DEFAULT_HEADERS,
    ...config.headers,
    ...headersToRecord(fetchInit.headers),
  };

  let res: Response;
  try {
    res = await fetch(url, {
      ...fetchInit,
      headers,
      signal,
    });
  } catch (e) {
    if (e instanceof Error && e.name === "AbortError") {
      throw new ApiError("Request timeout", 408, "TIMEOUT");
    }
    throw new ApiError(
      e instanceof Error ? e.message : String(e),
      0,
      "NETWORK_ERROR",
      e,
    );
  }

  const text = await res.text();
  if (!res.ok) {
    const parsed = parseErrorBody(text);
    throw new ApiError(
      parsed.message ?? `API error ${res.status}`,
      res.status,
      parsed.code,
      parsed.detail,
    );
  }

  if (text.trim() === "") {
    throw new ApiError("Empty response body", res.status, "EMPTY_RESPONSE");
  }

  return safeJson<T>(text);
}

/**
 * Fetch response as text (e.g. CSV). Uses same timeout and error handling as requestJson.
 */
export async function requestText(
  path: string,
  init: RequestInit & { query?: Record<string, string>; config?: RequestConfig } = {},
): Promise<string> {
  const { query, config = {}, ...fetchInit } = init;
  const timeoutMs = config.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const signal = config.signal
    ? withTimeout(timeoutMs, config.signal)
    : undefined;
  const url = buildUrl(path, query);
  const headers: Record<string, string> = {
    ...DEFAULT_HEADERS,
    ...config.headers,
    ...headersToRecord(fetchInit.headers),
  };

  let res: Response;
  try {
    res = await fetch(url, {
      ...fetchInit,
      headers,
      signal,
    });
  } catch (e) {
    if (e instanceof Error && e.name === "AbortError") {
      throw new ApiError("Request timeout", 408, "TIMEOUT");
    }
    throw new ApiError(
      e instanceof Error ? e.message : String(e),
      0,
      "NETWORK_ERROR",
      e,
    );
  }

  const text = await res.text();
  if (!res.ok) {
    const parsed = parseErrorBody(text);
    throw new ApiError(
      parsed.message ?? `API error ${res.status}`,
      res.status,
      parsed.code,
      parsed.detail,
    );
  }
  return text;
}

/**
 * Fetch binary response (e.g. PDF) and return Blob.
 */
export async function requestBlob(
  path: string,
  init: RequestInit & { query?: Record<string, string>; config?: RequestConfig } = {},
): Promise<{ blob: Blob; filename: string | null }> {
  const { query, config = {}, ...fetchInit } = init;
  const timeoutMs = config.timeoutMs ?? 60_000;
  const signal = config.signal
    ? withTimeout(timeoutMs, config.signal)
    : undefined;
  const url = buildUrl(path, query);
  const headers: Record<string, string> = {
    Accept: "application/pdf",
    ...config.headers,
    ...headersToRecord(fetchInit.headers),
  };

  let res: Response;
  try {
    res = await fetch(url, {
      ...fetchInit,
      headers,
      signal,
    });
  } catch (e) {
    if (e instanceof Error && e.name === "AbortError") {
      throw new ApiError("Request timeout", 408, "TIMEOUT");
    }
    throw new ApiError(
      e instanceof Error ? e.message : String(e),
      0,
      "NETWORK_ERROR",
      e,
    );
  }

  if (!res.ok) {
    const text = await res.text();
    const parsed = parseErrorBody(text);
    throw new ApiError(
      parsed.message ?? `API error ${res.status}`,
      res.status,
      parsed.code,
      parsed.detail,
    );
  }

  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition");
  let filename: string | null = null;
  if (disposition) {
    const match = /filename="?([^";\n]+)"?/.exec(disposition);
    if (match) filename = match[1].trim();
  }
  return { blob, filename };
}
