#!/usr/bin/env python3
"""Run the complete 60-case B=4 routing regression."""
from __future__ import annotations

import ast
import csv
from pathlib import Path
import numpy as np

from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_channels import channel_at_time, random_scrambler
from hayden_preskill_toy.parametric_routing import route_line
from hayden_preskill_toy.parametric_synthesis import signed_dilation
from hayden_preskill_toy.parametric_validation import validate as parametric_validate
from validate_petz_dilation_t2 import validate as legacy_validate


TOLERANCE = 1e-12
SEEDS = tuple(range(4000, 4020))
DEPTHS = (3, 6, 9)


def assert_parametric_routing_is_independent() -> None:
    paths = (
        Path('hayden_preskill_toy/parametric_routing.py'),
        Path('hayden_preskill_toy/parametric_synthesis.py'),
        Path('hayden_preskill_toy/parametric_validation.py'),
    )
    for path in paths:
        source = path.read_text()
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import): imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom): imports.append(node.module or '')
        assert 'csv' not in imports, f'{path} imports csv'
        assert not any(name.endswith('experiment') for name in imports), f'{path} imports experiment'
        assert 'N_QUBITS' not in source and 'SCRAMBLED' not in source


def build_rows() -> list[dict[str, object]]:
    assert_parametric_routing_is_independent()
    layout = SystemLayout(n_black_hole=4)
    parametric = []
    for depth in DEPTHS:
        for seed in SEEDS:
            circuit = random_scrambler(layout, np.random.default_rng(seed), depth)
            channel = channel_at_time(layout, circuit, 2)
            logical_gates, _, _, _ = signed_dilation(layout, channel, circuit, 2)
            routed = route_line(layout, 2, logical_gates)
            metrics = parametric_validate(
                layout, channel, circuit, 2, physical_gates_override=routed.gates
            )
            parametric.append((seed, depth, routed, metrics))

    # Historical execution is deliberately delayed until all parametric
    # metrics are complete. It is an oracle, never an input to construction.
    rows = []
    for seed, depth, routed, metrics in parametric:
        old = legacy_validate(seed, depth, 2)
        chain = layout.chain(2)
        row = {
            'case_id': f'B4_seed{seed}_depth{depth}_t2',
            'B': 4,
            't': 2,
            'seed': seed,
            'scramble_depth': depth,
            'routed_fidelity_old': old['routed_entanglement_fidelity'],
            'routed_fidelity_new': metrics['circuit_fidelity'],
            'operator_error_old': old['max_operator_error_complete_basis'],
            'operator_error_new': metrics['operator_error'],
            'local_depth_old': old['local_two_qubit_depth_after_routing'],
            'local_depth_new': routed.two_qubit_depth,
            'routed_cnot_old': old['local_cnot_count_after_routing'],
            'routed_cnot_new': routed.cnot_count,
            'swap_old': old['local_swap_count_after_routing'],
            'swap_new': routed.swap_count,
            'final_order_old': ';'.join(map(str, chain)),
            'final_order_new': ';'.join(map(str, routed.final_wire_at_site)),
        }
        discrete = (
            row['local_depth_old'] == row['local_depth_new']
            and row['routed_cnot_old'] == row['routed_cnot_new']
            and row['swap_old'] == row['swap_new']
            and row['final_order_old'] == row['final_order_new']
        )
        numeric = (
            abs(row['routed_fidelity_old'] - row['routed_fidelity_new']) < TOLERANCE
            and abs(row['operator_error_old'] - row['operator_error_new']) < TOLERANCE
            and row['operator_error_new'] < TOLERANCE
        )
        row['regression_pass'] = bool(discrete and numeric and metrics['validated'])
        assert row['regression_pass'], row
        rows.append(row)
    return rows


def write_outputs(rows: list[dict[str, object]]) -> None:
    output = Path('results/parametric_routing_regression.csv')
    output.parent.mkdir(exist_ok=True)
    with output.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    depths = [int(row['local_depth_new']) for row in rows]
    swaps = [int(row['swap_new']) for row in rows]
    cnots = [int(row['routed_cnot_new']) for row in rows]
    report = f"""# Régression du routage paramétrique

Statut : **validé — {sum(r['regression_pass'] for r in rows)}/{len(rows)} cas passent**.
Tolérance numérique : `{TOLERANCE:g}`.

| Ressource | minimum | maximum |
|---|---:|---:|
| profondeur locale | {min(depths)} | {max(depths)} |
| CNOT routés | {min(cnots)} | {max(cnots)} |
| SWAP | {min(swaps)} | {max(swaps)} |

Pour chaque instance, fidélité routée et erreur opératorielle coïncident avec
l'oracle historique à moins de `1e-12`. Profondeur, CNOT, SWAP et ordre final
des fils coïncident exactement. Le routeur paramétrique utilise uniquement
`SystemLayout.chain(t)` et restitue cette permutation à l'identité.

Le chemin historique est exécuté seulement après le calcul de toutes les
métriques paramétriques. Le chemin paramétrique n'importe ni CSV, ni module
`experiment`, ni constantes B=4. Aucune instance B=5 n'est exécutée.
"""
    Path('docs/notes/PARAMETRIC_ROUTING_REGRESSION.md').write_text(report)


def main() -> None:
    rows = build_rows()
    write_outputs(rows)
    print(f'parametric routing regression: {sum(r["regression_pass"] for r in rows)}/{len(rows)} passed')


if __name__ == '__main__':
    main()
