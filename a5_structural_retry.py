#!/usr/bin/env python3
"""Budgeted A=5 retry using generator-level symplectic certification."""
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
from hayden_preskill_toy.parametric_channels import channel_at_time, random_scrambler
from hayden_preskill_toy.parametric_petz import entanglement_fidelity, support_rank
from hayden_preskill_toy.parametric_routing import route_line, two_qubit_depth
from hayden_preskill_toy.parametric_stabilizer import input_support_code
from hayden_preskill_toy.parametric_synthesis import signed_dilation


SEED = 20260802
SCRAMBLE_DEPTH = 6
SELECTED_T = 5
TOLERANCE = 1e-12
MAX_SECONDS = 120.0
MAX_RSS_MIB = 1024.0


class BudgetExceeded(RuntimeError):
    """Raised when the fixed A=5 wall-time or RSS budget is exceeded."""


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
        raise BudgetExceeded(
            f"wall-time budget exceeded after {stage}: {elapsed:.3f} s"
        )
    if rss > MAX_RSS_MIB:
        raise BudgetExceeded(f"RSS budget exceeded after {stage}: {rss:.1f} MiB")


def _timed(stage: str, started: float, timings: dict[str, float], function):
    stage_started = time.perf_counter()
    result = function()
    timings[stage] = time.perf_counter() - stage_started
    _check_budget(started, stage)
    return result


