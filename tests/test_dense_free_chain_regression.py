import csv
import inspect
from pathlib import Path

from hayden_preskill_toy import dense_free_pipeline
from hayden_preskill_toy.parametric_petz_stabilizer import StabilizerChannelData


def test_dense_free_chain_regression_a1_through_a7_is_exact():
    path = Path("results/dense_free_chain_regression.csv")
    assert path.exists()
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [int(row["A"]) for row in rows] == list(range(1, 8))
    for row in rows:
        assert row["regression_pass"] == "True"
        assert row["discrete_objects_equal"] == "True"
        assert row["signed_choi_generators_equal"] == "True"
        assert row["signed_tau_support_equal"] == "True"
        assert row["support_rank_equal"] == "True"
        assert row["resources_equal"] == "True"
        assert float(row["maximum_fidelity_difference"]) < 1e-12
        assert row["structural_dense_channel_constructed"] == "False"
        assert row["structural_dense_tau_constructed"] == "False"
        assert row["structural_dense_choi_constructed"] == "False"


def test_production_structural_entry_points_do_not_construct_dense_quantum_objects():
    source = inspect.getsource(dense_free_pipeline.run_structural_instance)
    channel_source = inspect.getsource(StabilizerChannelData)
    forbidden = (
        "channel_at_time_compact",
        "choi_purification",
        "from_state_vector",
        "np.linalg.svd",
        "tau_x(",
        "zero_state",
        "apply_circuit",
    )
    for token in forbidden:
        assert token not in source
        assert token not in channel_source


def test_dense_free_a7_confirmation_uses_no_dense_objects():
    path = Path("results/dense_free_pipeline_a7_resources.csv")
    assert path.exists()
    with path.open(newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["validated"] == "True"
    assert row["budget_pass"] == "True"
    assert int(row["message_qubits"]) == 7
    assert int(row["alphabet_size"]) == 128
    assert row["dense_channel_constructed"] == "False"
    assert row["dense_tau_constructed"] == "False"
    assert row["dense_choi_constructed"] == "False"
    assert row["dense_state_validation_constructed"] == "False"
    assert float(row["peak_rss_mib"]) < 1024
