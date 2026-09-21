import json
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.compliance.canonical import (
    EvaluationInputSnapshot,
    canonical_bytes,
    content_hash,
    evaluation_input_snapshot,
    normalize,
    strict_json,
)
from app.compliance.domain import ComplianceResult, ObservationBatch
from domain_tests.fixtures.synthetic import (
    CODE,
    FixtureObservation,
    FixtureObservationV2,
    context,
    engine,
    evaluate,
    instrument,
    observations,
    ruleset,
)


def snapshot(**changes):
    return evaluation_input_snapshot(
        **(
            dict(
                test_code=CODE,
                instrument_snapshot=instrument(),
                procedure_context=context(),
                observations=observations(),
                ruleset_configuration_hash=ruleset().configuration_hash,
                engine_version=engine().engine_version,
            )
            | changes
        )
    )


@pytest.mark.parametrize("value", ["10", "10.0", "10.000", "1E+1", "+0010.000"])
def test_canonical_decimal(value):
    assert canonical_bytes(Decimal(value)) == b'"10"'
    assert content_hash(Decimal(value)) == content_hash(Decimal("10"))


@pytest.mark.parametrize("value", ["-0", "-0.000", "0.00", "0E+9"])
def test_negative_zero(value):
    assert normalize(Decimal(value)) == "0"


def test_unicode_object_keys_times_and_explicit_nulls():
    assert canonical_bytes({"b": None, "a": "e\u0301"}) == canonical_bytes({"a": "é", "b": None})
    utc = datetime(2026, 1, 2, 3, 4, 5, 6, tzinfo=UTC)
    equivalent = utc.astimezone(timezone(timedelta(hours=5, minutes=30)))
    assert canonical_bytes(utc) == canonical_bytes(equivalent) == b'"2026-01-02T03:04:05.000006Z"'
    assert canonical_bytes(["a", "b"]) != canonical_bytes(["b", "a"])
    assert "maximum_tare_g" in normalize(instrument())
    assert normalize(instrument())["maximum_tare_g"] is None
    for bad in (datetime(2026, 1, 1), 1.0, Decimal("NaN"), {"é": 1, "e\u0301": 2}):
        with pytest.raises(ValueError):
            canonical_bytes(bad)


@pytest.mark.parametrize(
    "text", ['{"a":1,"a":2}', '{"é":1,"e\\u0301":2}', '{"a":NaN}', '{"a":Infinity}']
)
def test_duplicate_json_keys_and_nonfinite_rejected(text):
    with pytest.raises(ValueError):
        strict_json(text)


def test_exact_canonical_input_fields_and_ordering():
    current = snapshot()
    assert set(normalize(current)) == {
        "hash_schema_version",
        "instrument_snapshot",
        "test_code",
        "procedure_context",
        "observations",
        "ruleset_configuration_hash",
        "observation_schema_version",
        "engine_version",
    }
    assert current.hash_schema_version == "v1" and current.engine_version == engine().engine_version
    assert (
        current.input_hash
        == snapshot(observations=observations(rows=tuple(reversed(observations().rows)))).input_hash
    )
    direct = EvaluationInputSnapshot(
        **(
            current.model_dump()
            | {"procedure_context": context(), "observations": tuple(reversed(observations().rows))}
        )
    )
    assert direct.input_hash == current.input_hash
    with pytest.raises(ValidationError):
        EvaluationInputSnapshot(**(current.model_dump() | {"evaluated_at": "2026-01-01"}))


