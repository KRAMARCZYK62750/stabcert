#!/usr/bin/env python3
"""Isolated old/new worker for structural-compilation resource measurements."""
from __future__ import annotations

import argparse
import json
import platform
import resource
import time

import numpy as np

from hayden_preskill_toy.gf2 import count_operations
from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_certificate import (
    certify_routed_equivalence,
    structural_validation,
)
from hayden_preskill_toy.parametric_channels import channel_at_time, random_scrambler
from hayden_preskill_toy.parametric_petz import choi_tableau, support_rank
from hayden_preskill_toy.parametric_routing import route_line, two_qubit_depth
from hayden_preskill_toy.parametric_synthesis import (
    signed_dilation,
    signed_dilation_exhaustive,
)
from hayden_preskill_toy.parametric_stabilizer import input_support_code
from hayden_preskill_toy.parametric_validation import validate


CASES = {1: 2, 2: 3, 3: 3, 4: 5}


def _rss_mib() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    byte_value = value if platform.system() == "Darwin" else value * 1024
    return float(byte_value / 2**20)


def _gate_signature(gates) -> str:
    return ";".join(
        f"{gate.name}:{gate.a}" + ("" if gate.b is None else f":{gate.b}")
        for gate in gates
    )


def _row_signature(rows) -> str:
    return ";".join(
        "|".join(
            str(row[key])
            for key in ("logical_pauli", "input", "reference_transpose", "output")
        )
        for row in rows
    )


def run(mode: str, message_qubits: int):
    t = CASES[message_qubits]
    layout = SystemLayout(n_message=message_qubits, n_black_hole=4)
    scrambler = random_scrambler(
        layout, np.random.default_rng(20260802), 6
    )
    channel = channel_at_time(layout, scrambler, t)
    baseline_rss = _rss_mib()
    started = time.perf_counter()
    if mode == "old":
        gates, encoder, output, rows = signed_dilation_exhaustive(
            layout, channel, scrambler, t
        )
        routed = route_line(layout, t, gates)
        direct_metrics = validate(
            layout,
            channel,
            scrambler,
            t,
            physical_gates_override=gates,
        )
        routed_metrics = validate(
            layout,
            channel,
            scrambler,
            t,
            physical_gates_override=routed.gates,
        )
        certificate = {
            "certified": False,
            "target_generator_count": 0,
            "reduced_choi_equal": False,
        }
        choi_fidelity = direct_metrics["choi_fidelity"]
        operator_error = direct_metrics["operator_error"]
        gf2_stats = None
    elif mode == "new":
        with count_operations() as gf2_stats:
            gates, encoder, output, rows = signed_dilation(
                layout, channel, scrambler, t
            )
            routed = route_line(layout, t, gates)
            direct_metrics = structural_validation(
                layout, channel, scrambler, t, gates, encoder, output, rows
            )
            routed_metrics = structural_validation(
                layout, channel, scrambler, t, routed.gates, encoder, output, rows
            )
            certificate = direct_metrics
            if not certify_routed_equivalence(layout, t, gates, routed.gates):
                raise AssertionError("routed Clifford differs from direct Clifford")
            choi_fidelity = direct_metrics["choi_fidelity_certified"]
            operator_error = 0.0 if direct_metrics["reduced_choi_equal"] else 1.0
    else:
        raise ValueError(mode)
    elapsed = time.perf_counter() - started
    chain = layout.chain(t)
    local = {wire: index for index, wire in enumerate(chain)}
    local_gates = [
        type(gate)(
            gate.name,
            local[gate.a],
            None if gate.b is None else local[gate.b],
        )
        for gate in gates
    ]
    support = support_rank(channel)
    choi_qubits = len(choi_tableau(channel))
    structural_code = input_support_code(layout, scrambler, t)
    first_row = rows[0]
    return {
        "mode": mode,
        "A": message_qubits,
        "t": t,
        "petz_fidelity": direct_metrics["petz_fidelity"],
        "direct_circuit_fidelity": direct_metrics["circuit_fidelity"],
        "routed_circuit_fidelity": routed_metrics["circuit_fidelity"],
        "choi_fidelity": choi_fidelity,
        "operator_error_or_certificate_error": operator_error,
        "logical_depth": two_qubit_depth(local_gates, len(chain)),
        "logical_cnot": sum(gate.name == "CNOT" for gate in gates),
        "routed_depth": routed.two_qubit_depth,
        "routed_cnot": routed.cnot_count,
        "swap": routed.swap_count,
        "final_order": ";".join(map(str, routed.final_wire_at_site)),
        "encoder_tableau": str(encoder),
        "output_tableau": str(output),
        "signed_rows": _row_signature(rows),
        "gate_signature": _gate_signature(gates),
        "support_rank": support,
        "old_group_size_theoretical": 1 << choi_qubits,
        "old_operator_checks_theoretical": support**2,
        "generators_checked": certificate["target_generator_count"],
        "support_kernel_variables": structural_code.get("gf2_kernel_variables", 0),
        "support_kernel_constraints": structural_code.get("gf2_kernel_constraints", 0),
        "support_kernel_constraint_rank": structural_code.get(
            "gf2_kernel_constraint_rank", 0
        ),
        "support_kernel_dimension": structural_code.get("gf2_kernel_dimension", 0),
        "support_stabilizer_rank": structural_code["independent_stabilizers"],
        "centralizer_dimension": structural_code.get("gf2_centralizer_dimension", 0),
        "logical_quotient_dimension": structural_code.get(
            "gf2_logical_quotient_dimension", 0
        ),
        "choi_affine_variables": first_row.get("gf2_variables", 0),
        "choi_affine_constraints": first_row.get("gf2_constraints", 0),
        "choi_affine_constraint_rank": first_row.get("gf2_constraint_rank", 0),
        "choi_affine_kernel_dimension": first_row.get(
            "gf2_affine_kernel_dimension", 0
        ),
        "gf2_affine_systems_solved": 0
        if gf2_stats is None
        else gf2_stats.affine_systems_solved,
        "gf2_rank_reductions": 0 if gf2_stats is None else gf2_stats.rank_reductions,
        "gf2_pivots": 0 if gf2_stats is None else gf2_stats.pivots,
        "gf2_row_xors": 0 if gf2_stats is None else gf2_stats.row_xors,
        "gf2_scalar_bit_xors": 0
        if gf2_stats is None
        else gf2_stats.scalar_bit_xors,
        "certificate_pass": certificate["certified"],
        "reduced_choi_equal": certificate["reduced_choi_equal"],
        "elapsed_seconds": elapsed,
        "baseline_rss_mib": baseline_rss,
        "peak_rss_mib": _rss_mib(),
        "rss_increment_mib": max(0.0, _rss_mib() - baseline_rss),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("old", "new"), required=True)
    parser.add_argument("--message-qubits", type=int, choices=tuple(CASES), required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.mode, arguments.message_qubits)))


if __name__ == "__main__":
    main()
