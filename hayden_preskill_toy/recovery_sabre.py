"""Optional Qiskit SABRE adapter for channel-certified verification.

SABRE routes the already synthesized logical Clifford.  ORELIA then expands
Qiskit's explicit SWAP instructions and restores the v1 named-wire order by
replaying the inverse SWAP permutation.  The resulting artifact is not
trusted: ``verify_recovery(..., policy="channel-certified")`` remains the
authority on channel equivalence.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from .recovery_artifact import CircuitSpec, RecoveryArtifact, ResourceSpec
from .recovery_problem import GateSpec, RecoveryProblem
from .recovery_serialization import problem_document_hash, semantic_problem_hash
from .recovery_stabilizer import tableau_from_gate_specs, two_qubit_depth
from .recovery_verify import verify_recovery


@dataclass(frozen=True)
class SabreRoutingResult:
    gates: tuple[GateSpec, ...]
    qiskit_version: str
    seed: int
    heuristic: str
    trials: int
    movement_swaps: int
    restoration_swaps: int
    qiskit_routing_permutation: tuple[int, ...]
    final_wire_at_site_before_restoration: tuple[str, ...]
    final_wire_at_site: tuple[str, ...]


def _qiskit_modules():
    try:
        import qiskit
        from qiskit import QuantumCircuit
        from qiskit.transpiler import CouplingMap, PassManager
        from qiskit.transpiler.passes import SabreSwap
    except ImportError as error:
        raise RuntimeError(
            "Qiskit is required for the SABRE adapter; install the optional "
            "'sabre' dependency"
        ) from error
    return qiskit, QuantumCircuit, CouplingMap, PassManager, SabreSwap


def _logical_to_qiskit(gates, order, QuantumCircuit):
    positions = {wire: index for index, wire in enumerate(order)}
    circuit = QuantumCircuit(len(order), name="orelia_petz_logical")
    for gate in gates:
        indices = [positions[wire] for wire in gate.qubits]
        if gate.operation == "H":
            circuit.h(indices[0])
        elif gate.operation == "S":
            circuit.s(indices[0])
        elif gate.operation == "X":
            circuit.x(indices[0])
        elif gate.operation == "Z":
            circuit.z(indices[0])
        elif gate.operation == "CNOT":
            circuit.cx(indices[0], indices[1])
        else:
            raise ValueError(f"unsupported gate for SABRE: {gate.operation}")
    return circuit


def _expanded_swap(order: tuple[str, ...], left: int, right: int) -> tuple[GateSpec, ...]:
    return (
        GateSpec("CNOT", (order[left], order[right])),
        GateSpec("CNOT", (order[right], order[left])),
        GateSpec("CNOT", (order[left], order[right])),
    )


def route_gate_specs_with_sabre(
    problem: RecoveryProblem,
    gates: tuple[GateSpec, ...],
    *,
    seed: int = 20260803,
    heuristic: str = "decay",
    trials: int = 1,
) -> SabreRoutingResult:
    """Route a named Clifford through Qiskit SABRE with fixed initial layout."""
    if heuristic not in ("basic", "lookahead", "decay"):
        raise ValueError("unsupported SABRE heuristic")
    if trials < 1:
        raise ValueError("SABRE trials must be positive")
    if problem.physical_initial_order != problem.accessible_partition:
        raise ValueError("v1 SABRE adapter requires physical/accessibility order equality")
    if any(not set(gate.qubits) <= set(problem.accessible_partition) for gate in gates):
        raise ValueError("logical circuit references a wire outside X")

    qiskit, QuantumCircuit, CouplingMap, PassManager, SabreSwap = _qiskit_modules()
    order = problem.physical_initial_order
    indices = {wire: index for index, wire in enumerate(order)}
    directed_edges = []
    for left, right in problem.coupling_graph.edges:
        directed_edges.extend(((indices[left], indices[right]), (indices[right], indices[left])))
    coupling = CouplingMap(directed_edges)
    logical = _logical_to_qiskit(gates, order, QuantumCircuit)
    manager = PassManager([
        SabreSwap(
            coupling,
            heuristic=heuristic,
            seed=seed,
            trials=trials,
        )
    ])
    routed = manager.run(logical)

    result: list[GateSpec] = []
    movement_pairs: list[tuple[int, int]] = []
    wire_at_site = list(order)
    for instruction in routed.data:
        operation = instruction.operation.name
        positions = tuple(routed.find_bit(qubit).index for qubit in instruction.qubits)
        if operation == "swap":
            left, right = positions
            result.extend(_expanded_swap(order, left, right))
            movement_pairs.append((left, right))
            wire_at_site[left], wire_at_site[right] = wire_at_site[right], wire_at_site[left]
        elif operation == "cx":
            result.append(GateSpec("CNOT", (order[positions[0]], order[positions[1]])))
        elif operation in ("h", "s", "x", "z"):
            result.append(GateSpec(operation.upper(), (order[positions[0]],)))
        else:
            raise ValueError(f"unsupported Qiskit routed instruction: {operation}")

    before_restoration = tuple(wire_at_site)
    qiskit_permutation = tuple(routed.layout.routing_permutation())
    site_of_wire = tuple(before_restoration.index(wire) for wire in order)
    if qiskit_permutation != site_of_wire:
        raise AssertionError(
            "Qiskit final-layout convention disagrees with explicit SWAP replay"
        )

    # V1 requires restored order.  Reversing the exact SABRE SWAP sequence is
    # a deterministic, topology-preserving inverse of its final permutation.
    for left, right in reversed(movement_pairs):
        result.extend(_expanded_swap(order, left, right))
        wire_at_site[left], wire_at_site[right] = wire_at_site[right], wire_at_site[left]
    if tuple(wire_at_site) != order:
        raise AssertionError("inverse SABRE SWAP replay did not restore v1 wire order")

    routed_gates = tuple(result)
    if tableau_from_gate_specs(routed_gates, order) != tableau_from_gate_specs(gates, order):
        raise AssertionError("restored SABRE circuit changed the signed Clifford action")
    return SabreRoutingResult(
        gates=routed_gates,
        qiskit_version=qiskit.__version__,
        seed=seed,
        heuristic=heuristic,
        trials=trials,
        movement_swaps=len(movement_pairs),
        restoration_swaps=len(movement_pairs),
        qiskit_routing_permutation=qiskit_permutation,
        final_wire_at_site_before_restoration=before_restoration,
        final_wire_at_site=tuple(wire_at_site),
    )


def artifact_with_sabre_route(
    problem: RecoveryProblem,
    base_artifact: RecoveryArtifact,
    *,
    seed: int = 20260803,
    heuristic: str = "decay",
    trials: int = 1,
) -> tuple[RecoveryArtifact, SabreRoutingResult]:
    """Replace only the routed circuit of a verified v1 artifact with SABRE."""
    if base_artifact.source_semantic_problem_hash != semantic_problem_hash(problem):
        raise ValueError("base artifact semantic problem hash mismatch")
    if base_artifact.source_document_hash != problem_document_hash(problem):
        raise ValueError("base artifact problem document hash mismatch")
    if not verify_recovery(problem, base_artifact).verified:
        raise ValueError("base artifact must pass reproducible-route verification")

    routed = route_gate_specs_with_sabre(
        problem,
        base_artifact.logical_circuit.gates,
        seed=seed,
        heuristic=heuristic,
        trials=trials,
    )
    candidate = replace(
        base_artifact,
        routed_circuit=CircuitSpec(problem.accessible_partition, routed.gates),
        final_permutation=routed.final_wire_at_site,
        resources=ResourceSpec(
            logical_depth=two_qubit_depth(base_artifact.logical_circuit.gates),
            routed_depth=two_qubit_depth(routed.gates),
            logical_cnot=sum(
                gate.operation == "CNOT" for gate in base_artifact.logical_circuit.gates
            ),
            routed_cnot=sum(gate.operation == "CNOT" for gate in routed.gates),
            movement_swaps=routed.movement_swaps,
            restoration_swaps=routed.restoration_swaps,
            environment_qubits=base_artifact.resources.environment_qubits,
        ),
    )
    # The copied target, certificate claims and fidelity are deliberately
    # treated as untrusted by channel-certified verification.  Exact signed
    # tableau equality above predicts equivalence; the verifier must establish
    # it again through its independent reduced-Choi path.
    return candidate, routed
