"""Verify the public Render service without requiring credentials."""

import json
import os
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def service_origin() -> str:
    raw = os.environ.get("RENDER_SERVICE_URL", "").strip().rstrip("/")
    if not raw:
        raise RuntimeError("Set RENDER_SERVICE_URL to the deployed HTTPS service origin")
    parsed = urlsplit(raw)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path:
        raise RuntimeError("RENDER_SERVICE_URL must be an HTTPS origin without a path")
    return raw


def request(path: str) -> tuple[int, bytes, dict[str, str]]:
    req = Request(
        f"{service_origin()}{path}",
        headers={"Accept": "application/json", "User-Agent": "SIH26035-deploy-check/1"},
    )
    try:
        with urlopen(req, timeout=20) as response:
            return response.status, response.read(), {
                key.lower(): value for key, value in response.headers.items()
            }
    except HTTPError as error:
        return error.code, error.read(), {
            key.lower(): value for key, value in error.headers.items()
        }


def main() -> None:
    status, body, headers = request("/health")
    if status != 200 or json.loads(body) != {"status": "ok"}:
        raise RuntimeError("Render /health verification failed")
    if headers.get("cache-control") != "no-store":
        raise RuntimeError("/health must be no-store")

    docs_status, _, _ = request("/docs")
    if docs_status != 404:
        raise RuntimeError("Production /docs must be disabled")

    openapi_status, _, _ = request("/openapi.json")
    if openapi_status != 404:
        raise RuntimeError("Production /openapi.json must be disabled")

    auth_status, _, auth_headers = request("/api/v1/auth/me")
    if auth_status != 401:
        raise RuntimeError("Unauthenticated /api/v1/auth/me must return HTTP 401")
    if auth_headers.get("cache-control") != "no-store":
        raise RuntimeError("API responses must be no-store")

    print("Render public service verification: PASS")
    print("- HTTPS health endpoint: PASS")
    print("- production docs disabled: PASS")
    print("- production OpenAPI disabled: PASS")
    print("- protected API authentication boundary: PASS")
    print("- no-store response policy: PASS")


if __name__ == "__main__":
    main()
