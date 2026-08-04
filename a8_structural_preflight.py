#!/usr/bin/env python3
"""One collective A=8 preflight through the fully structural pipeline."""
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


def _state_certificates(identity_certified: bool) -> list[dict[str, object]]:
    tests = (
        (
            "basis_demo",
            "|10101101>",
            "10101101",
            173,
            "😀",
            False,
        ),
        (
            "superposition_ghz",
            "(|00000000>+|11111111>)/sqrt(2)",
            "",
            "",
            "",
            False,
        ),
        (
            "superposition_phase_i",
            "(|00000001>+i|11111110>)/sqrt(2)",
            "",
            "",
            "",
            True,
        ),
        (
            "uniform_complex_phase",
            "((|0>+i|1>)/sqrt(2))^tensor8",
            "",
            "",
            "",
            True,
        ),
    )
    return [
        {
            "test_kind": kind,
            "input_state": state,
            "primary_binary_symbol": bits,
            "primary_decimal_value": decimal,
            "visual_label_only": visual,
            "contains_complex_relative_phase": complex_phase,
            "preservation_certified": identity_certified,
            "certified_fidelity": 1.0 if identity_certified else "",
            "certification_method": (
                "corollary_of_signed_reduced_choi_identity"
                if identity_certified
                else "not_certified"
            ),
            "dense_state_constructed": False,
        }
        for kind, state, bits, decimal, visual, complex_phase in tests
    ]


