"""Generic compiler from a RecoveryProblem to a signed Clifford artifact."""
from __future__ import annotations

import numpy as np
import stim

from .gf2 import canonical_kernel_image_basis, lexicographic_solution, rank
from .recovery_artifact import (
    CertificateSpec,
    CircuitSpec,
    FORMAT_VERSION as ARTIFACT_FORMAT_VERSION,
    MetricEntry,
    PetzTargetSpec,
    RecoveryArtifact,
    ResourceSpec,
    TauSupportSpec,
)
from .recovery_problem import PauliSpec, RecoveryProblem
from .recovery_routing import route_named_circuit
from .recovery_serialization import problem_document_hash, semantic_problem_hash
from .recovery_stabilizer import (
    binary_label,
    candidate_reduced_choi_generators,
    canonical_signed_signature,
    pauli_binary,
    pauli_spec_to_stim,
    signed_reduced_stabilizers,
    stabilizer_overlap_with_pure_target,
    stim_to_pauli_spec,
    support_code_from_source_choi,
    support_encoder,
    symplectic_destabilizers,
    tableau_from_gate_specs,
    tableau_to_gate_specs,
    two_qubit_depth,
    bell_target_generators,
)


def _initial_source_choi_generators(problem: RecoveryProblem) -> list[stim.PauliString]:
    message = len(problem.channel_input)
    system_width = len(problem.qubit_order)
    total = message + system_width
    system_index = {wire: message + index for index, wire in enumerate(problem.qubit_order)}
    result: list[stim.PauliString] = []
    # Interleaved X/Z Bell generators are the canonical v1 ordering.  It is
    # also the ordering used by the frozen structural compiler regressions.
    for index, wire in enumerate(problem.channel_input):
        for pauli_name in ("X", "Z"):
            body = ["_"] * total
            body[index] = body[system_index[wire]] = pauli_name
            result.append(stim.PauliString("+" + "".join(body)))
    ancilla_position = {wire: index for index, wire in enumerate(problem.ancilla_qubits)}
    for spec in problem.ancilla_initial_stabilizers:
        local = pauli_spec_to_stim(spec)
        body = ["_"] * total
        local_body = str(local)[-len(local) :]
        for wire, position in ancilla_position.items():
            body[system_index[wire]] = local_body[position]
        phase = stim_to_pauli_spec(local, problem.ancilla_qubits).phase_exponent_mod_4
        result.append(
            pauli_spec_to_stim(
                PauliSpec(tuple(str(index) for index in range(total)), "".join(body).replace("_", "I"), phase)
            )
        )
    if len(result) != total:
        raise AssertionError("initial source Choi does not have a complete generator set")
    return result


def _compiler_source_choi(problem: RecoveryProblem) -> stim.Tableau:
    """Compiler path: prepare the state, then execute the source circuit."""
    message = len(problem.channel_input)
    total_order = tuple(f"ref:{wire}" for wire in problem.channel_input) + problem.qubit_order
    preparation = stim.Tableau.from_stabilizers(
        _initial_source_choi_generators(problem)
    ).to_circuit()
    index = {wire: message + position for position, wire in enumerate(problem.qubit_order)}
    for gate in problem.source_clifford:
        targets = [index[wire] for wire in gate.qubits]
        preparation.append("CX" if gate.operation == "CNOT" else gate.operation, targets)
    tableau = stim.Tableau.from_circuit(preparation)
    if len(tableau) != len(total_order):
        raise AssertionError("source Choi wire count changed during preparation")
    return tableau


def _compiler_petz_choi(problem: RecoveryProblem, source: stim.Tableau) -> stim.Tableau:
    """Compiler's structural Petz-target construction."""
    message = len(problem.channel_input)
    source_index = {wire: message + index for index, wire in enumerate(problem.qubit_order)}
    order = (
        *range(message),
        *[source_index[wire] for wire in problem.accessible_partition],
        *[source_index[wire] for wire in problem.inaccessible_partition],
    )
    stabilizers: list[stim.PauliString] = []
    for index in range(len(source)):
        item = source.z_output(index)
        body = str(item)[-len(item) :]
        reordered = "".join(body[wire] for wire in order)
        negative = complex(item.sign).real < 0
        negative ^= reordered.count("Y") % 2 == 1
        stabilizers.append(stim.PauliString(("-" if negative else "+") + reordered))
    return stim.Tableau.from_stabilizers(stabilizers)


