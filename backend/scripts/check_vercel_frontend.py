"""Verify the public Vercel frontend and same-origin API rewrite."""

import os
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def frontend_origin() -> str:
    raw = os.environ.get("VERCEL_FRONTEND_URL", "").strip().rstrip("/")
    if not raw:
        raise RuntimeError("Set VERCEL_FRONTEND_URL to the deployed HTTPS frontend origin")
    parsed = urlsplit(raw)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path:
        raise RuntimeError("VERCEL_FRONTEND_URL must be an HTTPS origin without a path")
    return raw


def request(path: str) -> tuple[int, bytes, dict[str, str]]:
    req = Request(
        f"{frontend_origin()}{path}",
        headers={"Accept": "application/json,text/html", "User-Agent": "SIH26035-vercel-check/1"},
    )
    try:
        with urlopen(req, timeout=30) as response:
            return response.status, response.read(), {
                key.lower(): value for key, value in response.headers.items()
            }
    except HTTPError as error:
        return error.code, error.read(), {
            key.lower(): value for key, value in error.headers.items()
        }


def main() -> None:
    login_status, login_body, _ = request("/login")
    if login_status != 200:
        raise RuntimeError(f"Vercel /login returned HTTP {login_status}")
    if not login_body:
        raise RuntimeError("Vercel /login returned an empty body")

    auth_status, _, auth_headers = request("/api/v1/auth/me")
    if auth_status != 401:
        raise RuntimeError(
            "Same-origin /api/v1 rewrite is not reaching the protected Render API"
        )
    if auth_headers.get("cache-control") != "no-store":
        raise RuntimeError("Proxied backend API response must remain no-store")

    print("Vercel frontend verification: PASS")
    print("- HTTPS login route: PASS")
    print("- same-origin /api/v1 rewrite: PASS")
    print("- Render authentication boundary through Vercel: PASS")
    print("- proxied no-store response policy: PASS")


if __name__ == "__main__":
    main()
