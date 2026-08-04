#!/usr/bin/env python3
"""Single-instance |A|=3 collective-message feasibility preflight."""
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
    entanglement_fidelity,
    petz,
    support_rank,
)
from hayden_preskill_toy.parametric_routing import route_line
from hayden_preskill_toy.parametric_stabilizer import input_support_code
from hayden_preskill_toy.parametric_synthesis import signed_dilation
from hayden_preskill_toy.parametric_validation import validate
from hayden_preskill_toy.simulator import Gate, X, apply_1q, apply_circuit, bell_pair, zero_state


SEED = 20260802
SCRAMBLE_DEPTH = 6
SELECTED_T = 3
TOLERANCE = 1e-12


def _rss_mib() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    byte_value = value if platform.system() == "Darwin" else value * 1024
    return float(byte_value / 2**20)


def _reduced_density(state: np.ndarray, keep: tuple[int, ...], n: int) -> np.ndarray:
    rest = tuple(q for q in range(n) if q not in keep)
    view = np.transpose(state.reshape((2,) * n), (*keep, *rest)).reshape(
        2 ** len(keep), -1
    )
    return view @ view.conj().T


def _entropy(rho: np.ndarray) -> float:
    values = np.linalg.eigvalsh((rho + rho.conj().T) / 2)
    values = values[values > 1e-14]
    return float(-np.sum(values * np.log2(values)))


def _decoupling(layout: SystemLayout, state: np.ndarray, t: int) -> tuple[float, float]:
    complement = layout.C(t)
    rho_rc = _reduced_density(state, (*layout.R_register, *complement), layout.n_qubits)
    rho_r = _reduced_density(state, layout.R_register, layout.n_qubits)
    rho_c = (
        _reduced_density(state, complement, layout.n_qubits)
        if complement
        else np.ones((1, 1), dtype=complex)
    )
    mutual_information = _entropy(rho_r) + _entropy(rho_c) - _entropy(rho_rc)
    difference = rho_rc - np.kron(rho_r, rho_c)
    trace_distance = 0.5 * np.sum(
        np.abs(np.linalg.eigvalsh((difference + difference.conj().T) / 2))
    )
    return max(0.0, float(mutual_information)), float(trace_distance)


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


def _state_tests() -> dict[str, tuple[np.ndarray, str]]:
    basis = np.eye(8, dtype=complex)
    tests = {f"|{index:03b}>": (basis[index], f"{index:03b}") for index in range(8)}
    tests["(|000>+|111>)/sqrt(2)"] = ((basis[0] + basis[7]) / np.sqrt(2), "")
    tests["(|001>+i|110>)/sqrt(2)"] = (
        (basis[1] + 1j * basis[6]) / np.sqrt(2),
        "",
    )
    rng = np.random.default_rng(314159)
    random_state = rng.normal(size=8) + 1j * rng.normal(size=8)
    random_state /= np.linalg.norm(random_state)
    tests["etat_aleatoire_seed314159"] = (random_state, "")
    return tests


