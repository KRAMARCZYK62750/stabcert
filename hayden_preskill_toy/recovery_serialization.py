"""Canonical JSON serialization and domain-separated content hashes."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any

from .recovery_artifact import (
    CertificateSpec,
    CircuitSpec,
    MetricEntry,
    PetzTargetSpec,
    RecoveryArtifact,
    ResourceSpec,
    TauSupportSpec,
)
from .recovery_problem import (
    CertificationThresholds,
    CouplingGraphSpec,
    GateSpec,
    PauliSpec,
    RecoveryProblem,
    RouterParameters,
)
from .recovery_run_report import RecoveryRunReport, RuntimeEnvironment


# Protocol constants, not names: these strings are hash domain separators.
# Renaming one changes every semantic and document hash, invalidating the
# immutable fixtures and every artifact already issued.  Do not "clean up".
PROBLEM_SEMANTIC_DOMAIN = b"orelia-recovery-problem-semantic/v1\x00"
PROBLEM_DOCUMENT_DOMAIN = b"orelia-recovery-problem-document/v1\x00"
ARTIFACT_DOCUMENT_DOMAIN = b"orelia-recovery-artifact-document/v1\x00"
CIRCUIT_DOMAIN = b"orelia-recovery-circuit/v1\x00"
RUN_REPORT_DOCUMENT_DOMAIN = b"orelia-recovery-run-report-document/v2\x00"


def _strict_object(
    value: Any,
    required: set[str] | frozenset[str],
    *,
    optional: set[str] | frozenset[str] = frozenset(),
    context: str,
) -> None:
    if not isinstance(value, dict):
        raise TypeError(f"{context} must be a JSON object")
    missing = sorted(set(required) - set(value))
    unknown = sorted(set(value) - set(required) - set(optional))
    if missing:
        raise ValueError(f"{context} missing fields: {', '.join(missing)}")
    if unknown:
        raise ValueError(f"{context} contains unknown fields: {', '.join(unknown)}")


def canonical_json_bytes(value: Any) -> bytes:
    """Canonical UTF-8 JSON for the v1 scalar domain.

    V1 intentionally stores certification thresholds and measured values as
    decimal strings. Consequently the canonical domain contains no JSON float,
    avoiding cross-runtime NaN and floating-number normalization ambiguity.
    """
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(domain: bytes, value: Any) -> str:
    return hashlib.sha256(domain + canonical_json_bytes(value)).hexdigest()


def problem_to_dict(problem: RecoveryProblem) -> dict[str, Any]:
    return asdict(problem)


def semantic_problem_dict(problem: RecoveryProblem) -> dict[str, Any]:
    value = problem_to_dict(problem)
    # These fields are non-normative claims/provenance. They are protected by
    # the document hash but do not change the compilation problem itself.
    value.pop("metadata", None)
    value.pop("expected_tau_support", None)
    return value


def semantic_problem_hash(problem: RecoveryProblem) -> str:
    return _sha256(PROBLEM_SEMANTIC_DOMAIN, semantic_problem_dict(problem))


def problem_document_hash(problem: RecoveryProblem) -> str:
    return _sha256(PROBLEM_DOCUMENT_DOMAIN, problem_to_dict(problem))


def artifact_to_dict(artifact: RecoveryArtifact) -> dict[str, Any]:
    return asdict(artifact)


def artifact_document_hash(artifact: RecoveryArtifact) -> str:
    return _sha256(ARTIFACT_DOCUMENT_DOMAIN, artifact_to_dict(artifact))


def circuit_hash(circuit: CircuitSpec) -> str:
    return _sha256(CIRCUIT_DOMAIN, asdict(circuit))


def run_report_to_dict(report: RecoveryRunReport) -> dict[str, Any]:
    return asdict(report)


def run_report_document_hash(report: RecoveryRunReport) -> str:
    return _sha256(RUN_REPORT_DOCUMENT_DOMAIN, run_report_to_dict(report))


def _pauli(value) -> PauliSpec:
    _strict_object(
        value,
        {"qubit_order", "operators", "phase_exponent_mod_4"},
        context="Pauli",
    )
    return PauliSpec(
        tuple(value["qubit_order"]),
        value["operators"],
        int(value["phase_exponent_mod_4"]),
    )


def _gate(value) -> GateSpec:
    _strict_object(value, {"operation", "qubits"}, context="gate")
    return GateSpec(value["operation"], tuple(value["qubits"]))


def _graph(value) -> CouplingGraphSpec:
    _strict_object(
        value,
        {"sites", "edges", "directed", "native_two_qubit_gate"},
        context="coupling graph",
    )
    return CouplingGraphSpec(
        sites=tuple(value["sites"]),
        edges=tuple(tuple(edge) for edge in value["edges"]),
        directed=bool(value["directed"]),
        native_two_qubit_gate=value["native_two_qubit_gate"],
    )


def problem_from_dict(value: dict[str, Any]) -> RecoveryProblem:
    router = value["router"]
    thresholds = value["certification_thresholds"]
    return RecoveryProblem(
        format_version=value["format_version"],
        qubit_order=tuple(value["qubit_order"]),
        channel_input=tuple(value["channel_input"]),
        source_clifford=tuple(_gate(item) for item in value["source_clifford"]),
        ancilla_qubits=tuple(value["ancilla_qubits"]),
        ancilla_initial_stabilizers=tuple(
            _pauli(item) for item in value["ancilla_initial_stabilizers"]
        ),
        accessible_partition=tuple(value["accessible_partition"]),
        inaccessible_partition=tuple(value["inaccessible_partition"]),
        requested_output=tuple(value["requested_output"]),
        logical_qubit_order=tuple(value["logical_qubit_order"]),
        physical_initial_order=tuple(value["physical_initial_order"]),
        coupling_graph=_graph(value["coupling_graph"]),
        allowed_gates=tuple(value["allowed_gates"]),
        depth_convention=value["depth_convention"],
        router=RouterParameters(
            algorithm=router["algorithm"],
            lookahead=int(router["lookahead"]),
            candidate_budget=int(router["candidate_budget"]),
            restore_final_order=bool(router["restore_final_order"]),
        ),
        certification_thresholds=CertificationThresholds(
            thresholds["numerical_tolerance"]
        ),
        petz_reference=value["petz_reference"],
        choi_convention=value["choi_convention"],
        transpose_convention=value["transpose_convention"],
        support_inverse_policy=value["support_inverse_policy"],
        expected_tau_support=tuple(
            _pauli(item) for item in value.get("expected_tau_support", [])
        ),
        metadata=tuple(tuple(item) for item in value.get("metadata", [])),
    )


def artifact_from_dict(value: dict[str, Any]) -> RecoveryArtifact:
    _strict_object(
        value,
        {
            "format_version",
            "source_semantic_problem_hash",
            "source_document_hash",
            "tau_support",
            "petz_target",
            "logical_circuit",
            "routed_circuit",
            "topology",
            "final_permutation",
            "resources",
            "certificate",
            "metrics",
        },
        context="RecoveryArtifact",
    )
    tau = value["tau_support"]
    target = value["petz_target"]
    logical = value["logical_circuit"]
    routed = value["routed_circuit"]
    resources = value["resources"]
    certificate = value["certificate"]
    _strict_object(
        tau,
        {"qubit_order", "signed_generators", "support_rank", "logical_qubits"},
        context="tau_support",
    )
    _strict_object(
        target,
        {"choi_qubit_order", "signed_generators", "representation"},
        context="petz_target",
    )
    for name, circuit in (("logical_circuit", logical), ("routed_circuit", routed)):
        _strict_object(circuit, {"qubit_order", "gates"}, context=name)
    _strict_object(
        resources,
        {
            "logical_depth",
            "routed_depth",
            "logical_cnot",
            "routed_cnot",
            "movement_swaps",
            "restoration_swaps",
            "environment_qubits",
        },
        context="resources",
    )
    _strict_object(
        certificate,
        {
            "target_reduced_choi_signature",
            "candidate_reduced_choi_signature",
            "logical_action_signature",
            "compiler_declared_valid",
        },
        context="certificate",
    )
    for metric in value["metrics"]:
        _strict_object(metric, {"name", "value", "unit"}, context="metric")
    return RecoveryArtifact(
        format_version=value["format_version"],
        source_semantic_problem_hash=value["source_semantic_problem_hash"],
        source_document_hash=value["source_document_hash"],
        tau_support=TauSupportSpec(
            qubit_order=tuple(tau["qubit_order"]),
            signed_generators=tuple(_pauli(item) for item in tau["signed_generators"]),
            support_rank=int(tau["support_rank"]),
            logical_qubits=int(tau["logical_qubits"]),
        ),
        petz_target=PetzTargetSpec(
            choi_qubit_order=tuple(target["choi_qubit_order"]),
            signed_generators=tuple(_pauli(item) for item in target["signed_generators"]),
            representation=target["representation"],
        ),
        logical_circuit=CircuitSpec(
            tuple(logical["qubit_order"]),
            tuple(_gate(item) for item in logical["gates"]),
        ),
        routed_circuit=CircuitSpec(
            tuple(routed["qubit_order"]),
            tuple(_gate(item) for item in routed["gates"]),
        ),
        topology=_graph(value["topology"]),
        final_permutation=tuple(value["final_permutation"]),
        resources=ResourceSpec(**{key: int(item) for key, item in resources.items()}),
        certificate=CertificateSpec(
            target_reduced_choi_signature=tuple(
                certificate["target_reduced_choi_signature"]
            ),
            candidate_reduced_choi_signature=tuple(
                certificate["candidate_reduced_choi_signature"]
            ),
            logical_action_signature=tuple(certificate["logical_action_signature"]),
            compiler_declared_valid=bool(certificate["compiler_declared_valid"]),
        ),
        metrics=tuple(
            MetricEntry(item["name"], item["value"], item["unit"])
            for item in value["metrics"]
        ),
    )


def run_report_from_dict(value: dict[str, Any]) -> RecoveryRunReport:
    environment = value["environment"]
    return RecoveryRunReport(
        format_version=value["format_version"],
        command=value["command"],
        status=value["status"],
        exit_code=int(value["exit_code"]),
        semantic_problem_hash=value["semantic_problem_hash"],
        problem_document_hash=value["problem_document_hash"],
        artifact_document_hash=value["artifact_document_hash"],
        started_at_utc=value["started_at_utc"],
        finished_at_utc=value["finished_at_utc"],
        wall_seconds=value["wall_seconds"],
        peak_rss_mib=value["peak_rss_mib"],
        iterations=int(value["iterations"]),
        verification_policy=value["verification_policy"],
        environment=RuntimeEnvironment(**environment),
        logs=tuple(value["logs"]),
    )


def write_problem(path: str | Path, problem: RecoveryProblem) -> None:
    Path(path).write_bytes(canonical_json_bytes(problem_to_dict(problem)) + b"\n")


def read_problem(path: str | Path) -> RecoveryProblem:
    return problem_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def write_artifact(path: str | Path, artifact: RecoveryArtifact) -> None:
    Path(path).write_bytes(canonical_json_bytes(artifact_to_dict(artifact)) + b"\n")


def read_artifact(path: str | Path) -> RecoveryArtifact:
    return artifact_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def write_run_report(path: str | Path, report: RecoveryRunReport) -> None:
    Path(path).write_bytes(canonical_json_bytes(run_report_to_dict(report)) + b"\n")


def read_run_report(path: str | Path) -> RecoveryRunReport:
    return run_report_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
