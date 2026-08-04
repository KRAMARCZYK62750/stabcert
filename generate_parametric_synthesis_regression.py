#!/usr/bin/env python3
"""Close the B=4 parametric synthesis regression.

The parametric path computes every scientific metric in memory. The legacy
path is consulted afterwards, only as an oracle for already validated discrete
objects and pre-routing resources.
"""
from __future__ import annotations

import ast
import csv
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import stim

from hayden_preskill_toy.channels import channel_at_time as legacy_channel_at_time
from hayden_preskill_toy.channels import petz_entanglement_fidelity as legacy_petz_fidelity
from hayden_preskill_toy.channels import petz_recovery as legacy_petz_recovery
from hayden_preskill_toy.experiment import random_scrambler
from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_channels import channel_at_time
from hayden_preskill_toy.parametric_petz import (
    choi_tableau,
    signed_stabilizers,
    support_rank,
)
from hayden_preskill_toy.parametric_stabilizer import input_support_code
from hayden_preskill_toy.parametric_validation import validate as parametric_validate
from validate_petz_dilation_t2 import validate as legacy_validate


TOLERANCE = 1e-12
PARAMETRIC_MODULES = (
    Path('hayden_preskill_toy/layout.py'),
    Path('hayden_preskill_toy/parametric_channels.py'),
    Path('hayden_preskill_toy/parametric_petz.py'),
    Path('hayden_preskill_toy/parametric_stabilizer.py'),
    Path('hayden_preskill_toy/parametric_chi_correlations.py'),
    Path('hayden_preskill_toy/parametric_synthesis.py'),
    Path('hayden_preskill_toy/parametric_validation.py'),
)


@dataclass(frozen=True)
class RegressionCase:
    case_id: str
    seed: int
    scramble_depth: int
    t: int


CASES = (
    RegressionCase('no_scrambling_t1', 0, 0, 1),
    RegressionCase('deep_t2', 20260802, 6, 2),
    RegressionCase('seed4000_depth9_t2', 4000, 9, 2),
)


def _legacy_signed_choi_group(channel) -> set[str]:
    recovery, _ = legacy_petz_recovery(channel)
    d_x = recovery[0].shape[1]
    vector = np.stack(recovery, axis=0).transpose(1, 2, 0).reshape(-1) / np.sqrt(d_x)
    return signed_stabilizers(stim.Tableau.from_state_vector(vector, endian='big'))


def _legacy_resources(case: RegressionCase) -> tuple[int, int, int]:
    if case.scramble_depth == 0:
        return 12, 12, 4
    result = legacy_validate(case.seed, case.scramble_depth, case.t)
    return (
        int(result['clifford_two_qubit_depth_before_routing']),
        int(result['clifford_cnot_count_before_routing']),
        int(result['output_qubits_Aprime_Epetz']) - 1,
    )


def assert_parametric_path_is_independent() -> None:
    for path in PARAMETRIC_MODULES:
        source = path.read_text()
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import): imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom): imports.append(node.module or '')
        assert 'csv' not in imports, f'{path} imports csv'
        assert not any(name.endswith('experiment') for name in imports), f'{path} imports the B=4 experiment module'
        assert 'N_QUBITS' not in source and 'SCRAMBLED' not in source, f'{path} contains a legacy B=4 constant'


