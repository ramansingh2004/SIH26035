"""Phase 23 Stage 3 — deployed SIH demo walkthrough acceptance.

This verifier uses only the public deployed API and signed preview-download URLs.
It does not import database models, repositories, SQLAlchemy, or compliance internals.
It never activates a ruleset, edits an evaluation outcome, approves a session, or issues
an official report. The only created records are normal unofficial report previews.
"""

from __future__ import annotations

import getpass
import hashlib
import os
from datetime import date
from urllib.parse import urlsplit

import httpx

LAB_CODE = "SIH26035-DEMO"
DEMO_RULESET_VERSION = "SYNTHETIC_TEST_SIH26035_DEMO_V1"

CANDIDATE_SCENARIOS = (
    "SIH26035-DEMO-NOMINAL",
    "SIH26035-DEMO-ADVERSE",
)

COMPLETE_SCENARIOS = (
    ("SIH26035-DEMO-POSITIVE", "COMPLIANT", False),
    ("SIH26035-DEMO-NEGATIVE", "NONCOMPLIANT", True),
)

DEMO_USERS = (
    (
        "demo.engineer@example.com",
        "PHASE23_ENGINEER_PASSWORD",
        "LAB_ENGINEER",
    ),
    (
        "demo.reviewer@example.com",
        "PHASE23_REVIEWER_PASSWORD",
        "REVIEWER",
    ),
    (
        "demo.approver@example.com",
        "PHASE23_APPROVER_PASSWORD",
        "APPROVING_OFFICER",
    ),
)


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
            f"HTTP {response.status_code}, expected {status}; {response.text[:900]}"
        )
    return response


def etag(resource: dict) -> str:
    version = resource.get("lock_version")
    if version is None:
        raise RuntimeError("Versioned resource is missing lock_version")
    return f'"{version}"'


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


def lab_scope(me: dict, laboratory_id: str) -> dict:
    scope = next(
        (
            item
            for item in me.get("laboratories", [])
            if item.get("laboratory_id") == laboratory_id
        ),
        None,
    )
    if scope is None:
        raise RuntimeError("Demo identity is not scoped to the SIH demo laboratory")
    return scope


def find_lab(client: httpx.Client) -> dict:
    rows = expect(
        client.get(
            "/api/v1/laboratories",
            params={"page": 1, "page_size": 100},
        )
    ).json()["items"]
    matches = [row for row in rows if row.get("code") == LAB_CODE]
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one SIH26035-DEMO laboratory")
    return matches[0]


def session_by_application(
    client: httpx.Client,
    laboratory_id: str,
    application: str,
) -> dict:
    page = expect(
        client.get(
            "/api/v1/test-sessions",
            params={
                "laboratory_id": laboratory_id,
                "application_number": application,
                "page": 1,
                "page_size": 100,
            },
        )
    ).json()
    matches = [
        row
        for row in page["items"]
        if row.get("application_number") == application
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one canonical session for {application}; got {len(matches)}"
        )
    return matches[0]


def find_demo_ruleset(client: httpx.Client) -> dict:
    rows = expect(
        client.get(
            "/api/v1/rulesets",
            params={"page": 1, "page_size": 100},
        )
    ).json()["items"]
    matches = [
        row for row in rows if row.get("version") == DEMO_RULESET_VERSION
    ]
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one synthetic SIH demo ruleset")
    ruleset = matches[0]
    if ruleset.get("ruleset_status") != "DRAFT":
        raise RuntimeError("Synthetic SIH demo ruleset must remain DRAFT")
    summary = ruleset.get("validation_summary") or {}
    if summary.get("synthetic_demo_only") is not True:
        raise RuntimeError("Synthetic demo ruleset marker is missing")
    return ruleset


def verify_candidate_shell(
    client: httpx.Client,
    laboratory_id: str,
    application: str,
) -> dict:
    session = session_by_application(client, laboratory_id, application)
    if session.get("compliance_outcome") != "UNDETERMINED":
        raise RuntimeError(f"{application} unexpectedly has a determined outcome")
    if session.get("workflow_status") in {"APPROVED", "REPORT_ISSUED"}:
        raise RuntimeError(f"{application} unexpectedly entered official workflow")

    applicability = expect(
        client.post(
            f"/api/v1/test-sessions/{session['id']}/applicability"
        )
    ).json()
    if applicability.get("confirmable") is not False:
        raise RuntimeError(
            f"{application} candidate applicability unexpectedly became confirmable"
        )
    return session


