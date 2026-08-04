import numpy as np
from hayden_preskill_toy.experiment import random_scrambler as legacy_scrambler
from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_channels import random_scrambler


def test_parametric_b4_scrambler_matches_legacy_exactly():
    layout = SystemLayout(n_black_hole=4)
    for seed in (4000, 4019, 20260802):
        for layers in (0, 3, 6, 9):
            assert random_scrambler(layout, np.random.default_rng(seed), layers) == legacy_scrambler(
                np.random.default_rng(seed), layers
            )
