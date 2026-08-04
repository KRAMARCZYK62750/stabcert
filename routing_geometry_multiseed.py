#!/usr/bin/env python3
"""Five-seed geometry reproducibility grid for the fixed A=9..12 circuits."""
from __future__ import annotations

import csv
import os
from pathlib import Path
import platform
import resource
import time

os.environ.setdefault("MPLCONFIGDIR", str(Path(".matplotlib-cache").resolve()))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_architecture_routing import (
    causal_lightcone_depth_bound,
    route_graph_lookahead,
)
from hayden_preskill_toy.parametric_certificate import (
    certify_routed_equivalence,
    circuit_entanglement_fidelity_stabilizer,
    structural_validation,
)
from hayden_preskill_toy.parametric_graph_routing import coupling_graph
from hayden_preskill_toy.parametric_petz_stabilizer import (
    random_stabilizer_scrambler,
    stabilizer_channel_at_time,
)
from hayden_preskill_toy.parametric_routing import two_qubit_depth
from hayden_preskill_toy.parametric_synthesis import signed_dilation


CASES = {9: 9, 10: 12, 11: 12, 12: 14}
SEEDS = tuple(range(20260802, 20260807))
ARCHITECTURES = ("chain", "ring", "grid_2d", "all_to_all")
SCRAMBLE_DEPTH = 6
LOOKAHEAD = 16
CANDIDATE_BUDGET = 64


def _rss_mib() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    byte_value = value if platform.system() == "Darwin" else value * 1024
    return float(byte_value / 2**20)


def _quantiles(values) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    return {
        "minimum": float(np.min(array)),
        "q1": float(np.quantile(array, 0.25)),
        "median": float(np.median(array)),
        "q3": float(np.quantile(array, 0.75)),
        "maximum": float(np.max(array)),
    }


def run_grid():
    started = time.perf_counter()
    rows = []
    for message_qubits, t in CASES.items():
        for seed in SEEDS:
            instance_started = time.perf_counter()
            layout = SystemLayout(n_message=message_qubits, n_black_hole=4)
            scrambler = random_stabilizer_scrambler(
                layout, np.random.default_rng(seed), SCRAMBLE_DEPTH
            )
            channel = stabilizer_channel_at_time(layout, scrambler, t)
            gates, encoder, output, correlations = signed_dilation(
                layout, channel, scrambler, t
            )
            logical_depth = two_qubit_depth(gates, layout.n_qubits)
            logical_cnot = sum(gate.name == "CNOT" for gate in gates)
            direct = structural_validation(
                layout,
                channel,
                scrambler,
                t,
                gates,
                encoder,
                output,
                correlations,
            )
            if not direct["validated"]:
                raise AssertionError((message_qubits, seed, "direct", direct))
            for architecture in ARCHITECTURES:
                graph = coupling_graph(architecture, len(layout.chain(t)))
                routing_started = time.perf_counter()
                routed = route_graph_lookahead(
                    layout,
                    t,
                    gates,
                    graph,
                    lookahead=LOOKAHEAD,
                    candidate_budget=CANDIDATE_BUDGET,
                )
                routing_seconds = time.perf_counter() - routing_started
                equivalent = certify_routed_equivalence(
                    layout, t, gates, routed.gates
                )
                overlap = circuit_entanglement_fidelity_stabilizer(
                    layout, scrambler, t, routed.gates
                )
                routed_fidelity = float(overlap["fidelity"])
                fidelity_matches = (
                    abs(routed_fidelity - float(direct["petz_fidelity"])) < 1e-12
                )
                validated = (
                    equivalent
                    and fidelity_matches
                    and routed.final_wire_at_site == layout.chain(t)
                )
                if not validated:
                    raise AssertionError(
                        (message_qubits, seed, architecture, routed_fidelity, direct)
                    )
                rows.append(
                    {
                        "A": message_qubits,
                        "t": t,
                        "seed": seed,
                        "scramble_depth": SCRAMBLE_DEPTH,
                        "architecture": architecture,
                        "lookahead": LOOKAHEAD,
                        "candidate_budget": CANDIDATE_BUDGET,
                        "accessible_sites": len(layout.chain(t)),
                        "logical_depth": logical_depth,
                        "logical_cnot": logical_cnot,
                        "causal_lightcone_depth_bound": causal_lightcone_depth_bound(
                            layout, t, gates, graph
                        ),
                        "routed_depth": routed.two_qubit_depth,
                        "depth_ratio": routed.two_qubit_depth / logical_depth,
                        "routed_cnot": routed.cnot_count,
                        "swap_total": routed.swap_count,
                        "swap_movement": routed.movement_swap_count,
                        "swap_restoration": routed.restoration_swap_count,
                        "restoration_swap_lower_bound": routed.restoration_swap_lower_bound,
                        "petz_fidelity": direct["petz_fidelity"],
                        "routed_fidelity": routed_fidelity,
                        "fidelity_difference": abs(
                            routed_fidelity - float(direct["petz_fidelity"])
                        ),
                        "signed_clifford_equivalent": equivalent,
                        "final_order_restored": routed.final_wire_at_site
                        == layout.chain(t),
                        "routing_seconds": routing_seconds,
                        "instance_elapsed_seconds": time.perf_counter()
                        - instance_started,
                        "validated": validated,
                    }
                )
    return rows, {
        "total_seconds": time.perf_counter() - started,
        "peak_rss_mib": _rss_mib(),
    }


