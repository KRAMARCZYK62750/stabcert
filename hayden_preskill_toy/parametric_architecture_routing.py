"""Architecture-aware Clifford routing with a fixed, graph-independent budget.

The router keeps the logical-to-physical placement between interactions.  For
each non-local CNOT it considers shortest-path moves of either endpoint and
uses the same bounded look-ahead score on every coupling graph. The final
placement is restored by the same connectivity-preserving token-placement
algorithm on every architecture.
"""
from __future__ import annotations

from dataclasses import dataclass

import stim

from .layout import SystemLayout
from .parametric_graph_routing import CouplingGraph, shortest_path
from .parametric_routing import two_qubit_depth
from .simulator import Gate


@dataclass(frozen=True)
class InteractionRoutingAudit:
    gate_index: int
    distance_before: int
    movement_swaps: int
    control_moves: int
    target_moves: int


@dataclass(frozen=True)
class ArchitectureRoutingResult:
    architecture: str
    gates: tuple[Gate, ...]
    swap_count: int
    movement_swap_count: int
    restoration_swap_count: int
    restoration_swap_lower_bound: int
    cnot_count: int
    two_qubit_depth: int
    final_wire_at_site: tuple[int, ...]
    lookahead: int
    candidate_budget: int
    audit: tuple[InteractionRoutingAudit, ...]


def _distance_matrix(graph: CouplingGraph) -> tuple[tuple[int, ...], ...]:
    n = len(graph.neighbours)
    return tuple(
        tuple(len(shortest_path(graph, left, right)) - 1 for right in range(n))
        for left in range(n)
    )


def _future_interactions(
    circuit: list[Gate] | tuple[Gate, ...], start: int, limit: int
) -> tuple[tuple[int, int], ...]:
    pairs = []
    for gate in circuit[start + 1 :]:
        if gate.name == "CNOT":
            assert gate.b is not None
            pairs.append((gate.a, gate.b))
            if len(pairs) == limit:
                break
    return tuple(pairs)


def _active_shortest_path(
    graph: CouplingGraph, start: int, goal: int, active: set[int]
) -> tuple[int, ...]:
    if start == goal:
        return (start,)
    pending = [start]
    previous: dict[int, int | None] = {start: None}
    for site in pending:
        for neighbour in graph.neighbours[site]:
            if neighbour not in active or neighbour in previous:
                continue
            previous[neighbour] = site
            if neighbour == goal:
                path = [goal]
                while path[-1] != start:
                    parent = previous[path[-1]]
                    assert parent is not None
                    path.append(parent)
                return tuple(reversed(path))
            pending.append(neighbour)
    raise ValueError("active coupling subgraph is disconnected")


def _removal_preserves_connectivity(
    graph: CouplingGraph, active: set[int], removed: int
) -> bool:
    remaining = active - {removed}
    if len(remaining) <= 1:
        return True
    start = min(remaining)
    reached = {start}
    pending = [start]
    for site in pending:
        for neighbour in graph.neighbours[site]:
            if neighbour in remaining and neighbour not in reached:
                reached.add(neighbour)
                pending.append(neighbour)
    return reached == remaining


def _localized_tableau(gates: list[Gate], n: int) -> stim.Tableau:
    circuit = stim.Circuit()
    for qubit in range(n):
        circuit.append("I", [qubit])
    for gate in gates:
        if gate.name == "CNOT":
            assert gate.b is not None
            circuit.append("CX", [gate.a, gate.b])
        else:
            circuit.append(gate.name, [gate.a])
    return stim.Tableau.from_circuit(circuit)


def causal_lightcone_depth_bound(
    layout: SystemLayout,
    t: int,
    circuit: list[Gate] | tuple[Gate, ...],
    graph: CouplingGraph,
) -> int:
    """Certified local-depth bound from signed Clifford Pauli propagation.

    A depth-K nearest-neighbour circuit can move the support of a Pauli
    generator by at most graph distance K from its input site.  The maximum
    input-to-output support distance of X_i and Z_i is therefore a lower bound
    for any local realization that restores the named output order.
    """
    chain = layout.chain(t)
    local = {wire: index for index, wire in enumerate(chain)}
    localized = [
        Gate(
            gate.name,
            local[gate.a],
            None if gate.b is None else local[gate.b],
        )
        for gate in circuit
    ]
    tableau = _localized_tableau(localized, len(chain))
    distances = _distance_matrix(graph)
    bound = 0
    for source in range(len(chain)):
        for pauli in (tableau.x_output(source), tableau.z_output(source)):
            x, z = pauli.to_numpy()
            for target in range(len(chain)):
                if x[target] or z[target]:
                    bound = max(bound, distances[source][target])
    return bound


