"""Create Phase 23 positive/negative synthetic SIH walkthrough scenarios.

The Stage 2 backend must be deployed before this script is run against production.
The script uses only the stable Vercel same-origin API and verifies that synthetic
demo records remain barred from regulatory review and official report generation.
"""

from __future__ import annotations

import getpass
import os
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

LAB_CODE = "SIH26035-DEMO"
INSTRUMENT_MODEL = "BPX-30K Class III — DEMO ONLY"
DEMO_ARTIFACT = "sih26035_demo_v1"

SCENARIOS = (
    ("SIH26035-DEMO-POSITIVE", "COMPLIANT", False),
    ("SIH26035-DEMO-NEGATIVE", "NONCOMPLIANT", True),
)


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Set {name}")
    return value


def secret(name: str, prompt: str) -> str:
    value = os.environ.get(name)
    if value is None:
        value = getpass.getpass(prompt)
    if not 12 <= len(value) <= 128:
        raise RuntimeError(f"{name} must contain 12-128 characters")
    return value


def production_origin() -> str:
    raw = os.environ.get(
        "VERCEL_FRONTEND_URL",
        "https://sih26035.vercel.app",
    ).strip().rstrip("/")
    parsed = urlsplit(raw)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path:
        raise RuntimeError("VERCEL_FRONTEND_URL must be an HTTPS origin without a path")
    return raw


def expect(response: httpx.Response, status: int = 200) -> httpx.Response:
    if response.status_code != status:
        raise RuntimeError(
            f"{response.request.method} {response.request.url.path}: "
            f"HTTP {response.status_code}, expected {status}; {response.text[:800]}"
        )
    return response


def etag(resource: dict) -> str:
    return f'"{resource["lock_version"]}"'


def login(client: httpx.Client, email: str, password: str) -> dict:
    response = expect(
        client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
    )
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    client.headers["X-CSRF-Token"] = client.cookies["sih_csrf"]
    return expect(client.get("/api/v1/auth/me")).json()


def find_lab(client: httpx.Client) -> dict:
    rows = expect(
        client.get(
            "/api/v1/laboratories",
            params={"page": 1, "page_size": 100},
        )
    ).json()["items"]
    result = next((row for row in rows if row["code"] == LAB_CODE), None)
    if result is None:
        raise RuntimeError("Run Phase 23 Stage 1 first; demo laboratory is missing")
    return result


def find_instrument(client: httpx.Client, lab_id: str) -> dict:
    rows = expect(
        client.get(
            "/api/v1/instruments",
            params={
                "laboratory_id": lab_id,
                "search": INSTRUMENT_MODEL,
                "page": 1,
                "page_size": 100,
            },
        )
    ).json()["items"]
    result = next((row for row in rows if row["model_name"] == INSTRUMENT_MODEL), None)
    if result is None:
        raise RuntimeError("Run Phase 23 Stage 1 first; demo instrument is missing")
    return result


def register_demo_ruleset(client: httpx.Client) -> dict:
    rows = expect(
        client.get(
            "/api/v1/rulesets",
            params={"page": 1, "page_size": 100},
        )
    ).json()["items"]
    existing = next(
        (
            row
            for row in rows
            if row.get("version") == "SYNTHETIC_TEST_SIH26035_DEMO_V1"
        ),
        None,
    )
    if existing is not None:
        return existing

    return expect(
        client.post(
            "/api/v1/rulesets",
            json={"artifact": DEMO_ARTIFACT},
        ),
        201,
    ).json()


def session_by_application(
    client: httpx.Client,
    lab_id: str,
    application: str,
) -> dict | None:
    rows = expect(
        client.get(
            "/api/v1/test-sessions",
            params={
                "laboratory_id": lab_id,
                "application_number": application,
                "page": 1,
                "page_size": 100,
            },
        )
    ).json()["items"]
    return next(
        (row for row in rows if row.get("application_number") == application),
        None,
    )


