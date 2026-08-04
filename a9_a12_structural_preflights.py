#!/usr/bin/env python3
"""Sequential dense-free preflights for A=9,10,11,12; stop on first failure."""
from __future__ import annotations

import csv
from pathlib import Path
import platform
import resource
import signal
import time

import numpy as np

from hayden_preskill_toy.dense_free_pipeline import (
    run_structural_instance,
    structural_timeline,
)
from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_petz_stabilizer import (
    random_stabilizer_scrambler,
)


MESSAGE_SIZES = (9, 10, 11, 12)
SEED = 20260802
SCRAMBLE_DEPTH = 6
FIDELITY_THRESHOLD = 0.99
TOLERANCE = 1e-12
MAX_SECONDS_PER_INSTANCE = 120.0
MAX_RSS_MIB = 1024.0


class BudgetExceeded(RuntimeError):
    pass


def _rss_mib() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    byte_value = value if platform.system() == "Darwin" else value * 1024
    return float(byte_value / 2**20)


def _alarm_handler(_signum, _frame) -> None:
    raise BudgetExceeded(
        f"wall-time budget exceeded ({MAX_SECONDS_PER_INSTANCE:.0f} s)"
    )


def _connected(layout: SystemLayout, gates) -> bool:
    adjacency = {qubit: set() for qubit in layout.scrambled}
    for gate in gates:
        if gate.name == "CNOT":
            assert gate.b is not None
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


