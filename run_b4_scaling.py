#!/usr/bin/env python3
"""Small, auditable B=4 scaling baseline for the signed Clifford Petz decoder.

This is intentionally not a proof of optimality and does not yet change |B|.
It separates logical synthesis, a fixed line router, and an ideal noise budget.
"""
from __future__ import annotations

import csv
from pathlib import Path
import subprocess
import sys

import numpy as np

from hayden_preskill_toy.channels import channel_at_time, petz_entanglement_fidelity
from hayden_preskill_toy.experiment import random_scrambler
from validate_petz_dilation_t2 import _candidate, validate


SEEDS = tuple(range(4000, 4020))
DEPTHS = (3, 6, 9)


def _causal_line_bound(gates, n: int) -> int:
    """Light-cone lower bound for output wire 0 on a nearest-neighbour line."""
    cone = {0}
    for gate in reversed(gates):
        if gate.name == 'CNOT' and (gate.a in cone or gate.b in cone):
            cone.update((gate.a, gate.b))
    return max(cone, default=0)


def _run_action(seed: int, depth: int) -> None:
    subprocess.run((sys.executable, 'petz_symplectic_action.py', '--seed', str(seed), '--layers', str(depth), '--t', '2'), check=True, stdout=subprocess.DEVNULL)


def run() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for depth in DEPTHS:
        for seed in SEEDS:
            scrambler = random_scrambler(np.random.default_rng(seed), depth)
            # t=1 is retained as an information-availability reference only.
            for t in (1, 2):
                petz, _ = petz_entanglement_fidelity(channel_at_time(scrambler, t))
                base = {'B_size': 4, 'seed': seed, 'scrambler_layers': depth, 'emission_time': t,
                        'petz_entanglement_fidelity': petz, 'noise_model': 'ideal', 'noise_depth': 0,
                        'synthesis_method': 'signed_symplectic_Clifford', 'claim': 'observed construction; not minimal'}
                if t != 2:
                    rows.append(base | {'geometry': 'not_compiled', 'architecture_diameter': '',
                                        'causal_line_lower_bound': '', 'logical_cnot_count': '',
                                        'logical_two_qubit_depth': '', 'mean_logical_interaction_distance': '', 'routing_swap_count': '',
                                        'routed_cnot_count': '', 'routed_two_qubit_depth': '',
                                        'final_entanglement_fidelity': '', 'status': 'Petz-only baseline; no circuit compiled'})
                    continue
                _run_action(seed, depth)
                try:
                    result = validate(seed, depth, t)
                    _, dilation, _, code, _, _ = _candidate(seed, depth, t)
                except ValueError as error:
                    rows.append(base | {'geometry': 'not_compiled', 'architecture_diameter': '',
                                        'causal_line_lower_bound': '', 'logical_cnot_count': '',
                                        'logical_two_qubit_depth': '', 'mean_logical_interaction_distance': '', 'routing_swap_count': '',
                                        'routed_cnot_count': '', 'routed_two_qubit_depth': '',
                                        'final_entanglement_fidelity': '',
                                        'status': f'symplectic completion obstruction: {error}'})
                    continue
                bound = _causal_line_bound(dilation, len(code['physical_qubits']))
                interactions = [abs(g.a - g.b) for g in dilation if g.name == 'CNOT']
                mean_distance = float(np.mean(interactions)) if interactions else 0.0
                rows.append(base | {'geometry': 'all_to_all_logical', 'architecture_diameter': 1,
                                    'causal_line_lower_bound': 0,
                                    'logical_cnot_count': result['clifford_cnot_count_before_routing'],
                                    'logical_two_qubit_depth': result['clifford_two_qubit_depth_before_routing'],
                                    'mean_logical_interaction_distance': mean_distance,
                                    'routing_swap_count': 0, 'routed_cnot_count': result['clifford_cnot_count_before_routing'],
                                    'routed_two_qubit_depth': result['clifford_two_qubit_depth_before_routing'],
                                    'final_entanglement_fidelity': result['synthesized_entanglement_fidelity'],
                                    'status': 'validated'})
                rows.append(base | {'geometry': 'line_E0-E1-E2-E3-D0-D1', 'architecture_diameter': 5,
                                    'causal_line_lower_bound': bound,
                                    'logical_cnot_count': result['clifford_cnot_count_before_routing'],
                                    'logical_two_qubit_depth': result['clifford_two_qubit_depth_before_routing'],
                                    'mean_logical_interaction_distance': mean_distance,
                                    'routing_swap_count': result['local_swap_count_after_routing'],
                                    'routed_cnot_count': result['local_cnot_count_after_routing'],
                                    'routed_two_qubit_depth': result['local_two_qubit_depth_after_routing'],
                                    'final_entanglement_fidelity': result['routed_entanglement_fidelity'],
                                    'status': 'validated'})
    return rows


def main() -> None:
    rows = run(); Path('results').mkdir(exist_ok=True)
    with Path('results/b4_scaling_baseline.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    print(f'wrote {len(rows)} rows to results/b4_scaling_baseline.csv')


if __name__ == '__main__':
    main()
