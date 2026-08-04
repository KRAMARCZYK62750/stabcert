import inspect
import numpy as np

from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_certificate import (
    circuit_entanglement_fidelity_stabilizer,
    certify_routed_equivalence,
    structural_validation,
)
from hayden_preskill_toy.parametric_channels import channel_at_time, random_scrambler
from hayden_preskill_toy.parametric_chi_correlations import logical_correlations
from hayden_preskill_toy.parametric_routing import route_line
from hayden_preskill_toy.parametric_stabilizer import input_support_code
from hayden_preskill_toy.parametric_synthesis import (
    _output_support_stabilizers,
    signed_dilation,
)
from hayden_preskill_toy.support_code import (
    _destabilizers_linear,
    _logical_pairs_linear,
    support_code_structural,
)


def test_structural_path_contains_no_exponential_enumeration_calls():
    functions = (
        support_code_structural,
        _logical_pairs_linear,
        _destabilizers_linear,
        logical_correlations,
        _output_support_stabilizers,
    )
    for function in functions:
        source = inspect.getsource(function)
        assert "_group(" not in source
        assert "range(1 <<" not in source
        assert "range(1<<" not in source


def test_state_free_entanglement_validator_has_no_dense_state_path():
    source = inspect.getsource(circuit_entanglement_fidelity_stabilizer)
    structural_source = inspect.getsource(structural_validation)
    forbidden = ("zero_state", "apply_circuit", "reshape", "np.zeros", "partial_trace")
    for token in forbidden:
        assert token not in source
        assert token not in structural_source


def test_structural_certificates_pass_a1_through_a4():
    for message_qubits, t in ((1, 2), (2, 3), (3, 3), (4, 5)):
        layout = SystemLayout(n_message=message_qubits, n_black_hole=4)
        scrambler = random_scrambler(
            layout, np.random.default_rng(20260802), 6
        )
        channel = channel_at_time(layout, scrambler, t)
        gates, encoder, output, rows = signed_dilation(
            layout, channel, scrambler, t
        )
        metrics = structural_validation(
            layout, channel, scrambler, t, gates, encoder, output, rows
        )
        routed = route_line(layout, t, gates)
        assert metrics["certified"]
        assert metrics["reduced_choi_equal"]
        assert metrics["validated"]
        assert metrics["stabilizer_group_elements_enumerated"] == 0
        assert metrics["support_operators_enumerated"] == 0
        assert certify_routed_equivalence(layout, t, gates, routed.gates)