def _transpose(pauli: stim.PauliString) -> stim.PauliString:
    return pauli * (-1 if str(pauli)[-len(pauli) :].count("Y") & 1 else 1)


def _make(label: str, sign: int = 1) -> stim.PauliString:
    return stim.PauliString(("+" if sign == 1 else "-") + label.replace("I", "_"))


def _label(pauli: stim.PauliString, wires: tuple[int, ...]) -> str:
    body = str(pauli)[-len(pauli) :]
    return "".join(body[wire].replace("_", "I") for wire in wires)


def _sign(pauli: stim.PauliString) -> int:
    return 1 if complex(pauli.sign).real > 0 else -1


def _binary_on_wires(pauli: stim.PauliString, wires: tuple[int, ...]) -> np.ndarray:
    x, z = pauli.to_numpy()
    return np.concatenate((x[list(wires)], z[list(wires)])).astype(np.uint8)


def _compiler_logical_correlations(
    petz: stim.Tableau, message: int, accessible: int, code
) -> list[dict[str, str]]:
    generators = [petz.z_output(index) for index in range(len(petz))]
    ref_wires = tuple(range(message, message + accessible))
    output_wires = (*range(message), *range(message + accessible, len(petz)))
    support = [_transpose(stim.PauliString(label)) for label in code.signed_stabilizer_labels]
    embedded_support: list[stim.PauliString] = []
    for item in support:
        body = str(item)[-len(item) :]
        sign = "-" if complex(item.sign).real < 0 else "+"
        embedded_support.append(
            stim.PauliString(sign + "_" * message + body + "_" * (len(petz) - message - accessible))
        )
    ref_rows = [_binary_on_wires(generator, ref_wires) for generator in generators]
    ref_rows.extend(pauli_binary(item) for item in support)
    system = np.asarray(ref_rows, dtype=np.uint8).T
    n_generators = len(generators)
    n_variables = n_generators + len(support)
    priority = [*reversed(range(n_generators)), *reversed(range(n_generators, n_variables))]
    rows: list[dict[str, str]] = []
    for family, labels in (("X", code.logical_x_labels), ("Z", code.logical_z_labels)):
        for index, label in enumerate(labels, 1):
            target = _transpose(_make(label))
            coefficients = lexicographic_solution(
                system, pauli_binary(target), n_variables, priority=priority
            )
            candidate = stim.PauliString("+" + "_" * len(petz))
            for position, generator in enumerate(generators):
                if coefficients[position]:
                    candidate *= generator
            for offset, gauge in enumerate(embedded_support):
                if coefficients[n_generators + offset]:
                    candidate *= gauge
            if _label(candidate, ref_wires) != _label(target, tuple(range(accessible))):
                raise AssertionError("signed Choi solve produced the wrong Ref restriction")
            found = _make(_label(candidate, output_wires), _sign(candidate) * _sign(target))
            rows.append(
                {
                    "logical_pauli": f"{family}{index}",
                    "input": str(_make(label)),
                    "reference_transpose": str(target),
                    "output": str(found),
                }
            )
    return rows


def _compiler_output_support_stabilizers(
    petz: stim.Tableau, message: int, accessible: int
) -> list[str]:
    generators = [petz.z_output(index) for index in range(len(petz))]
    ref_wires = tuple(range(message, message + accessible))
    output_wires = (*range(message), *range(message + accessible, len(petz)))
    constraints = np.asarray(
        [_binary_on_wires(generator, ref_wires) for generator in generators], dtype=np.uint8
    ).T
    mapping = np.asarray(
        [_binary_on_wires(generator, output_wires) for generator in generators], dtype=np.uint8
    ).T
    selected = canonical_kernel_image_basis(constraints, len(generators), mapping)
    result: list[str] = []
    for coefficients, _ in selected:
        item = stim.PauliString("+" + "_" * len(petz))
        for index, generator in enumerate(generators):
            if coefficients[index]:
                item *= generator
        sign = "-" if complex(item.sign).real < 0 else "+"
        result.append(sign + "".join(str(item)[-len(item) :][wire] for wire in output_wires))
    return result


