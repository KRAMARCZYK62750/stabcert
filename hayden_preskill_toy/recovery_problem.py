"""Immutable, model-independent input contract for stabilizer recovery."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation


FORMAT_VERSION = "orelia.recovery-problem/v1"
ALLOWED_CLIFFORD_GATES = ("H", "S", "X", "Z", "CNOT")


@dataclass(frozen=True, order=True)
class PauliSpec:
    """Canonical Pauli over an explicit qubit order.

    ``phase_exponent_mod_4`` encodes i**k. Stabilizer generators are required
    to be Hermitian (k in {0, 2}), while the representation remains capable of
    carrying the full Pauli-group phase.
    """

    qubit_order: tuple[str, ...]
    operators: str
    phase_exponent_mod_4: int = 0

    def __post_init__(self) -> None:
        if len(set(self.qubit_order)) != len(self.qubit_order):
            raise ValueError("Pauli qubit_order contains duplicates")
        if len(self.operators) != len(self.qubit_order):
            raise ValueError("Pauli width differs from qubit_order")
        if any(item not in "IXYZ" for item in self.operators):
            raise ValueError("Pauli operators must use I/X/Y/Z")
        if self.phase_exponent_mod_4 not in range(4):
            raise ValueError("Pauli phase exponent must be in {0,1,2,3}")

    @property
    def is_hermitian(self) -> bool:
        return self.phase_exponent_mod_4 in (0, 2)


@dataclass(frozen=True, order=True)
class GateSpec:
    operation: str
    qubits: tuple[str, ...]

    def __post_init__(self) -> None:
        expected = 2 if self.operation == "CNOT" else 1
        if self.operation not in ALLOWED_CLIFFORD_GATES:
            raise ValueError(f"unsupported Clifford gate: {self.operation}")
        if len(self.qubits) != expected or len(set(self.qubits)) != expected:
            raise ValueError(f"{self.operation} requires {expected} distinct qubits")


@dataclass(frozen=True)
class CouplingGraphSpec:
    sites: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]
    directed: bool = False
    native_two_qubit_gate: str = "CNOT"

    def __post_init__(self) -> None:
        if not self.sites or len(set(self.sites)) != len(self.sites):
            raise ValueError("coupling sites must be non-empty and unique")
        canonical = []
        for edge in self.edges:
            if len(edge) != 2 or edge[0] == edge[1]:
                raise ValueError("coupling edges require two distinct sites")
            if any(site not in self.sites for site in edge):
                raise ValueError("coupling edge references an unknown site")
            canonical.append(edge if self.directed else tuple(sorted(edge)))
        if tuple(sorted(set(canonical))) != self.edges:
            raise ValueError("coupling edges must be unique and canonically sorted")
        if self.native_two_qubit_gate != "CNOT":
            raise ValueError("v1 supports CNOT coupling edges only")
        if self.directed:
            raise ValueError("v1 supports undirected coupling graphs only")
        neighbours = {site: set() for site in self.sites}
        for left, right in self.edges:
            neighbours[left].add(right)
            neighbours[right].add(left)
        reached = {self.sites[0]}
        pending = list(reached)
        while pending:
            current = pending.pop()
            for neighbour in neighbours[current] - reached:
                reached.add(neighbour)
                pending.append(neighbour)
        if reached != set(self.sites):
            raise ValueError("v1 coupling graph must be connected")


@dataclass(frozen=True)
class RouterParameters:
    algorithm: str = "common_lookahead_token_restore"
    lookahead: int = 16
    candidate_budget: int = 64
    restore_final_order: bool = True

    def __post_init__(self) -> None:
        if self.algorithm != "common_lookahead_token_restore":
            raise ValueError("unsupported v1 router")
        if self.lookahead < 0 or self.candidate_budget < 1:
            raise ValueError("invalid router budget")
        if not self.restore_final_order:
            raise ValueError("v1 requires explicit final-order restoration")


@dataclass(frozen=True)
class CertificationThresholds:
    numerical_tolerance: str = "1e-12"

    def __post_init__(self) -> None:
        try:
            value = Decimal(self.numerical_tolerance)
        except InvalidOperation as error:
            raise ValueError("invalid decimal certification tolerance") from error
        if not value.is_finite() or value <= 0 or value > Decimal("1e-6"):
            raise ValueError("certification tolerance must lie in (0, 1e-6]")


@dataclass(frozen=True)
class RecoveryProblem:
    """Mathematical definition of a pure-Clifford stabilizer recovery task."""

    format_version: str
    qubit_order: tuple[str, ...]
    channel_input: tuple[str, ...]
    source_clifford: tuple[GateSpec, ...]
    ancilla_qubits: tuple[str, ...]
    ancilla_initial_stabilizers: tuple[PauliSpec, ...]
    accessible_partition: tuple[str, ...]
    inaccessible_partition: tuple[str, ...]
    requested_output: tuple[str, ...]
    logical_qubit_order: tuple[str, ...]
    physical_initial_order: tuple[str, ...]
    coupling_graph: CouplingGraphSpec
    allowed_gates: tuple[str, ...]
    depth_convention: str
    router: RouterParameters
    certification_thresholds: CertificationThresholds
    petz_reference: str = "maximally_mixed_on_channel_input"
    choi_convention: str = "normalized_bell_source_order_output_reference_environment"
    transpose_convention: str = "P_transpose_on_reference_Y_transpose_minus_Y"
    support_inverse_policy: str = "moore_penrose_on_exact_stabilizer_support"
    expected_tau_support: tuple[PauliSpec, ...] = ()
    metadata: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.format_version != FORMAT_VERSION:
            raise ValueError(f"unsupported RecoveryProblem version: {self.format_version}")
        if not self.qubit_order or len(set(self.qubit_order)) != len(self.qubit_order):
            raise ValueError("qubit_order must be non-empty and unique")
        all_qubits = set(self.qubit_order)
        groups = (
            self.channel_input,
            self.ancilla_qubits,
            self.accessible_partition,
            self.inaccessible_partition,
            self.requested_output,
            self.logical_qubit_order,
            self.physical_initial_order,
        )
        if any(len(set(group)) != len(group) or not set(group) <= all_qubits for group in groups):
            raise ValueError("register contains duplicate or unknown qubits")
        if set(self.channel_input) & set(self.ancilla_qubits):
            raise ValueError("channel input and ancillas overlap")
        if set(self.channel_input) | set(self.ancilla_qubits) != all_qubits:
            raise ValueError("channel input and ancillas must partition source qubits")
        if set(self.accessible_partition) & set(self.inaccessible_partition):
            raise ValueError("accessible and inaccessible partitions overlap")
        if set(self.accessible_partition) | set(self.inaccessible_partition) != all_qubits:
            raise ValueError("accessible/inaccessible must partition source outputs")
        if self.logical_qubit_order != self.channel_input:
            raise ValueError("v1 logical order must equal the channel-input order")
        if not set(self.requested_output) <= set(self.accessible_partition):
            raise ValueError("requested output must lie in the accessible partition")
        if len(self.requested_output) != len(self.channel_input):
            raise ValueError("recovery output width must equal message width")
        if self.physical_initial_order != self.accessible_partition:
            raise ValueError("v1 physical order must equal accessible order")
        if self.coupling_graph.sites != self.physical_initial_order:
            raise ValueError("coupling sites must equal physical_initial_order")
        if tuple(sorted(self.allowed_gates)) != tuple(sorted(ALLOWED_CLIFFORD_GATES)):
            raise ValueError("v1 gate set must be H/S/X/Z/CNOT")
        if self.depth_convention != "asap_two_qubit_layers_single_qubit_free":
            raise ValueError("unsupported depth convention")
        if self.petz_reference != "maximally_mixed_on_channel_input":
            raise ValueError("v1 supports only sigma=I/d")
        if self.choi_convention != "normalized_bell_source_order_output_reference_environment":
            raise ValueError("unsupported Choi convention")
        if self.transpose_convention != "P_transpose_on_reference_Y_transpose_minus_Y":
            raise ValueError("unsupported transpose convention")
        if self.support_inverse_policy != "moore_penrose_on_exact_stabilizer_support":
            raise ValueError("unsupported support inverse policy")
        for gate in self.source_clifford:
            if not set(gate.qubits) <= all_qubits:
                raise ValueError("source Clifford gate references an unknown qubit")
        if len(self.ancilla_initial_stabilizers) != len(self.ancilla_qubits):
            raise ValueError("ancilla stabilizers must define a pure stabilizer state")
        for pauli in self.ancilla_initial_stabilizers:
            if pauli.qubit_order != self.ancilla_qubits or not pauli.is_hermitian:
                raise ValueError("invalid ancilla stabilizer convention")
        for pauli in self.expected_tau_support:
            if pauli.qubit_order != self.accessible_partition or not pauli.is_hermitian:
                raise ValueError("invalid optional tau-support assertion")
        if tuple(sorted(self.metadata)) != self.metadata:
            raise ValueError("metadata entries must be uniquely keyed and sorted")
        if len({key for key, _ in self.metadata}) != len(self.metadata):
            raise ValueError("metadata keys must be unique")
