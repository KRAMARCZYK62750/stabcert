"""Generator-level certificates for signed Clifford Petz dilations."""
from __future__ import annotations

import numpy as np
import stim

from .gf2 import rank, solve_affine
from .gf2 import canonical_kernel_image_basis
from .layout import SystemLayout
from .parametric_synthesis import tableau_gates
from .simulator import Gate
from .stabilizer import pure_stabilizer_decoupling


def _binary(pauli: stim.PauliString) -> np.ndarray:
    x, z = pauli.to_numpy()
    return np.concatenate((x, z)).astype(np.uint8)


def _product(generators: list[stim.PauliString], coefficients) -> stim.PauliString:
    result = stim.PauliString("+" + "_" * len(generators[0]))
    for index, generator in enumerate(generators):
        if coefficients[index]:
            result *= generator
    return result


def signed_stabilizer_groups_equal(
    first: list[stim.PauliString], second: list[stim.PauliString]
) -> bool:
    """Compare signed stabilizer subgroups by row-space membership."""
    if not first or not second:
        return not first and not second
    first_binary = [_binary(item) for item in first]
    second_binary = [_binary(item) for item in second]
    if rank(first_binary) != rank(second_binary):
        return False

    def included(source, target, target_binary):
        system = np.asarray(target_binary, dtype=np.uint8).T
        for item in source:
            solved = solve_affine(system, _binary(item), len(target))
            if solved is None:
                return False
            if _product(target, solved[0]) != item:
                return False
        return True

    return included(first, second, second_binary) and included(
        second, first, first_binary
    )


def canonical_signed_stabilizer_signature(
    generators: list[stim.PauliString],
) -> tuple[str, ...]:
    """Canonical signed RREF basis of a commuting stabilizer subgroup."""
    if not generators:
        return ()
    rows = [item.copy() for item in generators]
    binary = [_binary(item) for item in rows]
    pivot_row = 0
    for column in range(len(binary[0])):
        selected = next(
            (index for index in range(pivot_row, len(rows)) if binary[index][column]),
            None,
        )
        if selected is None:
            continue
        rows[pivot_row], rows[selected] = rows[selected], rows[pivot_row]
        binary[pivot_row], binary[selected] = binary[selected], binary[pivot_row]
        for index in range(len(rows)):
            if index != pivot_row and binary[index][column]:
                rows[index] *= rows[pivot_row]
                binary[index] ^= binary[pivot_row]
        pivot_row += 1
        if pivot_row == len(rows):
            break
    if pivot_row != len(rows):
        raise ValueError("stabilizer generators are not independent")
    return tuple(str(item) for item in rows)


def _append_reference(
    output: stim.PauliString, logical: int, reference_index: int | None, pauli: str = "I"
) -> stim.PauliString:
    text = str(output)
    extended = stim.PauliString(text[0] + text[1:] + "_" * logical)
    if reference_index is None:
        return extended
    reference = ["_"] * (len(output) + logical)
    reference[len(output) + reference_index] = pauli
    return extended * stim.PauliString("+" + "".join(reference))


def _logical_choi_target_generators(rows, logical: int):
    by_name = {row["logical_pauli"]: stim.PauliString(row["output"]) for row in rows}
    result = []
    for index in range(logical):
        result.append(_append_reference(by_name[f"X{index + 1}"], logical, index, "X"))
        result.append(_append_reference(by_name[f"Z{index + 1}"], logical, index, "Z"))
    if not rows or "output_support_stabilizers" not in rows[0]:
        raise ValueError("signed dilation lacks target output-support generators")
    result.extend(
        _append_reference(stim.PauliString(label), logical, None)
        for label in rows[0]["output_support_stabilizers"]
    )
    return result


def _logical_choi_candidate_generators(output: stim.Tableau, logical: int):
    result = []
    for index in range(logical):
        result.append(_append_reference(output.x_output(index), logical, index, "X"))
        result.append(_append_reference(output.z_output(index), logical, index, "Z"))
    result.extend(
        _append_reference(output.z_output(index), logical, None)
        for index in range(logical, len(output))
    )
    return result


def _tableau_from_gates(gates: list[Gate], n: int) -> stim.Tableau:
    circuit = stim.Circuit()
    for qubit in range(n):
        circuit.append("I", [qubit])
    for gate in gates:
        if gate.name == "CNOT":
            assert gate.b is not None
            circuit.append("CX", [gate.a, gate.b])
        else:
            circuit.append(gate.name, [gate.a])
    return stim.Tableau.from_circuit(circuit)


