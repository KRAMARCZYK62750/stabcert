"""Nearest-neighbour line routing driven exclusively by SystemLayout."""
from __future__ import annotations

from dataclasses import dataclass

from .layout import SystemLayout
from .simulator import Gate


@dataclass(frozen=True)
class RoutingResult:
    gates: tuple[Gate, ...]
    swap_count: int
    movement_swap_count: int
    restoration_swap_count: int
    cnot_count: int
    two_qubit_depth: int
    final_wire_at_site: tuple[int, ...]
    interaction_distances: tuple[int, ...]
    interaction_swap_counts: tuple[int, ...]


def two_qubit_depth(gates: list[Gate] | tuple[Gate, ...], n: int) -> int:
    last = [0] * n
    for gate in gates:
        if gate.name == 'CNOT':
            assert gate.b is not None
            layer = max(last[gate.a], last[gate.b]) + 1
            last[gate.a] = last[gate.b] = layer
    return max(last, default=0)


def route_line(layout: SystemLayout, t: int, circuit: list[Gate]) -> RoutingResult:
    """Route a circuit on layout.chain(t), restoring every named output site."""
    chain = layout.chain(t)
    site_of = {wire: site for site, wire in enumerate(chain)}
    wire_at = list(chain)
    routed: list[Gate] = []
    swaps = 0
    movement_swaps = 0
    restoration_swaps = 0
    restoring = False
    interaction_distances: list[int] = []
    interaction_swap_counts: list[int] = []

    def swap_sites(left: int, right: int) -> None:
        nonlocal swaps, movement_swaps, restoration_swaps
        routed.extend((Gate('CNOT', left, right), Gate('CNOT', right, left), Gate('CNOT', left, right)))
        swaps += 1
        if restoring:
            restoration_swaps += 1
        else:
            movement_swaps += 1
        left_wire, right_wire = wire_at[left], wire_at[right]
        wire_at[left], wire_at[right] = right_wire, left_wire
        site_of[left_wire], site_of[right_wire] = right, left

    for gate in circuit:
        if gate.a not in site_of or (gate.b is not None and gate.b not in site_of):
            raise ValueError('circuit gate lies outside layout.X(t)')
        if gate.name != 'CNOT':
            routed.append(Gate(gate.name, site_of[gate.a]))
            continue
        assert gate.b is not None
        interaction_distances.append(abs(site_of[gate.a] - site_of[gate.b]))
        movement_before = movement_swaps
        while abs(site_of[gate.a] - site_of[gate.b]) > 1:
            target_site = site_of[gate.b]
            direction = 1 if site_of[gate.a] > target_site else -1
            swap_sites(target_site, target_site + direction)
        interaction_swap_counts.append(movement_swaps - movement_before)
        routed.append(Gate('CNOT', site_of[gate.a], site_of[gate.b]))

    # Restore the exact SystemLayout chain ordering at the output.
    restoring = True
    for desired_site, desired_wire in enumerate(chain):
        while site_of[desired_wire] != desired_site:
            current = site_of[desired_wire]
            direction = -1 if current > desired_site else 1
            swap_sites(current, current + direction)

    physical = tuple(
        Gate(g.name, chain[g.a], None if g.b is None else chain[g.b]) for g in routed
    )
    return RoutingResult(
        gates=physical,
        swap_count=swaps,
        movement_swap_count=movement_swaps,
        restoration_swap_count=restoration_swaps,
        cnot_count=sum(g.name == 'CNOT' for g in routed),
        two_qubit_depth=two_qubit_depth(routed, len(chain)),
        final_wire_at_site=tuple(wire_at),
        interaction_distances=tuple(interaction_distances),
        interaction_swap_counts=tuple(interaction_swap_counts),
    )