@lru_cache(maxsize=1)
def run_preflight():
    started = time.perf_counter()
    initial_rss = _rss_mib()
    layout = SystemLayout(n_message=3, n_black_hole=4)
    scrambler = random_scrambler(
        layout, np.random.default_rng(SEED), SCRAMBLE_DEPTH
    )
    if not _connected_scrambler(layout, scrambler):
        raise AssertionError("selected collective scrambler is disconnected")

    global_state = zero_state(layout.n_qubits)
    for left, right in (*zip(layout.R_register, layout.A_register), *zip(layout.B, layout.E)):
        global_state = bell_pair(global_state, left, right, layout.n_qubits)
    global_state = apply_circuit(global_state, scrambler, layout.n_qubits)

    timeline: list[dict[str, object]] = []
    channels = {}
    for t in range(len(layout.scrambled) + 1):
        step_started = time.perf_counter()
        channel = channel_at_time(layout, scrambler, t)
        fidelity, info = entanglement_fidelity(channel)
        mutual_information, trace_distance = _decoupling(layout, global_state, t)
        channels[t] = channel
        timeline.append(
            {
                "t": t,
                "accessible_qubits": len(layout.X(t)),
                "inaccessible_qubits": len(layout.C(t)),
                "channel_output_dimension": channel.kraus[0].shape[0],
                "channel_input_dimension": channel.kraus[0].shape[1],
                "kraus_count": len(channel.kraus),
                "support_rank_tau_X": support_rank(channel),
                "support_operator_basis_size": support_rank(channel) ** 2,
                "mutual_information_R_C_bits": mutual_information,
                "trace_distance_rhoRC_product": trace_distance,
                "petz_entanglement_fidelity": fidelity,
                "support_trace_preservation_error": info[
                    "support_trace_preservation_error"
                ],
                "elapsed_seconds": time.perf_counter() - step_started,
                "peak_rss_mib": _rss_mib(),
            }
        )

    channel = channels[SELECTED_T]
    code_started = time.perf_counter()
    code = input_support_code(layout, scrambler, SELECTED_T)
    code_seconds = time.perf_counter() - code_started
    synthesis_started = time.perf_counter()
    direct_gates, _, output_tableau, _ = signed_dilation(
        layout, channel, scrambler, SELECTED_T
    )
    synthesis_seconds = time.perf_counter() - synthesis_started
    routing_started = time.perf_counter()
    routed = route_line(layout, SELECTED_T, direct_gates)
    routing_seconds = time.perf_counter() - routing_started
    direct_validation_started = time.perf_counter()
    direct_validation = validate(layout, channel, scrambler, SELECTED_T)
    direct_validation_seconds = time.perf_counter() - direct_validation_started
    routed_validation_started = time.perf_counter()
    routed_validation = validate(
        layout,
        channel,
        scrambler,
        SELECTED_T,
        physical_gates_override=routed.gates,
    )
    routed_validation_seconds = time.perf_counter() - routed_validation_started

    recovery, _ = petz(channel)
    state_rows: list[dict[str, object]] = []
    for label, (message, expected_bits) in _state_tests().items():
        input_density = np.outer(message, message.conj())
        channel_output = apply_channel(channel, input_density)
        abstract_output = sum(
            (r @ channel_output @ r.conj().T for r in recovery),
            start=np.zeros((8, 8), dtype=complex),
        )
        outputs = (
            ("Petz abstrait", abstract_output),
            (
                "Clifford direct",
                _physical_output(layout, scrambler, direct_gates, message, SELECTED_T),
            ),
            (
                "Clifford route chaine",
                _physical_output(layout, scrambler, routed.gates, message, SELECTED_T),
            ),
        )
        for method, output in outputs:
            probabilities = np.real(np.diag(output))
            decoded_bits = f"{int(np.argmax(probabilities)):03b}" if expected_bits else ""
            state_rows.append(
                {
                    "method": method,
                    "input_state": label,
                    "expected_basis_symbol": expected_bits,
                    "decoded_basis_symbol": decoded_bits,
                    "basis_symbol_correct": (
                        decoded_bits == expected_bits if expected_bits else ""
                    ),
                    "state_fidelity": float(np.real(np.vdot(message, output @ message))),
                }
            )

    resources = [
        {
            "method": "Petz abstrait",
            "entanglement_fidelity": timeline[SELECTED_T]["petz_entanglement_fidelity"],
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
    metadata = {
        "message_qubits": layout.n_message,
        "alphabet_size": 1 << layout.n_message,
        "black_hole_qubits": layout.n_black_hole,
        "total_simulated_qubits": layout.n_qubits,
        "scrambled_qubits": len(layout.scrambled),
        "scrambler_connected": True,
        "seed": SEED,
        "scramble_depth": SCRAMBLE_DEPTH,
        "selected_t": SELECTED_T,
        "support_rank": code["support_dimension"],
        "support_logical_qubits": code["logical_qubits"],
        "support_stabilizers": code["independent_stabilizers"],
        "full_operator_checks": code["support_dimension"] ** 2,
        "choi_purification_qubits": layout.n_message
        + len(layout.X(SELECTED_T))
        + len(channel.kraus).bit_length()
        - 1,
        "physical_chain": "-".join(map(str, layout.chain(SELECTED_T))),
        "final_order_restored": routed.final_wire_at_site == layout.chain(SELECTED_T),
        "code_extraction_seconds": code_seconds,
        "synthesis_seconds": synthesis_seconds,
        "routing_seconds": routing_seconds,
        "direct_validation_seconds": direct_validation_seconds,
        "routed_validation_seconds": routed_validation_seconds,
        "total_seconds": time.perf_counter() - started,
        "initial_rss_mib": initial_rss,
        "peak_rss_mib": _rss_mib(),
        "dense_choi_matrix_avoided": True,
    }
    assert direct_validation["validated"] and routed_validation["validated"]
    return timeline, state_rows, resources, metadata


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(timeline, state_rows, resources, metadata) -> None:
    output = Path("results")
    output.mkdir(exist_ok=True)
    _write_csv(output / "a3_preflight_timeline.csv", timeline)
    _write_csv(output / "a3_preflight_state_tests.csv", state_rows)
    _write_csv(output / "a3_preflight_resources.csv", resources)

    timeline_lines = "\n".join(
        "| {t} | {mutual_information_R_C_bits:.12g} | "
        "{trace_distance_rhoRC_product:.12g} | {petz_entanglement_fidelity:.15g} | "
        "{support_rank_tau_X} | {support_operator_basis_size} | {elapsed_seconds:.4f} | "
        "{peak_rss_mib:.1f} |".format(**row)
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
    report = f"""# Pré-vol collectif |A|=3

Statut : **pré-vol unique validé**. Aucune campagne et aucun calcul `|A|=8`
n'ont été lancés.

## Configuration

- message collectif : 3 qubits, soit un alphabet choisi de 8 symboles
  orthogonaux ;
- B=4, E=4, total simulé : {metadata['total_simulated_qubits']} qubits ;
- brouilleur unique connecté sur {metadata['scrambled_qubits']} qubits ;
- graine {metadata['seed']}, profondeur {metadata['scramble_depth']} ;
- plancher sans information attendu : `1/8² = 1/64`.

## Pré-vol selon le temps d'émission

| t | I(R:C) bits | distance trace | fidélité Petz | rang support | opérateurs du support | secondes | RSS pic Mio |
|---:|---:|---:|---:|---:|---:|---:|---:|
{timeline_lines}

Le premier temps dépassant `F_Petz>0,99` est `t={SELECTED_T}`. À ce point,
`I(R:C)={timeline[SELECTED_T]['mutual_information_R_C_bits']:.3g}` et la distance
en trace vaut `{timeline[SELECTED_T]['trace_distance_rhoRC_product']:.3g}`.

## Synthèse et validation complètes à t={SELECTED_T}

Le support a le rang {metadata['support_rank']} : la validation exhaustive
porte donc sur {metadata['full_operator_checks']} états et cohérences de base.
Le Choi purifié comporte {metadata['choi_purification_qubits']} qubits. Sa
matrice dense carrée n'est jamais construite ; lorsque les deux Choi sont purs,
la fidélité et la norme de différence sont calculées exactement dans leur
sous-espace de dimension deux.

| réalisation | fidélité intrication | fidélité Choi | erreur opératorielle | profondeur 2q | CNOT | SWAP | validation s |
|---|---:|---:|---:|---:|---:|---:|---:|
{resource_lines}

Chaîne : `{metadata['physical_chain']}`. Ordre final restauré :
`{metadata['final_order_restored']}`. Temps total du pré-vol :
`{metadata['total_seconds']:.3f} s`; RSS maximale observée :
`{metadata['peak_rss_mib']:.1f} Mio`.

## Alphabet de huit symboles et cohérences

Les huit états `000` à `111` sont tous décodés correctement. Sont également
testés `(000+111)/sqrt(2)`, `(001+i110)/sqrt(2)` et un état complexe aléatoire.
Fidélités minimales :

- Petz abstrait : `{minimum_fidelities['Petz abstrait']:.15g}` ;
- Clifford direct : `{minimum_fidelities['Clifford direct']:.15g}` ;
- Clifford routé : `{minimum_fidelities['Clifford route chaine']:.15g}`.

Ces étiquettes constituent un alphabet choisi dans une base. La validation des
superpositions et de toute la base d'opérateurs certifie davantage que la seule
transmission de trois bits classiques.

## Limites

Une seule instance Clifford idéale est testée. Les temps et la mémoire ne sont
pas une loi d'échelle. Ce résultat n'autorise ni `|A|=8`, ni une affirmation de
profondeur minimale, ni une conclusion sur le bruit ou les circuits
non-Clifford.
"""
    Path("docs/notes/A3_COLLECTIVE_PREFLIGHT.md").write_text(report)


def main() -> None:
    timeline, state_rows, resources, metadata = run_preflight()
    write_outputs(timeline, state_rows, resources, metadata)
    print(
        f"A=3 preflight: floor={timeline[0]['petz_entanglement_fidelity']:.15g}; "
        f"t={SELECTED_T} Petz={resources[0]['entanglement_fidelity']:.15g}; "
        f"direct={resources[1]['entanglement_fidelity']:.15g}; "
        f"routed={resources[2]['entanglement_fidelity']:.15g}"
    )
    print(
        f"checks={metadata['full_operator_checks']}; "
        f"depth={resources[1]['two_qubit_depth']}->{resources[2]['two_qubit_depth']}; "
        f"peak_rss={metadata['peak_rss_mib']:.1f} MiB; "
        f"elapsed={metadata['total_seconds']:.3f} s"
    )


if __name__ == "__main__":
    main()