def _synthesize_dilation(problem: RecoveryProblem, petz: stim.Tableau, code):
    message = len(problem.channel_input)
    accessible = len(problem.accessible_partition)
    rows = _compiler_logical_correlations(petz, message, accessible, code)
    output_stabilizers = _compiler_output_support_stabilizers(petz, message, accessible)
    xs = [stim.PauliString(row["output"]) for row in rows if row["logical_pauli"].startswith("X")]
    zs = [stim.PauliString(row["output"]) for row in rows if row["logical_pauli"].startswith("Z")]
    output_width = len(xs[0])
    if len(output_stabilizers) != output_width - code.logical_qubits:
        raise ValueError("output support stabilizer count is inconsistent")
    logical_pairs = list(zip((pauli_binary(item) for item in xs), (pauli_binary(item) for item in zs)))
    output_destabilizers = [
        stim.PauliString(binary_label(vector))
        for vector in symplectic_destabilizers(
            [pauli_binary(stim.PauliString(item)) for item in output_stabilizers],
            logical_pairs,
            output_width,
        )
    ]
    encoder = support_encoder(code)
    output = stim.Tableau.from_conjugated_generators(
        xs=xs + output_destabilizers,
        zs=zs + [stim.PauliString(item) for item in output_stabilizers],
    )
    environment_order = tuple(
        wire for wire in problem.accessible_partition if wire not in problem.requested_output
    )
    output_wires = (*problem.requested_output, *environment_order[: output_width - message])
    if len(output_wires) != output_width:
        raise ValueError("not enough accessible wires for the Petz dilation")
    gates = (
        *tableau_to_gate_specs(encoder.inverse(), problem.accessible_partition),
        *tableau_to_gate_specs(output, output_wires),
    )
    logical_signature = tuple(
        str(item)
        for pair in zip(
            [output.x_output(index) for index in range(code.logical_qubits)],
            [output.z_output(index) for index in range(code.logical_qubits)],
        )
        for item in pair
    )
    return tuple(gates), encoder, output, rows, logical_signature


def _source_entanglement_fidelity(
    problem: RecoveryProblem, source: stim.Tableau, circuit
) -> float:
    message = len(problem.channel_input)
    preparation = source.to_circuit()
    system_index = {wire: message + index for index, wire in enumerate(problem.qubit_order)}
    for gate in circuit:
        targets = [system_index[wire] for wire in gate.qubits]
        preparation.append("CX" if gate.operation == "CNOT" else gate.operation, targets)
    final = stim.Tableau.from_circuit(preparation)
    generators = [final.z_output(index) for index in range(len(final))]
    keep = (*range(message), *[system_index[wire] for wire in problem.requested_output])
    reduced = signed_reduced_stabilizers(generators, tuple(keep))
    return stabilizer_overlap_with_pure_target(reduced, bell_target_generators(message))


def _petz_fidelity_from_source(problem: RecoveryProblem, source: stim.Tableau) -> float:
    message = len(problem.channel_input)
    source_index = {wire: message + index for index, wire in enumerate(problem.qubit_order)}
    complement = tuple(source_index[wire] for wire in problem.inaccessible_partition)
    generators = [source.z_output(index) for index in range(len(source))]
    s_c = len(complement) - len(signed_reduced_stabilizers(generators, complement))
    rc = (*range(message), *complement)
    s_rc = len(rc) - len(signed_reduced_stabilizers(generators, rc))
    mutual_information = message + s_c - s_rc
    return 2.0 ** (-mutual_information)


