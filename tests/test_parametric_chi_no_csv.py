import inspect
import numpy as np
from hayden_preskill_toy.experiment import random_scrambler
from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_channels import channel_at_time
from hayden_preskill_toy.parametric_chi_correlations import logical_correlations
from hayden_preskill_toy.parametric_stabilizer import input_support_code


def test_signed_chi_correlations_are_derived_in_memory_without_csv():
    layout=SystemLayout(); circuit=random_scrambler(np.random.default_rng(20260802),6)
    rows=logical_correlations(layout,channel_at_time(layout,circuit,2),input_support_code(layout,circuit,2))
    assert len(rows)==8 and all(row['output'][0] in '+-' for row in rows)
    assert 'csv' not in inspect.getsource(logical_correlations).lower()
