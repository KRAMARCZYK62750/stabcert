import numpy as np
from hayden_preskill_toy.experiment import A, B, E, N_QUBITS, random_scrambler
from hayden_preskill_toy.support_code import support_code


def test_signed_support_generators_align_with_binary_generators():
    code = support_code(random_scrambler(np.random.default_rng(4000), 9), N_QUBITS, 0, A, B, E, 2)
    assert [value[1:] for value in code['signed_stabilizer_labels']] == code['stabilizer_labels']
