#!/usr/bin/env python3
"""Frozen SABRE regression over the immutable A=1, A=8, A=12 fixtures."""
from __future__ import annotations

from dataclasses import replace
import csv
import json
from pathlib import Path
import platform
import time

from hayden_preskill_toy.recovery_artifact import CircuitSpec
from hayden_preskill_toy.recovery_problem import GateSpec
from hayden_preskill_toy.recovery_sabre import artifact_with_sabre_route
from hayden_preskill_toy.recovery_serialization import (
    artifact_document_hash,
    read_artifact,
    read_problem,
    write_artifact,
)
from hayden_preskill_toy.recovery_verify import verify_recovery


ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "tests" / "fixtures" / "recovery_v1"
RESULTS = ROOT / "results"
CSV_PATH = RESULTS / "sabre_regression_a1_a12.csv"
JSON_PATH = RESULTS / "sabre_regression_a1_a12.json"
REPORT_PATH = ROOT / "SABRE_REGRESSION_A1_A12.md"
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
    sabre, routing = artifact_with_sabre_route(problem, base)
    route_seconds = time.perf_counter() - started
    repeated, repeated_routing = artifact_with_sabre_route(problem, base)
    deterministic = sabre == repeated and routing == repeated_routing

    phase_mutation = replace(
        sabre,
        routed_circuit=CircuitSpec(
            problem.accessible_partition,
            (
                *sabre.routed_circuit.gates,
                GateSpec("Z", (problem.requested_output[0],)),
            ),
        ),
    )
    permutation_mutation = replace(
        sabre,
        final_permutation=(*sabre.final_permutation[1:], sabre.final_permutation[0]),
    )
    strict = verify_recovery(problem, sabre)
    channel = verify_recovery(problem, sabre, policy="channel-certified")
    phase = verify_recovery(problem, phase_mutation, policy="channel-certified")
    permutation = verify_recovery(
        problem, permutation_mutation, policy="channel-certified"
    )
    route_differs = sabre.routed_circuit.gates != base.routed_circuit.gates
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
        raise AssertionError(f"SABRE regression failed for {case_id}")

    sabre_path = RESULTS / f"sabre_{case_id}.artifact.json"
    phase_path = RESULTS / f"sabre_{case_id}_phase_mutation.artifact.json"
    permutation_path = RESULTS / f"sabre_{case_id}_permutation_mutation.artifact.json"
    write_artifact(sabre_path, sabre)
    write_artifact(phase_path, phase_mutation)
    write_artifact(permutation_path, permutation_mutation)
    return {
        "case_id": case_id,
        "message_qubits": len(problem.channel_input),
        "qiskit_version": routing.qiskit_version,
        "seed": routing.seed,
        "heuristic": routing.heuristic,
        "trials": routing.trials,
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
        "entanglement_fidelity": _metric(sabre, "circuit_entanglement_fidelity"),
        "logical_depth": sabre.resources.logical_depth,
        "logical_cnot": sabre.resources.logical_cnot,
        "orelia_routed_depth": base.resources.routed_depth,
        "sabre_routed_depth": sabre.resources.routed_depth,
        "depth_ratio_sabre_over_orelia": format(
            sabre.resources.routed_depth / base.resources.routed_depth, ".9f"
        ),
        "orelia_routed_cnot": base.resources.routed_cnot,
        "sabre_routed_cnot": sabre.resources.routed_cnot,
        "cnot_ratio_sabre_over_orelia": format(
            sabre.resources.routed_cnot / base.resources.routed_cnot, ".9f"
        ),
        "sabre_movement_swaps": routing.movement_swaps,
        "adapter_restoration_swaps": routing.restoration_swaps,
        "route_seconds_first_run": format(route_seconds, ".9f"),
        "sabre_artifact_hash": artifact_document_hash(sabre),
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
        "format_version": "orelia.sabre-regression/v1",
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
        "# Régression SABRE certifiée — A=1, A=8 et A=12",
        "",
        "## Verdict",
        "",
        "**3/3 instances validées.**",
        "",
        "Pour chaque fixture immuable, SABRE produit une route différente de la route ORELIA. La politique `reproducible-route` la refuse, tandis que `channel-certified` certifie exactement le canal réduit. Une phase `Z` ajoutée à la sortie et une permutation finale falsifiée sont rejetées pour chaque taille.",
        "",
        "| A | Route SABRE différente | Strict | Canal certifié | Phase rejetée | Permutation rejetée |",
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
        "| A | Profondeur logique | Profondeur ORELIA | Profondeur SABRE | CNOT ORELIA | CNOT SABRE | SWAP SABRE |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in rows:
        lines.append(
            f"| {row['message_qubits']} | {row['logical_depth']} | {row['orelia_routed_depth']} | {row['sabre_routed_depth']} | {row['orelia_routed_cnot']} | {row['sabre_routed_cnot']} | {row['sabre_movement_swaps']} + {row['adapter_restoration_swaps']} restitution |"
        )
    lines.extend([
        "",
        "Sur ces trois fixtures et avec ce protocole figé, SABRE produit davantage de profondeur et de CNOT que le routeur ORELIA. Trois instances ne suffisent pas pour conclure à une supériorité générale. La restauration v1 par inversion de tous les SWAP SABRE est correcte mais volontairement conservatrice.",
        "",
        "## Reproductibilité",
        "",
        "- Qiskit `2.5.1` ;",
        "- `SabreSwap`, heuristique `decay` ;",
        "- graine `20260803` ;",
        "- `trials=1` ;",
        "- layout initial identité ;",
        "- chaque compilation a été répétée et comparée exactement ;",
        f"- durée totale : `{metadata['elapsed_seconds']}` s ;",
        f"- RSS maximale : `{metadata['peak_rss_mib']}` Mio.",
        "",
        "## Limites",
        "",
        "Le circuit logique de Petz est synthétisé par ORELIA ; SABRE assure uniquement le routage. Cette régression ne constitue ni une loi d'échelle, ni un benchmark statistique, ni une preuve de minimalité.",
        "",
        "## Sorties",
        "",
        "- `results/sabre_regression_a1_a12.csv` ;",
        "- `results/sabre_regression_a1_a12.json` ;",
        "- artefacts SABRE et mutations dans `results/` ;",
        "- tests automatiques dans `tests/test_sabre_channel_certified.py`.",
        "",
    ])
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
