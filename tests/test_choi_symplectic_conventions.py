from choi_symplectic_conventions import audit


def test_transpose_choi_convention_recovers_signed_control():
    _, rows = audit()
    by_name = {row["variant"]: row for row in rows}
    assert by_name["transpose"]["signed_single_pauli_match"]
    assert by_name["transpose"]["candidate_entanglement_fidelity"] == 1.0
    assert not by_name["direct"]["signed_single_pauli_match"]
    assert by_name["inverse_symplectic"]["candidate_entanglement_fidelity"] < 0.251