def certify_signed_dilation(channel, encoder, output, rows, logical: int):
    """Certify the fixed-gauge Petz purification using signed generators."""
    target = _logical_choi_target_generators(rows, logical)
    candidate = _logical_choi_candidate_generators(output, logical)
    purification_equal = signed_stabilizer_groups_equal(target, candidate)
    encoder_gates = tableau_gates(encoder.inverse(), tuple(range(len(encoder))))
    output_gates = tableau_gates(output, tuple(range(len(output))))
    encoder_synthesis_equal = _tableau_from_gates(
        encoder_gates, len(encoder)
    ) == encoder.inverse()
    output_synthesis_equal = _tableau_from_gates(
        output_gates, len(output)
    ) == output
    return {
        "target_generator_count": len(target),
        "candidate_generator_count": len(candidate),
        "signed_generator_groups_equal": purification_equal,
        "purification_equal_in_fixed_gauge": purification_equal,
        "reduced_choi_equal": purification_equal,
        "environment_isometry": "identity_in_fixed_purification_gauge",
        "encoder_tableau_synthesis_equal": encoder_synthesis_equal,
        "output_tableau_synthesis_equal": output_synthesis_equal,
        "certified": purification_equal
        and encoder_synthesis_equal
        and output_synthesis_equal,
        "stabilizer_group_elements_enumerated": 0,
        "support_operators_enumerated": 0,
    }


def certify_routed_equivalence(
    layout: SystemLayout,
    t: int,
    direct_gates: list[Gate],
    routed_gates: tuple[Gate, ...] | list[Gate],
) -> bool:
    chain = layout.chain(t)
    local = {wire: index for index, wire in enumerate(chain)}

    def localized(gates):
        return [
            Gate(
                gate.name,
                local[gate.a],
                None if gate.b is None else local[gate.b],
            )
            for gate in gates
        ]

    return _tableau_from_gates(localized(direct_gates), len(chain)) == _tableau_from_gates(
        localized(routed_gates), len(chain)
    )


def _signed_final_stabilizers(
    layout: SystemLayout,
    scrambler: list[Gate],
    gates: list[Gate] | tuple[Gate, ...],
) -> list[stim.PauliString]:
    """Final pure-state generators without constructing a state vector."""
    circuit = stim.Circuit()
    for qubit in range(layout.n_qubits):
        circuit.append("I", [qubit])
    for left, right in (
        *zip(layout.R_register, layout.A_register),
        *zip(layout.B, layout.E),
    ):
        circuit.append("H", [left])
        circuit.append("CX", [left, right])
    for gate in (*scrambler, *gates):
        if gate.name == "CNOT":
            assert gate.b is not None
            circuit.append("CX", [gate.a, gate.b])
        else:
            circuit.append(gate.name, [gate.a])
    tableau = stim.Tableau.from_circuit(circuit)
    return [tableau.z_output(index) for index in range(layout.n_qubits)]


def _restriction(pauli: stim.PauliString, wires: tuple[int, ...]) -> np.ndarray:
    x, z = pauli.to_numpy()
    return np.concatenate((x[list(wires)], z[list(wires)])).astype(np.uint8)


def _localized(pauli: stim.PauliString, wires: tuple[int, ...]) -> stim.PauliString:
    text = str(pauli)
    return stim.PauliString(
        text[0] + "".join(text[1 + wire] for wire in wires)
    )


def _signed_reduced_stabilizers(
    generators: list[stim.PauliString], keep: tuple[int, ...]
) -> list[stim.PauliString]:
    """Independent signed stabilizers of a reduced stabilizer state."""
    n = len(generators[0])
    outside = tuple(qubit for qubit in range(n) if qubit not in keep)
    constraints = np.asarray(
        [_restriction(generator, outside) for generator in generators],
        dtype=np.uint8,
    ).T
    mapping = np.asarray(
        [_restriction(generator, keep) for generator in generators],
        dtype=np.uint8,
    ).T
    selected = canonical_kernel_image_basis(constraints, len(generators), mapping)
    reduced = []
    for coefficients, _ in selected:
        item = stim.PauliString("+" + "_" * n)
        for index, generator in enumerate(generators):
            if coefficients[index]:
                item *= generator
        reduced.append(_localized(item, keep))
    return reduced


def _bell_target_generators(message_qubits: int) -> list[stim.PauliString]:
    """Signed generators of Phi(R:A') in wire order R|A'."""
    result = []
    width = 2 * message_qubits
    for index in range(message_qubits):
        x = ["_"] * width
        x[index] = x[message_qubits + index] = "X"
        result.append(stim.PauliString("+" + "".join(x)))
        z = ["_"] * width
        z[index] = z[message_qubits + index] = "Z"
        result.append(stim.PauliString("+" + "".join(z)))
    return result