@pytest.mark.parametrize(
    "change", ["observation", "context", "range", "ruleset_hash", "schema", "engine"]
)
def test_meaningful_input_change_changes_hash(change):
    before = snapshot()
    if change == "observation":
        after = snapshot(observations=observations(error="21"))
    elif change == "context":
        after = snapshot(procedure_context=context(zero_error_g="1"))
    elif change == "range":
        cap = instrument().ranges[0].model_dump() | {"scale_interval_d_g": "5"}
        after = snapshot(instrument_snapshot=instrument(scale_interval_d_g="5", ranges=[cap]))
    elif change == "ruleset_hash":
        after = snapshot(ruleset_configuration_hash="f" * 64)
    elif change == "schema":
        rows = tuple(
            FixtureObservationV2(**(r.model_dump() | {"observation_schema_version": "v2"}))
            for r in observations().rows
        )
        batch = ObservationBatch(
            test_code=CODE, protocol="SYNTHETIC", observation_schema_version="v2", rows=rows
        )
        after = snapshot(observations=batch)
    else:
        after = snapshot(engine_version="r76-domain-next")
    assert after.input_hash != before.input_hash


def test_nfc_timezone_decimal_equivalence_in_full_input_and_result():
    first = snapshot(procedure_context=context(protocol_note="é", zero_error_g="0.000"))
    ctx = context(
        protocol_note="e\u0301",
        environment=dict(measured_at="2000-01-01T05:30:00+05:30", temperature_c="20.000"),
    )
    second = snapshot(procedure_context=ctx)
    assert first.input_hash == second.input_hash
    row = observations().rows[1]
    changed = FixtureObservation(
        **(row.model_dump() | {"measured_at": "2000-01-01T05:30:02+05:30"})
    )
    assert (
        snapshot(observations=observations(rows=(observations().rows[0], changed))).input_hash
        == snapshot().input_hash
    )
    assert (
        evaluate(procedure_context=context(protocol_note="é")).result_hash
        == evaluate(procedure_context=context(protocol_note="e\u0301")).result_hash
    )


def test_ordered_stages_are_not_reordered_and_unordered_features_are_sorted():
    assert (
        snapshot(procedure_context=context(stages=("LOAD", "ZERO"))).input_hash
        != snapshot().input_hash
    )
    first = instrument(
        peripherals=("printer", "display"), interfaces=[dict(name="USB"), dict(name="RS232")]
    )
    second = instrument(
        peripherals=("display", "printer"), interfaces=[dict(name="RS232"), dict(name="USB")]
    )
    assert (
        snapshot(instrument_snapshot=first).input_hash
        == snapshot(instrument_snapshot=second).input_hash
    )
    with pytest.raises(ValueError):
        instrument(peripherals=("é", "e\u0301"))


def test_result_hash_determinism_meaningful_change_and_no_persistence_metadata():
    first, second = evaluate(), evaluate()
    assert first.result_hash == second.result_hash and first.input_hash == second.input_hash
    assert evaluate(observations=observations(error="19")).result_hash != first.result_hash
    assert not {"id", "evaluated_at", "actor_id", "result_hash"} & set(normalize(first))
    with pytest.raises(ValidationError):
        ComplianceResult(**(first.model_dump() | {"id": "record-id"}))
    # Persistence metadata is outside the explicit engine contract, never filtered
    # out of arbitrary JSON supplied as an evaluation input.
    record_a = {"id": "a", "evaluated_at": "yesterday", "value": first}
    record_b = {"id": "b", "evaluated_at": "today", "value": second}
    assert record_a["value"].result_hash == record_b["value"].result_hash


def test_canonical_v1_golden_bytes():
    value = {
        "null": None,
        "text": "e\u0301",
        "decimal": Decimal("-0.000"),
        "measured_at": datetime(2000, 1, 1, tzinfo=UTC),
        "ordered": ("b", "a"),
    }
    expected = (
        '{"decimal":"0","measured_at":"2000-01-01T00:00:00.000000Z",'
        '"null":null,"ordered":["b","a"],"text":"é"}'
    ).encode()
    assert canonical_bytes(value) == expected


def test_full_engine_golden_snapshot_and_result():
    golden = json.loads((Path(__file__).parent / "fixtures" / "golden-v1.json").read_text())
    assert normalize(snapshot()) == golden["input"]
    assert normalize(evaluate()) == golden["result"]
    assert snapshot().input_hash == golden["input_hash"]
    assert evaluate().result_hash == golden["result_hash"]
