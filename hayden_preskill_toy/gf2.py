"""Small deterministic linear-algebra helpers over GF(2)."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

import numpy as np


@dataclass
class GF2OperationStats:
    """Exact counters for the row reductions performed by this module."""

    affine_systems_solved: int = 0
    rank_reductions: int = 0
    pivots: int = 0
    row_xors: int = 0
    scalar_bit_xors: int = 0


_ACTIVE_STATS: ContextVar[GF2OperationStats | None] = ContextVar(
    "gf2_active_stats", default=None
)


@contextmanager
def count_operations():
    """Count GF(2) eliminations in the current structural calculation."""
    stats = GF2OperationStats()
    token = _ACTIVE_STATS.set(stats)
    try:
        yield stats
    finally:
        _ACTIVE_STATS.reset(token)


def _record(*, affine=0, rank_call=0, pivots=0, row_xors=0, width=0) -> None:
    stats = _ACTIVE_STATS.get()
    if stats is None:
        return
    stats.affine_systems_solved += affine
    stats.rank_reductions += rank_call
    stats.pivots += pivots
    stats.row_xors += row_xors
    stats.scalar_bit_xors += row_xors * width


def rank(matrix) -> int:
    data = np.asarray(matrix, dtype=np.uint8).copy()
    if data.ndim == 1:
        data = data.reshape(1, -1)
    if data.size == 0:
        _record(rank_call=1)
        return 0
    _record(rank_call=1)
    result = 0
    for column in range(data.shape[1]):
        pivots = np.flatnonzero(data[result:, column])
        if not len(pivots):
            continue
        pivot = result + int(pivots[0])
        data[[result, pivot]] = data[[pivot, result]]
        row_xors = 0
        for row in range(data.shape[0]):
            if row != result and data[row, column]:
                data[row] ^= data[result]
                row_xors += 1
        _record(pivots=1, row_xors=row_xors, width=data.shape[1])
        result += 1
        if result == data.shape[0]:
            break
    return result


def solve_affine(matrix, target, n_variables: int | None = None):
    """Return one solution and a nullspace basis, or ``None`` if inconsistent."""
    a = np.asarray(matrix, dtype=np.uint8)
    b = np.asarray(target, dtype=np.uint8).reshape(-1)
    if a.ndim == 1:
        a = a.reshape(1, -1)
    if n_variables is None:
        n_variables = a.shape[1] if a.ndim == 2 else 0
    if a.size == 0:
        a = np.zeros((0, n_variables), dtype=np.uint8)
    if a.shape != (len(b), n_variables):
        raise ValueError("GF(2) affine-system dimensions do not match")
    _record(affine=1)
    augmented = np.concatenate((a.copy(), b[:, None]), axis=1)
    pivot_columns: list[int] = []
    pivot_row = 0
    for column in range(n_variables):
        pivots = np.flatnonzero(augmented[pivot_row:, column])
        if not len(pivots):
            continue
        selected = pivot_row + int(pivots[0])
        augmented[[pivot_row, selected]] = augmented[[selected, pivot_row]]
        row_xors = 0
        for row in range(len(augmented)):
            if row != pivot_row and augmented[row, column]:
                augmented[row] ^= augmented[pivot_row]
                row_xors += 1
        _record(pivots=1, row_xors=row_xors, width=augmented.shape[1])
        pivot_columns.append(column)
        pivot_row += 1
        if pivot_row == len(augmented):
            break
    for row in range(pivot_row, len(augmented)):
        if not augmented[row, :n_variables].any() and augmented[row, n_variables]:
            return None
    particular = np.zeros(n_variables, dtype=np.uint8)
    for row, column in enumerate(pivot_columns):
        particular[column] = augmented[row, n_variables]
    free_columns = [column for column in range(n_variables) if column not in pivot_columns]
    nullspace: list[np.ndarray] = []
    for free in free_columns:
        vector = np.zeros(n_variables, dtype=np.uint8)
        vector[free] = 1
        for row, column in enumerate(pivot_columns):
            vector[column] = augmented[row, free]
        nullspace.append(vector)
    return particular, nullspace


def in_span(vector, basis) -> bool:
    vector = np.asarray(vector, dtype=np.uint8)
    rows = [np.asarray(row, dtype=np.uint8) for row in basis]
    return rank(rows + [vector]) == rank(rows)


def _extend(matrix, target, row, value):
    matrix = np.asarray(matrix, dtype=np.uint8)
    target = np.asarray(target, dtype=np.uint8)
    if matrix.size == 0:
        matrix = np.zeros((0, len(row)), dtype=np.uint8)
    return np.vstack((matrix, np.asarray(row, dtype=np.uint8))), np.append(
        target, np.uint8(value)
    )


def lexicographic_solution(
    matrix,
    target,
    n_variables: int,
    *,
    priority: list[int] | tuple[int, ...] | None = None,
) -> np.ndarray:
    """Minimum solution in integer-mask order, without enumerating solutions."""
    a = np.asarray(matrix, dtype=np.uint8)
    if a.size == 0:
        a = np.zeros((0, n_variables), dtype=np.uint8)
    b = np.asarray(target, dtype=np.uint8)
    if solve_affine(a, b, n_variables) is None:
        raise ValueError("inconsistent GF(2) system")
    order = list(priority) if priority is not None else list(reversed(range(n_variables)))
    for index in order:
        selector = np.zeros(n_variables, dtype=np.uint8)
        selector[index] = 1
        trial_a, trial_b = _extend(a, b, selector, 0)
        if solve_affine(trial_a, trial_b, n_variables) is not None:
            a, b = trial_a, trial_b
        else:
            a, b = _extend(a, b, selector, 1)
    solved = solve_affine(a, b, n_variables)
    if solved is None:
        raise AssertionError("greedy GF(2) minimization lost consistency")
    return solved[0]


def _has_mapped_solution_outside_span(
    matrix, target, n_variables: int, mapping: np.ndarray, span
) -> bool:
    solved = solve_affine(matrix, target, n_variables)
    if solved is None:
        return False
    particular, nullspace = solved
    image = (mapping @ particular) & 1
    if not in_span(image, span):
        return True
    return any(not in_span((mapping @ vector) & 1, span) for vector in nullspace)


def lexicographic_mapped_outside_span(
    matrix,
    target,
    n_variables: int,
    mapping: np.ndarray,
    span,
    *,
    priority: list[int] | tuple[int, ...] | None = None,
) -> np.ndarray:
    """Minimum affine solution whose mapped vector is outside ``span``."""
    a = np.asarray(matrix, dtype=np.uint8)
    if a.size == 0:
        a = np.zeros((0, n_variables), dtype=np.uint8)
    b = np.asarray(target, dtype=np.uint8)
    if not _has_mapped_solution_outside_span(a, b, n_variables, mapping, span):
        raise ValueError("no GF(2) solution maps outside the requested span")
    order = list(priority) if priority is not None else list(reversed(range(n_variables)))
    for index in order:
        selector = np.zeros(n_variables, dtype=np.uint8)
        selector[index] = 1
        trial_a, trial_b = _extend(a, b, selector, 0)
        if _has_mapped_solution_outside_span(
            trial_a, trial_b, n_variables, mapping, span
        ):
            a, b = trial_a, trial_b
        else:
            a, b = _extend(a, b, selector, 1)
    solved = solve_affine(a, b, n_variables)
    if solved is None:
        raise AssertionError("mapped GF(2) minimization lost consistency")
    return solved[0]


def canonical_kernel_image_basis(
    constraint_matrix: np.ndarray,
    n_variables: int,
    mapping: np.ndarray,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Reproduce mask-ordered independent kernel images without enumeration."""
    constraints = np.asarray(constraint_matrix, dtype=np.uint8)
    if constraints.size == 0:
        constraints = np.zeros((0, n_variables), dtype=np.uint8)
    solved = solve_affine(
        constraints, np.zeros(len(constraints), dtype=np.uint8), n_variables
    )
    if solved is None:
        raise AssertionError("homogeneous kernel system is inconsistent")
    image_rank = rank([(mapping @ vector) & 1 for vector in solved[1]])
    selected_images: list[np.ndarray] = []
    result: list[tuple[np.ndarray, np.ndarray]] = []
    while len(selected_images) < image_rank:
        coefficients = lexicographic_mapped_outside_span(
            constraints,
            np.zeros(len(constraints), dtype=np.uint8),
            n_variables,
            mapping,
            selected_images,
        )
        image = (mapping @ coefficients) & 1
        selected_images.append(image)
        result.append((coefficients, image))
    return result
