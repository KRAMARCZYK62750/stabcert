"""Regression: the logical-action signature spans the whole Petz dilation.

When recovery is inexact the dilation is wider than the support code
(``environment_qubits > 0``).  Release 0.1.0 reconstructed the signature on
``code.logical_qubits`` wires only, so ``verify`` rejected artifacts that
``compile`` had just produced.  The frozen fixtures did not show it: all three
have exact recovery.
"""
from __future__ import annotations

from dataclasses import replace
from functools import lru_cache

import numpy as np
import pytest

from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.recovery_compile import compile_recovery
from hayden_preskill_toy.recovery_hayden_preskill_adapter import (
    hayden_preskill_to_recovery_problem,
)
from hayden_preskill_toy.recovery_verify import VerificationPolicy, verify_recovery
from hayden_preskill_toy.simulator import Gate


def _scrambler(seed: int, layout: SystemLayout, layers: int) -> list[Gate]:
    rng = np.random.default_rng(seed)
    wires = list(layout.scrambled)
    gates: list[Gate] = []
    for _ in range(layers):
        for wire in wires:
            gates.append(Gate(("H", "S")[int(rng.integers(2))], wire))
        rng.shuffle(wires)
        for control, target in zip(wires[::2], wires[1::2]):
            gates.append(Gate("CNOT", int(control), int(target)))
    return gates


# Every emission time for six scramblers on four black-hole qubits, plus the
# one six-qubit instance of the wider sweep whose dilation needs two
# environment wires.
CASES = tuple(
    (4, seed, emission_time) for seed in range(6) for emission_time in range(6)
) + ((6, 2, 1),)


@lru_cache(maxsize=None)
def _instances():
    """Every compilable case, exact and inexact recovery alike."""
    found = []
    for black_hole, seed, emission_time in CASES:
        layout = SystemLayout(1, black_hole)
        scrambler = _scrambler(1000 + seed, layout, 3 * black_hole)
        problem = hayden_preskill_to_recovery_problem(layout, scrambler, emission_time)
        try:
            artifact = compile_recovery(problem)
        except ValueError:
            continue
        found.append(((black_hole, seed, emission_time), problem, artifact))
    return tuple(found)


def _inexact():
    return tuple(item for item in _instances() if item[2].resources.environment_qubits > 0)


def test_sweep_contains_exact_and_inexact_recovery():
    assert len(_instances()) - len(_inexact()) >= 20
    assert len(_inexact()) == 7
    assert {item[2].resources.environment_qubits for item in _inexact()} == {1, 2}


@pytest.mark.parametrize(
    "policy",
    (VerificationPolicy.REPRODUCIBLE_ROUTE, VerificationPolicy.CHANNEL_CERTIFIED),
)
def test_compiler_output_is_accepted_whatever_the_fidelity(policy):
    rejected = [
        (case, [check.name for check in report.checks if not check.passed])
        for case, problem, artifact in _instances()
        for report in (verify_recovery(problem, artifact, policy=policy),)
        if not report.verified
    ]
    assert rejected == []


def test_signature_width_is_the_dilation_width():
    for _, problem, artifact in _inexact():
        width = len(problem.channel_input) + len(problem.inaccessible_partition)
        declared = artifact.certificate.logical_action_signature
        assert {len(label) - 1 for label in declared} == {width}
        assert width == artifact.tau_support.logical_qubits + artifact.resources.environment_qubits


def test_false_claim_on_an_environment_wire_is_rejected():
    """The wires added by this fix are checked, not merely tolerated."""
    for _, problem, artifact in _inexact():
        declared = artifact.certificate.logical_action_signature
        first = declared[0]
        flipped = first[:-1] + ("X" if first[-1] != "X" else "Z")
        forged = replace(
            artifact,
            certificate=replace(
                artifact.certificate,
                logical_action_signature=(flipped, *declared[1:]),
            ),
        )
        report = verify_recovery(
            problem, forged, policy=VerificationPolicy.CHANNEL_CERTIFIED
        )
        failed = [check.name for check in report.checks if not check.passed]
        assert not report.verified
        assert failed == ["certificate_signature_claims"]
