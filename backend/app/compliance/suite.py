"""Registered evaluator mechanics implemented through Phase 11.

Registration does not make candidate regulatory configuration authoritative.  The
engine still applies the RuleSet verification/implementation gates before any
calculation can produce a determined outcome.
"""

from app.compliance.eccentricity import section3_registration
from app.compliance.evaluators import EvaluatorRegistry
from app.compliance.phase7 import (
    creep_registration,
    discrimination_registration,
    sensitivity_registration,
    stability_registration,
    zero_return_registration,
)
from app.compliance.phase8 import (
    temperature_zero_registration,
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
from app.compliance.repeatability import section5_registration
from app.compliance.tare import section9_registration
from app.compliance.weighing import section1_registration

IMPLEMENTED_TEST_CODES = (
    "WEIGHING_PERFORMANCE",
    "TEMPERATURE_ZERO",
    "ECCENTRICITY",
    "REPEATABILITY",
    "DISCRIMINATION",
    "SENSITIVITY",
    "ZERO_RETURN",
    "CREEP",
    "STABILITY_EQUILIBRIUM",
    "TILTING",
    "TARE",
    "WARM_UP",
    "VOLTAGE_VARIATION",
    "DISTURBANCE_VOLTAGE_DIP",
    "DISTURBANCE_BURST",
    "DISTURBANCE_SURGE",
    "DISTURBANCE_ESD",
    "DISTURBANCE_RADIATED_RF",
    "DISTURBANCE_CONDUCTED_RF",
    "DISTURBANCE_VEHICLE_SUPPLY",
    "DAMP_HEAT",
    "SPAN_STABILITY",
    "ENDURANCE",
)


def implemented_registry() -> EvaluatorRegistry:
    return EvaluatorRegistry(
        (
            section1_registration(),
            temperature_zero_registration(),
            section3_registration(),
            section5_registration(),
            discrimination_registration(),
            sensitivity_registration(),
            zero_return_registration(),
            creep_registration(),
            stability_registration(),
            tilting_registration(),
            section9_registration(),
            warm_up_registration(),
            voltage_variation_registration(),
            *disturbance_registrations(),
            damp_heat_registration(),
            span_stability_registration(),
            endurance_registration(),
        )
    )
