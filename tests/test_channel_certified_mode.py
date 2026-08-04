from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

import pytest

from hayden_preskill_toy.recovery_artifact import CircuitSpec
from hayden_preskill_toy.recovery_exit_codes import RecoveryExitCode
from hayden_preskill_toy.recovery_problem import GateSpec
from hayden_preskill_toy.recovery_serialization import (
    read_artifact,
    read_problem,
    read_run_report,
    write_artifact,
)
from hayden_preskill_toy.recovery_stabilizer import two_qubit_depth
from hayden_preskill_toy.recovery_verify import VerificationPolicy, verify_recovery


FIXTURES = Path("tests/fixtures/recovery_v1")


def _fixture():
    return (
        read_problem(FIXTURES / "a1.problem.json"),
        read_artifact(FIXTURES / "a1.artifact.json"),
    )


def _append_routed(artifact, *gates: GateSpec, update_cnot_resources: bool = False):
    routed = (*artifact.routed_circuit.gates, *gates)
    resources = artifact.resources
    if update_cnot_resources:
        resources = replace(
            resources,
            routed_depth=two_qubit_depth(routed),
            routed_cnot=sum(gate.operation == "CNOT" for gate in routed),
        )
    return replace(
        artifact,
        routed_circuit=CircuitSpec(artifact.routed_circuit.qubit_order, routed),
        resources=resources,
    )


@pytest.mark.parametrize("case_id", ("a1", "a8", "a12"))
def test_historical_route_passes_both_policies(case_id):
    problem = read_problem(FIXTURES / f"{case_id}.problem.json")
    artifact = read_artifact(FIXTURES / f"{case_id}.artifact.json")
    strict = verify_recovery(problem, artifact)
    channel = verify_recovery(
        problem, artifact, policy=VerificationPolicy.CHANNEL_CERTIFIED
    )
    assert strict.verified and channel.verified
    assert strict.verification_policy == "reproducible-route"
    assert channel.verification_policy == "channel-certified"
    assert channel.channel_verified
    assert channel.topology_verified
    assert channel.logical_action_verified
    assert channel.final_order_verified
    assert channel.resource_counts_verified
    assert channel.swap_accounting_status == "not_certified"
    assert channel.observed_resources.logical_two_qubit_gates == artifact.resources.logical_cnot
    assert channel.observed_resources.routed_two_qubit_gates == artifact.resources.routed_cnot
    assert channel.observed_resources.logical_two_qubit_depth == artifact.resources.logical_depth
    assert channel.observed_resources.routed_two_qubit_depth == artifact.resources.routed_depth
    assert channel.observed_resources.max_routed_interaction_distance == 1


def test_textually_different_identity_route_is_channel_certified_only():
    problem, artifact = _fixture()
    alternative = _append_routed(
        artifact,
        GateSpec("H", (problem.requested_output[0],)),
        GateSpec("H", (problem.requested_output[0],)),
    )
    strict = verify_recovery(problem, alternative)
    channel = verify_recovery(problem, alternative, policy="channel-certified")
    assert not strict.verified
    assert not next(
        item for item in strict.checks if item.name == "deterministic_routing"
    ).passed
    assert channel.verified
    assert channel.channel_verified


def test_environment_gauge_does_not_change_reduced_channel():
    problem, artifact = _fixture()
    environment_wire = next(
        wire for wire in problem.accessible_partition if wire not in problem.requested_output
    )
    gauged = _append_routed(artifact, GateSpec("H", (environment_wire,)))
    strict = verify_recovery(problem, gauged)
    channel = verify_recovery(problem, gauged, policy="channel-certified")
    assert not strict.verified
    assert not next(
        item for item in strict.checks if item.name == "logical_routed_action"
    ).passed
    assert channel.verified
    assert channel.channel_verified


