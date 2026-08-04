import csv
from pathlib import Path


def test_statefree_validation_regression_a1_through_a6_passes():
    path = Path("results/stabilizer_validation_regression.csv")
    assert path.exists()
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [int(row["A"]) for row in rows] == [1, 2, 3, 4, 5, 6]
    for row in rows:
        assert row["regression_pass"] == "True"
        assert row["verdicts_equal"] == "True"
        assert float(row["maximum_fidelity_difference"]) < 1e-12
        assert row["reduced_choi_equal_structural"] == "True"
        assert row["signed_phases_validated"] == "True"
        assert int(row["dense_state_amplitudes_new"]) == 0
        assert int(row["dense_reduced_entries_new"]) == 0
