"""End-to-end Phase 22 production acceptance through the stable Vercel origin."""

import hashlib
import os
from datetime import date
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    b"trailer\n<<>>\n"
    b"%%EOF\n"
)


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Set {name}")
    return value


def production_origin() -> str:
    raw = required("VERCEL_FRONTEND_URL").rstrip("/")
    parsed = urlsplit(raw)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path:
        raise RuntimeError("VERCEL_FRONTEND_URL must be an HTTPS origin without a path")
    return raw


def expect(response: httpx.Response, status: int = 200) -> httpx.Response:
    if response.status_code != status:
        raise RuntimeError(
            f"{response.request.method} {response.request.url.path}: "
            f"HTTP {response.status_code}, expected {status}; {response.text[:500]}"
        )
    return response


def etag(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Expected versioned JSON resource at {response.request.url.path}"
        ) from exc

    version = body.get("lock_version")
    if version is None:
        raise RuntimeError(
            f"Missing lock_version on {response.request.url.path}"
        )

    return f'"{version}"'


def verify_login_cookies(response: httpx.Response) -> None:
    cookies = response.headers.get_list("set-cookie")
    refresh = next((value for value in cookies if value.lower().startswith("sih_refresh=")), None)
    csrf = next((value for value in cookies if value.lower().startswith("sih_csrf=")), None)
    if refresh is None or csrf is None:
        raise RuntimeError("Login did not set both refresh and CSRF cookies")

    refresh_lower = refresh.lower()
    csrf_lower = csrf.lower()

    for marker in ("secure", "httponly", "samesite=strict", "path=/api/v1/auth"):
        if marker not in refresh_lower:
            raise RuntimeError(f"Refresh cookie is missing {marker}")

    for marker in ("secure", "samesite=strict", "path=/"):
        if marker not in csrf_lower:
            raise RuntimeError(f"CSRF cookie is missing {marker}")

    if "httponly" in csrf_lower:
        raise RuntimeError("CSRF cookie must remain readable by the frontend")


