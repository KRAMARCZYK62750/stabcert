from generate_parametric_routing_regression import (
    TOLERANCE,
    assert_parametric_routing_is_independent,
    build_rows,
)


def test_all_60_b4_routing_regressions_pass():
    assert_parametric_routing_is_independent()
    rows = build_rows()
    assert len(rows) == 60
    for row in rows:
        assert row['local_depth_old'] == row['local_depth_new']
        assert row['routed_cnot_old'] == row['routed_cnot_new']
        assert row['swap_old'] == row['swap_new']
        assert row['final_order_old'] == row['final_order_new']
        assert abs(row['routed_fidelity_old'] - row['routed_fidelity_new']) < TOLERANCE
        assert abs(row['operator_error_old'] - row['operator_error_new']) < TOLERANCE
        assert row['operator_error_new'] < TOLERANCE
        assert row['regression_pass']