def observation_rows(*, failing: bool) -> list[dict]:
    values = [
        (1, "UP", "200", "200", "2000-01-01T00:00:01Z"),
        (
            2,
            "UP",
            "30000",
            "30030" if failing else "30000",
            "2000-01-01T00:00:02Z",
        ),
        (3, "DOWN", "30000", "30000", "2000-01-01T00:00:03Z"),
        (4, "DOWN", "200", "200", "2000-01-01T00:00:04Z"),
    ]
    rows = []
    for sequence, direction, load, indication, measured_at in values:
        rows.append(
            {
                "sequence_no": sequence,
                "observation_type": "WEIGHING_PERFORMANCE",
                "payload_schema_version": "v1",
                "payload": {
                    "test_code": "WEIGHING_PERFORMANCE",
                    "protocol": "WEIGHING_V1",
                    "observation_schema_version": "v1",
                    "sequence_no": sequence,
                    "load_g": load,
                    "indication_g": indication,
                    "additional_load_g": "5",
                    "zero_error_g": "0",
                    "direction": direction,
                    "measured_at": measured_at,
                },
            }
        )
    return rows


def create_scenario(
    client: httpx.Client,
    *,
    lab_id: str,
    instrument_id: str,
    ruleset_id: str,
    application: str,
    expected_outcome: str,
    failing: bool,
) -> dict:
    def current(path: str) -> tuple[dict, str]:
        # The Vercel same-origin rewrite is intentionally used in production.
        # Cache-bust optimistic-lock reads so If-Match is always derived from
        # the current application resource rather than any intermediary copy.
        response = expect(
            client.get(
                path,
                params={"_phase23_nonce": uuid4().hex},
                headers={
                    "Cache-Control": "no-cache, no-store, max-age=0",
                    "Pragma": "no-cache",
                },
            )
        )
        body = response.json()
        # Application concurrency is defined by lock_version. Do not depend on
        # an intermediary/proxy ETag header for mutation preconditions.
        return body, etag(body)

    existing = session_by_application(client, lab_id, application)

    if existing is None:
        session = expect(
            client.post(
                "/api/v1/test-sessions",
                headers={"Idempotency-Key": uuid4().hex},
                json={
                    "instrument_id": instrument_id,
                    "rule_set_id": ruleset_id,
                    "application_number": application,
                    "evaluation_context": "SIH_DEMO",
                    "notes": (
                        "SYNTHETIC SIH DEMO ONLY. This scenario demonstrates deterministic "
                        "software mechanics and must never be represented as an OIML "
                        "compliance determination or official report."
                    ),
                },
            ),
            201,
        ).json()
    else:
        session, _ = current(f"/api/v1/test-sessions/{existing['id']}")

    session_path = f"/api/v1/test-sessions/{session['id']}"

    # Resume safely if a previous Stage 2 seeding attempt stopped mid-scenario.
    if not (
        session["evaluation_status"] == "COMPLETE"
        and session["compliance_outcome"] == expected_outcome
    ):
        if session["workflow_status"] == "DRAFT":
            session, token = current(session_path)
            session = expect(
                client.post(
                    session_path + "/configure",
                    headers={"If-Match": token},
                    json={"instrument_snapshot": session["instrument_snapshot"]},
                )
            ).json()

        if session["workflow_status"] == "INSTRUMENT_CONFIGURATION":
            applicability = expect(
                client.post(session_path + "/applicability")
            ).json()
            if applicability["confirmable"] is not True:
                raise RuntimeError(
                    "Synthetic SIH demo applicability was not explicitly confirmable"
                )

            session, token = current(session_path)
            session = expect(
                client.post(
                    session_path + "/confirm-applicability",
                    headers={"If-Match": token},
                    json={"elections": {}},
                )
            ).json()

        requirements = expect(
            client.get(session_path + "/requirements")
        ).json()
        required_rows = [
            row
            for row in requirements
            if row["applicability_status"] == "REQUIRED"
        ]
        if len(required_rows) != 1:
            raise RuntimeError(
                "Demo ruleset must create exactly one required assessment"
            )
        requirement = required_rows[0]
        if requirement["slot_snapshot"]["test_code"] != "WEIGHING_PERFORMANCE":
            raise RuntimeError("Unexpected required demo assessment")

        session, token = current(session_path)
        if session["workflow_status"] == "APPLICABILITY_CONFIRMED":
            session = expect(
                client.post(
                    session_path + "/start-testing",
                    headers={"If-Match": token},
                )
            ).json()
        elif session["workflow_status"] != "TESTING":
            raise RuntimeError(
                f"Cannot resume {application} from workflow "
                f"{session['workflow_status']}"
            )

        run_id = requirement["selected_run_id"]
        run_path = f"/api/v1/test-runs/{run_id}"

        run, token = current(run_path)
        if run["started_at"] is None:
            expect(
                client.post(
                    run_path + "/start",
                    headers={"If-Match": token},
                )
            )
            run, token = current(run_path)

        desired_context = {
            "test_code": "WEIGHING_PERFORMANCE",
            "procedure_variant": "DIGITAL_PRE_ROUNDING",
            "procedure_schema_version": "v1",
            "evaluation_context": "SIH_DEMO",
            "protocol": "WEIGHING_V1",
            "range_no": 1,
            "scenario": "demo",
            "stages": ["UP", "DOWN"],
            "preloaded": False,
            "warmed_up_seconds": "0",
            "stabilized": False,
            "zero_condition": "DEMO_ZERO",
            "environment": [],
            "equipment": [],
            "evidence_hashes": [],
        }
        context = run.get("procedure_context") or {}
        context_ready = (
            context.get("test_code") == desired_context["test_code"]
            and context.get("procedure_variant")
            == desired_context["procedure_variant"]
            and context.get("procedure_schema_version")
            == desired_context["procedure_schema_version"]
            and context.get("evaluation_context")
            == desired_context["evaluation_context"]
            and context.get("protocol") == desired_context["protocol"]
            and context.get("range_no") == desired_context["range_no"]
            and context.get("scenario") == desired_context["scenario"]
            and context.get("stages") == desired_context["stages"]
            and context.get("preloaded") is False
            and str(context.get("warmed_up_seconds")) in {"0", "0.0"}
            and context.get("stabilized") is False
            and context.get("zero_condition")
            == desired_context["zero_condition"]
            and not context.get("environment")
            and not context.get("equipment")
            and not context.get("evidence_hashes")
        )
        if not context_ready:
            _, token = current(run_path)
            response = client.patch(
                run_path + "/procedure-context",
                headers={
                    "If-Match": token,
                    "Cache-Control": "no-cache, no-store, max-age=0",
                    "Pragma": "no-cache",
                },
                json={"procedure_context": desired_context},
            )
            if response.status_code == 412:
                _, token = current(run_path)
                response = client.patch(
                    run_path + "/procedure-context",
                    headers={
                        "If-Match": token,
                        "Cache-Control": "no-cache, no-store, max-age=0",
                        "Pragma": "no-cache",
                    },
                    json={"procedure_context": desired_context},
                )
            expect(response)

        existing_observations = expect(
            client.get(run_path + "/observations")
        ).json()
        existing_sequences = {
            row["sequence_no"] for row in existing_observations
        }

        for row in observation_rows(failing=failing):
            if row["sequence_no"] in existing_sequences:
                continue

            # A 412 means the mutation did not occur, so it is safe to reload
            # the current run version and retry this create operation.
            response = None
            for _attempt in range(3):
                _, token = current(run_path)
                response = client.post(
                    run_path + "/observations",
                    headers={
                        "If-Match": token,
                        "Cache-Control": "no-cache, no-store, max-age=0",
                        "Pragma": "no-cache",
                    },
                    json=row,
                )
                if response.status_code != 412:
                    break

            if response is None:
                raise RuntimeError("Observation request was not attempted")
            expect(response, 201)

        run, token = current(run_path)
        if not (
            run["current_result_id"]
            and run["evaluation_status"] == "COMPLETE"
            and run["compliance_outcome"] == expected_outcome
        ):
            result = expect(
                client.post(
                    run_path + "/evaluate",
                    headers={
                        "If-Match": token,
                        "Idempotency-Key": uuid4().hex,
                    },
                )
            ).json()

            if result["evaluation_status"] != "COMPLETE":
                raise RuntimeError("Demo evaluator did not complete")
            if result["compliance_outcome"] != expected_outcome:
                raise RuntimeError(
                    f"Expected {expected_outcome}, "
                    f"got {result['compliance_outcome']}"
                )
            if result["deterministic_result"].get("synthetic_fixture") is not True:
                raise RuntimeError("Demo result lost its synthetic fixture marker")

        run, token = current(run_path)
        if run["completed_at"] is None:
            expect(
                client.post(
                    run_path + "/complete",
                    headers={"If-Match": token},
                )
            )

        session, _ = current(session_path)
        if (
            session["evaluation_status"] != "COMPLETE"
            or session["compliance_outcome"] != expected_outcome
        ):
            raise RuntimeError("Completed demo session aggregate is incorrect")

    session, session_token = current(session_path)

    sections = expect(
        client.get(session_path + "/sections")
    ).json()
    if len(sections) != 17:
        raise RuntimeError("Demo session must expose all 17 report sections")

    preview = expect(
        client.post(
            session_path + "/report-previews",
            headers={"If-Match": session_token},
        ),
        201,
    ).json()
    if (
        preview["preview_context_snapshot"].get("document_kind")
        != "UNOFFICIAL_PREVIEW"
    ):
        raise RuntimeError("Demo preview is not explicitly unofficial")

    session, session_token = current(session_path)
    review_attempt = client.post(
        session_path + "/submit-for-review",
        headers={"If-Match": session_token},
    )
    if review_attempt.status_code != 409:
        raise RuntimeError("Synthetic demo unexpectedly entered regulatory review")
    if (
        review_attempt.json().get("error", {}).get("code")
        != "SYNTHETIC_DEMO_OFFICIAL_FORBIDDEN"
    ):
        raise RuntimeError(
            "Unexpected synthetic demo review gate: "
            f"{review_attempt.text[:500]}"
        )

    session, session_token = current(session_path)
    official_attempt = client.post(
        session_path + "/reports",
        headers={
            "If-Match": session_token,
            "Idempotency-Key": uuid4().hex,
        },
        json={
            "intended_issuer_id": session["started_by"],
            "planned_issue_date": "2000-01-01",
        },
    )
    if official_attempt.status_code != 409:
        raise RuntimeError(
            "Synthetic demo unexpectedly entered official report generation"
        )
    if (
        official_attempt.json().get("error", {}).get("code")
        != "SYNTHETIC_DEMO_OFFICIAL_FORBIDDEN"
    ):
        raise RuntimeError(
            "Unexpected synthetic demo report gate: "
            f"{official_attempt.text[:500]}"
        )

    return session