def run_one(message_qubits: int):
    started = time.perf_counter()
    initial_rss = _rss_mib()
    previous_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, MAX_SECONDS_PER_INSTANCE)
    try:
        layout = SystemLayout(n_message=message_qubits, n_black_hole=4)
        scrambler = random_stabilizer_scrambler(
            layout, np.random.default_rng(SEED), SCRAMBLE_DEPTH
        )
        if not _connected(layout, scrambler):
            raise AssertionError(f"A={message_qubits} scrambler is not connected")
        timeline_started = time.perf_counter()
        timeline = structural_timeline(layout, scrambler)
        timeline_seconds = time.perf_counter() - timeline_started
        selected = next(
            (row for row in timeline if row["petz_fidelity"] > FIDELITY_THRESHOLD),
            None,
        )
        if selected is None:
            raise RuntimeError(
                f"A={message_qubits}: no time reaches the Petz threshold"
            )
        selected_t = int(selected["t"])
        construction_started = time.perf_counter()
        result = run_structural_instance(layout, scrambler, selected_t)
        construction_seconds = time.perf_counter() - construction_started
        metrics = result.metrics
        total_seconds = time.perf_counter() - started
        peak_rss = _rss_mib()
        identity_certified = (
            bool(metrics["validated"])
            and bool(metrics["reduced_choi_equal"])
            and bool(metrics["signed_phases_validated"])
            and abs(float(metrics["petz_fidelity"]) - 1.0) < TOLERANCE
            and abs(float(metrics["direct_fidelity"]) - 1.0) < TOLERANCE
            and abs(float(metrics["routed_fidelity"]) - 1.0) < TOLERANCE
        )
        dense_free = not any(
            bool(metrics[key])
            for key in (
                "dense_channel_constructed",
                "dense_tau_constructed",
                "dense_choi_constructed",
                "dense_state_validation_constructed",
            )
        )
        budget_pass = (
            total_seconds <= MAX_SECONDS_PER_INSTANCE and peak_rss <= MAX_RSS_MIB
        )
        validated = identity_certified and dense_free and budget_pass
        resource_row = {
            "status": "validated" if validated else "failed_validation",
            **metrics,
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
            "basis_states_enumerated": 0,
            "basis_states_collectively_certified": (
                1 << message_qubits if identity_certified else 0
            ),
            "identity_channel_on_message_certified": identity_certified,
            "timeline_seconds": timeline_seconds,
            "construction_certification_routing_seconds": construction_seconds,
            "total_seconds": total_seconds,
            "initial_rss_mib": initial_rss,
            "peak_rss_mib": peak_rss,
            "max_seconds_budget": MAX_SECONDS_PER_INSTANCE,
            "max_rss_budget_mib": MAX_RSS_MIB,
            "budget_pass": budget_pass,
            "dense_free_chain": dense_free,
            "first_obstruction": "none" if validated else "validation_or_budget",
        }
        timeline_rows = [{"A": message_qubits, **row} for row in timeline]
        if not validated:
            raise AssertionError(resource_row)
        return timeline_rows, resource_row
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def run_all():
    timelines = []
    resources = []
    for message_qubits in MESSAGE_SIZES:
        try:
            timeline, resource_row = run_one(message_qubits)
        except Exception as error:
            resources.append(
                {
                    "status": "stopped",
                    "message_qubits": message_qubits,
                    "alphabet_size": 1 << message_qubits,
                    "first_obstruction": f"{type(error).__name__}: {error}",
                }
            )
            break
        timelines.extend(timeline)
        resources.append(resource_row)
    return timelines, resources


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(timelines, resources) -> None:
    output = Path("results")
    output.mkdir(exist_ok=True)
    if timelines:
        _write_csv(output / "a9_a12_structural_timelines.csv", timelines)
    _write_csv(output / "a9_a12_structural_preflights.csv", resources)
    validated = [row for row in resources if row["status"] == "validated"]
    table = "\n".join(
        f"| {row['message_qubits']} | {row['alphabet_size']} | {row['selected_t']} | "
        f"{row['selected_mutual_information_bits']} | {row['support_rank']} | "
        f"{row['petz_fidelity']} | {row['logical_depth']} | {row['routed_depth']} | "
        f"{row['logical_cnot']} | {row['routed_cnot']} | {row['swap']} | "
        f"{row['total_seconds']:.3f} | {row['peak_rss_mib']:.1f} |"
        for row in validated
    )
    stopped = next((row for row in resources if row["status"] != "validated"), None)
    stop_text = (
        "Aucune obstruction dans les quatre pré-vols."
        if stopped is None
        else f"Arrêt à A={stopped['message_qubits']} : `{stopped['first_obstruction']}`."
    )
    report = f"""# Pré-vols structurels séquentiels A=9 à A=12

Statut : **{len(validated)}/{len(MESSAGE_SIZES)} instances validées**.
Une graine par taille, B=4, budget individuel
{MAX_SECONDS_PER_INSTANCE:.0f} s / {MAX_RSS_MIB:.0f} Mio. Aucun ajustement du
compilateur entre les tailles et aucun A=13.

| A | alphabet | t favorable | I(R:C) | rang support | F | profondeur logique | profondeur routée | CNOT logiques | CNOT routés | SWAP | secondes | RSS Mio |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{table}

{stop_text}

Pour chaque ligne validée, Petz, le circuit direct et le circuit routé ont une
fidélité certifiée égale à 1 ; les Choi réduits et les phases signées
coïncident. Les alphabets sont couverts par le certificat du canal complet sans
énumération des états de base.

## Limites

Il s'agit de quatre instances Clifford pures idéales et non d'une campagne
statistique. Les tailles de message dépassent B=4 et s'éloignent du régime
Hayden--Preskill à petit message. Ces résultats ne définissent aucune loi
d'échelle, aucune profondeur minimale et aucune propriété cryptographique.
"""
    Path("docs/notes/A9_A12_STRUCTURAL_PREFLIGHTS.md").write_text(report)


def main() -> None:
    timelines, resources = run_all()
    write_outputs(timelines, resources)
    for row in resources:
        if row["status"] == "validated":
            print(
                f"A={row['message_qubits']}: t={row['selected_t']}; "
                f"depth={row['logical_depth']}->{row['routed_depth']}; "
                f"elapsed={row['total_seconds']:.3f}s; RSS={row['peak_rss_mib']:.1f}MiB"
            )
        else:
            print(
                f"A={row['message_qubits']}: stopped: {row['first_obstruction']}"
            )


if __name__ == "__main__":
    main()
