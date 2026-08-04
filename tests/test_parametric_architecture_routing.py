from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_architecture_routing import (
    causal_lightcone_depth_bound,
    route_graph_lookahead,
)
from hayden_preskill_toy.parametric_certificate import certify_routed_equivalence
from hayden_preskill_toy.parametric_graph_routing import coupling_graph
from hayden_preskill_toy.simulator import Gate


def test_lookahead_router_is_graph_local_exact_and_restores_named_wires():
    layout = SystemLayout(n_message=1, n_black_hole=4)
    t = 2
    wires = layout.chain(t)
    circuit = [
        Gate("H", wires[1]),
        Gate("CNOT", wires[1], wires[5]),
        Gate("CNOT", wires[0], wires[4]),
    ]
    for architecture in ("chain", "ring", "grid_2d", "all_to_all"):
        graph = coupling_graph(architecture, len(wires))
        routed = route_graph_lookahead(layout, t, circuit, graph)
        site = {wire: index for index, wire in enumerate(wires)}
        assert routed.final_wire_at_site == wires
        assert certify_routed_equivalence(layout, t, circuit, routed.gates)
        assert routed.swap_count == (
            routed.movement_swap_count + routed.restoration_swap_count
        )
        assert routed.restoration_swap_lower_bound <= routed.restoration_swap_count
        assert causal_lightcone_depth_bound(layout, t, circuit, graph) <= (
            routed.two_qubit_depth
        )
        for gate in routed.gates:
            if gate.name == "CNOT":
                assert site[gate.b] in graph.neighbours[site[gate.a]]


def test_all_to_all_needs_no_routing_swaps():
    layout = SystemLayout(n_message=1, n_black_hole=4)
    t = 2
    wires = layout.chain(t)
    circuit = [Gate("CNOT", wires[0], wires[-1])]
    result = route_graph_lookahead(
        layout, t, circuit, coupling_graph("all_to_all", len(wires))
    )
    assert result.swap_count == 0
    assert result.two_qubit_depth == 1

