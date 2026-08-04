"""Deterministic routing on fixed undirected coupling graphs."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math

from .layout import SystemLayout
from .parametric_routing import two_qubit_depth
from .simulator import Gate


@dataclass(frozen=True)
class CouplingGraph:
    name: str
    neighbours: tuple[tuple[int, ...], ...]
    rows: int | None = None
    columns: int | None = None

    @property
    def edge_count(self) -> int:
        return sum(len(items) for items in self.neighbours) // 2


@dataclass(frozen=True)
class GraphRoutingResult:
    architecture: str
    gates: tuple[Gate, ...]
    swap_count: int
    movement_swap_count: int
    restoration_swap_count: int
    cnot_count: int
    two_qubit_depth: int
    final_wire_at_site: tuple[int, ...]
    edge_count: int
    diameter: int
    grid_rows: int | None
    grid_columns: int | None
    interaction_distances: tuple[int, ...]
    interaction_swap_counts: tuple[int, ...]


def _from_edges(
    name: str,
    n: int,
    edges: set[tuple[int, int]],
    *,
    rows: int | None = None,
    columns: int | None = None,
) -> CouplingGraph:
    neighbours = [set() for _ in range(n)]
    for left, right in edges:
        if left == right:
            continue
        neighbours[left].add(right)
        neighbours[right].add(left)
    if n > 1 and any(not items for items in neighbours):
        raise ValueError(f"{name} graph is disconnected")
    return CouplingGraph(
        name,
        tuple(tuple(sorted(items)) for items in neighbours),
        rows,
        columns,
    )


def coupling_graph(name: str, n: int) -> CouplingGraph:
    if n < 1:
        raise ValueError("coupling graph requires at least one site")
    if name == "chain":
        return _from_edges(name, n, {(site, site + 1) for site in range(n - 1)})
    if name == "ring":
        edges = {(site, site + 1) for site in range(n - 1)}
        if n > 2:
            edges.add((0, n - 1))
        return _from_edges(name, n, edges)
    if name == "grid_2d":
        columns = math.ceil(math.sqrt(n))
        rows = math.ceil(n / columns)
        edges = set()
        for site in range(n):
            if site % columns + 1 < columns and site + 1 < n:
                edges.add((site, site + 1))
            if site + columns < n:
                edges.add((site, site + columns))
        return _from_edges(name, n, edges, rows=rows, columns=columns)
    if name == "all_to_all":
        return _from_edges(
            name,
            n,
            {(left, right) for left in range(n) for right in range(left + 1, n)},
        )
    raise ValueError(f"unknown coupling graph: {name}")


def shortest_path(graph: CouplingGraph, start: int, goal: int) -> tuple[int, ...]:
    if start == goal:
        return (start,)
    previous = {start: None}
    pending = deque([start])
    while pending:
        site = pending.popleft()
        for neighbour in graph.neighbours[site]:
            if neighbour in previous:
                continue
            previous[neighbour] = site
            if neighbour == goal:
                path = [goal]
                while path[-1] != start:
                    path.append(previous[path[-1]])
                return tuple(reversed(path))
            pending.append(neighbour)
    raise ValueError(f"no path in {graph.name} from {start} to {goal}")


def graph_diameter(graph: CouplingGraph) -> int:
    return max(
        len(shortest_path(graph, left, right)) - 1
        for left in range(len(graph.neighbours))
        for right in range(left, len(graph.neighbours))
    )


def route_graph(
    layout: SystemLayout,
    t: int,
    circuit: list[Gate] | tuple[Gate, ...],
    graph: CouplingGraph,
) -> GraphRoutingResult:
    """Route by moving the target along deterministic shortest paths.

    Every routing SWAP is replayed in reverse after the logical circuit. This
    restores the exact named-wire ordering without a separate token-swapping
    heuristic and makes the equivalence audit unambiguous.
    """
    chain = layout.chain(t)
    if len(graph.neighbours) != len(chain):
        raise ValueError("coupling graph/site count differs from layout.chain(t)")
    site_of = {wire: site for site, wire in enumerate(chain)}
    wire_at = list(chain)
    local_gates: list[Gate] = []
    forward_swaps: list[tuple[int, int]] = []
    interaction_distances: list[int] = []
    interaction_swap_counts: list[int] = []

    def swap_sites(left: int, right: int, *, remember: bool) -> None:
        if right not in graph.neighbours[left]:
            raise AssertionError("attempted SWAP outside coupling graph")
        local_gates.extend(
            (
                Gate("CNOT", left, right),
                Gate("CNOT", right, left),
                Gate("CNOT", left, right),
            )
        )
        left_wire, right_wire = wire_at[left], wire_at[right]
        wire_at[left], wire_at[right] = right_wire, left_wire
        site_of[left_wire], site_of[right_wire] = right, left
        if remember:
            forward_swaps.append((left, right))

    for gate in circuit:
        if gate.a not in site_of or (gate.b is not None and gate.b not in site_of):
            raise ValueError("logical gate lies outside layout.X(t)")
        if gate.name != "CNOT":
            local_gates.append(Gate(gate.name, site_of[gate.a]))
            continue
        assert gate.b is not None
        path = shortest_path(graph, site_of[gate.a], site_of[gate.b])
        interaction_distances.append(len(path) - 1)
        movement_before = len(forward_swaps)
        for position in range(len(path) - 1, 1, -1):
            swap_sites(path[position], path[position - 1], remember=True)
        interaction_swap_counts.append(len(forward_swaps) - movement_before)
        control_site = site_of[gate.a]
        target_site = site_of[gate.b]
        if target_site not in graph.neighbours[control_site]:
            raise AssertionError("routing failed to make CNOT endpoints adjacent")
        local_gates.append(Gate("CNOT", control_site, target_site))

    for left, right in reversed(forward_swaps):
        swap_sites(left, right, remember=False)
    if tuple(wire_at) != chain:
        raise AssertionError("inverse SWAP replay did not restore wire order")

    physical = tuple(
        Gate(
            gate.name,
            chain[gate.a],
            None if gate.b is None else chain[gate.b],
        )
        for gate in local_gates
    )
    swap_count = 2 * len(forward_swaps)
    return GraphRoutingResult(
        architecture=graph.name,
        gates=physical,
        swap_count=swap_count,
        movement_swap_count=len(forward_swaps),
        restoration_swap_count=len(forward_swaps),
        cnot_count=sum(gate.name == "CNOT" for gate in local_gates),
        two_qubit_depth=two_qubit_depth(local_gates, len(chain)),
        final_wire_at_site=tuple(wire_at),
        edge_count=graph.edge_count,
        diameter=graph_diameter(graph),
        grid_rows=graph.rows,
        grid_columns=graph.columns,
        interaction_distances=tuple(interaction_distances),
        interaction_swap_counts=tuple(interaction_swap_counts),
    )


def logical_interaction_distances(
    layout: SystemLayout,
    t: int,
    circuit: list[Gate] | tuple[Gate, ...],
    graph: CouplingGraph,
) -> tuple[int, ...]:
    initial_site = {wire: site for site, wire in enumerate(layout.chain(t))}
    return tuple(
        len(shortest_path(graph, initial_site[gate.a], initial_site[gate.b])) - 1
        for gate in circuit
        if gate.name == "CNOT" and gate.b is not None
    )
