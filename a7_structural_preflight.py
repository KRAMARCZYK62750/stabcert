#!/usr/bin/env python3
"""Single budgeted A=7 preflight after state-free validation regression."""
from __future__ import annotations

import csv
from pathlib import Path
import platform
import resource
import signal
import time

import numpy as np

from hayden_preskill_toy.gf2 import count_operations
from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_certificate import (
    certify_routed_equivalence,
    structural_validation,
)
from hayden_preskill_toy.parametric_channels import (
    channel_at_time_compact,
    random_scrambler,
)
from hayden_preskill_toy.parametric_petz import entanglement_fidelity
from hayden_preskill_toy.parametric_routing import route_line, two_qubit_depth
from hayden_preskill_toy.parametric_stabilizer import input_support_code
from hayden_preskill_toy.parametric_synthesis import signed_dilation
from hayden_preskill_toy.stabilizer import pure_stabilizer_decoupling


SEED = 20260802
SCRAMBLE_DEPTH = 6
FIDELITY_THRESHOLD = 0.99
TOLERANCE = 1e-12
MAX_SECONDS = 120.0
MAX_RSS_MIB = 1024.0


class BudgetExceeded(RuntimeError):
    pass


def _rss_mib() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    byte_value = value if platform.system() == "Darwin" else value * 1024
    return float(byte_value / 2**20)


def _alarm_handler(_signum, _frame) -> None:
    raise BudgetExceeded(f"wall-time budget exceeded ({MAX_SECONDS:.0f} s)")


def _check_budget(started: float, stage: str) -> None:
    elapsed = time.perf_counter() - started
    rss = _rss_mib()
    if elapsed > MAX_SECONDS:
        raise BudgetExceeded(f"time budget exceeded after {stage}: {elapsed:.3f} s")
    if rss > MAX_RSS_MIB:
        raise BudgetExceeded(f"RSS budget exceeded after {stage}: {rss:.1f} MiB")


def _timed(stage: str, started: float, timings: dict[str, float], function):
    stage_started = time.perf_counter()
    result = function()
    timings[stage] = time.perf_counter() - stage_started
    _check_budget(started, stage)
    return result


def _connected(layout: SystemLayout, gates) -> bool:
    adjacency = {qubit: set() for qubit in layout.scrambled}
    for gate in gates:
        if gate.name == "CNOT":
            adjacency[gate.a].add(gate.b)
            adjacency[gate.b].add(gate.a)
    reached = {layout.scrambled[0]}
    pending = list(reached)
    while pending:
        current = pending.pop()
        for neighbour in adjacency[current] - reached:
            reached.add(neighbour)
            pending.append(neighbour)
    return reached == set(layout.scrambled)