def run_preflight():
    started = time.perf_counter()
    initial_rss = _rss_mib()
    previous_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, MAX_SECONDS)
    try:
        layout = SystemLayout(n_message=8, n_black_hole=4)
        scrambler = random_stabilizer_scrambler(
            layout, np.random.default_rng(SEED), SCRAMBLE_DEPTH
        )
        if not _connected(layout, scrambler):
            raise AssertionError("A8 scrambler is not connected")
        timeline_started = time.perf_counter()
        timeline = structural_timeline(layout, scrambler)
        timeline_seconds = time.perf_counter() - timeline_started
        _check_budget(started, "structural timeline")
        selected = next(
            (row for row in timeline if row["petz_fidelity"] > FIDELITY_THRESHOLD),
            None,
        )
        if selected is None:
            raise RuntimeError("no A8 time reaches the Petz threshold")
        selected_t = int(selected["t"])
        construction_started = time.perf_counter()
        result = run_structural_instance(layout, scrambler, selected_t)
        construction_seconds = time.perf_counter() - construction_started
        _check_budget(started, "synthesis, certification and routing")

        metrics = result.metrics
        identity_certified = (
            bool(metrics["validated"])
            and bool(metrics["reduced_choi_equal"])
            and bool(metrics["signed_phases_validated"])
            and abs(float(metrics["petz_fidelity"]) - 1.0) < TOLERANCE
            and abs(float(metrics["direct_fidelity"]) - 1.0) < TOLERANCE
            and abs(float(metrics["routed_fidelity"]) - 1.0) < TOLERANCE
        )
        state_rows = _state_certificates(identity_certified)
        total_seconds = time.perf_counter() - started
        peak_rss = _rss_mib()
        budget_pass = total_seconds <= MAX_SECONDS and peak_rss <= MAX_RSS_MIB
        dense_free = not any(
            bool(metrics[key])
            for key in (
                "dense_channel_constructed",
                "dense_tau_constructed",
                "dense_choi_constructed",
                "dense_state_validation_constructed",
            )
        )
        validated = identity_certified and budget_pass and dense_free
        metadata = {
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
            "basis_alphabet_size": 256,
            "basis_states_enumerated": 0,
            "basis_states_collectively_certified": 256
            if identity_certified
            else 0,
            "identity_channel_on_message_certified": identity_certified,
            "timeline_seconds": timeline_seconds,
            "construction_certification_routing_seconds": construction_seconds,
            "total_seconds": total_seconds,
            "initial_rss_mib": initial_rss,
            "peak_rss_mib": peak_rss,
            "memory_headroom_mib": MAX_RSS_MIB - peak_rss,
            "max_seconds_budget": MAX_SECONDS,
            "max_rss_budget_mib": MAX_RSS_MIB,
            "budget_pass": budget_pass,
            "dense_free_chain": dense_free,
            "first_obstruction": "none" if validated else "validation_or_budget",
        }
        return timeline, state_rows, metadata
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(timeline, state_rows, metadata) -> None:
    output = Path("results")
    output.mkdir(exist_ok=True)
    _write_csv(output / "a8_structural_preflight_timeline.csv", timeline)
    _write_csv(output / "a8_structural_preflight_state_certificates.csv", state_rows)
    _write_csv(output / "a8_structural_preflight_resources.csv", [metadata])
    timeline_lines = "\n".join(
        "| {t} | {mutual_information_R_C_bits} | "
        "{trace_distance_rhoRC_product:.12g} | {petz_fidelity:.15g} | "
        "{support_rank} | {elapsed_seconds:.4f} |".format(**row)
        for row in timeline
    )
    state_lines = "\n".join(
        f"| {str(row['input_state']).replace('|', '\\|')} | {row['certified_fidelity']} | "
        f"{row['contains_complex_relative_phase']} | {row['dense_state_constructed']} |"
        for row in state_rows
    )
    report = f"""# Pré-vol structurel collectif |A|=8

Statut : **{'validé' if metadata['status'] == 'validated' else metadata['status']}**.
Instance unique, B=4, budget {MAX_SECONDS:.0f} s / {MAX_RSS_MIB:.0f} Mio.
Aucune campagne et aucun A=9 ne sont lancés.

## Chronologie

| t | I(R:C) | distance trace | fidélité Petz | rang support | secondes |
|---:|---:|---:|---:|---:|---:|
{timeline_lines}

Le premier temps favorable est `t={metadata['selected_t']}` :
`I(R:C)={metadata['selected_mutual_information_bits']}`, distance
`{metadata['selected_trace_distance']}` et rang du support
`{metadata['support_rank']}`.

## Canal construit et certifié

- fidélité Petz : `{metadata['petz_fidelity']}` ;
- fidélité directe : `{metadata['direct_fidelity']}` ;
- fidélité routée : `{metadata['routed_fidelity']}` ;
- Choi réduits égaux : `{metadata['reduced_choi_equal']}` ;
- phases signées validées : `{metadata['signed_phases_validated']}` ;
- générateurs Choi signés : {metadata['choi_signed_generator_count']} ;
- profondeur : `{metadata['logical_depth']} -> {metadata['routed_depth']}` ;
- CNOT : `{metadata['logical_cnot']} -> {metadata['routed_cnot']}` ;
- SWAP : `{metadata['swap']}`.

## Alphabet de 256 états de base

Les 256 états ne sont pas énumérés. L'égalité du Choi réduit signé et la
fidélité d'intrication égale à 1 certifient l'identité du canal composé sur tout
l'espace de dimension 256. États certifiés collectivement :
`{metadata['basis_states_collectively_certified']}` ; états parcourus :
`{metadata['basis_states_enumerated']}`.

La démonstration visuelle conserve les données primaires :
`10101101 = 173`; `😀` est seulement une étiquette d'affichage.

| état représentatif | fidélité certifiée | phase complexe | état dense construit |
|---|---:|---:|---:|
{state_lines}

Ces lignes sont des corollaires du certificat du canal complet, pas quatre
simulations indépendantes.

## Budget et constructions

- chronologie : `{metadata['timeline_seconds']:.3f} s` ;
- synthèse, certification et routage :
  `{metadata['construction_certification_routing_seconds']:.3f} s` ;
- total : `{metadata['total_seconds']:.3f} s` ;
- RSS maximale : `{metadata['peak_rss_mib']:.1f} Mio` ;
- marge mémoire : `{metadata['memory_headroom_mib']:.1f} Mio` ;
- chaîne sans objet dense : `{metadata['dense_free_chain']}`.

## Limites

Une seule instance Clifford pure idéale est certifiée. Ce résultat ne montre
pas que toutes les instances A=8 passent, ne fournit aucune loi d'échelle,
aucune minimalité de profondeur et aucune sécurité cryptographique. Le symbole
peut représenter un octet ou un pixel 8 bits, mais le canal ne connaît pas sa
sémantique.
"""
    Path("docs/notes/A8_STRUCTURAL_PREFLIGHT.md").write_text(report)


def main() -> None:
    timeline, state_rows, metadata = run_preflight()
    write_outputs(timeline, state_rows, metadata)
    print(
        f"A=8 structural preflight: status={metadata['status']}; "
        f"t={metadata['selected_t']}; F={metadata['petz_fidelity']}; "
        f"depth={metadata['logical_depth']}->{metadata['routed_depth']}"
    )
    print(
        f"CNOT={metadata['logical_cnot']}->{metadata['routed_cnot']}; "
        f"SWAP={metadata['swap']}; elapsed={metadata['total_seconds']:.3f}s; "
        f"RSS={metadata['peak_rss_mib']:.1f}MiB"
    )


if __name__ == "__main__":
    main()
