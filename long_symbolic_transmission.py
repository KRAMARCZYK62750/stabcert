#!/usr/bin/env python3
"""Long symbolic transmission through independent uses of the B=4 Petz channel.

The eleven-symbol alphabet in ``ORELIA EST VIVANTE`` cannot fit into the
eight orthogonal states supplied by three qubits.  This experiment therefore
uses four independent, parallel copies of the already validated one-qubit
channel per character.  It does not change the underlying Hayden--Preskill
toy instance and does not inject a four-qubit message into one instance.
"""
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
from hayden_preskill_toy.parametric_petz import entanglement_fidelity, petz
from hayden_preskill_toy.parametric_routing import route_line
from hayden_preskill_toy.parametric_synthesis import signed_dilation
from hayden_preskill_toy.parametric_validation import validate
from hayden_preskill_toy.simulator import Gate, X, apply_1q, apply_circuit


MESSAGE = "ORELIA EST VIVANTE"
SYMBOL_WIDTH = 4
SEED = 20260802
SCRAMBLE_DEPTH = 6
EMISSION_TIME = 2
TOLERANCE = 1e-12

# Stable order by first appearance in the message.  Eleven symbols require
# ceil(log2(11)) = 4 bits; the remaining five code words are unused.
ALPHABET = tuple(dict.fromkeys(MESSAGE))
SYMBOLS = {symbol: f"{index:0{SYMBOL_WIDTH}b}" for index, symbol in enumerate(ALPHABET)}


def _compress_kraus(kraus: tuple[np.ndarray, ...]) -> tuple[np.ndarray, ...]:
    """Return a minimal numerical Kraus family from the 2x2 Choi matrix."""
    choi = sum(
        (np.outer(k.reshape(-1), k.reshape(-1).conj()) for k in kraus),
        start=np.zeros((4, 4), dtype=complex),
    )
    values, vectors = np.linalg.eigh((choi + choi.conj().T) / 2)
    cutoff = TOLERANCE * max(float(values[-1]), 1.0)
    compact = tuple(
        np.sqrt(value) * vectors[:, index].reshape(2, 2)
        for index, value in enumerate(values)
        if value > cutoff
    )
    completeness = sum(
        (k.conj().T @ k for k in compact), start=np.zeros((2, 2), dtype=complex)
    )
    if np.linalg.norm(completeness - np.eye(2)) >= 1e-10:
        raise AssertionError("compressed effective channel is not trace preserving")
    return compact


def _effective_output_kraus(
    layout: SystemLayout,
    scrambler: list[Gate],
    decoder: list[Gate] | tuple[Gate, ...],
    t: int,
) -> tuple[np.ndarray, ...]:
    """Extract A -> A'=X(t)[0] Kraus operators from an actual circuit."""
    columns: list[np.ndarray] = []
    output = layout.X(t)[0]
    for bit in range(2):
        state = environment_state(layout)
        if bit:
            state = apply_1q(state, X, layout.A, layout.n_qubits)
        state = apply_circuit(state, scrambler, layout.n_qubits)
        state = apply_circuit(state, list(decoder), layout.n_qubits)
        rest = tuple(q for q in range(layout.n_qubits) if q != output)
        matrix = np.transpose(
            state.reshape((2,) * layout.n_qubits), (output, *rest)
        ).reshape(2, -1)
        columns.append(matrix)
    kraus = tuple(
        np.stack((columns[0][:, index], columns[1][:, index]), axis=1)
        for index in range(columns[0].shape[1])
    )
    return _compress_kraus(kraus)


def _entanglement_fidelity(kraus: tuple[np.ndarray, ...]) -> float:
    return float(np.real(sum(abs(np.trace(k)) ** 2 for k in kraus) / 4))


def _lift(kraus: np.ndarray, qubit: int, n: int) -> np.ndarray:
    left = np.eye(1 << qubit, dtype=complex)
    right = np.eye(1 << (n - qubit - 1), dtype=complex)
    return np.kron(np.kron(left, kraus), right)


def _apply_product_channel(
    operator: np.ndarray, kraus: tuple[np.ndarray, ...], n: int = SYMBOL_WIDTH
) -> np.ndarray:
    result = operator
    for qubit in range(n):
        lifted = tuple(_lift(k, qubit, n) for k in kraus)
        result = sum(
            (k @ result @ k.conj().T for k in lifted),
            start=np.zeros_like(result),
        )
    return result