def compile_recovery(problem: RecoveryProblem) -> RecoveryArtifact:
    """Compile a pure-Clifford stabilizer recovery problem without dense states."""
    source = _compiler_source_choi(problem)
    petz = _compiler_petz_choi(problem, source)
    code = support_code_from_source_choi(
        source,
        len(problem.channel_input),
        problem.qubit_order,
        problem.accessible_partition,
    )
    if problem.expected_tau_support:
        expected = [pauli_spec_to_stim(item) for item in problem.expected_tau_support]
        actual = [stim.PauliString(item) for item in code.signed_stabilizer_labels]
        if canonical_signed_signature(expected) != canonical_signed_signature(actual):
            raise ValueError("derived tau support differs from the optional assertion")
    logical_gates, _, output, _, logical_signature = _synthesize_dilation(problem, petz, code)
    routed = route_named_circuit(logical_gates, problem.coupling_graph, problem.router)
    logical_tableau = tableau_from_gate_specs(logical_gates, problem.accessible_partition)
    routed_tableau = tableau_from_gate_specs(routed.gates, problem.accessible_partition)
    circuit_equivalent = logical_tableau == routed_tableau

    target_reduced = signed_reduced_stabilizers(
        [petz.z_output(index) for index in range(len(petz))],
        tuple(range(len(problem.channel_input) + len(problem.accessible_partition))),
    )
    candidate_reduced = candidate_reduced_choi_generators(
        problem.accessible_partition, problem.requested_output, code, routed.gates
    )
    target_signature = canonical_signed_signature(target_reduced)
    candidate_signature = canonical_signed_signature(candidate_reduced)
    reduced_choi_equal = target_signature == candidate_signature
    petz_fidelity = _petz_fidelity_from_source(problem, source)
    circuit_fidelity = _source_entanglement_fidelity(problem, source, routed.gates)
    tolerance = float(problem.certification_thresholds.numerical_tolerance)
    compiler_valid = (
        circuit_equivalent
        and reduced_choi_equal
        and abs(petz_fidelity - circuit_fidelity) < tolerance
        and routed.final_wire_at_site == problem.physical_initial_order
    )

    tau_generators = tuple(
        stim_to_pauli_spec(stim.PauliString(item), problem.accessible_partition)
        for item in code.signed_stabilizer_labels
    )
    choi_order = (
        *tuple(f"out:{wire}" for wire in problem.requested_output),
        *tuple(f"ref:{wire}" for wire in problem.accessible_partition),
        *tuple(f"env:{wire}" for wire in problem.inaccessible_partition),
    )
    petz_generators = tuple(
        stim_to_pauli_spec(petz.z_output(index), choi_order)
        for index in range(len(petz))
    )
    metrics = tuple(
        sorted(
            (
                MetricEntry("circuit_entanglement_fidelity", format(circuit_fidelity, ".17g"), "probability"),
                MetricEntry("petz_entanglement_fidelity", format(petz_fidelity, ".17g"), "probability"),
                MetricEntry("reduced_choi_equal", "1" if reduced_choi_equal else "0", "boolean"),
            ),
            key=lambda item: item.name,
        )
    )
    return RecoveryArtifact(
        format_version=ARTIFACT_FORMAT_VERSION,
        source_semantic_problem_hash=semantic_problem_hash(problem),
        source_document_hash=problem_document_hash(problem),
        tau_support=TauSupportSpec(
            qubit_order=problem.accessible_partition,
            signed_generators=tau_generators,
            support_rank=code.support_rank,
            logical_qubits=code.logical_qubits,
        ),
        petz_target=PetzTargetSpec(choi_order, petz_generators),
        logical_circuit=CircuitSpec(problem.accessible_partition, logical_gates),
        routed_circuit=CircuitSpec(problem.accessible_partition, routed.gates),
        topology=problem.coupling_graph,
        final_permutation=routed.final_wire_at_site,
        resources=ResourceSpec(
            logical_depth=two_qubit_depth(logical_gates),
            routed_depth=routed.two_qubit_depth,
            logical_cnot=sum(gate.operation == "CNOT" for gate in logical_gates),
            routed_cnot=routed.cnot_count,
            movement_swaps=routed.movement_swaps,
            restoration_swaps=routed.restoration_swaps,
            environment_qubits=len(output) - code.logical_qubits,
        ),
        certificate=CertificateSpec(
            target_reduced_choi_signature=target_signature,
            candidate_reduced_choi_signature=candidate_signature,
            logical_action_signature=logical_signature,
            compiler_declared_valid=compiler_valid,
        ),
        metrics=metrics,
    )
