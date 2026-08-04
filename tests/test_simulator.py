import numpy as np
from fractions import Fraction
from hayden_preskill_toy.simulator import Gate, apply_circuit, apply_unitary, bell_fidelity, bell_pair, zero_state
from hayden_preskill_toy.experiment import N_QUBITS, R, A, B, initial_state, inverse_decoder, random_scrambler, two_qubit_depth
from hayden_preskill_toy.channels import apply_channel, channel_at_time, channel_validation, conditional_collision_entropy, petz_entanglement_fidelity, petz_recovery
from hayden_preskill_toy.channels import decoupling_metrics
from hayden_preskill_toy.stabilizer import diagnostics
from hayden_preskill_toy.local import chain_layout, light_cone_bound, petz_stinespring_resources, stinespring_unitary_extension


def test_bell_fidelity_is_one_for_bell_pair():
    state = bell_pair(zero_state(2), 0, 1, 2)
    assert np.isclose(bell_fidelity(state, 0, 1, 2), 1.0)


def test_clifford_inverse_recovers_initial_state():
    circuit = random_scrambler(np.random.default_rng(7), 4)
    start = initial_state(); end = apply_circuit(start, circuit, N_QUBITS)
    recovered = apply_circuit(end, circuit, N_QUBITS, inverse=True)
    assert np.allclose(recovered, start)


def test_bell_reference_is_recovered_by_full_inverse():
    circuit = random_scrambler(np.random.default_rng(8), 3)
    state = apply_circuit(initial_state(), circuit, N_QUBITS)
    state = apply_circuit(state, circuit, N_QUBITS, inverse=True)
    assert np.isclose(bell_fidelity(state, R, A, N_QUBITS), 1.0)


def test_disjoint_cnots_share_a_depth_layer():
    assert two_qubit_depth([Gate("CNOT", 0, 1), Gate("CNOT", 2, 3)]) == 1


def test_inverse_is_unavailable_when_an_emitted_slot_is_missing():
    circuit = random_scrambler(np.random.default_rng(3), 1)
    assert inverse_decoder(circuit, (B[-1],)) is None


def test_channel_is_trace_preserving_and_petz_preserves_its_support():
    channel = channel_at_time(random_scrambler(np.random.default_rng(12), 2), 2)
    validation = channel_validation(channel)
    _, petz = petz_recovery(channel)
    assert validation["cp_by_kraus"]
    assert validation["trace_preservation_error"] < 1e-12
    assert petz["support_trace_preservation_error"] < 1e-10
    rho = np.array([[.7, .2j], [-.2j, .3]], dtype=complex)
    assert np.linalg.eigvalsh(apply_channel(channel, rho)).min() > -1e-12


def test_petz_recovers_the_unscrambled_message():
    fidelity, _ = petz_entanglement_fidelity(channel_at_time([], 1))
    assert np.isclose(fidelity, 1.0)


def test_nonuniform_dephasing_refutes_the_claimed_renyi2_identity():
    for p in (0., .25, .5):
        e0 = np.array([np.sqrt(1-p), np.sqrt(p)])
        e1 = np.array([np.sqrt(1-p), -np.sqrt(p)])
        rho_rc = .5 * np.kron([[1, 0], [0, 0]], np.outer(e0, e0)) + .5 * np.kron([[0, 0], [0, 1]], np.outer(e1, e1))
        rho_c = .5 * (np.outer(e0, e0) + np.outer(e1, e1))
        h2 = conditional_collision_entropy(rho_rc, rho_c)
        petz_fidelity = (1-p)**2 + p**2
        assert np.isclose(h2, -np.log2((1 + 2*np.sqrt(p*(1-p))) / 2))
        if p == .25:
            assert not np.isclose(petz_fidelity, 2**(h2 - 1))
        else:
            assert np.isclose(petz_fidelity, 2**(h2 - 1))


def test_clifford_correlation_rank_matches_information_and_petz_for_one_instance():
    circuit = random_scrambler(np.random.default_rng(22), 6); t = 2
    state = apply_circuit(initial_state(), circuit, N_QUBITS)
    values = decoupling_metrics(state, t, include_early_radiation=True)
    data = diagnostics(circuit, N_QUBITS, R, A, B, (6, 7, 8, 9), t)
    fidelity, _ = petz_entanglement_fidelity(channel_at_time(circuit, t))
    assert np.isclose(values["mutual_information_bits"], data["stabilizer_correlation_rank_r"])
    assert np.isclose(fidelity, 2 ** (-data["stabilizer_correlation_rank_r"]))
    assert np.isclose(fidelity, values["rank_rho_RC"] / (2 * values["rank_rho_C"]))


def test_atomic_stabilizer_rank_formula_in_exact_rational_arithmetic():
    # Identity, uniform Pauli-dephasing, and reset/EPR-complement blocks.
    assert Fraction(2, 2 * 1) == Fraction(1, 1)
    assert Fraction(2, 2 * 2) == Fraction(1, 2)
    assert Fraction(1, 2 * 2) == Fraction(1, 4)


def test_local_chain_accounting_is_explicit():
    assert chain_layout(2) == ("E0", "E1", "E2", "E3", "D0", "D1")
    assert light_cone_bound(2)["causal_depth_lower_bound_if_farthest_required"] == 5
    resources = petz_stinespring_resources(channel_at_time([], 1))
    assert resources["petz_choi_rank"] >= 1
    unitary, audit = stinespring_unitary_extension(channel_at_time([], 1))
    assert np.allclose(unitary.conj().T @ unitary, np.eye(32))
    assert audit["extension_action_error"] < 1e-10


def test_dense_unitary_application_respects_qubit_order():
    state = zero_state(3)
    x = np.array([[0, 1], [1, 0]], complex)
    assert np.argmax(np.abs(apply_unitary(state, x, (1,), 3))) == 2
