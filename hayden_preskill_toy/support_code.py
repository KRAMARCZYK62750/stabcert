"""Extract the stabilizer code defining supp(tau_X), without unitary synthesis."""
from __future__ import annotations
import numpy as np
import stim
from .gf2 import canonical_kernel_image_basis, lexicographic_mapped_outside_span, lexicographic_solution, rank
from .simulator import Gate
from .stabilizer import _rank_gf2, independent_basis, pauli_label, propagated_generators, subgroup_vectors


def _register(value: int | tuple[int, ...]) -> tuple[int, ...]:
    return (value,) if isinstance(value, int) else tuple(value)


def _signed_full_stabilizers(circuit: list[Gate], n: int, r: int | tuple[int, ...], a: int | tuple[int, ...], b: tuple[int, ...], e: tuple[int, ...]) -> list[stim.PauliString]:
    """Signed stabilizers of the prepared pure state, in physical wire order.

    The binary routines below intentionally discard phases for rank arithmetic.
    This companion construction retains them for Choi/Petz convention audits.
    """
    preparation = stim.Circuit()
    r_register, a_register = _register(r), _register(a)
    if len(r_register) != len(a_register): raise ValueError('R/A register-size mismatch')
    for left, right in (*zip(r_register, a_register), *zip(b, e)):
        preparation.append("H", [left]); preparation.append("CX", [left, right])
    for gate in circuit:
        if gate.name == "CNOT": preparation.append("CX", [gate.a, gate.b])
        else: preparation.append(gate.name, [gate.a])
    tableau = stim.Tableau.from_circuit(preparation)
    return [tableau.z_output(q) for q in range(n)]


def _signed_supported_representatives(circuit: list[Gate], n: int, r: int | tuple[int, ...], a: int | tuple[int, ...], b: tuple[int, ...], e: tuple[int, ...], support: tuple[int, ...]) -> dict[tuple[int, ...], stim.PauliString]:
    generators = _signed_full_stabilizers(circuit, n, r, a, b, e)
    outside = set(range(n)) - set(support)
    candidates: dict[tuple[int, ...], stim.PauliString] = {}
    for mask in range(1, 1 << n):
        item = stim.PauliString("+" + "_" * n)
        for i, generator in enumerate(generators):
            if mask & (1 << i): item *= generator
        text = str(item)[1:]
        if any(text[q] != "_" for q in outside): continue
        x, z = item.to_numpy(); vector = np.concatenate((x, z)).astype(np.uint8)
        candidates[tuple(map(int, vector))] = item
    return candidates


def _symplectic(a: np.ndarray, b: np.ndarray) -> int:
    n = len(a) // 2
    return int((np.dot(a[:n], b[n:]) + np.dot(a[n:], b[:n])) & 1)


def _logical_pairs(stabilizers: list[np.ndarray], n: int) -> list[tuple[np.ndarray, np.ndarray]]:
    candidates=[]
    for value in range(1, 1 << (2*n)):
        row=np.array([(value >> bit) & 1 for bit in range(2*n)], dtype=np.uint8)
        if all(_symplectic(row,s)==0 for s in stabilizers): candidates.append(row)
    span=list(stabilizers); pairs=[]
    while len(span) < 2*n - len(stabilizers):
        x=next(v for v in candidates if _rank_gf2(span+[v])>len(span))
        z=next(v for v in candidates if _symplectic(x,v)==1 and _rank_gf2(span+[x,v])>len(span)+1)
        pairs.append((x,z)); span += [x,z]
        # Symplectic Gram--Schmidt: make every future candidate commute with this pair.
        candidates=[v ^ (_symplectic(v,z)*x) ^ (_symplectic(v,x)*z) for v in candidates]
    return pairs


def _destabilizers(stabilizers: list[np.ndarray], logical_pairs: list[tuple[np.ndarray, np.ndarray]], n: int) -> list[np.ndarray]:
    candidates=[np.array([(value>>bit)&1 for bit in range(2*n)],dtype=np.uint8) for value in range(1,1<<(2*n))]
    result=[]
    for i, stabilizer in enumerate(stabilizers):
        for candidate in candidates:
            if _symplectic(candidate,stabilizer)!=1: continue
            if any(_symplectic(candidate,other) for j,other in enumerate(stabilizers) if j!=i): continue
            if any(_symplectic(candidate,p) for pair in logical_pairs for p in pair): continue
            if any(_symplectic(candidate,old) for old in result): continue
            result.append(candidate); break
        else: raise ValueError("no destabilizer found")
    return result


