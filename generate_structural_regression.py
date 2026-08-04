#!/usr/bin/env python3
"""Run isolated exhaustive/structural regressions for A=1 through A=4."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys


TOLERANCE = 1e-12


def _worker(mode: str, message_qubits: int):
    process = subprocess.run(
        [
            sys.executable,
            "structural_regression_worker.py",
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


def build_rows():
    rows = []
    for message_qubits in range(1, 5):
        old = _worker("old", message_qubits)
        new = _worker("new", message_qubits)
        discrete_keys = (
            "A",
            "t",
            "logical_depth",
            "logical_cnot",
            "routed_depth",
            "routed_cnot",
            "swap",
            "final_order",
            "encoder_tableau",
            "output_tableau",
            "signed_rows",
            "gate_signature",
            "support_rank",
        )
        discrete_equal = all(old[key] == new[key] for key in discrete_keys)
        encoder_tableau_equal = old["encoder_tableau"] == new["encoder_tableau"]
        output_tableau_equal = old["output_tableau"] == new["output_tableau"]
        signed_correlations_equal = old["signed_rows"] == new["signed_rows"]
        gate_signature_equal = old["gate_signature"] == new["gate_signature"]
        numeric_keys = (
            "petz_fidelity",
            "direct_circuit_fidelity",
            "routed_circuit_fidelity",
            "choi_fidelity",
            "operator_error_or_certificate_error",
        )
        numeric_max_difference = max(abs(old[key] - new[key]) for key in numeric_keys)
        regression_pass = (
            discrete_equal
            and numeric_max_difference < TOLERANCE
            and new["certificate_pass"]
            and new["reduced_choi_equal"]
        )
        row = {
            "A": message_qubits,
            "t": old["t"],
            "regression_pass": regression_pass,
            "discrete_objects_equal": discrete_equal,
            "encoder_tableau_equal": encoder_tableau_equal,
            "output_tableau_equal": output_tableau_equal,
            "signed_correlations_and_phases_equal": signed_correlations_equal,
            "gate_signature_equal": gate_signature_equal,
            "numeric_max_difference": numeric_max_difference,
            "petz_fidelity_old": old["petz_fidelity"],
            "petz_fidelity_new": new["petz_fidelity"],
            "circuit_fidelity_old": old["direct_circuit_fidelity"],
            "circuit_fidelity_new": new["direct_circuit_fidelity"],
            "routed_fidelity_old": old["routed_circuit_fidelity"],
            "routed_fidelity_new": new["routed_circuit_fidelity"],
            "choi_fidelity_old": old["choi_fidelity"],
            "choi_fidelity_new_certified": new["choi_fidelity"],
            "operator_error_old": old["operator_error_or_certificate_error"],
            "certificate_error_new": new["operator_error_or_certificate_error"],
            "logical_depth_old": old["logical_depth"],
            "logical_depth_new": new["logical_depth"],
            "logical_cnot_old": old["logical_cnot"],
            "logical_cnot_new": new["logical_cnot"],
            "routed_depth_old": old["routed_depth"],
            "routed_depth_new": new["routed_depth"],
            "routed_cnot_old": old["routed_cnot"],
            "routed_cnot_new": new["routed_cnot"],
            "swap_old": old["swap"],
            "swap_new": new["swap"],
            "final_order_equal": old["final_order"] == new["final_order"],
            "old_group_size_theoretical": old["old_group_size_theoretical"],
            "old_operator_checks_theoretical": old["old_operator_checks_theoretical"],
            "new_generators_checked": new["generators_checked"],
            "support_kernel_variables": new["support_kernel_variables"],
            "support_kernel_constraints": new["support_kernel_constraints"],
            "support_kernel_constraint_rank": new[
                "support_kernel_constraint_rank"
            ],
            "support_kernel_dimension": new["support_kernel_dimension"],
            "support_stabilizer_rank": new["support_stabilizer_rank"],
            "centralizer_dimension": new["centralizer_dimension"],
            "logical_quotient_dimension": new["logical_quotient_dimension"],
            "choi_affine_variables": new["choi_affine_variables"],
            "choi_affine_constraints": new["choi_affine_constraints"],
            "choi_affine_constraint_rank": new["choi_affine_constraint_rank"],
            "choi_affine_kernel_dimension": new[
                "choi_affine_kernel_dimension"
            ],
            "gf2_affine_systems_solved": new["gf2_affine_systems_solved"],
            "gf2_rank_reductions": new["gf2_rank_reductions"],
            "gf2_pivots": new["gf2_pivots"],
            "gf2_row_xors": new["gf2_row_xors"],
            "gf2_scalar_bit_xors": new["gf2_scalar_bit_xors"],
            "old_elapsed_seconds": old["elapsed_seconds"],
            "new_elapsed_seconds": new["elapsed_seconds"],
            "speedup": old["elapsed_seconds"] / new["elapsed_seconds"],
            "old_peak_rss_mib": old["peak_rss_mib"],
            "new_peak_rss_mib": new["peak_rss_mib"],
            "old_rss_increment_mib": old["rss_increment_mib"],
            "new_rss_increment_mib": new["rss_increment_mib"],
            "certificate_pass": new["certificate_pass"],
            "reduced_choi_equal": new["reduced_choi_equal"],
        }
        assert regression_pass, row
        rows.append(row)
    return rows


def write_outputs(rows) -> None:
    output = Path("results/structural_compiler_regression.csv")
    output.parent.mkdir(exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    table = "\n".join(
        f"| {row['A']} | {row['old_group_size_theoretical']} | "
        f"{row['old_operator_checks_theoretical']} | {row['new_generators_checked']} | "
        f"{row['old_elapsed_seconds']:.3f} | {row['new_elapsed_seconds']:.3f} | "
        f"{row['speedup']:.2f} | {row['old_peak_rss_mib']:.1f} | "
        f"{row['new_peak_rss_mib']:.1f} |"
        for row in rows
    )
    algebra_table = "\n".join(
        f"| {row['A']} | {row['support_kernel_variables']} | "
        f"{row['support_kernel_constraints']} | "
        f"{row['support_kernel_constraint_rank']} | "
        f"{row['support_kernel_dimension']} | {row['support_stabilizer_rank']} | "
        f"{row['centralizer_dimension']} | {row['logical_quotient_dimension']} | "
        f"{row['choi_affine_variables']} | {row['choi_affine_constraint_rank']} | "
        f"{row['choi_affine_kernel_dimension']} | {row['gf2_affine_systems_solved']} | "
        f"{row['gf2_scalar_bit_xors']} |"
        for row in rows
    )
    report = f"""# Régression du compilateur structurel

