#!/usr/bin/env python3
"""Measure the cost of one GF(2) elimination against system size.

The composition in Section 7 multiplies a count of eliminations by a cost per
elimination. That second factor had been assumed rather than measured, and the
assumption mixed units: it took n**3, which is the bit count, for the row
count. Three lines of measurement settle it, and 32 points of sweeping had not.
"""
from __future__ import annotations

import csv, json
from pathlib import Path

import numpy as np

from hayden_preskill_toy.gf2 import count_operations, solve_affine

ROOT = Path(__file__).resolve().parent
SIZES = (16, 24, 32, 48, 64, 96, 128)
SEED = 20260804


def main() -> int:
    rng = np.random.default_rng(SEED)
    rows = []
    for size in SIZES:
        matrix = rng.integers(0, 2, size=(size, size), dtype=np.uint8)
        target = rng.integers(0, 2, size=size, dtype=np.uint8)
        with count_operations() as stats:
            solve_affine(matrix, target, size)
        rows.append({"size": size, "row_xors": stats.row_xors,
                     "scalar_bit_xors": stats.scalar_bit_xors, "pivots": stats.pivots})
    widths = np.array(SIZES, dtype=float)
    summary = {"format_version": "orelia.elimination-cost/v1", "seed": SEED,
               "sizes": list(SIZES)}
    for counter in ("row_xors", "scalar_bit_xors"):
        values = np.array([r[counter] for r in rows], dtype=float)
        summary[counter] = {
            "log_log_exponent_all_points": float(np.polyfit(np.log(widths), np.log(values), 1)[0]),
            "log_log_exponent_upper_half": float(np.polyfit(np.log(widths[-4:]), np.log(values[-4:]), 1)[0]),
        }
    out = ROOT / "results" / "elimination_cost.csv"
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    Path(str(out).replace(".csv", ".json")).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
