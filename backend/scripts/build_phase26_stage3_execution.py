"""Generate the immutable Phase 26 Stage 3 V3 demo artifact + datasets.

This generator is development/demo tooling.  It may import domain-test fixture
builders, but the generated runtime artifact never does.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from app.compliance.demo import (
    DEMO_SOURCE_REFERENCE,
    FULL_DEMO_EXECUTION_EDITION,
    FULL_DEMO_EXECUTION_STANDARD_NAME,
    FULL_DEMO_EXECUTION_VERSION,
)
from app.compliance.domain import InstrumentSnapshot
from app.compliance.engine import R76Engine
from app.compliance.full_demo import full_demo_registry, load_full_demo_run_ruleset
from app.compliance.ruleset import RuleSet
from domain_tests.fixtures import core_reusable as core
from domain_tests.fixtures import phase7_functional_time as p7
from domain_tests.fixtures import phase8_influence as p8
from domain_tests.fixtures import phase9_climatic as p9
from domain_tests.fixtures import phase10_disturbances as p10
from domain_tests.fixtures import phase11_endurance as p11
from domain_tests.fixtures import weighing
from domain_tests.fixtures.synthetic import instrument

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "app" / "compliance" / "demo_artifacts"
RULESET_PATH = OUT / "phase26_full_demo_v3_ruleset.json"
DATA_PATH = OUT / "phase26_full_demo_v3_data.json"

SOURCE = {
    "part": "SYNTHETIC",
    "edition": FULL_DEMO_EXECUTION_EDITION,
    "identity": "SYNTHETIC TEST FIXTURE — SIH26035 V3 EXECUTION MATRIX ONLY",
    "clause": "demo-execution-matrix-only",
    "digest": "3" * 64,
}


def verification(key: str) -> dict:
    return {
        "status": "VERIFIED",
        "verified_by": "SIH26035 V3 DEMO FIXTURE — NOT REGULATORY VERIFIER",
        "verified_at": "2000-01-01T00:00:00Z",
        "evidence": f"SYNTHETIC-DEMO-EXECUTION:{key}",
    }


@dataclass(frozen=True)
class Provider:
    code: str
    rules: Callable[[], RuleSet]
    context: Callable[[], object]
    observations: Callable[[], object]


DISTURBANCE_CODES = (
    "DISTURBANCE_VOLTAGE_DIP",
    "DISTURBANCE_BURST",
    "DISTURBANCE_SURGE",
    "DISTURBANCE_ESD",
    "DISTURBANCE_RADIATED_RF",
    "DISTURBANCE_CONDUCTED_RF",
    "DISTURBANCE_VEHICLE_SUPPLY",
)


def providers() -> tuple[Provider, ...]:
    values = [
        Provider(
            "WEIGHING_PERFORMANCE",
            weighing.fixture_rules,
            weighing.fixture_context,
            partial(weighing.fixture_observations, error="0"),
        ),
        Provider(
            "TEMPERATURE_ZERO",
            partial(p8.temperature_rules, accuracy_class="III"),
            partial(p8.temperature_context, accuracy_class="III"),
            partial(p8.temperature_observations, accuracy_class="III"),
        ),
        Provider(
            "ECCENTRICITY",
            core.eccentricity_rules,
            core.eccentricity_context,
            core.eccentricity_observations,
        ),
        Provider(
            "DISCRIMINATION",
            partial(p7.discrimination_rules, mode="DIGITAL"),
            partial(p7.discrimination_context, mode="DIGITAL"),
            partial(p7.discrimination_observations, mode="DIGITAL"),
        ),
        Provider(
            "SENSITIVITY",
            p7.sensitivity_rules,
            p7.sensitivity_context,
            p7.sensitivity_observations,
        ),
        Provider(
            "REPEATABILITY",
            core.repeatability_rules,
            core.repeatability_context,
            core.repeatability_observations,
        ),
        Provider(
            "ZERO_RETURN",
            p7.zero_return_rules,
            p7.zero_return_context,
            p7.zero_return_observations,
        ),
        Provider(
            "CREEP",
            partial(p7.creep_rules, mode="SHORT"),
            partial(p7.creep_context, mode="SHORT"),
            partial(p7.creep_observations, mode="SHORT"),
        ),
        Provider(
            "STABILITY_EQUILIBRIUM",
            p7.stability_rules,
            p7.stability_context,
            p7.stability_observations,
        ),
        Provider(
            "TILTING",
            partial(p8.tilting_rules, mode="NO_LEVEL_DEVICE"),
            partial(p8.tilting_context, mode="NO_LEVEL_DEVICE"),
            partial(p8.tilting_observations, mode="NO_LEVEL_DEVICE"),
        ),
        Provider(
            "TARE",
            core.tare_rules,
            core.tare_context,
            core.tare_observations,
        ),
        Provider(
            "WARM_UP",
            p8.warm_up_rules,
            p8.warm_up_context,
            p8.warm_up_observations,
        ),
        Provider(
            "VOLTAGE_VARIATION",
            partial(p8.voltage_rules, profile="AC_MAINS"),
            partial(p8.voltage_context, profile="AC_MAINS"),
            partial(p8.voltage_observations, profile="AC_MAINS"),
        ),
    ]
    values.extend(
        Provider(
            code,
            partial(p10.disturbance_rules, code),
            partial(p10.disturbance_context, code),
            partial(p10.disturbance_observations, code),
        )
        for code in DISTURBANCE_CODES
    )
    values.extend(
        (
            Provider(
                "DAMP_HEAT",
                partial(p9.damp_heat_rules, accuracy_class="III"),
                p9.damp_heat_context,
                p9.damp_heat_observations,
            ),
            Provider(
                "SPAN_STABILITY",
                p9.span_rules,
                p9.span_context,
                p9.span_observations,
            ),
            Provider(
                "ENDURANCE",
                p11.endurance_rules,
                p11.endurance_context,
                p11.endurance_observations,
            ),
        )
    )
    return tuple(values)


def execution_instrument() -> InstrumentSnapshot:
    return instrument(
        accuracy_class="III",
        indication_type="DIGITAL",
        is_self_indicating=False,
        is_electronic=True,
        is_software_controlled=True,
        is_portable=False,
        is_mobile=False,
        load_receptor_type="RECTANGULAR",
        support_point_count=4,
        tare_type="SUBTRACTIVE",
        maximum_tare_g="5000",
        zero_setting_type="AUTOMATIC",
        zero_tracking_available=True,
        level_indicator_available=False,
        automatic_tilt_sensor=False,
        power_supply_type="AC",
        nominal_voltage="230",
        min_voltage="200",
        max_voltage="250",
        declared_temp_min_c="-10",
        declared_temp_max_c="40",
        software_identifier="SIH26035-V3-DEMO",
        is_direct_sales=False,
        is_price_computing=False,
        is_labeling=False,
        data_storage_device_present=True,
        printing_device_present=True,
        extended_indication_available=True,
        embedded_software_present=True,
        loadable_software_present=False,
        interfaces=(),
        peripherals=(),
        components=(),
        battery_charging_during_operation=False,
        vehicle_powered=True,
        conducted_rf_path_available=True,
        vehicle_power_details="SYNTHETIC SOFTWARE EXERCISE MATRIX",
        declared_operating_conditions="SYNTHETIC SIH DEMO ONLY",
        declared_installation="SYNTHETIC LABORATORY DEMONSTRATION",
    )


def _normalized_rule(rule: dict, code: str, context) -> dict:
    mapping = {
        "BASE": f"DEMO3_BASE_{code}",
        "APP": f"DEMO3_APP_{code}",
    }
    data = dict(rule)
    data["key"] = mapping.get(data["key"], data["key"])
    data["dependencies"] = [
        mapping.get(value, value) for value in data.get("dependencies", [])
    ]
    data["source"] = SOURCE
    data["verification"] = verification(data["key"])
    data["blockers"] = []

    if data["kind"] == "applicability_policy_v1":
        parameters = list(data.get("parameters", []))
        policy_rows = [
            item for item in parameters if item.get("name") == "POLICY_JSON"
        ]
        if len(policy_rows) != 1:
            raise ValueError(f"{code}: synthetic applicability policy missing")
        policy = json.loads(policy_rows[0]["value"])
        policy["scope"] = "EACH_RANGE"
        policy["scenarios"] = [
            {
                "procedure_variant": context.procedure_variant,
                "scenario": context.scenario,
            }
        ]
        policy["cases"] = [
            {
                "when": {"kind": "always"},
                "decision": "REQUIRED",
                "reason": (
                    "SYNTHETIC V3 SOFTWARE EXERCISE MATRIX ONLY — "
                    "branch forced for evaluator demonstration"
                ),
            }
        ]
        policy_rows[0]["value"] = json.dumps(
            policy,
            sort_keys=True,
            separators=(",", ":"),
        )
        data["parameters"] = parameters
    return data


def _normalized_base_rule(rule) -> dict:
    data = rule.model_dump(mode="python")
    data["source"] = SOURCE
    data["verification"] = verification(data["key"])
    data["blockers"] = []
    return data


def build() -> tuple[RuleSet, dict]:
    provider_rows = providers()
    if len(provider_rows) != 23:
        raise ValueError("Stage 3 requires exactly 23 evaluator providers")
    if len({item.code for item in provider_rows}) != 23:
        raise ValueError("Duplicate Stage 3 evaluator provider")

    base = load_full_demo_run_ruleset()
    rules = {item.key: _normalized_base_rule(item) for item in base.rules}
    tests = {
        item.code: (
            item.model_dump(mode="python")
            | {
                "source": SOURCE,
                "verification": verification(item.code),
            }
        )
        for item in base.tests
    }

    datasets = []
    contexts = {}
    observations = {}
    for provider in provider_rows:
        fixture_ruleset = provider.rules()
        context = provider.context()
        batch = provider.observations()
        contexts[provider.code] = context
        observations[provider.code] = batch

        if context.test_code != provider.code or batch.test_code != provider.code:
            raise ValueError(f"{provider.code}: fixture code mismatch")
        fixture_test = next(
            item for item in fixture_ruleset.tests if item.code == provider.code
        )
        mapping = {
            "BASE": f"DEMO3_BASE_{provider.code}",
            "APP": f"DEMO3_APP_{provider.code}",
        }

        for rule in fixture_ruleset.rules:
            normalized = _normalized_rule(
                rule.model_dump(mode="python"),
                provider.code,
                context,
            )
            rules[normalized["key"]] = normalized

        target = tests[provider.code]
        target["dependencies"] = [
            mapping.get(value, value)
            for value in fixture_test.dependencies
        ]
        target["implemented"] = True
        target["source"] = SOURCE
        target["verification"] = verification(provider.code)

        datasets.append(
            {
                "test_code": provider.code,
                "section": target["section"],
                "procedure_context": context.model_dump(mode="json"),
                "observation_batch": {
                    "test_code": batch.test_code,
                    "protocol": batch.protocol,
                    "observation_schema_version": (
                        batch.observation_schema_version
                    ),
                    "rows": [
                        row.model_dump(mode="json")
                        for row in batch.rows
                    ],
                },
                "expected_evaluation_status": "COMPLETE",
                "expected_compliance_outcome": "COMPLIANT",
            }
        )

    checklist = []
    for item in base.checklist:
        data = item.model_dump(mode="python")
        data["source"] = SOURCE
        data["verification"] = verification(item.key)
        checklist.append(data)

    ruleset = RuleSet.model_validate(
        {
            "metadata": {
                "schema_version": 1,
                "standard_code": "OIML_R76",
                "standard_name": FULL_DEMO_EXECUTION_STANDARD_NAME,
                "edition": FULL_DEMO_EXECUTION_EDITION,
                "version": FULL_DEMO_EXECUTION_VERSION,
                "standard_parts": [SOURCE],
                "supported_test_codes": sorted(
                    item.code for item in provider_rows
                ),
                "source_reference": DEMO_SOURCE_REFERENCE,
            },
            "rules": list(rules.values()),
            "tests": list(tests.values()),
            "checklist": checklist,
        }
    )

    common_instrument = execution_instrument()
    engine = R76Engine(full_demo_registry())
    result_rows = []
    for item in datasets:
        code = item["test_code"]
        result = engine.evaluate(
            test_code=code,
            instrument_snapshot=common_instrument,
            procedure_context=contexts[code],
            observations=observations[code],
            ruleset=ruleset,
        )
        if (
            result.evaluation_status != "COMPLETE"
            or result.compliance_outcome != "COMPLIANT"
            or result.synthetic_fixture is not True
        ):
            raise RuntimeError(
                f"{code}: Stage 3 fixture did not evaluate COMPLIANT "
                f"({result.evaluation_status}/{result.compliance_outcome})"
            )
        result_rows.append(
            {
                "test_code": code,
                "evaluation_status": str(result.evaluation_status),
                "compliance_outcome": str(result.compliance_outcome),
                "synthetic_fixture": result.synthetic_fixture,
                "input_hash": result.input_hash,
            }
        )

    data = {
        "schema_version": 1,
        "artifact": "sih26035_full_flow_demo_v3",
        "ruleset_version": FULL_DEMO_EXECUTION_VERSION,
        "evaluation_context": "SYNTHETIC",
        "instrument_snapshot": common_instrument.model_dump(mode="json"),
        "datasets": sorted(datasets, key=lambda item: item["test_code"]),
        "verified_results": sorted(
            result_rows,
            key=lambda item: item["test_code"],
        ),
        "notice": (
            "SYNTHETIC SOFTWARE EXERCISE MATRIX ONLY; NOT A PHYSICALLY "
            "COHERENT REGULATORY TEST PROGRAM AND NOT AN OIML CONCLUSION."
        ),
    }
    return ruleset, data


def main() -> None:
    ruleset, data = build()
    OUT.mkdir(parents=True, exist_ok=True)
    RULESET_PATH.write_text(
        json.dumps(
            ruleset.snapshot(),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    DATA_PATH.write_text(
        json.dumps(
            data,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print("Phase 26 Stage 3 generated artifacts: PASS")
    print(f"- ruleset: {RULESET_PATH.relative_to(ROOT)}")
    print(f"- data: {DATA_PATH.relative_to(ROOT)}")
    print("- evaluator datasets: 23")
    print("- deterministic COMPLIANT evaluations: 23")


if __name__ == "__main__":
    main()
