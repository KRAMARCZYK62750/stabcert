"""Binary-symplectic diagnostics for pure Clifford/stabilizer channels."""
from __future__ import annotations
import numpy as np
from .simulator import Gate


def _register(value: int | tuple[int, ...]) -> tuple[int, ...]:
    return (value,) if isinstance(value, int) else tuple(value)


def propagated_generators(circuit: list[Gate], n: int, r: int | tuple[int, ...], a: int | tuple[int, ...], b: tuple[int, ...], e: tuple[int, ...]) -> list[tuple[np.ndarray, np.ndarray]]:
    """Propagate generators of Bell(R,A) and Bell(B,E); phases do not affect ranks."""
    gens: list[tuple[np.ndarray, np.ndarray]] = []
    r_register, a_register = _register(r), _register(a)
    if len(r_register) != len(a_register): raise ValueError('R/A register-size mismatch')
    for p, q in (*zip(r_register, a_register), *zip(b, e)):
        x = np.zeros(n, dtype=np.uint8); x[p] = x[q] = 1; gens.append((x, np.zeros(n, dtype=np.uint8)))
        z = np.zeros(n, dtype=np.uint8); z[p] = z[q] = 1; gens.append((np.zeros(n, dtype=np.uint8), z))
    for gate in circuit:
        for x, z in gens:
            if gate.name == "H": x[gate.a], z[gate.a] = z[gate.a], x[gate.a]
            elif gate.name == "S": z[gate.a] ^= x[gate.a]
            elif gate.name == "CNOT":
                assert gate.b is not None
                x[gate.b] ^= x[gate.a]; z[gate.a] ^= z[gate.b]
            else: raise ValueError(f"non-Clifford gate in tableau: {gate.name}")
    return gens


def _rank_gf2(rows: list[np.ndarray]) -> int:
    if not rows: return 0
    matrix = np.asarray(rows, dtype=np.uint8).copy(); rank = 0
    for col in range(matrix.shape[1]):
        pivots = np.flatnonzero(matrix[rank:, col])
        if not len(pivots): continue
        pivot = rank + pivots[0]; matrix[[rank, pivot]] = matrix[[pivot, rank]]
        for row in range(matrix.shape[0]):
            if row != rank and matrix[row, col]: matrix[row] ^= matrix[rank]
        rank += 1
        if rank == matrix.shape[0]: break
    return rank


def independent_basis(rows: list[np.ndarray]) -> list[np.ndarray]:
    basis: list[np.ndarray] = []
    for row in rows:
        if _rank_gf2(basis + [row]) > len(basis): basis.append(row.copy())
    return basis


def pauli_label(vector: np.ndarray, qubits: tuple[int, ...], n: int) -> str:
    chars=[]
    for q in qubits:
        chars.append("IXZY"[int(vector[q]) + 2 * int(vector[n+q])])
    return "".join(chars)


def subgroup_vectors(gens: list[tuple[np.ndarray, np.ndarray]], support: tuple[int, ...], n: int) -> list[np.ndarray]:
    """All independent stabilizers having identity outside support (n=10 permits enumeration)."""
    outside = [q for q in range(n) if q not in support]; found = []
    for mask in range(1, 1 << len(gens)):
        x = np.zeros(n, dtype=np.uint8); z = np.zeros(n, dtype=np.uint8)
        for i, (gx, gz) in enumerate(gens):
            if mask >> i & 1: x ^= gx; z ^= gz
        if not (x[outside].any() or z[outside].any()): found.append(np.concatenate((x, z)))
    return found


def supported_stabilizer_dimension(
    gens: list[tuple[np.ndarray, np.ndarray]], support: tuple[int, ...], n: int
) -> int:
    """Dimension of stabilizers supported in X, via a GF(2) kernel.

    A product of the independent pure-state generators is supported in X iff
    its binary restriction to the complement of X vanishes. The desired
    dimension is therefore nullity of that restriction map; no stabilizer
    group enumeration is needed.
    """
    outside = tuple(q for q in range(n) if q not in support)
    if not outside:
        return len(gens)
    restricted = [
        np.concatenate((x[list(outside)], z[list(outside)])) for x, z in gens
    ]
    return len(gens) - _rank_gf2(restricted)


def pure_stabilizer_decoupling(
    circuit: list[Gate],
    n: int,
    r: int | tuple[int, ...],
    a: int | tuple[int, ...],
    b: tuple[int, ...],
    e: tuple[int, ...],
    t: int,
) -> dict[str, float | int]:
    """Exact I(R:C) and trace distance for the pure stabilizer construction."""
    r_register, a_register = _register(r), _register(a)
    generators = propagated_generators(circuit, n, r_register, a_register, b, e)
    c_register = (*a_register, *b)[t:]
    rc_register = (*r_register, *c_register)
    dim_s_r = supported_stabilizer_dimension(generators, r_register, n)
    dim_s_c = supported_stabilizer_dimension(generators, c_register, n)
    dim_s_rc = supported_stabilizer_dimension(generators, rc_register, n)
    entropy_r = len(r_register) - dim_s_r
    entropy_c = len(c_register) - dim_s_c
    entropy_rc = len(rc_register) - dim_s_rc
    mutual_information = entropy_r + entropy_c - entropy_rc
    # The flat stabilizer support for rho_RC is contained in the support of
    # rho_R tensor rho_C because S_R x S_C is a subgroup of S_RC. Therefore
    # the trace distance of the normalized nested projectors is 1-2**(-I).
    trace_distance = 0.0 if mutual_information == 0 else 1 - 2.0 ** (-mutual_information)
    return {
        'mutual_information_bits': int(mutual_information),
        'trace_distance_product': float(trace_distance),
        'stabilizer_dim_R': dim_s_r,
        'stabilizer_dim_C': dim_s_c,
        'stabilizer_dim_RC': dim_s_rc,
    }


def diagnostics(circuit: list[Gate], n: int, r: int | tuple[int, ...], a: int | tuple[int, ...], b: tuple[int, ...], e: tuple[int, ...], t: int) -> dict[str, int]:
    r_register, a_register = _register(r), _register(a)
    gens = propagated_generators(circuit, n, r, a, b, e)
    c = (*a_register, *b)[t:]; rc = (*r_register, *c)
    s_rc = subgroup_vectors(gens, rc, n); s_c = subgroup_vectors(gens, c, n); s_r = subgroup_vectors(gens, r_register, n)
    d_rc, d_c, d_r = _rank_gf2(s_rc), _rank_gf2(s_c), _rank_gf2(s_r)
    # Rank of restrictions to R of joint RC stabilizers is the number of logical Pauli constraints visible in C.
    restricted_r = [np.concatenate((v[list(r_register)], v[[n + q for q in r_register]])) for v in s_rc]
    logical_c = _rank_gf2(restricted_r)
    return {"stabilizer_dim_RC": d_rc, "stabilizer_dim_C": d_c, "stabilizer_dim_R": d_r,
            "stabilizer_correlation_rank_r": d_rc - d_c - d_r,
            "accessible_message_pauli_rank_in_C": logical_c}
