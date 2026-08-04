#!/usr/bin/env python3
"""One genuinely collective two-qubit-message Clifford/Petz experiment."""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

import numpy as np

from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_channels import (
    channel_at_time,
    environment_state,
    random_scrambler,
)
from hayden_preskill_toy.parametric_petz import entanglement_fidelity, petz, support_rank
from hayden_preskill_toy.parametric_routing import route_line
from hayden_preskill_toy.parametric_stabilizer import input_support_code
from hayden_preskill_toy.parametric_synthesis import signed_dilation
from hayden_preskill_toy.parametric_validation import validate
from hayden_preskill_toy.simulator import Gate, X, apply_1q, apply_circuit, bell_pair, zero_state


SEED = 20260802
SCRAMBLE_DEPTH = 6
SELECTED_T = 3
TOLERANCE = 1e-12


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


def _compress_kraus(kraus: tuple[np.ndarray, ...]) -> tuple[np.ndarray, ...]:
    output_dimension, input_dimension = kraus[0].shape
    choi_dimension = output_dimension * input_dimension
    choi = sum(
        (np.outer(k.reshape(-1), k.reshape(-1).conj()) for k in kraus),
        start=np.zeros((choi_dimension, choi_dimension), dtype=complex),
    )
    values, vectors = np.linalg.eigh((choi + choi.conj().T) / 2)
    cutoff = TOLERANCE * max(float(values[-1]), 1.0)
    compact = tuple(
        np.sqrt(value) * vectors[:, index].reshape(output_dimension, input_dimension)
        for index, value in enumerate(values)
        if value > cutoff
    )
    complete = sum(
        (k.conj().T @ k for k in compact),
        start=np.zeros((input_dimension, input_dimension), dtype=complex),
    )
    if np.linalg.norm(complete - np.eye(input_dimension)) >= 1e-10:
        raise AssertionError("compressed channel is not trace preserving")
    return compact


def _effective_output_kraus(
    layout: SystemLayout,
    scrambler: list[Gate],
    decoder: list[Gate] | tuple[Gate, ...],
    t: int,
) -> tuple[np.ndarray, ...]:
    input_dimension = 1 << layout.n_message
    output = layout.X(t)[: layout.n_message]
    matrices: list[np.ndarray] = []
    for basis_index in range(input_dimension):
        state = environment_state(layout)
        for offset, qubit in enumerate(layout.A_register):
            if basis_index >> (layout.n_message - offset - 1) & 1:
                state = apply_1q(state, X, qubit, layout.n_qubits)
        state = apply_circuit(state, scrambler, layout.n_qubits)
        state = apply_circuit(state, list(decoder), layout.n_qubits)
        rest = tuple(q for q in range(layout.n_qubits) if q not in output)
        matrices.append(
            np.transpose(
                state.reshape((2,) * layout.n_qubits), (*output, *rest)
            ).reshape(input_dimension, -1)
        )
    kraus = tuple(
        np.stack([matrix[:, column] for matrix in matrices], axis=1)
        for column in range(matrices[0].shape[1])
    )
    return _compress_kraus(kraus)


def _apply_channel(kraus: tuple[np.ndarray, ...], rho: np.ndarray) -> np.ndarray:
    return sum(
        (k @ rho @ k.conj().T for k in kraus), start=np.zeros_like(rho)
    )


def _channel_operator_error(
    actual: tuple[np.ndarray, ...], reference: tuple[np.ndarray, ...]
) -> float:
    dimension = actual[0].shape[1]
    maximum = 0.0
    for row in range(dimension):
        for column in range(dimension):
            operator = np.zeros((dimension, dimension), dtype=complex)
            operator[row, column] = 1
            difference = _apply_channel(actual, operator) - _apply_channel(reference, operator)
            maximum = max(maximum, float(np.linalg.norm(difference, 2)))
    return maximum


def _state_tests() -> dict[str, np.ndarray]:
    basis = np.eye(4, dtype=complex)
    rng = np.random.default_rng(271828)
    random_state = rng.normal(size=4) + 1j * rng.normal(size=4)
    random_state /= np.linalg.norm(random_state)
    return {
        "|00>": basis[0],
        "|01>": basis[1],
        "|10>": basis[2],
        "|11>": basis[3],
        "(|00>+|11>)/sqrt(2)": (basis[0] + basis[3]) / np.sqrt(2),
        "(|01>+i|10>)/sqrt(2)": (basis[1] + 1j * basis[2]) / np.sqrt(2),
        "uniforme_4": np.ones(4, dtype=complex) / 2,
        "etat_aleatoire_seed271828": random_state,
    }


