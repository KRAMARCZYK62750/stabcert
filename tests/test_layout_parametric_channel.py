import numpy as np
from hayden_preskill_toy.channels import channel_at_time as legacy
from hayden_preskill_toy.experiment import random_scrambler
from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_channels import channel_at_time


def test_b4_layout_and_channel_match_legacy_known_instance():
    layout=SystemLayout(n_black_hole=4); circuit=random_scrambler(np.random.default_rng(4000),6)
    old,new=legacy(circuit,2),channel_at_time(layout,circuit,2)
    assert (layout.R,layout.A,layout.B,layout.E,layout.X(2),layout.C(2)) == (0,1,(2,3,4,5),(6,7,8,9),(6,7,8,9,1,2),(3,4,5))
    assert old.output == new.output and old.complement == new.complement
    assert len(old.kraus)==len(new.kraus)
    assert max(np.linalg.norm(a-b) for a,b in zip(old.kraus,new.kraus)) < 1e-12
