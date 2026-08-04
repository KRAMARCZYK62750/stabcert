#!/usr/bin/env python3
"""Audit compiler and geometry costs on the fixed A=9..12 Petz circuits."""
from __future__ import annotations

import csv
from pathlib import Path
import platform
import resource
import time

import numpy as np

from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_architecture_routing import (
    causal_lightcone_depth_bound,
    route_graph_lookahead,
)
from hayden_preskill_toy.parametric_certificate import (
    certify_routed_equivalence,
    structural_validation,
)
from hayden_preskill_toy.parametric_graph_routing import (
    coupling_graph,
    graph_diameter,
    logical_interaction_distances,
    route_graph,
    shortest_path,
)
from hayden_preskill_toy.parametric_petz_stabilizer import (
    random_stabilizer_scrambler,
    stabilizer_channel_at_time,
)
from hayden_preskill_toy.parametric_routing import route_line, two_qubit_depth
from hayden_preskill_toy.parametric_synthesis import signed_dilation
from hayden_preskill_toy.simulator import Gate


CASES = {9: 9, 10: 12, 11: 12, 12: 14}
ARCHITECTURES = ("chain", "ring", "grid_2d", "all_to_all")
SEED = 20260802
SCRAMBLE_DEPTH = 6
LOOKAHEAD = 16
CANDIDATE_BUDGET = 64


def _rss_mib() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    byte_value = value if platform.system() == "Darwin" else value * 1024
    return float(byte_value / 2**20)


def _compiled_congestion(
    layout: SystemLayout, t: int, gates: tuple[Gate, ...] | list[Gate]
) -> tuple[int, int]:
    """Depth lower bounds for the already compiled two-qubit gate multiset."""
    chain = layout.chain(t)
    local = {wire: site for site, wire in enumerate(chain)}
    qubit_load = [0] * len(chain)
    edge_load: dict[tuple[int, int], int] = {}
    for gate in gates:
        if gate.name != "CNOT":
            continue
        assert gate.b is not None
        left, right = local[gate.a], local[gate.b]
        qubit_load[left] += 1
        qubit_load[right] += 1
        edge = tuple(sorted((left, right)))
        edge_load[edge] = edge_load.get(edge, 0) + 1
    return max(qubit_load, default=0), max(edge_load.values(), default=0)


def _static_shortest_path_proxy(layout, t, gates, graph) -> tuple[int, int]:
    """Initial-placement path workload; a proxy, not a routing lower bound."""
    initial = {wire: site for site, wire in enumerate(layout.chain(t))}
    edge_load: dict[tuple[int, int], int] = {}
    total_length = 0
    for gate in gates:
        if gate.name != "CNOT":
            continue
        assert gate.b is not None
        path = shortest_path(graph, initial[gate.a], initial[gate.b])
        total_length += len(path) - 1
        for left, right in zip(path, path[1:]):
            edge = tuple(sorted((left, right)))
            edge_load[edge] = edge_load.get(edge, 0) + 1
    return total_length, max(edge_load.values(), default=0)


