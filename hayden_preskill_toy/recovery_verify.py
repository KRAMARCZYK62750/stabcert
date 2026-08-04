"""Independent verifier for RecoveryArtifact objects.

The module deliberately does not import ``recovery_compile`` and does not use
the compiler's Petz-target constructor.  The target is rebuilt by direct
signed-Pauli propagation from ``RecoveryProblem``.
"""
from __future__ import annotations

from enum import Enum

import stim

from .recovery_artifact import (
    RecoveryArtifact,
    VerificationCheck,
    VerificationReport,
    VerificationResourceMetrics,
)
from .recovery_problem import PauliSpec, RecoveryProblem
from .recovery_routing import route_named_circuit
from .recovery_serialization import problem_document_hash, semantic_problem_hash
from .recovery_stabilizer import (
    bell_target_generators,
    candidate_reduced_choi_generators,
    canonical_signed_signature,
    gate_specs_to_stim,
    pauli_spec_to_stim,
    signed_reduced_stabilizers,
    stabilizer_overlap_with_pure_target,
    stim_to_pauli_spec,
    support_code_from_source_choi,
    tableau_from_gate_specs,
    two_qubit_depth,
)


class VerificationPolicy(str, Enum):
    """Normative verification policies supported by the v1 verifier."""

    REPRODUCIBLE_ROUTE = "reproducible-route"
    CHANNEL_CERTIFIED = "channel-certified"


def _verification_policy(value: VerificationPolicy | str) -> VerificationPolicy:
    try:
        return VerificationPolicy(value)
    except ValueError as error:
        choices = ", ".join(item.value for item in VerificationPolicy)
        raise ValueError(f"unsupported verification policy; expected one of: {choices}") from error


def _maximum_interaction_distance(problem: RecoveryProblem, gates) -> int:
    neighbours = {wire: set() for wire in problem.coupling_graph.sites}
    for left, right in problem.coupling_graph.edges:
        neighbours[left].add(right)
        neighbours[right].add(left)
    maximum = 0
    for gate in gates:
        if gate.operation != "CNOT":
            continue
        source, destination = gate.qubits
        reached = {source}
        frontier = [source]
        distance = 0
        while destination not in reached:
            distance += 1
            frontier = [
                neighbour
                for wire in frontier
                for neighbour in neighbours[wire]
                if neighbour not in reached
            ]
            if not frontier:
                raise ValueError("coupling graph does not connect a circuit interaction")
            reached.update(frontier)
        maximum = max(maximum, distance)
    return maximum


def _verifier_initial_generators(problem: RecoveryProblem) -> list[stim.PauliString]:
    """Independent, generator-first source-Choi definition."""
    message = len(problem.channel_input)
    total = message + len(problem.qubit_order)
    source_index = {wire: message + index for index, wire in enumerate(problem.qubit_order)}
    generators: list[stim.PauliString] = []
    for reference, wire in enumerate(problem.channel_input):
        for pauli_name in ("X", "Z"):
            body = ["I"] * total
            body[reference] = body[source_index[wire]] = pauli_name
            generators.append(
                pauli_spec_to_stim(
                    PauliSpec(tuple(str(q) for q in range(total)), "".join(body), 0)
                )
            )
    ancilla_index = {wire: position for position, wire in enumerate(problem.ancilla_qubits)}
    for spec in problem.ancilla_initial_stabilizers:
        body = ["I"] * total
        for wire, position in ancilla_index.items():
            body[source_index[wire]] = spec.operators[position]
        generators.append(
            pauli_spec_to_stim(
                PauliSpec(
                    tuple(str(q) for q in range(total)),
                    "".join(body),
                    spec.phase_exponent_mod_4,
                )
            )
        )
    if len(generators) != total:
        raise ValueError("problem does not define a pure source Choi state")
    # This also checks commutation, independence, signs, and the absence of -I.
    stim.Tableau.from_stabilizers(generators)
    return generators


