from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest

pytest.importorskip("qiskit")

from hayden_preskill_toy.recovery_artifact import CircuitSpec
from hayden_preskill_toy.recovery_problem import GateSpec
from hayden_preskill_toy.recovery_sabre import artifact_with_sabre_route
from hayden_preskill_toy.recovery_serialization import read_artifact, read_problem
from hayden_preskill_toy.recovery_verify import verify_recovery


FIXTURES = Path("tests/fixtures/recovery_v1")


@lru_cache(maxsize=None)
def _sabre_case(case_id="a1"):
    problem = read_problem(FIXTURES / f"{case_id}.problem.json")
    base = read_artifact(FIXTURES / f"{case_id}.artifact.json")
    candidate, routing = artifact_with_sabre_route(problem, base)
    return problem, base, candidate, routing


@pytest.mark.parametrize("case_id", ("a1", "a8", "a12"))
def test_sabre_route_is_different_rejected_by_strict_and_channel_certified(case_id):
    problem, base, candidate, routing = _sabre_case(case_id)
    assert candidate.routed_circuit.gates != base.routed_circuit.gates
    assert routing.movement_swaps > 0
    assert routing.final_wire_at_site == problem.physical_initial_order

    strict = verify_recovery(problem, candidate)
    channel = verify_recovery(problem, candidate, policy="channel-certified")
    assert not strict.verified
    assert not next(
        item for item in strict.checks if item.name == "deterministic_routing"
    ).passed
    assert channel.verified
    assert channel.channel_verified
    assert channel.topology_verified
    assert channel.final_order_verified
    assert channel.resource_counts_verified
    assert channel.swap_accounting_status == "not_certified"


def test_sabre_adapter_is_deterministic_for_fixed_seed_and_trials():
    problem, base, first, first_routing = _sabre_case()
    second, second_routing = artifact_with_sabre_route(problem, base)
    assert first == second
    assert first_routing == second_routing


@pytest.mark.parametrize("case_id", ("a1", "a8", "a12"))
def test_phase_mutation_of_sabre_candidate_is_rejected_as_wrong_channel(case_id):
    problem, _, candidate, _ = _sabre_case(case_id)
    gates = (
        *candidate.routed_circuit.gates,
        GateSpec("Z", (problem.requested_output[0],)),
    )
    mutated = replace(
        candidate,
        routed_circuit=CircuitSpec(problem.accessible_partition, gates),
    )
    report = verify_recovery(problem, mutated, policy="channel-certified")
    assert not report.verified
    assert not report.channel_verified
    assert not next(
        item for item in report.checks if item.name == "reduced_choi_channel"
    ).passed


@pytest.mark.parametrize("case_id", ("a1", "a8", "a12"))
def test_final_permutation_mutation_of_sabre_candidate_is_rejected(case_id):
    problem, _, candidate, _ = _sabre_case(case_id)
    shifted = (*candidate.final_permutation[1:], candidate.final_permutation[0])
    mutated = replace(candidate, final_permutation=shifted)
    report = verify_recovery(problem, mutated, policy="channel-certified")
    assert not report.verified
    assert report.channel_verified
    assert not report.final_order_verified
    assert not next(
        item
        for item in report.checks
        if item.name == "restored_final_order_declaration"
    ).passed
