#!/usr/bin/env python3
"""Review pass 2: recompute every reported figure from its artifact.

Direction matters. Each figure is recomputed from the published artifact and
then looked for in the paper. The paper is never the source, and no figure is
checked against another passage of the paper, a note, or an earlier message --
that would produce a guaranteed and empty confirmation.

Derived quantities are recomputed from their formula rather than read from a
file, since publishing an arithmetic table as a dataset would be traceability
theatre. They are marked ``derived`` below.

Searches run on the flattened paper: markdown wraps sentences, and a
line-oriented search reports a present figure as absent.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import statistics

import numpy as np

ROOT = Path(__file__).resolve().parent
PAPER = ROOT / "docs" / "paper" / "stabcert.md"


def flatten(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def rows(name: str) -> list[dict[str, str]]:
    with (ROOT / "results" / name).open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load(name: str) -> dict:
    return json.loads((ROOT / "results" / name).read_text(encoding="utf-8"))


def scaling_rows() -> dict[int, dict[str, str]]:
    table: dict[int, dict[str, str]] = {}
    for name in ("gf2_scaling.csv", "gf2_scaling_n21_n30.csv", "gf2_scaling_n31_n40.csv"):
        for row in rows(name):
            table[int(row["accessible_width"])] = row
    return table


def expected() -> list[tuple[str, str, str]]:
    """(label, source, string the paper must contain)."""
    out: list[tuple[str, str, str]] = []

    # ---- 6.2 campaigns -------------------------------------------------
    def campaign(name: str) -> tuple[int, int, int, int]:
        table = rows(name)
        invalid = sum(1 for r in table if r["expected_valid"] == "False")
        false_accept = sum(1 for r in table if r["false_accept"] == "True")
        false_reject = sum(1 for r in table if r["false_reject"] == "True")
        return invalid, len(table) - invalid, false_accept, false_reject

    def thousands(value: int) -> str:
        return f"{value:,}".replace(",", " ")

    for name, label in (("verifier_adversarial_validation.csv", "verifier"),
                        ("channel_certified_adversarial.csv", "channel")):
        invalid, valid, false_accept, false_reject = campaign(name)
        out.append((f"6.2 {label} campaign", name,
                    f"| {thousands(invalid)} | {thousands(valid)} | {false_accept} | {false_reject} |"))
    channel = rows("channel_certified_adversarial.csv")
    family = [r for r in channel if r["category"] == "outside_support_only"]
    accepted = sum(1 for r in family if r["observed_valid"] == "True")
    out.append(("6.2 outside_support_only", "channel_certified_adversarial.csv",
                f"**All {accepted} are accepted.**"))

    # ---- 6.3 resources -------------------------------------------------
    manifest = {str(m["message_qubits"]): m for m in
                json.loads((ROOT / "tests" / "fixtures" / "recovery_v1" / "manifest.json").read_text())}
    sabre = {r["message_qubits"]: r for r in rows("sabre_regression_a1_a12.csv")}
    pytket = {r["message_qubits"]: r for r in rows("pytket_regression_a1_a12.csv")}
    for message in ("1", "8", "12"):
        s, p = sabre[message], pytket[message]
        cells = (f"| {message} | {manifest[message]['architecture']} | "
                 f"{s['logical_depth']} / {s['logical_cnot']} | "
                 f"{s['orelia_routed_depth']} / {s['orelia_routed_cnot']} | "
                 f"{s['sabre_routed_depth']} / {s['sabre_routed_cnot']} | "
                 f"{p['pytket_routed_depth']} / {p['pytket_routed_cnot']} |")
        out.append((f"6.3 resources A={message}", "sabre/pytket regression csv", cells))
        ld, lc = float(s["logical_depth"]), float(s["logical_cnot"])
        ratio = (f"| {message} | {manifest[message]['architecture']} | "
                 f"{float(s['orelia_routed_depth'])/ld:.2f} / {float(s['orelia_routed_cnot'])/lc:.2f} | "
                 f"{float(s['sabre_routed_depth'])/ld:.2f} / {float(s['sabre_routed_cnot'])/lc:.2f} | "
                 f"{float(p['pytket_routed_depth'])/ld:.2f} / {float(p['pytket_routed_cnot'])/lc:.2f} |")
        out.append((f"6.3 overhead A={message}", "derived from the same csv", ratio))
    depth_gap = int(sabre["12"]["orelia_routed_depth"]) - int(pytket["12"]["pytket_routed_depth"])
    cnot_gap = int(pytket["12"]["pytket_routed_cnot"]) - int(sabre["12"]["orelia_routed_cnot"])
    out.append(("6.3 A=12 crossover", "derived from the same csv",
                f"shallower than the reference by {depth_gap} layers while using {cnot_gap} more CNOTs"))

    # ---- 6.4 time ------------------------------------------------------
    for name, label in (("sabre_regression_a1_a12.json", "SABRE"),
                        ("pytket_regression_a1_a12.json", "pytket")):
        meta = load(name)
        out.append((f"6.4 {label} runtime", name,
                    f"{float(meta['elapsed_seconds']):.2f} s, peak RSS {float(meta['peak_rss_mib']):.2f} MiB"))
    elapsed = [float(r["elapsed_seconds"]) for r in channel]
    out.append(("6.4 campaign timing", "channel_certified_adversarial.csv",
                f"median {statistics.median(elapsed)*1000:.1f} ms, mean "
                f"{statistics.mean(elapsed)*1000:.1f} ms, max {max(elapsed)*1000:.1f} ms"))
    scale = scaling_rows()
    out.append(("6.4 verification times", "gf2_scaling csv",
                " / ".join(f"{float(scale[n]['verify_seconds']):.2f} s" for n in (9, 20, 40))))
    factor = float(scale[40]["verify_seconds"]) / float(scale[20]["verify_seconds"])
    out.append(("6.4 cross-check factor", "derived from the same csv", f"**{factor:.1f}**"))

    # ---- 7 cost --------------------------------------------------------
    summary = load("gf2_scaling_n9_n40.json")
    counters = summary["counters"]
    verdict = summary["prediction_verdict"]
    coefficients = counters["affine_systems_solved"]["exact_polynomial_coefficients"]
    a, b, c = (int(round(x)) for x in coefficients)
    out.append(("7.2 exact identity", "gf2_scaling_n9_n40.json",
                f"N_sys(n) = {a}n² − {abs(b)}n + {c}"))
    out.append(("7.2 instance count", "gf2_scaling csv",
                f"Over {len(scale)} instances"))
    out.append(("7.3 bias asymptote", "derived from the identity",
                f"{abs(b)}/{a} = {abs(b)/a:.3f} / n"))
    out.append(("7.3 tolerance", "gf2_scaling_n9_n40.json",
                f"the measured bias being {verdict['tolerance']:.4f}"))
    for key, name in (("affine_systems_solved", "calibrator"), ("row_xors", "row_xors"),
                      ("scalar_bit_xors", "scalar_bit_xors"), ("verify_seconds", "time")):
        entry = counters[key]
        low = entry["log_log_exponent_lower_window"]
        high = entry["log_log_exponent_upper_half"]
        out.append((f"7.4 {name} window", "gf2_scaling_n9_n40.json",
                    f"{low:.3f} | **{high:.3f}** |" if key in ("row_xors", "scalar_bit_xors")
                    else f"{low:.3f} | {high:.3f} |"))
    density = load("density_cost_comparison.json")
    joint = density["joint_regression"]["row_xors"]
    control = density["joint_regression"]["calibrator_control"]
    out.append(("7.6 joint coefficients", "density_cost_comparison.json",
                f"b = {joint['degree_at_fixed_density_b']:.3f}     c = {joint['density_elasticity_c']:.3f}"))
    out.append(("7.6 control elasticity", "density_cost_comparison.json",
                f"it returns `c₀ = {control['density_elasticity_c']:.3f}`"))
    out.append(("7.6 contrast drift", "density_cost_comparison.json",
                f"from {density['density_contrast_first']:.3f} to {density['density_contrast_last']:.3f}, "
                f"an exponent of `n^{{{density['density_contrast_drift_exponent']:.3f}}}`"))
    rejected = summary["rejected_method_control"]
    out.append(("7.7 rejected method", "gf2_scaling_n9_n40.json",
                f"`γ = {rejected['estimated_degree']:.3f}` with a jackknife spread of "
                f"`[{rejected['jackknife_spread'][0]:.3f}, {rejected['jackknife_spread'][1]:.3f}]`"))

    # ---- 4.5 density range and the derived surface-code figure ---------
    values = [float(r["mean_generator_density"])
              for name in ("gf2_scaling_dense_d6.csv", "gf2_scaling_sparse_d3.csv")
              for r in rows(name)]
    out.append(("4.5 measured density range", "gf2_scaling dense/sparse csv",
                f"**{min(values):.3f} to {max(values):.3f}**"))
    distance, generators = 5, 5 * 5 - 1
    mean_weight = 4 - 2 * (2 * (distance - 1)) / generators
    out.append(("4.5 surface-code density", "derived",
                f"`{mean_weight:.2f} / {distance * distance} ≈ {mean_weight/distance**2:.3f}`"))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper", default=str(PAPER))
    arguments = parser.parse_args()
    text = flatten(Path(arguments.paper))
    missing = []
    for label, source, needle in expected():
        if " ".join(needle.split()) not in text:
            missing.append({"figure": label, "artifact": source, "recomputed": needle})
    result = {"checked": len(expected()), "mismatches": missing, "clean": not missing}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
