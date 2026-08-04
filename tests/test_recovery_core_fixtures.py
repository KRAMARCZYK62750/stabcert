from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from hayden_preskill_toy.recovery_artifact import MetricEntry
from hayden_preskill_toy.recovery_compile import compile_recovery
from hayden_preskill_toy.recovery_serialization import (
    circuit_hash,
    read_artifact,
    read_problem,
)
from hayden_preskill_toy.recovery_verify import verify_recovery


FIXTURES = Path("tests/fixtures/recovery_v1")


def test_a1_a8_a12_compile_and_verify_against_immutable_fixtures():
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    assert [row["case_id"] for row in manifest] == ["a1", "a8", "a12"]
    for row in manifest:
        problem = read_problem(FIXTURES / row["problem_file"])
        frozen = read_artifact(FIXTURES / row["artifact_file"])
        compiled = compile_recovery(problem)
        report = verify_recovery(problem, compiled)
        frozen_report = verify_recovery(problem, frozen)
        assert report.verified and frozen_report.verified
        assert circuit_hash(compiled.logical_circuit) == row["logical_circuit_hash"]
        assert circuit_hash(compiled.routed_circuit) == row["routed_circuit_hash"]
        assert compiled.logical_circuit == frozen.logical_circuit
        assert compiled.routed_circuit == frozen.routed_circuit
        assert compiled.tau_support == frozen.tau_support
        assert compiled.petz_target == frozen.petz_target
        assert compiled.resources == frozen.resources
        assert compiled.final_permutation == frozen.final_permutation
        assert compiled.certificate == frozen.certificate
        assert report.target_reduced_choi_signature == frozen_report.target_reduced_choi_signature
        assert report.candidate_reduced_choi_signature == frozen_report.candidate_reduced_choi_signature
        compiled_metrics = {item.name: item.value for item in compiled.metrics}
        frozen_metrics = {item.name: item.value for item in frozen.metrics}
        for name in (
            "petz_entanglement_fidelity",
            "circuit_entanglement_fidelity",
            "reduced_choi_equal",
        ):
            assert abs(float(compiled_metrics[name]) - float(frozen_metrics[name])) < 1e-12


def test_verifier_ignores_declared_verdict_but_rejects_a_false_metric_claim():
    problem = read_problem(FIXTURES / "a1.problem.json")
    artifact = read_artifact(FIXTURES / "a1.artifact.json")
    untrusted_verdict = replace(
        artifact,
        certificate=replace(artifact.certificate, compiler_declared_valid=False),
    )
    assert verify_recovery(problem, untrusted_verdict).verified

    metrics = tuple(
        MetricEntry(item.name, "0" if item.name == "circuit_entanglement_fidelity" else item.value, item.unit)
        for item in artifact.metrics
    )
    tampered = replace(
        artifact,
        metrics=metrics,
        certificate=replace(artifact.certificate, compiler_declared_valid=True),
    )
    report = verify_recovery(problem, tampered)
    assert not report.verified
    assert not next(item for item in report.checks if item.name == "circuit_entanglement_fidelity").passed
