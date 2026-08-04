import csv
from pathlib import Path


def _read(name):
    with Path("results", name).open(newline="") as handle:
        return list(csv.DictReader(handle))


def test_multiseed_grid_contains_all_unfiltered_exact_routes():
    rows = _read("routing_geometry_multiseed.csv")
    assert len(rows) == 80
    assert {int(row["A"]) for row in rows} == {9, 10, 11, 12}
    assert {int(row["seed"]) for row in rows} == set(range(20260802, 20260807))
    assert {row["architecture"] for row in rows} == {
        "chain",
        "ring",
        "grid_2d",
        "all_to_all",
    }
    assert {int(row["lookahead"]) for row in rows} == {16}
    assert {int(row["candidate_budget"]) for row in rows} == {64}
    assert all(row["validated"] == "True" for row in rows)
    assert all(row["signed_clifford_equivalent"] == "True" for row in rows)
    assert all(row["final_order_restored"] == "True" for row in rows)
    assert max(float(row["fidelity_difference"]) for row in rows) < 1e-12
    # Partial Petz recoveries are retained rather than filtered.
    assert {float(row["petz_fidelity"]) for row in rows} == {0.25, 0.5, 1.0}


def test_grid_advantage_is_paired_and_persistent_on_all_twenty_circuits():
    rows = _read("routing_geometry_paired_reductions.csv")
    grid = [row for row in rows if row["comparison"] == "chain_to_grid_2d"]
    assert len(grid) == 20
    assert all(row["comparison_is_lower"] == "True" for row in grid)
    assert min(float(row["relative_reduction"]) for row in grid) > 0.25
    # The ring is deliberately not overclaimed: it loses on several instances.
    ring = [row for row in rows if row["comparison"] == "chain_to_ring"]
    assert any(row["comparison_is_lower"] == "False" for row in ring)


def test_multiseed_depth_medians_are_reproducible():
    rows = _read("routing_geometry_multiseed_summary.csv")
    medians = {
        (int(row["A"]), row["architecture"]): float(row["depth_median"])
        for row in rows
    }
    assert medians == {
        (9, "chain"): 451.0,
        (9, "ring"): 402.0,
        (9, "grid_2d"): 278.0,
        (9, "all_to_all"): 91.0,
        (10, "chain"): 600.0,
        (10, "ring"): 558.0,
        (10, "grid_2d"): 374.0,
        (10, "all_to_all"): 117.0,
        (11, "chain"): 558.0,
        (11, "ring"): 594.0,
        (11, "grid_2d"): 371.0,
        (11, "all_to_all"): 129.0,
        (12, "chain"): 795.0,
        (12, "ring"): 776.0,
        (12, "grid_2d"): 464.0,
        (12, "all_to_all"): 154.0,
    }


def test_multiseed_plot_and_report_exist():
    assert Path("results/routing_geometry_multiseed_depths.png").stat().st_size > 0
    assert Path("docs/notes/ROUTING_GEOMETRY_MULTISEED.md").stat().st_size > 0

