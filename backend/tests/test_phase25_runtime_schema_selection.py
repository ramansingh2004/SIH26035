"""Explicit runtime schema selection regression contracts."""

import pytest

from app.compliance.phase7 import (
    creep_registration,
    stability_registration,
    zero_return_registration,
)
from app.compliance.phase8 import (
    tilting_registration,
    voltage_variation_registration,
    warm_up_registration,
)
from app.compliance.phase9 import (
    damp_heat_registration,
    span_stability_registration,
)
from app.compliance.phase10 import disturbance_registrations
from app.compliance.phase11 import endurance_registration
from app.compliance.tare import section9_registration


@pytest.mark.parametrize(
    ("registration", "variant"),
    (
        (zero_return_registration(), "ZERO_RETURN"),
        (creep_registration(), "SHORT"),
        (creep_registration(), "EXTENDED"),
        (stability_registration(), "FUNCTIONAL"),
        (tilting_registration(), "LEVEL_INDICATOR"),
        (section9_registration(), "DIGITAL_PRE_ROUNDING"),
        (warm_up_registration(), "WARM_UP"),
        (voltage_variation_registration(), "AC_MAINS"),
        (damp_heat_registration(), "STEADY_STATE"),
        (span_stability_registration(), "LONG_DURATION"),
        (endurance_registration(), "MECHANICAL_CYCLING"),
    ),
)
def test_dual_schema_registration_uses_explicit_v1_runtime(
    registration,
    variant,
):
    assert registration.runtime_schema_versions(variant) == ("v1", "v1")


def test_disturbance_registrations_use_explicit_v1_runtime():
    for registration in disturbance_registrations():
        variants = {
            item.procedure_variant
            for item in registration.contexts.registrations
            if item.procedure_schema_version == "v1"
        }

        for variant in variants:
            assert registration.runtime_schema_versions(variant) == (
                "v1",
                "v1",
            )
