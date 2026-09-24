import { API_BASE_URL } from "@/lib/config";

import { apiErrorFromResponse } from "./errors";
import type { ApiRequestOptions, ApiResponse } from "./types";

type TokenView = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

let accessToken: string | null = null;
let refreshPromise: Promise<string | null> | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") {
    return null;
  }

  const prefix = `${encodeURIComponent(name)}=`;
  for (const raw of document.cookie.split(";")) {
    const value = raw.trim();
    if (value.startsWith(prefix)) {
      return decodeURIComponent(value.slice(prefix.length));
    }
  }
  return null;
}

function csrfToken(): string | null {
  return readCookie("sih_csrf");
}

function isMutation(method: string): boolean {
  return method === "POST" || method === "PATCH" || method === "DELETE";
}

async function rawRefresh(): Promise<string | null> {
  const csrf = csrfToken();
  if (!csrf) {
    setAccessToken(null);
    return null;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: {
        Accept: "application/json",
        "X-CSRF-Token": csrf,
      },
      cache: "no-store",
    });
  } catch {
    setAccessToken(null);
    return null;
  }

  if (!response.ok) {
    setAccessToken(null);
    return null;
  }

  const token = (await response.json()) as TokenView;
  setAccessToken(token.access_token);
  return token.access_token;
}

export async function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = rawRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<ApiResponse<T>> {
  const method = options.method ?? "GET";
  const auth = options.auth ?? true;
  const retryAuth = options.retryAuth ?? true;

  const headers = new Headers({
    Accept: "application/json",
  });

  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  if (auth && accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  if (options.etag) {
    headers.set("If-Match", options.etag);
  }

  if (options.idempotencyKey) {
    headers.set("Idempotency-Key", options.idempotencyKey);
  }

  const csrf = csrfToken();
  if (isMutation(method) && csrf) {
    headers.set("X-CSRF-Token", csrf);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      credentials: "include",
      headers,
      body:
        options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
      cache: "no-store",
    });
  } catch {
    throw new Error(`Unable to reach the SIH26035 API at ${API_BASE_URL}.`);
  }

  if (
    response.status === 401 &&
    auth &&
    retryAuth &&
    path !== "/api/v1/auth/refresh"
  ) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return apiRequest<T>(path, {
        ...options,
        retryAuth: false,
      });
    }
  }

  if (!response.ok) {
    throw await apiErrorFromResponse(response);
  }

  const data =
    response.status === 204 ? (undefined as T) : ((await response.json()) as T);

  return {
    data,
    etag: response.headers.get("ETag"),
    instrumentEtag: response.headers.get("X-Instrument-ETag"),
    requestId: response.headers.get("X-Request-ID"),
  };
}
