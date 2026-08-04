#!/usr/bin/env python3
"""Three-use symbolic ORELIA demonstration for the validated one-qubit model.

The base Hayden--Preskill channel remains strictly one qubit in -> one qubit
out.  A 3-bit letter is therefore sent through three independent, parallel
uses of that *unchanged* channel.  This is not a 3-qubit message injected into
one black-hole instance.
"""
from __future__ import annotations

import csv
from pathlib import Path
import numpy as np

from hayden_preskill_toy.channels import channel_at_time, petz_recovery
from hayden_preskill_toy.experiment import A, B, E, N_QUBITS, random_scrambler
from hayden_preskill_toy.simulator import Gate, X, apply_1q, apply_circuit
from hayden_preskill_toy.channels import environment_state
from validate_petz_dilation_t2 import _candidate, _route_line


SYMBOLS = {'O': '000', 'R': '001', 'E': '010', 'L': '011', 'I': '100', 'A': '101'}


def _output_kraus(decoder: list[Gate], scrambler: list[Gate]) -> tuple[np.ndarray, ...]:
    """Kraus operators A -> A'=E0 obtained from the actual Clifford circuit."""
    columns = []
    for bit in range(2):
        state = environment_state()
        if bit: state = apply_1q(state, X, A, N_QUBITS)
        state = apply_circuit(apply_circuit(state, scrambler, N_QUBITS), decoder, N_QUBITS)
        rest = tuple(q for q in range(N_QUBITS) if q != E[0])
        columns.append(np.transpose(state.reshape((2,) * N_QUBITS), (E[0], *rest)).reshape(2, -1))
    return tuple(np.stack((columns[0][:, j], columns[1][:, j]), axis=1) for j in range(columns[0].shape[1]))


def _apply_one_qubit_channel(rho: np.ndarray, kraus: tuple[np.ndarray, ...], qubit: int, n: int = 3) -> np.ndarray:
    left = np.eye(1 << qubit, dtype=complex); right = np.eye(1 << (n - qubit - 1), dtype=complex)
    return sum((np.kron(np.kron(left, k), right) @ rho @ np.kron(np.kron(left, k), right).conj().T for k in kraus), start=np.zeros_like(rho))


def _apply_three(rho: np.ndarray, kraus: tuple[np.ndarray, ...]) -> np.ndarray:
    for qubit in range(3): rho = _apply_one_qubit_channel(rho, kraus, qubit)
    return rho


def _ket(bits: str) -> np.ndarray:
    vector = np.zeros(8, complex); vector[int(bits, 2)] = 1; return vector


def _row(method: str, kind: str, label: str, ket: np.ndarray, kraus: tuple[np.ndarray, ...]) -> dict[str, object]:
    output = _apply_three(np.outer(ket, ket.conj()), kraus)
    fidelity = float(np.real(np.vdot(ket, output @ ket)))
    probabilities = np.real(np.diag(output)); index = int(np.argmax(probabilities))
    decoded = next((letter for letter, bits in SYMBOLS.items() if int(bits, 2) == index), f'non-symbol:{index:03b}')
    return {'method': method, 'kind': kind, 'input': label, 'decoded_symbol': decoded,
            'state_fidelity': fidelity, 'largest_readout_probability': float(probabilities[index]),
            'relative_phase_target': '', 'relative_phase_output': ''}


def run() -> list[dict[str, object]]:
    encode, dilation, physical, _, recovery, scrambler = _candidate()
    del encode
    abstract = tuple(r @ k for r in recovery for k in channel_at_time(scrambler, 2).kraus)
    routed_local, _ = _route_line(dilation, 6)
    wires = (*E, A, B[0])
    routed = [Gate(g.name, wires[g.a], None if g.b is None else wires[g.b]) for g in routed_local]
    channels = {
        'Petz abstract': abstract,
        'Clifford direct': _output_kraus(physical, scrambler),
        'Clifford routed chain': _output_kraus(routed, scrambler),
    }
    rows: list[dict[str, object]] = []
    for method, kraus in channels.items():
        for letter, bits in SYMBOLS.items(): rows.append(_row(method, 'basis_symbol', letter, _ket(bits), kraus))
        tests = {
            '(O+R)/sqrt(2)': (_ket('000') + _ket('001')) / np.sqrt(2),
            '(E+iL)/sqrt(2)': (_ket('010') + 1j * _ket('011')) / np.sqrt(2),
            'uniform_6_symbols': sum((_ket(bits) for bits in SYMBOLS.values()), start=np.zeros(8, complex)) / np.sqrt(6),
        }
        for label, vector in tests.items():
            row = _row(method, 'superposition', label, vector, kraus)
            output = _apply_three(np.outer(vector, vector.conj()), kraus)
            if label == '(O+R)/sqrt(2)':
                row['relative_phase_target'] = '0'; row['relative_phase_output'] = str(float(np.angle(output[0, 1])))
            elif label == '(E+iL)/sqrt(2)':
                row['relative_phase_target'] = '-pi/2'; row['relative_phase_output'] = str(float(np.angle(output[2, 3])))
            rows.append(row)
    return rows


def main() -> None:
    rows = run(); Path('results').mkdir(exist_ok=True)
    with Path('results/orelia_symbolic_results.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    for method in ('Petz abstract', 'Clifford direct', 'Clifford routed chain'):
        word = ''.join(next(r['decoded_symbol'] for r in rows if r['method'] == method and r['kind'] == 'basis_symbol' and r['input'] == letter) for letter in 'ORELIA')
        probability = float(np.prod([next(r['largest_readout_probability'] for r in rows if r['method'] == method and r['kind'] == 'basis_symbol' and r['input'] == letter) for letter in 'ORELIA']))
        print(f'{method}: input ORELIA -> output {word}; P(word)={probability:.15g}')


if __name__ == '__main__':
    main()
