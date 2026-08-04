"""Exact channel, decoupling, and Petz-recovery calculations for the toy model."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .simulator import Gate, X, apply_1q, apply_circuit, bell_pair, zero_state
from .experiment import A, B, E, N_QUBITS, R, SCRAMBLED

PINV_RELATIVE_CUTOFF = 1e-12


@dataclass(frozen=True)
class ChannelData:
    kraus: tuple[np.ndarray, ...]
    output: tuple[int, ...]
    complement: tuple[int, ...]


def environment_state() -> np.ndarray:
    """|0>_R |0>_A and the fixed pure B--E environment."""
    state = zero_state(N_QUBITS)
    for b, e in zip(B, E):
        state = bell_pair(state, b, e, N_QUBITS)
    return state


def channel_at_time(scrambler: list[Gate], t: int) -> ChannelData:
    """Kraus representation of N_t: A -> E+D(t), with C(t) traced out."""
    output = (*E, *SCRAMBLED[:t])
    complement = SCRAMBLED[t:]
    states = []
    base = environment_state()
    for bit in range(2):
        source = base if bit == 0 else apply_1q(base, X, A, N_QUBITS)
        states.append(apply_circuit(source, scrambler, N_QUBITS))
    matrices = []
    for state in states:
        tensor = state.reshape((2,) * N_QUBITS)[0]  # R is fixed to |0> for the channel.
        axes = tuple(q - 1 for q in (*output, *complement))
        matrices.append(np.transpose(tensor, axes).reshape(2**len(output), 2**len(complement)))
    kraus = tuple(np.stack([mat[:, c] for mat in matrices], axis=1) for c in range(2**len(complement)))
    return ChannelData(kraus, output, complement)


def reduced_density(state: np.ndarray, keep: tuple[int, ...], n: int = N_QUBITS) -> np.ndarray:
    rest = tuple(q for q in range(n) if q not in keep)
    view = np.transpose(state.reshape((2,) * n), (*keep, *rest)).reshape(2**len(keep), -1)
    return view @ view.conj().T


def entropy(rho: np.ndarray) -> float:
    vals = np.linalg.eigvalsh((rho + rho.conj().T) / 2)
    vals = vals[vals > 1e-14]
    return float(-np.sum(vals * np.log2(vals)))


def trace_distance(rho: np.ndarray, sigma: np.ndarray) -> float:
    vals = np.linalg.eigvalsh((rho - sigma + (rho - sigma).conj().T) / 2)
    return float(.5 * np.sum(np.abs(vals)))


def inverse_fractional_power(rho: np.ndarray, power: float, relative_cutoff: float = PINV_RELATIVE_CUTOFF) -> np.ndarray:
    """Moore--Penrose rho**power on supp(rho); zero on its kernel."""
    vals, vectors = np.linalg.eigh((rho + rho.conj().T) / 2)
    cutoff = relative_cutoff * max(float(vals.max()), 1.0)
    keep = vals > cutoff
    return (vectors[:, keep] * vals[keep] ** power) @ vectors[:, keep].conj().T


def conditional_collision_entropy(rho_rc: np.ndarray, rho_c: np.ndarray, relative_cutoff: float = PINV_RELATIVE_CUTOFF) -> float:
    """Sandwiched conditional collision entropy.

    H_2(R|C)=-log2 Tr[(I_R⊗rho_C^-1/4 rho_RC I_R⊗rho_C^-1/4)^2].
    The inverse is the Moore--Penrose inverse restricted to supp(rho_C).
    """
    dim_c = rho_c.shape[0]; dim_r = rho_rc.shape[0] // dim_c
    factor = np.kron(np.eye(dim_r), inverse_fractional_power(rho_c, -.25, relative_cutoff))
    sandwiched = factor @ rho_rc @ factor
    collision = float(np.real(np.trace(sandwiched @ sandwiched)))
    return float(-np.log2(collision))


def decoupling_metrics(scrambled_state: np.ndarray, t: int, include_early_radiation: bool) -> dict[str, float]:
    """For E+D access use C; for D-only access use E+C as the inaccessible complement."""
    complement = SCRAMBLED[t:]
    inaccessible = complement if include_early_radiation else (*E, *complement)
    rho_rc = reduced_density(scrambled_state, (R, *inaccessible))
    rho_r = reduced_density(scrambled_state, (R,))
    rho_c = reduced_density(scrambled_state, inaccessible) if inaccessible else np.ones((1, 1), complex)
    mutual = entropy(rho_r) + entropy(rho_c) - entropy(rho_rc)
    product = np.kron(rho_r, rho_c)
    h2 = conditional_collision_entropy(rho_rc, rho_c)
    eig_rc = np.linalg.eigvalsh((rho_rc + rho_rc.conj().T) / 2); eig_c = np.linalg.eigvalsh((rho_c + rho_c.conj().T) / 2)
    nonzero_rc = eig_rc[eig_rc > 1e-12]; nonzero_c = eig_c[eig_c > 1e-12]
    return {"mutual_information_bits": max(0.0, mutual), "trace_distance_product": trace_distance(rho_rc, product),
            "conditional_collision_entropy_bits": h2, "rank_rho_RC": int(len(nonzero_rc)), "rank_rho_C": int(len(nonzero_c)),
            "spectrum_rho_RC": ";".join(f"{x:.12g}" for x in nonzero_rc), "spectrum_rho_C": ";".join(f"{x:.12g}" for x in nonzero_c)}


def channel_validation(channel: ChannelData) -> dict[str, float | bool]:
    complete = sum((k.conj().T @ k for k in channel.kraus), start=np.zeros((2, 2), complex))
    # Complete positivity is constructive: rho -> sum_j K_j rho K_j^dagger.
    return {"cp_by_kraus": True, "trace_preservation_error": float(np.linalg.norm(complete - np.eye(2))),
            "minimum_completeness_eigenvalue": float(np.linalg.eigvalsh(complete).min())}


def apply_channel(channel: ChannelData, rho: np.ndarray) -> np.ndarray:
    return sum((k @ rho @ k.conj().T for k in channel.kraus), start=np.zeros((2**len(channel.output),) * 2, complex))


def petz_recovery(channel: ChannelData, relative_cutoff: float = PINV_RELATIVE_CUTOFF) -> tuple[tuple[np.ndarray, ...], dict[str, float]]:
    """Transpose/Petz channel for sigma=I/2, using only the support of N(sigma)."""
    stacked = np.concatenate(channel.kraus, axis=1) / np.sqrt(2)
    u, s, _ = np.linalg.svd(stacked, full_matrices=False)
    cutoff = relative_cutoff * (s[0] if len(s) else 1.0)
    kept = s > cutoff
    support = u[:, kept]
    invsqrt = (support / s[kept]) @ support.conj().T
    recovery = tuple((k.conj().T @ invsqrt) / np.sqrt(2) for k in channel.kraus)
    support_projector = support @ support.conj().T
    recovered_identity = sum((r.conj().T @ r for r in recovery), start=np.zeros_like(support_projector))
    return recovery, {"support_dimension": int(kept.sum()), "support_cutoff": float(cutoff),
                      "output_dimension": int(2**len(channel.output)), "choi_dimension": int(2 * 2**len(channel.output)),
                      "support_trace_preservation_error": float(np.linalg.norm(recovered_identity - support_projector))}


def petz_entanglement_fidelity(channel: ChannelData) -> tuple[float, dict[str, float]]:
    recovery, info = petz_recovery(channel)
    fidelity = 0.0
    # (I_R \otimes R o N)(Phi): each composite Kraus is L_j K_i.
    bell = np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2)
    for k in channel.kraus:
        for r in recovery:
            op = r @ k
            fidelity += abs(np.vdot(bell, np.kron(np.eye(2), op) @ bell)) ** 2
    return float(np.real(fidelity)), info
