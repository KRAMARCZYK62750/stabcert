from orelia_symbolic_test import run


def test_three_independent_uses_preserve_symbols_and_superpositions():
    rows = run()
    for row in rows:
        assert row['state_fidelity'] > 1 - 1e-10
    for row in rows:
        if row['kind'] == 'basis_symbol': assert row['decoded_symbol'] == row['input']