Statut : **validé — {sum(row['regression_pass'] for row in rows)}/4 cas**.
Tolérance numérique : `{TOLERANCE:g}`.

| A | ancien groupe | anciens opérateurs | générateurs vérifiés | temps ancien s | temps nouveau s | accélération | RSS ancien Mio | RSS nouveau Mio |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{table}

Pour A=1 à A=4, les tableaux encodeur/sortie, corrélations signées,
circuits, profondeurs, CNOT, SWAP, routage et ordre final sont exactement
identiques. Les fidélités numériques concordent à moins de `1e-12`.

Le nouveau certificat vérifie l'égalité des purifications Choi dans la jauge
fixée ; l'isométrie d'environnement est donc `W_E=I`, ce qui implique l'égalité
des Choi réduits après trace. Aucun élément du groupe stabilisateur et aucun
opérateur de la base complète du support ne sont énumérés sur le nouveau chemin.

## Dimensions de l'algèbre binaire

| A | variables noyau support | contraintes | rang | dim noyau | rang stabilisateur | dim centralisateur | dim quotient logique | variables Choi | rang Choi | dim noyau affine | systèmes résolus | XOR scalaires instrumentés |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{algebra_table}

Le quotient logique est le centralisateur modulo le stabilisateur et possède
donc la dimension binaire `2k`. Le compteur couvre exactement les réductions de
lignes effectuées par `gf2.py` (systèmes affines, calculs de rang, pivots et
XOR de lignes). Il ne compte pas les opérations internes de Stim ni les
produits matriciels NumPy hors de ces éliminations ; la colonne ne doit donc
pas être interprétée comme un nombre total d'instructions machine.

Les mesures RSS proviennent de processus isolés. Les durées comprennent
synthèse, certification et les deux évaluations physiques de fidélité. Elles
ne constituent pas une loi d'échelle.
"""
    Path("docs/notes/STRUCTURAL_COMPILER_REGRESSION.md").write_text(report)


def main() -> None:
    rows = build_rows()
    write_outputs(rows)
    print(f"structural regression: {sum(row['regression_pass'] for row in rows)}/4 passed")


if __name__ == "__main__":
    main()
