"""The cost bound of the paper, read off the loops of ``gf2.py`` and checked.

Proposition 2 of the paper bounds the GF(2) work of the verifier.  Its proof is
a count of calls; this module states the same count as code and checks it on
real calls, one call at a time:

* the number of affine systems solved is an exact function of the dimensions;
* rank reductions, pivots, row operations and bit operations stay under the
  bounds;
* the verifier makes ``n + k + 6`` calls, of the dimensions the proof names;
* nothing else in the verifier reaches the elimination routines;
* none of it depends on the number of gates read.

Notation: a call has ``c`` constraints, ``v`` variables, a mapping of ``w``
rows, a span of ``sigma`` rows, and returns ``rho`` generators.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

import hayden_preskill_toy.gf2 as gf2
import hayden_preskill_toy.recovery_stabilizer as recovery_stabilizer
from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_petz_stabilizer import random_stabilizer_scrambler
from hayden_preskill_toy.recovery_compile import compile_recovery
from hayden_preskill_toy.recovery_hayden_preskill_adapter import (
    hayden_preskill_to_recovery_problem,
)
from hayden_preskill_toy.recovery_problem import GateSpec, RouterParameters
from hayden_preskill_toy.recovery_verify import VerificationPolicy, verify_recovery
from hayden_preskill_toy.simulator import Gate

ENTRY_POINTS = (
    "canonical_kernel_image_basis",
    "lexicographic_mapped_outside_span",
    "lexicographic_solution",
)
COUNTERS = ("affine_systems_solved", "rank_reductions", "pivots", "row_xors", "scalar_bit_xors")


# --- one elimination ---------------------------------------------------------

def _solve(rows: int, v: int) -> dict[str, int]:
    """``solve_affine`` on ``rows`` equations: an augmented matrix of v+1 columns."""
    pivots = min(rows, v)
    xors = pivots * max(rows - 1, 0)
    return {"pivots": pivots, "row_xors": xors, "scalar_bit_xors": xors * (v + 1)}


def _rank(rows: int, w: int) -> dict[str, int]:
    pivots = min(rows, w)
    xors = pivots * max(rows - 1, 0)
    return {"pivots": pivots, "row_xors": xors, "scalar_bit_xors": xors * w}


def _scaled(times: int, cost: dict[str, int]) -> dict[str, int]:
    return {key: times * value for key, value in cost.items()}


def _added(*costs: dict[str, int]) -> dict[str, int]:
    return {key: sum(cost[key] for cost in costs) for key in costs[0]}


# --- the three entry points ---------------------------------------------------

def bound_lexicographic_solution(c: int, v: int) -> dict[str, int]:
    """One solve, one per variable, one last: v + 2, on at most c + v rows."""
    return {"affine_systems_solved": v + 2, "rank_reductions": 0,
            **_scaled(v + 2, _solve(c + v, v))}


def bound_lexicographic_mapped(c: int, v: int, w: int, sigma: int) -> dict[str, int]:
    """v + 1 feasibility tests and one last solve.

    A feasibility test solves once, then tests the particular solution and at
    most v kernel vectors for membership in the span; a membership test is two
    rank reductions, on sigma + 1 and on sigma rows.  The membership loop may
    stop early, so its count is a bound; the solve count is exact.
    """
    membership = _added(_rank(sigma + 1, w), _rank(sigma, w))
    feasibility = _added(_solve(c + v, v), _scaled(v + 1, membership))
    return {"affine_systems_solved": v + 2, "rank_reductions": 2 * (v + 1) ** 2,
            **_added(_scaled(v + 1, feasibility), _solve(c + v, v))}


def bound_kernel_image_basis(c: int, v: int, w: int, rho: int) -> dict[str, int]:
    """One solve, one rank reduction on at most v rows, then rho searches."""
    search = bound_lexicographic_mapped(c, v, w, max(rho - 1, 0))
    work = _added(
        _solve(c, v), _rank(v, w),
        _scaled(rho, {key: search[key] for key in ("pivots", "row_xors", "scalar_bit_xors")}),
    )
    return {"affine_systems_solved": 1 + rho * (v + 2),
            "rank_reductions": 1 + rho * search["rank_reductions"], **work}


# --- instrumentation ----------------------------------------------------------

def _row_count(matrix) -> int:
    data = np.asarray(matrix, dtype=np.uint8)
    if data.size == 0:
        return 0
    return 1 if data.ndim == 1 else data.shape[0]


def _snapshot() -> tuple[int, ...]:
    stats = gf2._ACTIVE_STATS.get()
    return tuple(getattr(stats, name) for name in COUNTERS)


@pytest.fixture
def calls(monkeypatch):
    """Record every outermost call the verifier makes into the entry points."""
    log: list[dict[str, object]] = []
    depth = [0]

    def wrap(name):
        original = getattr(gf2, name)

        def wrapped(*args, **kwargs):
            if depth[0] or gf2._ACTIVE_STATS.get() is None:
                return original(*args, **kwargs)
            depth[0] += 1
            before = _snapshot()
            try:
                result = original(*args, **kwargs)
            finally:
                depth[0] -= 1
            measured = dict(zip(COUNTERS, (b - a for a, b in zip(before, _snapshot()))))
            if name == "canonical_kernel_image_basis":
                c, v, w = _row_count(args[0]), args[1], np.asarray(args[2]).shape[0]
                dims = {"c": c, "v": v, "w": w, "rho": len(result)}
                bound = bound_kernel_image_basis(c, v, w, len(result))
            elif name == "lexicographic_mapped_outside_span":
                c, v, w = _row_count(args[0]), args[2], np.asarray(args[3]).shape[0]
                dims = {"c": c, "v": v, "w": w, "sigma": len(args[4])}
                bound = bound_lexicographic_mapped(c, v, w, len(args[4]))
            else:
                c, v = _row_count(args[0]), args[2]
                dims = {"c": c, "v": v}
                bound = bound_lexicographic_solution(c, v)
            log.append({"name": name, "dims": dims, "measured": measured, "bound": bound})
            return result

        return wrapped

    for name in ENTRY_POINTS:
        monkeypatch.setattr(recovery_stabilizer, name, wrap(name))
    return log


# --- instances ----------------------------------------------------------------

def _scrambler(seed: int, layout: SystemLayout, layers: int) -> list[Gate]:
    rng = np.random.default_rng(seed)
    wires = list(layout.scrambled)
    gates: list[Gate] = []
    for _ in range(layers):
        for wire in wires:
            gates.append(Gate(("H", "S")[int(rng.integers(2))], wire))
        rng.shuffle(wires)
        for control, target in zip(wires[::2], wires[1::2]):
            gates.append(Gate("CNOT", int(control), int(target)))
    return gates


def _instance(message: int, black_hole: int, emission: int, seed: int):
    layout = SystemLayout(message, black_hole)
    problem = hayden_preskill_to_recovery_problem(
        layout, _scrambler(seed, layout, 3 * black_hole), emission
    )
    return problem, compile_recovery(problem)


def _paper_family(message: int):
    """A member of the swept family of the paper (``measure_gf2_scaling.py``)."""
    layout = SystemLayout(n_message=message, n_black_hole=4)
    scrambler = random_stabilizer_scrambler(layout, np.random.default_rng(20260802), 6)
    problem = hayden_preskill_to_recovery_problem(
        layout, scrambler, message + 4, architecture="chain",
        router=RouterParameters(lookahead=16, candidate_budget=64),
    )
    return problem, compile_recovery(problem)


INSTANCES = {
    "exact, 1 message qubit": lambda: _instance(1, 4, 3, 1001),
    "exact, wider": lambda: _instance(1, 6, 5, 1001),
    "exact, 2 message qubits": lambda: _instance(2, 6, 5, 79),
    "inexact, 1 environment wire": lambda: _instance(1, 4, 1, 1000),
    "inexact, 2 environment wires": lambda: _instance(1, 6, 1, 1002),
    "paper family, n = 9": lambda: _paper_family(1),
    "paper family, n = 10": lambda: _paper_family(2),
}


def _verify_counted(problem, artifact):
    with gf2.count_operations() as stats:
        report = verify_recovery(problem, artifact, policy=VerificationPolicy.CHANNEL_CERTIFIED)
    return report, {name: getattr(stats, name) for name in COUNTERS}


@pytest.mark.parametrize("label", INSTANCES)
def test_every_call_obeys_the_count_read_off_the_loops(label, calls):
    problem, artifact = INSTANCES[label]()
    report, totals = _verify_counted(problem, artifact)
    assert report.verified

    # Nothing else in the verifier reaches the elimination routines.
    for name in COUNTERS:
        assert sum(call["measured"][name] for call in calls) == totals[name]

    for call in calls:
        measured, bound = call["measured"], call["bound"]
        # The solve count is exact, not merely bounded.
        assert measured["affine_systems_solved"] == bound["affine_systems_solved"], call
        for name in COUNTERS[1:]:
            assert measured[name] <= bound[name], (name, call)


@pytest.mark.parametrize("label", INSTANCES)
def test_the_verifier_makes_the_calls_the_proof_names(label, calls):
    problem, artifact = INSTANCES[label]()
    _verify_counted(problem, artifact)
    m = len(problem.channel_input)
    n = len(problem.accessible_partition)
    inaccessible = len(problem.inaccessible_partition)
    width = m + n + inaccessible
    k = artifact.tau_support.logical_qubits

    assert len(calls) == n + k + 6
    names = [call["name"] for call in calls]
    assert names == (
        ["canonical_kernel_image_basis"]
        + ["lexicographic_mapped_outside_span"] * (2 * k)
        + ["lexicographic_solution"] * (n - k)
        + ["canonical_kernel_image_basis"] * 5
    )

    def dims(index, *keys):
        return tuple(calls[index]["dims"][key] for key in keys)

    assert dims(0, "c", "v", "w", "rho") == (2 * (width - n), width, 2 * n, n - k)
    for index in range(1, 1 + 2 * k):
        assert dims(index, "v", "w") == (2 * n, 2 * n)
        assert calls[index]["dims"]["sigma"] <= 2 * n
    for index in range(1 + 2 * k, 1 + n + k):
        assert calls[index]["dims"]["v"] == 2 * n
        assert calls[index]["dims"]["c"] <= 2 * n
    tail = 1 + n + k
    assert dims(tail, "c", "v", "w") == (2 * inaccessible, width, 2 * (m + n))        # target
    assert dims(tail + 1, "c", "v", "w") == (2 * (n - m), 2 * n, 2 * (m + n))         # candidate
    assert dims(tail + 2, "c", "v", "w") == (2 * inaccessible, width, 2 * (m + n))    # declared target
    assert dims(tail + 3, "c", "v", "w") == (2 * (width - 2 * m), width, 4 * m)       # fidelity
    assert dims(tail + 4, "c", "w") == (4 * m, 4 * m)                                 # overlap
    assert calls[tail + 4]["dims"]["v"] <= 4 * m

    # Every dimension is at most twice the width of the source Choi tableau,
    # which is what turns the per-call counts into a bound in that width.
    for call in calls:
        for key in ("c", "v", "w"):
            if key in call["dims"]:
                assert call["dims"][key] <= 2 * width


@pytest.mark.parametrize("message", (1, 2))
def test_closed_form_gives_the_identity_published_for_the_swept_family(message, calls):
    problem, artifact = _paper_family(message)
    _, totals = _verify_counted(problem, artifact)
    n = len(problem.accessible_partition)
    k = artifact.tau_support.logical_qubits
    closed_form = (n + k) * (2 * n + 2) + sum(
        1 + call["dims"]["rho"] * (call["dims"]["v"] + 2)
        for call in calls
        if call["name"] == "canonical_kernel_image_basis"
    )
    assert totals["affine_systems_solved"] == closed_form
    assert closed_form == 28 * n * n - 232 * n + 598


def test_the_counts_do_not_depend_on_the_number_of_gates_read():
    problem, artifact = _instance(1, 4, 3, 1001)
    _, short = _verify_counted(problem, artifact)
    wire = problem.accessible_partition[-1]
    padding = (GateSpec("H", (wire,)),) * 400
    padded = replace(
        artifact,
        routed_circuit=replace(
            artifact.routed_circuit, gates=artifact.routed_circuit.gates + padding
        ),
    )
    report, long = _verify_counted(problem, padded)
    checks = {check.name: check.passed for check in report.checks}
    assert checks["reduced_choi_channel"]
    assert long == short
