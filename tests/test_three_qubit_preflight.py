from three_qubit_preflight import SELECTED_T, TOLERANCE, run_preflight


def test_a3_preflight_validates_full_collective_channel():
    timeline, state_rows, resources, metadata = run_preflight()
    assert metadata["message_qubits"] == 3
    assert metadata["alphabet_size"] == 8
    assert metadata["scrambler_connected"] is True
    assert metadata["dense_choi_matrix_avoided"] is True
    assert metadata["final_order_restored"] is True
    assert metadata["support_rank"] == 128
    assert metadata["full_operator_checks"] == 16384
    assert abs(timeline[0]["petz_entanglement_fidelity"] - 1 / 64) < TOLERANCE
    assert timeline[SELECTED_T]["mutual_information_R_C_bits"] < TOLERANCE
    assert timeline[SELECTED_T]["trace_distance_rhoRC_product"] < TOLERANCE
    for row in resources:
        assert row["entanglement_fidelity"] > 1 - TOLERANCE
        assert row["choi_fidelity"] > 1 - TOLERANCE
        assert row["operator_error"] < TOLERANCE
    for row in state_rows:
        assert row["state_fidelity"] > 1 - TOLERANCE
        if row["expected_basis_symbol"]:
            assert row["basis_symbol_correct"] is True


def test_a3_preflight_resources_are_explicit():
    _, _, resources, metadata = run_preflight()
    direct = next(row for row in resources if row["method"] == "Clifford direct")
    routed = next(row for row in resources if row["method"] == "Clifford route chaine")
    assert direct["two_qubit_depth"] == 31
    assert direct["cnot"] == 33
    assert routed["two_qubit_depth"] == 147
    assert routed["cnot"] == 195
    assert routed["swap"] == 54
    # Pytest's process-wide ru_maxrss also includes imported test/cache state;
    # the standalone report records the experiment's lower isolated peak.
    assert metadata["peak_rss_mib"] < 1024
