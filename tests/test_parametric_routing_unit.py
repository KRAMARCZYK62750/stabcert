from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_routing import route_line
from hayden_preskill_toy.simulator import Gate


def test_parametric_router_is_local_and_restores_layout_order():
    layout = SystemLayout(n_black_hole=4)
    chain = layout.chain(2)
    result = route_line(layout, 2, [Gate('CNOT', chain[0], chain[-1])])
    positions = {wire: i for i, wire in enumerate(chain)}
    assert result.final_wire_at_site == chain
    assert result.swap_count == 2 * (len(chain) - 2)
    assert all(
        gate.name != 'CNOT' or abs(positions[gate.a] - positions[gate.b]) == 1
        for gate in result.gates
    )
