from collective_two_qubit_experiment import SELECTED_T, TOLERANCE, run_experiment


def test_collective_two_qubit_pipeline_reproduces_petz():
    timeline, state_rows, resources, metadata = run_experiment()
    assert metadata["message_qubits"] == 2
    assert metadata["scrambler_connected"] is True
    assert metadata["final_order_restored"] is True
    assert abs(timeline[0]["petz_entanglement_fidelity"] - 1 / 16) < TOLERANCE
    assert timeline[SELECTED_T]["mutual_information_R_C_bits"] < TOLERANCE
    assert timeline[SELECTED_T]["trace_distance_rhoRC_product"] < TOLERANCE
    assert timeline[SELECTED_T]["petz_entanglement_fidelity"] > 1 - TOLERANCE
    for row in resources:
        assert row["entanglement_fidelity"] > 1 - TOLERANCE
        assert row["choi_fidelity"] > 1 - TOLERANCE
        assert row["operator_error"] < TOLERANCE
    for row in state_rows:
        assert row["state_fidelity"] > 1 - TOLERANCE
        assert row["operator_error_to_parametric_petz"] < TOLERANCE


def test_collective_two_qubit_resources_are_not_parallel_use_totals():
    _, _, resources, metadata = run_experiment()
    direct = next(row for row in resources if row["method"] == "Clifford direct")
    routed = next(row for row in resources if row["method"] == "Clifford route chaine")
    assert metadata["support_rank"] == 32
    assert metadata["support_logical_qubits"] == 5
    assert direct["two_qubit_depth"] == 31
    assert direct["cnot"] == 40
    assert routed["two_qubit_depth"] == 136
    assert routed["cnot"] == 196
    assert routed["swap"] == 52
