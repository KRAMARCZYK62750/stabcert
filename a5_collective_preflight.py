#!/usr/bin/env python3
"""Budget gate for one collective five-qubit-message instance."""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
import platform
import resource
import time

import numpy as np

from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_channels import channel_at_time, random_scrambler
from hayden_preskill_toy.parametric_petz import choi_tableau, entanglement_fidelity, support_rank
from hayden_preskill_toy.simulator import Gate
from hayden_preskill_toy.stabilizer import pure_stabilizer_decoupling


SEED = 20260802
SCRAMBLE_DEPTH = 6
FIDELITY_THRESHOLD = 0.99
MAX_RSS_MIB = 1024.0
MAX_SECONDS = 120.0
MAX_OPERATOR_CHECKS = 65_536
MAX_SIGNED_CHOI_GROUP_SIZE = 131_072

# Empirical standalone A4 reference used only for a clearly labelled runtime
# estimate; no A4 artifact participates in the A5 scientific calculation.
A4_OPERATOR_CHECKS = 16_384
A4_DIRECT_VALIDATION_SECONDS = 10.832054666941985
A4_ROUTED_VALIDATION_SECONDS = 11.16774991597049


def _rss_mib() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    byte_value = value if platform.system() == "Darwin" else value * 1024
    return float(byte_value / 2**20)


def _connected_scrambler(layout: SystemLayout, scrambler: list[Gate]) -> bool:
    adjacency = {qubit: set() for qubit in layout.scrambled}
    for gate in scrambler:
        if gate.name == "CNOT":
            assert gate.b is not None
            adjacency[gate.a].add(gate.b)
            adjacency[gate.b].add(gate.a)
    reached = {layout.scrambled[0]}
    pending = list(reached)
    while pending:
        qubit = pending.pop()
        for neighbour in adjacency[qubit] - reached:
            reached.add(neighbour)
            pending.append(neighbour)
    return reached == set(layout.scrambled)


