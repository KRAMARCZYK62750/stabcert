"""Local-chain resource accounting for exact Petz Stinespring dilations."""
from __future__ import annotations
import numpy as np
from .channels import ChannelData, petz_recovery


def chain_layout(t: int) -> tuple[str, ...]:
    return tuple([f"E{i}" for i in range(4)] + [f"D{i}" for i in range(t)])


def petz_choi_rank(channel: ChannelData) -> int:
    kraus, _ = petz_recovery(channel)
    columns = np.stack([k.reshape(-1) for k in kraus], axis=1)
    return int(np.linalg.matrix_rank(columns, tol=1e-10))


def petz_stinespring_resources(channel: ChannelData) -> dict[str, int | bool]:
    """Exact dimension accounting; this does not claim a circuit synthesis."""
    kraus, info = petz_recovery(channel)
    d_x = channel.kraus[0].shape[0]; d_a = channel.kraus[0].shape[1]
    rank = petz_choi_rank(channel)
    dilation_dim = d_a * rank
    ancillas = max(0, int(np.ceil(np.log2(max(1, dilation_dim / d_x)))))
    # Petz is TP only on supp(tau); a full-input unitary requires an explicitly chosen extension.
    return {"input_dimension": d_x, "output_dimension": d_a, "petz_choi_rank": rank,
            "stinespring_environment_dimension": rank, "stinespring_output_dimension": dilation_dim,
            "minimum_ancillas_dimension_only": ancillas,
            "support_isometry_embeddable_in_X": dilation_dim <= d_x,
            "tau_support_dimension": int(info["support_dimension"])}


def stinespring_unitary_extension(channel: ChannelData) -> tuple[np.ndarray, dict[str, float | int]]:
    """Extend Petz exactly on supp(tau) to a unitary on X; arbitrary off support."""
    kraus, info = petz_recovery(channel)
    d_x = channel.kraus[0].shape[0]; d_a = channel.kraus[0].shape[1]; rank = petz_choi_rank(channel)
    # Pick an independent Kraus basis, so the environment uses the Choi rank.
    raw = np.stack([k.reshape(-1) for k in kraus], axis=1)
    _, _, vh = np.linalg.svd(raw, full_matrices=False)
    independent = raw @ vh.conj().T[:, :rank]
    reduced = [independent[:, j].reshape(d_a, d_x) for j in range(rank)]
    # Put logical A' first in the physical tensor order, then the Stinespring label.
    w_small = np.stack(reduced, axis=0).reshape(rank, d_a, d_x).transpose(1, 0, 2).reshape(d_a * rank, d_x)
    if w_small.shape[0] > d_x:
        raise ValueError("requires explicit ancillas; output Stinespring space exceeds X")
    embed = np.zeros((d_x, w_small.shape[0]), complex); embed[:w_small.shape[0], :] = np.eye(w_small.shape[0])
    partial = embed @ w_small
    # Domains/ranges of the partial isometry; SVD gives orthonormal support bases.
    left, singular, right_h = np.linalg.svd(partial, full_matrices=True)
    q = int(np.sum(singular > 1e-10)); q_dom = right_h.conj().T[:, :q]; q_range = left[:, :q]
    # Complete both orthonormal bases. Their pairing defines an arbitrary unitary off supp(tau).
    unitary = left @ right_h
    error = np.linalg.norm(unitary @ q_dom - partial @ q_dom)
    return unitary, {"support_dimension": q, "extension_action_error": float(error),
                     "unitarity_error": float(np.linalg.norm(unitary.conj().T @ unitary - np.eye(d_x))),
                     "petz_choi_rank": rank}


def compile_unitary_on_linear_chain(unitary: np.ndarray):
    """Exact numerical synthesis and routing; intended only for small validated cases."""
    from qiskit import QuantumCircuit, transpile
    from qiskit.quantum_info import Operator
    from qiskit.transpiler import CouplingMap
    n = int(round(np.log2(unitary.shape[0])))
    if unitary.shape != (2**n, 2**n): raise ValueError("unitary dimension is not a qubit power")
    # NumPy uses q0 as the most-significant tensor axis; Qiskit matrices use little-endian q0.
    permutation = np.zeros((2**n, 2**n))
    for index in range(2**n):
        reverse = int(f"{index:0{n}b}"[::-1], 2); permutation[reverse, index] = 1
    qiskit_unitary = permutation @ unitary @ permutation
    circuit = QuantumCircuit(n); circuit.unitary(qiskit_unitary, list(range(n)))
    coupling = CouplingMap.from_line(n, bidirectional=True)
    routed = transpile(circuit, basis_gates=["u", "cx", "swap"], coupling_map=coupling, optimization_level=0,
                       seed_transpiler=7, initial_layout=list(range(n)), layout_method="trivial", routing_method="basic")
    actual = permutation @ Operator(routed).data @ permutation
    final_layout = routed.layout.final_index_layout()
    wire_permutation = np.zeros((2**n, 2**n))
    for index in range(2**n):
        bits = [(index >> (n - 1 - q)) & 1 for q in range(n)]; moved = [0] * n
        for q, bit in enumerate(bits): moved[final_layout[q]] = bit
        target = sum(bit << (n - 1 - q) for q, bit in enumerate(moved)); wire_permutation[target, index] = 1
    # The router tracks a final wire permutation. Undo it logically for operator verification.
    actual = wire_permutation.conj().T @ actual
    phase = np.vdot(unitary.reshape(-1), actual.reshape(-1)); phase /= abs(phase) if abs(phase) else 1
    error = np.linalg.norm(actual - phase * unitary) / np.sqrt(unitary.size)
    counts = routed.count_ops()
    inversions = sum(final_layout[i] > final_layout[j] for i in range(n) for j in range(i + 1, n))
    return routed, {"compiled_unitary_error": float(error), "two_qubit_depth": int(routed.depth(lambda x: x.operation.num_qubits == 2)),
                    "cx_count": int(counts.get("cx", 0)), "swap_count": int(counts.get("swap", 0)),
                    "one_qubit_count": int(sum(v for name, v in counts.items() if name == "u")), "qubits": n,
                    "final_layout": "-".join(map(str, final_layout)), "logical_output_physical_site": int(final_layout[0]),
                    "swap_restoration_lower_bound": int(inversions)}


def light_cone_bound(t: int, output_site: int = 0) -> dict[str, int | str]:
    layout = chain_layout(t)
    farthest = len(layout) - 1
    return {"t": t, "layout": "-".join(layout), "output_site": output_site, "farthest_site": farthest,
            "distance_to_farthest": abs(farthest - output_site),
            "causal_depth_lower_bound_if_farthest_required": abs(farthest - output_site)}
