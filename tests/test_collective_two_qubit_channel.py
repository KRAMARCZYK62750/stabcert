import numpy as np
import pytest

from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_channels import channel_at_time, random_scrambler
from hayden_preskill_toy.parametric_petz import entanglement_fidelity, petz, tau_x


def test_two_qubit_message_channel_and_petz_dimensions():
    layout = SystemLayout(n_message=2, n_black_hole=4)
    assert layout.R_register == (0, 1)
    assert layout.A_register == (2, 3)
    assert layout.B == (4, 5, 6, 7)
    assert layout.E == (8, 9, 10, 11)
    assert layout.n_qubits == 12
    with pytest.raises(ValueError, match="R_register"):
        _ = layout.R
    with pytest.raises(ValueError, match="A_register"):
        _ = layout.A
    circuit = random_scrambler(layout, np.random.default_rng(20260802), 6)
    channel = channel_at_time(layout, circuit, 3)
    assert channel.kraus[0].shape == (128, 4)
    complete = sum(
        (k.conj().T @ k for k in channel.kraus),
        start=np.zeros((4, 4), dtype=complex),
    )
    assert np.linalg.norm(complete - np.eye(4)) < 1e-12
    assert tau_x(channel).shape == (128, 128)
    recovery, info = petz(channel)
    assert recovery[0].shape == (4, 128)
    assert info["support_trace_preservation_error"] < 1e-12
    fidelity, _ = entanglement_fidelity(channel)
    assert 0 <= fidelity <= 1 + 1e-12