def stabilizer_state_fidelity(
    reduced_generators: list[stim.PauliString],
    pure_target_generators: list[stim.PauliString],
) -> dict[str, object]:
    """Exact overlap with a pure stabilizer target from a signed intersection.

    If the binary intersection has rank ell and its sign characters agree, the
    overlap is 2**(ell-q), where q is the number of target qubits. A sign
    conflict makes the character sum, and therefore the overlap, exactly zero.
    """
    q = len(pure_target_generators)
    if any(len(item) != q for item in pure_target_generators):
        raise ValueError("target generators do not define a q-qubit pure state")
    if any(len(item) != q for item in reduced_generators):
        raise ValueError("reduced and target stabilizers use different widths")
    source_binary = [_binary(item) for item in reduced_generators]
    target_binary = [_binary(item) for item in pure_target_generators]
    source_matrix = np.asarray(source_binary, dtype=np.uint8)
    if source_matrix.size == 0:
        source_matrix = np.zeros((0, 2 * q), dtype=np.uint8)
    target_matrix = np.asarray(target_binary, dtype=np.uint8)
    variables = len(source_binary) + len(target_binary)
    constraints = np.concatenate(
        (source_matrix.T, target_matrix.T), axis=1
    )
    mapping = np.concatenate(
        (
            source_matrix.T,
            np.zeros((2 * q, len(target_binary)), dtype=np.uint8),
        ),
        axis=1,
    )
    intersection = canonical_kernel_image_basis(constraints, variables, mapping)
    phases_match = True
    for coefficients, _ in intersection:
        source_product = stim.PauliString("+" + "_" * q)
        target_product = stim.PauliString("+" + "_" * q)
        for index, generator in enumerate(reduced_generators):
            if coefficients[index]:
                source_product *= generator
        offset = len(reduced_generators)
        for index, generator in enumerate(pure_target_generators):
            if coefficients[offset + index]:
                target_product *= generator
        if source_product != target_product:
            phases_match = False
            break
    intersection_rank = len(intersection)
    fidelity = 0.0 if not phases_match else 2.0 ** (intersection_rank - q)
    return {
        "fidelity": fidelity,
        "intersection_rank": intersection_rank,
        "target_rank": q,
        "phases_match_on_intersection": phases_match,
    }


def circuit_entanglement_fidelity_stabilizer(
    layout: SystemLayout,
    scrambler: list[Gate],
    t: int,
    gates: list[Gate] | tuple[Gate, ...],
) -> dict[str, object]:
    """Exact Bell fidelity without dense states or reduced matrices."""
    keep = (*layout.R_register, *layout.X(t)[: layout.n_message])
    final_generators = _signed_final_stabilizers(layout, scrambler, gates)
    reduced = _signed_reduced_stabilizers(final_generators, keep)
    target = _bell_target_generators(layout.n_message)
    result = stabilizer_state_fidelity(reduced, target)
    return {
        **result,
        "reduced_stabilizer_rank": len(reduced),
        "dense_state_amplitudes_constructed": 0,
        "dense_reduced_matrices_constructed": 0,
    }


def structural_validation(
    layout: SystemLayout,
    channel,
    scrambler: list[Gate],
    t: int,
    gates: list[Gate] | tuple[Gate, ...],
    encoder,
    output,
    rows,
):
    support_logical = len(rows) // 2
    certificate = certify_signed_dilation(
        channel, encoder, output, rows, support_logical
    )
    circuit_overlap = circuit_entanglement_fidelity_stabilizer(
        layout, scrambler, t, gates
    )
    circuit_fidelity = float(circuit_overlap["fidelity"])
    decoupling = pure_stabilizer_decoupling(
        scrambler,
        layout.n_qubits,
        layout.R_register,
        layout.A_register,
        layout.B,
        layout.E,
        t,
    )
    # Exact only in the audited pure-Clifford/maximally-entangled subclass.
    petz_fidelity = 2.0 ** (-int(decoupling["mutual_information_bits"]))
    return {
        **certificate,
        **{f"entanglement_{key}": value for key, value in circuit_overlap.items()},
        "petz_fidelity": petz_fidelity,
        "circuit_fidelity": circuit_fidelity,
        "choi_fidelity_certified": 1.0 if certificate["reduced_choi_equal"] else 0.0,
        "validated": certificate["certified"]
        and abs(circuit_fidelity - petz_fidelity) < 1e-12,
    }
