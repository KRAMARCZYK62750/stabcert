#!/usr/bin/env python3
"""Compare fixed A=9..12 Clifford decoders across four coupling graphs."""
from __future__ import annotations

import csv
from pathlib import Path
import platform
import resource
import time

import numpy as np

from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_certificate import (
    certify_routed_equivalence,
    structural_validation,
)
from hayden_preskill_toy.parametric_graph_routing import (
    coupling_graph,
    logical_interaction_distances,
    route_graph,
)
from hayden_preskill_toy.parametric_petz_stabilizer import (
    random_stabilizer_scrambler,
    stabilizer_channel_at_time,
)
from hayden_preskill_toy.parametric_routing import route_line, two_qubit_depth
from hayden_preskill_toy.parametric_synthesis import signed_dilation


CASES = {9: 9, 10: 12, 11: 12, 12: 14}
ARCHITECTURES = ("chain", "ring", "grid_2d", "all_to_all")
SEED = 20260802
SCRAMBLE_DEPTH = 6


def _rss_mib() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    byte_value = value if platform.system() == "Darwin" else value * 1024
    return float(byte_value / 2**20)


def run_comparison():
    started = time.perf_counter()
    rows = []
    for message_qubits, t in CASES.items():
        layout = SystemLayout(n_message=message_qubits, n_black_hole=4)
        scrambler = random_stabilizer_scrambler(
            layout, np.random.default_rng(SEED), SCRAMBLE_DEPTH
        )
        channel = stabilizer_channel_at_time(layout, scrambler, t)
        gates, encoder, output, correlations = signed_dilation(
            layout, channel, scrambler, t
        )
        logical_depth = two_qubit_depth(gates, layout.n_qubits)
        logical_cnot = sum(gate.name == "CNOT" for gate in gates)
        for architecture_label in ("chain_historical", *ARCHITECTURES):
            architecture = (
                "chain" if architecture_label == "chain_historical" else architecture_label
            )
            graph = coupling_graph(architecture, len(layout.chain(t)))
            routing_started = time.perf_counter()
            if architecture_label == "chain_historical":
                historical = route_line(layout, t, gates)
                routed_gates = historical.gates
                swap_count = historical.swap_count
                cnot_count = historical.cnot_count
                depth = historical.two_qubit_depth
                final_order = historical.final_wire_at_site
                edge_count = graph.edge_count
                diameter = graph.diameter if hasattr(graph, "diameter") else len(layout.chain(t)) - 1
                grid_rows = None
                grid_columns = None
                routing_policy = "historical_line_router"
            else:
                routed = route_graph(layout, t, gates, graph)
                routed_gates = routed.gates
                swap_count = routed.swap_count
                cnot_count = routed.cnot_count
                depth = routed.two_qubit_depth
                final_order = routed.final_wire_at_site
                edge_count = routed.edge_count
                diameter = routed.diameter
                grid_rows = routed.grid_rows
                grid_columns = routed.grid_columns
                routing_policy = "common_shortest_path_inverse_replay"
            routing_seconds = time.perf_counter() - routing_started
            equivalent = certify_routed_equivalence(
                layout, t, gates, routed_gates
            )
            validation = structural_validation(
                layout,
                channel,
                scrambler,
                t,
                routed_gates,
                encoder,
                output,
                correlations,
            )
            distances = logical_interaction_distances(layout, t, gates, graph)
            validated = (
                equivalent
                and bool(validation["validated"])
                and final_order == layout.chain(t)
            )
            if not validated:
                raise AssertionError((message_qubits, architecture, validation))
            rows.append(
                {
                    "A": message_qubits,
                    "t": t,
                    "accessible_sites": len(layout.chain(t)),
                    "architecture": architecture_label,
                    "coupling_graph": architecture,
                    "routing_policy": routing_policy,
                    "graph_edges": edge_count,
                    "graph_diameter": diameter,
                    "grid_rows": "" if grid_rows is None else grid_rows,
                    "grid_columns": "" if grid_columns is None else grid_columns,
                    "logical_depth": logical_depth,
                    "logical_cnot": logical_cnot,
                    "routed_depth": depth,
                    "routing_depth_overhead": depth - logical_depth,
                    "depth_ratio": depth / logical_depth,
                    "routed_cnot": cnot_count,
                    "swap": swap_count,
                    "mean_initial_logical_cnot_distance": sum(distances) / len(distances),
                    "max_initial_logical_cnot_distance": max(distances),
                    "petz_fidelity": validation["petz_fidelity"],
                    "routed_fidelity": validation["circuit_fidelity"],
                    "signed_clifford_equivalent": equivalent,
                    "final_order_restored": final_order == layout.chain(t),
                    "routing_seconds": routing_seconds,
                    "validated": validated,
                }
            )
    return rows, {
        "total_seconds": time.perf_counter() - started,
        "peak_rss_mib": _rss_mib(),
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(rows, metadata) -> None:
    output = Path("results")
    output.mkdir(exist_ok=True)
    _write_csv(output / "geometry_routing_comparison.csv", rows)
    table = "\n".join(
        f"| {row['A']} | {row['architecture']} | {row['graph_diameter']} | "
        f"{row['logical_depth']} | {row['routed_depth']} | {row['depth_ratio']:.2f} | "
        f"{row['routed_cnot']} | {row['swap']} | "
        f"{row['mean_initial_logical_cnot_distance']:.2f} |"
        for row in rows
    )
    report = f"""# Comparaison du coût de routage par géométrie

Même circuit logique, même graine et même temps d'émission pour chaque ligne A.
Les quatre comparaisons principales — `chain`, `ring`, `grid_2d` et
`all_to_all` — utilisent exactement le même routeur par plus court chemin avec
rejeu inverse des SWAP. `chain_historical` conserve séparément l'ancien routeur
spécialisé. Toutes les lignes restaurent l'ordre final et reproduisent
exactement le Clifford signé d'origine.

| A | architecture | diamètre | profondeur logique | profondeur routée | rapport | CNOT routés | SWAP | distance CNOT moyenne initiale |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
{table}

Temps total : `{metadata['total_seconds']:.3f} s` ; RSS maximale :
`{metadata['peak_rss_mib']:.1f} Mio`.

## Lecture

Le cas tout-à-tout constitue le contrôle : aucun SWAP et profondeur routée
égale à la profondeur logique. Les différences `chain`/`ring`/`grid_2d`
isolent la géométrie sous une heuristique identique, mais pas une profondeur
minimale. La ligne historique montre aussi combien une heuristique spécialisée
peut changer le résultat à géométrie fixe.

## Limites

Quatre circuits Clifford idéaux seulement sont comparés. Les routeurs ne sont
pas annoncés optimaux et les résultats ne constituent ni une loi d'échelle ni
une borne fondamentale liée à la géométrie.
"""
    Path("docs/notes/GEOMETRY_ROUTING_COMPARISON.md").write_text(report)


def main() -> None:
    rows, metadata = run_comparison()
    write_outputs(rows, metadata)
    for message_qubits in CASES:
        selected = [row for row in rows if row["A"] == message_qubits]
        values = ", ".join(
            f"{row['architecture']}={row['routed_depth']}"
            for row in selected
        )
        print(f"A={message_qubits}: {values}")


if __name__ == "__main__":
    main()