@lru_cache(maxsize=1)
def run_preflight():
    started = time.perf_counter()
    initial_rss = _rss_mib()
    layout = SystemLayout(n_message=5, n_black_hole=4)
    scrambler = random_scrambler(
        layout, np.random.default_rng(SEED), SCRAMBLE_DEPTH
    )
    if not _connected_scrambler(layout, scrambler):
        raise AssertionError("selected A5 scrambling graph is disconnected")

    timeline: list[dict[str, object]] = []
    channels = {}
    for t in range(len(layout.scrambled) + 1):
        step_started = time.perf_counter()
        channel = channel_at_time(layout, scrambler, t)
        fidelity, info = entanglement_fidelity(channel)
        rank = support_rank(channel)
        decoupling = pure_stabilizer_decoupling(
            scrambler,
            layout.n_qubits,
            layout.R_register,
            layout.A_register,
            layout.B,
            layout.E,
            t,
        )
        channels[t] = channel
        timeline.append(
            {
                "t": t,
                "accessible_qubits": len(layout.X(t)),
                "inaccessible_qubits": len(layout.C(t)),
                "channel_output_dimension": channel.kraus[0].shape[0],
                "channel_input_dimension": channel.kraus[0].shape[1],
                "kraus_count": len(channel.kraus),
                "support_rank_tau_X": rank,
                "support_operator_basis_size": rank**2,
                "mutual_information_R_C_bits": decoupling[
                    "mutual_information_bits"
                ],
                "trace_distance_rhoRC_product": decoupling[
                    "trace_distance_product"
                ],
                "petz_entanglement_fidelity": fidelity,
                "support_trace_preservation_error": info[
                    "support_trace_preservation_error"
                ],
                "elapsed_seconds": time.perf_counter() - step_started,
                "peak_rss_mib": _rss_mib(),
            }
        )
        if _rss_mib() > MAX_RSS_MIB or time.perf_counter() - started > MAX_SECONDS:
            raise RuntimeError(f"A5 timeline exceeded runtime budget at t={t}")

    selected = next(
        (row for row in timeline if row["petz_entanglement_fidelity"] > FIDELITY_THRESHOLD),
        None,
    )
    if selected is None:
        raise RuntimeError("no A5 time reaches the Petz threshold")
    selected_t = int(selected["t"])
    channel = channels[selected_t]

    choi_started = time.perf_counter()
    choi = choi_tableau(channel)
    choi_seconds = time.perf_counter() - choi_started
    choi_qubits = len(choi)
    signed_group_size = 1 << choi_qubits
    operator_checks = int(selected["support_operator_basis_size"])
    symplectic_candidate_space = 1 << (2 * len(layout.X(selected_t)))

    reasons = []
    if operator_checks > MAX_OPERATOR_CHECKS:
        reasons.append(
            f"operator_checks={operator_checks}>{MAX_OPERATOR_CHECKS}"
        )
    if signed_group_size > MAX_SIGNED_CHOI_GROUP_SIZE:
        reasons.append(
            f"signed_choi_group={signed_group_size}>{MAX_SIGNED_CHOI_GROUP_SIZE}"
        )
    estimated_direct = (
        operator_checks / A4_OPERATOR_CHECKS * A4_DIRECT_VALIDATION_SECONDS
    )
    estimated_routed = (
        operator_checks / A4_OPERATOR_CHECKS * A4_ROUTED_VALIDATION_SECONDS
    )
    if estimated_direct + estimated_routed > MAX_SECONDS:
        reasons.append(
            "estimated_two_validations_seconds="
            f"{estimated_direct + estimated_routed:.1f}>{MAX_SECONDS:.1f}"
        )
    if not reasons:
        raise AssertionError("A5 unexpectedly fits every inherited synthesis budget")

    metadata = {
        "status": "stopped_before_synthesis",
        "message_qubits": layout.n_message,
        "alphabet_size": 1 << layout.n_message,
        "black_hole_qubits": layout.n_black_hole,
        "message_larger_than_black_hole": layout.n_message > layout.n_black_hole,
        "total_simulated_qubits": layout.n_qubits,
        "scrambled_qubits": len(layout.scrambled),
        "scrambler_connected": True,
        "seed": SEED,
        "scramble_depth": SCRAMBLE_DEPTH,
        "selected_t": selected_t,
        "selected_mutual_information_bits": selected[
            "mutual_information_R_C_bits"
        ],
        "selected_trace_distance": selected["trace_distance_rhoRC_product"],
        "selected_petz_fidelity": selected["petz_entanglement_fidelity"],
        "support_rank": selected["support_rank_tau_X"],
        "full_operator_checks": operator_checks,
        "max_operator_checks": MAX_OPERATOR_CHECKS,
        "choi_petz_is_stabilizer": True,
        "choi_purification_qubits": choi_qubits,
        "signed_choi_group_size": signed_group_size,
        "max_signed_choi_group_size": MAX_SIGNED_CHOI_GROUP_SIZE,
        "symplectic_candidate_space_size": symplectic_candidate_space,
        "choi_purification_vector_mib": (1 << choi_qubits) * 16 / 2**20,
        "dense_choi_projector_gib_avoided": (1 << (2 * choi_qubits)) * 16 / 2**30,
        "choi_stabilizer_check_seconds": choi_seconds,
        "estimated_direct_validation_seconds_from_a4": estimated_direct,
        "estimated_routed_validation_seconds_from_a4": estimated_routed,
        "estimated_combined_validation_seconds_from_a4": estimated_direct
        + estimated_routed,
        "stop_reasons": ";".join(reasons),
        "compilation_attempted": False,
        "operator_validation_attempted": False,
        "state_tests_attempted": False,
        "routing_attempted": False,
        "initial_rss_mib": initial_rss,
        "peak_rss_mib": _rss_mib(),
        "elapsed_seconds": time.perf_counter() - started,
        "max_rss_budget_mib": MAX_RSS_MIB,
        "max_seconds_budget": MAX_SECONDS,
    }
    return timeline, metadata


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(timeline, metadata) -> None:
    output = Path("results")
    output.mkdir(exist_ok=True)
    _write_csv(output / "a5_preflight_timeline.csv", timeline)
    _write_csv(output / "a5_preflight_feasibility.csv", [metadata])
    timeline_lines = "\n".join(
        "| {t} | {mutual_information_R_C_bits} | {trace_distance_rhoRC_product:.12g} | "
        "{petz_entanglement_fidelity:.15g} | {support_rank_tau_X} | "
        "{support_operator_basis_size} | {elapsed_seconds:.3f} | {peak_rss_mib:.1f} |".format(**row)
        for row in timeline
    )
    report = f"""# Pré-vol collectif |A|=5

Statut : **arrêté proprement avant synthèse**.

## Configuration et budget

- message collectif : 5 qubits, dimension 32 ;
- B=4, E=4, total : {metadata['total_simulated_qubits']} qubits ;
- le message est désormais plus grand que B ; ce test s'éloigne donc du régime
  Hayden--Preskill à petit message ;
- budget hérité de A4 : {MAX_RSS_MIB:.0f} Mio, {MAX_SECONDS:.0f} s,
  {MAX_OPERATOR_CHECKS} contrôles opératoriels et
  {MAX_SIGNED_CHOI_GROUP_SIZE} éléments Choi signés ;
- plancher attendu : `1/32² = 1/1024`.

## Chronologie calculée

| t | I(R:C) | distance trace | fidélité Petz | rang support | opérateurs² | secondes | RSS Mio |
|---:|---:|---:|---:|---:|---:|---:|---:|
{timeline_lines}

Le premier temps avec `F_Petz>0,99` est `t={metadata['selected_t']}` :
`I(R:C)={metadata['selected_mutual_information_bits']}`,
distance `{metadata['selected_trace_distance']}` et fidélité Petz
`{metadata['selected_petz_fidelity']:.15g}`.

## Première limite exacte

À ce temps :

- rang du support : {metadata['support_rank']} ;
- contrôles requis : {metadata['full_operator_checks']}, soit
  {metadata['full_operator_checks'] / MAX_OPERATOR_CHECKS:.0f} fois le budget ;
- Choi Petz stabilisateur : `{metadata['choi_petz_is_stabilizer']}` ;
- purification Choi : {metadata['choi_purification_qubits']} qubits,
  {metadata['choi_purification_vector_mib']:.1f} Mio comme vecteur ;
- groupe signé : {metadata['signed_choi_group_size']} éléments, soit
  {metadata['signed_choi_group_size'] / MAX_SIGNED_CHOI_GROUP_SIZE:.0f} fois le budget ;
- espace candidat symplectique : {metadata['symplectic_candidate_space_size']} vecteurs.

L'extrapolation linéaire du seul contrôle opératoriel depuis A4 donne environ
`{metadata['estimated_direct_validation_seconds_from_a4']:.1f} s` pour le
circuit direct et `{metadata['estimated_routed_validation_seconds_from_a4']:.1f} s`
pour le routé, avant même de compter la synthèse. Cette estimation est un
indicateur de faisabilité, pas une mesure A5.

Motifs d'arrêt enregistrés : `{metadata['stop_reasons']}`.

## Actions volontairement non exécutées

- synthèse Clifford : `{metadata['compilation_attempted']}` ;
- validation opératorielle : `{metadata['operator_validation_attempted']}` ;
- routage : `{metadata['routing_attempted']}` ;
- tests des 32 symboles et superpositions : `{metadata['state_tests_attempted']}`.

Ainsi, ce pré-vol établit seulement que le découplage et Petz abstrait sont
favorables pour cette instance. Il ne valide pas un canal Clifford A5 construit
et ne permet pas d'annoncer un alphabet collectif de 32 symboles transmis.

## Ressources du pré-vol

Chronologie et vérification stabilisatrice du Choi :
`{metadata['elapsed_seconds']:.3f} s`, RSS maximale
`{metadata['peak_rss_mib']:.1f} Mio`. Le projecteur Choi dense théorique de
{metadata['dense_choi_projector_gib_avoided']:.0f} Gio n'est pas construit.

La prochaine étape n'est pas A6 : elle consiste à remplacer l'énumération du
groupe Choi et la validation opérateur par opérateur par des preuves sur
générateurs symplectiques signés.
"""
    Path("docs/notes/A5_COLLECTIVE_PREFLIGHT.md").write_text(report)


def main() -> None:
    timeline, metadata = run_preflight()
    write_outputs(timeline, metadata)
    print(
        f"A=5 preflight: selected t={metadata['selected_t']}; "
        f"Petz={metadata['selected_petz_fidelity']:.15g}; "
        f"status={metadata['status']}"
    )
    print(metadata["stop_reasons"])


if __name__ == "__main__":
    main()
