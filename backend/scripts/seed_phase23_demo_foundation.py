"""Phase 23 Stage 1 — production-safe SIH demo foundation.

All records are created through the public application API via the stable Vercel
origin. This script does not import database models, repositories or compliance
services and does not bypass regulatory workflow gates.

The candidate OIML R76 artifact remains unverified. Demo scenario shells therefore
remain UNDETERMINED and are visibly labelled as synthetic/demo-only.
"""

from __future__ import annotations

import getpass
import os
from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

LAB_CODE = "SIH26035-DEMO"
LAB_NAME = "SIH26035 Demonstration Laboratory"
MANUFACTURER_NAME = "Bharat Precision Instruments — DEMO ONLY"
INSTRUMENT_MODEL = "BPX-30K Class III — DEMO ONLY"

SCENARIOS = (
    (
        "SIH26035-DEMO-NOMINAL",
        "SYNTHETIC SIH DEMO ONLY. Illustrative nominal-reading scenario. "
        "The candidate regulatory ruleset is incomplete; this record intentionally "
        "remains UNDETERMINED and must not be presented as a compliant evaluation.",
    ),
    (
        "SIH26035-DEMO-ADVERSE",
        "SYNTHETIC SIH DEMO ONLY. Illustrative adverse-reading scenario. "
        "The candidate regulatory ruleset is incomplete; this record intentionally "
        "remains UNDETERMINED and must not be presented as a noncompliant evaluation.",
    ),
)


@dataclass(frozen=True)
class DemoUser:
    key: str
    email: str
    full_name: str
    role: str
    password_env: str


DEMO_USERS = (
    DemoUser(
        "engineer",
        "demo.engineer@example.com",
        "SIH Demo Engineer",
        "LAB_ENGINEER",
        "PHASE23_ENGINEER_PASSWORD",
    ),
    DemoUser(
        "reviewer",
        "demo.reviewer@example.com",
        "SIH Demo Reviewer",
        "REVIEWER",
        "PHASE23_REVIEWER_PASSWORD",
    ),
    DemoUser(
        "approver",
        "demo.approver@example.com",
        "SIH Demo Approving Officer",
        "APPROVING_OFFICER",
        "PHASE23_APPROVER_PASSWORD",
    ),
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
            f"HTTP {response.status_code}, expected {status}; {response.text[:700]}"
        )
    return response


def resource_etag(resource: dict) -> str:
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


def exact_user(client: httpx.Client, email: str) -> dict | None:
    items = expect(
        client.get(
            "/api/v1/users",
            params={
                "search": email,
                "page": 1,
                "page_size": 100,
            },
        )
    ).json()["items"]
    matches = [row for row in items if row["email"].lower() == email.lower()]
    if len(matches) > 1:
        raise RuntimeError(f"Multiple users unexpectedly matched {email}")
    return matches[0] if matches else None


def ensure_lab(client: httpx.Client) -> dict:
    items = expect(
        client.get(
            "/api/v1/laboratories",
            params={"page": 1, "page_size": 100},
        )
    ).json()["items"]
    existing = next((row for row in items if row["code"] == LAB_CODE), None)
    if existing is not None:
        return existing

    return expect(
        client.post(
            "/api/v1/laboratories",
            json={
                "name": LAB_NAME,
                "code": LAB_CODE,
                "address_line1": "Synthetic SIH demonstration environment",
                "address_line2": "",
                "city": "Ghaziabad",
                "state": "Uttar Pradesh",
                "postal_code": "201009",
                "country": "India",
                "phone": "0000000000",
                "email": "demo.lab@example.com",
                "accreditation_no": "DEMO-NOT-ACCREDITED",
                "timezone": "Asia/Kolkata",
            },
        ),
        201,
    ).json()


