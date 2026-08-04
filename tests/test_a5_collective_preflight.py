from a5_collective_preflight import (
    MAX_OPERATOR_CHECKS,
    MAX_SIGNED_CHOI_GROUP_SIZE,
    run_preflight,
)


def test_a5_preflight_stops_before_synthesis_at_exact_budget_gate():
    timeline, metadata = run_preflight()
    assert metadata["status"] == "stopped_before_synthesis"
    assert metadata["message_qubits"] == 5
    assert metadata["alphabet_size"] == 32
    assert metadata["selected_t"] == 5
    assert metadata["selected_mutual_information_bits"] == 0
    assert metadata["selected_trace_distance"] == 0
    assert metadata["selected_petz_fidelity"] > 0.99
    assert metadata["choi_petz_is_stabilizer"] is True
    assert metadata["full_operator_checks"] == 262_144
    assert metadata["full_operator_checks"] > MAX_OPERATOR_CHECKS
    assert metadata["signed_choi_group_size"] == 262_144
    assert metadata["signed_choi_group_size"] > MAX_SIGNED_CHOI_GROUP_SIZE
    assert metadata["compilation_attempted"] is False
    assert metadata["operator_validation_attempted"] is False
    assert metadata["state_tests_attempted"] is False
    assert metadata["routing_attempted"] is False
    assert abs(timeline[0]["petz_entanglement_fidelity"] - 1 / 1024) < 1e-12
