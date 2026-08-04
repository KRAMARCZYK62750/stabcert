"""Model-independent copy of the validated common look-ahead router.

The algorithm is intentionally unchanged from the scientific pipeline.  This
module merely replaces integer Hayden--Preskill registers by named wires from
``RecoveryProblem``.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .recovery_problem import CouplingGraphSpec, GateSpec, RouterParameters
from .recovery_stabilizer import two_qubit_depth


@dataclass(frozen=True)
class NamedRoutingResult:
    gates: tuple[GateSpec, ...]
    movement_swaps: int
    restoration_swaps: int
    cnot_count: int
    two_qubit_depth: int
    final_wire_at_site: tuple[str, ...]


def _neighbours(graph: CouplingGraphSpec) -> tuple[tuple[int, ...], ...]:
    indices = {site: index for index, site in enumerate(graph.sites)}
    values = [set() for _ in graph.sites]
    for left_name, right_name in graph.edges:
        left, right = indices[left_name], indices[right_name]
        values[left].add(right)
        values[right].add(left)
    return tuple(tuple(sorted(items)) for items in values)


def _shortest_path(
    neighbours: tuple[tuple[int, ...], ...], start: int, goal: int
) -> tuple[int, ...]:
    if start == goal:
        return (start,)
    previous: dict[int, int | None] = {start: None}
    pending = deque([start])
    while pending:
        site = pending.popleft()
        for neighbour in neighbours[site]:
            if neighbour in previous:
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
    raise ValueError("coupling graph is disconnected")


def _distance_matrix(neighbours: tuple[tuple[int, ...], ...]) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(len(_shortest_path(neighbours, left, right)) - 1 for right in range(len(neighbours)))
        for left in range(len(neighbours))
    )


def _future_interactions(
    circuit: tuple[GateSpec, ...], start: int, limit: int
) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for gate in circuit[start + 1 :]:
        if gate.operation == "CNOT":
            pairs.append((gate.qubits[0], gate.qubits[1]))
            if len(pairs) == limit:
                break
    return tuple(pairs)


def _active_shortest_path(
    neighbours: tuple[tuple[int, ...], ...], start: int, goal: int, active: set[int]
) -> tuple[int, ...]:
    if start == goal:
        return (start,)
    previous: dict[int, int | None] = {start: None}
    pending = [start]
    for site in pending:
        for neighbour in neighbours[site]:
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
    neighbours: tuple[tuple[int, ...], ...], active: set[int], removed: int
) -> bool:
    remaining = active - {removed}
    if len(remaining) <= 1:
        return True
    start = min(remaining)
    reached = {start}
    pending = [start]
    for site in pending:
        for neighbour in neighbours[site]:
            if neighbour in remaining and neighbour not in reached:
                reached.add(neighbour)
                pending.append(neighbour)
    return reached == remaining


def route_named_circuit(
    circuit: tuple[GateSpec, ...],
    graph: CouplingGraphSpec,
    router: RouterParameters,
) -> NamedRoutingResult:
    """Route and restore a named-wire circuit on an undirected graph."""
    if graph.directed:
        raise ValueError("v1 router requires an undirected coupling graph")
    chain = graph.sites
    neighbours = _neighbours(graph)
    distances = _distance_matrix(neighbours)
    site_of = {wire: site for site, wire in enumerate(chain)}
    wire_at = list(chain)
    home = dict(site_of)
    local_gates: list[tuple[str, int, int | None]] = []
    movement_swaps = 0
    restoration_swaps = 0

    def swap_sites(left: int, right: int, *, restoration: bool) -> None:
        nonlocal movement_swaps, restoration_swaps
        if right not in neighbours[left]:
            raise AssertionError("attempted SWAP outside coupling graph")
        local_gates.extend(
            (("CNOT", left, right), ("CNOT", right, left), ("CNOT", left, right))
        )
        left_wire, right_wire = wire_at[left], wire_at[right]
        wire_at[left], wire_at[right] = right_wire, left_wire
        site_of[left_wire], site_of[right_wire] = right, left
        if restoration:
            restoration_swaps += 1
        else:
            movement_swaps += 1

    def candidate_score(
        left: int, right: int, future: tuple[tuple[str, str], ...]
    ) -> tuple[int, int, int, int]:
        left_wire, right_wire = wire_at[left], wire_at[right]

        def hypothetical_site(wire: str) -> int:
            if wire == left_wire:
                return right
            if wire == right_wire:
                return left
            return site_of[wire]

        weighted_future = 0
        for offset, (control, target) in enumerate(future):
            weight = len(future) - offset
            weighted_future += weight * distances[hypothetical_site(control)][hypothetical_site(target)]
        restore_potential = sum(
            distances[hypothetical_site(wire)][home[wire]] for wire in chain
        )
        return weighted_future, restore_potential, min(left, right), max(left, right)

    for gate_index, gate in enumerate(circuit):
        if any(wire not in site_of for wire in gate.qubits):
            raise ValueError("logical gate lies outside physical_initial_order")
        if gate.operation != "CNOT":
            local_gates.append((gate.operation, site_of[gate.qubits[0]], None))
            continue
        control, target = gate.qubits
        future = _future_interactions(circuit, gate_index, router.lookahead)
        while distances[site_of[control]][site_of[target]] > 1:
            control_site, target_site = site_of[control], site_of[target]
            current_distance = distances[control_site][target_site]
            candidates: list[tuple[tuple[int, int, int, int], int, int]] = []
            for neighbour in neighbours[control_site]:
                if distances[neighbour][target_site] == current_distance - 1:
                    candidates.append((candidate_score(control_site, neighbour, future), control_site, neighbour))
            for neighbour in neighbours[target_site]:
                if distances[control_site][neighbour] == current_distance - 1:
                    candidates.append((candidate_score(target_site, neighbour, future), target_site, neighbour))
            candidates.sort()
            if not candidates:
                raise AssertionError("no shortest-path routing move found")
            _, left, right = candidates[: router.candidate_budget][0]
            swap_sites(left, right, restoration=False)
        control_site, target_site = site_of[control], site_of[target]
        if target_site not in neighbours[control_site]:
            raise AssertionError("routing failed to make CNOT endpoints adjacent")
        local_gates.append(("CNOT", control_site, target_site))

    active = set(range(len(chain)))
    while len(active) > 1:
        choices = []
        for desired_site in sorted(active):
            if not _removal_preserves_connectivity(neighbours, active, desired_site):
                continue
            desired_wire = chain[desired_site]
            path = _active_shortest_path(neighbours, site_of[desired_wire], desired_site, active)
            choices.append((len(path) - 1, desired_site, path))
        if not choices:
            raise AssertionError("no connectivity-preserving restoration step")
        _, desired_site, path = min(choices)
        for left, right in zip(path, path[1:]):
            swap_sites(left, right, restoration=True)
        active.remove(desired_site)
    if tuple(wire_at) != chain:
        raise AssertionError("canonical restoration did not restore wire order")

    gates = tuple(
        GateSpec(operation, (chain[left],) if right is None else (chain[left], chain[right]))
        for operation, left, right in local_gates
    )
    return NamedRoutingResult(
        gates=gates,
        movement_swaps=movement_swaps,
        restoration_swaps=restoration_swaps,
        cnot_count=sum(gate.operation == "CNOT" for gate in gates),
        two_qubit_depth=two_qubit_depth(gates),
        final_wire_at_site=tuple(wire_at),
    )