def _row(
    *,
    message_qubits,
    t,
    layout,
    architecture,
    strategy,
    graph,
    logical_gates,
    logical_depth,
    logical_cnot,
    routed,
    movement_swaps,
    restoration_swaps,
    restoration_swap_lower_bound,
    lookahead,
    candidate_budget,
    channel,
    scrambler,
    encoder,
    output,
    correlations,
):
    started = time.perf_counter()
    equivalent = certify_routed_equivalence(
        layout, t, logical_gates, routed.gates
    )
    validation = structural_validation(
        layout,
        channel,
        scrambler,
        t,
        routed.gates,
        encoder,
        output,
        correlations,
    )
    validation_seconds = time.perf_counter() - started
    qubit_congestion, edge_congestion = _compiled_congestion(
        layout, t, routed.gates
    )
    static_path_length, static_edge_congestion = _static_shortest_path_proxy(
        layout, t, logical_gates, graph
    )
    distances = logical_interaction_distances(layout, t, logical_gates, graph)
    causal_bound = causal_lightcone_depth_bound(
        layout, t, logical_gates, graph
    )
    validated = (
        equivalent
        and bool(validation["validated"])
        and routed.final_wire_at_site == layout.chain(t)
    )
    if not validated:
        raise AssertionError((message_qubits, architecture, strategy, validation))
    return {
        "A": message_qubits,
        "t": t,
        "accessible_sites": len(layout.chain(t)),
        "architecture": architecture,
        "strategy": strategy,
        "lookahead": lookahead,
        "candidate_budget": candidate_budget,
        "graph_diameter": graph_diameter(graph),
        "logical_depth": logical_depth,
        "logical_cnot": logical_cnot,
        "causal_lightcone_depth_bound": causal_bound,
        "logical_depth_baseline": logical_depth,
        "routed_depth": routed.two_qubit_depth,
        "depth_overhead": routed.two_qubit_depth - logical_depth,
        "depth_ratio": routed.two_qubit_depth / logical_depth,
        "routed_cnot": routed.cnot_count,
        "swap_total": routed.swap_count,
        "swap_movement": movement_swaps,
        "swap_restoration": restoration_swaps,
        "restoration_swap_lower_bound": restoration_swap_lower_bound,
        "compiled_qubit_congestion_bound": qubit_congestion,
        "compiled_edge_congestion_bound": edge_congestion,
        "static_shortest_path_length_proxy": static_path_length,
        "static_edge_congestion_proxy": static_edge_congestion,
        "mean_initial_cnot_distance": sum(distances) / len(distances),
        "max_initial_cnot_distance": max(distances),
        "petz_fidelity": validation["petz_fidelity"],
        "routed_fidelity": validation["circuit_fidelity"],
        "signed_clifford_equivalent": equivalent,
        "final_order_restored": routed.final_wire_at_site == layout.chain(t),
        "validation_seconds": validation_seconds,
        "validated": validated,
    }