def summarize(rows):
    summaries = []
    for message_qubits in CASES:
        for architecture in ARCHITECTURES:
            selected = [
                row
                for row in rows
                if row["A"] == message_qubits
                and row["architecture"] == architecture
            ]
            depth = _quantiles([row["routed_depth"] for row in selected])
            swaps = _quantiles([row["swap_total"] for row in selected])
            ratio = _quantiles([row["depth_ratio"] for row in selected])
            summaries.append(
                {
                    "A": message_qubits,
                    "architecture": architecture,
                    "count": len(selected),
                    **{f"depth_{key}": value for key, value in depth.items()},
                    **{f"swap_{key}": value for key, value in swaps.items()},
                    **{f"ratio_{key}": value for key, value in ratio.items()},
                    "petz_fidelity_min": min(
                        float(row["petz_fidelity"]) for row in selected
                    ),
                    "petz_fidelity_max": max(
                        float(row["petz_fidelity"]) for row in selected
                    ),
                    "validated_count": sum(bool(row["validated"]) for row in selected),
                }
            )
    return summaries


def paired_reductions(rows):
    records = []
    for message_qubits in CASES:
        for seed in SEEDS:
            selected = {
                row["architecture"]: row
                for row in rows
                if row["A"] == message_qubits and row["seed"] == seed
            }
            chain_depth = int(selected["chain"]["routed_depth"])
            for architecture in ("ring", "grid_2d", "all_to_all"):
                depth = int(selected[architecture]["routed_depth"])
                records.append(
                    {
                        "A": message_qubits,
                        "seed": seed,
                        "comparison": f"chain_to_{architecture}",
                        "chain_depth": chain_depth,
                        "comparison_depth": depth,
                        "absolute_reduction": chain_depth - depth,
                        "relative_reduction": (chain_depth - depth) / chain_depth,
                        "comparison_is_lower": depth < chain_depth,
                    }
                )
    return records


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _plot(rows, path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), sharey=False)
    colors = ("#264653", "#2a9d8f", "#e9c46a", "#e76f51")
    labels = ("chaîne", "anneau", "grille 2D", "tout-à-tout")
    for axis, message_qubits in zip(axes.flat, CASES):
        data = [
            [
                int(row["routed_depth"])
                for row in rows
                if row["A"] == message_qubits
                and row["architecture"] == architecture
            ]
            for architecture in ARCHITECTURES
        ]
        box = axis.boxplot(data, patch_artist=True, tick_labels=labels)
        for patch, color in zip(box["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.72)
        axis.set_title(f"A={message_qubits}")
        axis.set_ylabel("profondeur locale")
        axis.tick_params(axis="x", rotation=20)
        axis.grid(axis="y", alpha=0.25)
    fig.suptitle("Même routeur, cinq graines par taille")
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def write_outputs(rows, metadata):
    result_dir = Path("results")
    result_dir.mkdir(exist_ok=True)
    summaries = summarize(rows)
    reductions = paired_reductions(rows)
    _write_csv(result_dir / "routing_geometry_multiseed.csv", rows)
    _write_csv(result_dir / "routing_geometry_multiseed_summary.csv", summaries)
    _write_csv(result_dir / "routing_geometry_paired_reductions.csv", reductions)
    _plot(rows, result_dir / "routing_geometry_multiseed_depths.png")

    table = "\n".join(
        f"| {row['A']} | {row['architecture']} | {row['depth_minimum']:.0f} | "
        f"{row['depth_q1']:.1f} | {row['depth_median']:.1f} | "
        f"{row['depth_q3']:.1f} | {row['depth_maximum']:.0f} | "
        f"{row['ratio_median']:.2f} |"
        for row in summaries
    )
    paired_lines = []
    for message_qubits in CASES:
        for comparison in ("chain_to_ring", "chain_to_grid_2d", "chain_to_all_to_all"):
            selected = [
                row
                for row in reductions
                if row["A"] == message_qubits and row["comparison"] == comparison
            ]
            values = [100 * float(row["relative_reduction"]) for row in selected]
            paired_lines.append(
                f"| {message_qubits} | {comparison.removeprefix('chain_to_')} | "
                f"{sum(bool(row['comparison_is_lower']) for row in selected)}/5 | "
                f"{np.median(values):.1f} % | {min(values):.1f}…{max(values):.1f} % |"
            )
    fidelity_values = [float(row["petz_fidelity"]) for row in rows]
    report = f"""# Reproductibilité multi-graines du coût géométrique

Cette campagne conserve exactement le même routeur et le même budget sur
20 circuits logiques : A=9…12, cinq graines par taille, quatre architectures.
Elle contient 80 routages. Aucune instance n'est filtrée selon sa fidélité Petz.

## Distributions de profondeur

| A | architecture | min | Q1 | médiane | Q3 | max | rapport médian routé/logique |
|---:|---|---:|---:|---:|---:|---:|---:|
{table}

## Comparaisons appariées à la chaîne

| A | architecture | profondeur inférieure à la chaîne | réduction médiane | étendue |
|---:|---|---:|---:|---:|
{chr(10).join(paired_lines)}

Les comparaisons sont appariées : même A, même graine et même circuit logique.
Une réduction négative signifie que l'architecture comparée a été plus coûteuse
pour cette instance avec le routeur fixé.

## Validation

- Routages validés : {sum(bool(row['validated']) for row in rows)}/{len(rows)}.
- Fidélité Petz observée : {min(fidelity_values):.12g}…{max(fidelity_values):.12g}.
- Écart maximal circuit/Petz : {max(float(row['fidelity_difference']) for row in rows):.3e}.
- Temps total : {metadata['total_seconds']:.3f} s.
- RSS maximale : {metadata['peak_rss_mib']:.1f} Mio.

## Interprétation autorisée

La campagne mesure si l'avantage géométrique observé persiste au-delà d'une
seule graine dans cette famille finie. Elle ne démontre ni une profondeur
minimale, ni une loi d'échelle, ni les performances d'un dispositif réel.
Le bruit, la correction d'erreurs et les contraintes matérielles de parallélisme
ne sont pas modélisés.
"""
    Path("docs/notes/ROUTING_GEOMETRY_MULTISEED.md").write_text(report)
    return summaries, reductions


def main():
    rows, metadata = run_grid()
    summaries, reductions = write_outputs(rows, metadata)
    for message_qubits in CASES:
        selected = [row for row in summaries if row["A"] == message_qubits]
        print(
            f"A={message_qubits}: "
            + ", ".join(
                f"{row['architecture']} median={row['depth_median']:.0f}"
                for row in selected
            )
        )


if __name__ == "__main__":
    main()