def ensure_demo_user(
    client: httpx.Client,
    spec: DemoUser,
    password: str,
    lab_id: str,
    roles: dict[str, str],
) -> dict:
    user = exact_user(client, spec.email)
    if user is None:
        user = expect(
            client.post(
                "/api/v1/users",
                json={
                    "email": spec.email,
                    "full_name": spec.full_name,
                    "password": password,
                    "initial_assignment": {
                        "role_code": spec.role,
                        "scope_type": "LABORATORY",
                        "laboratory_id": lab_id,
                    },
                },
            ),
            201,
        ).json()
        return user

    assignments = expect(
        client.get(
            f"/api/v1/users/{user['id']}/role-assignments",
            params={"page": 1, "page_size": 100},
        )
    ).json()["items"]

    expected_role_id = roles[spec.role]
    already_assigned = any(
        row["role_id"] == expected_role_id
        and row["laboratory_id"] == lab_id
        and row["revoked_at"] is None
        for row in assignments
    )
    if already_assigned:
        return user

    # Role grants increment the target user's lock_version, so always reload the
    # target immediately before the optimistic-concurrency mutation.
    user = exact_user(client, spec.email)
    if user is None:
        raise RuntimeError(f"Demo user disappeared while provisioning: {spec.email}")

    expect(
        client.post(
            f"/api/v1/users/{user['id']}/role-assignments",
            headers={"If-Match": resource_etag(user)},
            json={
                "role_code": spec.role,
                "scope_type": "LABORATORY",
                "laboratory_id": lab_id,
            },
        ),
        201,
    )
    refreshed = exact_user(client, spec.email)
    if refreshed is None:
        raise RuntimeError(f"Could not reload demo user: {spec.email}")
    return refreshed


def ensure_ruleset(client: httpx.Client) -> dict:
    rows = expect(
        client.get(
            "/api/v1/rulesets",
            params={"page": 1, "page_size": 100},
        )
    ).json()["items"]

    candidate = next(
        (
            row
            for row in rows
            if row.get("standard_code") == "OIML R 76-1"
            and row.get("edition") == "2006"
        ),
        None,
    )
    if candidate is not None:
        return candidate

    return expect(
        client.post(
            "/api/v1/rulesets",
            json={"artifact": "oiml_r76_2006/candidate-v1"},
        ),
        201,
    ).json()


def ensure_manufacturer(client: httpx.Client, lab_id: str) -> dict:
    items = expect(
        client.get(
            "/api/v1/manufacturers",
            params={
                "laboratory_id": lab_id,
                "search": MANUFACTURER_NAME,
                "page": 1,
                "page_size": 100,
            },
        )
    ).json()["items"]
    existing = next((row for row in items if row["name"] == MANUFACTURER_NAME), None)
    if existing is not None:
        return existing

    return expect(
        client.post(
            "/api/v1/manufacturers",
            json={
                "laboratory_id": lab_id,
                "name": MANUFACTURER_NAME,
                "registration_no": "DEMO-MFG-001",
                "address": {
                    "address_line1": "Synthetic manufacturer address",
                    "city": "Ghaziabad",
                    "state": "Uttar Pradesh",
                    "postal_code": "201009",
                    "country": "India",
                },
                "contact_person": "Demo Contact",
                "email": "demo.manufacturer@example.com",
                "phone": "0000000000",
                "country": "India",
            },
        ),
        201,
    ).json()


