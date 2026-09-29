from datetime import date
from uuid import uuid4

import pytest

from tests.test_phase26_stage6_api import start_v3_testing

pytest_plugins = ("tests.test_phase26_stage7_api",)

pytestmark = pytest.mark.asyncio


async def test_stage8_final_judge_flow_is_end_to_end_and_non_official(
    client,
    stage7,
):
    path, testing = await start_v3_testing(client, stage7)

    completed = await client.post(
        path + "/demo-complete-evaluation",
        headers={"If-Match": testing.headers["etag"]},
    )
    assert completed.status_code == 200, completed.text
    dashboard = completed.json()

    assert dashboard["session"]["workflow_status"] == "EXAMINATION"
    assert dashboard["session"]["evaluation_status"] == "COMPLETE"
    assert dashboard["session"]["compliance_outcome"] == "COMPLIANT"
    assert len(dashboard["sections"]) == 17
    assert all(
        section["applicability_status"] == "REQUIRED"
        and section["evaluation_status"] == "COMPLETE"
        and section["compliance_outcome"] == "COMPLIANT"
        for section in dashboard["sections"]
    )

    selected_run_id = next(
        requirement["selected_run_id"]
        for requirement in dashboard["requirements"]
        if requirement["selected_run_id"] is not None
    )
    evidence = await client.get(
        f"/api/v1/test-runs/{selected_run_id}/evidence"
    )
    assert evidence.status_code == 200, evidence.text
    assert len(evidence.json()) == 1
    assert evidence.json()[0]["purpose"].startswith(
        "synthetic_demo_traceability_"
    )

    current = await client.get(path)
    assert current.status_code == 200, current.text

    report = await client.post(
        path + "/full-demo-report-previews",
        headers={"If-Match": current.headers["etag"]},
    )
    assert report.status_code == 201, report.text
    preview = report.json()
    assert preview["preview_status"] == "READY"
    context = preview["preview_context_snapshot"]
    assert context["document_kind"] == "FULL_DEMO_REPORT"
    assert context["demonstration"]["not_an_official_oiml_certificate"] is True
    assert context["demonstration"]["source_counts"]["sections"] == 17
    assert context["demonstration"]["source_counts"]["runs"] == 23
    assert context["demonstration"]["source_counts"]["evidence_links"] == 85
    assert (
        context["demonstration"]["source_counts"]["unique_evidence_attachments"]
        == 60
    )

    current = await client.get(path)
    review = await client.post(
        path + "/submit-for-review",
        headers={"If-Match": current.headers["etag"]},
    )
    assert review.status_code == 409
    assert (
        review.json()["error"]["code"]
        == "SYNTHETIC_DEMO_OFFICIAL_FORBIDDEN"
    )

    current = await client.get(path)
    official = await client.post(
        path + "/reports",
        headers={
            "If-Match": current.headers["etag"],
            "Idempotency-Key": uuid4().hex,
        },
        json={
            "intended_issuer_id": str(stage7.users["officer"].id),
            "planned_issue_date": date.today().isoformat(),
        },
    )
    assert official.status_code == 409
    assert (
        official.json()["error"]["code"]
        == "SYNTHETIC_DEMO_OFFICIAL_FORBIDDEN"
    )

    repository = await client.get(
        "/api/v1/reports",
        params={
            "laboratory_id": str(stage7.labs[0].id),
            "page": 1,
            "page_size": 100,
        },
    )
    assert repository.status_code == 200, repository.text
    assert all(
        row["test_session_id"] != dashboard["session"]["id"]
        for row in repository.json()["items"]
    )
