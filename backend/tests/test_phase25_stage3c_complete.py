"""Phase 25 Stage 3C completion contracts."""

import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.compliance import stage3_dispatch
from app.compliance.phase7 import CreepEvaluator, StabilityEvaluator, ZeroReturnEvaluator
from app.compliance.phase8 import TiltingEvaluator, WarmUpEvaluator, _tilting_policy
from app.compliance.regulatory import RegulatoryBlocked
from app.compliance.tare import TareEvaluator

REPO = Path(__file__).resolve().parents[2]


def test_stage3c_dispatch_preserves_v1_policy(monkeypatch):
    marker = object()

    monkeypatch.setattr(
        stage3_dispatch,
        "rule_policy_variant",
        lambda *args, **kwargs: ("legacy_v1", marker),
    )

    result = stage3_dispatch.load_stage3_policy_for_runtime(
        ruleset=object(),
        key="RULE",
        legacy_kind="legacy_v1",
        legacy_schema=object,
        v2_kind="policy_v2",
        v2_schema=object,
    )
    assert result is marker


def test_stage3c_dispatch_blocks_v2_instead_of_coercing_to_v1(monkeypatch):
    marker = object()

    monkeypatch.setattr(
        stage3_dispatch,
        "rule_policy_variant",
        lambda *args, **kwargs: ("policy_v2", marker),
    )
    monkeypatch.setattr(
        stage3_dispatch,
        "dependencies",
        lambda *args, **kwargs: SimpleNamespace(rule_references=()),
    )

    with pytest.raises(RegulatoryBlocked) as exc:
        stage3_dispatch.load_stage3_policy_for_runtime(
            ruleset=object(),
            key="SECTION6_ZERO_RETURN_PROCEDURE",
            legacy_kind="legacy_v1",
            legacy_schema=object,
            v2_kind="policy_v2",
            v2_schema=object,
        )

    assert exc.value.resolution.unresolved_rule_ids == (
        "SECTION6_ZERO_RETURN_PROCEDURE",
    )


def test_stage3c_sections_6_to_10_use_dual_policy_dispatch_boundary():
    direct_methods = (
        ZeroReturnEvaluator.validate_procedure,
        ZeroReturnEvaluator.evaluate,
        CreepEvaluator.validate_procedure,
        CreepEvaluator.evaluate,
        StabilityEvaluator.validate_procedure,
        StabilityEvaluator.evaluate,
        TareEvaluator.validate_procedure,
        WarmUpEvaluator.validate_procedure,
        WarmUpEvaluator.evaluate,
    )

    for method in direct_methods:
        assert "load_stage3_policy_for_runtime" in inspect.getsource(method)

    for method in (
        TiltingEvaluator.validate_procedure,
        TiltingEvaluator.evaluate,
    ):
        assert "_tilting_policy" in inspect.getsource(method)
    assert "rule_policy_variant" in inspect.getsource(_tilting_policy)


def test_stage3c_mpe_consumers_use_compatible_v1_v2_mpe_path():
    tilting_source = inspect.getsource(TiltingEvaluator.evaluate)
    tare_validate = inspect.getsource(TareEvaluator.validate_procedure)
    tare_evaluate = inspect.getsource(TareEvaluator.evaluate)
    warm_source = inspect.getsource(WarmUpEvaluator.evaluate)

    assert "calculate_mpe_compatible" in tilting_source
    assert "compatible_mpe_profile" in tare_validate
    assert "calculate_mpe_compatible" in tare_evaluate
    assert "calculate_mpe_compatible" in warm_source


def test_stage3c_does_not_promote_candidate_ruleset():
    root = (
        REPO
        / "backend"
        / "app"
        / "compliance"
        / "rules"
        / "oiml_r76_2006"
    )
    metadata = json.loads((root / "metadata.yaml").read_text(encoding="utf-8"))
    mpe = json.loads((root / "mpe.yaml").read_text(encoding="utf-8"))

    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []
    assert mpe["rules"][0]["key"] == "MPE_PENDING"
    assert mpe["rules"][0]["parameters"][0]["value"] is None


def test_stage3c_resolved_contracts_remain_available_for_native_followup():
    from app.compliance import stage3_resolved

    expected = {
        "resolve_zero_return_policy_v2",
        "resolve_creep_policy_v2",
        "resolve_stability_policy_v2",
        "resolve_tilting_policy_v2",
        "resolve_tare_policy_v2",
        "resolve_warm_up_policy_v2",
    }

    assert expected <= set(stage3_resolved.__all__)