def support_code(circuit: list[Gate], n: int, r: int | tuple[int, ...], a: int | tuple[int, ...], b: tuple[int, ...], e: tuple[int, ...], t: int) -> dict[str, object]:
    a_register = _register(a)
    x = (*e, *((*a_register, *b)[:t])); gens = propagated_generators(circuit, n, r, a, b, e)
    supported = independent_basis(subgroup_vectors(gens, x, n))
    # Restrict full symplectic rows to X, preserving the physical order used in the chain.
    restricted = [np.concatenate(([v[q] for q in x], [v[n+q] for q in x])).astype(np.uint8) for v in supported]
    pairs=_logical_pairs(restricted,len(x))
    destabilizers=_destabilizers(restricted,pairs,len(x))
    def label_local(v):
        return "".join("IXZY"[int(v[i])+2*int(v[len(x)+i])] for i in range(len(x)))
    signed_representatives = _signed_supported_representatives(circuit, n, r, a, b, e, x)
    signed_local = []
    # Align signs with the *same binary generators* used above to construct
    # logical pairs and destabilizers. An independent signed basis is not
    # interchangeable position-by-position with that binary basis.
    for vector in supported:
        item = signed_representatives[tuple(map(int, vector))]
        text = str(item)
        signed_local.append(text[0] + "".join(text[1 + q].replace("_", "I") for q in x))
    return {"physical_qubits": x, "support_dimension": 2 ** (len(x) - len(restricted)),
            "independent_stabilizers": len(restricted), "logical_qubits": len(x) - len(restricted),
            "stabilizer_labels": [pauli_label(v, x, n) for v in supported], "signed_stabilizer_labels": signed_local,
            "symplectic_generators": restricted,
            "logical_X_labels":[label_local(pair[0]) for pair in pairs], "logical_Z_labels":[label_local(pair[1]) for pair in pairs],
            "destabilizer_labels":[label_local(v) for v in destabilizers]}


def _j(vector: np.ndarray) -> np.ndarray:
    width = len(vector) // 2
    return np.concatenate((vector[width:], vector[:width])).astype(np.uint8)