def verify_complete_scenario(
    client: httpx.Client,
    laboratory_id: str,
    application: str,
    expected_outcome: str,
    expect_failure: bool,
) -> tuple[dict, dict, dict]:
    session = session_by_application(client, laboratory_id, application)
    session = expect(
        client.get(f"/api/v1/test-sessions/{session['id']}")
    ).json()

    if session.get("workflow_status") != "TESTING":
        raise RuntimeError(
            f"{application} must remain in TESTING, not official review/approval"
        )
    if session.get("evaluation_status") != "COMPLETE":
        raise RuntimeError(f"{application} is not COMPLETE")
    if session.get("compliance_outcome") != expected_outcome:
        raise RuntimeError(
            f"{application}: expected {expected_outcome}, "
            f"got {session.get('compliance_outcome')}"
        )

    dashboard = expect(
        client.get(f"/api/v1/test-sessions/{session['id']}/dashboard")
    ).json()
    sections = dashboard["sections"]
    requirements = dashboard["requirements"]

    if len(sections) != 17:
        raise RuntimeError(f"{application} does not expose all 17 sections")

    required_sections = [
        section
        for section in sections
        if section.get("applicability_status") == "REQUIRED"
    ]
    not_applicable_sections = [
        section
        for section in sections
        if section.get("applicability_status") == "NOT_APPLICABLE"
    ]
    if len(required_sections) != 1 or required_sections[0].get("section_number") != 1:
        raise RuntimeError(
            f"{application} must have only synthetic Section 1 as REQUIRED"
        )
    if len(not_applicable_sections) != 16:
        raise RuntimeError(
            f"{application} must have Sections 2-17 explicitly NOT_APPLICABLE"
        )

    required = [
        item
        for item in requirements
        if item.get("applicability_status") == "REQUIRED"
    ]
    if len(required) != 1 or not required[0].get("selected_run_id"):
        raise RuntimeError(f"{application} is missing its selected required run")

    run_id = required[0]["selected_run_id"]
    run = expect(client.get(f"/api/v1/test-runs/{run_id}")).json()
    if run.get("completed_at") is None:
        raise RuntimeError(f"{application} selected run is not completed")
    if run.get("evaluation_status") != "COMPLETE":
        raise RuntimeError(f"{application} run evaluation is not COMPLETE")
    if run.get("compliance_outcome") != expected_outcome:
        raise RuntimeError(f"{application} run outcome does not match session")
    if not run.get("current_result_id"):
        raise RuntimeError(f"{application} has no current deterministic result")

    history = expect(
        client.get(
            f"/api/v1/test-runs/{run_id}/history",
            params={"page": 1, "page_size": 100},
        )
    ).json()
    result = next(
        (
            item
            for item in history["results"]
            if item.get("id") == run["current_result_id"]
        ),
        None,
    )
    if result is None:
        raise RuntimeError(f"{application} current result is absent from history")
    if result.get("evaluation_status") != "COMPLETE":
        raise RuntimeError(f"{application} historical result is not COMPLETE")
    if result.get("compliance_outcome") != expected_outcome:
        raise RuntimeError(f"{application} historical result outcome is incorrect")

    deterministic = result.get("deterministic_result") or {}
    if deterministic.get("synthetic_fixture") is not True:
        raise RuntimeError(f"{application} lost the synthetic fixture marker")
    if not result.get("calculations_json"):
        raise RuntimeError(f"{application} has no deterministic calculation trace")
    if not result.get("acceptance_limits_json"):
        raise RuntimeError(f"{application} has no persisted acceptance-limit trace")

    failures = result.get("failed_conditions_json") or []
    if expect_failure and not failures:
        raise RuntimeError(f"{application} must persist a failed-condition trace")
    if not expect_failure and failures:
        raise RuntimeError(f"{application} unexpectedly has failed conditions")

    if not history.get("events"):
        raise RuntimeError(f"{application} has no append-only result history events")

    return session, run, result


