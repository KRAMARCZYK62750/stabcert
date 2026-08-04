"""Experiment definition and statistically reproducible aggregation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv
from itertools import product
import numpy as np

from .simulator import Gate, apply_circuit, bell_fidelity, bell_pair, zero_state

# Register order.  A is absorbed and, together with B, becomes five emitted slots D0..D4.
R, A = 0, 1
B = (2, 3, 4, 5)
E = (6, 7, 8, 9)
N_QUBITS = 10
SCRAMBLED = (A, *B)


@dataclass(frozen=True)
class Config:
    seed: int = 20260802
    trials: int = 50
    decoder_samples: int = 1
    depths: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6, 8)
    output_dir: str = "results"


def initial_state() -> np.ndarray:
    state = bell_pair(zero_state(N_QUBITS), R, A, N_QUBITS)
    for b, e in zip(B, E):
        state = bell_pair(state, b, e, N_QUBITS)
    return state


def random_scrambler(rng: np.random.Generator, layers: int) -> list[Gate]:
    gates: list[Gate] = []
    q = list(SCRAMBLED)
    for _ in range(layers):
        for x in q:
            name = ("H", "S")[int(rng.integers(2))]
            gates.append(Gate(name, x))
        rng.shuffle(q)
        for c, target in zip(q[::2], q[1::2]):
            gates.append(Gate("CNOT", c, target))
    return gates


def random_decoder(rng: np.random.Generator, accessible: tuple[int, ...], depth: int) -> list[Gate]:
    """Witness ensemble: depth counts layers containing at most one two-qubit gate."""
    gates: list[Gate] = []
    if not accessible:
        return gates
    for _ in range(depth):
        for q in accessible:
            if rng.random() < 0.35:
                gates.append(Gate(("H", "S")[int(rng.integers(2))], q))
        if len(accessible) >= 2:
            c, target = rng.choice(accessible, 2, replace=False)
            gates.append(Gate("CNOT", int(c), int(target)))
    return gates


def inverse_decoder(scrambler: list[Gate], accessible: tuple[int, ...]) -> list[Gate] | None:
    """Known-U construction, only if every qubit touched by U is accessible."""
    # The caller applies this circuit with inverse=True; this matters for S -> S†.
    return scrambler if set(SCRAMBLED).issubset(accessible) else None


def two_qubit_depth(circuit: list[Gate]) -> int:
    """Greedy valid layering of ordered CNOTs; one-qubit gates cost zero here."""
    layers: list[set[int]] = []
    for gate in circuit:
        if gate.name != "CNOT":
            continue
        assert gate.b is not None
        used = {gate.a, gate.b}
        for layer in layers:
            if not (layer & used):
                layer.update(used)
                break
        else:
            layers.append(set(used))
    return len(layers)


def bounded_clifford_search(state: np.ndarray, accessible: tuple[int, ...], output: int,
                            max_depth: int) -> tuple[list[Gate], float]:
    """Exhaustive witness for <=3 accessible qubits and depth <=2.

    This deliberately tiny enumerator is supplied for validation experiments, not
    used in the 4E prototype (whose access register is already larger).  It does
    not certify an optimum beyond the enumerated gate set and bound.
    """
    if len(accessible) > 3 or max_depth > 2:
        raise ValueError("bounded search is intentionally limited to <=3 qubits and depth <=2")
    local_choices = list(product(("I", "H", "S"), repeat=len(accessible)))
    entanglers: list[tuple[int, int] | None] = [None] + [(a, b) for a in accessible for b in accessible if a != b]
    layers: list[list[Gate]] = []
    for local in local_choices:
        singles = [Gate(name, q) for q, name in zip(accessible, local) if name != "I"]
        for pair in entanglers:
            layers.append(singles + ([] if pair is None else [Gate("CNOT", *pair)]))
    best_circuit: list[Gate] = []
    best_score = bell_fidelity(state, R, output, N_QUBITS)
    frontier = [([], state)]
    for _ in range(max_depth):
        new_frontier = []
        for prefix, partial in frontier:
            for layer in layers:
                candidate = prefix + layer
                evolved = apply_circuit(partial, layer, N_QUBITS)
                score = bell_fidelity(evolved, R, output, N_QUBITS)
                if score > best_score:
                    best_circuit, best_score = candidate, score
                new_frontier.append((candidate, evolved))
        frontier = new_frontier
    return best_circuit, best_score


def access_set(t: int, mode: str) -> tuple[int, ...]:
    emitted = SCRAMBLED[:t]
    if mode == "cumulative":
        return (*E, *emitted)
    if mode == "last_only":
        return (*E, emitted[-1]) if emitted else E
    if mode == "no_early":
        return emitted
    raise ValueError(mode)


def evaluate_trial(scrambler: list[Gate], rng: np.random.Generator, t: int, depth: int, mode: str,
                   decoder_samples: int) -> list[float]:
    scrambled = apply_circuit(initial_state(), scrambler, N_QUBITS)
    accessible = access_set(t, mode)
    values: list[float] = []
    # A random witness circuit is never claimed to be optimal; retain the best sampled witness.
    for _ in range(decoder_samples):
        candidate = random_decoder(rng, accessible, depth)
        state = apply_circuit(scrambled.copy(), candidate, N_QUBITS)
        values.append(bell_fidelity(state, R, A, N_QUBITS))
    inv = inverse_decoder(scrambler, accessible)
    if inv is not None and depth >= two_qubit_depth(inv):
        state = apply_circuit(scrambled.copy(), inv, N_QUBITS, inverse=True)
        values.append(bell_fidelity(state, R, A, N_QUBITS))
    return values


def run(config: Config) -> list[dict[str, object]]:
    rng = np.random.default_rng(config.seed)
    rows: list[dict[str, object]] = []
    regimes = {"none": 0, "weak": 1, "deep": 6}
    for regime, layers in regimes.items():
        for mode in ("cumulative", "no_early", "last_only"):
            for t in range(1, len(SCRAMBLED) + 1):
                for depth in config.depths:
                    scores = []
                    for _ in range(config.trials):
                        scores.append(max(evaluate_trial(random_scrambler(rng, layers), rng, t, depth, mode,
                                                       config.decoder_samples)))
                    a = np.asarray(scores)
                    rows.append({"regime": regime, "access": mode, "t": t, "k": depth,
                                 "trials": config.trials, "mean_fidelity": a.mean(),
                                 "median_fidelity": np.median(a), "std_fidelity": a.std(),
                                 "proportion_ge_090": np.mean(a >= .90),
                                 "proportion_ge_099": np.mean(a >= .99)})
    return rows


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def run_decoupling_and_petz(config: Config) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Phase A plus explicit Petz recovery; no SDP and no depth claim."""
    from .channels import channel_at_time, channel_validation, decoupling_metrics, petz_entanglement_fidelity
    from .stabilizer import diagnostics as stabilizer_diagnostics

    rng = np.random.default_rng(config.seed + 1)
    decoupling_rows: list[dict[str, object]] = []
    recovery_rows: list[dict[str, object]] = []
    regimes = {"none": 0, "weak": 1, "deep": 6}
    witness_depths = (0, 2, 4, 6, 8)
    for regime, layers in regimes.items():
        for trial in range(config.trials):
            scrambler = random_scrambler(rng, layers)
            state = apply_circuit(initial_state(), scrambler, N_QUBITS)
            for t in range(1, len(SCRAMBLED) + 1):
                cumulative_metrics = None
                for access_name, has_e in (("E_plus_D", True), ("D_only", False)):
                    metrics = decoupling_metrics(state, t, include_early_radiation=has_e)
                    if has_e:
                        cumulative_metrics = metrics
                    decoupling_rows.append({"regime": regime, "trial": trial, "t": t, "access_model": access_name,
                                             **metrics})
                channel = channel_at_time(scrambler, t)
                validation = channel_validation(channel)
                petz_fidelity, petz_info = petz_entanglement_fidelity(channel)
                stabilizer = stabilizer_diagnostics(scrambler, N_QUBITS, R, A, B, E, t)
                assert cumulative_metrics is not None
                h2 = cumulative_metrics["conditional_collision_entropy_bits"]
                information = cumulative_metrics["mutual_information_bits"]
                audit = {"mutual_information_bits": information, "H2_R_given_C_bits": h2, "renyi2_candidate": 2 ** (h2 - 1),
                         "von_neumann_candidate": 2 ** (-information),
                         "stabilizer_rank_formula": cumulative_metrics["rank_rho_RC"] / (2 * cumulative_metrics["rank_rho_C"]),
                         "petz_minus_stabilizer_rank_formula": petz_fidelity - cumulative_metrics["rank_rho_RC"] / (2 * cumulative_metrics["rank_rho_C"]),
                         "petz_minus_renyi2_candidate": petz_fidelity - 2 ** (h2 - 1),
                         "petz_minus_von_neumann_candidate": petz_fidelity - 2 ** (-information),
                         "rank_rho_RC": cumulative_metrics["rank_rho_RC"], "rank_rho_C": cumulative_metrics["rank_rho_C"],
                         "spectrum_rho_RC": cumulative_metrics["spectrum_rho_RC"], "spectrum_rho_C": cumulative_metrics["spectrum_rho_C"]}
                recovery_rows.append({"regime": regime, "trial": trial, "t": t, "algorithm": "petz",
                                      "two_qubit_depth": "", "entanglement_fidelity": petz_fidelity,
                                      **validation, **petz_info, **audit, **stabilizer})
                accessible = access_set(t, "cumulative")
                for depth in witness_depths:
                    decoded = apply_circuit(state.copy(), random_decoder(rng, accessible, depth), N_QUBITS)
                    recovery_rows.append({"regime": regime, "trial": trial, "t": t,
                                          "algorithm": "random_witness", "two_qubit_depth": depth,
                                          "entanglement_fidelity": bell_fidelity(decoded, R, A, N_QUBITS),
                                          **validation, **petz_info, **audit, **stabilizer})
                inv = inverse_decoder(scrambler, accessible)
                if inv is not None:
                    decoded = apply_circuit(state.copy(), inv, N_QUBITS, inverse=True)
                    recovery_rows.append({"regime": regime, "trial": trial, "t": t, "algorithm": "U_inverse_control",
                                          "two_qubit_depth": two_qubit_depth(inv),
                                          "entanglement_fidelity": bell_fidelity(decoded, R, A, N_QUBITS),
                                          **validation, **petz_info, **audit, **stabilizer})
    return decoupling_rows, recovery_rows


def summarize(rows: list[dict[str, object]], group: tuple[str, ...], value: str) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    keys = sorted({tuple(row[k] for k in group) for row in rows})
    for key in keys:
        values = np.asarray([float(row[value]) for row in rows if tuple(row[k] for k in group) == key])
        result.append(dict(zip(group, key)) | {"count": len(values), "mean": values.mean(), "median": np.median(values),
                                                "std": values.std(), "q10": np.quantile(values, .10),
                                                "q50": np.quantile(values, .50), "q90": np.quantile(values, .90)})
    return result