def main() -> None:
    origin = production_origin()
    email = required("PRODUCTION_ADMIN_EMAIL")
    password = required("PRODUCTION_ADMIN_PASSWORD")

    with httpx.Client(
        base_url=origin,
        headers={"Origin": origin, "Accept": "application/json"},
        timeout=60,
        follow_redirects=False,
    ) as client:
        # Authentication and same-origin strict-cookie contract.
        login = expect(
            client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )
        )
        verify_login_cookies(login)
        client.headers["Authorization"] = "Bearer " + login.json()["access_token"]
        client.headers["X-CSRF-Token"] = client.cookies["sih_csrf"]

        me = expect(client.get("/api/v1/auth/me"))
        me_etag = etag(me)
        user_id = me.json()["id"]

        original_refresh = client.cookies["sih_refresh"]
        refreshed = expect(client.post("/api/v1/auth/refresh"))
        if client.cookies["sih_refresh"] == original_refresh:
            raise RuntimeError("Refresh token did not rotate")
        client.headers["Authorization"] = "Bearer " + refreshed.json()["access_token"]
        client.headers["X-CSRF-Token"] = client.cookies["sih_csrf"]

        # Create/reuse a stable production laboratory.
        labs = expect(client.get("/api/v1/laboratories?page=1&page_size=100")).json()["items"]
        lab = next((item for item in labs if item["code"] == "SIH26035-PROD"), None)
        if lab is None:
            lab = expect(
                client.post(
                    "/api/v1/laboratories",
                    json={
                        "name": "SIH26035 Production Laboratory",
                        "code": "SIH26035-PROD",
                        "address_line1": "Production acceptance environment",
                        "address_line2": "",
                        "city": "Ghaziabad",
                        "state": "Uttar Pradesh",
                        "postal_code": "201009",
                        "country": "India",
                        "phone": "0000000000",
                        "email": "laboratory@example.com",
                        "accreditation_no": "SIH26035-DEMO",
                        "timezone": "Asia/Kolkata",
                    },
                ),
                201,
            ).json()
        lab_id = lab["id"]

        # Explicitly grant operational lab authority; global ADMIN alone remains insufficient.
        roles = expect(client.get("/api/v1/roles?page=1&page_size=100")).json()["items"]
        role_ids = {item["code"]: item["id"] for item in roles}

        def active_assignments():
            return expect(
                client.get(
                    f"/api/v1/users/{user_id}/role-assignments?page=1&page_size=100"
                )
            ).json()["items"]

        for role_code in ("LAB_ENGINEER", "REVIEWER", "APPROVING_OFFICER"):
            assignments = active_assignments()
            if any(
                item["laboratory_id"] == lab_id
                and item["role_id"] == role_ids[role_code]
                and item["revoked_at"] is None
                for item in assignments
            ):
                continue
            users = expect(
                client.get(
                    "/api/v1/users",
                    params={
                        "search": email,
                        "page": 1,
                        "page_size": 20,
                    },
                )
            ).json()["items"]

            matches = [
                item
                for item in users
                if item["id"] == user_id
            ]
            if len(matches) != 1:
                raise RuntimeError(
                    "Could not resolve the current target user version"
                )

            me_etag = f'"{matches[0]["lock_version"]}"'
            expect(
                client.post(
                    f"/api/v1/users/{user_id}/role-assignments",
                    headers={"If-Match": me_etag},
                    json={
                        "role_code": role_code,
                        "scope_type": "LABORATORY",
                        "laboratory_id": lab_id,
                    },
                ),
                201,
            )

        expect(client.get(f"/api/v1/dashboard/summary?laboratory_id={lab_id}"))

        # Register/reuse the trusted candidate artifact. Never activate it: production
        # regulatory blockers must remain authoritative.
        rulesets = expect(client.get("/api/v1/rulesets?page=1&page_size=100")).json()["items"]
        ruleset = next(
            (
                item
                for item in rulesets
                if item.get("standard_code") == "OIML R 76-1"
                or item.get("edition") == "2006"
            ),
            None,
        )
        if ruleset is None:
            ruleset = expect(
                client.post(
                    "/api/v1/rulesets",
                    json={"artifact": "oiml_r76_2006/candidate-v1"},
                ),
                201,
            ).json()
        ruleset_id = ruleset["id"]

        # Master data.
        manufacturers = expect(
            client.get(
                f"/api/v1/manufacturers?laboratory_id={lab_id}"
                "&search=Stage%205%20Acceptance&page=1&page_size=100"
            )
        ).json()["items"]
        manufacturer = next(
            (item for item in manufacturers if item["name"] == "Stage 5 Acceptance Manufacturer"),
            None,
        )
        if manufacturer is None:
            manufacturer_response = expect(
                client.post(
                    "/api/v1/manufacturers",
                    json={
                        "laboratory_id": lab_id,
                        "name": "Stage 5 Acceptance Manufacturer",
                        "address": {
                            "address_line1": "Synthetic production acceptance fixture",
                            "country": "India",
                        },
                    },
                ),
                201,
            )
            manufacturer = manufacturer_response.json()

        instruments = expect(
            client.get(
                f"/api/v1/instruments?laboratory_id={lab_id}"
                "&search=Stage%205%20Acceptance%20Scale&page=1&page_size=100"
            )
        ).json()["items"]
        instrument = next(
            (item for item in instruments if item["model_name"] == "Stage 5 Acceptance Scale"),
            None,
        )
        if instrument is None:
            instrument_response = expect(
                client.post(
                    "/api/v1/instruments",
                    json={
                        "laboratory_id": lab_id,
                        "manufacturer_id": manufacturer["id"],
                        "model_name": "Stage 5 Acceptance Scale",
                        "accuracy_class": "III",
                        "range_type": "SINGLE",
                        "indication_type": "DIGITAL",
                        "max_capacity_g": "20000",
                        "min_capacity_g": "0",
                        "verification_interval_e_g": "10",
                        "scale_interval_d_g": "10",
                    },
                ),
                201,
            )
            instrument = instrument_response.json()
            expect(
                client.post(
                    f"/api/v1/instruments/{instrument['id']}/ranges",
                    headers={"If-Match": etag(instrument_response)},
                    json={
                        "range_no": 1,
                        "max_capacity_g": "20000",
                        "min_capacity_g": "0",
                        "verification_interval_e_g": "10",
                        "scale_interval_d_g": "10",
                    },
                ),
                201,
            )

        
        # Reconcile the explicit instrument range on every acceptance run.
        # This also repairs a fixture left partially created by an interrupted run.
        ranges = expect(
            client.get(
                f"/api/v1/instruments/{instrument['id']}/ranges",
                params={
                    "page": 1,
                    "page_size": 100,
                },
            )
        ).json()["items"]

        if not any(
            item["range_no"] == 1 and item["is_active"]
            for item in ranges
        ):
            current_instrument = expect(
                client.get(
                    f"/api/v1/instruments/{instrument['id']}"
                )
            )

            expect(
                client.post(
                    f"/api/v1/instruments/{instrument['id']}/ranges",
                    headers={
                        "If-Match": etag(current_instrument),
                    },
                    json={
                        "range_no": 1,
                        "max_capacity_g": "20000",
                        "min_capacity_g": "0",
                        "verification_interval_e_g": "10",
                        "scale_interval_d_g": "10",
                    },
                ),
                201,
            )

        manufacturer_detail = expect(
            client.get(f"/api/v1/manufacturers/{manufacturer['id']}")
        )

        # Real Vercel-origin -> S3 browser preflight and versioned evidence lifecycle.
        digest = hashlib.sha256(PDF).hexdigest()
        presign = expect(
            client.post(
                "/api/v1/attachments/presign",
                headers={"If-Match": etag(manufacturer_detail)},
                json={
                    "laboratory_id": lab_id,
                    "entity_type": "manufacturers",
                    "entity_id": manufacturer["id"],
                    "purpose": "stage5_acceptance",
                    "file_name": "stage5-acceptance.pdf",
                    "content_type": "application/pdf",
                    "file_size": len(PDF),
                    "sha256": digest,
                },
            ),
            201,
        ).json()

        with httpx.Client(timeout=60, follow_redirects=False, trust_env=False) as storage_client:
            preflight = storage_client.options(
                presign["upload_url"],
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "PUT",
                    "Access-Control-Request-Headers": "content-type",
                },
            )
            if preflight.status_code not in (200, 204):
                raise RuntimeError(
                    f"S3 browser CORS preflight failed with HTTP {preflight.status_code}"
                )
            if preflight.headers.get("access-control-allow-origin") != origin:
                raise RuntimeError("S3 CORS did not allow the exact Vercel production origin")

            upload_headers = {
                key: value
                for key, value in presign["headers"].items()
                if key.lower() != "content-length"
            }
            upload_headers["Origin"] = origin
            expect(
                storage_client.put(
                    presign["upload_url"],
                    content=PDF,
                    headers=upload_headers,
                )
            )

        finalized = expect(
            client.post(
                "/api/v1/attachments/complete",
                headers={"If-Match": etag(manufacturer_detail)},
                json={"upload_id": presign["upload_id"]},
            ),
            201,
        ).json()

        download = expect(
            client.get(f"/api/v1/attachments/{finalized['id']}/download")
        ).json()
        with httpx.Client(timeout=60, follow_redirects=False, trust_env=False) as storage_client:
            downloaded = expect(storage_client.get(download["download_url"])).content
        if downloaded != PDF or hashlib.sha256(downloaded).hexdigest() != digest:
            raise RuntimeError("Production evidence download integrity verification failed")

        # Candidate evaluation and regulatory safety gate.
        application_number = f"STAGE5-{uuid4().hex[:12].upper()}"
        created = expect(
            client.post(
                "/api/v1/test-sessions",
                headers={"Idempotency-Key": uuid4().hex},
                json={
                    "instrument_id": instrument["id"],
                    "rule_set_id": ruleset_id,
                    "application_number": application_number,
                    "evaluation_context": "INITIAL_VERIFICATION",
                },
            ),
            201,
        )
        session = created.json()
        session_id = session["id"]

        sections = expect(
            client.get(f"/api/v1/test-sessions/{session_id}/sections")
        ).json()
        if len(sections) != 17:
            raise RuntimeError(f"Expected 17 session sections, found {len(sections)}")

        configured = expect(
            client.post(
                f"/api/v1/test-sessions/{session_id}/configure",
                headers={"If-Match": etag(created)},
                json={"instrument_snapshot": session["instrument_snapshot"]},
            )
        )

        applicability = expect(
            client.post(f"/api/v1/test-sessions/{session_id}/applicability")
        ).json()
        if applicability.get("confirmable") is not False:
            raise RuntimeError("Candidate ruleset unexpectedly became confirmable")

        blocked = client.post(
            f"/api/v1/test-sessions/{session_id}/confirm-applicability",
            headers={"If-Match": etag(configured)},
            json={"elections": {}},
        )
        expect(blocked, 409)
        if blocked.json().get("error", {}).get("code") != "TODO_REGULATORY_VALIDATION":
            raise RuntimeError("Candidate regulatory gate returned an unexpected error")

        # Governance/repository/history surfaces must be reachable, while official
        # progression remains blocked for this incomplete candidate session.
        expect(client.get(f"/api/v1/test-sessions/{session_id}/revisions"))
        expect(client.get(f"/api/v1/test-sessions/{session_id}/reviews"))
        expect(client.get(f"/api/v1/test-sessions/{session_id}/corrections"))
        expect(client.get(f"/api/v1/instruments/{instrument['id']}/history"))
        expect(client.get(f"/api/v1/reports?laboratory_id={lab_id}"))

        review_attempt = client.post(
            f"/api/v1/test-sessions/{session_id}/submit-for-review",
            headers={"If-Match": etag(configured)},
        )
        if review_attempt.status_code not in (409, 422):
            raise RuntimeError(
                "Incomplete candidate session unexpectedly allowed review submission"
            )

        # Unofficial previews are deliberately available before approval.
        # They must remain clearly non-official and carry no report number.
        preview = expect(
            client.post(
                f"/api/v1/test-sessions/{session_id}/report-previews",
                headers={"If-Match": etag(configured)},
            ),
            201,
        ).json()

        if preview["preview_status"] != "READY":
            raise RuntimeError(
                "Production unofficial report preview did not become READY"
            )

        preview_context = preview["preview_context_snapshot"]

        if preview_context.get("document_kind") != "UNOFFICIAL_PREVIEW":
            raise RuntimeError(
                "Preview was not explicitly marked UNOFFICIAL_PREVIEW"
            )

        preview_control = preview_context.get("document_control", {})

        if (
            preview_control.get("report_number") is not None
            or preview_control.get("revision_no") is not None
            or preview_control.get("report_status") != "UNOFFICIAL_PREVIEW"
        ):
            raise RuntimeError(
                "Unofficial preview contains official report identity"
            )

        # Official generation, unlike preview generation, must remain blocked
        # until the session is approved, complete and has a determined outcome.
        official_attempt = client.post(
            f"/api/v1/test-sessions/{session_id}/reports",
            headers={
                "If-Match": etag(configured),
                "Idempotency-Key": uuid4().hex,
            },
            json={
                "intended_issuer_id": user_id,
                "planned_issue_date": date.today().isoformat(),
            },
        )

        expect(official_attempt, 409)

        if (
            official_attempt.json()
            .get("error", {})
            .get("code")
            != "SESSION_NOT_READY_FOR_APPROVAL"
        ):
            raise RuntimeError(
                "Official report generation returned an unexpected gate"
            )

        # Final refresh rotation and logout.
        old_refresh = client.cookies["sih_refresh"]
        refreshed = expect(client.post("/api/v1/auth/refresh"))
        if client.cookies["sih_refresh"] == old_refresh:
            raise RuntimeError("Final refresh token did not rotate")
        client.headers["Authorization"] = "Bearer " + refreshed.json()["access_token"]
        client.headers["X-CSRF-Token"] = client.cookies["sih_csrf"]

        expect(client.post("/api/v1/auth/logout"), 204)
        client.headers.pop("Authorization", None)
        if client.get("/api/v1/auth/me").status_code != 401:
            raise RuntimeError("Logout did not invalidate the authenticated browser state")

    print("Phase 22 production acceptance: PASS")
    print("- Vercel same-origin login and secure strict cookies: PASS")
    print("- refresh rotation and logout: PASS")
    print("- explicit laboratory-scoped authorization: PASS")
    print("- dashboard and master data: PASS")
    print("- exact-origin S3 browser CORS preflight: PASS")
    print("- private versioned evidence upload/download integrity: PASS")
    print("- 17-section candidate evaluation creation: PASS")
    print("- append-only history/repository read surfaces: PASS")
    print("- TODO_REGULATORY_VALIDATION gate: PASS")
    print("- unofficial report preview generation: PASS")
    print("- official report generation correctly blocked: PASS")
    print("- no authoritative compliance outcome or official report was fabricated")


if __name__ == "__main__":
    main()
