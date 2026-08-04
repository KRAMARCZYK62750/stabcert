"""Low-level stabilizer primitives shared by recovery compiler and verifier.

This module contains representation and GF(2) operations only.  In
particular, it does not construct the Petz target; the compiler and verifier
do that independently in their respective modules.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import stim

from .gf2 import (
    canonical_kernel_image_basis,
    lexicographic_mapped_outside_span,
    lexicographic_solution,
    rank,
    solve_affine,
)
from .recovery_problem import GateSpec, PauliSpec


def pauli_spec_to_stim(spec: PauliSpec) -> stim.PauliString:
    phase = ("+", "+i", "-", "-i")[spec.phase_exponent_mod_4]
    return stim.PauliString(phase + spec.operators.replace("I", "_"))


def stim_to_pauli_spec(
    pauli: stim.PauliString, qubit_order: tuple[str, ...]
) -> PauliSpec:
    if len(pauli) != len(qubit_order):
        raise ValueError("Pauli width/order mismatch")
    sign = complex(pauli.sign)
    phase = {
        1 + 0j: 0,
        0 + 1j: 1,
        -1 + 0j: 2,
        0 - 1j: 3,
    }.get(sign)
    if phase is None:
        raise ValueError(f"unsupported Pauli phase: {sign}")
    return PauliSpec(
        qubit_order,
        str(pauli)[len(str(pauli)) - len(pauli) :].replace("_", "I"),
        phase,
    )


def pauli_binary(pauli: stim.PauliString) -> np.ndarray:
    x, z = pauli.to_numpy()
    return np.concatenate((x, z)).astype(np.uint8)


def binary_label(vector: np.ndarray) -> str:
    width = len(vector) // 2
    return "".join(
        "IXZY"[int(vector[index]) + 2 * int(vector[width + index])]
        for index in range(width)
    )


def _j(vector: np.ndarray) -> np.ndarray:
    width = len(vector) // 2
    return np.concatenate((vector[width:], vector[:width])).astype(np.uint8)


def symplectic_logical_pairs(
    stabilizers: list[np.ndarray], n: int
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Canonical logical basis of a stabilizer code by GF(2) elimination."""
    width = 2 * n
    constraints = np.asarray([_j(row) for row in stabilizers], dtype=np.uint8)
    if constraints.size == 0:
        constraints = np.zeros((0, width), dtype=np.uint8)
    targets = np.zeros(len(constraints), dtype=np.uint8)
    transformation = np.eye(width, dtype=np.uint8)
    span = [row.copy() for row in stabilizers]
    pairs: list[tuple[np.ndarray, np.ndarray]] = []
    for _ in range(n - len(stabilizers)):
        source_x = lexicographic_mapped_outside_span(
            constraints, targets, width, transformation, span
        )
        logical_x = (transformation @ source_x) & 1
        z_constraint = (transformation.T @ _j(logical_x)) & 1
        source_z = lexicographic_mapped_outside_span(
            np.vstack((constraints, z_constraint)),
            np.append(targets, np.uint8(1)),
            width,
            transformation,
            span + [logical_x],
        )
        logical_z = (transformation @ source_z) & 1
        pairs.append((logical_x, logical_z))
        span.extend((logical_x, logical_z))
        transformation = (
            (
                np.eye(width, dtype=np.uint8)
                ^ np.outer(logical_x, _j(logical_z))
                ^ np.outer(logical_z, _j(logical_x))
            )
            @ transformation
        ) & 1
    return pairs


def symplectic_destabilizers(
    stabilizers: list[np.ndarray],
    logical_pairs: list[tuple[np.ndarray, np.ndarray]],
    n: int,
) -> list[np.ndarray]:
    width = 2 * n
    result: list[np.ndarray] = []
    for index in range(len(stabilizers)):
        rows = [_j(row) for row in stabilizers]
        values = [int(position == index) for position in range(len(stabilizers))]
        for pair in logical_pairs:
            for logical in pair:
                rows.append(_j(logical))
                values.append(0)
        for previous in result:
            rows.append(_j(previous))
            values.append(0)
        result.append(
            lexicographic_solution(
                np.asarray(rows, dtype=np.uint8),
                np.asarray(values, dtype=np.uint8),
                width,
            )
        )
    return result