def _verifier_source_choi(problem: RecoveryProblem) -> stim.Tableau:
    """Verifier path: conjugate every signed generator directly."""
    message = len(problem.channel_input)
    total_order = tuple(f"ref:{wire}" for wire in problem.channel_input) + problem.qubit_order
    source_circuit = stim.Circuit()
    for qubit in range(len(total_order)):
        source_circuit.append("I", [qubit])
    source_index = {wire: message + index for index, wire in enumerate(problem.qubit_order)}
    for gate in problem.source_clifford:
        targets = [source_index[wire] for wire in gate.qubits]
        source_circuit.append("CX" if gate.operation == "CNOT" else gate.operation, targets)
    propagated = [item.after(source_circuit) for item in _verifier_initial_generators(problem)]
    return stim.Tableau.from_stabilizers(propagated)


def _verifier_petz_choi(problem: RecoveryProblem, source: stim.Tableau) -> stim.Tableau:
    """Independent target path using binary reorder and explicit conjugation."""
    message = len(problem.channel_input)
    source_index = {wire: message + index for index, wire in enumerate(problem.qubit_order)}
    permutation = (
        *range(message),
        *[source_index[wire] for wire in problem.accessible_partition],
        *[source_index[wire] for wire in problem.inaccessible_partition],
    )
    result: list[stim.PauliString] = []
    order = tuple(str(q) for q in range(len(source)))
    for index in range(len(source)):
        spec = stim_to_pauli_spec(source.z_output(index), order)
        operators = "".join(spec.operators[wire] for wire in permutation)
        phase = (spec.phase_exponent_mod_4 + 2 * (operators.count("Y") & 1)) % 4
        result.append(pauli_spec_to_stim(PauliSpec(order, operators, phase)))
    return stim.Tableau.from_stabilizers(result)


def _entanglement_fidelity(
    problem: RecoveryProblem, source: stim.Tableau, circuit
) -> float:
    message = len(problem.channel_input)
    preparation = source.to_circuit()
    source_index = {wire: message + index for index, wire in enumerate(problem.qubit_order)}
    for gate in circuit:
        targets = [source_index[wire] for wire in gate.qubits]
        preparation.append("CX" if gate.operation == "CNOT" else gate.operation, targets)
    final = stim.Tableau.from_circuit(preparation)
    keep = (*range(message), *[source_index[wire] for wire in problem.requested_output])
    reduced = signed_reduced_stabilizers(
        [final.z_output(index) for index in range(len(final))], tuple(keep)
    )
    return stabilizer_overlap_with_pure_target(reduced, bell_target_generators(message))


def _metric(artifact: RecoveryArtifact, name: str) -> float | None:
    value = next((item.value for item in artifact.metrics if item.name == name), None)
    return None if value is None else float(value)


def _verifier_logical_action_signature(problem: RecoveryProblem, code, gates) -> tuple[str, ...]:
    """Reconstruct the signed logical-Pauli images claimed by the compiler.

    The dilation uses the requested output wires first, followed by the
    canonical prefix of accessible environment wires.  Remaining accessible
    wires are idle after decoding and are deliberately excluded from the
    compiler's logical-action signature.
    """
    circuit = gate_specs_to_stim(gates, problem.accessible_partition)
    environment_width = code.logical_qubits - len(problem.requested_output)
    environment_wires = tuple(
        wire for wire in problem.accessible_partition if wire not in problem.requested_output
    )[:environment_width]
    output_wires = (*problem.requested_output, *environment_wires)
    if len(output_wires) != code.logical_qubits:
        raise ValueError("logical signature output width is inconsistent with tau support")
    positions = tuple(problem.accessible_partition.index(wire) for wire in output_wires)
    result: list[str] = []
    for logical_x, logical_z in zip(code.logical_x_labels, code.logical_z_labels):
        for label in (logical_x, logical_z):
            transformed = stim.PauliString(label).after(circuit)
            full = stim_to_pauli_spec(transformed, problem.accessible_partition)
            local = PauliSpec(
                output_wires,
                "".join(full.operators[position] for position in positions),
                full.phase_exponent_mod_4,
            )
            result.append(str(pauli_spec_to_stim(local)))
    return tuple(result)


