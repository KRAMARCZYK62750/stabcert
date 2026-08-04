import numpy as np
from hayden_preskill_toy.experiment import random_scrambler
from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_stabilizer import input_support_code
from hayden_preskill_toy.support_code import support_code


def test_parametric_support_code_matches_b4_known_cases():
    layout=SystemLayout(n_black_hole=4)
    cases=(([],1),(random_scrambler(np.random.default_rng(20260802),6),2),(random_scrambler(np.random.default_rng(4000),9),2))
    for circuit,t in cases:
        old=support_code(circuit,10,0,1,(2,3,4,5),(6,7,8,9),t)
        new=input_support_code(layout,circuit,t)
        for key in ('physical_qubits','support_dimension','independent_stabilizers','logical_qubits','stabilizer_labels','signed_stabilizer_labels','logical_X_labels','logical_Z_labels','destabilizer_labels'):
            assert new[key] == old[key]
