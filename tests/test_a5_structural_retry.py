import csv
from pathlib import Path


def test_a5_structural_retry_artifact_is_certified_and_within_budget():
    path = Path("results/a5_structural_retry_resources.csv")
    assert path.exists()
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "validated"
    assert row["support_dimensions_match"] == "True"
    assert row["signed_generator_certificate"] == "True"
    assert row["reduced_choi_equal"] == "True"
    assert row["routed_clifford_equal"] == "True"
    assert row["final_order_restored"] == "True"
    assert int(row["group_elements_enumerated"]) == 0
    assert int(row["support_operators_enumerated"]) == 0
    assert abs(float(row["direct_circuit_fidelity"]) - float(row["petz_fidelity"])) < 1e-12
    assert abs(float(row["routed_circuit_fidelity"]) - float(row["petz_fidelity"])) < 1e-12
    assert float(row["total_seconds"]) <= float(row["max_seconds_budget"])
    assert float(row["peak_rss_mib"]) <= float(row["max_rss_budget_mib"])