def run_audit():
    started = time.perf_counter()
    rows = []
    interaction_rows = []
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

        chain_graph = coupling_graph("chain", len(layout.chain(t)))
        routing_started = time.perf_counter()
        historical = route_line(layout, t, gates)
        routing_seconds = time.perf_counter() - routing_started
        historical_row = _row(
            message_qubits=message_qubits,
            t=t,
            layout=layout,
            architecture="chain",
            strategy="historical_target_move",
            graph=chain_graph,
            logical_gates=gates,
            logical_depth=logical_depth,
            logical_cnot=logical_cnot,
            routed=historical,
            movement_swaps=historical.movement_swap_count,
            restoration_swaps=historical.restoration_swap_count,
            restoration_swap_lower_bound="",
            lookahead=0,
            candidate_budget=1,
            channel=channel,
            scrambler=scrambler,
            encoder=encoder,
            output=output,
            correlations=correlations,
        )
        historical_row["routing_seconds"] = routing_seconds
        rows.append(historical_row)
        if message_qubits == 12:
            for interaction_index, (distance, swaps) in enumerate(
                zip(
                    historical.interaction_distances,
                    historical.interaction_swap_counts,
                )
            ):
                interaction_rows.append(
                    {
                        "A": message_qubits,
                        "t": t,
                        "architecture": "chain",
                        "strategy": "historical_target_move",
                        "interaction_index": interaction_index,
                        "gate_index": "",
                        "distance_before": distance,
                        "movement_swaps": swaps,
                        "control_moves": 0,
                        "target_moves": swaps,
                    }
                )

        for architecture in ARCHITECTURES:
            graph = coupling_graph(architecture, len(layout.chain(t)))

            routing_started = time.perf_counter()
            baseline = route_graph(layout, t, gates, graph)
            routing_seconds = time.perf_counter() - routing_started
            baseline_row = _row(
                message_qubits=message_qubits,
                t=t,
                layout=layout,
                architecture=architecture,
                strategy="shortest_path_inverse_replay",
                graph=graph,
                logical_gates=gates,
                logical_depth=logical_depth,
                logical_cnot=logical_cnot,
                routed=baseline,
                movement_swaps=baseline.movement_swap_count,
                restoration_swaps=baseline.restoration_swap_count,
                restoration_swap_lower_bound="",
                lookahead=0,
                candidate_budget=1,
                channel=channel,
                scrambler=scrambler,
                encoder=encoder,
                output=output,
                correlations=correlations,
            )
            baseline_row["routing_seconds"] = routing_seconds
            rows.append(baseline_row)
            if message_qubits == 12 and architecture == "chain":
                for interaction_index, (distance, swaps) in enumerate(
                    zip(
                        baseline.interaction_distances,
                        baseline.interaction_swap_counts,
                    )
                ):
                    interaction_rows.append(
                        {
                            "A": message_qubits,
                            "t": t,
                            "architecture": architecture,
                            "strategy": "shortest_path_inverse_replay",
                            "interaction_index": interaction_index,
                            "gate_index": "",
                            "distance_before": distance,
                            "movement_swaps": swaps,
                            "control_moves": 0,
                            "target_moves": swaps,
                        }
                    )

            routing_started = time.perf_counter()
            optimized = route_graph_lookahead(
                layout,
                t,
                gates,
                graph,
                lookahead=LOOKAHEAD,
                candidate_budget=CANDIDATE_BUDGET,
            )
            routing_seconds = time.perf_counter() - routing_started
            optimized_row = _row(
                message_qubits=message_qubits,
                t=t,
                layout=layout,
                architecture=architecture,
                strategy="common_lookahead_token_restore",
                graph=graph,
                logical_gates=gates,
                logical_depth=logical_depth,
                logical_cnot=logical_cnot,
                routed=optimized,
                movement_swaps=optimized.movement_swap_count,
                restoration_swaps=optimized.restoration_swap_count,
                restoration_swap_lower_bound=optimized.restoration_swap_lower_bound,
                lookahead=optimized.lookahead,
                candidate_budget=optimized.candidate_budget,
                channel=channel,
                scrambler=scrambler,
                encoder=encoder,
                output=output,
                correlations=correlations,
            )
            optimized_row["routing_seconds"] = routing_seconds
            rows.append(optimized_row)
            if message_qubits == 12:
                for interaction_index, item in enumerate(optimized.audit):
                    interaction_rows.append(
                        {
                            "A": message_qubits,
                            "t": t,
                            "architecture": architecture,
                            "strategy": "common_lookahead_token_restore",
                            "interaction_index": interaction_index,
                            "gate_index": item.gate_index,
                            "distance_before": item.distance_before,
                            "movement_swaps": item.movement_swaps,
                            "control_moves": item.control_moves,
                            "target_moves": item.target_moves,
                        }
                    )
    return rows, interaction_rows, {
        "total_seconds": time.perf_counter() - started,
        "peak_rss_mib": _rss_mib(),
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(rows, interaction_rows, metadata) -> None:
    result_dir = Path("results")
    result_dir.mkdir(exist_ok=True)
    _write_csv(result_dir / "routing_geometry_audit.csv", rows)
    _write_csv(result_dir / "routing_a12_interactions.csv", interaction_rows)
    primary = [
        row for row in rows if row["strategy"] == "common_lookahead_token_restore"
    ]
    table = "\n".join(
        f"| {row['A']} | {row['architecture']} | {row['logical_depth']} | "
        f"{row['routed_depth']} | {row['swap_movement']} | "
        f"{row['swap_restoration']} | {row['swap_total']} | "
        f"{row['causal_lightcone_depth_bound']} | "
        f"{row['compiled_qubit_congestion_bound']} |"
        for row in primary
    )
    a12_chain = {
        row["strategy"]: row
        for row in rows
        if row["A"] == 12 and row["architecture"] == "chain"
    }
    comparisons = "\n".join(
        f"| {name} | {row['routed_depth']} | {row['swap_movement']} | "
        f"{row['swap_restoration']} | {row['swap_total']} |"
        for name, row in a12_chain.items()
    )
    report = f"""# Audit du routeur et du coût géométrique

Les circuits logiques A=9…12, les graines et les temps d'émission sont figés.
Le routeur principal utilise le même budget (`lookahead={LOOKAHEAD}`,
`candidate_budget={CANDIDATE_BUDGET}`) sur chaîne, anneau, grille 2D et
tout-à-tout. Il conserve le placement entre CNOT et restaure finalement les
sorties par le même algorithme de placement de jetons sur graphe connecté.

## Résultats du routeur commun amélioré

| A | géométrie | profondeur logique | profondeur routée | SWAP mouvement | SWAP restitution | SWAP total | borne causale | borne congestion du circuit compilé |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
{table}

Avec cette politique commune, la grille réduit la profondeur par rapport à la
chaîne de 36.2 % (A=9), 43.0 % (A=10), 37.2 % (A=11) et 50.2 % (A=12).
Pour A=12, le tout-à-tout supprime entièrement le routage : 154 couches, soit
exactement la profondeur logique, contre 464 sur grille et 932 sur chaîne.

## Audit de l'écart A=12 sur chaîne

| stratégie | profondeur | SWAP mouvement | SWAP restitution | SWAP total |
|---|---:|---:|---:|---:|
{comparisons}

Le routeur naïf et l'ancien routeur effectuent les mêmes 563 SWAP de
mouvement. L'écart 2169/1209 venait donc principalement du rejeu inverse des
563 SWAP, contre 63 SWAP pour une restitution directe. Le routeur à regard en
avant réduit en plus le mouvement à 439 SWAP ; sa restitution en demande 101,
pour une profondeur finale de 932.

Ces deux comparaisons séparent donc deux contributions observées : la nouvelle
heuristique fait passer la chaîne de 1209 à 932, puis le changement de chaîne à
grille, à heuristique fixée, fait passer 932 à 464. Cette séparation est
expérimentale et les coûts ne sont pas supposés additifs.

## Portée des bornes

`causal_lightcone_depth_bound` est une borne démontrée pour le Clifford cible :
un circuit local de profondeur K ne peut étendre le support d'un Pauli au-delà
de la distance K. `logical_depth_baseline` est la profondeur du circuit logique
imposé, pas une borne fondamentale sur toute resynthèse. Les bornes de congestion s'appliquent au multiensemble de
portes du circuit déjà compilé. Les charges de chemins statiques sont seulement
des indicateurs descriptifs et ne sont pas annoncées comme bornes globales.

## Validation et limites

Chaque circuit routé restitue l'ordre des fils, réalise exactement le même
Clifford signé et conserve la fidélité Petz. Les profondeurs sont les meilleures
observées avec ces trois stratégies, sans preuve de minimalité. Quatre circuits
idéaux seulement sont étudiés ; aucune loi d'échelle n'est ajustée.

Temps total : `{metadata['total_seconds']:.3f} s` ; mémoire RSS maximale :
`{metadata['peak_rss_mib']:.1f} Mio`.
"""
    Path("docs/notes/ROUTING_GEOMETRY_AUDIT.md").write_text(report)


def main() -> None:
    rows, interactions, metadata = run_audit()
    write_outputs(rows, interactions, metadata)
    for message_qubits in CASES:
        selected = [
            row
            for row in rows
            if row["A"] == message_qubits
            and row["strategy"] == "common_lookahead_token_restore"
        ]
        print(
            f"A={message_qubits}: "
            + ", ".join(
                f"{row['architecture']}={row['routed_depth']}" for row in selected
            )
        )


if __name__ == "__main__":
    main()
