"""Phase 26 Stage 8 — repeatable SIH full-demo operator.

All mutations go through the public HTTP API. The script never imports database
models/repositories and never deletes regulatory history.

Commands:
    reset   Retire unfinished prior live-demo sessions and prepare a fresh V3
            session in TESTING, ready for the judge UI walkthrough.
    accept  Perform reset, complete all 17 sections, generate the full Stage 7
            PDF/DOCX pair, verify downloads, and prove official paths stay blocked.
    status  Show the newest Stage 8 live-demo session.

Secrets are read from environment variables or prompted securely and are never
printed or written to disk.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from scripts.seed_phase23_demo_foundation import (
    DemoUser,
    ensure_demo_user,
    ensure_lab,
    ensure_manufacturer,
    expect,
    login,
    resource_etag,
)

LAB_CODE = "SIH26035-DEMO"
ENGINEER_EMAIL = "demo.engineer@example.com"
ENGINEER_SPEC = DemoUser(
    "phase26_engineer",
    ENGINEER_EMAIL,
    "SIH Demo Engineer",
    "LAB_ENGINEER",
    "PHASE26_ENGINEER_PASSWORD",
)
V3_ARTIFACT = "sih26035_full_flow_demo_v3"
V3_VERSION = "SYNTHETIC_TEST_SIH26035_FULL_FLOW_V3"
LIVE_PREFIX = "SIH26035-FULL-DEMO-LIVE"
INSTRUMENT_MODEL = "SIH26035 V3 Full-Flow Demo - DEMO ONLY"
MUTABLE_WORKFLOWS = {
    "DRAFT",
    "INSTRUMENT_CONFIGURATION",
    "APPLICABILITY_CONFIRMED",
    "TESTING",
}
EXPECTED_REPORT_COUNTS = {
    "sections": 17,
    "runs": 23,
    "observations": 92,
    "environment_readings": 23,
    "equipment_links": 24,
    "results": 23,
    "construction_items": 8,
    "checklist": 27,
    "evidence_links": 85,
    "unique_evidence_attachments": 60,
}


def env_or_prompt(name: str, prompt: str, *, secret: bool = False) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    value = getpass.getpass(prompt) if secret else input(prompt)
    value = value.strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def password(name: str, prompt: str) -> str:
    value = env_or_prompt(name, prompt, secret=True)
    if not 12 <= len(value) <= 128:
        raise RuntimeError(f"{name} must contain 12-128 characters")
    return value


def _origin(raw: str, name: str) -> str:
    raw = raw.strip().rstrip("/")
    parsed = urlsplit(raw)
    loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if (
        not parsed.netloc
        or parsed.path
        or parsed.query
        or parsed.fragment
        or (parsed.scheme != "https" and not (parsed.scheme == "http" and loopback))
    ):
        raise RuntimeError(
            f"{name} must be an HTTPS origin, or HTTP only on localhost/127.0.0.1"
        )
    return raw


def api_origin() -> str:
    raw = (
        os.environ.get("PHASE26_DEMO_API_ORIGIN")
        or os.environ.get("VERCEL_FRONTEND_URL")
        or "http://127.0.0.1:8000"
    )
    return _origin(raw, "PHASE26_DEMO_API_ORIGIN")


def ui_origin(api: str) -> str:
    explicit = os.environ.get("PHASE26_DEMO_UI_ORIGIN")
    if explicit:
        return _origin(explicit, "PHASE26_DEMO_UI_ORIGIN")
    parsed = urlsplit(api)
    if parsed.hostname in {"localhost", "127.0.0.1", "::1"} and parsed.port == 8000:
        host = "127.0.0.1" if parsed.hostname != "::1" else "[::1]"
        return f"http://{host}:3000"
    return api


def canonical_snapshot() -> dict:
    path = (
        Path(__file__).resolve().parents[1]
        / "app/compliance/demo_artifacts/phase26_full_demo_v3_data.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    snapshot = payload.get("instrument_snapshot")
    if not isinstance(snapshot, dict):
        raise RuntimeError("Canonical V3 execution instrument is missing")
    if snapshot.get("software_identifier") != "SIH26035-V3-DEMO":
        raise RuntimeError("Unexpected canonical V3 execution instrument")
    return snapshot


def exact_user(client: httpx.Client, email: str) -> dict | None:
    rows = expect(
        client.get(
            "/api/v1/users",
            params={"search": email, "page": 1, "page_size": 100},
        )
    ).json()["items"]
    matches = [row for row in rows if row["email"].lower() == email.lower()]
    if len(matches) > 1:
        raise RuntimeError(f"Multiple users matched {email}")
    return matches[0] if matches else None


def reset_engineer_password(
    client: httpx.Client,
    user: dict,
    replacement: str,
) -> dict:
    expect(
        client.post(
            f"/api/v1/users/{user['id']}/reset-password",
            headers={"If-Match": resource_etag(user)},
            json={"new_password": replacement},
        ),
        204,
    )
    refreshed = exact_user(client, user["email"])
    if refreshed is None:
        raise RuntimeError("Demo engineer disappeared after password reset")
    return refreshed


def ensure_v3_ruleset(client: httpx.Client) -> dict:
    rows = expect(
        client.get("/api/v1/rulesets", params={"page": 1, "page_size": 100})
    ).json()["items"]
    matches = [row for row in rows if row.get("version") == V3_VERSION]
    if len(matches) > 1:
        raise RuntimeError("Multiple V3 full-demo rulesets exist")
    if matches:
        ruleset = matches[0]
    else:
        ruleset = expect(
            client.post(
                "/api/v1/rulesets",
                json={"artifact": V3_ARTIFACT},
            ),
            201,
        ).json()

    if ruleset.get("ruleset_status") != "DRAFT":
        raise RuntimeError("V3 synthetic demo ruleset must remain DRAFT")
    summary = ruleset.get("validation_summary") or {}
    if summary.get("synthetic_demo_only") is not True:
        raise RuntimeError("V3 synthetic demo-only marker is missing")
    return ruleset


def instrument_payload(
    laboratory_id: str,
    manufacturer_id: str,
    snapshot: dict,
) -> dict:
    metadata_keys = (
        "is_direct_sales",
        "is_price_computing",
        "is_labeling",
        "data_storage_device_present",
        "printing_device_present",
        "extended_indication_available",
        "embedded_software_present",
        "loadable_software_present",
        "interfaces",
        "peripherals",
        "battery_charging_during_operation",
        "vehicle_powered",
        "conducted_rf_path_available",
        "vehicle_power_details",
        "declared_operating_conditions",
        "declared_installation",
    )
    return {
        "laboratory_id": laboratory_id,
        "manufacturer_id": manufacturer_id,
        "model_name": INSTRUMENT_MODEL,
        "type_designation": "V3 synthetic software exercise matrix",
        "serial_number": "SIH26035-V3-DEMO-001",
        "accuracy_class": snapshot["accuracy_class"],
        "range_type": snapshot["range_type"],
        "indication_type": snapshot["indication_type"],
        "is_self_indicating": snapshot["is_self_indicating"],
        "is_electronic": snapshot["is_electronic"],
        "is_software_controlled": snapshot["is_software_controlled"],
        "is_portable": snapshot["is_portable"],
        "is_mobile": snapshot["is_mobile"],
        "load_receptor_type": snapshot["load_receptor_type"],
        "support_point_count": snapshot["support_point_count"],
        "tare_type": snapshot["tare_type"],
        "maximum_tare_g": snapshot["maximum_tare_g"],
        "zero_setting_type": snapshot["zero_setting_type"],
        "zero_tracking_available": snapshot["zero_tracking_available"],
        "level_indicator_available": snapshot["level_indicator_available"],
        "automatic_tilt_sensor": snapshot["automatic_tilt_sensor"],
        "power_supply_type": snapshot["power_supply_type"],
        "nominal_voltage": snapshot["nominal_voltage"],
        "min_voltage": snapshot["min_voltage"],
        "max_voltage": snapshot["max_voltage"],
        "declared_temp_min_c": snapshot["declared_temp_min_c"],
        "declared_temp_max_c": snapshot["declared_temp_max_c"],
        "software_identifier": snapshot["software_identifier"],
        "min_capacity_g": snapshot["min_capacity_g"],
        "max_capacity_g": snapshot["max_capacity_g"],
        "verification_interval_e_g": snapshot["verification_interval_e_g"],
        "scale_interval_d_g": snapshot["scale_interval_d_g"],
        "metadata_json": {
            key: snapshot.get(key)
            for key in metadata_keys
        },
    }


def ensure_v3_instrument(
    client: httpx.Client,
    laboratory_id: str,
    manufacturer_id: str,
    snapshot: dict,
) -> dict:
    rows = expect(
        client.get(
            "/api/v1/instruments",
            params={
                "laboratory_id": laboratory_id,
                "search": INSTRUMENT_MODEL,
                "page": 1,
                "page_size": 100,
            },
        )
    ).json()["items"]
    matches = [
        row
        for row in rows
        if row.get("model_name") == INSTRUMENT_MODEL
        and row.get("instrument_status") == "ACTIVE"
    ]
    if len(matches) > 1:
        raise RuntimeError("Multiple active Stage 8 V3 demo instruments exist")

    if matches:
        instrument = expect(
            client.get(f"/api/v1/instruments/{matches[0]['id']}")
        ).json()
    else:
        instrument = expect(
            client.post(
                "/api/v1/instruments",
                json=instrument_payload(
                    laboratory_id,
                    manufacturer_id,
                    snapshot,
                ),
            ),
            201,
        ).json()

    # A dedicated single range keeps the master-data page aligned with the
    # canonical V3 evaluation snapshot used by Stage 6.
    ranges = expect(
        client.get(
            f"/api/v1/instruments/{instrument['id']}/ranges",
            params={"page": 1, "page_size": 100},
        )
    ).json()["items"]
    range_one = next(
        (
            row
            for row in ranges
            if row.get("range_no") == 1 and row.get("is_active") is True
        ),
        None,
    )
    if range_one is None:
        current = expect(
            client.get(f"/api/v1/instruments/{instrument['id']}")
        ).json()
        canonical_range = snapshot["ranges"][0]
        expect(
            client.post(
                f"/api/v1/instruments/{instrument['id']}/ranges",
                headers={"If-Match": resource_etag(current)},
                json={
                    "range_no": 1,
                    "min_capacity_g": canonical_range["min_capacity_g"],
                    "max_capacity_g": canonical_range["max_capacity_g"],
                    "verification_interval_e_g": canonical_range[
                        "verification_interval_e_g"
                    ],
                    "scale_interval_d_g": canonical_range["scale_interval_d_g"],
                },
            ),
            201,
        )

    instrument = expect(
        client.get(f"/api/v1/instruments/{instrument['id']}")
    ).json()
    for field in (
        "accuracy_class",
        "max_capacity_g",
        "min_capacity_g",
        "verification_interval_e_g",
        "scale_interval_d_g",
        "maximum_tare_g",
        "software_identifier",
    ):
        if str(instrument.get(field)) != str(snapshot.get(field)):
            raise RuntimeError(
                f"Stage 8 master instrument mismatch for {field}: "
                f"{instrument.get(field)!r} != {snapshot.get(field)!r}"
            )
    return instrument


def live_sessions(client: httpx.Client, laboratory_id: str) -> list[dict]:
    page = expect(
        client.get(
            "/api/v1/test-sessions",
            params={
                "laboratory_id": laboratory_id,
                "search": LIVE_PREFIX,
                "page": 1,
                "page_size": 100,
            },
        )
    ).json()
    return [
        row
        for row in page["items"]
        if str(row.get("application_number") or "").startswith(LIVE_PREFIX)
    ]


def retire_unfinished(client: httpx.Client, laboratory_id: str) -> int:
    retired = 0
    for row in live_sessions(client, laboratory_id):
        if row.get("workflow_status") not in MUTABLE_WORKFLOWS:
            continue
        current = expect(
            client.get(f"/api/v1/test-sessions/{row['id']}")
        ).json()
        expect(
            client.post(
                f"/api/v1/test-sessions/{row['id']}/cancel",
                headers={"If-Match": resource_etag(current)},
                json={
                    "reason": (
                        "Phase 26 Stage 8 demo reset: preserve history and "
                        "replace unfinished live-demo session."
                    )
                },
            )
        )
        retired += 1
    return retired


def fresh_application_number() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"{LIVE_PREFIX}-{timestamp}-{uuid4().hex[:6].upper()}"


def prepare_live_session(
    client: httpx.Client,
    laboratory_id: str,
    instrument: dict,
    ruleset: dict,
    snapshot: dict,
) -> dict:
    application_number = fresh_application_number()
    session = expect(
        client.post(
            "/api/v1/test-sessions",
            headers={"Idempotency-Key": uuid4().hex},
            json={
                "instrument_id": instrument["id"],
                "rule_set_id": ruleset["id"],
                "evaluation_context": "SYNTHETIC",
                "application_number": application_number,
                "notes": (
                    "SYNTHETIC SIH26035 PHASE 26 STAGE 8 LIVE DEMO ONLY. "
                    "Not regulatory evidence and not an official OIML evaluation."
                ),
            },
        ),
        201,
    ).json()

    session = expect(
        client.post(
            f"/api/v1/test-sessions/{session['id']}/configure",
            headers={"If-Match": resource_etag(session)},
            json={"instrument_snapshot": snapshot},
        )
    ).json()

    applicability = expect(
        client.post(
            f"/api/v1/test-sessions/{session['id']}/applicability"
        )
    ).json()
    if applicability.get("confirmable") is not True:
        raise RuntimeError("V3 Stage 8 applicability is not confirmable")
    if len(applicability.get("plan", [])) != 28:
        raise RuntimeError("V3 Stage 8 applicability must contain 28 slots")

    session = expect(
        client.post(
            f"/api/v1/test-sessions/{session['id']}/confirm-applicability",
            headers={"If-Match": resource_etag(session)},
            json={"elections": {}},
        )
    ).json()
    session = expect(
        client.post(
            f"/api/v1/test-sessions/{session['id']}/start-testing",
            headers={"If-Match": resource_etag(session)},
        )
    ).json()

    dashboard = expect(
        client.get(f"/api/v1/test-sessions/{session['id']}/dashboard")
    ).json()
    if session.get("workflow_status") != "TESTING":
        raise RuntimeError("Fresh Stage 8 session did not enter TESTING")
    if len(dashboard.get("sections", [])) != 17:
        raise RuntimeError("Fresh Stage 8 session does not expose all 17 sections")
    requirements = dashboard.get("requirements", [])
    if len(requirements) != 28:
        raise RuntimeError("Fresh Stage 8 session does not expose all 28 requirements")
    selected = [row for row in requirements if row.get("selected_run_id")]
    if len(selected) != 23:
        raise RuntimeError("Fresh Stage 8 session must have 23 selected executable runs")
    return session


def find_latest(client: httpx.Client, laboratory_id: str) -> dict:
    rows = live_sessions(client, laboratory_id)
    if not rows:
        raise RuntimeError("No Phase 26 Stage 8 live-demo session exists")
    rows.sort(
        key=lambda row: (
            row.get("created_at") or "",
            row.get("application_number") or "",
        ),
        reverse=True,
    )
    return expect(
        client.get(f"/api/v1/test-sessions/{rows[0]['id']}")
    ).json()


def verify_complete_dashboard(client: httpx.Client, session_id: str) -> dict:
    dashboard = expect(
        client.get(f"/api/v1/test-sessions/{session_id}/dashboard")
    ).json()
    session = dashboard["session"]
    sections = dashboard["sections"]
    if (
        session.get("workflow_status") != "EXAMINATION"
        or session.get("evaluation_status") != "COMPLETE"
        or session.get("compliance_outcome") != "COMPLIANT"
    ):
        raise RuntimeError("Stage 8 completed session state is incorrect")
    if len(sections) != 17:
        raise RuntimeError("Stage 8 completed session must expose 17 sections")
    if any(
        row.get("applicability_status") != "REQUIRED"
        or row.get("evaluation_status") != "COMPLETE"
        or row.get("compliance_outcome") != "COMPLIANT"
        for row in sections
    ):
        raise RuntimeError("Stage 8 requires 17 REQUIRED COMPLETE COMPLIANT sections")
    return dashboard


def _download_allowed(url: str) -> bool:
    parsed = urlsplit(url)
    return parsed.scheme == "https" or (
        parsed.scheme == "http"
        and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    )


def generate_and_verify_report(
    client: httpx.Client,
    session: dict,
) -> dict:
    preview = expect(
        client.post(
            f"/api/v1/test-sessions/{session['id']}/full-demo-report-previews",
            headers={"If-Match": resource_etag(session)},
        ),
        201,
    ).json()
    if preview.get("preview_status") != "READY":
        raise RuntimeError(
            f"Stage 7 report is not READY: {preview.get('error_code')}"
        )

    context = preview.get("preview_context_snapshot") or {}
    if context.get("document_kind") != "FULL_DEMO_REPORT":
        raise RuntimeError("Stage 8 did not receive FULL_DEMO_REPORT")
    demonstration = context.get("demonstration") or {}
    if demonstration.get("source_counts") != EXPECTED_REPORT_COUNTS:
        raise RuntimeError(
            f"Stage 8 report source counts mismatch: "
            f"{demonstration.get('source_counts')}"
        )
    if demonstration.get("not_an_official_oiml_certificate") is not True:
        raise RuntimeError("Stage 8 report lost its non-official certificate marker")

    for file_format, signature in (("pdf", b"%PDF-"), ("docx", b"PK")):
        metadata = expect(
            client.get(
                f"/api/v1/report-previews/{preview['id']}/download",
                params={"format": file_format},
            )
        ).json()
        url = metadata.get("download_url")
        if not isinstance(url, str) or not _download_allowed(url):
            raise RuntimeError(f"Unsafe or invalid {file_format} download URL")

        with httpx.Client(timeout=120, follow_redirects=True) as downloader:
            body_response = expect(downloader.get(url))
            body = body_response.content
        if not body.startswith(signature):
            raise RuntimeError(f"Downloaded Stage 8 {file_format} signature is invalid")
        if hashlib.sha256(body).hexdigest() != metadata.get("sha256"):
            raise RuntimeError(f"Downloaded Stage 8 {file_format} SHA-256 mismatch")

    return preview


def verify_official_paths_blocked(
    client: httpx.Client,
    session: dict,
    actor_id: str,
    laboratory_id: str,
) -> None:
    current = expect(
        client.get(f"/api/v1/test-sessions/{session['id']}")
    ).json()
    review = client.post(
        f"/api/v1/test-sessions/{session['id']}/submit-for-review",
        headers={"If-Match": resource_etag(current)},
    )
    if review.status_code != 409 or (
        review.json().get("error", {}).get("code")
        != "SYNTHETIC_DEMO_OFFICIAL_FORBIDDEN"
    ):
        raise RuntimeError(f"Synthetic review guard failed: {review.text[:700]}")

    current = expect(
        client.get(f"/api/v1/test-sessions/{session['id']}")
    ).json()
    official = client.post(
        f"/api/v1/test-sessions/{session['id']}/reports",
        headers={
            "If-Match": resource_etag(current),
            "Idempotency-Key": uuid4().hex,
        },
        json={
            "intended_issuer_id": actor_id,
            "planned_issue_date": date.today().isoformat(),
        },
    )
    if official.status_code != 409 or (
        official.json().get("error", {}).get("code")
        != "SYNTHETIC_DEMO_OFFICIAL_FORBIDDEN"
    ):
        raise RuntimeError(f"Synthetic official-report guard failed: {official.text[:700]}")

    repository = expect(
        client.get(
            "/api/v1/reports",
            params={
                "laboratory_id": laboratory_id,
                "page": 1,
                "page_size": 100,
            },
        )
    ).json()
    if any(
        row.get("test_session_id") == session["id"]
        for row in repository.get("items", [])
    ):
        raise RuntimeError("Synthetic Stage 8 session entered official report repository")


def admin_and_engineer_credentials() -> tuple[str, str, str]:
    admin_email = (
        os.environ.get("PHASE26_ADMIN_EMAIL")
        or os.environ.get("PRODUCTION_ADMIN_EMAIL")
        or ""
    ).strip()
    if not admin_email:
        admin_email = env_or_prompt(
            "PHASE26_ADMIN_EMAIL",
            "Administrator email: ",
        )
    admin_password = password(
        "PHASE26_ADMIN_PASSWORD"
        if os.environ.get("PHASE26_ADMIN_PASSWORD")
        else "PRODUCTION_ADMIN_PASSWORD",
        "Administrator password: ",
    )
    engineer_password = password(
        "PHASE26_ENGINEER_PASSWORD"
        if os.environ.get("PHASE26_ENGINEER_PASSWORD")
        else "PHASE23_ENGINEER_PASSWORD",
        "SIH Demo Engineer password: ",
    )
    return admin_email, admin_password, engineer_password


def bootstrap(
    client: httpx.Client,
    admin_email: str,
    admin_password: str,
    engineer_password: str,
) -> tuple[dict, dict, dict, dict, dict]:
    login(client, admin_email, admin_password)
    lab = ensure_lab(client)

    roles = expect(
        client.get("/api/v1/roles", params={"page": 1, "page_size": 100})
    ).json()["items"]
    role_ids = {row["code"]: row["id"] for row in roles}

    engineer = ensure_demo_user(
        client,
        ENGINEER_SPEC,
        engineer_password,
        lab["id"],
        role_ids,
    )
    engineer = reset_engineer_password(client, engineer, engineer_password)

    ruleset = ensure_v3_ruleset(client)
    snapshot = canonical_snapshot()

    # Master-data mutations are owned by the lab engineer. Global ADMIN is
    # deliberately not a laboratory regulatory/master-data wildcard.
    me = login(client, ENGINEER_EMAIL, engineer_password)
    scope = next(
        (
            item
            for item in me.get("laboratories", [])
            if item.get("laboratory_id") == lab["id"]
        ),
        None,
    )
    if scope is None or "LAB_ENGINEER" not in scope.get("roles", []):
        raise RuntimeError("Demo engineer lacks LAB_ENGINEER in SIH26035-DEMO")

    manufacturer = ensure_manufacturer(client, lab["id"])
    instrument = ensure_v3_instrument(
        client,
        lab["id"],
        manufacturer["id"],
        snapshot,
    )
    return lab, engineer, ruleset, instrument, snapshot


def print_ready(
    api: str,
    ui: str,
    lab: dict,
    session: dict,
    retired: int,
) -> None:
    print("Phase 26 Stage 8 demo reset: PASS")
    print(f"- API origin: {api}")
    print(f"- demo laboratory: {lab['code']}")
    print(f"- retired unfinished prior live-demo sessions: {retired}")
    print(f"- fresh application: {session['application_number']}")
    print(f"- fresh session id: {session['id']}")
    print("- workflow: TESTING")
    print("- applicability slots: 28 REQUIRED")
    print("- selected executable runs: 23")
    print("- UI sections available: 17")
    print(f"- engineer login: {ENGINEER_EMAIL}")
    print(f"- judge URL: {ui}/evaluations/{session['id']}")
    print("- password was not printed or stored")
    print("- next UI action: Complete all 17 synthetic demo sections")


def command_reset(client: httpx.Client, api: str, ui: str) -> dict:
    admin_email, admin_password, engineer_password = admin_and_engineer_credentials()
    lab, engineer, ruleset, instrument, snapshot = bootstrap(
        client,
        admin_email,
        admin_password,
        engineer_password,
    )
    retired = retire_unfinished(client, lab["id"])
    session = prepare_live_session(
        client,
        lab["id"],
        instrument,
        ruleset,
        snapshot,
    )
    print_ready(api, ui, lab, session, retired)
    return {
        "lab": lab,
        "engineer": engineer,
        "session": session,
        "engineer_password": engineer_password,
    }


def command_status(client: httpx.Client, api: str, ui: str) -> None:
    engineer_password = password(
        "PHASE26_ENGINEER_PASSWORD"
        if os.environ.get("PHASE26_ENGINEER_PASSWORD")
        else "PHASE23_ENGINEER_PASSWORD",
        "SIH Demo Engineer password: ",
    )
    login(client, ENGINEER_EMAIL, engineer_password)
    labs = expect(
        client.get("/api/v1/laboratories", params={"page": 1, "page_size": 100})
    ).json()["items"]
    lab = next((row for row in labs if row.get("code") == LAB_CODE), None)
    if lab is None:
        raise RuntimeError("SIH26035-DEMO laboratory is not provisioned")
    session = find_latest(client, lab["id"])
    print("Phase 26 Stage 8 status")
    print(f"- application: {session['application_number']}")
    print(f"- session id: {session['id']}")
    print(f"- workflow: {session['workflow_status']}")
    print(f"- evaluation: {session['evaluation_status']}")
    print(f"- outcome: {session['compliance_outcome']}")
    print(f"- judge URL: {ui}/evaluations/{session['id']}")


def command_accept(client: httpx.Client, api: str, ui: str) -> None:
    state = command_reset(client, api, ui)
    session = state["session"]
    lab = state["lab"]
    engineer = state["engineer"]

    completed = expect(
        client.post(
            f"/api/v1/test-sessions/{session['id']}/demo-complete-evaluation",
            headers={"If-Match": resource_etag(session)},
        )
    ).json()
    session = completed["session"]
    verify_complete_dashboard(client, session["id"])

    current = expect(
        client.get(f"/api/v1/test-sessions/{session['id']}")
    ).json()
    preview = generate_and_verify_report(client, current)
    verify_official_paths_blocked(
        client,
        current,
        engineer["id"],
        lab["id"],
    )

    print("")
    print("Phase 26 Stage 8 final SIH acceptance: PASS")
    print("- public-API reset/seed path: PASS")
    print("- 17/17 sections REQUIRED + COMPLETE + COMPLIANT: PASS")
    print("- 23 deterministic typed runs persisted: PASS")
    print("- Section 16 construction flow: PASS")
    print("- Section 17 checklist flow: PASS")
    print("- full Stage 7 PDF download + SHA-256: PASS")
    print("- full Stage 7 DOCX download + SHA-256: PASS")
    print("- report source: 85 evidence links / 60 unique attachments")
    print("- NOT AN OFFICIAL OIML CERTIFICATE marker: PASS")
    print("- technical review blocked for synthetic demo: PASS")
    print("- official report generation blocked for synthetic demo: PASS")
    print("- synthetic session absent from official report repository: PASS")
    print(f"- completed session: {ui}/evaluations/{session['id']}")
    print(f"- full-demo preview id: {preview['id']}")
    print("")
    print(
        "Run `uv run python -m scripts.phase26_demo reset` once more "
        "before judging to leave a fresh TESTING session ready for the UI."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SIH26035 Phase 26 final repeatable demo operator"
    )
    parser.add_argument(
        "command",
        choices=("reset", "accept", "status"),
        nargs="?",
        default="reset",
    )
    args = parser.parse_args()

    api = api_origin()
    ui = ui_origin(api)
    with httpx.Client(
        base_url=api,
        headers={
            "Origin": ui,
            "Accept": "application/json",
        },
        timeout=120,
        follow_redirects=False,
    ) as client:
        if args.command == "reset":
            command_reset(client, api, ui)
        elif args.command == "accept":
            command_accept(client, api, ui)
        else:
            command_status(client, api, ui)


if __name__ == "__main__":
    main()
