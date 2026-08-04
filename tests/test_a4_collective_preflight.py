from a4_collective_preflight import (
    MAX_RSS_MIB,
    MAX_SECONDS,
    TOLERANCE,
    run_preflight,
)


def test_a4_collective_preflight_validates_full_channel():
    timeline, state_rows, resources, metadata = run_preflight()
    assert metadata["status"] == "validated"
    assert metadata["message_qubits"] == 4
    assert metadata["alphabet_size"] == 16
    assert metadata["selected_t"] == 5
    assert metadata["scrambler_connected"] is True
    assert metadata["choi_petz_is_stabilizer"] is True
    assert metadata["dense_choi_matrices_avoided"] is True
    assert metadata["final_order_restored"] is True
    assert metadata["support_rank"] == 128
    assert metadata["full_operator_checks"] == 16_384
    assert abs(timeline[0]["petz_entanglement_fidelity"] - 1 / 256) < TOLERANCE
    assert timeline[5]["mutual_information_R_C_bits"] == 0
    assert timeline[5]["trace_distance_rhoRC_product"] == 0
    for row in resources:
        assert row["entanglement_fidelity"] > 1 - TOLERANCE
        assert row["choi_fidelity"] > 1 - TOLERANCE
        assert row["operator_error"] < TOLERANCE
    for row in state_rows:
        assert row["state_fidelity"] > 1 - TOLERANCE
        if row["primary_binary_symbol"]:
            assert row["basis_symbol_correct"] is True


def test_a4_resources_and_budget_are_explicit():
    _, _, resources, metadata = run_preflight()
    direct = next(row for row in resources if row["method"] == "Clifford direct")
    routed = next(row for row in resources if row["method"] == "Clifford route chaine")
    assert direct["two_qubit_depth"] == 57
    assert direct["cnot"] == 62
    assert routed["two_qubit_depth"] == 213
    assert routed["cnot"] == 338
    assert routed["swap"] == 92
    # ru_maxrss is process-wide under pytest, so allow its explicit budget plus
    # test-runner overhead; the standalone CSV contains the isolated peak.
    assert metadata["peak_rss_mib"] < MAX_RSS_MIB + 256
    assert metadata["total_seconds"] < MAX_SECONDS