def create_and_verify_preview(
    client: httpx.Client,
    session_id: str,
) -> dict:
    session = expect(
        client.get(f"/api/v1/test-sessions/{session_id}")
    ).json()
    preview = expect(
        client.post(
            f"/api/v1/test-sessions/{session_id}/report-previews",
            headers={"If-Match": etag(session)},
        ),
        201,
    ).json()

    if preview.get("preview_status") != "READY":
        raise RuntimeError(
            f"Unofficial preview did not become READY: {preview.get('error_code')}"
        )
    context = preview.get("preview_context_snapshot") or {}
    if context.get("document_kind") != "UNOFFICIAL_PREVIEW":
        raise RuntimeError("Preview is not visibly marked UNOFFICIAL_PREVIEW")

    for file_format, prefix in (("pdf", b"%PDF-"), ("docx", b"PK")):
        metadata = expect(
            client.get(
                f"/api/v1/report-previews/{preview['id']}/download",
                params={"format": file_format},
            )
        ).json()

        if metadata.get("format") != file_format:
            raise RuntimeError(f"Preview {file_format} metadata format mismatch")
        download_url = metadata.get("download_url")
        if not isinstance(download_url, str) or not download_url.startswith("https://"):
            raise RuntimeError(f"Preview {file_format} signed URL is invalid")

        with httpx.Client(
            timeout=90,
            follow_redirects=True,
            headers={"Accept": "*/*"},
        ) as download_client:
            body_response = expect(download_client.get(download_url))
            body = body_response.content

        if not body.startswith(prefix):
            raise RuntimeError(f"Downloaded {file_format} has an invalid file signature")
        digest = hashlib.sha256(body).hexdigest()
        if digest != metadata.get("sha256"):
            raise RuntimeError(f"Downloaded {file_format} SHA-256 does not match metadata")

    return preview


def verify_official_guards(
    client: httpx.Client,
    session: dict,
    actor_id: str,
) -> None:
    session = expect(
        client.get(f"/api/v1/test-sessions/{session['id']}")
    ).json()

    review = client.post(
        f"/api/v1/test-sessions/{session['id']}/submit-for-review",
        headers={"If-Match": etag(session)},
    )
    if review.status_code != 409:
        raise RuntimeError("Synthetic demo unexpectedly entered regulatory review")
    if (
        review.json().get("error", {}).get("code")
        != "SYNTHETIC_DEMO_OFFICIAL_FORBIDDEN"
    ):
        raise RuntimeError(f"Unexpected review guard: {review.text[:700]}")

    session = expect(
        client.get(f"/api/v1/test-sessions/{session['id']}")
    ).json()
    official = client.post(
        f"/api/v1/test-sessions/{session['id']}/reports",
        headers={
            "If-Match": etag(session),
            "Idempotency-Key": hashlib.sha256(
                f"stage3:{session['id']}:{session['lock_version']}".encode()
            ).hexdigest(),
        },
        json={
            "intended_issuer_id": actor_id,
            "planned_issue_date": date.today().isoformat(),
        },
    )
    if official.status_code != 409:
        raise RuntimeError("Synthetic demo unexpectedly generated an official report")
    if (
        official.json().get("error", {}).get("code")
        != "SYNTHETIC_DEMO_OFFICIAL_FORBIDDEN"
    ):
        raise RuntimeError(f"Unexpected official-report guard: {official.text[:700]}")


def verify_repository_has_no_synthetic_reports(
    client: httpx.Client,
    laboratory_id: str,
    scenario_ids: set[str],
) -> None:
    page = expect(
        client.get(
            "/api/v1/reports",
            params={
                "laboratory_id": laboratory_id,
                "page": 1,
                "page_size": 100,
            },
        )
    ).json()
    bad = [
        item
        for item in page["items"]
        if item.get("test_session_id") in scenario_ids
    ]
    if bad:
        raise RuntimeError(
            "Synthetic complete scenario unexpectedly appears in official report repository"
        )


