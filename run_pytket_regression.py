#!/usr/bin/env python3
"""Frozen pytket regression over the immutable A=1, A=8, A=12 fixtures."""
from __future__ import annotations

from dataclasses import replace
import csv
import json
import os
from pathlib import Path
import platform
import time

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("XDG_CONFIG_HOME", str(ROOT / ".pytket-config"))

from hayden_preskill_toy.recovery_artifact import CircuitSpec
from hayden_preskill_toy.recovery_problem import GateSpec
from hayden_preskill_toy.recovery_pytket import artifact_with_pytket_route
from hayden_preskill_toy.recovery_serialization import (
    artifact_document_hash,
    read_artifact,
    read_problem,
    write_artifact,
)
from hayden_preskill_toy.recovery_verify import verify_recovery


FIXTURES = ROOT / "tests" / "fixtures" / "recovery_v1"
RESULTS = ROOT / "results"
CSV_PATH = RESULTS / "pytket_regression_a1_a12.csv"
JSON_PATH = RESULTS / "pytket_regression_a1_a12.json"
REPORT_PATH = ROOT / "PYTKET_REGRESSION_A1_A12.md"
CASES = ("a1", "a8", "a12")


def _failed(report) -> str:
    return ";".join(item.name for item in report.checks if not item.passed)


def _metric(artifact, name: str) -> str:
    return next(item.value for item in artifact.metrics if item.name == name)


def _rss_mib() -> float | None:
    try:
        import resource
    except ImportError:
        return None
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() != "Darwin":
        value *= 1024
    return value / 2**20


