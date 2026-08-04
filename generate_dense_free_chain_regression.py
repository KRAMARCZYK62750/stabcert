#!/usr/bin/env python3
"""Regress dense and stabilizer-only Petz chains for A=1 through A=7."""
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
            "dense_free_chain_regression_worker.py",
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
    for message_qubits in range(1, 8):
        dense = _worker("dense", message_qubits)
        structural = _worker("structural", message_qubits)
        discrete_keys = (
            "A",
            "t",
            "output",
            "complement",
            "support_rank",
            "support_logical_qubits",
            "support_signed_signature",
            "choi_qubits",
            "choi_signed_signature",
            "encoder_tableau",
            "output_tableau",
            "gate_signature",
            "logical_depth",
            "logical_cnot",
            "routed_depth",
            "routed_cnot",
            "swap",
            "final_order",
            "environment_qubits",
        )
        discrete_equal = all(dense[key] == structural[key] for key in discrete_keys)
        fidelity_difference = max(
            abs(float(dense[key]) - float(structural[key]))
            for key in ("petz_fidelity", "direct_fidelity", "routed_fidelity")
        )
        regression_pass = (
            discrete_equal
            and fidelity_difference < TOLERANCE
            and structural["reduced_choi_equal"]
            and structural["signed_phases_validated"]
            and not structural["dense_channel_constructed"]
            and not structural["dense_tau_factor_constructed"]
            and not structural["dense_choi_vector_constructed"]
        )
        row = {
            "A": message_qubits,
            "t": dense["t"],
            "regression_pass": regression_pass,
            "discrete_objects_equal": discrete_equal,
            "signed_choi_generators_equal": dense["choi_signed_signature"]
            == structural["choi_signed_signature"],
            "signed_tau_support_equal": dense["support_signed_signature"]
            == structural["support_signed_signature"],
            "support_rank_equal": dense["support_rank"]
            == structural["support_rank"],
            "resources_equal": all(
                dense[key] == structural[key]
                for key in (
                    "logical_depth",
                    "logical_cnot",
                    "routed_depth",
                    "routed_cnot",
                    "swap",
                    "environment_qubits",
                )
            ),
            "maximum_fidelity_difference": fidelity_difference,
            "petz_fidelity_dense": dense["petz_fidelity"],
            "petz_fidelity_structural": structural["petz_fidelity"],
            "direct_fidelity_dense_channel": dense["direct_fidelity"],
            "direct_fidelity_structural_channel": structural["direct_fidelity"],
            "routed_fidelity_dense_channel": dense["routed_fidelity"],
            "routed_fidelity_structural_channel": structural["routed_fidelity"],
            "support_rank": structural["support_rank"],
            "choi_qubits": structural["choi_qubits"],
            "logical_depth": structural["logical_depth"],
            "logical_cnot": structural["logical_cnot"],
            "routed_depth": structural["routed_depth"],
            "routed_cnot": structural["routed_cnot"],
            "swap": structural["swap"],
            "environment_qubits": structural["environment_qubits"],
            "dense_elapsed_seconds": dense["elapsed_seconds"],
            "structural_elapsed_seconds": structural["elapsed_seconds"],
            "speedup": float(dense["elapsed_seconds"])
            / float(structural["elapsed_seconds"]),
            "dense_peak_rss_mib": dense["peak_rss_mib"],
            "structural_peak_rss_mib": structural["peak_rss_mib"],
            "dense_rss_increment_mib": dense["rss_increment_mib"],
            "structural_rss_increment_mib": structural["rss_increment_mib"],
            "structural_dense_channel_constructed": structural[
                "dense_channel_constructed"
            ],
            "structural_dense_tau_constructed": structural[
                "dense_tau_factor_constructed"
            ],
            "structural_dense_choi_constructed": structural[
                "dense_choi_vector_constructed"
            ],
        }
        assert regression_pass, row
        rows.append(row)
    return rows


def write_outputs(rows: list[dict[str, object]]) -> None:
    output = Path("results/dense_free_chain_regression.csv")
    output.parent.mkdir(exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    table = "\n".join(
        f"| {row['A']} | {row['support_rank']} | {row['choi_qubits']} | "
        f"{row['maximum_fidelity_difference']:.3g} | "
        f"{row['dense_elapsed_seconds']:.3f} | "
        f"{row['structural_elapsed_seconds']:.3f} | {row['speedup']:.2f} | "
        f"{row['dense_peak_rss_mib']:.1f} | {row['structural_peak_rss_mib']:.1f} |"
        for row in rows
    )
    report = f"""# Régression de la chaîne Petz entièrement stabilisatrice

Statut : **validé — {sum(bool(row['regression_pass']) for row in rows)}/7**.
Tolérance numérique : `{TOLERANCE:g}`.

| A | rang tau_X | qubits Choi | écart fidélité max | temps dense s | temps structurel s | accélération | RSS dense Mio | RSS structurelle Mio |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{table}

Pour A=1 à A=7, les objets suivants coïncident exactement : partitions X/C,
supports signés de `tau_X`, groupes Choi Petz signés sous forme RREF canonique,
tableaux encodeur/sortie, circuits, profondeurs, CNOT, SWAP, environnement et
ordre final. Les fidélités concordent à moins de `1e-12`.

Le nouveau chemin représente le canal par son isométrie stabilisatrice pure,
`tau_X` par son projecteur stabilisateur normalisé, et le Choi Petz par la
conjugaison complexe du Choi global après permutation `R|X|C` vers
`A'|Ref|E_Petz`. Il ne construit ni Kraus dense, ni matrice `tau_X`, ni vecteur
Choi dense.

Les chemins NumPy/SVD restent présents uniquement dans les travailleurs de
régression dense. Ces mesures ne constituent pas une loi d'échelle.
"""
    Path("docs/notes/DENSE_FREE_CHAIN_REGRESSION.md").write_text(report)


def main() -> None:
    rows = build_rows()
    write_outputs(rows)
    print(f"dense-free Petz-chain regression: {len(rows)}/7 passed")


if __name__ == "__main__":
    main()
