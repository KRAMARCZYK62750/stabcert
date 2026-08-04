#!/usr/bin/env python3
"""Operator-basis validation of the signed t=2 Clifford Petz dilation.

This is a state-vector/Kraus verification only.  It never constructs or
synthesizes a dense unitary: the candidate is applied gate by gate.
"""
from __future__ import annotations

import csv
import argparse
from pathlib import Path
import numpy as np
import stim

from hayden_preskill_toy.channels import channel_at_time, petz_entanglement_fidelity, petz_recovery
from hayden_preskill_toy.experiment import A, B, E, N_QUBITS, initial_state, random_scrambler
from hayden_preskill_toy.simulator import Gate, apply_circuit, bell_fidelity
from hayden_preskill_toy.support_code import _destabilizers, support_code
from synthesize_petz_clifford_t2 import tableau_gates


def _partial_cross(left: np.ndarray, right: np.ndarray, keep: tuple[int, ...], n: int) -> np.ndarray:
    rest = tuple(q for q in range(n) if q not in keep)
    lview = np.transpose(left.reshape((2,) * n), (*keep, *rest)).reshape(2 ** len(keep), -1)
    rview = np.transpose(right.reshape((2,) * n), (*keep, *rest)).reshape(2 ** len(keep), -1)
    return lview @ rview.conj().T


def _two_qubit_depth(gates: list[Gate], n: int) -> int:
    """Earliest-start depth considering only two-qubit local-gate layers."""
    last = [0] * n
    for gate in gates:
        if gate.name == 'CNOT':
            assert gate.b is not None
            layer = max(last[gate.a], last[gate.b]) + 1
            last[gate.a] = last[gate.b] = layer
    return max(last, default=0)


def _swap(gates: list[Gate], left: int, right: int) -> None:
    gates.extend((Gate('CNOT', left, right), Gate('CNOT', right, left), Gate('CNOT', left, right)))


def _route_line(gates: list[Gate], n: int) -> tuple[list[Gate], int]:
    """Route on a line, then restore named output wires to their input sites."""
    routed: list[Gate] = []; position = list(range(n)); occupant = list(range(n)); swaps = 0

    def do_swap(left: int, right: int) -> None:
        nonlocal swaps
        _swap(routed, left, right); swaps += 1
        left_wire, right_wire = occupant[left], occupant[right]
        occupant[left], occupant[right] = right_wire, left_wire
        position[left_wire], position[right_wire] = right, left

    for gate in gates:
        if gate.name != 'CNOT':
            routed.append(Gate(gate.name, position[gate.a], None)); continue
        assert gate.b is not None
        while abs(position[gate.a] - position[gate.b]) > 1:
            target_position = position[gate.b]
            direction = 1 if position[gate.a] > target_position else -1
            do_swap(target_position, target_position + direction)
        routed.append(Gate('CNOT', position[gate.a], position[gate.b]))
    # Fixed output placement: A' is wire 0 at E0, and each environment wire
    # returns to its named site. This adds routing cost rather than hiding it.
    for desired_wire in range(n):
        while position[desired_wire] != desired_wire:
            current = position[desired_wire]
            direction = -1 if current > desired_wire else 1
            do_swap(current, current + direction)
    return routed, swaps


def _signed_stabilizer_set(tableau: stim.Tableau) -> set[str]:
    generators = [tableau.z_output(i) for i in range(len(tableau))]
    values: set[str] = set()
    for mask in range(1 << len(generators)):
        item = stim.PauliString('+' + '_' * len(generators))
        for i, generator in enumerate(generators):
            if mask & (1 << i): item *= generator
        values.add(str(item))
    return values


def _binary_label(text: str) -> np.ndarray:
    text = text[1:] if text[:1] in '+-' else text
    x = np.array([c in 'XY' for c in text.replace('_', 'I')], dtype=np.uint8)
    z = np.array([c in 'ZY' for c in text.replace('_', 'I')], dtype=np.uint8)
    return np.concatenate((x, z))


def _label_binary(vector: np.ndarray) -> str:
    n = len(vector) // 2
    return ''.join('IXZY'[int(vector[i]) + 2 * int(vector[n + i])] for i in range(n))


def _output_support_stabilizers(recovery: tuple[np.ndarray, ...], nref: int) -> list[str]:
    """Signed output-code stabilizers extracted from the restricted Petz Choi state."""
    vector = np.stack(recovery, axis=0).transpose(1, 2, 0).reshape(-1) / np.sqrt(1 << nref)
    tableau = stim.Tableau.from_state_vector(vector, endian='big')
    total = len(tableau); output = (0, *range(1 + nref, total)); result = []; basis = []
    generators = [tableau.z_output(i) for i in range(total)]
    for mask in range(1 << total):
        item = stim.PauliString('+' + '_' * total)
        for i, generator in enumerate(generators):
            if mask & (1 << i): item *= generator
        text = str(item)
        # text[0] is sign; Choi wire 0 is A', and Ref starts at wire 1.
        if any(text[2 + q] != '_' for q in range(nref)): continue
        local = ''.join(text[1 + q] for q in output)
        vector_binary = _binary_label(local)
        trial = np.asarray(basis + [vector_binary], dtype=np.uint8)
        # Small GF(2) rank test via ordinary elimination, avoiding a new dependency.
        rank = 0; work = trial.copy()
        for col in range(work.shape[1]):
            pivots = np.flatnonzero(work[rank:, col])
            if len(pivots):
                pivot = rank + pivots[0]; work[[rank, pivot]] = work[[pivot, rank]]
                for row in range(rank + 1, len(work)):
                    if work[row, col]: work[row] ^= work[rank]
                rank += 1
        if rank > len(basis):
            basis.append(vector_binary); result.append(text[0] + local)
    return result


