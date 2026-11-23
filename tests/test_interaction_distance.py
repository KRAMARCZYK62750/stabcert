"""The distance diagnostic of the verifier is a breadth-first search.

Release 0.1.1 kept the frontier as a list, so a site reached along several
shortest paths entered the next layer once per path.  On a layered graph one
nonlocal CNOT then cost time exponential in the distance: an artifact that
would be rejected could stall the verifier that was about to reject it.
"""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from hayden_preskill_toy.recovery_verify import _maximum_interaction_distance


def _problem(sites, edges):
    return SimpleNamespace(
        coupling_graph=SimpleNamespace(sites=tuple(sites), edges=tuple(edges))
    )


def _cnot(control, target):
    return SimpleNamespace(operation="CNOT", qubits=(control, target))


def _layered(layers: int):
    """Two sites per layer, every site joined to both sites of the next layer."""
    sites = ["s", "t"] + [f"{side}{i}" for i in range(layers) for side in "ab"]
    edges = [("s", "a0"), ("s", "b0"), (f"a{layers - 1}", "t"), (f"b{layers - 1}", "t")]
    for i in range(layers - 1):
        edges += [(f"{x}{i}", f"{y}{i + 1}") for x in "ab" for y in "ab"]
    return _problem(sites, edges)


def test_distances_on_a_chain_and_a_ring():
    chain = _problem("abcde", [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")])
    assert _maximum_interaction_distance(chain, [_cnot("a", "b")]) == 1
    assert _maximum_interaction_distance(chain, [_cnot("a", "e")]) == 4
    assert _maximum_interaction_distance(chain, [_cnot("b", "c"), _cnot("e", "b")]) == 3
    ring = _problem("abcdef", [(x, y) for x, y in zip("abcdef", "bcdefa")])
    assert _maximum_interaction_distance(ring, [_cnot("a", "d")]) == 3
    assert _maximum_interaction_distance(ring, [_cnot("a", "e")]) == 2


def test_single_qubit_gates_are_ignored():
    chain = _problem("abc", [("a", "b"), ("b", "c")])
    gates = [SimpleNamespace(operation="H", qubits=("a",))]
    assert _maximum_interaction_distance(chain, gates) == 0


def test_a_disconnected_interaction_is_refused():
    split = _problem("abcd", [("a", "b"), ("c", "d")])
    with pytest.raises(ValueError):
        _maximum_interaction_distance(split, [_cnot("a", "d")])


@pytest.mark.parametrize("layers", (4, 16, 200))
def test_layered_graph_distance_is_the_number_of_layers_plus_one(layers):
    assert _maximum_interaction_distance(_layered(layers), [_cnot("s", "t")]) == layers + 1


def test_one_nonlocal_cnot_on_a_layered_graph_does_not_stall_the_verifier():
    # 2**200 shortest paths join the two ends. With a frontier holding one
    # entry per path this search does not finish; visiting each site once, it
    # is a few hundred set operations.
    problem = _layered(200)
    started = time.perf_counter()
    assert _maximum_interaction_distance(problem, [_cnot("s", "t")] * 50) == 201
    assert time.perf_counter() - started < 5.0