def ensure_instrument(
    client: httpx.Client,
    lab_id: str,
    manufacturer_id: str,
) -> dict:
    items = expect(
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
    instrument = next(
        (row for row in items if row["model_name"] == INSTRUMENT_MODEL),
        None,
    )

    if instrument is None:
        instrument = expect(
            client.post(
                "/api/v1/instruments",
                json={
                    "laboratory_id": lab_id,
                    "manufacturer_id": manufacturer_id,
                    "model_name": INSTRUMENT_MODEL,
                    "type_designation": "Synthetic demonstration NAWI",
                    "serial_number": "DEMO-SCALE-001",
                    "accuracy_class": "III",
                    "range_type": "SINGLE",
                    "indication_type": "DIGITAL",
                    "is_self_indicating": True,
                    "is_electronic": True,
                    "is_software_controlled": True,
                    "is_portable": False,
                    "is_mobile": False,
                    "load_receptor_type": "Platform",
                    "support_point_count": 4,
                    "tare_type": "SUBTRACTIVE",
                    "maximum_tare_g": "10000",
                    "zero_setting_type": "AUTOMATIC_AND_SEMI_AUTOMATIC",
                    "zero_tracking_available": True,
                    "level_indicator_available": True,
                    "automatic_tilt_sensor": False,
                    "power_supply_type": "AC",
                    "nominal_voltage": "230",
                    "min_voltage": "207",
                    "max_voltage": "253",
                    "declared_temp_min_c": "-10",
                    "declared_temp_max_c": "40",
                    "software_identifier": "DEMO-1.0",
                    "max_capacity_g": "30000",
                    "min_capacity_g": "200",
                    "verification_interval_e_g": "10",
                    "scale_interval_d_g": "10",
                    "metadata_json": {
                        "is_direct_sales": False,
                        "is_price_computing": False,
                        "is_labeling": False,
                        "data_storage_device_present": True,
                        "interfaces": [
                            {
                                "name": "USB service port",
                                "interface_type": "USB",
                                "purpose": "Synthetic demo interface",
                                "externally_accessible": True,
                            }
                        ],
                        "peripherals": ["Synthetic demo printer"],
                        "battery_charging_during_operation": False,
                        "vehicle_powered": False,
                        "declared_operating_conditions": (
                            "SYNTHETIC SIH DEMO ONLY; not regulatory evidence."
                        ),
                        "declared_installation": "Indoor laboratory demonstration.",
                    },
                },
            ),
            201,
        ).json()

    # Explicit range is required even for a single-range instrument.
    ranges = expect(
        client.get(
            f"/api/v1/instruments/{instrument['id']}/ranges",
            params={"page": 1, "page_size": 100},
        )
    ).json()["items"]
    if not any(row["range_no"] == 1 and row["is_active"] for row in ranges):
        current = expect(
            client.get(f"/api/v1/instruments/{instrument['id']}")
        ).json()
        expect(
            client.post(
                f"/api/v1/instruments/{instrument['id']}/ranges",
                headers={"If-Match": resource_etag(current)},
                json={
                    "range_no": 1,
                    "max_capacity_g": "30000",
                    "min_capacity_g": "200",
                    "verification_interval_e_g": "10",
                    "scale_interval_d_g": "10",
                },
            ),
            201,
        )

    # Give the demo instrument enough physical structure for meaningful screens.
    components = expect(
        client.get(
            f"/api/v1/instruments/{instrument['id']}/components",
            params={"page": 1, "page_size": 100},
        )
    ).json()["items"]

    wanted = (
        {
            "component_type": "LOAD_CELL",
            "manufacturer_name": "Synthetic Load Cell Works",
            "model": "LC-50-DEMO",
            "serial_or_type": "DEMO-LC-001",
            "certificate_reference": "DEMO-COMPONENT-CERT-001",
            "technical_specifications": {
                "description": "Synthetic load cell for SIH demonstration only",
                "rated_capacity_g": "50000",
                "nominal_voltage": "10",
                "interface_type": "ANALOG",
            },
            "notes": "SYNTHETIC SIH DEMO ONLY; not regulatory evidence.",
        },
        {
            "component_type": "INDICATOR",
            "manufacturer_name": "Synthetic Indicator Works",
            "model": "IND-III-DEMO",
            "serial_or_type": "DEMO-IND-001",
            "certificate_reference": "DEMO-COMPONENT-CERT-002",
            "technical_specifications": {
                "description": "Synthetic digital indicator for SIH demonstration only",
                "interface_type": "USB",
                "software_identifier": "DEMO-1.0",
            },
            "notes": "SYNTHETIC SIH DEMO ONLY; not regulatory evidence.",
        },
    )

    for data in wanted:
        present = any(
            row["component_type"] == data["component_type"]
            and row.get("model") == data["model"]
            and row["is_active"]
            for row in components
        )
        if present:
            continue
        current = expect(
            client.get(f"/api/v1/instruments/{instrument['id']}")
        ).json()
        expect(
            client.post(
                f"/api/v1/instruments/{instrument['id']}/components",
                headers={"If-Match": resource_etag(current)},
                json=data,
            ),
            201,
        )
        components = expect(
            client.get(
                f"/api/v1/instruments/{instrument['id']}/components",
                params={"page": 1, "page_size": 100},
            )
        ).json()["items"]

    return expect(
        client.get(f"/api/v1/instruments/{instrument['id']}")
    ).json()


def ensure_equipment(client: httpx.Client, lab_id: str) -> list[dict]:
    items = expect(
        client.get(
            "/api/v1/test-equipment",
            params={
                "laboratory_id": lab_id,
                "is_active": "true",
                "page": 1,
                "page_size": 100,
            },
        )
    ).json()["items"]

    wanted = (
        {
            "category": "Reference mass set — DEMO ONLY",
            "manufacturer": "Synthetic Metrology",
            "model": "M1 Demo Set",
            "serial_number": "DEMO-WEIGHTS-001",
            "reference_number": "DEMO-EQ-001",
            "calibration_certificate_no": "DEMO-CAL-001",
            "accuracy_or_class": "M1",
            "metadata_json": {
                "notes": (
                    "SYNTHETIC SIH DEMO ONLY. Calibration identity is illustrative "
                    "and must not be treated as regulatory evidence."
                ),
                "nominal_mass_g": "30000",
                "certificate_reference": "DEMO-CAL-001",
            },
        },
        {
            "category": "Temperature and humidity logger — DEMO ONLY",
            "manufacturer": "Synthetic Environmental Instruments",
            "model": "TH-100-DEMO",
            "serial_number": "DEMO-ENV-001",
            "reference_number": "DEMO-EQ-002",
            "calibration_certificate_no": "DEMO-CAL-002",
            "accuracy_or_class": "DEMO",
            "metadata_json": {
                "notes": (
                    "SYNTHETIC SIH DEMO ONLY. Environmental traceability is illustrative."
                ),
                "certificate_reference": "DEMO-CAL-002",
            },
        },
        {
            "category": "Programmable AC source — DEMO ONLY",
            "manufacturer": "Synthetic Power Instruments",
            "model": "AC-300-DEMO",
            "serial_number": "DEMO-POWER-001",
            "reference_number": "DEMO-EQ-003",
            "calibration_certificate_no": "DEMO-CAL-003",
            "accuracy_or_class": "DEMO",
            "metadata_json": {
                "notes": (
                    "SYNTHETIC SIH DEMO ONLY. Power-source traceability is illustrative."
                ),
                "certificate_reference": "DEMO-CAL-003",
            },
        },
    )

    for data in wanted:
        existing = next(
            (
                row
                for row in items
                if row.get("reference_number") == data["reference_number"]
                and row["is_active"]
            ),
            None,
        )
        if existing is not None:
            continue
        created = expect(
            client.post(
                "/api/v1/test-equipment",
                json={"laboratory_id": lab_id, **data},
            ),
            201,
        ).json()
        items.append(created)

    return [
        row
        for row in items
        if row.get("reference_number") in {"DEMO-EQ-001", "DEMO-EQ-002", "DEMO-EQ-003"}
    ]


def ensure_candidate_scenarios(
    client: httpx.Client,
    lab_id: str,
    instrument: dict,
    ruleset_id: str,
) -> list[dict]:
    result = []

    for application_number, notes in SCENARIOS:
        rows = expect(
            client.get(
                "/api/v1/test-sessions",
                params={
                    "laboratory_id": lab_id,
                    "application_number": application_number,
                    "page": 1,
                    "page_size": 100,
                },
            )
        ).json()["items"]
        session = next(
            (
                row
                for row in rows
                if row.get("application_number") == application_number
            ),
            None,
        )

        if session is None:
            response = expect(
                client.post(
                    "/api/v1/test-sessions",
                    headers={"Idempotency-Key": uuid4().hex},
                    json={
                        "instrument_id": instrument["id"],
                        "rule_set_id": ruleset_id,
                        "application_number": application_number,
                        "evaluation_context": "INITIAL_VERIFICATION",
                        "notes": notes,
                    },
                ),
                201,
            )
            session = response.json()

        if session["workflow_status"] == "DRAFT":
            response = expect(
                client.post(
                    f"/api/v1/test-sessions/{session['id']}/configure",
                    headers={"If-Match": resource_etag(session)},
                    json={
                        "instrument_snapshot": session["instrument_snapshot"],
                    },
                )
            )
            session = response.json()

        applicability = expect(
            client.post(
                f"/api/v1/test-sessions/{session['id']}/applicability"
            )
        ).json()
        if applicability.get("confirmable") is not False:
            raise RuntimeError(
                "Candidate demo rules unexpectedly became confirmable; "
                "do not continue without regulatory review"
            )
        if session["compliance_outcome"] != "UNDETERMINED":
            raise RuntimeError(
                "Stage 1 demo scenario unexpectedly has an authoritative outcome"
            )
        result.append(session)

    return result


def main() -> None:
    origin = production_origin()
    admin_email = required("PRODUCTION_ADMIN_EMAIL")
    admin_password = secret(
        "PRODUCTION_ADMIN_PASSWORD",
        "Production administrator password: ",
    )

    demo_passwords = {
        spec.key: secret(
            spec.password_env,
            f"{spec.full_name} password: ",
        )
        for spec in DEMO_USERS
    }

    with httpx.Client(
        base_url=origin,
        headers={
            "Origin": origin,
            "Accept": "application/json",
        },
        timeout=60,
        follow_redirects=False,
    ) as client:
        login(client, admin_email, admin_password)

        lab = ensure_lab(client)
        lab_id = lab["id"]

        role_rows = expect(
            client.get(
                "/api/v1/roles",
                params={"page": 1, "page_size": 100},
            )
        ).json()["items"]
        role_ids = {row["code"]: row["id"] for row in role_rows}

        users = {}
        for spec in DEMO_USERS:
            users[spec.key] = ensure_demo_user(
                client,
                spec,
                demo_passwords[spec.key],
                lab_id,
                role_ids,
            )

        ruleset = ensure_ruleset(client)

        # The engineer owns data entry. Reviewer and approving officer remain separate
        # identities so Stage 2 can demonstrate independence rules honestly.
        login(
            client,
            next(spec.email for spec in DEMO_USERS if spec.key == "engineer"),
            demo_passwords["engineer"],
        )

        manufacturer = ensure_manufacturer(client, lab_id)
        instrument = ensure_instrument(
            client,
            lab_id,
            manufacturer["id"],
        )
        equipment = ensure_equipment(client, lab_id)
        sessions = ensure_candidate_scenarios(
            client,
            lab_id,
            instrument,
            ruleset["id"],
        )

        expect(
            client.get(
                "/api/v1/dashboard/summary",
                params={"laboratory_id": lab_id},
            )
        )

    print("Phase 23 Stage 1 demo foundation: PASS")
    print(f"- laboratory: {LAB_CODE}")
    print(f"- manufacturer: {MANUFACTURER_NAME}")
    print(f"- Class III instrument: {INSTRUMENT_MODEL}")
    print("- explicit range + load-cell/indicator components: PASS")
    print(f"- demonstration equipment records: {len(equipment)}")
    print("- separate Engineer / Reviewer / Approving Officer identities: PASS")
    print(f"- candidate scenario shells: {len(sessions)}")
    print("- scenario outcomes remain UNDETERMINED: PASS")
    print("- candidate applicability remains blocked by regulatory TODOs: PASS")
    print("- no rule activation, approval bypass, or official report issue performed")
    print("- no passwords were printed or stored by this script")


if __name__ == "__main__":
    main()