def route_graph_lookahead(
    layout: SystemLayout,
    t: int,
    circuit: list[Gate] | tuple[Gate, ...],
    graph: CouplingGraph,
    *,
    lookahead: int = 16,
    candidate_budget: int = 64,
) -> ArchitectureRoutingResult:
    """Route a fixed Clifford circuit using the same heuristic on every graph."""
    if lookahead < 0 or candidate_budget < 1:
        raise ValueError("invalid routing budget")
    chain = layout.chain(t)
    n = len(chain)
    if len(graph.neighbours) != n:
        raise ValueError("coupling graph/site count differs from layout.chain(t)")
    site_of = {wire: site for site, wire in enumerate(chain)}
    wire_at = list(chain)
    home = dict(site_of)
    distances = _distance_matrix(graph)
    local_gates: list[Gate] = []
    movement_swaps = 0
    restoration_swaps = 0
    audits: list[InteractionRoutingAudit] = []
    restoration_swap_lower_bound = 0

    def swap_sites(left: int, right: int, *, restoration: bool) -> None:
        nonlocal movement_swaps, restoration_swaps
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
        if restoration:
            restoration_swaps += 1
        else:
            movement_swaps += 1

    def candidate_score(
        left: int,
        right: int,
        future: tuple[tuple[int, int], ...],
    ) -> tuple[int, int, int, int]:
        left_wire, right_wire = wire_at[left], wire_at[right]

        def hypothetical_site(wire: int) -> int:
            if wire == left_wire:
                return right
            if wire == right_wire:
                return left
            return site_of[wire]

        weighted_future = 0
        for offset, (control, target) in enumerate(future):
            weight = len(future) - offset
            weighted_future += weight * distances[
                hypothetical_site(control)
            ][hypothetical_site(target)]
        restore_potential = sum(
            distances[hypothetical_site(wire)][home[wire]] for wire in chain
        )
        return weighted_future, restore_potential, min(left, right), max(left, right)

    for gate_index, gate in enumerate(circuit):
        if gate.a not in site_of or (gate.b is not None and gate.b not in site_of):
            raise ValueError("logical gate lies outside layout.X(t)")
        if gate.name != "CNOT":
            local_gates.append(Gate(gate.name, site_of[gate.a]))
            continue
        assert gate.b is not None
        distance_before = distances[site_of[gate.a]][site_of[gate.b]]
        future = _future_interactions(circuit, gate_index, lookahead)
        control_moves = 0
        target_moves = 0
        swaps_here = 0
        while distances[site_of[gate.a]][site_of[gate.b]] > 1:
            control_site = site_of[gate.a]
            target_site = site_of[gate.b]
            current_distance = distances[control_site][target_site]
            candidates: list[tuple[tuple[int, int, int, int], int, int, str]] = []
            for neighbour in graph.neighbours[control_site]:
                if distances[neighbour][target_site] == current_distance - 1:
                    candidates.append(
                        (candidate_score(control_site, neighbour, future), control_site, neighbour, "control")
                    )
            for neighbour in graph.neighbours[target_site]:
                if distances[control_site][neighbour] == current_distance - 1:
                    candidates.append(
                        (candidate_score(target_site, neighbour, future), target_site, neighbour, "target")
                    )
            candidates.sort()
            if not candidates:
                raise AssertionError("no shortest-path routing move found")
            _, left, right, moved = candidates[0:candidate_budget][0]
            swap_sites(left, right, restoration=False)
            swaps_here += 1
            if moved == "control":
                control_moves += 1
            else:
                target_moves += 1
        control_site = site_of[gate.a]
        target_site = site_of[gate.b]
        if target_site not in graph.neighbours[control_site]:
            raise AssertionError("routing failed to make CNOT endpoints adjacent")
        local_gates.append(Gate("CNOT", control_site, target_site))
        audits.append(
            InteractionRoutingAudit(
                gate_index,
                distance_before,
                swaps_here,
                control_moves,
                target_moves,
            )
        )

    # Restore the named output order on any connected graph. At each step, fix
    # one vertex whose removal leaves the active graph connected. The desired
    # token is brought to that vertex along an active shortest path, after
    # which the vertex is never touched again. This is a deterministic,
    # architecture-neutral token-placement construction, not an optimal
    # token-swapping solver.
    total_home_distance = sum(
        distances[site_of[wire]][home[wire]] for wire in chain
    )
    # One adjacent SWAP can reduce this sum by at most two.
    restoration_swap_lower_bound = (total_home_distance + 1) // 2
    active = set(range(n))
    while len(active) > 1:
        choices = []
        for desired_site in sorted(active):
            if not _removal_preserves_connectivity(graph, active, desired_site):
                continue
            desired_wire = chain[desired_site]
            current = site_of[desired_wire]
            path = _active_shortest_path(graph, current, desired_site, active)
            choices.append((len(path) - 1, desired_site, path))
        if not choices:
            raise AssertionError("no connectivity-preserving restoration step")
        _, desired_site, path = min(choices)
        for left, right in zip(path, path[1:]):
            swap_sites(left, right, restoration=True)
        active.remove(desired_site)
    if tuple(wire_at) != chain:
        raise AssertionError("canonical restoration did not restore wire order")

    physical = tuple(
        Gate(
            gate.name,
            chain[gate.a],
            None if gate.b is None else chain[gate.b],
        )
        for gate in local_gates
    )
    return ArchitectureRoutingResult(
        architecture=graph.name,
        gates=physical,
        swap_count=movement_swaps + restoration_swaps,
        movement_swap_count=movement_swaps,
        restoration_swap_count=restoration_swaps,
        restoration_swap_lower_bound=restoration_swap_lower_bound,
        cnot_count=sum(gate.name == "CNOT" for gate in local_gates),
        two_qubit_depth=two_qubit_depth(local_gates, n),
        final_wire_at_site=tuple(wire_at),
        lookahead=lookahead,
        candidate_budget=candidate_budget,
        audit=tuple(audits),
    )