def run_preflight():
    started = time.perf_counter()
    initial_rss = _rss_mib()
    timings: dict[str, float] = {}
    previous_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, MAX_SECONDS)
    try:
        layout = SystemLayout(n_message=7, n_black_hole=4)
        scrambler = random_scrambler(
            layout, np.random.default_rng(SEED), SCRAMBLE_DEPTH
        )
        if not _connected(layout, scrambler):
            raise AssertionError("A7 scrambler is not connected")

        timeline = []
        timeline_started = time.perf_counter()
        for t in range(len(layout.scrambled) + 1):
            step_started = time.perf_counter()
            decoupling = pure_stabilizer_decoupling(
                scrambler,
                layout.n_qubits,
                layout.R_register,
                layout.A_register,
                layout.B,
                layout.E,
                t,
            )
            code = input_support_code(layout, scrambler, t)
            petz_rank_fidelity = 2.0 ** (
                -int(decoupling["mutual_information_bits"])
            )
            timeline.append(
                {
                    "t": t,
                    "accessible_qubits": len(layout.X(t)),
                    "inaccessible_qubits": len(layout.C(t)),
                    "support_rank_stabilizer": code["support_dimension"],
                    "old_operator_checks_theoretical": int(
                        code["support_dimension"]
                    )
                    ** 2,
                    "mutual_information_R_C_bits": decoupling[
                        "mutual_information_bits"
                    ],
                    "trace_distance_rhoRC_product": decoupling[
                        "trace_distance_product"
                    ],
                    "petz_fidelity_from_pure_clifford_ranks": petz_rank_fidelity,
                    "elapsed_seconds": time.perf_counter() - step_started,
                    "peak_rss_mib": _rss_mib(),
                }
            )
            _check_budget(started, f"structural timeline t={t}")
        timings["structural_timeline_seconds"] = time.perf_counter() - timeline_started
        selected = next(
            (
                row
                for row in timeline
                if row["petz_fidelity_from_pure_clifford_ranks"]
                > FIDELITY_THRESHOLD
            ),
            None,
        )
        if selected is None:
            raise RuntimeError("no A7 emission time reaches the Petz threshold")
        selected_t = int(selected["t"])

        channel = _timed(
            "selected_channel_seconds",
            started,
            timings,
            lambda: channel_at_time_compact(layout, scrambler, selected_t),
        )
        petz_dense_fidelity, petz_info = _timed(
            "petz_dense_crosscheck_seconds",
            started,
            timings,
            lambda: entanglement_fidelity(channel),
        )
        with count_operations() as support_operations:
            code = _timed(
                "support_code_seconds",
                started,
                timings,
                lambda: input_support_code(layout, scrambler, selected_t),
            )
        with count_operations() as synthesis_operations:
            direct_gates, encoder, output, rows = _timed(
                "synthesis_seconds",
                started,
                timings,
                lambda: signed_dilation(
                    layout, channel, scrambler, selected_t
                ),
            )
        with count_operations() as direct_operations:
            direct = _timed(
                "direct_certificate_seconds",
                started,
                timings,
                lambda: structural_validation(
                    layout,
                    channel,
                    scrambler,
                    selected_t,
                    direct_gates,
                    encoder,
                    output,
                    rows,
                ),
            )
        routed = _timed(
            "routing_seconds",
            started,
            timings,
            lambda: route_line(layout, selected_t, direct_gates),
        )
        with count_operations() as routed_operations:
            routed_metrics = _timed(
                "routed_certificate_seconds",
                started,
                timings,
                lambda: structural_validation(
                    layout,
                    channel,
                    scrambler,
                    selected_t,
                    routed.gates,
                    encoder,
                    output,
                    rows,
                ),
            )
        routed_equal = certify_routed_equivalence(
            layout, selected_t, direct_gates, routed.gates
        )
        rank_fidelity = float(selected["petz_fidelity_from_pure_clifford_ranks"])
        total_seconds = time.perf_counter() - started
        peak_rss = _rss_mib()
        counters = (
            support_operations,
            synthesis_operations,
            direct_operations,
            routed_operations,
        )
        checks = {
            "support_rank_matches": int(code["support_dimension"])
            == int(petz_info["support_dimension"]),
            "dense_petz_matches_rank": abs(petz_dense_fidelity - rank_fidelity)
            < TOLERANCE,
            "direct_matches_rank_petz": abs(
                float(direct["circuit_fidelity"]) - rank_fidelity
            )
            < TOLERANCE,
            "routed_matches_rank_petz": abs(
                float(routed_metrics["circuit_fidelity"]) - rank_fidelity
            )
            < TOLERANCE,
            "direct_certificate": bool(direct["certified"]),
            "routed_certificate": bool(routed_metrics["certified"]),
            "reduced_choi_equal": bool(direct["reduced_choi_equal"]),
            "signed_phases": bool(
                direct["entanglement_phases_match_on_intersection"]
            ),
            "state_free_direct": int(
                direct["entanglement_dense_state_amplitudes_constructed"]
            )
            == 0,
            "state_free_routed": int(
                routed_metrics["entanglement_dense_state_amplitudes_constructed"]
            )
            == 0,
            "routed_equal": routed_equal,
            "final_order_restored": routed.final_wire_at_site
            == layout.chain(selected_t),
            "time_budget": total_seconds <= MAX_SECONDS,
            "rss_budget": peak_rss <= MAX_RSS_MIB,
        }
        validated = all(checks.values())
        metadata = {
            "status": "validated" if validated else "failed_validation",
            "message_qubits": layout.n_message,
            "alphabet_size": 1 << layout.n_message,
            "black_hole_qubits": layout.n_black_hole,
            "total_simulated_qubits": layout.n_qubits,
            "seed": SEED,
            "scramble_depth": SCRAMBLE_DEPTH,
            "scrambler_connected": True,
            "selected_t": selected_t,
            "selected_mutual_information_bits": selected[
                "mutual_information_R_C_bits"
            ],
            "selected_trace_distance": selected[
                "trace_distance_rhoRC_product"
            ],
            "support_rank_numeric": petz_info["support_dimension"],
            "support_rank_stabilizer": code["support_dimension"],
            "support_logical_qubits": code["logical_qubits"],
            "environment_qubits": len(output) - int(code["logical_qubits"]),
            "petz_fidelity_from_ranks": rank_fidelity,
            "petz_fidelity_dense_crosscheck": petz_dense_fidelity,
            "direct_circuit_fidelity_structural": direct["circuit_fidelity"],
            "routed_circuit_fidelity_structural": routed_metrics[
                "circuit_fidelity"
            ],
            "choi_fidelity_certified": direct["choi_fidelity_certified"],
            "reduced_choi_equal": direct["reduced_choi_equal"],
            "environment_isometry": direct["environment_isometry"],
            "signed_phases_validated": direct[
                "entanglement_phases_match_on_intersection"
            ],
            "signed_generators_checked": direct["target_generator_count"],
            "entanglement_intersection_rank": direct[
                "entanglement_intersection_rank"
            ],
            "dense_validation_state_amplitudes": direct[
                "entanglement_dense_state_amplitudes_constructed"
            ],
            "dense_validation_reduced_entries": direct[
                "entanglement_dense_reduced_matrices_constructed"
            ],
            "old_group_size_avoided": 1 << layout.n_qubits,
            "old_operator_checks_avoided": int(code["support_dimension"]) ** 2,
            "group_elements_enumerated": direct[
                "stabilizer_group_elements_enumerated"
            ],
            "support_operators_enumerated": direct[
                "support_operators_enumerated"
            ],
            "logical_depth": two_qubit_depth(direct_gates, layout.n_qubits),
            "logical_cnot": sum(gate.name == "CNOT" for gate in direct_gates),
            "routed_depth": routed.two_qubit_depth,
            "routed_cnot": routed.cnot_count,
            "swap": routed.swap_count,
            "routed_clifford_equal": routed_equal,
            "final_order_restored": routed.final_wire_at_site
            == layout.chain(selected_t),
            "gf2_affine_systems_solved": sum(
                counter.affine_systems_solved for counter in counters
            ),
            "gf2_scalar_bit_xors": sum(
                counter.scalar_bit_xors for counter in counters
            ),
            "dense_channel_used_at_selected_t": True,
            "dense_choi_used_during_synthesis": True,
            **timings,
            "total_seconds": total_seconds,
            "initial_rss_mib": initial_rss,
            "peak_rss_mib": peak_rss,
            "memory_headroom_mib": MAX_RSS_MIB - peak_rss,
            "memory_budget_fraction": peak_rss / MAX_RSS_MIB,
            "max_seconds_budget": MAX_SECONDS,
            "max_rss_budget_mib": MAX_RSS_MIB,
            "first_new_bottleneck": (
                "dense_channel_and_choi_synthesis_memory"
                if validated and peak_rss > 0.8 * MAX_RSS_MIB
                else (
                    "none_within_fixed_budget"
                    if validated
                    else ";".join(name for name, passed in checks.items() if not passed)
                )
            ),
        }
        return timeline, metadata
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(timeline, metadata) -> None:
    output = Path("results")
    output.mkdir(exist_ok=True)
    _write_csv(output / "a7_structural_preflight_timeline.csv", timeline)
    _write_csv(output / "a7_structural_preflight_resources.csv", [metadata])
    timeline_lines = "\n".join(
        "| {t} | {mutual_information_R_C_bits} | "
        "{trace_distance_rhoRC_product:.12g} | "
        "{petz_fidelity_from_pure_clifford_ranks:.15g} | "
        "{support_rank_stabilizer} | {elapsed_seconds:.4f} |".format(**row)
        for row in timeline
    )
    report = f"""# Pré-vol structurel collectif |A|=7

Statut : **{'validé' if metadata['status'] == 'validated' else metadata['status']}**.
Instance unique, budget strict {MAX_SECONDS:.0f} s / {MAX_RSS_MIB:.0f} Mio.
Aucun A=8 n'est lancé.

## Configuration

- message collectif : 7 qubits, dimension 128 ;
- B=4, graine {SEED}, profondeur {SCRAMBLE_DEPTH} ;
- brouilleur Clifford unique et connecté ;
- chronologie calculée uniquement par rangs stabilisateurs ;
- canal dense construit seulement au temps finalement sélectionné.

## Chronologie structurelle

| t | I(R:C) | distance trace | fidélité Petz par rangs | rang support | secondes |
|---:|---:|---:|---:|---:|---:|
{timeline_lines}

Le premier temps avec `F_Petz>0,99` est `t={metadata['selected_t']}` :
`I(R:C)={metadata['selected_mutual_information_bits']}` et distance
`{metadata['selected_trace_distance']}`.

## Validation du récupérateur

| quantité | valeur |
|---|---:|
| Petz par rangs stabilisateurs | {metadata['petz_fidelity_from_ranks']:.15g} |
| Petz dense, contrôle indépendant | {metadata['petz_fidelity_dense_crosscheck']:.15g} |
| circuit Clifford direct | {metadata['direct_circuit_fidelity_structural']:.15g} |
| circuit Clifford routé | {metadata['routed_circuit_fidelity_structural']:.15g} |
| fidélité Choi certifiée | {metadata['choi_fidelity_certified']} |

La validation d'intrication construit
`{metadata['dense_validation_state_amplitudes']}` amplitude dense et
`{metadata['dense_validation_reduced_entries']}` entrée de matrice réduite.
Les phases signées sont compatibles : `{metadata['signed_phases_validated']}` ;
les Choi réduits sont égaux : `{metadata['reduced_choi_equal']}`.

Les anciennes énumérations théoriques de
{metadata['old_group_size_avoided']} éléments de groupe et
{metadata['old_operator_checks_avoided']} opérateurs sont évitées.

## Ressources construites

| réalisation | profondeur 2q | CNOT | SWAP |
|---|---:|---:|---:|
| Clifford direct | {metadata['logical_depth']} | {metadata['logical_cnot']} | 0 |
| chaîne locale | {metadata['routed_depth']} | {metadata['routed_cnot']} | {metadata['swap']} |

Temps total : `{metadata['total_seconds']:.3f} s` ; RSS maximale :
`{metadata['peak_rss_mib']:.1f} Mio` ({metadata['memory_budget_fraction']:.1%}
du budget). Marge : `{metadata['memory_headroom_mib']:.1f} Mio`.

Premier nouveau goulot : `{metadata['first_new_bottleneck']}`.

## Limites

La validation est entièrement stabilisatrice et sans état dense. En revanche,
le contrôle Petz indépendant et l'extraction Choi utilisée pendant la synthèse
emploient encore des matrices/vecteurs denses au seul temps sélectionné. Cette
instance ne prouve ni que toutes les instances A=7 passent, ni une loi de coût,
ni la faisabilité de A=8, ni une propriété cryptographique.
"""
    Path("docs/notes/A7_STRUCTURAL_PREFLIGHT.md").write_text(report)


def main() -> None:
    timeline, metadata = run_preflight()
    write_outputs(timeline, metadata)
    print(
        f"A=7 structural preflight: status={metadata['status']}; "
        f"t={metadata['selected_t']}; "
        f"Petz={metadata['petz_fidelity_from_ranks']:.15g}; "
        f"direct={metadata['direct_circuit_fidelity_structural']:.15g}; "
        f"routed={metadata['routed_circuit_fidelity_structural']:.15g}"
    )
    print(
        f"depth={metadata['logical_depth']}->{metadata['routed_depth']}; "
        f"SWAP={metadata['swap']}; elapsed={metadata['total_seconds']:.3f}s; "
        f"RSS={metadata['peak_rss_mib']:.1f}MiB"
    )


if __name__ == "__main__":
    main()
