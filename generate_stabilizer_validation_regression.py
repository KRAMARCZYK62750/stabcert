#!/usr/bin/env python3
"""Generate the A=1..6 dense/state-free validation regression."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys


TOLERANCE = 1e-12


def _worker(mode: str, message_qubits: int) -> dict[str, object]:
    process = subprocess.run(
        [
            sys.executable,
            "stabilizer_validation_regression_worker.py",
            "--mode",
            mode,
            "--message-qubits",
            str(message_qubits),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(process.stdout)


def build_rows() -> list[dict[str, object]]:
    rows = []
    for message_qubits in range(1, 7):
        dense = _worker("dense", message_qubits)
        structural = _worker("structural", message_qubits)
        maximum_difference = max(
            abs(float(dense[key]) - float(structural[key]))
            for key in ("petz_fidelity", "direct_fidelity", "routed_fidelity")
        )
        verdicts_equal = (
            dense["direct_validated"] == structural["direct_validated"]
            and dense["routed_validated"] == structural["routed_validated"]
        )
        regression_pass = (
            maximum_difference < TOLERANCE
            and verdicts_equal
            and structural["reduced_choi_equal"]
            and structural["signed_phases_validated"]
            and structural["dense_state_amplitudes_constructed"] == 0
            and structural["dense_reduced_matrix_entries_constructed"] == 0
        )
        row = {
            "A": message_qubits,
            "t": dense["t"],
            "regression_pass": regression_pass,
            "maximum_fidelity_difference": maximum_difference,
            "verdicts_equal": verdicts_equal,
            "petz_fidelity_dense": dense["petz_fidelity"],
            "petz_fidelity_structural": structural["petz_fidelity"],
            "direct_fidelity_dense": dense["direct_fidelity"],
            "direct_fidelity_structural": structural["direct_fidelity"],
            "routed_fidelity_dense": dense["routed_fidelity"],
            "routed_fidelity_structural": structural["routed_fidelity"],
            "reduced_choi_equal_structural": structural["reduced_choi_equal"],
            "signed_phases_validated": structural["signed_phases_validated"],
            "intersection_rank": structural["intersection_rank"],
            "dense_state_amplitudes_old": dense[
                "dense_state_amplitudes_constructed"
            ],
            "dense_state_amplitudes_new": structural[
                "dense_state_amplitudes_constructed"
            ],
            "dense_reduced_entries_old": dense[
                "dense_reduced_matrix_entries_constructed"
            ],
            "dense_reduced_entries_new": structural[
                "dense_reduced_matrix_entries_constructed"
            ],
            "dense_validation_seconds": dense["validation_seconds"],
            "structural_validation_seconds": structural["validation_seconds"],
            "validation_speedup": float(dense["validation_seconds"])
            / float(structural["validation_seconds"]),
            "dense_peak_rss_mib": dense["peak_rss_mib"],
            "structural_peak_rss_mib": structural["peak_rss_mib"],
            "dense_validation_rss_increment_mib": dense[
                "validation_rss_increment_mib"
            ],
            "structural_validation_rss_increment_mib": structural[
                "validation_rss_increment_mib"
            ],
        }
        assert regression_pass, row
        rows.append(row)
    return rows


def write_outputs(rows: list[dict[str, object]]) -> None:
    output = Path("results/stabilizer_validation_regression.csv")
    output.parent.mkdir(exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    table = "\n".join(
        f"| {row['A']} | {row['t']} | {row['maximum_fidelity_difference']:.3g} | "
        f"{row['dense_state_amplitudes_old']} | "
        f"{row['structural_validation_seconds']:.4f} | "
        f"{row['dense_validation_seconds']:.4f} | {row['validation_speedup']:.2f} | "
        f"{row['dense_peak_rss_mib']:.1f} | {row['structural_peak_rss_mib']:.1f} |"
        for row in rows
    )
    report = f"""# Régression de la validation stabilisatrice sans état dense

Statut : **validé — {sum(bool(row['regression_pass']) for row in rows)}/6**.
Tolérance : `{TOLERANCE:g}`.

| A | t | écart fidélité max | amplitudes denses anciennes | temps structurel s | temps dense s | accélération | RSS dense Mio | RSS structurelle Mio |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{table}

Pour chaque cas, les fidélités Petz, directe et routée concordent à moins de
`1e-12`, et les verdicts sont identiques. Le nouveau chemin vérifie :

- intersection exacte du stabilisateur réduit avec le stabilisateur de Bell ;
- compatibilité des phases sur cette intersection ;
- égalité des Choi réduits par groupes générateurs signés ;
- zéro amplitude de vecteur d'état et zéro entrée de matrice réduite dense
  construite par la validation.

La fidélité structurelle vaut `2^(ell-2A)` lorsque les phases sont compatibles,
où `ell` est le rang de l'intersection ; elle vaut zéro en cas de conflit de
phase. La référence Petz `2^(-I(R:C))` est utilisée seulement sous les
hypothèses déjà auditées : isométrie Clifford, environnement stabilisateur pur
et référence maximale.

Les processus dense et structurel sont isolés. Leurs RSS incluent le canal et
la synthèse communs déjà présents avant la validation ; les colonnes
d'incrément de RSS du CSV isolent mieux la couche remplacée.
"""
    Path("docs/notes/STABILIZER_VALIDATION_REGRESSION.md").write_text(report)


def main() -> None:
    rows = build_rows()
    write_outputs(rows)
    print(f"state-free validation regression: {len(rows)}/6 passed")


if __name__ == "__main__":
    main()
