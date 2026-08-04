import numpy as np
from hayden_preskill_toy.channels import apply_channel, petz_entanglement_fidelity, petz_recovery
from hayden_preskill_toy.experiment import random_scrambler
from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_channels import channel_at_time
from hayden_preskill_toy.parametric_petz import choi_purification, entanglement_fidelity, petz, support_rank, tau_x


def test_parametric_petz_matches_b4_regimes_and_times():
    layout=SystemLayout(n_black_hole=4)
    for layers in (0,1,6):
        circuit=[] if layers==0 else random_scrambler(np.random.default_rng(8100+layers),layers)
        for t in (1,2,4,5):
            channel=channel_at_time(layout,circuit,t)
            old,old_info=petz_recovery(channel); new,new_info=petz(channel)
            for key in ('support_dimension','support_cutoff','output_dimension','choi_dimension'):
                assert old_info[key] == new_info[key]
            assert abs(
                old_info['support_trace_preservation_error']
                - new_info['support_trace_preservation_error']
            ) < 1e-12
            assert new_info['support_trace_preservation_error'] < 1e-12
            assert max(np.linalg.norm(a-b) for a,b in zip(old,new)) < 1e-12
            assert np.linalg.norm(tau_x(channel)-apply_channel(channel,np.eye(2)/2)) < 1e-12
            assert support_rank(channel) == new_info['support_dimension']
            assert abs(petz_entanglement_fidelity(channel)[0]-entanglement_fidelity(channel)[0]) < 1e-12
            old_choi=np.stack(old,axis=0).transpose(1,2,0).reshape(-1)/np.sqrt(old[0].shape[1])
            assert np.linalg.norm(old_choi-choi_purification(channel)) < 1e-12
