import csv
import inspect
from pathlib import Path

import a9_a12_structural_preflights


def test_a9_through_a12_sequential_preflights_pass_without_dense_objects():
    path = Path("results/a9_a12_structural_preflights.csv")
    assert path.exists()
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [int(row["message_qubits"]) for row in rows] == [9, 10, 11, 12]
    assert [int(row["alphabet_size"]) for row in rows] == [512, 1024, 2048, 4096]
    assert [int(row["selected_t"]) for row in rows] == [9, 12, 12, 14]
    for row in rows:
        assert row["status"] == "validated"
        assert row["validated"] == "True"
        assert row["budget_pass"] == "True"
        assert row["dense_free_chain"] == "True"
        assert float(row["selected_mutual_information_bits"]) == 0
        assert float(row["selected_trace_distance"]) == 0
        assert float(row["petz_fidelity"]) == 1
        assert float(row["direct_fidelity"]) == 1
        assert float(row["routed_fidelity"]) == 1
        assert row["reduced_choi_equal"] == "True"
        assert row["signed_phases_validated"] == "True"
        assert int(row["basis_states_enumerated"]) == 0
        assert int(row["basis_states_collectively_certified"]) == 1 << int(
            row["message_qubits"]
        )
        for key in (
            "dense_channel_constructed",
            "dense_tau_constructed",
            "dense_choi_constructed",
            "dense_state_validation_constructed",
        ):
            assert row[key] == "False"
        assert float(row["total_seconds"]) <= float(row["max_seconds_budget"])
        assert float(row["peak_rss_mib"]) <= float(row["max_rss_budget_mib"])


def test_a9_a12_script_has_no_dense_or_a13_execution_path():
    source = inspect.getsource(a9_a12_structural_preflights)
    forbidden = (
        "n_message=13",
        "channel_at_time_compact",
        "choi_purification",
        "from_state_vector",
        "signed_dilation_exhaustive",
    )
    for token in forbidden:
        assert token not in source
