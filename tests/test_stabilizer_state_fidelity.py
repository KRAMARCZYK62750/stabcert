import stim

from hayden_preskill_toy.parametric_certificate import stabilizer_state_fidelity


def test_stabilizer_overlap_recovers_floor_perfect_and_phase_conflict():
    bell = [stim.PauliString("+XX"), stim.PauliString("+ZZ")]
    floor = stabilizer_state_fidelity([], bell)
    perfect = stabilizer_state_fidelity(bell, bell)
    conflict = stabilizer_state_fidelity(
        [stim.PauliString("-XX"), stim.PauliString("+ZZ")], bell
    )
    assert floor["fidelity"] == 0.25
    assert perfect["fidelity"] == 1.0
    assert conflict["fidelity"] == 0.0
    assert not conflict["phases_match_on_intersection"]
