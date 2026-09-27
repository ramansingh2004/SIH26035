"""Phase 25 Fix 8: conditional RF applicability/profile selection."""

import pytest

from app.compliance.applicability import BooleanFact, predicate_value
from app.compliance.parameterized import (
    PolicyResolutionError,
    PolicySelector,
    selector_state,
)
from app.compliance.parameterized_stage4 import DisturbancePolicyV2
from domain_tests.fixtures.synthetic import instrument


def _profile(path_available, start_mhz):
    return {
        "procedure_variant": "RADIATED_RF",
        "evaluation_context": "SYNTHETIC",
        "selector": {
            "conducted_rf_path_available": path_available,
        },
        "severities": [
            {
                "severity_id": f"rf-{start_mhz}",
                "standard_reference": "SYNTHETIC-STANDARD",
                "application": "RADIATED_SWEEP",
                "frequency_start_mhz": str(start_mhz),
                "frequency_end_mhz": "2000",
            }
        ],
        "repetitions_per_severity": 1,
        "minimum_interval_seconds": None,
        "deviation_limit_multiplier_e": "1",
        "deviation_operator": "<=",
        "deviation_semantics": "ABSOLUTE",
        "require_warm_up": True,
        "require_environment_stabilized": True,
        "require_peripherals_connected": False,
        "require_no_load_deviation": False,
        "require_environment": False,
        "require_equipment": False,
        "require_certificate": False,
        "require_evidence": True,
        "require_fault_response_evidence": True,
        "require_state_trace": True,
        "require_monotonic_timestamps": True,
        "accepted_fault_responses": [],
    }


def policy():
    return DisturbancePolicyV2.model_validate(
        {
            "schema_version": "v2",
            "test_code": "DISTURBANCE_RADIATED_RF",
            "profiles": [
                _profile(True, 80),
                _profile(False, 26),
            ],
        }
    )


@pytest.mark.parametrize(
    "value, expected_start",
    [(True, "80"), (False, "26")],
)
def test_rf_profile_is_selected_from_explicit_raw_path_fact(value, expected_start):
    selected = policy().select(
        "RADIATED_RF",
        instrument(conducted_rf_path_available=value),
        "SYNTHETIC",
    )
    assert str(selected.severities[0].frequency_start_mhz) == expected_start


def test_unknown_rf_path_fact_fails_closed():
    with pytest.raises(PolicyResolutionError):
        policy().select(
            "RADIATED_RF",
            instrument(conducted_rf_path_available=None),
            "SYNTHETIC",
        )


@pytest.mark.parametrize(
    "value,expected",
    [(True, True), (False, False), (None, None)],
)
def test_applicability_predicate_preserves_three_valued_rf_path_fact(value, expected):
    predicate = BooleanFact(
        kind="boolean",
        feature="conducted_rf_path_available",
        expected=True,
    )
    assert (
        predicate_value(
            predicate,
            instrument(conducted_rf_path_available=value),
        )
        is expected
    )


def test_general_policy_selector_preserves_three_valued_rf_path_fact():
    selector = PolicySelector(conducted_rf_path_available=True)
    assert (
        selector_state(
            selector,
            instrument(conducted_rf_path_available=True),
            "SYNTHETIC",
        )
        is True
    )
    assert (
        selector_state(
            selector,
            instrument(conducted_rf_path_available=False),
            "SYNTHETIC",
        )
        is False
    )
    assert (
        selector_state(
            selector,
            instrument(conducted_rf_path_available=None),
            "SYNTHETIC",
        )
        is None
    )