def _logical_pairs_linear(
    stabilizers: list[np.ndarray], n: int
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Mask-order-compatible symplectic Gram--Schmidt using GF(2) solves."""
    width = 2 * n
    constraints = np.asarray([_j(row) for row in stabilizers], dtype=np.uint8)
    if constraints.size == 0:
        constraints = np.zeros((0, width), dtype=np.uint8)
    targets = np.zeros(len(constraints), dtype=np.uint8)
    transformation = np.eye(width, dtype=np.uint8)
    span = [row.copy() for row in stabilizers]
    pairs: list[tuple[np.ndarray, np.ndarray]] = []
    for _ in range(n - len(stabilizers)):
        source_x = lexicographic_mapped_outside_span(
            constraints, targets, width, transformation, span
        )
        logical_x = (transformation @ source_x) & 1
        z_constraint = (transformation.T @ _j(logical_x)) & 1
        z_constraints = np.vstack((constraints, z_constraint))
        z_targets = np.append(targets, np.uint8(1))
        source_z = lexicographic_mapped_outside_span(
            z_constraints,
            z_targets,
            width,
            transformation,
            span + [logical_x],
        )
        logical_z = (transformation @ source_z) & 1
        pairs.append((logical_x, logical_z))
        span.extend((logical_x, logical_z))
        projection = (
            np.eye(width, dtype=np.uint8)
            ^ np.outer(logical_x, _j(logical_z))
            ^ np.outer(logical_z, _j(logical_x))
        )
        transformation = (projection @ transformation) & 1
    return pairs


def _destabilizers_linear(
    stabilizers: list[np.ndarray],
    logical_pairs: list[tuple[np.ndarray, np.ndarray]],
    n: int,
) -> list[np.ndarray]:
    width = 2 * n
    result: list[np.ndarray] = []
    for index in range(len(stabilizers)):
        rows = [_j(row) for row in stabilizers]
        values = [int(position == index) for position in range(len(stabilizers))]
        for pair in logical_pairs:
            for logical in pair:
                rows.append(_j(logical)); values.append(0)
        for previous in result:
            rows.append(_j(previous)); values.append(0)
        result.append(
            lexicographic_solution(
                np.asarray(rows, dtype=np.uint8),
                np.asarray(values, dtype=np.uint8),
                width,
            )
        )
    return result


def _ordered_signed_generators(
    circuit: list[Gate],
    n: int,
    r: int | tuple[int, ...],
    a: int | tuple[int, ...],
    b: tuple[int, ...],
    e: tuple[int, ...],
    binary_generators: list[np.ndarray],
) -> list[stim.PauliString]:
    signed = _signed_full_stabilizers(circuit, n, r, a, b, e)
    by_binary = {}
    for item in signed:
        x, z = item.to_numpy()
        by_binary[tuple(map(int, np.concatenate((x, z))))] = item
    return [by_binary[tuple(map(int, vector))] for vector in binary_generators]


def support_code_structural(
    circuit: list[Gate],
    n: int,
    r: int | tuple[int, ...],
    a: int | tuple[int, ...],
    b: tuple[int, ...],
    e: tuple[int, ...],
    t: int,
) -> dict[str, object]:
    """Support code from kernels and symplectic elimination, without groups."""
    a_register = _register(a)
    physical = (*e, *((*a_register, *b)[:t]))
    propagated = propagated_generators(circuit, n, r, a, b, e)
    full_generators = [np.concatenate((x, z)).astype(np.uint8) for x, z in propagated]
    outside = tuple(q for q in range(n) if q not in physical)
    restricted_outside = np.asarray(
        [
            np.concatenate((vector[list(outside)], vector[[n + q for q in outside]]))
            for vector in full_generators
        ],
        dtype=np.uint8,
    )
    if restricted_outside.size == 0:
        constraints = np.zeros((0, len(full_generators)), dtype=np.uint8)
    else:
        constraints = restricted_outside.T
    selected = canonical_kernel_image_basis(
        constraints, len(full_generators), np.asarray(full_generators, dtype=np.uint8).T
    )
    supported = [image for _, image in selected]
    restricted = [
        np.concatenate(
            ([vector[q] for q in physical], [vector[n + q] for q in physical])
        ).astype(np.uint8)
        for vector in supported
    ]
    pairs = _logical_pairs_linear(restricted, len(physical))
    destabilizers = _destabilizers_linear(restricted, pairs, len(physical))

    signed_generators = _ordered_signed_generators(
        circuit, n, r, a, b, e, full_generators
    )
    signed_local = []
    for coefficients, _ in selected:
        item = stim.PauliString("+" + "_" * n)
        for position, generator in enumerate(signed_generators):
            if coefficients[position]:
                item *= generator
        text = str(item)
        signed_local.append(
            text[0] + "".join(text[1 + q].replace("_", "I") for q in physical)
        )

    def label_local(vector):
        return "".join(
            "IXZY"[int(vector[i]) + 2 * int(vector[len(physical) + i])]
            for i in range(len(physical))
        )

    return {
        "physical_qubits": physical,
        "support_dimension": 2 ** (len(physical) - len(restricted)),
        "independent_stabilizers": len(restricted),
        "logical_qubits": len(physical) - len(restricted),
        "stabilizer_labels": [pauli_label(vector, physical, n) for vector in supported],
        "signed_stabilizer_labels": signed_local,
        "symplectic_generators": restricted,
        "logical_X_labels": [label_local(pair[0]) for pair in pairs],
        "logical_Z_labels": [label_local(pair[1]) for pair in pairs],
        "destabilizer_labels": [label_local(vector) for vector in destabilizers],
        "gf2_kernel_variables": len(full_generators),
        "gf2_kernel_constraints": int(constraints.shape[0]),
        "gf2_kernel_constraint_rank": rank(constraints),
        "gf2_kernel_dimension": len(full_generators) - rank(constraints),
        "gf2_centralizer_dimension": 2 * len(physical) - len(restricted),
        "gf2_logical_quotient_dimension": 2 * (len(physical) - len(restricted)),
        "pauli_candidates_enumerated": 0,
        "stabilizer_group_elements_enumerated": 0,
    }


# Explicit oracle names used only by structural-regression tests.
support_code_exhaustive = support_code
logical_pairs_exhaustive = _logical_pairs
destabilizers_exhaustive = _destabilizers
destabilizers_structural = _destabilizers_linear
