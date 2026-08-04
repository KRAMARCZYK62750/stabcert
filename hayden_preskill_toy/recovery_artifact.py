"""Immutable output contract produced by a stabilizer recovery compiler."""
from __future__ import annotations

from dataclasses import dataclass

from .recovery_problem import CouplingGraphSpec, GateSpec, PauliSpec


FORMAT_VERSION = "orelia.recovery-artifact/v1"


@dataclass(frozen=True)
class CircuitSpec:
    qubit_order: tuple[str, ...]
    gates: tuple[GateSpec, ...]

    def __post_init__(self) -> None:
        if not self.qubit_order or len(set(self.qubit_order)) != len(self.qubit_order):
            raise ValueError("circuit qubit_order must be non-empty and unique")
        if any(not set(gate.qubits) <= set(self.qubit_order) for gate in self.gates):
            raise ValueError("circuit gate references an unknown wire")


@dataclass(frozen=True)
class TauSupportSpec:
    qubit_order: tuple[str, ...]
    signed_generators: tuple[PauliSpec, ...]
    support_rank: int
    logical_qubits: int

    def __post_init__(self) -> None:
        if any(generator.qubit_order != self.qubit_order for generator in self.signed_generators):
            raise ValueError("tau-support generator order mismatch")
        if any(not generator.is_hermitian for generator in self.signed_generators):
            raise ValueError("tau-support stabilizers must be Hermitian")


@dataclass(frozen=True)
class PetzTargetSpec:
    choi_qubit_order: tuple[str, ...]
    signed_generators: tuple[PauliSpec, ...]
    representation: str = "pure_stabilizer_choi_purification"

    def __post_init__(self) -> None:
        if self.representation != "pure_stabilizer_choi_purification":
            raise ValueError("unsupported Petz target representation")
        if any(generator.qubit_order != self.choi_qubit_order for generator in self.signed_generators):
            raise ValueError("Petz-target generator order mismatch")
        if any(not generator.is_hermitian for generator in self.signed_generators):
            raise ValueError("Petz-target stabilizers must be Hermitian")


@dataclass(frozen=True)
class ResourceSpec:
    logical_depth: int
    routed_depth: int
    logical_cnot: int
    routed_cnot: int
    movement_swaps: int
    restoration_swaps: int
    environment_qubits: int


@dataclass(frozen=True)
class CertificateSpec:
    target_reduced_choi_signature: tuple[str, ...]
    candidate_reduced_choi_signature: tuple[str, ...]
    logical_action_signature: tuple[str, ...]
    compiler_declared_valid: bool


@dataclass(frozen=True)
class MetricEntry:
    name: str
    value: str
    unit: str


@dataclass(frozen=True)
class RecoveryArtifact:
    format_version: str
    source_semantic_problem_hash: str
    source_document_hash: str
    tau_support: TauSupportSpec
    petz_target: PetzTargetSpec
    logical_circuit: CircuitSpec
    routed_circuit: CircuitSpec
    topology: CouplingGraphSpec
    final_permutation: tuple[str, ...]
    resources: ResourceSpec
    certificate: CertificateSpec
    metrics: tuple[MetricEntry, ...]

    def __post_init__(self) -> None:
        if self.format_version != FORMAT_VERSION:
            raise ValueError(f"unsupported RecoveryArtifact version: {self.format_version}")
        for digest in (self.source_semantic_problem_hash, self.source_document_hash):
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError("artifact source hashes must be lowercase SHA-256")
        if self.logical_circuit.qubit_order != self.routed_circuit.qubit_order:
            raise ValueError("logical and routed circuits must use the same wires")
        if self.topology.sites != self.routed_circuit.qubit_order:
            raise ValueError("artifact topology/circuit order mismatch")
        if (
            len(self.final_permutation) != len(self.topology.sites)
            or len(set(self.final_permutation)) != len(self.final_permutation)
            or set(self.final_permutation) != set(self.topology.sites)
        ):
            raise ValueError("invalid final permutation")
        if self.tau_support.qubit_order != self.logical_circuit.qubit_order:
            raise ValueError("tau support/circuit input order mismatch")
        if self.tau_support.support_rank != 2 ** self.tau_support.logical_qubits:
            raise ValueError("stabilizer support rank/logical-qubit mismatch")
        if any(value < 0 for value in (
            self.resources.logical_depth,
            self.resources.routed_depth,
            self.resources.logical_cnot,
            self.resources.routed_cnot,
            self.resources.movement_swaps,
            self.resources.restoration_swaps,
            self.resources.environment_qubits,
        )):
            raise ValueError("resource values must be non-negative")
        if tuple(sorted(self.metrics, key=lambda item: item.name)) != self.metrics:
            raise ValueError("metrics must be sorted by unique name")
        if len({item.name for item in self.metrics}) != len(self.metrics):
            raise ValueError("metric names must be unique")


@dataclass(frozen=True)
class VerificationCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class VerificationResourceMetrics:
    logical_one_qubit_gates: int
    routed_one_qubit_gates: int
    logical_two_qubit_gates: int
    routed_two_qubit_gates: int
    logical_two_qubit_depth: int
    routed_two_qubit_depth: int
    max_routed_interaction_distance: int


@dataclass(frozen=True)
class VerificationReport:
    semantic_problem_hash: str
    document_hash: str
    checks: tuple[VerificationCheck, ...]
    target_reduced_choi_signature: tuple[str, ...]
    candidate_reduced_choi_signature: tuple[str, ...]
    verification_policy: str
    channel_verified: bool
    topology_verified: bool
    logical_action_verified: bool
    final_order_verified: bool
    resource_counts_verified: bool
    swap_accounting_status: str
    observed_resources: VerificationResourceMetrics
    verified: bool
