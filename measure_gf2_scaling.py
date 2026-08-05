#!/usr/bin/env python3
"""Measure the GF(2) cost of channel-certified verification versus width.

The composed worst-case bound on the elimination routines is loose: it
multiplies one factor of ``n`` per nesting level.  The counters in
``hayden_preskill_toy.gf2`` give the exact number of eliminations actually
performed, which is deterministic and free of timing noise.  This script
sweeps a Hayden--Preskill family, records those counters, and reports which
of them are exact polynomials in the accessible width.

Scope of the measured family, which bounds what any extrapolation may claim:
the scrambler is a depth-6 random Clifford on a chain, so the stabilizer
generators are dense and the affine systems solved here are dense too.  This
is the unfavourable end.  Codes with local, low-weight stabilizers -- surface
codes, LDPC families -- produce sparse systems, and the cost may then be
governed by generator weight and lattice structure rather than by width
alone.  Extrapolating these numbers to such a code gives an upper bound, not
a prediction.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import time

import numpy as np

from hayden_preskill_toy.gf2 import count_operations
from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_petz_stabilizer import random_stabilizer_scrambler
from hayden_preskill_toy.recovery_compile import compile_recovery
from hayden_preskill_toy.recovery_hayden_preskill_adapter import (
    hayden_preskill_to_recovery_problem,
)
from hayden_preskill_toy.recovery_problem import RouterParameters
from hayden_preskill_toy.recovery_verify import VerificationPolicy, verify_recovery

SEED = 20260802
SCRAMBLE_DEPTH = 6
ARCHITECTURE = "chain"
COUNTERS = (
    # Structural: how many eliminations the nesting performs.  Exact.
    "affine_systems_solved",
    # Work: row XORs are vectorized by NumPy, so machine cost tracks this one.
    "row_xors",
    # Machine-model-independent upper bound; overcounts vectorized work by ~n.
    "scalar_bit_xors",
    "rank_reductions",
    "pivots",
)
CALIBRATOR_FOR_CONTROL = "affine_systems_solved"
EXACTNESS_TOLERANCE = 1e-9
# Degrees predicted by composing the nesting with the cost of one elimination:
# n**2 eliminations, each a Gaussian elimination costing ~n**3 row operations,
# each row operation touching ~n bits.  The measurement tests these, it does
# not assume them; observed local exponents sit above and decrease with n.
#
# What a "confirmed" verdict is an exponent OF.  These are exponents of this
# family as parameterized -- depth-6 scrambler, t = A + 4 -- whose generator
# density is not constant along n but drifts as roughly n**-0.24.  A confirmed
# exponent is therefore b + c*delta, mixing the degree at fixed density with
# the cost of that drift, not the fixed-density degree.  The joint regression
# in ``compare_density_cost.py`` separates them and finds a density elasticity
# of about 1.4, so the two quantities genuinely differ.  Confirmation stands;
# its object is the family, not the algorithm in the abstract.
STRUCTURAL_PREDICTION = {
    "affine_systems_solved": 2,
    "row_xors": 5,
    "scalar_bit_xors": 6,
}


def _scrambler_connects_all(layout: SystemLayout, gates) -> bool:
    """A scrambler that leaves a qubit isolated makes the instance degenerate."""
    adjacency = {qubit: set() for qubit in layout.scrambled}
    for gate in gates:
        if gate.name == "CNOT" and gate.b is not None:
            adjacency[gate.a].add(gate.b)
            adjacency[gate.b].add(gate.a)
    reached = {layout.scrambled[0]}
    pending = [layout.scrambled[0]]
    while pending:
        for neighbour in adjacency[pending.pop()] - reached:
            reached.add(neighbour)
            pending.append(neighbour)
    return len(reached) == len(layout.scrambled)


def _density(artifact) -> dict[str, float]:
    """Pauli weight of the derived tau support, the operational density metric."""
    weights = [
        sum(letter != "I" for letter in spec.operators)
        for spec in artifact.tau_support.signed_generators
    ]
    width = len(artifact.logical_circuit.qubit_order)
    return {
        "tau_generator_count": len(weights),
        "mean_generator_weight": float(np.mean(weights)) if weights else 0.0,
        "max_generator_weight": max(weights, default=0),
        "mean_generator_density": float(np.mean(weights)) / width if weights else 0.0,
    }


def measure(message_sizes: range, scramble_depth: int = SCRAMBLE_DEPTH) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for message in message_sizes:
        layout = SystemLayout(n_message=message, n_black_hole=4)
        scrambler = random_stabilizer_scrambler(
            layout, np.random.default_rng(SEED), scramble_depth
        )
        if not _scrambler_connects_all(layout, scrambler):
            print(f"A={message}: scrambler leaves an isolated qubit; instance skipped")
            continue
        emission = message + layout.n_black_hole
        problem = hayden_preskill_to_recovery_problem(
            layout,
            scrambler,
            emission,
            architecture=ARCHITECTURE,
            router=RouterParameters(lookahead=16, candidate_budget=64),
        )
        artifact = compile_recovery(problem)
        start = time.perf_counter()
        with count_operations() as stats:
            report = verify_recovery(
                problem, artifact, policy=VerificationPolicy.CHANNEL_CERTIFIED
            )
        elapsed = time.perf_counter() - start
        if not report.verified:
            raise AssertionError(f"instance A={message} did not verify")
        rows.append(
            {
                "message_qubits": message,
                "emission_time": emission,
                "accessible_width": len(problem.accessible_partition),
                "scramble_depth": scramble_depth,
                "logical_qubits": artifact.tau_support.logical_qubits,
                "support_rank": artifact.tau_support.support_rank,
                **_density(artifact),
                **{name: getattr(stats, name) for name in COUNTERS},
                "verify_seconds": elapsed,
            }
        )
    return rows


def _exact_degree(widths: np.ndarray, values: np.ndarray) -> int | None:
    for degree in range(1, min(6, len(widths) - 1)):
        fit = np.polyfit(widths, values, degree)
        if np.abs(np.polyval(fit, widths) - values).max() <= EXACTNESS_TOLERANCE * values.max():
            return degree
    return None


def analyse(rows: list[dict[str, object]]) -> dict[str, object]:
    widths = np.asarray([row["accessible_width"] for row in rows], dtype=float)
    summary: dict[str, object] = {}
    for name in (*COUNTERS, "verify_seconds"):
        values = np.asarray([row[name] for row in rows], dtype=float)
        upper = max(2, len(widths) // 2)
        entry: dict[str, object] = {
            "log_log_exponent_all_points": float(
                np.polyfit(np.log(widths), np.log(values), 1)[0]
            ),
            "log_log_exponent_upper_half": float(
                np.polyfit(np.log(widths[-upper:]), np.log(values[-upper:]), 1)[0]
            ),
            "log_log_exponent_last_step": float(
                np.log(values[-1] / values[-2]) / np.log(widths[-1] / widths[-2])
            ),
        }
        if name in STRUCTURAL_PREDICTION:
            entry["structural_prediction"] = STRUCTURAL_PREDICTION[name]
        degree = _exact_degree(widths, values)
        if degree is not None:
            coefficients = np.polyfit(widths, values, degree)
            entry["exact_polynomial_degree"] = degree
            entry["exact_polynomial_coefficients"] = [
                float(np.round(value)) for value in coefficients
            ]
        entry["log_log_exponent_lower_window"] = float(
            np.polyfit(np.log(widths[:upper]), np.log(values[:upper]), 1)[0]
        )
        summary[name] = entry
    return summary


def evaluate_prediction(summary: dict[str, object]) -> dict[str, object]:
    """Decide the structural composition against a pre-registered criterion.

    Registered on 4 August 2026, before the n=21..30 sweep was read.

    Finite-size bias inflates every measured exponent, so the observed value
    cannot be compared to the target directly.  ``affine_systems_solved`` is
    known exactly (degree 2), so the same instances calibrate that bias:
    ``tolerance = max(observed - 2, 0.1)`` on the upper window.

    Per counter, with ``excess = observed_upper - target``:

    - confirmed  : excess <= tolerance and the exponent is still decreasing;
    - rejected   : excess > 2 * tolerance, or the exponent rose by >= 0.1;
    - undecided  : anything else -- and only this verdict justifies extending
      the sweep, because a plateau above target is then not yet separable
      from a lower-order term that has not washed out.

    Termination, registered 4 August 2026 before the n=31..40 sweep was read.
    The bias of this family is known in closed form from the exact identity,
    ``b(n) = (232n - 1196) / (28n^2 - 232n + 598) -> 8.286/n``, so excess and
    tolerance shrink together and ``undecided`` can repeat at a constant
    ratio forever.  The sweep therefore stops at n=40 whatever the verdict.
    If n=40 is undecided and ``excess / tolerance`` has moved by less than
    0.05 from its n<=30 value, the dense family is declared exhausted and the
    result is published as "undecided over n=9..40, consistent with the
    structural composition, not confirmed at threshold".  Remaining compute
    goes to a sparse instance instead, which tests whether cost follows
    generator density rather than width -- the question this family cannot
    answer at any length.

    A bias-corrected extrapolation ``e(n) = d + K/n`` was evaluated as a
    faster route and rejected: run against the calibrator, whose degree is
    known to be exactly 2, it returns d = 1.929 with a jackknife spread of
    [1.927, 1.930], excluding the truth with a spuriously tight interval.
    The 1/n form is only the leading correction, so its residuals are
    systematic.  Do not reinstate it without a control that passes.
    """
    calibrator = summary["affine_systems_solved"]
    bias = float(calibrator["log_log_exponent_upper_half"]) - float(
        STRUCTURAL_PREDICTION["affine_systems_solved"]
    )
    tolerance = max(bias, 0.1)
    verdicts: dict[str, object] = {
        "registered": "2026-08-04, before reading the n=21..30 sweep",
        "calibrator": "affine_systems_solved (exact degree 2)",
        "exponent_of": (
            "this family as parameterized (depth-6 scrambler, t = A + 4), whose "
            "generator density drifts as about n**-0.24 rather than staying "
            "constant; a confirmed exponent is b + c*delta, not the degree at "
            "fixed density. See docs/notes/GF2_SCALING_RESULT.md."
        ),
        "finite_size_bias": bias,
        "tolerance": tolerance,
    }
    for name, target in STRUCTURAL_PREDICTION.items():
        entry = summary[name]
        observed = float(entry["log_log_exponent_upper_half"])
        trend = observed - float(entry["log_log_exponent_lower_window"])
        excess = observed - target
        if excess > 2 * tolerance or trend >= 0.1:
            verdict = "rejected"
        elif excess <= tolerance and trend < 0:
            verdict = "confirmed"
        else:
            verdict = "undecided"
        verdicts[name] = {
            "target": target,
            "observed_upper_half": observed,
            "excess": excess,
            "trend": trend,
            "verdict": verdict,
        }
    return verdicts


def _coerce(value: str):
    for cast in (int, float):
        try:
            return cast(value)
        except ValueError:
            continue
    return value


def rejected_method_control(rows: list[dict[str, object]]) -> dict[str, object]:
    """Emit the numbers that justify rejecting the bias-corrected extrapolation.

    Fitting ``e(n) = d + K/n`` to the sequence of local exponents would read the
    asymptotic degree directly. Run against the calibrator, whose degree is
    exactly 2, it returns a confidently wrong answer. Those numbers are quoted
    when the rejection is reported, so they are emitted here rather than
    recomputed by hand: a figure that appears in a write-up should be
    recomputable from a published artifact.
    """
    widths = np.asarray([row["accessible_width"] for row in rows], dtype=float)
    values = np.asarray([row[CALIBRATOR_FOR_CONTROL] for row in rows], dtype=float)
    secant = np.log(values[1:] / values[:-1]) / np.log(widths[1:] / widths[:-1])
    midpoints = (widths[1:] + widths[:-1]) / 2
    design = np.vstack([np.ones_like(midpoints), 1 / midpoints]).T
    degree, coefficient = np.linalg.lstsq(design, secant, rcond=None)[0]
    jackknife = [
        float(np.linalg.lstsq(np.delete(design, index, 0), np.delete(secant, index), rcond=None)[0][0])
        for index in range(len(secant))
    ]
    return {
        "method": "e(n) = d + K/n fitted to local exponents",
        "fitted_on": CALIBRATOR_FOR_CONTROL,
        "true_degree": 2,
        "estimated_degree": float(degree),
        "jackknife_spread": [min(jackknife), max(jackknife)],
        "excludes_truth": not (min(jackknife) <= 2 <= max(jackknife)),
        "verdict": (
            "rejected: a jackknife measures the stability of a fit, not its "
            "accuracy, and tightens around the wrong value when the residuals "
            "are systematic -- here the 1/n form is only the leading correction"
        ),
    }


def _rows_from_csv(paths: list[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in paths:
        with Path(path).open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                rows.append(
                    {
                        key: _coerce(value)
                        for key, value in row.items()
                    }
                )
    return sorted(rows, key=lambda row: row["accessible_width"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-message", type=int, default=1)
    parser.add_argument("--max-message", type=int, default=12)
    parser.add_argument("--output", default="results/gf2_scaling.csv")
    parser.add_argument("--scramble-depth", type=int, default=SCRAMBLE_DEPTH)
    parser.add_argument(
        "--analyse",
        nargs="+",
        help="score existing sweeps instead of measuring; pass one or more CSV paths",
    )
    arguments = parser.parse_args()

    output = Path(arguments.output)
    rows = (
        _rows_from_csv(arguments.analyse)
        if arguments.analyse
        else measure(
            range(arguments.min_message, arguments.max_message + 1),
            arguments.scramble_depth,
        )
    )
    if not rows:
        raise SystemExit(
            "no instance survived: at this scrambler depth every layout was "
            "discarded as disconnected; raise --scramble-depth"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = analyse(rows)
    result = {
        "format_version": "orelia.gf2-scaling/v1",
        "architecture": ARCHITECTURE,
        "seed": SEED,
        "scramble_depth": arguments.scramble_depth,
        "policy": VerificationPolicy.CHANNEL_CERTIFIED.value,
        "instances": len(rows),
        "accessible_width_range": [rows[0]["accessible_width"], rows[-1]["accessible_width"]],
        "counters": summary,
        "prediction_verdict": evaluate_prediction(summary),
        "rejected_method_control": rejected_method_control(rows),
    }
    Path(str(output).replace(".csv", ".json")).write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
