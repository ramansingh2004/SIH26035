"""Registered evaluator mechanics implemented through Phase 6.

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
from app.compliance.repeatability import section5_registration
from app.compliance.tare import section9_registration
from app.compliance.weighing import section1_registration

IMPLEMENTED_TEST_CODES = (
    "WEIGHING_PERFORMANCE",
    "ECCENTRICITY",
    "REPEATABILITY",
    "DISCRIMINATION",
    "SENSITIVITY",
    "ZERO_RETURN",
    "CREEP",
    "STABILITY_EQUILIBRIUM",
    "TARE",
)


def implemented_registry() -> EvaluatorRegistry:
    return EvaluatorRegistry(
        (
            section1_registration(),
            section3_registration(),
            section5_registration(),
            discrimination_registration(),
            sensitivity_registration(),
            zero_return_registration(),
            creep_registration(),
            stability_registration(),
            section9_registration(),
        )
    )
