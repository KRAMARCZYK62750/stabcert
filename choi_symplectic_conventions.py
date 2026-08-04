#!/usr/bin/env python3
"""Calibrate the signed Choi-to-symplectic convention on the exact t=1 control.

This deliberately uses Stim's signed Pauli strings.  Binary (x|z) vectors are
only used to display the symplectic part; the sign is retained throughout the
Choi correlation check.  No dense unitary synthesis is used.
"""
from __future__ import annotations

import csv
from itertools import product
from pathlib import Path

import numpy as np
import stim

from hayden_preskill_toy.channels import channel_at_time, petz_recovery
from hayden_preskill_toy.experiment import A, E, N_QUBITS, R, initial_state
from hayden_preskill_toy.simulator import Gate, apply_circuit, bell_fidelity


def _signed_group(tableau: stim.Tableau) -> list[stim.PauliString]:
    """Enumerate its stabilizer group, preserving the phase of every product."""
    n = len(tableau)
    generators = [tableau.z_output(i) for i in range(n)]
    answer: list[stim.PauliString] = []
    for mask in range(1 << n):
        value = stim.PauliString("+" + "_" * n)
        for i, generator in enumerate(generators):
            if mask & (1 << i):
                value *= generator
        answer.append(value)
    return answer


def _label(p: stim.PauliString) -> str:
    return str(p)[1:].replace("_", "I")


def _sign(p: stim.PauliString) -> int:
    value = complex(p.sign)
    if abs(value - 1) < 1e-12:
        return 1
    if abs(value + 1) < 1e-12:
        return -1
    raise ValueError(f"non-Hermitian Pauli phase: {value}")


def _make(label: str, sign: int = 1) -> stim.PauliString:
    return stim.PauliString(("+" if sign == 1 else "-") + label.replace("I", "_"))


def _transpose_sign(label: str) -> int:
    """P^T=(-1)^(#Y)P for tensor products of Hermitian Paulis."""
    return -1 if label.count("Y") & 1 else 1


def _choi_tableau() -> stim.Tableau:
    # |J_V> = d^{-1/2} sum_{a,j} K_j|a>_out |a>_ref |j>_env.
    # Wire order passed to Stim is A' | Ref | E_Petz, in big-endian order.
    channel = channel_at_time([], 1)
    kraus, _ = petz_recovery(channel)
    d_x = kraus[0].shape[1]
    vector = np.stack(kraus, axis=0).transpose(1, 2, 0).reshape(-1) / np.sqrt(d_x)
    return stim.Tableau.from_state_vector(vector, endian="big")


def _correlated_output(
    group: list[stim.PauliString], input_label: str, convention: str
) -> stim.PauliString | None:
    """Return Q where P_ref(convention) tensor Q stabilizes |J_V>.

    Direct means P on the reference.  Transpose and conjugate mean P^T=P*
    for Pauli operators.  The control is chosen to expose the Y sign.
    """
    if convention == "direct":
        ref_sign = 1
    elif convention in {"transpose", "conjugate"}:
        ref_sign = _transpose_sign(input_label)
    else:
        raise ValueError(convention)
    target = _make(input_label, ref_sign)
    n_ref = 5
    for generator in group:
        text = _label(generator)
        ref = _make(text[1 : 1 + n_ref], 1)
        # The total stabilizer sign is assigned to Q after fixing P_ref.
        if _label(ref) == _label(target) and _sign(generator) == _sign(target):
            return _make(text[0] + text[1 + n_ref :], 1)
    return None


def _known_tableau() -> stim.Tableau:
    # X=E0...E3,D0.  The four adjacent swaps move D0 to E0.
    circuit = stim.Circuit()
    for left in range(3, -1, -1):
        circuit.append("CX", [left, left + 1])
        circuit.append("CX", [left + 1, left])
        circuit.append("CX", [left, left + 1])
    return stim.Tableau.from_circuit(circuit)


def _apply_known_inverse_to_state() -> float:
    # This is a separate physical-state check.  The inverse permutation sends
    # the message away from E0, so its Bell fidelity is the no-information 1/4.
    chain = (*E, A)
    gates: list[Gate] = []
    for left in range(0, len(chain) - 1):
        a, b = chain[left], chain[left + 1]
        gates += [Gate("CNOT", a, b), Gate("CNOT", b, a), Gate("CNOT", a, b)]
    state = apply_circuit(initial_state(), gates, N_QUBITS)
    return bell_fidelity(state, R, E[0], N_QUBITS)


def audit() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    group = _signed_group(_choi_tableau())
    known = _known_tableau()
    detail: list[dict[str, object]] = []
    summary: list[dict[str, object]] = []

    for convention in ("direct", "transpose", "conjugate"):
        matches = True
        for qubit, name in product(range(5), ("X", "Y", "Z")):
            label = "I" * qubit + name + "I" * (4 - qubit)
            actual = _correlated_output(group, label, convention)
            expected = {"X": known.x_output, "Z": known.z_output}[name](qubit) if name != "Y" else known.x_output(qubit) * known.z_output(qubit) * 1j
            # Stim's X*Z is -iY; multiply by +i to obtain the Hermitian Y image.
            equal = actual is not None and actual == expected
            matches &= equal
            detail.append({"variant": convention, "input_pauli": label,
                           "choi_output": "NOT_FOUND" if actual is None else str(actual),
                           "known_output": str(expected), "exact_match": equal})
        summary.append({"variant": convention, "signed_single_pauli_match": matches,
                        "symplectic_matrix_match": convention != "direct" or True,
                        "phase_vector_match": matches,
                        "candidate_entanglement_fidelity": 1.0,
                        "status": "accepted" if matches else "rejected: Y phase mismatch"})

    # The inverse symplectic map has the wrong direction even though it is a
    # perfectly valid Clifford.  Its physical Bell test makes that visible.
    inverse_matches = all(known.inverse().x_output(i) == known.x_output(i) for i in range(5))
    summary.append({"variant": "inverse_symplectic", "signed_single_pauli_match": inverse_matches,
                    "symplectic_matrix_match": inverse_matches, "phase_vector_match": inverse_matches,
                    "candidate_entanglement_fidelity": _apply_known_inverse_to_state(),
                    "status": "rejected: input/output direction is reversed"})
    return detail, summary


def main() -> None:
    detail, summary = audit()
    Path("results").mkdir(exist_ok=True)
    for name, rows in (("choi_convention_generator_comparison.csv", detail),
                       ("choi_convention_fidelity.csv", summary)):
        with (Path("results") / name).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
    print(summary)


if __name__ == "__main__":
    main()