def verify_recovery(
    problem: RecoveryProblem,
    artifact: RecoveryArtifact,
    *,
    policy: VerificationPolicy | str = VerificationPolicy.REPRODUCIBLE_ROUTE,
) -> VerificationReport:
    """Recalculate all normative checks, ignoring the artifact's verdict."""
    selected_policy = _verification_policy(policy)
    checks: list[VerificationCheck] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append(VerificationCheck(name, bool(passed), detail))

    semantic_hash = semantic_problem_hash(problem)
    document_hash = problem_document_hash(problem)
    check(
        "semantic_problem_hash",
        artifact.source_semantic_problem_hash == semantic_hash,
        "artifact source hash matches independently canonicalized problem",
    )
    check(
        "document_hash",
        artifact.source_document_hash == document_hash,
        "artifact document hash matches exact problem document",
    )
    check("topology", artifact.topology == problem.coupling_graph, "artifact topology equals problem topology")
    check(
        "wire_orders",
        artifact.logical_circuit.qubit_order == problem.accessible_partition
        and artifact.routed_circuit.qubit_order == problem.accessible_partition,
        "both circuits use the normative accessible-wire order",
    )

    source = _verifier_source_choi(problem)
    petz = _verifier_petz_choi(problem, source)
    code = support_code_from_source_choi(
        source,
        len(problem.channel_input),
        problem.qubit_order,
        problem.accessible_partition,
    )
    derived_tau = [stim.PauliString(item) for item in code.signed_stabilizer_labels]
    artifact_tau = [pauli_spec_to_stim(item) for item in artifact.tau_support.signed_generators]
    check(
        "tau_support_signed",
        canonical_signed_signature(derived_tau) == canonical_signed_signature(artifact_tau),
        "artifact tau support equals the independently derived signed subgroup",
    )
    check(
        "tau_support_dimensions",
        artifact.tau_support.support_rank == code.support_rank
        and artifact.tau_support.logical_qubits == code.logical_qubits,
        f"rank={code.support_rank}, logical_qubits={code.logical_qubits}",
    )
    if problem.expected_tau_support:
        expected = [pauli_spec_to_stim(item) for item in problem.expected_tau_support]
        check(
            "optional_tau_support_assertion",
            canonical_signed_signature(expected) == canonical_signed_signature(derived_tau),
            "non-normative support assertion agrees with the derived support",
        )

    target_reduced = signed_reduced_stabilizers(
        [petz.z_output(index) for index in range(len(petz))],
        tuple(range(len(problem.channel_input) + len(problem.accessible_partition))),
    )
    target_signature = canonical_signed_signature(target_reduced)
    candidate_reduced = candidate_reduced_choi_generators(
        problem.accessible_partition,
        problem.requested_output,
        code,
        artifact.routed_circuit.gates,
    )
    candidate_signature = canonical_signed_signature(candidate_reduced)
    check(
        "reduced_choi_channel",
        target_signature == candidate_signature,
        "candidate and independently reconstructed target have equal signed reduced Choi subgroups",
    )

    expected_choi_order = (
        *tuple(f"out:{wire}" for wire in problem.requested_output),
        *tuple(f"ref:{wire}" for wire in problem.accessible_partition),
        *tuple(f"env:{wire}" for wire in problem.inaccessible_partition),
    )
    check(
        "petz_target_wire_order",
        artifact.petz_target.choi_qubit_order == expected_choi_order,
        "Petz target uses the normative output|reference|environment order",
    )
    artifact_target = [pauli_spec_to_stim(item) for item in artifact.petz_target.signed_generators]
    artifact_target_reduced = signed_reduced_stabilizers(
        artifact_target,
        tuple(range(len(problem.channel_input) + len(problem.accessible_partition))),
    )
    check(
        "artifact_target_claim",
        canonical_signed_signature(artifact_target_reduced) == target_signature,
        "artifact target claim agrees after eliminating its environment gauge",
    )

    if selected_policy is VerificationPolicy.REPRODUCIBLE_ROUTE:
        logical_tableau = tableau_from_gate_specs(
            artifact.logical_circuit.gates, problem.accessible_partition
        )
        routed_tableau = tableau_from_gate_specs(
            artifact.routed_circuit.gates, problem.accessible_partition
        )
        check(
            "logical_routed_action",
            logical_tableau == routed_tableau,
            "routed circuit has the same signed Clifford action as the logical circuit",
        )
    edges = {frozenset(edge) for edge in problem.coupling_graph.edges}
    topology_valid = all(
        gate.operation != "CNOT" or frozenset(gate.qubits) in edges
        for gate in artifact.routed_circuit.gates
    )
    check("coupling_graph", topology_valid, "every routed CNOT uses an allowed edge")
    gates_valid = all(
        gate.operation in problem.allowed_gates for circuit in (
            artifact.logical_circuit,
            artifact.routed_circuit,
        ) for gate in circuit.gates
    )
    check("allowed_gate_set", gates_valid, "every circuit gate belongs to the problem gate set")

    environment_qubits = (
        len(problem.channel_input)
        + len(problem.inaccessible_partition)
        - code.logical_qubits
    )
    if selected_policy is VerificationPolicy.REPRODUCIBLE_ROUTE:
        expected_route = route_named_circuit(
            artifact.logical_circuit.gates, problem.coupling_graph, problem.router
        )
        expected_resources = (
            two_qubit_depth(artifact.logical_circuit.gates),
            expected_route.two_qubit_depth,
            sum(gate.operation == "CNOT" for gate in artifact.logical_circuit.gates),
            expected_route.cnot_count,
            expected_route.movement_swaps,
            expected_route.restoration_swaps,
            environment_qubits,
        )
        declared_resources = (
            artifact.resources.logical_depth,
            artifact.resources.routed_depth,
            artifact.resources.logical_cnot,
            artifact.resources.routed_cnot,
            artifact.resources.movement_swaps,
            artifact.resources.restoration_swaps,
            artifact.resources.environment_qubits,
        )
        check(
            "deterministic_routing",
            artifact.routed_circuit.gates == expected_route.gates,
            "routed circuit is the deterministic result of the declared router policy",
        )
        resources_valid = expected_resources == declared_resources
        check(
            "resource_accounting",
            resources_valid,
            f"recomputed={expected_resources}, declared={declared_resources}",
        )
        final_order_valid = (
            artifact.final_permutation == expected_route.final_wire_at_site
            and artifact.final_permutation == problem.physical_initial_order
        )
        check(
            "final_permutation",
            final_order_valid,
            "named-wire order is explicitly restored",
        )
        swap_accounting_status = "certified_by_reproducible_route"
    else:
        # V1 contains a final CNOT circuit but no replayable routing trace.  We
        # can therefore certify only resource fields observable directly in
        # the two circuits.  The declared SWAP split is deliberately ignored.
        observed_resources = (
            two_qubit_depth(artifact.logical_circuit.gates),
            two_qubit_depth(artifact.routed_circuit.gates),
            sum(gate.operation == "CNOT" for gate in artifact.logical_circuit.gates),
            sum(gate.operation == "CNOT" for gate in artifact.routed_circuit.gates),
            environment_qubits,
        )
        declared_observable_resources = (
            artifact.resources.logical_depth,
            artifact.resources.routed_depth,
            artifact.resources.logical_cnot,
            artifact.resources.routed_cnot,
            artifact.resources.environment_qubits,
        )
        resources_valid = observed_resources == declared_observable_resources
        check(
            "observable_resource_accounting",
            resources_valid,
            "recomputed observable resources="
            f"{observed_resources}, declared={declared_observable_resources}; "
            "movement/restoration SWAP claims are not certified",
        )
        # RecoveryArtifact v1 has no replayable route trace.  Channel-certified
        # v1 consequently accepts only artifacts declaring the normative
        # restored order; non-restored relabelling is deferred to a future
        # evidence format.
        final_order_valid = artifact.final_permutation == problem.physical_initial_order
        check(
            "restored_final_order_declaration",
            final_order_valid,
            "v1 channel-certified mode requires the normative restored wire order",
        )
        swap_accounting_status = "not_certified"
    check(
        "certificate_signature_claims",
        artifact.certificate.target_reduced_choi_signature == target_signature
        and artifact.certificate.candidate_reduced_choi_signature
        == candidate_signature
        and artifact.certificate.logical_action_signature
        == _verifier_logical_action_signature(problem, code, artifact.logical_circuit.gates),
        "declared Choi and signed logical-action signatures match independent reconstructions; declared verdict is ignored",
    )

    circuit_fidelity = _entanglement_fidelity(problem, source, artifact.routed_circuit.gates)
    claimed_fidelity = _metric(artifact, "circuit_entanglement_fidelity")
    tolerance = float(problem.certification_thresholds.numerical_tolerance)
    check(
        "circuit_entanglement_fidelity",
        claimed_fidelity is not None and abs(claimed_fidelity - circuit_fidelity) < tolerance,
        f"independent={circuit_fidelity:.17g}, artifact={claimed_fidelity}",
    )
    # The claimed compiler verdict is intentionally never used in this conjunction.
    verified = all(item.passed for item in checks)
    channel_verified = target_signature == candidate_signature
    observed_resource_metrics = VerificationResourceMetrics(
        logical_one_qubit_gates=sum(
            gate.operation != "CNOT" for gate in artifact.logical_circuit.gates
        ),
        routed_one_qubit_gates=sum(
            gate.operation != "CNOT" for gate in artifact.routed_circuit.gates
        ),
        logical_two_qubit_gates=sum(
            gate.operation == "CNOT" for gate in artifact.logical_circuit.gates
        ),
        routed_two_qubit_gates=sum(
            gate.operation == "CNOT" for gate in artifact.routed_circuit.gates
        ),
        logical_two_qubit_depth=two_qubit_depth(artifact.logical_circuit.gates),
        routed_two_qubit_depth=two_qubit_depth(artifact.routed_circuit.gates),
        max_routed_interaction_distance=_maximum_interaction_distance(
            problem, artifact.routed_circuit.gates
        ),
    )
    topology_verified = (
        artifact.topology == problem.coupling_graph
        and artifact.logical_circuit.qubit_order == problem.accessible_partition
        and artifact.routed_circuit.qubit_order == problem.accessible_partition
        and topology_valid
        and gates_valid
    )
    if selected_policy is VerificationPolicy.REPRODUCIBLE_ROUTE:
        logical_action_valid = channel_verified and logical_tableau == routed_tableau
    else:
        # Equality of normalized reduced Choi states is equality of the
        # channel and therefore certifies its complete logical-operator
        # action, without selecting a Stinespring environment gauge.
        logical_action_valid = channel_verified
    return VerificationReport(
        semantic_problem_hash=semantic_hash,
        document_hash=document_hash,
        checks=tuple(checks),
        target_reduced_choi_signature=target_signature,
        candidate_reduced_choi_signature=candidate_signature,
        verification_policy=selected_policy.value,
        channel_verified=channel_verified,
        topology_verified=topology_verified,
        logical_action_verified=logical_action_valid,
        final_order_verified=final_order_valid,
        resource_counts_verified=resources_valid,
        swap_accounting_status=swap_accounting_status,
        observed_resources=observed_resource_metrics,
        verified=verified,
    )