def run_retry() -> dict[str, object]:
    started = time.perf_counter()
    initial_rss = _rss_mib()
    timings: dict[str, float] = {}
    previous_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, MAX_SECONDS)
    try:
        layout = SystemLayout(n_message=5, n_black_hole=4)
        scrambler = random_scrambler(
            layout, np.random.default_rng(SEED), SCRAMBLE_DEPTH
        )
        channel = _timed(
            "channel_seconds",
            started,
            timings,
            lambda: channel_at_time(layout, scrambler, SELECTED_T),
        )
        petz_fidelity, petz_info = _timed(
            "petz_seconds",
            started,
            timings,
            lambda: entanglement_fidelity(channel),
        )
        with count_operations() as support_operations:
            code = _timed(
                "support_code_seconds",
                started,
                timings,
                lambda: input_support_code(layout, scrambler, SELECTED_T),
            )
        with count_operations() as synthesis_operations:
            synthesis = _timed(
                "synthesis_seconds",
                started,
                timings,
                lambda: signed_dilation(layout, channel, scrambler, SELECTED_T),
            )
        direct_gates, encoder, output, rows = synthesis
        with count_operations() as direct_certificate_operations:
            direct_validation = _timed(
                "direct_certification_seconds",
                started,
                timings,
                lambda: structural_validation(
                    layout,
                    channel,
                    scrambler,
                    SELECTED_T,
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
            lambda: route_line(layout, SELECTED_T, direct_gates),
        )
        with count_operations() as routed_certificate_operations:
            routed_validation = _timed(
                "routed_certification_seconds",
                started,
                timings,
                lambda: structural_validation(
                    layout,
                    channel,
                    scrambler,
                    SELECTED_T,
                    routed.gates,
                    encoder,
                    output,
                    rows,
                ),
            )
        routed_equivalent = certify_routed_equivalence(
            layout, SELECTED_T, direct_gates, routed.gates
        )
        support_rank_numeric = support_rank(channel)
        support_rank_stabilizer = int(code["support_dimension"])
        environment_qubits = len(output) - int(code["logical_qubits"])
        operation_counters = (
            support_operations,
            synthesis_operations,
            direct_certificate_operations,
            routed_certificate_operations,
        )
        total_seconds = time.perf_counter() - started
        peak_rss = _rss_mib()

        discrete_checks = {
            "support_dimensions_match": support_rank_numeric
            == support_rank_stabilizer,
            "signed_generator_certificate": bool(
                direct_validation["signed_generator_groups_equal"]
            ),
            "reduced_choi_equal": bool(direct_validation["reduced_choi_equal"]),
            "routed_clifford_equal": bool(routed_equivalent),
            "final_order_restored": routed.final_wire_at_site
            == layout.chain(SELECTED_T),
            "zero_group_enumeration": int(
                direct_validation["stabilizer_group_elements_enumerated"]
            )
            == 0,
            "zero_operator_enumeration": int(
                direct_validation["support_operators_enumerated"]
            )
            == 0,
        }
        numeric_checks = {
            "direct_matches_petz": abs(
                float(direct_validation["circuit_fidelity"]) - petz_fidelity
            )
            < TOLERANCE,
            "routed_matches_petz": abs(
                float(routed_validation["circuit_fidelity"]) - petz_fidelity
            )
            < TOLERANCE,
            "support_trace_preserved": float(
                petz_info["support_trace_preservation_error"]
            )
            < TOLERANCE,
        }
        validated = (
            all(discrete_checks.values())
            and all(numeric_checks.values())
            and bool(direct_validation["validated"])
            and bool(routed_validation["validated"])
            and total_seconds <= MAX_SECONDS
            and peak_rss <= MAX_RSS_MIB
        )
        result: dict[str, object] = {
            "status": "validated" if validated else "failed_validation",
            "message_qubits": layout.n_message,
            "alphabet_size": 1 << layout.n_message,
            "black_hole_qubits": layout.n_black_hole,
            "seed": SEED,
            "scramble_depth": SCRAMBLE_DEPTH,
            "t": SELECTED_T,
            "support_rank_numeric": support_rank_numeric,
            "support_rank_stabilizer": support_rank_stabilizer,
            "support_logical_qubits": code["logical_qubits"],
            "environment_qubits": environment_qubits,
            "petz_fidelity": petz_fidelity,
            "direct_circuit_fidelity": direct_validation["circuit_fidelity"],
            "routed_circuit_fidelity": routed_validation["circuit_fidelity"],
            "direct_choi_fidelity_certified": direct_validation[
                "choi_fidelity_certified"
            ],
            "routed_choi_fidelity_certified": routed_validation[
                "choi_fidelity_certified"
            ],
            "direct_certificate_error": 0.0
            if direct_validation["certified"]
            else 1.0,
            "routed_certificate_error": 0.0
            if routed_validation["certified"]
            else 1.0,
            "target_generators_checked": direct_validation[
                "target_generator_count"
            ],
            "candidate_generators_checked": direct_validation[
                "candidate_generator_count"
            ],
            "support_kernel_variables": code["gf2_kernel_variables"],
            "support_kernel_constraints": code["gf2_kernel_constraints"],
            "support_kernel_constraint_rank": code[
                "gf2_kernel_constraint_rank"
            ],
            "support_kernel_dimension": code["gf2_kernel_dimension"],
            "support_stabilizer_rank": code["independent_stabilizers"],
            "centralizer_dimension": code["gf2_centralizer_dimension"],
            "logical_quotient_dimension": code[
                "gf2_logical_quotient_dimension"
            ],
            "choi_affine_variables": rows[0]["gf2_variables"],
            "choi_affine_constraints": rows[0]["gf2_constraints"],
            "choi_affine_constraint_rank": rows[0]["gf2_constraint_rank"],
            "choi_affine_kernel_dimension": rows[0][
                "gf2_affine_kernel_dimension"
            ],
            "gf2_affine_systems_solved": sum(
                counter.affine_systems_solved for counter in operation_counters
            ),
            "gf2_rank_reductions": sum(
                counter.rank_reductions for counter in operation_counters
            ),
            "gf2_pivots": sum(counter.pivots for counter in operation_counters),
            "gf2_row_xors": sum(counter.row_xors for counter in operation_counters),
            "gf2_scalar_bit_xors": sum(
                counter.scalar_bit_xors for counter in operation_counters
            ),
            "old_group_size_avoided": 1
            << (len(output) + int(code["logical_qubits"])),
            "old_operator_checks_avoided": support_rank_numeric**2,
            "group_elements_enumerated": direct_validation[
                "stabilizer_group_elements_enumerated"
            ],
            "support_operators_enumerated": direct_validation[
                "support_operators_enumerated"
            ],
            "logical_depth": two_qubit_depth(direct_gates, layout.n_qubits),
            "logical_cnot": sum(gate.name == "CNOT" for gate in direct_gates),
            "routed_depth": routed.two_qubit_depth,
            "routed_cnot": routed.cnot_count,
            "swap": routed.swap_count,
            "routed_clifford_equal": routed_equivalent,
            "final_order_restored": routed.final_wire_at_site
            == layout.chain(SELECTED_T),
            "support_dimensions_match": discrete_checks[
                "support_dimensions_match"
            ],
            "signed_generator_certificate": discrete_checks[
                "signed_generator_certificate"
            ],
            "reduced_choi_equal": discrete_checks["reduced_choi_equal"],
            "environment_isometry": direct_validation["environment_isometry"],
            "support_trace_preservation_error": petz_info[
                "support_trace_preservation_error"
            ],
            **timings,
            "total_seconds": total_seconds,
            "initial_rss_mib": initial_rss,
            "peak_rss_mib": peak_rss,
            "max_seconds_budget": MAX_SECONDS,
            "max_rss_budget_mib": MAX_RSS_MIB,
        }
        if not validated:
            failed = [
                name
                for name, passed in (*discrete_checks.items(), *numeric_checks.items())
                if not passed
            ]
            result["first_new_bottleneck"] = ";".join(failed)
        else:
            result["first_new_bottleneck"] = "none_within_fixed_budget"
        return result
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(result: dict[str, object]) -> None:
    output = Path("results")
    output.mkdir(exist_ok=True)
    _write_csv(output / "a5_structural_retry_resources.csv", [result])
    report = f"""# Nouvelle tentative collective |A|=5 — compilateur structurel

Statut : **{result['status']}** sous le budget fixe de
{result['max_seconds_budget']:.0f} s et {result['max_rss_budget_mib']:.0f} Mio RSS.

## Instance

- message collectif : 5 qubits, dimension {result['alphabet_size']} ;
- B={result['black_hole_qubits']}, graine {result['seed']}, profondeur de
  brouillage {result['scramble_depth']}, t={result['t']} ;
- rang du support numérique/stabilisateur :
  {result['support_rank_numeric']}/{result['support_rank_stabilizer']} ;
- qubits logiques du support : {result['support_logical_qubits']} ;
- qubits d'environnement de la dilatation : {result['environment_qubits']}.

## Fidélités et certificat

| objet | valeur |
|---|---:|
| Petz abstrait | {result['petz_fidelity']:.15g} |
| circuit Clifford direct | {result['direct_circuit_fidelity']:.15g} |
| circuit Clifford routé | {result['routed_circuit_fidelity']:.15g} |
| fidélité Choi directe certifiée | {result['direct_choi_fidelity_certified']} |
| fidélité Choi routée certifiée | {result['routed_choi_fidelity_certified']} |

Le certificat compare exactement {result['target_generators_checked']}
générateurs signés de la purification Choi cible et synthétisée. Dans la jauge
fixée, les purifications coïncident, donc `W_E=I` et les Choi réduits sont égaux
après trace de l'environnement : `{result['reduced_choi_equal']}`.

Les anciennes énumérations de {result['old_group_size_avoided']} éléments de
groupe et {result['old_operator_checks_avoided']} opérateurs du support sont
évitées. Éléments/opérateurs effectivement énumérés :
{result['group_elements_enumerated']}/{result['support_operators_enumerated']}.

Dimensions GF(2) : noyau support
`{result['support_kernel_variables']} variables / {result['support_kernel_constraints']}
contraintes / rang {result['support_kernel_constraint_rank']} / dimension
{result['support_kernel_dimension']}` ; centralisateur
`{result['centralizer_dimension']}` ; quotient logique
`{result['logical_quotient_dimension']}`. Le solveur Choi utilise
`{result['choi_affine_variables']}` variables, un rang
`{result['choi_affine_constraint_rank']}` et un noyau affine de dimension
`{result['choi_affine_kernel_dimension']}`. Les calculs ont résolu
{result['gf2_affine_systems_solved']} systèmes et effectué
{result['gf2_scalar_bit_xors']} XOR scalaires instrumentés dans les éliminations
de lignes.

## Coût construit

| réalisation | profondeur 2q | CNOT | SWAP |
|---|---:|---:|---:|
| Clifford direct | {result['logical_depth']} | {result['logical_cnot']} | 0 |
| chaîne locale | {result['routed_depth']} | {result['routed_cnot']} | {result['swap']} |

Ordre final restauré : `{result['final_order_restored']}` ; équivalence Clifford
direct/routé : `{result['routed_clifford_equal']}`.

## Temps et mémoire

| étape | secondes |
|---|---:|
| canal | {result['channel_seconds']:.6f} |
| Petz abstrait | {result['petz_seconds']:.6f} |
| code support | {result['support_code_seconds']:.6f} |
| synthèse | {result['synthesis_seconds']:.6f} |
| certification directe | {result['direct_certification_seconds']:.6f} |
| routage | {result['routing_seconds']:.6f} |
| certification routée | {result['routed_certification_seconds']:.6f} |
| total | {result['total_seconds']:.6f} |

RSS maximale : {result['peak_rss_mib']:.1f} Mio. Premier nouveau goulot :
`{result['first_new_bottleneck']}`.

## Portée

Ce résultat porte sur une instance Clifford idéale unique. Le certificat sur
générateurs remplace exactement les énumérations dans cette sous-classe ; il ne
constitue ni une loi d'échelle, ni une borne de complexité minimale. Aucun test
A=6 n'est lancé.
"""
    Path("docs/notes/A5_STRUCTURAL_RETRY.md").write_text(report)


def main() -> None:
    result = run_retry()
    write_outputs(result)
    print(
        "A=5 structural retry: "
        f"status={result['status']}; "
        f"Petz={result['petz_fidelity']:.15g}; "
        f"direct={result['direct_circuit_fidelity']:.15g}; "
        f"routed={result['routed_circuit_fidelity']:.15g}"
    )
    print(
        f"depth={result['logical_depth']}->{result['routed_depth']}; "
        f"SWAP={result['swap']}; elapsed={result['total_seconds']:.3f}s; "
        f"RSS={result['peak_rss_mib']:.1f}MiB"
    )


if __name__ == "__main__":
    main()
