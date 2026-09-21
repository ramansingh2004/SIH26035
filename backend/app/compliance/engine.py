"""Standalone deterministic orchestration. Inputs are already-loaded immutable values."""

from dataclasses import dataclass

from app.compliance.applicability import ApplicabilityEngine
from app.compliance.canonical import ENGINE_VERSION, evaluation_input_snapshot
from app.compliance.domain import (
    Applicability,
    ApplicabilityDecision,
    ComplianceOutcome,
    ComplianceResult,
    EvaluationStatus,
    InstrumentSnapshot,
    ObservationBatch,
    ProcedureContext,
    RangeProcedureContext,
)
from app.compliance.evaluators import EvaluatorRegistry
from app.compliance.numbers import EvaluationNotPossible
from app.compliance.regulatory import (
    RegulatoryBlocked,
    dependencies,
    reference,
    rule_policy,
    verified,
)
from app.compliance.ruleset import TODO, RuleSet


def synthetic_artifact(ruleset: RuleSet) -> bool:
    """Fixture status can never be inferred merely from a verified rule flag."""
    return (
        ruleset.metadata.version.startswith("SYNTHETIC_TEST_")
        and ruleset.metadata.source_reference == "SYNTHETIC TEST FIXTURE ONLY"
        and all(
            s.identity.startswith("SYNTHETIC TEST FIXTURE") for s in ruleset.metadata.standard_parts
        )
    )


