from validate_petz_dilation_t2 import validate


def test_signed_clifford_dilation_matches_petz_on_the_t2_support():
    result = validate()
    assert result['validated']
    assert result['max_operator_error_complete_basis'] < 1e-10
    assert result['choi_state_fidelity_after_syndrome_trace'] > 1 - 1e-10
    assert abs(result['synthesized_entanglement_fidelity'] - result['abstract_petz_entanglement_fidelity']) < 1e-10