def _connected_scrambler(layout: SystemLayout, scrambler: list[Gate]) -> bool:
    adjacency = {qubit: set() for qubit in layout.scrambled}
    for gate in scrambler:
        if gate.name == "CNOT":
            assert gate.b is not None
            adjacency[gate.a].add(gate.b)
            adjacency[gate.b].add(gate.a)
    reached = {layout.scrambled[0]}
    frontier = list(reached)
    while frontier:
        qubit = frontier.pop()
        for neighbour in adjacency[qubit] - reached:
            reached.add(neighbour)
            frontier.append(neighbour)
    return reached == set(layout.scrambled)


@lru_cache(maxsize=1)
def run_experiment():
    layout = SystemLayout(n_message=2, n_black_hole=4)
    scrambler = random_scrambler(
        layout, np.random.default_rng(SEED), SCRAMBLE_DEPTH
    )
    if not _connected_scrambler(layout, scrambler):
        raise AssertionError("the selected scrambling interaction graph is disconnected")

    global_state = zero_state(layout.n_qubits)
    for left, right in (*zip(layout.R_register, layout.A_register), *zip(layout.B, layout.E)):
        global_state = bell_pair(global_state, left, right, layout.n_qubits)
    global_state = apply_circuit(global_state, scrambler, layout.n_qubits)

    timeline: list[dict[str, object]] = []
    for t in range(len(layout.scrambled) + 1):
        channel = channel_at_time(layout, scrambler, t)
        mutual_information, trace_distance = _decoupling(layout, global_state, t)
        fidelity, info = entanglement_fidelity(channel)
        timeline.append(
            {
                "t": t,
                "accessible_qubits": len(layout.X(t)),
                "inaccessible_qubits": len(layout.C(t)),
                "mutual_information_R_C_bits": mutual_information,
                "trace_distance_rhoRC_product": trace_distance,
                "petz_entanglement_fidelity": fidelity,
                "support_rank_tau_X": support_rank(channel),
                "support_trace_preservation_error": info[
                    "support_trace_preservation_error"
                ],
            }
        )

    channel = channel_at_time(layout, scrambler, SELECTED_T)
    recovery, _ = petz(channel)
    abstract_kraus = _compress_kraus(
        tuple(r @ k for r in recovery for k in channel.kraus)
    )
    direct_gates, _, output_tableau, _ = signed_dilation(
        layout, channel, scrambler, SELECTED_T
    )
    routed = route_line(layout, SELECTED_T, direct_gates)
    direct_validation = validate(layout, channel, scrambler, SELECTED_T)
    routed_validation = validate(
        layout,
        channel,
        scrambler,
        SELECTED_T,
        physical_gates_override=routed.gates,
    )
    direct_kraus = _effective_output_kraus(
        layout, scrambler, direct_gates, SELECTED_T
    )
    routed_kraus = _effective_output_kraus(
        layout, scrambler, routed.gates, SELECTED_T
    )

    methods = (
        ("Petz abstrait", abstract_kraus, 1.0, 0.0),
        (
            "Clifford direct",
            direct_kraus,
            direct_validation["choi_fidelity"],
            _channel_operator_error(direct_kraus, abstract_kraus),
        ),
        (
            "Clifford route chaine",
            routed_kraus,
            routed_validation["choi_fidelity"],
            _channel_operator_error(routed_kraus, abstract_kraus),
        ),
    )
    state_rows: list[dict[str, object]] = []
    for method, kraus, choi_fidelity, operator_error in methods:
        for label, state in _state_tests().items():
            output = _apply_channel(kraus, np.outer(state, state.conj()))
            state_rows.append(
                {
                    "method": method,
                    "input_state": label,
                    "state_fidelity": float(np.real(np.vdot(state, output @ state))),
                    "choi_fidelity_to_parametric_petz": choi_fidelity,
                    "operator_error_to_parametric_petz": operator_error,
                }
            )

    code = input_support_code(layout, scrambler, SELECTED_T)
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
        },
    ]
    metadata = {
        "message_qubits": layout.n_message,
        "black_hole_qubits": layout.n_black_hole,
        "early_radiation_qubits": len(layout.E),
        "total_simulated_qubits": layout.n_qubits,
        "scrambled_qubits": len(layout.scrambled),
        "scrambler_connected": True,
        "seed": SEED,
        "scramble_depth": SCRAMBLE_DEPTH,
        "selected_t": SELECTED_T,
        "physical_chain": "-".join(map(str, layout.chain(SELECTED_T))),
        "support_rank": code["support_dimension"],
        "support_logical_qubits": code["logical_qubits"],
        "support_stabilizers": code["independent_stabilizers"],
        "final_order_restored": routed.final_wire_at_site == layout.chain(SELECTED_T),
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
    _write_csv(output / "collective_two_qubit_timeline.csv", timeline)
    _write_csv(output / "collective_two_qubit_state_tests.csv", state_rows)
    _write_csv(output / "collective_two_qubit_resources.csv", resources)

    timeline_lines = "\n".join(
        "| {t} | {mutual_information_R_C_bits:.12g} | "
        "{trace_distance_rhoRC_product:.12g} | {petz_entanglement_fidelity:.15g} | "
        "{support_rank_tau_X} |".format(**row)
        for row in timeline
    )
    resource_lines = "\n".join(
        f"| {row['method']} | {float(row['entanglement_fidelity']):.15g} | "
        f"{float(row['choi_fidelity']):.15g} | {float(row['operator_error']):.3g} | "
        f"{row['two_qubit_depth']} | {row['cnot']} | {row['swap']} |"
        for row in resources
    )
    minimum_state_fidelity = {
        method: min(
            float(row["state_fidelity"])
            for row in state_rows
            if row["method"] == method
        )
        for method in ("Petz abstrait", "Clifford direct", "Clifford route chaine")
    }
    report = f"""# Message collectif de deux qubits

## Construction

Cette expérience utilise une seule dynamique Clifford collective sur
`A0,A1,B0,B1,B2,B3`. Les deux qubits-message sont chacun initialement intriqués
avec un qubit de référence, puis les deux font partie du même brouilleur. Le
graphe des CNOT de la graine {metadata['seed']} est connecté sur les six qubits
brouillés. Il ne s'agit donc pas de deux usages indépendants assemblés après
le calcul.

Configuration : `|A|=2`, `|B|=|E|=4`, {metadata['total_simulated_qubits']} qubits
simulés, profondeur de brouillage {metadata['scramble_depth']}. La compilation
complète est évaluée à `t={metadata['selected_t']}`, avant l'émission totale
(`t=6`).

## Disponibilité et Petz abstrait

| t | I(R:C) bits | distance en trace | fidélité Petz | rang supp(tau_X) |
|---:|---:|---:|---:|---:|
{timeline_lines}

À `t=3`, `I(R:C)={timeline[SELECTED_T]['mutual_information_R_C_bits']:.3g}` et la
distance en trace vaut `{timeline[SELECTED_T]['trace_distance_rhoRC_product']:.3g}`.
Ce sont des indicateurs quantitatifs de découplage dans ce modèle fini ; ils ne
constituent pas une équivalence générale sans borne.

## Canal collectif construit

Le support d'entrée a le rang {metadata['support_rank']}, soit
{metadata['support_logical_qubits']} qubits logiques et
{metadata['support_stabilizers']} stabilisateurs indépendants. La dilatation
rejette {resources[1]['environment_qubits']} qubits d'environnement.

| réalisation | fidélité d'intrication | fidélité Choi | erreur opératorielle | profondeur 2q | CNOT | SWAP |
|---|---:|---:|---:|---:|---:|---:|
{resource_lines}

La chaîne physique est `{metadata['physical_chain']}` et sa permutation finale
est restituée exactement. Le routage multiplie ici la profondeur observée par
`{int(resources[2]['two_qubit_depth']) / int(resources[1]['two_qubit_depth']):.3f}`.

## États vérifiés

La base complète `|00>`, `|01>`, `|10>`, `|11>`, deux superpositions avec
intrication ou phase relative, la superposition uniforme et un état complexe
aléatoire ont été transmis. Les fidélités minimales sont :

- Petz abstrait : `{minimum_state_fidelity['Petz abstrait']:.15g}` ;
- Clifford direct : `{minimum_state_fidelity['Clifford direct']:.15g}` ;
- Clifford routé : `{minimum_state_fidelity['Clifford route chaine']:.15g}`.

La validation opératorielle porte en plus sur toute la base d'opérateurs du
support d'entrée, pas seulement sur ces états exemples.

## Limites

Il s'agit d'une instance Clifford idéale, sans bruit, avec B=4 et une seule
graine. Cette réussite ne fournit ni loi d'échelle, ni profondeur minimale, ni
résultat sur un message classique long. Elle établit seulement que le pipeline
paramétrique sait traiter un message de deux qubits réellement brouillé et
récupéré collectivement. Aucun calcul `|A|=3` n'a été lancé.
"""
    Path("docs/notes/COLLECTIVE_TWO_QUBIT_MESSAGE.md").write_text(report)


def main() -> None:
    timeline, state_rows, resources, metadata = run_experiment()
    write_outputs(timeline, state_rows, resources, metadata)
    print(
        f"collective |A|=2: t={SELECTED_T}; "
        f"Petz={resources[0]['entanglement_fidelity']:.15g}; "
        f"direct={resources[1]['entanglement_fidelity']:.15g}; "
        f"routed={resources[2]['entanglement_fidelity']:.15g}"
    )
    print(
        f"depth direct={resources[1]['two_qubit_depth']}; "
        f"depth routed={resources[2]['two_qubit_depth']}; "
        f"SWAP={resources[2]['swap']}"
    )


if __name__ == "__main__":
    main()