def main() -> None:
    base = production_origin()
    admin_email = required("PRODUCTION_ADMIN_EMAIL")
    admin_password = secret(
        "PRODUCTION_ADMIN_PASSWORD",
        "Production administrator password: ",
    )
    engineer_password = secret(
        "PHASE23_ENGINEER_PASSWORD",
        "SIH Demo Engineer password: ",
    )
    engineer_email = os.environ.get(
        "PHASE23_ENGINEER_EMAIL",
        "demo.engineer@example.com",
    ).strip()

    with httpx.Client(
        base_url=base,
        headers={"Origin": base, "Accept": "application/json"},
        timeout=90,
        follow_redirects=False,
    ) as client:
        login(client, admin_email, admin_password)
        demo_ruleset = register_demo_ruleset(client)
        if demo_ruleset["ruleset_status"] != "DRAFT":
            raise RuntimeError("Synthetic SIH demo ruleset must remain DRAFT")
        if demo_ruleset["validation_summary"].get("synthetic_demo_only") is not True:
            raise RuntimeError("Ruleset is missing the synthetic demo marker")

        login(client, engineer_email, engineer_password)
        lab = find_lab(client)
        instrument = find_instrument(client, lab["id"])

        for application, outcome, failing in SCENARIOS:
            create_scenario(
                client,
                lab_id=lab["id"],
                instrument_id=instrument["id"],
                ruleset_id=demo_ruleset["id"],
                application=application,
                expected_outcome=outcome,
                failing=failing,
            )

    print("Phase 23 Stage 2 synthetic demo scenarios: PASS")
    print("- SIH26035-DEMO-POSITIVE: COMPLETE / COMPLIANT / SYNTHETIC DEMO ONLY")
    print("- SIH26035-DEMO-NEGATIVE: COMPLETE / NONCOMPLIANT / SYNTHETIC DEMO ONLY")
    print("- all 17 report sections are visible in both scenarios")
    print("- deterministic calculations and failed-condition trace are persisted")
    print("- unofficial previews are allowed")
    print("- regulatory review/final approval is blocked")
    print("- official report generation/issue is blocked")
    print("- demo ruleset remains DRAFT and can never be activated")
    print("- no regulatory threshold or OIML conclusion was claimed")


if __name__ == "__main__":
    main()
