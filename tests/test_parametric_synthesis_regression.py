from generate_parametric_synthesis_regression import (
    TOLERANCE,
    assert_parametric_path_is_independent,
    build_rows,
)


def test_parametric_synthesis_regression_closes_all_three_cases():
    assert_parametric_path_is_independent()
    rows = build_rows()
    assert len(rows) == 3
    for row in rows:
        assert row['support_dimensions_match']
        assert row['signed_choi_group_equal']
        assert row['signed_choi_group_size_old'] == row['signed_choi_group_size_new'] == 1024
        assert row['logical_depth_old'] == row['logical_depth_new']
        assert row['cnot_old'] == row['cnot_new']
        assert row['environment_qubits_old'] == row['environment_qubits_new']
        assert abs(row['petz_fidelity_old'] - row['petz_fidelity_parametric']) < TOLERANCE
        assert abs(row['circuit_entanglement_fidelity_parametric'] - row['petz_fidelity_parametric']) < TOLERANCE
        assert row['choi_fidelity_parametric'] > 1 - TOLERANCE
        assert row['choi_difference_norm'] < TOLERANCE
        assert row['max_operator_error'] < TOLERANCE
        assert row['regression_pass']