def test_wrong_channel_is_rejected_even_when_topology_is_valid():
    problem, artifact = _fixture()
    wrong = _append_routed(
        artifact, GateSpec("X", (problem.requested_output[0],))
    )
    report = verify_recovery(problem, wrong, policy="channel-certified")
    assert not report.verified
    assert not report.channel_verified
    assert report.topology_verified
    assert not next(
        item for item in report.checks if item.name == "reduced_choi_channel"
    ).passed


def test_identity_on_forbidden_edge_is_rejected_by_topology():
    problem, artifact = _fixture()
    edges = {frozenset(edge) for edge in problem.coupling_graph.edges}
    forbidden = next(
        (left, right)
        for index, left in enumerate(problem.accessible_partition)
        for right in problem.accessible_partition[index + 1 :]
        if frozenset((left, right)) not in edges
    )
    candidate = _append_routed(
        artifact,
        GateSpec("CNOT", forbidden),
        GateSpec("CNOT", forbidden),
        update_cnot_resources=True,
    )
    report = verify_recovery(problem, candidate, policy="channel-certified")
    assert report.channel_verified
    assert not report.topology_verified
    assert report.resource_counts_verified
    assert not report.verified


def test_observable_resources_are_certified_but_v1_swap_split_is_not():
    problem, artifact = _fixture()
    false_cnot = replace(
        artifact,
        resources=replace(
            artifact.resources, routed_cnot=artifact.resources.routed_cnot + 1
        ),
    )
    rejected = verify_recovery(problem, false_cnot, policy="channel-certified")
    assert rejected.channel_verified
    assert not rejected.resource_counts_verified
    assert not rejected.verified

    false_swap_claim = replace(
        artifact,
        resources=replace(
            artifact.resources, movement_swaps=artifact.resources.movement_swaps + 999
        ),
    )
    accepted = verify_recovery(problem, false_swap_claim, policy="channel-certified")
    assert accepted.verified
    assert accepted.resource_counts_verified
    assert accepted.swap_accounting_status == "not_certified"
    assert not verify_recovery(problem, false_swap_claim).verified


def test_incorrect_final_order_declaration_is_rejected():
    problem, artifact = _fixture()
    shifted = (*artifact.final_permutation[1:], artifact.final_permutation[0])
    candidate = replace(artifact, final_permutation=shifted)
    report = verify_recovery(problem, candidate, policy="channel-certified")
    assert report.channel_verified
    assert not report.final_order_verified
    assert not report.verified


def test_cli_exposes_policy_and_records_it_in_run_report(tmp_path):
    problem, artifact = _fixture()
    alternative = _append_routed(
        artifact,
        GateSpec("H", (problem.requested_output[0],)),
        GateSpec("H", (problem.requested_output[0],)),
    )
    artifact_path = tmp_path / "alternative.artifact.json"
    report_path = tmp_path / "verify.run-report.json"
    write_artifact(artifact_path, alternative)
    base = [
        sys.executable,
        "-m",
        "hayden_preskill_toy.recovery_cli",
        "verify",
        str(FIXTURES / "a1.problem.json"),
        str(artifact_path),
    ]
    strict = subprocess.run(base, capture_output=True, text=True)
    channel = subprocess.run(
        [*base, "--policy", "channel-certified", "--run-report", str(report_path)],
        capture_output=True,
        text=True,
    )
    assert strict.returncode == RecoveryExitCode.VERIFICATION_REJECTED
    assert channel.returncode == RecoveryExitCode.SUCCESS, channel.stderr
    payload = json.loads(channel.stdout)
    assert payload["verification_policy"] == "channel-certified"
    assert payload["overall_verdict"] == "valid"
    assert payload["channel_verified"] is True
    assert payload["swap_accounting_status"] == "not_certified"
    assert read_run_report(report_path).verification_policy == "channel-certified"


def test_invalid_policy_is_rejected_before_verification():
    problem, artifact = _fixture()
    try:
        verify_recovery(problem, artifact, policy="unknown")
    except ValueError as error:
        assert "unsupported verification policy" in str(error)
    else:
        raise AssertionError("unsupported policy was accepted")
