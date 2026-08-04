from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_certificate import certify_routed_equivalence
from hayden_preskill_toy.parametric_graph_routing import coupling_graph, route_graph
from hayden_preskill_toy.simulator import Gate


def test_graph_routers_restore_order_obey_edges_and_preserve_clifford():
    layout = SystemLayout(n_message=1, n_black_hole=4)
    t = 2
    chain = layout.chain(t)
    # Sites 1 and 5 are non-neighbours on the chain, ring, and 2D grid for
    # this six-site layout. Every constrained geometry therefore exercises
    # SWAP insertion, while all-to-all remains SWAP-free.
    circuit = [Gate("H", chain[1]), Gate("CNOT", chain[1], chain[5])]
    for architecture in ("chain", "ring", "grid_2d", "all_to_all"):
        graph = coupling_graph(architecture, len(chain))
        routed = route_graph(layout, t, circuit, graph)
        site = {wire: index for index, wire in enumerate(chain)}
        assert routed.final_wire_at_site == chain
        assert certify_routed_equivalence(layout, t, circuit, routed.gates)
        for gate in routed.gates:
            if gate.name == "CNOT":
                assert site[gate.b] in graph.neighbours[site[gate.a]]
        if architecture == "all_to_all":
            assert routed.swap_count == 0
        else:
            assert routed.swap_count > 0
