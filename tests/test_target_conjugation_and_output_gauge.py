"""Two properties a reviewer of the paper asked to see tested.

1. The target is complex-conjugated before comparison.  A one-qubit message
   with an ancilla in ``|+i>`` (stabilizer ``+Y``) is the smallest instance on
   which that matters: the candidate's reference carries ``-Y``, so a target
   compared without conjugation would reject the correct recovery.

2. The verdict is invariant under a transformation of the discarded
   environment on the output side (Proposition 1).  The family singled out in
   the adversarial campaign acts on the input side and tests the restriction
   to the code subspace instead.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.recovery_compile import compile_recovery
from hayden_preskill_toy.recovery_hayden_preskill_adapter import (
    hayden_preskill_to_recovery_problem,
)
from hayden_preskill_toy.recovery_problem import (
    ALLOWED_CLIFFORD_GATES,
    FORMAT_VERSION,
    CertificationThresholds,
    CouplingGraphSpec,
    GateSpec,
    PauliSpec,
    RecoveryProblem,
    RouterParameters,
)
from hayden_preskill_toy.recovery_verify import VerificationPolicy, verify_recovery
from hayden_preskill_toy.simulator import Gate

CHANNEL = "reduced_choi_channel"


def _one_ancilla_problem(operator: str, phase: int, source=()) -> RecoveryProblem:
    wires = ("M", "K")
    return RecoveryProblem(
        format_version=FORMAT_VERSION,
        qubit_order=wires,
        channel_input=("M",),
        source_clifford=tuple(GateSpec(name, targets) for name, targets in source),
        ancilla_qubits=("K",),
        ancilla_initial_stabilizers=(PauliSpec(("K",), operator, phase),),
        accessible_partition=wires,
        inaccessible_partition=(),
        requested_output=("M",),
        logical_qubit_order=("M",),
        physical_initial_order=wires,
        coupling_graph=CouplingGraphSpec(sites=wires, edges=(("K", "M"),)),
        allowed_gates=ALLOWED_CLIFFORD_GATES,
        depth_convention="asap_two_qubit_layers_single_qubit_free",
        router=RouterParameters(),
        certification_thresholds=CertificationThresholds("1e-12"),
    )


def _with_gates(artifact, gates):
    return replace(
        artifact,
        routed_circuit=replace(
            artifact.routed_circuit,
            gates=tuple(GateSpec(name, targets) for name, targets in gates),
        ),
    )


def _channel_check(problem, artifact) -> bool:
    report = verify_recovery(problem, artifact, policy=VerificationPolicy.CHANNEL_CERTIFIED)
    return {check.name: check.passed for check in report.checks}[CHANNEL]


ANCILLAS = (("Y", 0), ("Y", 2), ("Z", 0), ("Z", 2), ("X", 0), ("X", 2))
CNOT = (("CNOT", ("M", "K")),)


@pytest.mark.parametrize("operator,phase", ANCILLAS)
def test_returning_the_message_is_accepted_for_every_ancilla_state(operator, phase):
    problem = _one_ancilla_problem(operator, phase)
    artifact = compile_recovery(problem)
    report = verify_recovery(problem, artifact, policy=VerificationPolicy.CHANNEL_CERTIFIED)
    assert report.verified
    # The empty circuit is the recovery a reader would write by hand.
    assert _channel_check(problem, _with_gates(artifact, ()))


def test_target_of_a_plus_i_ancilla_is_conjugated():
    problem = _one_ancilla_problem("Y", 0)
    report = verify_recovery(
        problem, compile_recovery(problem), policy=VerificationPolicy.CHANNEL_CERTIFIED
    )
    # +Y on the ancilla of the specification, -Y in the target compared.
    assert "-__Y" in report.target_reduced_choi_signature
    assert "+__Y" not in report.target_reduced_choi_signature


@pytest.mark.parametrize("operator,phase", ANCILLAS)
def test_entangling_source_needs_its_inverse(operator, phase):
    problem = _one_ancilla_problem(operator, phase, CNOT)
    artifact = compile_recovery(problem)
    assert _channel_check(problem, _with_gates(artifact, CNOT))
    if operator == "X":
        # CNOT acts trivially on a |+> or |-> target up to a sign on the
        # control: the message is not spread, and doing nothing is a recovery
        # exactly when that sign is +.
        assert _channel_check(problem, _with_gates(artifact, ())) is (phase == 0)
    else:
        assert not _channel_check(problem, _with_gates(artifact, ()))


def _hayden_preskill_instance():
    layout = SystemLayout(1, 4)
    rng = np.random.default_rng(1001)
    wires = list(layout.scrambled)
    gates: list[Gate] = []
    for _ in range(12):
        for wire in wires:
            gates.append(Gate(("H", "S")[int(rng.integers(2))], wire))
        rng.shuffle(wires)
        for control, target in zip(wires[::2], wires[1::2]):
            gates.append(Gate("CNOT", int(control), int(target)))
    problem = hayden_preskill_to_recovery_problem(layout, gates, 3)
    return problem, compile_recovery(problem)


def test_gates_on_discarded_output_wires_do_not_move_the_verdict():
    problem, artifact = _hayden_preskill_instance()
    assert _channel_check(problem, artifact)
    discarded = [w for w in problem.accessible_partition if w not in problem.requested_output]
    assert len(discarded) >= 2
    base = [(g.operation, g.qubits) for g in artifact.routed_circuit.gates]
    for wire in discarded:
        for name in ("H", "S", "X", "Z"):
            assert _channel_check(problem, _with_gates(artifact, base + [(name, (wire,))]))
    edges = [
        edge
        for edge in problem.coupling_graph.edges
        if all(site in discarded for site in edge)
    ]
    assert edges
    for left, right in edges:
        assert _channel_check(problem, _with_gates(artifact, base + [("CNOT", (left, right))]))
        assert _channel_check(problem, _with_gates(artifact, base + [("CNOT", (right, left))]))


def test_the_same_gates_on_the_requested_output_are_rejected():
    problem, artifact = _hayden_preskill_instance()
    base = [(g.operation, g.qubits) for g in artifact.routed_circuit.gates]
    for wire in problem.requested_output:
        for name in ("H", "S", "X", "Z"):
            assert not _channel_check(problem, _with_gates(artifact, base + [(name, (wire,))]))
