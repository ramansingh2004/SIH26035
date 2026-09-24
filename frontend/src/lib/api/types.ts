export type ApiErrorBody = {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
    request_id?: string;
  };
};

export type ApiResponse<T> = {
  data: T;
  etag: string | null;
  requestId: string | null;
};

export type ApiRequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  etag?: string | null;
  idempotencyKey?: string | null;
  auth?: boolean;
  retryAuth?: boolean;
  signal?: AbortSignal;
};
