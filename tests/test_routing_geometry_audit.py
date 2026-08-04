import csv
from pathlib import Path


def _rows():
    with Path("results/routing_geometry_audit.csv").open(newline="") as handle:
        return list(csv.DictReader(handle))


def test_routing_geometry_audit_is_complete_and_exact():
    rows = _rows()
    assert len(rows) == 36
    assert all(row["validated"] == "True" for row in rows)
    assert all(row["signed_clifford_equivalent"] == "True" for row in rows)
    assert all(row["final_order_restored"] == "True" for row in rows)
    assert all(float(row["petz_fidelity"]) == 1.0 for row in rows)
    assert all(float(row["routed_fidelity"]) == 1.0 for row in rows)
    primary = [
        row for row in rows if row["strategy"] == "common_lookahead_token_restore"
    ]
    assert len(primary) == 16
    assert {int(row["lookahead"]) for row in primary} == {16}
    assert {int(row["candidate_budget"]) for row in primary} == {64}
    for row in primary:
        assert int(row["causal_lightcone_depth_bound"]) <= int(row["routed_depth"])
        assert int(row["compiled_qubit_congestion_bound"]) <= int(
            row["routed_depth"]
        )


def test_a12_router_audit_and_geometry_depths_are_reproducible():
    rows = [row for row in _rows() if int(row["A"]) == 12]
    chain = {
        row["strategy"]: row for row in rows if row["architecture"] == "chain"
    }
    assert {
        name: (
            int(row["routed_depth"]),
            int(row["swap_movement"]),
            int(row["swap_restoration"]),
        )
        for name, row in chain.items()
    } == {
        "historical_target_move": (1209, 563, 63),
        "shortest_path_inverse_replay": (2169, 563, 563),
        "common_lookahead_token_restore": (932, 439, 101),
    }
    primary = {
        row["architecture"]: int(row["routed_depth"])
        for row in rows
        if row["strategy"] == "common_lookahead_token_restore"
    }
    assert primary == {
        "chain": 932,
        "ring": 915,
        "grid_2d": 464,
        "all_to_all": 154,
    }
    assert primary["grid_2d"] < primary["chain"]


def test_a12_interaction_audit_covers_all_logical_cnots():
    with Path("results/routing_a12_interactions.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_strategy_architecture = {}
    for row in rows:
        key = row["strategy"], row["architecture"]
        by_strategy_architecture.setdefault(key, []).append(row)
    assert len(by_strategy_architecture[("historical_target_move", "chain")]) == 229
    assert len(by_strategy_architecture[("shortest_path_inverse_replay", "chain")]) == 229
    for architecture in ("chain", "ring", "grid_2d", "all_to_all"):
        selected = by_strategy_architecture[
            ("common_lookahead_token_restore", architecture)
        ]
        assert len(selected) == 229
        assert sum(int(row["movement_swaps"]) for row in selected) == {
            "chain": 439,
            "ring": 410,
            "grid_2d": 148,
            "all_to_all": 0,
        }[architecture]