@dataclass(frozen=True)
class R76Engine:
    registry: EvaluatorRegistry = EvaluatorRegistry()

    @property
    def engine_version(self):
        implementations = tuple(
            sorted(
                r.test_code + "@" + r.implementation_version for r in self.registry.registrations
            )
        )
        return ENGINE_VERSION + ("|" + ";".join(implementations) if implementations else "")

    def evaluate(
        self,
        *,
        test_code: str,
        instrument_snapshot: InstrumentSnapshot,
        procedure_context: ProcedureContext,
        observations: ObservationBatch,
        ruleset: RuleSet,
    ) -> ComplianceResult:
        registration = self.registry.find(test_code)
        if (
            not isinstance(instrument_snapshot, InstrumentSnapshot)
            or not isinstance(procedure_context, ProcedureContext)
            or not isinstance(observations, ObservationBatch)
            or not isinstance(ruleset, RuleSet)
        ):
            raise TypeError("Engine requires typed immutable domain inputs")
        if isinstance(procedure_context, RangeProcedureContext):
            instrument_snapshot.select_range(procedure_context.range_no)
        instrument_snapshot = InstrumentSnapshot.model_validate(
            instrument_snapshot.model_dump(mode="python")
        )
        if registration is not None:
            procedure_context = registration.contexts.validate(procedure_context)
            observations = registration.observations.validate(observations)
        snapshot = evaluation_input_snapshot(
            test_code=test_code,
            instrument_snapshot=instrument_snapshot,
            procedure_context=procedure_context,
            observations=observations,
            ruleset_configuration_hash=ruleset.configuration_hash,
            engine_version=self.engine_version,
        )
        test = next((t for t in ruleset.tests if t.code == test_code), None)
        if test is None:
            raise ValueError("Test absent from pinned catalog")
        required = test.dependencies
        if registration:
            required += registration.evaluator.required_rules(
                instrument_snapshot=instrument_snapshot, procedure_context=procedure_context
            )
        resolution = dependencies(ruleset, required)
        policy_blockers = set()
        if registration and resolution.verified:
            schemas = {p.kind: p.schema for p in registration.policy_schemas}
            required_keys = {r.rule_id for r in resolution.rule_references}
            for rule in ruleset.rules:
                if rule.key not in required_keys or rule.kind == "dependency_v1":
                    continue
                if rule.kind not in schemas:
                    policy_blockers.add(rule.key)
                    continue
                try:
                    rule_policy(ruleset, rule.key, rule.kind, schemas[rule.kind])
                except RegulatoryBlocked as exc:
                    policy_blockers.update(exc.resolution.unresolved_rule_ids)
        applicability_args = dict(
            test_code=test_code,
            instrument_snapshot=instrument_snapshot,
            ruleset=ruleset,
            procedure_variant=procedure_context.procedure_variant,
        )
        if isinstance(procedure_context, RangeProcedureContext):
            applicability_args |= dict(
                range_no=procedure_context.range_no, scenario=procedure_context.scenario
            )
        decision = ApplicabilityEngine().determine(**applicability_args)
        # Dependency blockers take precedence over unknown facts or procedure issues.
        unresolved = (
            set(resolution.unresolved_rule_ids)
            | set(decision.unresolved_rule_ids)
            | policy_blockers
        )
        refs = {r.rule_id: r for r in (*resolution.rule_references, reference(test, test_code))}
        fixture = bool(registration and registration.synthetic_fixture)
        if registration is None:
            unresolved.add(test_code + ":UNSUPPORTED_EVALUATOR")
        if not verified(test):
            unresolved.add(test_code)
        if test_code not in ruleset.metadata.supported_test_codes:
            unresolved.add(test_code + ":UNSUPPORTED_TEST")
        # The candidate catalog's implemented=False stays unchanged. Only isolated,
        # labelled synthetic artifacts paired with fixture registrations exercise
        # calculations in Phase 4; their results remain explicitly non-regulatory.
        if fixture:
            if not synthetic_artifact(ruleset):
                unresolved.add(test_code + ":FIXTURE_ARTIFACT_REQUIRED")
        elif not test.implemented or synthetic_artifact(ruleset):
            unresolved.add(test_code + ":NOT_IMPLEMENTED")
        common = dict(
            test_code=test_code,
            ruleset_version=ruleset.metadata.version,
            ruleset_configuration_hash=ruleset.configuration_hash,
            engine_version=self.engine_version,
            input_hash=snapshot.input_hash,
            synthetic_fixture=fixture,
            rule_references=tuple(refs[k] for k in sorted(refs)),
        )

        def result(status, outcome, *, issue=None, reasons=(), **fields):
            return ComplianceResult(
                **common,
                applicability=decision,
                evaluation_status=status,
                compliance_outcome=outcome,
                issue_code=issue,
                reasons=reasons,
                **fields,
            )

        if unresolved:
            decision = ApplicabilityDecision(
                applicability=Applicability.REQUIRES_REVIEW,
                reason="Missing, unverified or unsupported regulatory dependencies",
                unresolved_rule_ids=tuple(sorted(unresolved)),
                rule_references=common["rule_references"],
                range_no=decision.range_no,
                scenario=decision.scenario,
            )
            return result(
                EvaluationStatus.REVIEW_REQUIRED,
                ComplianceOutcome.UNDETERMINED,
                issue=TODO,
                reasons=(decision.reason,),
                unresolved_rule_ids=tuple(sorted(unresolved)),
            )
        if decision.applicability == Applicability.REQUIRES_REVIEW:
            return result(
                EvaluationStatus.REVIEW_REQUIRED,
                ComplianceOutcome.UNDETERMINED,
                issue="INSTRUMENT_FACTS_REQUIRED",
                reasons=(decision.reason,),
            )
        # Evaluators must agree with the generic verified applicability policy.
        refined = registration.evaluator.applicability(
            instrument_snapshot=instrument_snapshot,
            procedure_context=procedure_context,
            ruleset=ruleset,
        )
        if refined != decision:
            raise ValueError("Evaluator applicability disagrees with pinned policy")
        if decision.applicability == Applicability.NOT_APPLICABLE:
            return result(
                EvaluationStatus.COMPLETE,
                ComplianceOutcome.NOT_APPLICABLE,
                reasons=(decision.reason,),
            )
        args = dict(
            instrument_snapshot=instrument_snapshot,
            procedure_context=procedure_context,
            observations=observations,
            ruleset=ruleset,
        )
        try:
            issues = registration.evaluator.validate_procedure(**args)
            if issues:
                return result(
                    EvaluationStatus.INCOMPLETE,
                    ComplianceOutcome.UNDETERMINED,
                    issue=issues[0].code,
                    reasons=tuple(i.reason for i in issues),
                    procedure_issues=issues,
                )
            output = registration.evaluator.evaluate(**args)
        except RegulatoryBlocked as exc:
            return result(
                EvaluationStatus.REVIEW_REQUIRED,
                ComplianceOutcome.UNDETERMINED,
                issue=TODO,
                reasons=(str(exc),),
                unresolved_rule_ids=exc.resolution.unresolved_rule_ids,
            )
        except EvaluationNotPossible as exc:
            return result(
                EvaluationStatus.INCOMPLETE,
                ComplianceOutcome.UNDETERMINED,
                issue=exc.code,
                reasons=(str(exc),),
            )
        return result(
            EvaluationStatus.COMPLETE,
            output.compliance_outcome,
            reasons=output.reasons,
            calculations=output.calculations,
            acceptance_limits=output.acceptance_limits,
            failed_conditions=output.failed_conditions,
        )
