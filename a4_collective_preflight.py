#!/usr/bin/env python3
"""Budgeted single-instance collective preflight for a four-qubit message."""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
import platform
import resource
import time

import numpy as np

from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_channels import (
    channel_at_time,
    environment_state,
    random_scrambler,
)
from hayden_preskill_toy.parametric_petz import (
    apply_channel,
    choi_tableau,
    entanglement_fidelity,
    petz,
    support_rank,
)
from hayden_preskill_toy.parametric_routing import route_line
from hayden_preskill_toy.parametric_stabilizer import input_support_code
from hayden_preskill_toy.parametric_synthesis import signed_dilation
from hayden_preskill_toy.parametric_validation import validate
from hayden_preskill_toy.simulator import Gate, X, apply_1q, apply_circuit
from hayden_preskill_toy.stabilizer import pure_stabilizer_decoupling


SEED = 20260802
SCRAMBLE_DEPTH = 6
FIDELITY_THRESHOLD = 0.99
TOLERANCE = 1e-12
MAX_RSS_MIB = 1024.0
MAX_SECONDS = 120.0
MAX_OPERATOR_CHECKS = 65_536
MAX_SIGNED_CHOI_GROUP_SIZE = 131_072

EMOJIS = (
    "😀", "🚀", "🧠", "🌙", "☀️", "🔥", "💧", "🌱",
    "🎵", "🐈", "🍎", "⚙️", "🧩", "🛰️", "🌈", "⭐",
)


def _rss_mib() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    byte_value = value if platform.system() == "Darwin" else value * 1024
    return float(byte_value / 2**20)


def _check_runtime_budget(started: float, stage: str) -> None:
    rss = _rss_mib()
    elapsed = time.perf_counter() - started
    if rss > MAX_RSS_MIB:
        raise RuntimeError(f"A4 budget exceeded after {stage}: RSS={rss:.1f} MiB")
    if elapsed > MAX_SECONDS:
        raise RuntimeError(f"A4 budget exceeded after {stage}: elapsed={elapsed:.1f} s")


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


def _reduced_density(state: np.ndarray, keep: tuple[int, ...], n: int) -> np.ndarray:
    rest = tuple(q for q in range(n) if q not in keep)
    view = np.transpose(state.reshape((2,) * n), (*keep, *rest)).reshape(
        2 ** len(keep), -1
    )
    return view @ view.conj().T


def _message_input_state(layout: SystemLayout, message: np.ndarray) -> np.ndarray:
    base = environment_state(layout)
    state = np.zeros_like(base)
    for basis_index, amplitude in enumerate(message):
        component = base
        for offset, qubit in enumerate(layout.A_register):
            if basis_index >> (layout.n_message - offset - 1) & 1:
                component = apply_1q(component, X, qubit, layout.n_qubits)
        state += amplitude * component
    return state


def _physical_output(
    layout: SystemLayout,
    scrambler: list[Gate],
    decoder: list[Gate] | tuple[Gate, ...],
    message: np.ndarray,
    t: int,
) -> np.ndarray:
    state = _message_input_state(layout, message)
    state = apply_circuit(state, scrambler, layout.n_qubits)
    state = apply_circuit(state, list(decoder), layout.n_qubits)
    return _reduced_density(state, layout.X(t)[: layout.n_message], layout.n_qubits)


def _state_tests() -> dict[str, tuple[np.ndarray, str, str]]:
    basis = np.eye(16, dtype=complex)
    tests = {
        f"|{index:04b}>": (basis[index], f"{index:04b}", EMOJIS[index])
        for index in range(16)
    }
    tests["(|0000>+|1111>)/sqrt(2)"] = (
        (basis[0] + basis[15]) / np.sqrt(2), "", ""
    )
    tests["(|0001>+i|1110>)/sqrt(2)"] = (
        (basis[1] + 1j * basis[14]) / np.sqrt(2), "", ""
    )
    rng = np.random.default_rng(161803)
    random_state = rng.normal(size=16) + 1j * rng.normal(size=16)
    random_state /= np.linalg.norm(random_state)
    tests["etat_aleatoire_seed161803"] = (random_state, "", "")
    return tests


