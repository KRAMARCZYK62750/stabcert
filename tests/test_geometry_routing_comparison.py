import csv
from pathlib import Path


def test_geometry_comparison_uses_same_router_for_primary_four_graphs():
    path = Path("results/geometry_routing_comparison.csv")
    assert path.exists()
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 20
    for message_qubits in (9, 10, 11, 12):
        selected = [row for row in rows if int(row["A"]) == message_qubits]
        assert {row["architecture"] for row in selected} == {
            "chain_historical",
            "chain",
            "ring",
            "grid_2d",
            "all_to_all",
        }
        primary = [row for row in selected if row["architecture"] != "chain_historical"]
        assert {
            row["routing_policy"] for row in primary
        } == {"common_shortest_path_inverse_replay"}
        assert all(row["validated"] == "True" for row in selected)
        assert all(row["signed_clifford_equivalent"] == "True" for row in selected)
        assert all(row["final_order_restored"] == "True" for row in selected)
        by_name = {row["architecture"]: row for row in selected}
        assert int(by_name["all_to_all"]["swap"]) == 0
        assert int(by_name["all_to_all"]["routed_depth"]) == int(
            by_name["all_to_all"]["logical_depth"]
        )
        assert int(by_name["grid_2d"]["routed_depth"]) < int(
            by_name["chain"]["routed_depth"]
        )
        assert int(by_name["ring"]["routed_depth"]) < int(
            by_name["chain"]["routed_depth"]
        )


def test_a12_geometry_depths_are_reproducible():
    path = Path("results/geometry_routing_comparison.csv")
    with path.open(newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if int(row["A"]) == 12]
    depths = {row["architecture"]: int(row["routed_depth"]) for row in rows}
    assert depths == {
        "chain_historical": 1209,
        "chain": 2169,
        "ring": 1886,
        "grid_2d": 1192,
        "all_to_all": 154,
    }