def _product_operator_error(
    actual: tuple[np.ndarray, ...], reference: tuple[np.ndarray, ...]
) -> float:
    """Maximum spectral error on all 16x16 matrix units."""
    dimension = 1 << SYMBOL_WIDTH
    maximum = 0.0
    for row in range(dimension):
        for column in range(dimension):
            operator = np.zeros((dimension, dimension), dtype=complex)
            operator[row, column] = 1
            difference = _apply_product_channel(operator, actual) - _apply_product_channel(
                operator, reference
            )
            maximum = max(maximum, float(np.linalg.norm(difference, 2)))
    return maximum


def _ket(bits: str) -> np.ndarray:
    vector = np.zeros(1 << SYMBOL_WIDTH, dtype=complex)
    vector[int(bits, 2)] = 1
    return vector


def _display(symbol: str) -> str:
    return "ESPACE" if symbol == " " else symbol


@lru_cache(maxsize=1)
def run_experiment() -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    """Run the 18-character experiment and return detail, summary, metadata."""
    layout = SystemLayout(n_black_hole=4)
    scrambler = random_scrambler(
        layout, np.random.default_rng(SEED), SCRAMBLE_DEPTH
    )
    channel = channel_at_time(layout, scrambler, EMISSION_TIME)
    recovery, _ = petz(channel)
    abstract_kraus = _compress_kraus(
        tuple(r @ k for r in recovery for k in channel.kraus)
    )

    direct_gates, _, output_tableau, _ = signed_dilation(
        layout, channel, scrambler, EMISSION_TIME
    )
    routed = route_line(layout, EMISSION_TIME, direct_gates)
    direct_validation = validate(layout, channel, scrambler, EMISSION_TIME)
    routed_validation = validate(
        layout,
        channel,
        scrambler,
        EMISSION_TIME,
        physical_gates_override=routed.gates,
    )
    direct_kraus = _effective_output_kraus(
        layout, scrambler, direct_gates, EMISSION_TIME
    )
    routed_kraus = _effective_output_kraus(
        layout, scrambler, routed.gates, EMISSION_TIME
    )

    abstract_fidelity, _ = entanglement_fidelity(channel)
    if abs(_entanglement_fidelity(abstract_kraus) - abstract_fidelity) >= TOLERANCE:
        raise AssertionError("effective abstract channel disagrees with Petz fidelity")
    if abs(_entanglement_fidelity(direct_kraus) - direct_validation["circuit_fidelity"]) >= TOLERANCE:
        raise AssertionError("effective direct circuit disagrees with validation")
    if abs(_entanglement_fidelity(routed_kraus) - routed_validation["circuit_fidelity"]) >= TOLERANCE:
        raise AssertionError("effective routed circuit disagrees with validation")

    logical_cnot_single = int(direct_validation["cnot_count"])
    logical_depth = int(direct_validation["logical_depth"])
    environment_qubits = len(output_tableau) - 1
    methods = (
        {
            "method": "Petz abstrait",
            "kraus": abstract_kraus,
            "entanglement_fidelity_single": abstract_fidelity,
            "choi_fidelity_single": 1.0,
            "operator_error_single": 0.0,
            "logical_depth": None,
            "routed_depth": None,
            "logical_cnot": None,
            "routed_cnot": None,
            "swaps": None,
        },
        {
            "method": "Clifford direct",
            "kraus": direct_kraus,
            "entanglement_fidelity_single": direct_validation["circuit_fidelity"],
            "choi_fidelity_single": direct_validation["choi_fidelity"],
            "operator_error_single": direct_validation["operator_error"],
            "logical_depth": logical_depth,
            "routed_depth": None,
            "logical_cnot": SYMBOL_WIDTH * logical_cnot_single,
            "routed_cnot": None,
            "swaps": 0,
        },
        {
            "method": "Clifford route chaine",
            "kraus": routed_kraus,
            "entanglement_fidelity_single": routed_validation["circuit_fidelity"],
            "choi_fidelity_single": routed_validation["choi_fidelity"],
            "operator_error_single": routed_validation["operator_error"],
            "logical_depth": logical_depth,
            "routed_depth": routed.two_qubit_depth,
            "logical_cnot": SYMBOL_WIDTH * logical_cnot_single,
            "routed_cnot": SYMBOL_WIDTH * routed.cnot_count,
            "swaps": SYMBOL_WIDTH * routed.swap_count,
        },
    )

    product_errors = {
        str(method["method"]): _product_operator_error(
            method["kraus"], abstract_kraus  # type: ignore[arg-type]
        )
        for method in methods
    }
    detail: list[dict[str, object]] = []
    for method in methods:
        kraus = method["kraus"]
        for position, symbol in enumerate(MESSAGE, start=1):
            bits = SYMBOLS[symbol]
            state = _ket(bits)
            output = _apply_product_channel(np.outer(state, state.conj()), kraus)  # type: ignore[arg-type]
            probabilities = np.real(np.diag(output))
            decoded_index = int(np.argmax(probabilities))
            decoded_bits = f"{decoded_index:0{SYMBOL_WIDTH}b}"
            decoded = next(
                (letter for letter, code in SYMBOLS.items() if code == decoded_bits),
                f"NON_UTILISE_{decoded_bits}",
            )
            state_fidelity = float(np.real(np.vdot(state, output @ state)))
            detail.append(
                {
                    "position": position,
                    "method": method["method"],
                    "symbol_sent": symbol,
                    "symbol_sent_display": _display(symbol),
                    "symbol_code": bits,
                    "symbol_decoded": decoded,
                    "symbol_decoded_display": _display(decoded),
                    "correct": decoded == symbol,
                    "symbol_state_fidelity": state_fidelity,
                    "largest_readout_probability": float(probabilities[decoded_index]),
                    "entanglement_fidelity_single_use": method["entanglement_fidelity_single"],
                    "entanglement_fidelity_character": float(method["entanglement_fidelity_single"]) ** SYMBOL_WIDTH,
                    "choi_fidelity_single_use": method["choi_fidelity_single"],
                    "choi_fidelity_character": float(method["choi_fidelity_single"]) ** SYMBOL_WIDTH,
                    "operator_error_single_use": method["operator_error_single"],
                    "operator_error_character": product_errors[str(method["method"])],
                    "logical_depth_per_character": method["logical_depth"] if method["logical_depth"] is not None else "",
                    "routed_depth_per_character": method["routed_depth"] if method["routed_depth"] is not None else "",
                    "logical_cnot_per_character": method["logical_cnot"] if method["logical_cnot"] is not None else "",
                    "routed_cnot_per_character": method["routed_cnot"] if method["routed_cnot"] is not None else "",
                    "swap_per_character": method["swaps"] if method["swaps"] is not None else "",
                }
            )

    summary: list[dict[str, object]] = []
    for method in methods:
        method_rows = [row for row in detail if row["method"] == method["method"]]
        reconstructed = "".join(str(row["symbol_decoded"]) for row in method_rows)
        numeric_costs = {
            name: [int(row[name]) for row in method_rows if row[name] != ""]
            for name in (
                "logical_depth_per_character",
                "routed_depth_per_character",
                "logical_cnot_per_character",
                "routed_cnot_per_character",
                "swap_per_character",
            )
        }
        summary_row: dict[str, object] = {
            "method": method["method"],
            "message_sent": MESSAGE,
            "message_decoded": reconstructed,
            "character_count": len(method_rows),
            "correct_characters": sum(bool(row["correct"]) for row in method_rows),
            "character_accuracy": float(np.mean([bool(row["correct"]) for row in method_rows])),
            "mean_symbol_state_fidelity": float(np.mean([float(row["symbol_state_fidelity"]) for row in method_rows])),
            "mean_entanglement_fidelity_character": float(np.mean([float(row["entanglement_fidelity_character"]) for row in method_rows])),
            "mean_choi_fidelity_character": float(np.mean([float(row["choi_fidelity_character"]) for row in method_rows])),
            "mean_operator_error_character": float(np.mean([float(row["operator_error_character"]) for row in method_rows])),
        }
        for name, values in numeric_costs.items():
            prefix = name.removesuffix("_per_character")
            summary_row[f"mean_{prefix}_per_character"] = float(np.mean(values)) if values else ""
            summary_row[f"total_{prefix}"] = sum(values) if values else ""
            if values:
                assert summary_row[f"total_{prefix}"] == sum(
                    int(row[name]) for row in method_rows
                )
        summary_row["elementary_cost_sum_verified"] = True
        summary.append(summary_row)

    metadata = {
        "B": layout.n_black_hole,
        "t": EMISSION_TIME,
        "seed": SEED,
        "scramble_depth": SCRAMBLE_DEPTH,
        "symbol_width": SYMBOL_WIDTH,
        "alphabet_size": len(ALPHABET),
        "message_length": len(MESSAGE),
        "environment_qubits_per_use": environment_qubits,
        "logical_depth_per_use": logical_depth,
        "logical_cnot_per_use": logical_cnot_single,
        "routed_depth_per_use": routed.two_qubit_depth,
        "routed_cnot_per_use": routed.cnot_count,
        "swap_per_use": routed.swap_count,
    }
    return detail, summary, metadata


