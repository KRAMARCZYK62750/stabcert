#!/usr/bin/env python3
"""Isolated dense-oracle vs fully structural Petz-chain worker."""
from __future__ import annotations

import argparse
import json
import platform
import resource
import time

import numpy as np
import stim

from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_certificate import (
    canonical_signed_stabilizer_signature,
    structural_validation,
)
from hayden_preskill_toy.parametric_channels import (
    channel_at_time_compact,
    random_scrambler,
)
from hayden_preskill_toy.parametric_petz import choi_tableau, entanglement_fidelity
from hayden_preskill_toy.parametric_petz_stabilizer import stabilizer_channel_at_time
from hayden_preskill_toy.parametric_routing import route_line, two_qubit_depth
from hayden_preskill_toy.parametric_stabilizer import input_support_code
from hayden_preskill_toy.parametric_synthesis import signed_dilation


CASES = {1: 2, 2: 3, 3: 3, 4: 5, 5: 5, 6: 8, 7: 8}


def _rss_mib() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    byte_value = value if platform.system() == "Darwin" else value * 1024
    return float(byte_value / 2**20)


def _gate_signature(gates) -> str:
    return ";".join(
        f"{gate.name}:{gate.a}" + ("" if gate.b is None else f":{gate.b}")
        for gate in gates
    )


def _support_signature(labels) -> tuple[str, ...]:
    return canonical_signed_stabilizer_signature(
        [stim.PauliString(label.replace("I", "_")) for label in labels]
    )


def run(mode: str, message_qubits: int) -> dict[str, object]:
    t = CASES[message_qubits]
    layout = SystemLayout(n_message=message_qubits, n_black_hole=4)
    scrambler = random_scrambler(
        layout, np.random.default_rng(20260802), 6
    )
    baseline_rss = _rss_mib()
    started = time.perf_counter()
    if mode == "dense":
        channel = channel_at_time_compact(layout, scrambler, t)
        petz_fidelity, petz_info = entanglement_fidelity(channel)
        tableau = choi_tableau(channel)
        support_rank = int(petz_info["support_dimension"])
        dense_channel_constructed = True
        dense_tau_factor_constructed = True
        dense_choi_vector_constructed = True
    elif mode == "structural":
        channel = stabilizer_channel_at_time(layout, scrambler, t)
        petz_fidelity = channel.petz_entanglement_fidelity
        tableau = channel.petz_choi_tableau
        support_rank = channel.tau_support.rank
        dense_channel_constructed = False
        dense_tau_factor_constructed = False
        dense_choi_vector_constructed = False
    else:
        raise ValueError(mode)
    gates, encoder, output, rows = signed_dilation(layout, channel, scrambler, t)
    routed = route_line(layout, t, gates)
    direct = structural_validation(
        layout, channel, scrambler, t, gates, encoder, output, rows
    )
    routed_metrics = structural_validation(
        layout, channel, scrambler, t, routed.gates, encoder, output, rows
    )
    code = input_support_code(layout, scrambler, t)
    elapsed = time.perf_counter() - started
    peak_rss = _rss_mib()
    choi_signature = canonical_signed_stabilizer_signature(
        [tableau.z_output(index) for index in range(len(tableau))]
    )
    return {
        "mode": mode,
        "A": message_qubits,
        "t": t,
        "output": ";".join(map(str, channel.output)),
        "complement": ";".join(map(str, channel.complement)),
        "support_rank": support_rank,
        "support_logical_qubits": code["logical_qubits"],
        "support_signed_signature": "|".join(
            _support_signature(code["signed_stabilizer_labels"])
        ),
        "choi_qubits": len(tableau),
        "choi_signed_signature": "|".join(choi_signature),
        "petz_fidelity": petz_fidelity,
        "direct_fidelity": direct["circuit_fidelity"],
        "routed_fidelity": routed_metrics["circuit_fidelity"],
        "reduced_choi_equal": direct["reduced_choi_equal"],
        "signed_phases_validated": direct[
            "entanglement_phases_match_on_intersection"
        ],
        "encoder_tableau": str(encoder),
        "output_tableau": str(output),
        "gate_signature": _gate_signature(gates),
        "logical_depth": two_qubit_depth(gates, layout.n_qubits),
        "logical_cnot": sum(gate.name == "CNOT" for gate in gates),
        "routed_depth": routed.two_qubit_depth,
        "routed_cnot": routed.cnot_count,
        "swap": routed.swap_count,
        "final_order": ";".join(map(str, routed.final_wire_at_site)),
        "environment_qubits": len(output) - int(code["logical_qubits"]),
        "dense_channel_constructed": dense_channel_constructed,
        "dense_tau_factor_constructed": dense_tau_factor_constructed,
        "dense_choi_vector_constructed": dense_choi_vector_constructed,
        "elapsed_seconds": elapsed,
        "baseline_rss_mib": baseline_rss,
        "peak_rss_mib": peak_rss,
        "rss_increment_mib": max(0.0, peak_rss - baseline_rss),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("dense", "structural"), required=True)
    parser.add_argument("--message-qubits", type=int, choices=tuple(CASES), required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.mode, arguments.message_qubits)))


if __name__ == "__main__":
    main()
