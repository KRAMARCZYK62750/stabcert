"""Optional pytket routing adapter for channel-certified verification."""
from __future__ import annotations

from dataclasses import dataclass, replace

from .recovery_artifact import CircuitSpec, RecoveryArtifact, ResourceSpec
from .recovery_problem import GateSpec, RecoveryProblem
from .recovery_serialization import problem_document_hash, semantic_problem_hash
from .recovery_stabilizer import tableau_from_gate_specs, two_qubit_depth
from .recovery_verify import verify_recovery


@dataclass(frozen=True)
class PytketRoutingResult:
    gates: tuple[GateSpec, ...]
    pytket_version: str
    routing_pass: str
    movement_swaps: int
    restoration_swaps: int
    bridges_before_decomposition: int
    final_wire_at_site_before_restoration: tuple[str, ...]
    final_wire_at_site: tuple[str, ...]
    global_phase_half_turns: str


def _pytket_modules():
    try:
        import pytket
        from pytket import Circuit, OpType, Qubit
        from pytket.architecture import Architecture
        from pytket.passes import DecomposeSwapsToCXs, RoutingPass
        from pytket.placement import place_with_map
        from pytket.unit_id import Node
    except ImportError as error:
        raise RuntimeError(
            "pytket is required for the pytket adapter; install the optional "
            "'pytket' dependency"
        ) from error
    return (
        pytket,
        Circuit,
        OpType,
        Qubit,
        Architecture,
        RoutingPass,
        DecomposeSwapsToCXs,
        place_with_map,
        Node,
    )


def _logical_to_pytket(gates, order, Circuit):
    positions = {wire: index for index, wire in enumerate(order)}
    circuit = Circuit(len(order), name="orelia_petz_logical")
    for gate in gates:
        indices = [positions[wire] for wire in gate.qubits]
        if gate.operation == "H":
            circuit.H(indices[0])
        elif gate.operation == "S":
            circuit.S(indices[0])
        elif gate.operation == "X":
            circuit.X(indices[0])
        elif gate.operation == "Z":
            circuit.Z(indices[0])
        elif gate.operation == "CNOT":
            circuit.CX(indices[0], indices[1])
        else:
            raise ValueError(f"unsupported gate for pytket: {gate.operation}")
    return circuit


def _node_position(unit) -> int:
    if len(unit.index) != 1:
        raise ValueError(f"unsupported multidimensional pytket unit: {unit}")
    return int(unit.index[0])


def route_gate_specs_with_pytket(
    problem: RecoveryProblem,
    gates: tuple[GateSpec, ...],
) -> PytketRoutingResult:
    """Route with pytket's deterministic LexiLabelling/LexiRoute pass."""
    if problem.physical_initial_order != problem.accessible_partition:
        raise ValueError("v1 pytket adapter requires physical/accessibility order equality")
    if any(not set(gate.qubits) <= set(problem.accessible_partition) for gate in gates):
        raise ValueError("logical circuit references a wire outside X")
    (
        pytket,
        Circuit,
        OpType,
        Qubit,
        Architecture,
        RoutingPass,
        DecomposeSwapsToCXs,
        place_with_map,
        Node,
    ) = _pytket_modules()
    order = problem.physical_initial_order
    indices = {wire: index for index, wire in enumerate(order)}
    architecture = Architecture(
        [(indices[left], indices[right]) for left, right in problem.coupling_graph.edges]
    )
    circuit = _logical_to_pytket(gates, order, Circuit)
    place_with_map(circuit, {Qubit(index): Node(index) for index in range(len(order))})
    RoutingPass(architecture).apply(circuit)

    movement_pairs: list[tuple[int, int]] = []
    bridges = 0
    wire_at_site = list(order)
    for command in circuit.get_commands():
        if command.op.type == OpType.SWAP:
            left, right = (_node_position(qubit) for qubit in command.qubits)
            movement_pairs.append((left, right))
            wire_at_site[left], wire_at_site[right] = wire_at_site[right], wire_at_site[left]
        elif command.op.type == OpType.BRIDGE:
            bridges += 1
    before_restoration = tuple(wire_at_site)

    # RoutingPass emits physical SWAPs.  If their net permutation is already
    # identity, no restoration is added.  Otherwise v1 order is restored by
    # replaying the exact movement sequence in reverse.
    restoration_pairs = [] if before_restoration == order else list(reversed(movement_pairs))
    for left, right in restoration_pairs:
        circuit.SWAP(Node(left), Node(right))
        wire_at_site[left], wire_at_site[right] = wire_at_site[right], wire_at_site[left]
    if tuple(wire_at_site) != order:
        raise AssertionError("inverse pytket SWAP replay did not restore v1 wire order")
    DecomposeSwapsToCXs(architecture, respect_direction=False).apply(circuit)

    gate_names = {
        OpType.H: "H",
        OpType.S: "S",
        OpType.X: "X",
        OpType.Z: "Z",
        OpType.CX: "CNOT",
    }
    result: list[GateSpec] = []
    for command in circuit.get_commands():
        operation = gate_names.get(command.op.type)
        if operation is None:
            raise ValueError(f"unsupported routed pytket operation: {command.op.type}")
        positions = tuple(_node_position(qubit) for qubit in command.qubits)
        result.append(GateSpec(operation, tuple(order[index] for index in positions)))
    routed_gates = tuple(result)
    if tableau_from_gate_specs(routed_gates, order) != tableau_from_gate_specs(gates, order):
        raise AssertionError("restored pytket circuit changed the signed Clifford action")
    return PytketRoutingResult(
        gates=routed_gates,
        pytket_version=pytket.__version__,
        routing_pass="RoutingPass(LexiLabellingMethod,LexiRouteRoutingMethod)",
        movement_swaps=len(movement_pairs),
        restoration_swaps=len(restoration_pairs),
        bridges_before_decomposition=bridges,
        final_wire_at_site_before_restoration=before_restoration,
        final_wire_at_site=tuple(wire_at_site),
        global_phase_half_turns=str(circuit.phase),
    )


def artifact_with_pytket_route(
    problem: RecoveryProblem,
    base_artifact: RecoveryArtifact,
) -> tuple[RecoveryArtifact, PytketRoutingResult]:
    """Replace only the routed circuit of a verified v1 artifact with pytket."""
    if base_artifact.source_semantic_problem_hash != semantic_problem_hash(problem):
        raise ValueError("base artifact semantic problem hash mismatch")
    if base_artifact.source_document_hash != problem_document_hash(problem):
        raise ValueError("base artifact problem document hash mismatch")
    if not verify_recovery(problem, base_artifact).verified:
        raise ValueError("base artifact must pass reproducible-route verification")
    routed = route_gate_specs_with_pytket(problem, base_artifact.logical_circuit.gates)
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
    return candidate, routed