def write_outputs(
    detail: list[dict[str, object]],
    summary: list[dict[str, object]],
    metadata: dict[str, object],
) -> None:
    output_directory = Path("results")
    output_directory.mkdir(exist_ok=True)
    detail_path = output_directory / "long_symbolic_transmission.csv"
    summary_path = output_directory / "long_symbolic_transmission_summary.csv"
    with detail_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(detail[0]))
        writer.writeheader()
        writer.writerows(detail)
    with summary_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

    table_rows = []
    for row in summary:
        table_rows.append(
            "| {method} | `{message_decoded}` | {correct_characters}/{character_count} | "
            "{character_accuracy:.12g} | {mean_symbol_state_fidelity:.15g} | "
            "{mean_entanglement_fidelity_character:.15g} |".format(**row)
        )
    direct = next(row for row in summary if row["method"] == "Clifford direct")
    routed = next(row for row in summary if row["method"] == "Clifford route chaine")
    mapping = "  ".join(
        f"`{'ESPACE' if symbol == ' ' else symbol}={bits}`"
        for symbol, bits in SYMBOLS.items()
    )
    report = f"""# Transmission symbolique longue

## Résultat numérique

Instance inchangée : B={metadata['B']}, t={metadata['t']}, graine={metadata['seed']},
profondeur de brouillage={metadata['scramble_depth']}. Le texte est traité comme
une suite de {metadata['message_length']} symboles sans signification particulière.

| décodeur | sortie | caractères corrects | taux correct | fidélité moyenne des symboles | fidélité d'intrication par caractère |
|---|---|---:|---:|---:|---:|
{chr(10).join(table_rows)}

Entrée : `{MESSAGE}`  
Sortie Petz abstrait : `{summary[0]['message_decoded']}`  
Sortie Clifford direct : `{summary[1]['message_decoded']}`  
Sortie Clifford routé : `{summary[2]['message_decoded']}`

## Encodage effectivement utilisé

Le message contient {metadata['alphabet_size']} symboles distincts. Trois usages
indépendants ne fournissent que 8 états orthogonaux ; ils sont donc
dimensionnellement insuffisants. Après validation explicite, cette expérience
emploie **quatre usages parallèles indépendants du canal un-qubit par caractère**,
soit 16 mots de code possibles :

{mapping}

Ce changement ne crée pas un message de quatre qubits dans une seule dynamique
Hayden--Preskill. Chaque caractère mobilise quatre exemplaires indépendants de
l'instance B=4 déjà validée.

## Coûts observés

Les quatre usages d'un caractère sont parallèles : leurs profondeurs ne
s'additionnent pas, tandis que CNOT et SWAP sont des comptes agrégés. Les 18
caractères sont comptés successivement pour le coût total du message.

| réalisation | profondeur/caractère | CNOT/caractère | SWAP/caractère | profondeur totale séquentielle | CNOT totaux | SWAP totaux |
|---|---:|---:|---:|---:|---:|---:|
| Clifford direct | {int(direct['mean_logical_depth_per_character'])} | {int(direct['mean_logical_cnot_per_character'])} | 0 | {direct['total_logical_depth']} | {direct['total_logical_cnot']} | 0 |
| Clifford routé | {int(routed['mean_routed_depth_per_character'])} | {int(routed['mean_routed_cnot_per_character'])} | {int(routed['mean_swap_per_character'])} | {routed['total_routed_depth']} | {routed['total_routed_cnot']} | {routed['total_swap']} |

Pour chaque colonne de coût applicable, le total a été recalculé comme somme
des 18 coûts élémentaires et l'égalité est vérifiée automatiquement. Petz
abstrait n'a pas de coût de circuit attribué.

## Portée

Cette expérience vérifie uniquement que le pipeline paramétrique déjà validé
fonctionne sur une séquence plus longue. Elle ne démontre aucune propriété
nouvelle du canal, aucun stockage de document, aucun chiffrement et aucun
brouillage collectif d'un message de quatre qubits.

Les valeurs par caractère sont dans
`results/long_symbolic_transmission.csv`; les agrégats sont dans
`results/long_symbolic_transmission_summary.csv`.
"""
    Path("docs/notes/LONG_SYMBOLIC_TRANSMISSION.md").write_text(report)


def main() -> None:
    detail, summary, metadata = run_experiment()
    write_outputs(detail, summary, metadata)
    for row in summary:
        print(
            f"{row['method']}: input {row['message_sent']} -> "
            f"output {row['message_decoded']}; "
            f"correct={row['correct_characters']}/{row['character_count']}; "
            f"mean fidelity={row['mean_symbol_state_fidelity']:.15g}"
        )


if __name__ == "__main__":
    main()
