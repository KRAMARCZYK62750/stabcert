import numpy as np

from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_channels import (
    channel_at_time,
    channel_at_time_compact,
    random_scrambler,
)


def test_compact_channel_matches_reference_without_r_workspace():
    for message_qubits, t in ((1, 2), (2, 3), (3, 3), (4, 5)):
        layout = SystemLayout(n_message=message_qubits, n_black_hole=4)
        scrambler = random_scrambler(
            layout, np.random.default_rng(20260802), 6
        )
        old = channel_at_time(layout, scrambler, t)
        compact = channel_at_time_compact(layout, scrambler, t)
        assert old.output == compact.output
        assert old.complement == compact.complement
        assert len(old.kraus) == len(compact.kraus)
        assert max(
            np.max(np.abs(left - right))
            for left, right in zip(old.kraus, compact.kraus)
        ) < 1e-12