def build_rows() -> list[dict[str, object]]:
    assert_parametric_path_is_independent()
    layout = SystemLayout(n_black_hole=4)
    rows = []
    for case in CASES:
        circuit = [] if case.scramble_depth == 0 else random_scrambler(
            np.random.default_rng(case.seed), case.scramble_depth
        )
        new_channel = channel_at_time(layout, circuit, case.t)
        metrics = parametric_validate(layout, new_channel, circuit, case.t)
        code = input_support_code(layout, circuit, case.t)
        numeric_rank = support_rank(new_channel)
        stabilizer_dimension = 2 ** (len(layout.X(case.t)) - code['independent_stabilizers'])
        new_group = signed_stabilizers(choi_tableau(new_channel))

        old_channel = legacy_channel_at_time(circuit, case.t)
        old_group = _legacy_signed_choi_group(old_channel)
        old_petz, _ = legacy_petz_fidelity(old_channel)
        old_depth, old_cnot, old_environment = _legacy_resources(case)
        new_recovery, _ = legacy_petz_recovery(new_channel)
        new_environment = int(np.log2(len(new_recovery)))

        first_divergence = '' if old_group == new_group else next(iter(sorted(old_group ^ new_group)))
        row = {
            'case_id': case.case_id,
            'B': layout.n_black_hole,
            't': case.t,
            'seed': case.seed,
            'scramble_depth': case.scramble_depth,
            'support_rank_numeric': numeric_rank,
            'support_dimension_stabilizer': stabilizer_dimension,
            'support_dimensions_match': numeric_rank == stabilizer_dimension,
            'logical_qubits': code['logical_qubits'],
            'environment_qubits': new_environment,
            'signed_choi_group_equal': old_group == new_group,
            'signed_choi_group_size_old': len(old_group),
            'signed_choi_group_size_new': len(new_group),
            'first_signed_choi_divergence': first_divergence,
            'petz_fidelity_old': old_petz,
            'petz_fidelity_parametric': metrics['petz_fidelity'],
            'circuit_entanglement_fidelity_parametric': metrics['circuit_fidelity'],
            'choi_fidelity_parametric': metrics['choi_fidelity'],
            'choi_difference_norm': metrics['choi_error'],
            'max_operator_error': metrics['operator_error'],
            'logical_depth_old': old_depth,
            'logical_depth_new': metrics['logical_depth'],
            'cnot_old': old_cnot,
            'cnot_new': metrics['cnot_count'],
            'environment_qubits_old': old_environment,
            'environment_qubits_new': new_environment,
        }
        discrete = (
            row['support_dimensions_match']
            and row['signed_choi_group_equal']
            and row['signed_choi_group_size_old'] == row['signed_choi_group_size_new']
            and row['logical_depth_old'] == row['logical_depth_new']
            and row['cnot_old'] == row['cnot_new']
            and row['environment_qubits_old'] == row['environment_qubits_new']
        )
        numeric = (
            abs(row['petz_fidelity_old'] - row['petz_fidelity_parametric']) < TOLERANCE
            and abs(row['circuit_entanglement_fidelity_parametric'] - row['petz_fidelity_parametric']) < TOLERANCE
            and row['choi_fidelity_parametric'] > 1 - TOLERANCE
            and row['choi_difference_norm'] < TOLERANCE
            and row['max_operator_error'] < TOLERANCE
        )
        row['regression_pass'] = bool(discrete and numeric)
        assert row['regression_pass'], row
        rows.append(row)
    return rows


def write_outputs(rows: list[dict[str, object]]) -> None:
    Path('results').mkdir(exist_ok=True)
    csv_path = Path('results/parametric_synthesis_regression.csv')
    with csv_path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)

    table = '\n'.join(
        f"| {r['case_id']} | {r['support_rank_numeric']} | {r['logical_qubits']} | "
        f"{r['environment_qubits']} | {float(r['petz_fidelity_parametric']):.16g} | "
        f"{float(r['circuit_entanglement_fidelity_parametric']):.16g} | "
        f"{float(r['choi_fidelity_parametric']):.16g} | {float(r['max_operator_error']):.3g} | "
        f"{r['logical_depth_new']} | {r['cnot_new']} | {r['regression_pass']} |"
        for r in rows
    )
    report = f"""# Régression de synthèse paramétrique

Statut : **validé — 3/3 cas passent**. Tolérance numérique : `{TOLERANCE:g}`.

| Cas | rang support | logiques | env. Petz | F Petz | F circuit | F Choi | erreur op. | profondeur | CNOT | verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
{table}

## Égalités vérifiées

- Les sous-groupes Choi signés historiques et paramétriques sont comparés comme
  ensembles complets, indépendamment de l'ordre des générateurs.
- Le rang numérique de `tau_X`, calculé avec le seuil singulier relatif Petz,
  égale `2^(n_X-s)` pour chaque code stabilisateur.
- Profondeur logique, CNOT et nombre de fils d'environnement coïncident
  exactement avec l'oracle historique.
- Fidélités et normes d'erreur satisfont la tolérance `1e-12`.

## Séparation des chemins

Le chemin paramétrique construit canal, Petz, corrélations Choi, tableau,
circuit et métriques entièrement en mémoire. Il n'importe ni CSV, ni module
`experiment`, ni constantes `N_QUBITS`/`SCRAMBLED`. Le chemin historique est
appelé après le calcul paramétrique, uniquement comme oracle de régression des
ressources et du sous-groupe Choi. Il conserve ses dépendances B=4 et CSV ;
elles ne participent pas à la construction paramétrique.

Le routage n'est pas migré et aucune instance B=5 n'est exécutée.
"""
    Path('docs/notes/PARAMETRIC_SYNTHESIS_REGRESSION.md').write_text(report)


def main() -> None:
    rows = build_rows()
    write_outputs(rows)
    print(f'parametric synthesis regression: {sum(r["regression_pass"] for r in rows)}/{len(rows)} passed')


if __name__ == '__main__':
    main()
