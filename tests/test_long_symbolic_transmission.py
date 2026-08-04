from long_symbolic_transmission import (
    ALPHABET,
    MESSAGE,
    SYMBOLS,
    SYMBOL_WIDTH,
    TOLERANCE,
    run_experiment,
)


def test_alphabet_requires_four_independent_uses():
    assert len(ALPHABET) == 11
    assert 2**3 < len(ALPHABET) <= 2**SYMBOL_WIDTH
    assert len(set(SYMBOLS.values())) == len(ALPHABET)


def test_long_symbolic_transmission_is_exact_and_costs_add():
    detail, summary, metadata = run_experiment()
    assert metadata["B"] == 4
    assert metadata["symbol_width"] == 4
    assert len(detail) == 3 * len(MESSAGE)
    for row in detail:
        assert row["correct"]
        assert row["symbol_state_fidelity"] > 1 - TOLERANCE
        assert row["operator_error_character"] < TOLERANCE
    for row in summary:
        assert row["message_decoded"] == MESSAGE
        assert row["correct_characters"] == len(MESSAGE)
        assert row["character_accuracy"] == 1.0
        assert row["elementary_cost_sum_verified"] is True

    direct = next(row for row in summary if row["method"] == "Clifford direct")
    routed = next(row for row in summary if row["method"] == "Clifford route chaine")
    assert direct["total_logical_cnot"] == len(MESSAGE) * 4 * metadata["logical_cnot_per_use"]
    assert routed["total_routed_cnot"] == len(MESSAGE) * 4 * metadata["routed_cnot_per_use"]
    assert routed["total_swap"] == len(MESSAGE) * 4 * metadata["swap_per_use"]
