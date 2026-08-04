import numpy as np
from hayden_preskill_toy.experiment import random_scrambler
from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_channels import channel_at_time
from hayden_preskill_toy.parametric_synthesis import signed_dilation


def test_three_b4_signed_tableaux_build_without_csv():
    layout=SystemLayout()
    for seed,layers,t in ((0,0,1),(20260802,6,2),(4000,9,2)):
        circuit=[] if layers==0 else random_scrambler(np.random.default_rng(seed),layers)
        gates,encoder,output,rows=signed_dilation(layout,channel_at_time(layout,circuit,t),circuit,t)
        assert gates and len(encoder)==len(layout.X(t)) and len(output)==len(rows)//2