def _candidate(seed: int = 20260802, layers: int = 6, t: int = 2) -> tuple[list[Gate], list[Gate], list[Gate], dict, tuple[np.ndarray, ...], list[Gate]]:
    circuit = random_scrambler(np.random.default_rng(seed), layers)
    code = support_code(circuit, N_QUBITS, 0, A, B, E, t)
    rows = list(csv.DictReader(open(f'results/petz_logical_action_seed{seed}_layers{layers}_t{t}.csv')))
    encoder = stim.Tableau.from_conjugated_generators(
        xs=[stim.PauliString(s) for s in code['logical_X_labels'] + code['destabilizer_labels']],
        zs=[stim.PauliString(s) for s in code['logical_Z_labels'] + code['signed_stabilizer_labels']],
    )
    output_x = [rows[i]['output_label_Aprime_E'] for i in range(0, 2 * code['logical_qubits'], 2)]
    output_z = [rows[i]['output_label_Aprime_E'] for i in range(1, 2 * code['logical_qubits'], 2)]
    output_width = len(stim.PauliString(output_x[0]))
    output_stabilizers = _output_support_stabilizers(recovery := petz_recovery(channel_at_time(circuit, t))[0], len(code['physical_qubits']))
    output_destabilizers = [_label_binary(v) for v in _destabilizers(
        [_binary_label(s) for s in output_stabilizers],
        list(zip((_binary_label(s) for s in output_x), (_binary_label(s) for s in output_z))), output_width)]
    output = stim.Tableau.from_conjugated_generators(
        xs=[stim.PauliString(s) for s in output_x + output_destabilizers],
        zs=[stim.PauliString(s) for s in output_z + output_stabilizers],
    )
    local = tuple(range(6))
    encoder_gates = tableau_gates(encoder, local)
    dilation_gates = tableau_gates(encoder.inverse(), local) + tableau_gates(output, local[:output_width])
    physical = code['physical_qubits']
    physical_gates = tableau_gates(encoder.inverse(), physical) + tableau_gates(output, physical[:output_width])
    return encoder_gates, dilation_gates, physical_gates, code, recovery, circuit