def gate_specs_to_stim(
    gates: tuple[GateSpec, ...] | list[GateSpec], qubit_order: tuple[str, ...]
) -> stim.Circuit:
    index = {qubit: position for position, qubit in enumerate(qubit_order)}
    circuit = stim.Circuit()
    for qubit in range(len(qubit_order)):
        circuit.append("I", [qubit])
    for gate in gates:
        targets = [index[qubit] for qubit in gate.qubits]
        circuit.append("CX" if gate.operation == "CNOT" else gate.operation, targets)
    return circuit


def tableau_to_gate_specs(
    tableau: stim.Tableau, qubit_order: tuple[str, ...]
) -> tuple[GateSpec, ...]:
    if len(tableau) != len(qubit_order):
        raise ValueError("tableau/order mismatch")
    result: list[GateSpec] = []
    for instruction in tableau.to_circuit():
        targets = [target.value for target in instruction.targets_copy()]
        if instruction.name == "H":
            result.extend(GateSpec("H", (qubit_order[item],)) for item in targets)
        elif instruction.name == "S":
            result.extend(GateSpec("S", (qubit_order[item],)) for item in targets)
        elif instruction.name == "CX":
            result.extend(
                GateSpec("CNOT", (qubit_order[left], qubit_order[right]))
                for left, right in zip(targets[::2], targets[1::2])
            )
        elif instruction.name == "X":
            result.extend(GateSpec("X", (qubit_order[item],)) for item in targets)
        elif instruction.name == "Z":
            # Keep the v1 gate alphabet fixed while preserving the exact phase.
            for item in targets:
                result.extend((GateSpec("S", (qubit_order[item],)),) * 2)
        else:
            raise ValueError(f"unsupported synthesized Stim gate: {instruction.name}")
    return tuple(result)


def tableau_from_gate_specs(
    gates: tuple[GateSpec, ...] | list[GateSpec], qubit_order: tuple[str, ...]
) -> stim.Tableau:
    return stim.Tableau.from_circuit(gate_specs_to_stim(gates, qubit_order))


def two_qubit_depth(gates: tuple[GateSpec, ...] | list[GateSpec]) -> int:
    levels: dict[str, int] = {}
    depth = 0
    for gate in gates:
        if gate.operation != "CNOT":
            continue
        level = max(levels.get(gate.qubits[0], 0), levels.get(gate.qubits[1], 0)) + 1
        levels[gate.qubits[0]] = levels[gate.qubits[1]] = level
        depth = max(depth, level)
    return depth


def _restriction(pauli: stim.PauliString, wires: tuple[int, ...]) -> np.ndarray:
    x, z = pauli.to_numpy()
    if not wires:
        return np.zeros(0, dtype=np.uint8)
    return np.concatenate((x[list(wires)], z[list(wires)])).astype(np.uint8)


def _localized(pauli: stim.PauliString, wires: tuple[int, ...]) -> stim.PauliString:
    body = str(pauli)[-len(pauli) :]
    phase = stim_to_pauli_spec(pauli, tuple(str(q) for q in range(len(pauli))))
    local = "".join(body[wire] for wire in wires)
    return pauli_spec_to_stim(
        PauliSpec(tuple(str(q) for q in range(len(wires))), local.replace("_", "I"), phase.phase_exponent_mod_4)
    )


def signed_reduced_stabilizers(
    generators: list[stim.PauliString] | tuple[stim.PauliString, ...],
    keep: tuple[int, ...],
) -> list[stim.PauliString]:
    """Independent signed stabilizers after tracing all wires outside ``keep``."""
    if not generators:
        return []
    width = len(generators[0])
    if len(set(keep)) != len(keep) or any(not 0 <= wire < width for wire in keep):
        raise ValueError("invalid reduced-state wire selection")
    outside = tuple(wire for wire in range(width) if wire not in keep)
    constraints = np.asarray(
        [_restriction(generator, outside) for generator in generators], dtype=np.uint8
    ).T
    mapping = np.asarray(
        [_restriction(generator, keep) for generator in generators], dtype=np.uint8
    ).T
    selected = canonical_kernel_image_basis(constraints, len(generators), mapping)
    reduced: list[stim.PauliString] = []
    for coefficients, _ in selected:
        item = stim.PauliString("+" + "_" * width)
        for index, generator in enumerate(generators):
            if coefficients[index]:
                item *= generator
        reduced.append(_localized(item, keep))
    return reduced


