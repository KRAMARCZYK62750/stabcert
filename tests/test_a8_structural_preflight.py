import csv
import inspect
from pathlib import Path

import a8_structural_preflight


def test_a8_single_preflight_is_dense_free_certified_and_bounded():
    resource_path = Path("results/a8_structural_preflight_resources.csv")
    timeline_path = Path("results/a8_structural_preflight_timeline.csv")
    state_path = Path("results/a8_structural_preflight_state_certificates.csv")
    assert resource_path.exists() and timeline_path.exists() and state_path.exists()
    with resource_path.open(newline="") as handle:
        resource = next(csv.DictReader(handle))
    with timeline_path.open(newline="") as handle:
        timeline = list(csv.DictReader(handle))
    with state_path.open(newline="") as handle:
        states = list(csv.DictReader(handle))

    assert resource["status"] == "validated"
    assert int(resource["message_qubits"]) == 8
    assert int(resource["alphabet_size"]) == 256
    assert int(resource["selected_t"]) == 8
    assert float(resource["selected_mutual_information_bits"]) == 0
    assert float(resource["selected_trace_distance"]) == 0
    assert int(resource["support_rank"]) == 4096
    assert int(resource["choi_signed_generator_count"]) == 24
    assert float(resource["petz_fidelity"]) == 1
    assert float(resource["direct_fidelity"]) == 1
    assert float(resource["routed_fidelity"]) == 1
    assert resource["reduced_choi_equal"] == "True"
    assert resource["signed_phases_validated"] == "True"
    assert resource["dense_free_chain"] == "True"
    assert resource["budget_pass"] == "True"
    for key in (
        "dense_channel_constructed",
        "dense_tau_constructed",
        "dense_choi_constructed",
        "dense_state_validation_constructed",
    ):
        assert resource[key] == "False"
    assert int(resource["basis_states_enumerated"]) == 0
    assert int(resource["basis_states_collectively_certified"]) == 256
    assert float(resource["total_seconds"]) <= float(resource["max_seconds_budget"])
    assert float(resource["peak_rss_mib"]) <= float(resource["max_rss_budget_mib"])
    assert len(timeline) == 13
    assert abs(float(timeline[0]["petz_fidelity"]) - 1 / 65536) < 1e-12
    assert len(states) == 4
    assert states[0]["primary_binary_symbol"] == "10101101"
    assert int(states[0]["primary_decimal_value"]) == 173
    assert all(row["preservation_certified"] == "True" for row in states)
    assert all(row["dense_state_constructed"] == "False" for row in states)


def test_a8_preflight_has_no_dense_or_a9_path():
    source = inspect.getsource(a8_structural_preflight)
    forbidden = (
        "n_message=9",
        "channel_at_time_compact",
        "choi_purification",
        "from_state_vector",
        "signed_dilation_exhaustive",
    )
    for token in forbidden:
        assert token not in source
