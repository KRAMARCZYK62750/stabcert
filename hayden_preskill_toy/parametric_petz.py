"""Layout-independent Petz and signed-Choi helpers."""
from __future__ import annotations
import numpy as np
import stim
from .parametric_channels import ChannelData

PINV_RELATIVE_CUTOFF = 1e-12


def apply_channel(channel: ChannelData, rho: np.ndarray) -> np.ndarray:
    dimension = channel.kraus[0].shape[0]
    return sum((k @ rho @ k.conj().T for k in channel.kraus), start=np.zeros((dimension, dimension), complex))


def tau_x(channel: ChannelData) -> np.ndarray:
    input_dimension = channel.kraus[0].shape[1]
    return apply_channel(channel, np.eye(input_dimension, dtype=complex) / input_dimension)


def support_rank(channel: ChannelData, relative_cutoff: float = 1e-12) -> int:
    """Rank using exactly the singular-value support test used by Petz."""
    input_dimension = channel.kraus[0].shape[1]
    stacked = np.concatenate(channel.kraus, axis=1) / np.sqrt(input_dimension)
    singular_values = np.linalg.svd(stacked, compute_uv=False)
    cutoff = relative_cutoff * (singular_values[0] if len(singular_values) else 1.0)
    return int(np.count_nonzero(singular_values > cutoff))


def petz(channel: ChannelData, relative_cutoff: float = PINV_RELATIVE_CUTOFF):
    input_dimension = channel.kraus[0].shape[1]
    stacked = np.concatenate(channel.kraus, axis=1) / np.sqrt(input_dimension)
    u, singular_values, _ = np.linalg.svd(stacked, full_matrices=False)
    cutoff = relative_cutoff * (singular_values[0] if len(singular_values) else 1.0)
    kept = singular_values > cutoff
    support = u[:, kept]
    # Factor the support pseudo-inverse instead of materializing an
    # output_dimension-square matrix. This is decisive for late-time large-X
    # preflights and is algebraically identical on supp(tau_X).
    weighted_support = support / singular_values[kept]
    recovery = tuple(
        ((k.conj().T @ weighted_support) @ support.conj().T)
        / np.sqrt(input_dimension)
        for k in channel.kraus
    )
    recovery_on_support = [r @ support for r in recovery]
    complete_on_support = sum(
        (block.conj().T @ block for block in recovery_on_support),
        start=np.zeros((int(kept.sum()), int(kept.sum())), dtype=complex),
    )
    return recovery, {
        'support_dimension': int(kept.sum()),
        'support_cutoff': float(cutoff),
        'output_dimension': channel.kraus[0].shape[0],
        'choi_dimension': input_dimension * channel.kraus[0].shape[0],
        'support_trace_preservation_error': float(
            np.linalg.norm(complete_on_support - np.eye(int(kept.sum())))
        ),
    }


def entanglement_fidelity(channel: ChannelData):
    recovery, info = petz(channel)
    input_dimension = channel.kraus[0].shape[1]
    fidelity = sum(abs(np.trace(r @ k)) ** 2 for k in channel.kraus for r in recovery)
    fidelity /= input_dimension**2
    return float(np.real(fidelity)), info


def choi_purification(channel: ChannelData, relative_cutoff: float = 1e-12) -> np.ndarray:
    """Normalized |J_V>, wire order A'|Ref|E_Petz; Ref carries P^T."""
    recovery, _ = petz(channel, relative_cutoff)
    return np.stack(recovery,axis=0).transpose(1,2,0).reshape(-1)/np.sqrt(recovery[0].shape[1])


def choi_tableau(channel: ChannelData, relative_cutoff: float = 1e-12) -> stim.Tableau:
    return stim.Tableau.from_state_vector(choi_purification(channel,relative_cutoff), endian='big')


def signed_stabilizers(tableau: stim.Tableau) -> set[str]:
    generators=[tableau.z_output(i) for i in range(len(tableau))]; values=set()
    for mask in range(1 << len(generators)):
        item=stim.PauliString('+'+'_'*len(generators))
        for i,generator in enumerate(generators):
            if mask>>i & 1: item *= generator
        values.add(str(item))
    return values
