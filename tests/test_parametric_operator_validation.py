import numpy as np
from hayden_preskill_toy.experiment import random_scrambler
from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_channels import channel_at_time
from hayden_preskill_toy.parametric_validation import validate


def test_three_parametric_dilations_match_petz_on_full_support_basis():
    layout=SystemLayout()
    for seed,layers,t in ((0,0,1),(20260802,6,2),(4000,9,2)):
        c=[] if not layers else random_scrambler(np.random.default_rng(seed),layers)
        result=validate(layout,channel_at_time(layout,c,t),c,t)
        assert result['validated']