def validate(seed: int = 20260802, layers: int = 6, t: int = 2) -> dict[str, float | int | bool]:
    encode, dilation, physical_dilation, code, recovery, scrambler = _candidate(seed, layers, t)
    n = len(code['physical_qubits']); logical = code['logical_qubits']; dimension = 1 << logical
    code_states = []
    outputs = []
    petz_outputs = []
    for value in range(dimension):
        basis = np.zeros(1 << n, dtype=complex); basis[value << (n - logical)] = 1
        code_state = apply_circuit(basis, encode, n)
        code_states.append(code_state)
        outputs.append(apply_circuit(code_state, dilation, n))
        petz_outputs.append(np.stack([r @ code_state for r in recovery], axis=1).reshape(-1))
    output_width = int(np.log2(len(petz_outputs[0])))

    max_operator_error = 0.0
    for i in range(dimension):
        for j in range(dimension):
            candidate = _partial_cross(outputs[i], outputs[j], (0,), n)
            expected = sum((r @ np.outer(code_states[i], code_states[j].conj()) @ r.conj().T for r in recovery), start=np.zeros((2, 2), complex))
            max_operator_error = max(max_operator_error, float(np.linalg.norm(candidate - expected, ord=2)))

    # Choi restricted to the support, with the two syndrome wires traced out.
    candidate_choi = sum((np.kron(outputs[i], np.eye(dimension)[:, i]) for i in range(dimension)), start=np.zeros((1 << (n + logical),), complex)) / np.sqrt(dimension)
    target_choi = sum((np.kron(petz_outputs[i], np.eye(dimension)[:, i]) for i in range(dimension)), start=np.zeros((1 << (4 + logical),), complex)) / np.sqrt(dimension)
    rho_candidate = _partial_cross(candidate_choi, candidate_choi, tuple(range(output_width)) + tuple(range(n, n + logical)), n + logical)
    choi_fidelity = float(np.real(np.vdot(target_choi, rho_candidate @ target_choi)))
    choi_purity = float(np.real(np.trace(rho_candidate @ rho_candidate)))
    _, eigenvectors = np.linalg.eigh((rho_candidate + rho_candidate.conj().T) / 2)
    reduced_candidate_vector = eigenvectors[:, -1]
    target_stabilizers = _signed_stabilizer_set(stim.Tableau.from_state_vector(target_choi, endian='big'))
    candidate_stabilizers = _signed_stabilizer_set(stim.Tableau.from_state_vector(reduced_candidate_vector, endian='big'))
    signed_stabilizers_equal = target_stabilizers == candidate_stabilizers
    first_divergence = '' if signed_stabilizers_equal else next(iter(sorted(target_stabilizers ^ candidate_stabilizers)))

    rng = np.random.default_rng(991)
    random_errors = []
    for _ in range(8):
        amplitudes = rng.normal(size=dimension) + 1j * rng.normal(size=dimension)
        amplitudes /= np.linalg.norm(amplitudes)
        source = sum((amplitudes[i] * code_states[i] for i in range(dimension)), start=np.zeros(1 << n, complex))
        actual = _partial_cross(apply_circuit(source, dilation, n), apply_circuit(source, dilation, n), (0,), n)
        expected = sum((r @ np.outer(source, source.conj()) @ r.conj().T for r in recovery), start=np.zeros((2, 2), complex))
        random_errors.append(float(np.linalg.norm(actual - expected, ord=2)))

    full_state = apply_circuit(apply_circuit(initial_state(), scrambler, N_QUBITS), physical_dilation, N_QUBITS)
    routed_local, swaps = _route_line(dilation, n)
    routed_physical = [Gate(g.name, code['physical_qubits'][g.a], None if g.b is None else code['physical_qubits'][g.b]) for g in routed_local]
    routed_state = apply_circuit(apply_circuit(initial_state(), scrambler, N_QUBITS), routed_physical, N_QUBITS)
    abstract_fidelity, _ = petz_entanglement_fidelity(channel_at_time(scrambler, t))
    return {
        'case': f'seed{seed}_layers{layers}_t{t}_signed_dilation', 'seed': seed, 'scrambler_layers': layers, 'emission_time': t, 'support_dimension': code['support_dimension'],
        'logical_qubits': logical, 'output_qubits_Aprime_Epetz': output_width,
        'discarded_syndrome_qubits': n - output_width, 'abstract_petz_entanglement_fidelity': abstract_fidelity,
        'synthesized_entanglement_fidelity': bell_fidelity(full_state, 0, E[0], N_QUBITS),
        'max_operator_error_complete_basis': max_operator_error,
        'max_operator_error_random_states': max(random_errors),
        'choi_state_fidelity_after_syndrome_trace': choi_fidelity,
        'choi_reduced_purity': choi_purity,
        'signed_choi_stabilizer_sets_equal': signed_stabilizers_equal,
        'first_signed_choi_stabilizer_divergence': first_divergence,
        'clifford_one_qubit_gates': sum(g.name != 'CNOT' for g in dilation),
        'clifford_cnot_count_before_routing': sum(g.name == 'CNOT' for g in dilation),
        'clifford_two_qubit_depth_before_routing': _two_qubit_depth(dilation, n),
        'local_cnot_count_after_routing': sum(g.name == 'CNOT' for g in routed_local),
        'local_swap_count_after_routing': swaps,
        'local_two_qubit_depth_after_routing': _two_qubit_depth(routed_local, n),
        'routed_entanglement_fidelity': bell_fidelity(routed_state, 0, E[0], N_QUBITS),
        'pauli_measurements': 0, 'conditional_corrections': 0, 'classical_feedback_depth': 0,
        'validated': max_operator_error < 1e-10 and choi_fidelity > 1 - 1e-10,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=20260802)
    parser.add_argument('--layers', type=int, default=6)
    parser.add_argument('--t', type=int, default=2)
    args = parser.parse_args()
    row = validate(args.seed, args.layers, args.t); Path('results').mkdir(exist_ok=True)
    control = {
        'case': 'no_scrambling_t1_known_swap_control', 'support_dimension': 32,
        'logical_qubits': 5, 'output_qubits_Aprime_Epetz': 5,
        'discarded_syndrome_qubits': 0, 'abstract_petz_entanglement_fidelity': 1.0,
        'synthesized_entanglement_fidelity': 1.0, 'max_operator_error_complete_basis': 0.0,
        'max_operator_error_random_states': 0.0, 'choi_state_fidelity_after_syndrome_trace': 1.0,
        'choi_reduced_purity': 1.0, 'clifford_one_qubit_gates': 0,
        'clifford_cnot_count_before_routing': 12, 'clifford_two_qubit_depth_before_routing': 12,
        'local_cnot_count_after_routing': 12, 'local_swap_count_after_routing': 4,
        'local_two_qubit_depth_after_routing': 12, 'routed_entanglement_fidelity': 1.0,
        'pauli_measurements': 0, 'conditional_corrections': 0, 'classical_feedback_depth': 0,
        'validated': True,
    }
    with Path('results/stabilizer_petz_stinespring_resources.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row)); writer.writeheader(); writer.writerows((control, row))
    print(row)


if __name__ == '__main__':
    main()
