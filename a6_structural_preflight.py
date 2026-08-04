#!/usr/bin/env python3
"""One budgeted collective A=6 preflight using structural certification."""
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


def run_preflight():
    started = time.perf_counter()
    initial_rss = _rss_mib()
    timings: dict[str, float] = {}
    previous_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, MAX_SECONDS)
    try:
        layout = SystemLayout(n_message=6, n_black_hole=4)
        scrambler = random_scrambler(
            layout, np.random.default_rng(SEED), SCRAMBLE_DEPTH
        )
        timeline = []
        selected_channel = None
        selected_row = None
        timeline_started = time.perf_counter()
        for t in range(len(layout.scrambled) + 1):
            step_started = time.perf_counter()
            channel = channel_at_time_compact(layout, scrambler, t)
            petz_fidelity, petz_info = entanglement_fidelity(channel)
            decoupling = pure_stabilizer_decoupling(
                scrambler,
                layout.n_qubits,
                layout.R_register,
                layout.A_register,
                layout.B,
                layout.E,
                t,
            )
            row = {
                "t": t,
                "accessible_qubits": len(layout.X(t)),
                "inaccessible_qubits": len(layout.C(t)),
                "support_rank": petz_info["support_dimension"],
                "old_operator_checks_theoretical": int(
                    petz_info["support_dimension"]
                )
                ** 2,
                "mutual_information_R_C_bits": decoupling[
                    "mutual_information_bits"
                ],
                "trace_distance_rhoRC_product": decoupling[
                    "trace_distance_product"
                ],
                "petz_entanglement_fidelity": petz_fidelity,
                "support_trace_preservation_error": petz_info[
                    "support_trace_preservation_error"
                ],
                "elapsed_seconds": time.perf_counter() - step_started,
                "peak_rss_mib": _rss_mib(),
            }
            timeline.append(row)
            if selected_channel is None and petz_fidelity > FIDELITY_THRESHOLD:
                selected_channel = channel
                selected_row = row
            _check_budget(started, f"timeline t={t}")
        timings["timeline_seconds"] = time.perf_counter() - timeline_started
        if selected_channel is None or selected_row is None:
            metadata = {
                "status": "no_time_above_threshold",
                "message_qubits": 6,
                "alphabet_size": 64,
                "seed": SEED,
                "scramble_depth": SCRAMBLE_DEPTH,
                "synthesis_attempted": False,
                "routing_attempted": False,
                "total_seconds": time.perf_counter() - started,
                "peak_rss_mib": _rss_mib(),
            }
            return timeline, metadata

        selected_t = int(selected_row["t"])
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
                    layout, selected_channel, scrambler, selected_t
                ),
            )
        with count_operations() as direct_certificate_operations:
            direct = _timed(
                "direct_certification_seconds",
                started,
                timings,
                lambda: structural_validation(
                    layout,
                    selected_channel,
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
        with count_operations() as routed_certificate_operations:
            routed_validation = _timed(
                "routed_certification_seconds",
                started,
                timings,
                lambda: structural_validation(
                    layout,
                    selected_channel,
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
        counters = (
            support_operations,
            synthesis_operations,
            direct_certificate_operations,
            routed_certificate_operations,
        )
        total_seconds = time.perf_counter() - started
        peak_rss = _rss_mib()
        support_rank_numeric = int(selected_row["support_rank"])
        support_rank_stabilizer = int(code["support_dimension"])
        checks = (
            support_rank_numeric == support_rank_stabilizer,
            bool(direct["certified"]),
            bool(routed_validation["certified"]),
            bool(direct["reduced_choi_equal"]),
            routed_equal,
            routed.final_wire_at_site == layout.chain(selected_t),
            abs(float(direct["circuit_fidelity"]) - float(direct["petz_fidelity"]))
            < TOLERANCE,
            abs(
                float(routed_validation["circuit_fidelity"])
                - float(direct["petz_fidelity"])
            )
            < TOLERANCE,
            total_seconds <= MAX_SECONDS,
            peak_rss <= MAX_RSS_MIB,
        )
        validated = all(checks)
        metadata = {
            "status": "validated" if validated else "failed_validation",
            "message_qubits": layout.n_message,
            "alphabet_size": 1 << layout.n_message,
            "black_hole_qubits": layout.n_black_hole,
            "total_simulated_qubits": layout.n_qubits,
            "seed": SEED,
            "scramble_depth": SCRAMBLE_DEPTH,
            "selected_t": selected_t,
            "selected_mutual_information_bits": selected_row[
                "mutual_information_R_C_bits"
            ],
            "selected_trace_distance": selected_row[
                "trace_distance_rhoRC_product"
            ],
            "support_rank_numeric": support_rank_numeric,
            "support_rank_stabilizer": support_rank_stabilizer,
            "support_logical_qubits": code["logical_qubits"],
            "environment_qubits": len(output) - int(code["logical_qubits"]),
            "petz_fidelity": direct["petz_fidelity"],
            "direct_circuit_fidelity": direct["circuit_fidelity"],
            "routed_circuit_fidelity": routed_validation["circuit_fidelity"],
            "choi_fidelity_certified": direct["choi_fidelity_certified"],
            "reduced_choi_equal": direct["reduced_choi_equal"],
            "environment_isometry": direct["environment_isometry"],
            "signed_generators_checked": direct["target_generator_count"],
            # The historical correlation path expanded the full purified Choi
            # stabilizer group. Its qubit count is A' + (X+C) = 2A+2B.
            "old_group_size_avoided": 1 << layout.n_qubits,
            "old_operator_checks_avoided": support_rank_numeric**2,
            "group_elements_enumerated": direct[
                "stabilizer_group_elements_enumerated"
            ],
            "support_operators_enumerated": direct[
                "support_operators_enumerated"
            ],
            "support_kernel_variables": code["gf2_kernel_variables"],
            "support_kernel_constraints": code["gf2_kernel_constraints"],
            "support_kernel_constraint_rank": code[
                "gf2_kernel_constraint_rank"
            ],
            "support_kernel_dimension": code["gf2_kernel_dimension"],
            "centralizer_dimension": code["gf2_centralizer_dimension"],
            "logical_quotient_dimension": code[
                "gf2_logical_quotient_dimension"
            ],
            "gf2_affine_systems_solved": sum(
                counter.affine_systems_solved for counter in counters
            ),
            "gf2_scalar_bit_xors": sum(
                counter.scalar_bit_xors for counter in counters
            ),
            "logical_depth": two_qubit_depth(direct_gates, layout.n_qubits),
            "logical_cnot": sum(gate.name == "CNOT" for gate in direct_gates),
            "routed_depth": routed.two_qubit_depth,
            "routed_cnot": routed.cnot_count,
            "swap": routed.swap_count,
            "routed_clifford_equal": routed_equal,
            "final_order_restored": routed.final_wire_at_site
            == layout.chain(selected_t),
            "compact_channel_workspace_qubits": (
                layout.n_message + 2 * layout.n_black_hole
            ),
            "full_unused_reference_workspace_qubits_avoided": layout.n_message,
            **timings,
            "total_seconds": total_seconds,
            "initial_rss_mib": initial_rss,
            "peak_rss_mib": peak_rss,
            "memory_headroom_mib": MAX_RSS_MIB - peak_rss,
            "memory_budget_fraction": peak_rss / MAX_RSS_MIB,
            "max_seconds_budget": MAX_SECONDS,
            "max_rss_budget_mib": MAX_RSS_MIB,
            "first_new_bottleneck": (
                "memory_pressure_physical_state_vector_validation"
                if validated and peak_rss > 0.8 * MAX_RSS_MIB
                else (
                    "none_within_fixed_budget"
                    if validated
                    else "validation_or_budget"
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
    _write_csv(output / "a6_structural_preflight_timeline.csv", timeline)
    _write_csv(output / "a6_structural_preflight_resources.csv", [metadata])
    timeline_lines = "\n".join(
        "| {t} | {mutual_information_R_C_bits} | "
        "{trace_distance_rhoRC_product:.12g} | "
        "{petz_entanglement_fidelity:.15g} | {support_rank} | "
        "{elapsed_seconds:.3f} | {peak_rss_mib:.1f} |".format(**row)
        for row in timeline
    )
    if metadata["status"] == "no_time_above_threshold":
        result_section = "Aucun temps ne dépasse le seuil Petz 0,99 ; synthèse non lancée."
    else:
        result_section = f"""Le premier temps avec `F_Petz>0,99` est
`t={metadata['selected_t']}`. À ce temps :

- `I(R:C)={metadata['selected_mutual_information_bits']}` ;
- distance de trace `{metadata['selected_trace_distance']}` ;
- fidélité Petz `{metadata['petz_fidelity']:.15g}` ;
- fidélité directe `{metadata['direct_circuit_fidelity']:.15g}` ;
- fidélité routée `{metadata['routed_circuit_fidelity']:.15g}` ;
- profondeur `{metadata['logical_depth']} -> {metadata['routed_depth']}` ;
- CNOT `{metadata['logical_cnot']} -> {metadata['routed_cnot']}`,
  SWAP `{metadata['swap']}`.

Le certificat compare {metadata['signed_generators_checked']} générateurs
signés. Les Choi réduits sont égaux : `{metadata['reduced_choi_equal']}` ; dans
la jauge fixée, l'isométrie d'environnement est
`{metadata['environment_isometry']}`. Les anciennes énumérations théoriques de
{metadata['old_group_size_avoided']} éléments et
{metadata['old_operator_checks_avoided']} opérateurs sont remplacées par zéro
énumération exhaustive.
"""
    report = f"""# Pré-vol structurel collectif |A|=6

Statut : **{'validé' if metadata['status'] == 'validated' else metadata['status']}**. Instance unique, budget strict
{MAX_SECONDS:.0f} s / {MAX_RSS_MIB:.0f} Mio. Aucun A=7 n'est lancé.

## Configuration

- message collectif : 6 qubits, dimension 64 ;
- B=4, graine {SEED}, profondeur de brouillage {SCRAMBLE_DEPTH} ;
- un seul brouilleur Clifford connecté et une seule dynamique collective ;
- construction du canal dans l'espace compact A+B+E, préalablement régressée
  contre le chemin incluant le registre R inutilisé.

## Chronologie

| t | I(R:C) | distance trace | fidélité Petz | rang support | secondes | RSS Mio |
|---:|---:|---:|---:|---:|---:|---:|
{timeline_lines}

## Résultat

{result_section}

## Ressources

Temps total : `{metadata['total_seconds']:.3f} s` ; RSS maximale :
`{metadata['peak_rss_mib']:.1f} Mio`. Synthèse :
`{metadata.get('synthesis_seconds', 0):.3f} s` ; certification directe/routée :
`{metadata.get('direct_certification_seconds', 0):.3f} s` /
`{metadata.get('routed_certification_seconds', 0):.3f} s` ; routage :
`{metadata.get('routing_seconds', 0):.6f} s`.

Premier nouveau goulot : `{metadata.get('first_new_bottleneck', 'not_applicable')}`.
La RSS atteint {metadata.get('memory_budget_fraction', 0):.1%} du budget, avec
seulement {metadata.get('memory_headroom_mib', 0):.1f} Mio de marge. Il s'agit
d'une pression de calcul du modèle fini, pas d'une difficulté physique démontrée.

## Limites

Ce pré-vol ne concerne qu'une instance idéale. Il ne montre pas que toutes les
instances A=6 passent, ne définit aucune loi de coût et ne prédit pas A=7. La
dimension 64 décrit un alphabet logique possible ; aucun contenu sémantique,
chiffrement ou avantage physique général n'est revendiqué.
"""
    Path("docs/notes/A6_STRUCTURAL_PREFLIGHT.md").write_text(report)


def main() -> None:
    timeline, metadata = run_preflight()
    write_outputs(timeline, metadata)
    print(
        f"A=6 structural preflight: status={metadata['status']}; "
        f"t={metadata.get('selected_t', 'none')}; "
        f"Petz={metadata.get('petz_fidelity', float('nan')):.15g}"
    )
    if metadata["status"] == "validated":
        print(
            f"direct={metadata['direct_circuit_fidelity']:.15g}; "
            f"routed={metadata['routed_circuit_fidelity']:.15g}; "
            f"depth={metadata['logical_depth']}->{metadata['routed_depth']}; "
            f"elapsed={metadata['total_seconds']:.3f}s; "
            f"RSS={metadata['peak_rss_mib']:.1f}MiB"
        )


if __name__ == "__main__":
    main()