def _case(case_id: str) -> dict[str, object]:
    problem = read_problem(FIXTURES / f"{case_id}.problem.json")
    base = read_artifact(FIXTURES / f"{case_id}.artifact.json")
    started = time.perf_counter()
    candidate, routing = artifact_with_pytket_route(problem, base)
    route_seconds = time.perf_counter() - started
    repeated, repeated_routing = artifact_with_pytket_route(problem, base)
    deterministic = candidate == repeated and routing == repeated_routing

    phase_mutation = replace(
        candidate,
        routed_circuit=CircuitSpec(
            problem.accessible_partition,
            (
                *candidate.routed_circuit.gates,
                GateSpec("Z", (problem.requested_output[0],)),
            ),
        ),
    )
    permutation_mutation = replace(
        candidate,
        final_permutation=(
            *candidate.final_permutation[1:],
            candidate.final_permutation[0],
        ),
    )
    strict = verify_recovery(problem, candidate)
    channel = verify_recovery(problem, candidate, policy="channel-certified")
    phase = verify_recovery(problem, phase_mutation, policy="channel-certified")
    permutation = verify_recovery(
        problem, permutation_mutation, policy="channel-certified"
    )
    route_differs = candidate.routed_circuit.gates != base.routed_circuit.gates
    regression_pass = (
        route_differs
        and deterministic
        and not strict.verified
        and channel.verified
        and not phase.verified
        and not phase.channel_verified
        and not permutation.verified
        and not permutation.final_order_verified
    )
    if not regression_pass:
        raise AssertionError(f"pytket regression failed for {case_id}")

    candidate_path = RESULTS / f"pytket_{case_id}.artifact.json"
    phase_path = RESULTS / f"pytket_{case_id}_phase_mutation.artifact.json"
    permutation_path = RESULTS / f"pytket_{case_id}_permutation_mutation.artifact.json"
    write_artifact(candidate_path, candidate)
    write_artifact(phase_path, phase_mutation)
    write_artifact(permutation_path, permutation_mutation)
    return {
        "case_id": case_id,
        "message_qubits": len(problem.channel_input),
        "pytket_version": routing.pytket_version,
        "routing_pass": routing.routing_pass,
        "route_differs_from_orelia": route_differs,
        "deterministic_rerun_equal": deterministic,
        "reproducible_route_accepted": strict.verified,
        "channel_certified_accepted": channel.verified,
        "phase_mutation_accepted": phase.verified,
        "permutation_mutation_accepted": permutation.verified,
        "strict_failed_checks": _failed(strict),
        "channel_failed_checks": _failed(channel),
        "phase_failed_checks": _failed(phase),
        "permutation_failed_checks": _failed(permutation),
        "entanglement_fidelity": _metric(candidate, "circuit_entanglement_fidelity"),
        "logical_depth": candidate.resources.logical_depth,
        "logical_cnot": candidate.resources.logical_cnot,
        "orelia_routed_depth": base.resources.routed_depth,
        "pytket_routed_depth": candidate.resources.routed_depth,
        "depth_ratio_pytket_over_orelia": format(
            candidate.resources.routed_depth / base.resources.routed_depth, ".9f"
        ),
        "orelia_routed_cnot": base.resources.routed_cnot,
        "pytket_routed_cnot": candidate.resources.routed_cnot,
        "cnot_ratio_pytket_over_orelia": format(
            candidate.resources.routed_cnot / base.resources.routed_cnot, ".9f"
        ),
        "pytket_movement_swaps": routing.movement_swaps,
        "adapter_restoration_swaps": routing.restoration_swaps,
        "bridges_before_decomposition": routing.bridges_before_decomposition,
        "global_phase_half_turns": routing.global_phase_half_turns,
        "route_seconds_first_run": format(route_seconds, ".9f"),
        "pytket_artifact_hash": artifact_document_hash(candidate),
        "phase_artifact_hash": artifact_document_hash(phase_mutation),
        "permutation_artifact_hash": artifact_document_hash(permutation_mutation),
        "regression_pass": regression_pass,
    }


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    rows = [_case(case_id) for case_id in CASES]
    with CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    metadata = {
        "format_version": "orelia.pytket-regression/v1",
        "cases": rows,
        "all_regressions_pass": all(row["regression_pass"] for row in rows),
        "elapsed_seconds": format(time.perf_counter() - started, ".9f"),
        "peak_rss_mib": None if _rss_mib() is None else format(_rss_mib(), ".6f"),
        "python_version": platform.python_version(),
    }
    JSON_PATH.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Régression pytket certifiée — A=1, A=8 et A=12",
        "",
        "## Verdict",
        "",
        "**3/3 instances validées.**",
        "",
        "Pour chaque fixture, pytket produit une route différente de la route ORELIA. `reproducible-route` la refuse, `channel-certified` certifie le canal réduit, et les mutations de phase et de permutation sont rejetées.",
        "",
        "| A | Route différente | Strict | Canal certifié | Phase rejetée | Permutation rejetée |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['message_qubits']} | {row['route_differs_from_orelia']} | {'accepté' if row['reproducible_route_accepted'] else 'rejeté'} | {'accepté' if row['channel_certified_accepted'] else 'rejeté'} | {not row['phase_mutation_accepted']} | {not row['permutation_mutation_accepted']} |"
        )
    lines.extend([
        "",
        "## Ressources observées",
        "",
        "| A | Profondeur logique | Profondeur ORELIA | Profondeur pytket | CNOT ORELIA | CNOT pytket | SWAP + restitution | BRIDGE |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in rows:
        lines.append(
            f"| {row['message_qubits']} | {row['logical_depth']} | {row['orelia_routed_depth']} | {row['pytket_routed_depth']} | {row['orelia_routed_cnot']} | {row['pytket_routed_cnot']} | {row['pytket_movement_swaps']} + {row['adapter_restoration_swaps']} | {row['bridges_before_decomposition']} |"
        )
    lines.extend([
        "",
        "Sur `A=12`, pytket donne une profondeur légèrement inférieure à ORELIA mais davantage de CNOT. Ce croisement confirme qu'aucun classement scalaire n'est justifié avant un benchmark multidimensionnel et multi-instance.",
        "",
        "## Configuration",
        "",
        "- pytket `2.18.1` ;",
        "- layout initial identité via `place_with_map` ;",
        "- `RoutingPass` avec `LexiLabellingMethod` et `LexiRouteRoutingMethod` ;",
        "- SWAP et BRIDGE décomposés exactement en CNOT ;",
        "- ordre v1 restauré seulement lorsque la permutation nette n'est pas identité ;",
        "- chaque compilation répétée et comparée exactement ;",
        f"- durée totale : `{metadata['elapsed_seconds']}` s ;",
        f"- RSS maximale : `{metadata['peak_rss_mib']}` Mio.",
        "",
        "## Limites",
        "",
        "Le circuit logique de Petz est toujours synthétisé par ORELIA. pytket intervient uniquement pour le routage. Trois fixtures ne définissent ni une loi d'échelle ni une hiérarchie générale des routeurs.",
        "",
        "## Sorties",
        "",
        "- `results/pytket_regression_a1_a12.csv` ;",
        "- `results/pytket_regression_a1_a12.json` ;",
        "- artefacts pytket et mutations dans `results/` ;",
        "- `tests/test_pytket_channel_certified.py`.",
        "",
    ])
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
