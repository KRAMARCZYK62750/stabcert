#!/usr/bin/env python3
"""Isolated dense-vs-stabilizer entanglement-validation worker."""
from __future__ import annotations

import argparse
import json
import platform
import resource
import time

import numpy as np

from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_certificate import structural_validation
from hayden_preskill_toy.parametric_channels import (
    channel_at_time_compact,
    random_scrambler,
)
from hayden_preskill_toy.parametric_petz import entanglement_fidelity
from hayden_preskill_toy.parametric_routing import route_line
from hayden_preskill_toy.parametric_synthesis import signed_dilation
from hayden_preskill_toy.simulator import apply_circuit, bell_pair, zero_state


CASES = {1: 2, 2: 3, 3: 3, 4: 5, 5: 5, 6: 8}


def _rss_mib() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    byte_value = value if platform.system() == "Darwin" else value * 1024
    return float(byte_value / 2**20)


def _dense_bell_fidelity(layout, scrambler, gates, t: int) -> float:
    state = zero_state(layout.n_qubits)
    for left, right in (
        *zip(layout.R_register, layout.A_register),
        *zip(layout.B, layout.E),
    ):
        state = bell_pair(state, left, right, layout.n_qubits)
    state = apply_circuit(state, scrambler, layout.n_qubits)
    state = apply_circuit(state, list(gates), layout.n_qubits)
    keep = (*layout.R_register, *layout.X(t)[: layout.n_message])
    rest = tuple(qubit for qubit in range(layout.n_qubits) if qubit not in keep)
    factor = np.transpose(
        state.reshape((2,) * layout.n_qubits), (*keep, *rest)
    ).reshape(2 ** len(keep), -1)
    dimension = 1 << layout.n_message
    bell = np.zeros(dimension * dimension, dtype=complex)
    for index in range(dimension):
        bell[index * dimension + index] = 1 / np.sqrt(dimension)
    return float(np.real(np.vdot(bell, factor @ factor.conj().T @ bell)))


def run(mode: str, message_qubits: int) -> dict[str, object]:
    t = CASES[message_qubits]
    layout = SystemLayout(n_message=message_qubits, n_black_hole=4)
    scrambler = random_scrambler(
        layout, np.random.default_rng(20260802), 6
    )
    channel = channel_at_time_compact(layout, scrambler, t)
    gates, encoder, output, rows = signed_dilation(
        layout, channel, scrambler, t
    )
    routed = route_line(layout, t, gates)
    baseline_rss = _rss_mib()
    started = time.perf_counter()
    if mode == "dense":
        petz_fidelity, _ = entanglement_fidelity(channel)
        direct_fidelity = _dense_bell_fidelity(layout, scrambler, gates, t)
        routed_fidelity = _dense_bell_fidelity(layout, scrambler, routed.gates, t)
        direct_validated = abs(direct_fidelity - petz_fidelity) < 1e-12
        routed_validated = abs(routed_fidelity - petz_fidelity) < 1e-12
        reduced_choi_equal = None
        signed_phases_validated = None
        dense_state_amplitudes = 2 * (1 << layout.n_qubits)
        dense_reduced_entries = 2 * (1 << (4 * layout.n_message))
        intersection_rank = None
    elif mode == "structural":
        direct = structural_validation(
            layout, channel, scrambler, t, gates, encoder, output, rows
        )
        routed_metrics = structural_validation(
            layout, channel, scrambler, t, routed.gates, encoder, output, rows
        )
        petz_fidelity = float(direct["petz_fidelity"])
        direct_fidelity = float(direct["circuit_fidelity"])
        routed_fidelity = float(routed_metrics["circuit_fidelity"])
        direct_validated = bool(direct["validated"])
        routed_validated = bool(routed_metrics["validated"])
        reduced_choi_equal = bool(direct["reduced_choi_equal"])
        signed_phases_validated = bool(
            direct["entanglement_phases_match_on_intersection"]
        )
        dense_state_amplitudes = int(
            direct["entanglement_dense_state_amplitudes_constructed"]
        )
        dense_reduced_entries = int(
            direct["entanglement_dense_reduced_matrices_constructed"]
        )
        intersection_rank = int(direct["entanglement_intersection_rank"])
    else:
        raise ValueError(mode)
    elapsed = time.perf_counter() - started
    peak_rss = _rss_mib()
    return {
        "mode": mode,
        "A": message_qubits,
        "t": t,
        "petz_fidelity": petz_fidelity,
        "direct_fidelity": direct_fidelity,
        "routed_fidelity": routed_fidelity,
        "direct_validated": direct_validated,
        "routed_validated": routed_validated,
        "reduced_choi_equal": reduced_choi_equal,
        "signed_phases_validated": signed_phases_validated,
        "intersection_rank": intersection_rank,
        "dense_state_amplitudes_constructed": dense_state_amplitudes,
        "dense_reduced_matrix_entries_constructed": dense_reduced_entries,
        "validation_seconds": elapsed,
        "baseline_rss_mib": baseline_rss,
        "peak_rss_mib": peak_rss,
        "validation_rss_increment_mib": max(0.0, peak_rss - baseline_rss),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("dense", "structural"), required=True)
    parser.add_argument("--message-qubits", type=int, choices=tuple(CASES), required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.mode, arguments.message_qubits)))


if __name__ == "__main__":
    main()