def verify_dashboard(
    client: httpx.Client,
    laboratory_id: str,
    preview_id: str,
) -> dict:
    summary = expect(
        client.get(
            "/api/v1/dashboard/summary",
            params={
                "laboratory_id": laboratory_id,
                "page": 1,
                "page_size": 100,
            },
        )
    ).json()

    if summary.get("session_total", 0) < 4:
        raise RuntimeError("Demo dashboard does not contain the four canonical scenarios")
    outcomes = summary.get("outcome_counts") or {}
    if outcomes.get("COMPLIANT", 0) < 1:
        raise RuntimeError("Demo dashboard is missing the positive synthetic scenario")
    if outcomes.get("NONCOMPLIANT", 0) < 1:
        raise RuntimeError("Demo dashboard is missing the negative synthetic scenario")
    if outcomes.get("UNDETERMINED", 0) < 2:
        raise RuntimeError("Demo dashboard is missing the candidate undetermined shells")

    activity = summary.get("recent_activity", {}).get("items", [])
    if not any(
        item.get("entity_id") == preview_id
        and item.get("action") in {"report.preview_started", "report.preview_ready"}
        for item in activity
    ):
        raise RuntimeError("Recent dashboard activity does not expose the walkthrough preview")

    return summary


def main() -> None:
    origin = production_origin()

    passwords = {
        env_name: secret(
            env_name,
            f"{role.replace('_', ' ').title()} password: ",
        )
        for _email, env_name, role in DEMO_USERS
    }

    with httpx.Client(
        base_url=origin,
        headers={
            "Origin": origin,
            "Accept": "application/json",
        },
        timeout=90,
        follow_redirects=False,
    ) as client:
        # Engineer login establishes the canonical demo laboratory identifier.
        engineer_email, engineer_env, _ = DEMO_USERS[0]
        engineer = login(client, engineer_email, passwords[engineer_env])
        lab = find_lab(client)
        lab_id = lab["id"]

        identities = {}
        for email, env_name, expected_role in DEMO_USERS:
            me = login(client, email, passwords[env_name])
            scope = lab_scope(me, lab_id)
            if expected_role not in scope.get("roles", []):
                raise RuntimeError(
                    f"{email} does not hold expected lab role {expected_role}"
                )
            identities[expected_role] = me["id"]

        if len(set(identities.values())) != 3:
            raise RuntimeError("Demo Engineer, Reviewer and Approver must be distinct users")

        # Continue acceptance as the engineer/data-entry identity.
        engineer = login(client, engineer_email, passwords[engineer_env])

        find_demo_ruleset(client)

        candidate_sessions = [
            verify_candidate_shell(client, lab_id, application)
            for application in CANDIDATE_SCENARIOS
        ]

        complete = {}
        for application, outcome, expect_failure in COMPLETE_SCENARIOS:
            complete[application] = verify_complete_scenario(
                client,
                lab_id,
                application,
                outcome,
                expect_failure,
            )

        positive_session = complete["SIH26035-DEMO-POSITIVE"][0]
        negative_session = complete["SIH26035-DEMO-NEGATIVE"][0]

        preview = create_and_verify_preview(client, positive_session["id"])
        verify_official_guards(client, positive_session, engineer["id"])

        scenario_ids = {
            positive_session["id"],
            negative_session["id"],
        }
        verify_repository_has_no_synthetic_reports(client, lab_id, scenario_ids)
        verify_dashboard(client, lab_id, preview["id"])

        # Keep local variables meaningful for the acceptance summary and guarantee
        # both candidate shells were discovered as canonical unique sessions.
        if len({row["id"] for row in candidate_sessions}) != 2:
            raise RuntimeError("Candidate demo shells are not unique")

    print("Phase 23 Stage 3 judge walkthrough acceptance: PASS")
    print("- demo Engineer / Reviewer / Approving Officer role separation: PASS")
    print("- candidate NOMINAL / ADVERSE shells remain UNDETERMINED and blocked: PASS")
    print("- POSITIVE: COMPLETE / COMPLIANT / SYNTHETIC DEMO ONLY")
    print("- NEGATIVE: COMPLETE / NONCOMPLIANT / SYNTHETIC DEMO ONLY")
    print("- all 17 sections + selected-run/result history are present: PASS")
    print("- deterministic calculation and negative failed-condition traces: PASS")
    print("- dashboard presentation of all four canonical scenarios: PASS")
    print("- unofficial PDF + DOCX preview download integrity: PASS")
    print("- regulatory review and official report generation remain blocked: PASS")
    print("- report repository contains no synthetic official report: PASS")
    print("- canonical named demo state is unique and repeatable without deleting history")
    print("- no OIML regulatory threshold or official compliance conclusion was claimed")


if __name__ == "__main__":
    main()
