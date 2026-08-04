#!/usr/bin/env python3
"""Score the sparse/dense paired sweep against its pre-registered reading.

Written before the sparse arm finished, so the decision rule cannot be
adjusted to the numbers.  The protocol is `docs/notes/SPARSE_DENSE_COST_EXPERIMENT.md`.

Reading, as registered there, with ``R(n) = row_xors_dense / row_xors_sparse``
fitted by ``R(n) ~ n**rho`` and ``tau`` derived from the exactly known
calibrator:

- ``abs(rho) <= tau`` -- density does not change the degree *enough to be
  visible on the 1.8x contrast available here*.  Not "does not change it".
  The dense extrapolation stands as a valid upper bound.
- ``rho > tau``       -- density governs the degree; the dense extrapolation
  overestimates asymptotically and the FT projection must be redone.

Pairing is only legitimate while both arms share the same support rank at the
same width.  Where ``logical_qubits`` diverges, the paired reading is dropped
for a regression carrying it as a covariate, as registered -- not forced.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

TOLERANCE_FLOOR = 0.1
CALIBRATOR = "affine_systems_solved"
CALIBRATOR_EXACT_DEGREE = 2


def _rows(paths: list[str]) -> dict[int, dict[str, float]]:
    table: dict[int, dict[str, float]] = {}
    for path in paths:
        with Path(path).open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                parsed: dict[str, float] = {}
                for key, value in row.items():
                    try:
                        parsed[key] = float(value)
                    except ValueError:
                        continue
                table[int(parsed["accessible_width"])] = parsed
    return table


def _exponent(widths: np.ndarray, values: np.ndarray) -> float:
    return float(np.polyfit(np.log(widths), np.log(values), 1)[0])


def compare(dense_paths: list[str], sparse_paths: list[str]) -> dict[str, object]:
    dense, sparse = _rows(dense_paths), _rows(sparse_paths)
    widths = np.array(sorted(set(dense) & set(sparse)), dtype=float)
    if len(widths) < 4:
        raise SystemExit(f"only {len(widths)} matched widths; too few to fit")

    required = ("logical_qubits", "mean_generator_density", "row_xors", CALIBRATOR)
    for label, table in (("dense", dense), ("sparse", sparse)):
        missing = [key for key in required if key not in table[int(widths[0])]]
        if missing:
            raise SystemExit(
                f"{label} arm lacks {missing}; re-measure with the instrumented "
                "script rather than comparing an absent column"
            )
    mismatched = [
        int(n)
        for n in widths
        if dense[int(n)]["logical_qubits"] != sparse[int(n)]["logical_qubits"]
    ]
    same_structure = [
        int(n)
        for n in widths
        if dense[int(n)][CALIBRATOR] == sparse[int(n)][CALIBRATOR]
    ]

    upper = max(2, len(widths) // 2)
    calibrator_values = np.array([dense[int(n)][CALIBRATOR] for n in widths])
    bias = _exponent(widths[-upper:], calibrator_values[-upper:]) - CALIBRATOR_EXACT_DEGREE
    tolerance = max(bias, TOLERANCE_FLOOR)

    ratio = np.array(
        [dense[int(n)]["row_xors"] / sparse[int(n)]["row_xors"] for n in widths]
    )
    rho = _exponent(widths, ratio)

    contrast = np.array(
        [
            dense[int(n)]["mean_generator_density"] / sparse[int(n)]["mean_generator_density"]
            for n in widths
        ]
    )
    contrast_drift = _exponent(widths, contrast)

    if mismatched:
        verdict = "pairing_invalid"
        meaning = (
            "support rank diverges between arms; the paired reading is dropped "
            "as registered, and a covariate regression is required"
        )
    elif abs(contrast_drift) > tolerance:
        verdict = "contrast_not_constant"
        meaning = (
            "the density contrast itself scales with n, so rho conflates a "
            "degree effect with a widening gap; rho is not readable as registered"
        )
    elif abs(rho) <= tolerance:
        verdict = "density_not_visible_on_this_contrast"
        meaning = (
            "density does not change the degree enough to be visible on a 1.8x "
            "contrast; the dense extrapolation stands as an upper bound"
        )
    elif rho > tolerance:
        verdict = "density_governs_degree"
        meaning = (
            "density changes the degree; the dense extrapolation overestimates "
            "asymptotically and the FT projection must be redone"
        )
    else:
        verdict = "inverted_ratio"
        meaning = "the sparse arm costs more than the dense one; investigate before reading"

    return {
        "format_version": "orelia.density-cost-comparison/v1",
        "protocol": "docs/notes/SPARSE_DENSE_COST_EXPERIMENT.md",
        "matched_widths": [int(n) for n in widths],
        "pairing_valid": not mismatched,
        "support_rank_mismatch_at": mismatched,
        "identical_elimination_structure_at": same_structure,
        "density_dense_mean": float(
            np.mean([dense[int(n)].get("mean_generator_density", float("nan")) for n in widths])
        ),
        "density_sparse_mean": float(
            np.mean([sparse[int(n)].get("mean_generator_density", float("nan")) for n in widths])
        ),
        "ratio_first": float(ratio[0]),
        "ratio_last": float(ratio[-1]),
        "rho": rho,
        "density_contrast_first": float(contrast[0]),
        "density_contrast_last": float(contrast[-1]),
        "density_contrast_drift_exponent": contrast_drift,
        "finite_size_bias": bias,
        "tolerance": tolerance,
        "verdict": verdict,
        "meaning": meaning,
        "forbidden_reading": "density does not change the degree",
        "joint_regression": {
            "row_xors": joint_regression(dense, sparse, widths, "row_xors"),
            # Control: truth is 28n^2-232n+598, identical in both arms, so the
            # true density elasticity is exactly zero.  Whatever c this returns
            # is the method's false-positive floor, not an effect.
            "calibrator_control": joint_regression(dense, sparse, widths, CALIBRATOR),
        },
    }


def joint_regression(
    dense: dict[int, dict[str, float]],
    sparse: dict[int, dict[str, float]],
    widths: np.ndarray,
    response: str,
) -> dict[str, float]:
    """Fit log(response) = a + b log(n) + c log(density) over both arms pooled."""
    rows = [(n, arm[int(n)]) for n in widths for arm in (dense, sparse)]
    design = np.array(
        [[1.0, np.log(n), np.log(row["mean_generator_density"])] for n, row in rows]
    )
    observed = np.log([row[response] for _, row in rows])
    (a, b, c), *_ = np.linalg.lstsq(design, observed, rcond=None)
    predicted = design @ np.array([a, b, c])
    per_arm = {}
    for label, arm in (("dense", dense), ("sparse", sparse)):
        densities = np.array([arm[int(n)]["mean_generator_density"] for n in widths])
        values = np.array([arm[int(n)][response] for n in widths])
        delta = _exponent(widths, densities)
        per_arm[label] = {
            "density_drift_delta": delta,
            "observed_exponent": _exponent(widths, values),
            "model_implied_exponent": float(b + c * delta),
        }
    return {
        "degree_at_fixed_density_b": float(b),
        "density_elasticity_c": float(c),
        "max_abs_log_residual": float(np.abs(observed - predicted).max()),
        "per_arm": per_arm,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dense", nargs="+", required=True)
    parser.add_argument("--sparse", nargs="+", required=True)
    parser.add_argument("--output", default="results/density_cost_comparison.json")
    arguments = parser.parse_args()
    result = compare(arguments.dense, arguments.sparse)
    Path(arguments.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
