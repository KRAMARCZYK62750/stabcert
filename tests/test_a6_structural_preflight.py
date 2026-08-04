import csv
import inspect
from pathlib import Path

import a6_structural_preflight


def test_a6_structural_preflight_artifacts_are_certified_and_bounded():
    resource_path = Path("results/a6_structural_preflight_resources.csv")
    timeline_path = Path("results/a6_structural_preflight_timeline.csv")
    assert resource_path.exists() and timeline_path.exists()
    with resource_path.open(newline="") as handle:
        resource = next(csv.DictReader(handle))
    with timeline_path.open(newline="") as handle:
        timeline = list(csv.DictReader(handle))

    assert resource["status"] == "validated"
    assert int(resource["message_qubits"]) == 6
    assert int(resource["alphabet_size"]) == 64
    assert int(resource["selected_t"]) == 8
    assert float(resource["selected_mutual_information_bits"]) == 0
    assert resource["reduced_choi_equal"] == "True"
    assert resource["routed_clifford_equal"] == "True"
    assert resource["final_order_restored"] == "True"
    assert int(resource["old_group_size_avoided"]) == 1_048_576
    assert int(resource["group_elements_enumerated"]) == 0
    assert int(resource["support_operators_enumerated"]) == 0
    assert abs(
        float(resource["direct_circuit_fidelity"])
        - float(resource["petz_fidelity"])
    ) < 1e-12
    assert abs(
        float(resource["routed_circuit_fidelity"])
        - float(resource["petz_fidelity"])
    ) < 1e-12
    assert float(resource["total_seconds"]) <= float(resource["max_seconds_budget"])
    assert float(resource["peak_rss_mib"]) <= float(resource["max_rss_budget_mib"])
    assert len(timeline) == 11
    assert abs(float(timeline[0]["petz_entanglement_fidelity"]) - 1 / 4096) < 1e-12


def test_a6_preflight_has_no_a7_execution_or_exhaustive_compiler_path():
    source = inspect.getsource(a6_structural_preflight)
    assert "n_message=6" in source
    assert "n_message=7" not in source
    assert "signed_dilation_exhaustive" not in source