@lru_cache(maxsize=1)
def run_preflight():
    started = time.perf_counter()
    initial_rss = _rss_mib()
    layout = SystemLayout(n_message=4, n_black_hole=4)
    scrambler = random_scrambler(
        layout, np.random.default_rng(SEED), SCRAMBLE_DEPTH
    )
    if not _connected_scrambler(layout, scrambler):
        raise AssertionError("selected A4 scrambling graph is disconnected")

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
        _check_runtime_budget(started, f"timeline t={t}")

    selected = next(
        (row for row in timeline if row["petz_entanglement_fidelity"] > FIDELITY_THRESHOLD),
        None,
    )
    if selected is None:
        raise RuntimeError("no A4 emission time reaches the Petz threshold")
    selected_t = int(selected["t"])
    channel = channels[selected_t]
    choi = choi_tableau(channel)
    choi_qubits = len(choi)
    signed_choi_group_size = 1 << choi_qubits
    operator_checks = int(selected["support_operator_basis_size"])
    if operator_checks > MAX_OPERATOR_CHECKS:
        raise RuntimeError(
            f"A4 operator budget exceeded: {operator_checks}>{MAX_OPERATOR_CHECKS}"
        )
    if signed_choi_group_size > MAX_SIGNED_CHOI_GROUP_SIZE:
        raise RuntimeError(
            "A4 signed-Choi group budget exceeded: "
            f"{signed_choi_group_size}>{MAX_SIGNED_CHOI_GROUP_SIZE}"
        )

    code_started = time.perf_counter()
    code = input_support_code(layout, scrambler, selected_t)
    code_seconds = time.perf_counter() - code_started
    _check_runtime_budget(started, "support-code extraction")
    synthesis_started = time.perf_counter()
    direct_gates, _, output_tableau, _ = signed_dilation(
        layout, channel, scrambler, selected_t
    )
    synthesis_seconds = time.perf_counter() - synthesis_started
    _check_runtime_budget(started, "signed Clifford synthesis")
    routing_started = time.perf_counter()
    routed = route_line(layout, selected_t, direct_gates)
    routing_seconds = time.perf_counter() - routing_started
    direct_validation_started = time.perf_counter()
    direct_validation = validate(layout, channel, scrambler, selected_t)
    direct_validation_seconds = time.perf_counter() - direct_validation_started
    _check_runtime_budget(started, "direct full operator validation")
    routed_validation_started = time.perf_counter()
    routed_validation = validate(
        layout,
        channel,
        scrambler,
        selected_t,
        physical_gates_override=routed.gates,
    )
    routed_validation_seconds = time.perf_counter() - routed_validation_started
    _check_runtime_budget(started, "routed full operator validation")

    recovery, _ = petz(channel)
    state_rows: list[dict[str, object]] = []
    for label, (message, expected_bits, emoji) in _state_tests().items():
        input_density = np.outer(message, message.conj())
        channel_output = apply_channel(channel, input_density)
        abstract_output = sum(
            (r @ channel_output @ r.conj().T for r in recovery),
            start=np.zeros((16, 16), dtype=complex),
        )
        outputs = (
            ("Petz abstrait", abstract_output),
            (
                "Clifford direct",
                _physical_output(layout, scrambler, direct_gates, message, selected_t),
            ),
            (
                "Clifford route chaine",
                _physical_output(layout, scrambler, routed.gates, message, selected_t),
            ),
        )
        for method, output in outputs:
            probabilities = np.real(np.diag(output))
            decoded_bits = f"{int(np.argmax(probabilities)):04b}" if expected_bits else ""
            state_rows.append(
                {
                    "test_kind": "basis_symbol" if expected_bits else "superposition",
                    "method": method,
                    "input_state": label,
                    "primary_binary_symbol": expected_bits,
                    "visual_emoji_label": emoji,
                    "decoded_binary_symbol": decoded_bits,
                    "decoded_emoji_label": (
                        EMOJIS[int(decoded_bits, 2)] if decoded_bits else ""
                    ),
                    "basis_symbol_correct": (
                        decoded_bits == expected_bits if expected_bits else ""
                    ),
                    "state_fidelity": float(np.real(np.vdot(message, output @ message))),
                }
            )

    resources = [
        {
            "method": "Petz abstrait",
            "entanglement_fidelity": selected["petz_entanglement_fidelity"],
            "choi_fidelity": 1.0,
            "operator_error": 0.0,
            "two_qubit_depth": "",
            "cnot": "",
            "swap": "",
            "environment_qubits": len(output_tableau) - layout.n_message,
            "validation_seconds": "",
        },
        {
            "method": "Clifford direct",
            "entanglement_fidelity": direct_validation["circuit_fidelity"],
            "choi_fidelity": direct_validation["choi_fidelity"],
            "operator_error": direct_validation["operator_error"],
            "two_qubit_depth": direct_validation["logical_depth"],
            "cnot": direct_validation["cnot_count"],
            "swap": 0,
            "environment_qubits": len(output_tableau) - layout.n_message,
            "validation_seconds": direct_validation_seconds,
        },
        {
            "method": "Clifford route chaine",
            "entanglement_fidelity": routed_validation["circuit_fidelity"],
            "choi_fidelity": routed_validation["choi_fidelity"],
            "operator_error": routed_validation["operator_error"],
            "two_qubit_depth": routed.two_qubit_depth,
            "cnot": routed.cnot_count,
            "swap": routed.swap_count,
            "environment_qubits": len(output_tableau) - layout.n_message,
            "validation_seconds": routed_validation_seconds,
        },
    ]
    for resource_row in resources:
        state_rows.append(
            {
                "test_kind": "maximally_entangled_reference",
                "method": resource_row["method"],
                "input_state": "Phi_16(R:A)",
                "primary_binary_symbol": "",
                "visual_emoji_label": "",
                "decoded_binary_symbol": "",
                "decoded_emoji_label": "",
                "basis_symbol_correct": "",
                "state_fidelity": resource_row["entanglement_fidelity"],
            }
        )

    keep_choi_qubits = len(output_tableau) + int(code["logical_qubits"])
    metadata = {
        "status": "validated",
        "message_qubits": layout.n_message,
        "alphabet_size": 1 << layout.n_message,
        "black_hole_qubits": layout.n_black_hole,
        "total_simulated_qubits": layout.n_qubits,
        "scrambled_qubits": len(layout.scrambled),
        "scrambler_connected": True,
        "seed": SEED,
        "scramble_depth": SCRAMBLE_DEPTH,
        "selected_t": selected_t,
        "support_rank": code["support_dimension"],
        "support_logical_qubits": code["logical_qubits"],
        "support_stabilizers": code["independent_stabilizers"],
        "full_operator_checks": operator_checks,
        "choi_petz_is_stabilizer": True,
        "choi_purification_qubits": choi_qubits,
        "signed_choi_group_size": signed_choi_group_size,
        "choi_purification_vector_mib": (1 << choi_qubits) * 16 / 2**20,
        "dense_purification_projector_gib_avoided": (1 << (2 * choi_qubits)) * 16 / 2**30,
        "dense_validation_choi_gib_avoided": (1 << (2 * keep_choi_qubits)) * 16 / 2**30,
        "symplectic_candidate_space_size": 1 << (2 * len(layout.X(selected_t))),
        "physical_chain": "-".join(map(str, layout.chain(selected_t))),
        "final_order_restored": routed.final_wire_at_site == layout.chain(selected_t),
        "code_extraction_seconds": code_seconds,
        "synthesis_seconds": synthesis_seconds,
        "routing_seconds": routing_seconds,
        "direct_validation_seconds": direct_validation_seconds,
        "routed_validation_seconds": routed_validation_seconds,
        "total_seconds": time.perf_counter() - started,
        "initial_rss_mib": initial_rss,
        "peak_rss_mib": _rss_mib(),
        "max_rss_budget_mib": MAX_RSS_MIB,
        "max_seconds_budget": MAX_SECONDS,
        "dense_choi_matrices_avoided": True,
    }
    assert direct_validation["validated"] and routed_validation["validated"]
    _check_runtime_budget(started, "completed preflight")
    return timeline, state_rows, resources, metadata


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(timeline, state_rows, resources, metadata) -> None:
    output = Path("results")
    output.mkdir(exist_ok=True)
    _write_csv(output / "a4_preflight_timeline.csv", timeline)
    _write_csv(output / "a4_preflight_state_tests.csv", state_rows)
    _write_csv(output / "a4_preflight_resources.csv", resources)
    _write_csv(output / "a4_preflight_feasibility.csv", [metadata])

    timeline_lines = "\n".join(
        "| {t} | {mutual_information_R_C_bits} | {trace_distance_rhoRC_product:.12g} | "
        "{petz_entanglement_fidelity:.15g} | {support_rank_tau_X} | "
        "{support_operator_basis_size} | {elapsed_seconds:.3f} | {peak_rss_mib:.1f} |".format(**row)
        for row in timeline
    )
    resource_lines = "\n".join(
        f"| {row['method']} | {float(row['entanglement_fidelity']):.15g} | "
        f"{float(row['choi_fidelity']):.15g} | {float(row['operator_error']):.3g} | "
        f"{row['two_qubit_depth']} | {row['cnot']} | {row['swap']} | "
        f"{row['validation_seconds']} |"
        for row in resources
    )
    minimum_fidelities = {
        method: min(
            float(row["state_fidelity"])
            for row in state_rows
            if row["method"] == method
        )
        for method in ("Petz abstrait", "Clifford direct", "Clifford route chaine")
    }
    emoji_mapping = "  ".join(
        f"`{index:04b}={emoji}`" for index, emoji in enumerate(EMOJIS)
    )
    report = f"""# Pré-vol collectif |A|=4

Statut : **validé dans le budget fixé**. Budget : {MAX_RSS_MIB:.0f} Mio RSS et
{MAX_SECONDS:.0f} s pour cette instance unique. Aucun calcul `|A|=8` n'est lancé.

## Configuration

- message collectif : 4 qubits, dimension 16 ;
- B=4, E=4, total : {metadata['total_simulated_qubits']} qubits ;
- brouilleur Clifford unique et connecté sur {metadata['scrambled_qubits']} qubits ;
- graine {metadata['seed']}, profondeur {metadata['scramble_depth']} ;
- plancher attendu sans information : `1/16² = 1/256`.

## Chronologie avant synthèse

Le découplage est calculé exactement par les rangs des sous-groupes
stabilisateurs. Dans ce cas pur à spectres plats, les projecteurs de support
sont emboîtés et la distance en trace vaut exactement `1-2^(-I)` ; aucune
matrice `rho_RC` dense n'est construite.

| t | I(R:C) | distance trace | fidélité Petz | rang support | opérateurs² | secondes | RSS Mio |
|---:|---:|---:|---:|---:|---:|---:|---:|
{timeline_lines}

Le premier temps tel que `F_Petz>0,99` est `t={metadata['selected_t']}`. Son
support a le rang {metadata['support_rank']} et exige
{metadata['full_operator_checks']} contrôles opératoriels.

Les valeurs de fidélité légèrement supérieures à 1 sont conservées brutes et
proviennent des arrondis flottants. À `t=8`, l'erreur de conservation de la
trace sur support atteint `{timeline[8]['support_trace_preservation_error']:.3g}`,
légèrement au-dessus de `1e-12`; ce temps n'est pas utilisé pour la synthèse.
À `t={metadata['selected_t']}`, cette erreur vaut
`{timeline[metadata['selected_t']]['support_trace_preservation_error']:.3g}`.

## Faisabilité et évitement des objets denses

- Choi Petz stabilisateur : `{metadata['choi_petz_is_stabilizer']}` ;
- purification Choi : {metadata['choi_purification_qubits']} qubits,
  {metadata['choi_purification_vector_mib']:.1f} Mio comme vecteur ;
- groupe stabilisateur signé : {metadata['signed_choi_group_size']} éléments ;
- espace candidat symplectique actuel : {metadata['symplectic_candidate_space_size']} vecteurs ;
- projecteur dense de purification évité :
  {metadata['dense_purification_projector_gib_avoided']:.1f} Gio ;
- matrice Choi dense de validation évitée :
  {metadata['dense_validation_choi_gib_avoided']:.1f} Gio.

La pseudo-inverse de Petz et les comparaisons Choi utilisent leurs facteurs de
support exacts. Il ne s'agit ni d'un échantillonnage, ni d'une validation
partielle.

## Récupérateur construit à t={metadata['selected_t']}

| réalisation | fidélité intrication | fidélité Choi | erreur opératorielle | profondeur 2q | CNOT | SWAP | validation s |
|---|---:|---:|---:|---:|---:|---:|---:|
{resource_lines}

Chaîne : `{metadata['physical_chain']}` ; ordre final restauré :
`{metadata['final_order_restored']}`. Temps total :
`{metadata['total_seconds']:.3f} s`. RSS maximale :
`{metadata['peak_rss_mib']:.1f} Mio`.

## Alphabet de 16 symboles

Les codes binaires restent les données primaires. La table emoji est seulement
une couche d'affichage :

{emoji_mapping}

Les 16 états de base, `(0000+1111)/sqrt(2)`,
`(0001+i1110)/sqrt(2)`, un état complexe aléatoire et l'état maximal
`Phi_16(R:A)` sont testés. Fidélités minimales :

- Petz abstrait : `{minimum_fidelities['Petz abstrait']:.15g}` ;
- Clifford direct : `{minimum_fidelities['Clifford direct']:.15g}` ;
- Clifford routé : `{minimum_fidelities['Clifford route chaine']:.15g}`.

## Limites

Une seule instance Clifford idéale est validée. Les coûts ne constituent pas
une loi d'échelle et aucune minimalité n'est prouvée. Le compilateur emploie
encore des espaces exponentiels de taille {metadata['signed_choi_group_size']}
et {metadata['symplectic_candidate_space_size']} ; cela interdit d'extrapoler
directement à un alphabet de 256 symboles.
"""
    Path("docs/notes/A4_COLLECTIVE_PREFLIGHT.md").write_text(report)


def main() -> None:
    timeline, state_rows, resources, metadata = run_preflight()
    write_outputs(timeline, state_rows, resources, metadata)
    print(
        f"A=4 preflight: selected t={metadata['selected_t']}; "
        f"Petz={resources[0]['entanglement_fidelity']:.15g}; "
        f"direct={resources[1]['entanglement_fidelity']:.15g}; "
        f"routed={resources[2]['entanglement_fidelity']:.15g}"
    )
    print(
        f"checks={metadata['full_operator_checks']}; "
        f"depth={resources[1]['two_qubit_depth']}->{resources[2]['two_qubit_depth']}; "
        f"SWAP={resources[2]['swap']}; RSS={metadata['peak_rss_mib']:.1f} MiB; "
        f"elapsed={metadata['total_seconds']:.3f} s"
    )


if __name__ == "__main__":
    main()
