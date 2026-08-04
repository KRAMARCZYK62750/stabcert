import csv
import inspect
from pathlib import Path

import a7_structural_preflight


def test_a7_single_preflight_is_certified_state_free_and_bounded():
    resource_path = Path("results/a7_structural_preflight_resources.csv")
    timeline_path = Path("results/a7_structural_preflight_timeline.csv")
    assert resource_path.exists() and timeline_path.exists()
    with resource_path.open(newline="") as handle:
        resource = next(csv.DictReader(handle))
    with timeline_path.open(newline="") as handle:
        timeline = list(csv.DictReader(handle))

    assert resource["status"] == "validated"
    assert int(resource["message_qubits"]) == 7
    assert int(resource["alphabet_size"]) == 128
    assert int(resource["selected_t"]) == 8
    assert float(resource["selected_mutual_information_bits"]) == 0
    assert abs(
        float(resource["petz_fidelity_dense_crosscheck"])
        - float(resource["petz_fidelity_from_ranks"])
    ) < 1e-12
    assert abs(
        float(resource["direct_circuit_fidelity_structural"])
        - float(resource["petz_fidelity_from_ranks"])
    ) < 1e-12
    assert abs(
        float(resource["routed_circuit_fidelity_structural"])
        - float(resource["petz_fidelity_from_ranks"])
    ) < 1e-12
    assert resource["reduced_choi_equal"] == "True"
    assert resource["signed_phases_validated"] == "True"
    assert int(resource["dense_validation_state_amplitudes"]) == 0
    assert int(resource["dense_validation_reduced_entries"]) == 0
    assert int(resource["old_group_size_avoided"]) == 4_194_304
    assert int(resource["group_elements_enumerated"]) == 0
    assert int(resource["support_operators_enumerated"]) == 0
    assert float(resource["total_seconds"]) <= float(resource["max_seconds_budget"])
    assert float(resource["peak_rss_mib"]) <= float(resource["max_rss_budget_mib"])
    assert len(timeline) == 12
    assert abs(
        float(timeline[0]["petz_fidelity_from_pure_clifford_ranks"])
        - 1 / 16384
    ) < 1e-12


def test_a7_preflight_does_not_execute_a8():
    source = inspect.getsource(a7_structural_preflight)
    assert "n_message=7" in source
    assert "n_message=8" not in source
    assert "signed_dilation_exhaustive" not in source