def canonical_signed_signature(
    generators: list[stim.PauliString] | tuple[stim.PauliString, ...]
) -> tuple[str, ...]:
    """Canonical signed RREF basis, independent of generator ordering."""
    if not generators:
        return ()
    rows = [item.copy() for item in generators]
    binary = [pauli_binary(item) for item in rows]
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


def signed_groups_equal(
    first: list[stim.PauliString] | tuple[stim.PauliString, ...],
    second: list[stim.PauliString] | tuple[stim.PauliString, ...],
) -> bool:
    if not first or not second:
        return not first and not second
    first_binary = [pauli_binary(item) for item in first]
    second_binary = [pauli_binary(item) for item in second]
    if rank(first_binary) != rank(second_binary):
        return False

    def included(source, target, target_binary) -> bool:
        system = np.asarray(target_binary, dtype=np.uint8).T
        for item in source:
            solved = solve_affine(system, pauli_binary(item), len(target))
            if solved is None:
                return False
            product = stim.PauliString("+" + "_" * len(item))
            for position, generator in enumerate(target):
                if solved[0][position]:
                    product *= generator
            if product != item:
                return False
        return True

    return included(first, second, second_binary) and included(second, first, first_binary)


@dataclass(frozen=True)
class SupportCodeData:
    qubit_order: tuple[str, ...]
    signed_stabilizer_labels: tuple[str, ...]
    logical_x_labels: tuple[str, ...]
    logical_z_labels: tuple[str, ...]
    destabilizer_labels: tuple[str, ...]
    support_rank: int
    logical_qubits: int

    def legacy_dict(self) -> dict[str, object]:
        return {
            "physical_qubits": tuple(range(len(self.qubit_order))),
            "support_dimension": self.support_rank,
            "independent_stabilizers": len(self.signed_stabilizer_labels),
            "logical_qubits": self.logical_qubits,
            "signed_stabilizer_labels": list(self.signed_stabilizer_labels),
            "stabilizer_labels": [item[1:] for item in self.signed_stabilizer_labels],
            "logical_X_labels": list(self.logical_x_labels),
            "logical_Z_labels": list(self.logical_z_labels),
            "destabilizer_labels": list(self.destabilizer_labels),
        }


def support_code_from_source_choi(
    source_choi: stim.Tableau,
    message_qubits: int,
    source_qubit_order: tuple[str, ...],
    accessible_order: tuple[str, ...],
) -> SupportCodeData:
    """Derive supp(tau_X) from a pure source Choi stabilizer state."""
    source_index = {name: index for index, name in enumerate(source_qubit_order)}
    keep = tuple(message_qubits + source_index[name] for name in accessible_order)
    generators = [source_choi.z_output(index) for index in range(len(source_choi))]
    reduced = signed_reduced_stabilizers(generators, keep)
    stabilizer_vectors = [pauli_binary(item) for item in reduced]
    logical_pairs = symplectic_logical_pairs(stabilizer_vectors, len(keep))
    destabilizers = symplectic_destabilizers(stabilizer_vectors, logical_pairs, len(keep))
    logical = len(keep) - len(reduced)
    return SupportCodeData(
        qubit_order=accessible_order,
        signed_stabilizer_labels=tuple(str(item).replace("_", "I") for item in reduced),
        logical_x_labels=tuple(binary_label(pair[0]) for pair in logical_pairs),
        logical_z_labels=tuple(binary_label(pair[1]) for pair in logical_pairs),
        destabilizer_labels=tuple(binary_label(item) for item in destabilizers),
        support_rank=1 << logical,
        logical_qubits=logical,
    )


def support_encoder(code: SupportCodeData) -> stim.Tableau:
    return stim.Tableau.from_conjugated_generators(
        xs=[
            stim.PauliString(label)
            for label in (*code.logical_x_labels, *code.destabilizer_labels)
        ],
        zs=[
            stim.PauliString(label)
            for label in (*code.logical_z_labels, *code.signed_stabilizer_labels)
        ],
    )


def _append_mapped_instruction(
    destination: stim.Circuit,
    instruction,
    mapping: tuple[int, ...],
    *,
    complex_conjugate: bool = False,
) -> None:
    targets = [mapping[target.value] for target in instruction.targets_copy()]
    name = instruction.name
    if complex_conjugate and name == "S":
        for _ in range(3):
            destination.append("S", targets)
        return
    destination.append(name, targets)


