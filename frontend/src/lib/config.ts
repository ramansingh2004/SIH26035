function normalizedApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();

  if (!configured) {
    return "http://127.0.0.1:8000";
  }

  if (configured === "/") {
    return "";
  }

  return configured.replace(/\/+$/, "");
}

export const API_BASE_URL = normalizedApiBaseUrl();