def candidate_reduced_choi_generators(
    accessible_order: tuple[str, ...],
    requested_output: tuple[str, ...],
    code: SupportCodeData,
    circuit_gates: tuple[GateSpec, ...],
) -> list[stim.PauliString]:
    """Reduced Choi stabilizers of a circuit restricted to supp(tau_X).

    A canonical purification of the normalized support projector is prepared
    on ``Ref(X)|X``.  The result is reduced to ``A'|Ref(X)`` after the supplied
    circuit is applied to X, making the comparison independent of the chosen
    Stinespring environment gauge.
    """
    n = len(accessible_order)
    logical = code.logical_qubits
    if code.qubit_order != accessible_order:
        raise ValueError("support/accessibility order mismatch")
    if not set(requested_output) <= set(accessible_order):
        raise ValueError("requested output is outside X")
    initial: list[stim.PauliString] = []
    for index in range(logical):
        x = ["_"] * (2 * n)
        x[index] = x[n + index] = "X"
        initial.append(stim.PauliString("+" + "".join(x)))
    for index in range(logical):
        z = ["_"] * (2 * n)
        z[index] = z[n + index] = "Z"
        initial.append(stim.PauliString("+" + "".join(z)))
    for index in range(logical, n):
        ref_z = ["_"] * (2 * n)
        ref_z[index] = "Z"
        initial.append(stim.PauliString("+" + "".join(ref_z)))
    for index in range(logical, n):
        input_z = ["_"] * (2 * n)
        input_z[n + index] = "Z"
        initial.append(stim.PauliString("+" + "".join(input_z)))
    if len(initial) != 2 * n:
        raise AssertionError("support purification is not a pure stabilizer state")
    preparation = stim.Tableau.from_stabilizers(initial).to_circuit()
    encoder = support_encoder(code)
    ref_mapping = tuple(range(n))
    input_mapping = tuple(range(n, 2 * n))
    for instruction in encoder.to_circuit():
        _append_mapped_instruction(
            preparation, instruction, ref_mapping, complex_conjugate=True
        )
    for instruction in encoder.to_circuit():
        _append_mapped_instruction(preparation, instruction, input_mapping)
    input_index = {wire: n + index for index, wire in enumerate(accessible_order)}
    for gate in circuit_gates:
        targets = [input_index[wire] for wire in gate.qubits]
        preparation.append(
            "CX" if gate.operation == "CNOT" else gate.operation, targets
        )
    tableau = stim.Tableau.from_circuit(preparation)
    generators = [tableau.z_output(index) for index in range(2 * n)]
    output_index = {wire: n + index for index, wire in enumerate(accessible_order)}
    keep = (*[output_index[wire] for wire in requested_output], *range(n))
    return signed_reduced_stabilizers(generators, tuple(keep))


def bell_target_generators(message_qubits: int) -> list[stim.PauliString]:
    result: list[stim.PauliString] = []
    width = 2 * message_qubits
    for index in range(message_qubits):
        x = ["_"] * width
        x[index] = x[message_qubits + index] = "X"
        result.append(stim.PauliString("+" + "".join(x)))
        z = ["_"] * width
        z[index] = z[message_qubits + index] = "Z"
        result.append(stim.PauliString("+" + "".join(z)))
    return result


def stabilizer_overlap_with_pure_target(
    reduced: list[stim.PauliString], target: list[stim.PauliString]
) -> float:
    """Exact overlap with a pure stabilizer target."""
    q = len(target)
    source_binary = [pauli_binary(item) for item in reduced]
    target_binary = [pauli_binary(item) for item in target]
    source_matrix = np.asarray(source_binary, dtype=np.uint8)
    if source_matrix.size == 0:
        source_matrix = np.zeros((0, 2 * q), dtype=np.uint8)
    target_matrix = np.asarray(target_binary, dtype=np.uint8)
    constraints = np.concatenate((source_matrix.T, target_matrix.T), axis=1)
    mapping = np.concatenate(
        (source_matrix.T, np.zeros((2 * q, len(target_binary)), dtype=np.uint8)),
        axis=1,
    )
    intersection = canonical_kernel_image_basis(
        constraints, len(source_binary) + len(target_binary), mapping
    )
    for coefficients, _ in intersection:
        left = stim.PauliString("+" + "_" * q)
        right = stim.PauliString("+" + "_" * q)
        for index, generator in enumerate(reduced):
            if coefficients[index]:
                left *= generator
        for index, generator in enumerate(target):
            if coefficients[len(reduced) + index]:
                right *= generator
        if left != right:
            return 0.0
    return 2.0 ** (len(intersection) - q)
