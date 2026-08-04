#!/usr/bin/env python3
"""Create the three immutable v1 recovery-core regression fixtures."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_architecture_routing import route_graph_lookahead
from hayden_preskill_toy.parametric_graph_routing import coupling_graph
from hayden_preskill_toy.parametric_petz_stabilizer import (
    random_stabilizer_scrambler,
    stabilizer_channel_at_time,
)
from hayden_preskill_toy.parametric_routing import two_qubit_depth
from hayden_preskill_toy.parametric_synthesis import signed_dilation
from hayden_preskill_toy.recovery_compile import compile_recovery
from hayden_preskill_toy.recovery_hayden_preskill_adapter import (
    hayden_preskill_to_recovery_problem,
)
from hayden_preskill_toy.recovery_problem import GateSpec, RouterParameters
from hayden_preskill_toy.recovery_serialization import (
    artifact_document_hash,
    canonical_json_bytes,
    circuit_hash,
    problem_document_hash,
    semantic_problem_hash,
    write_artifact,
    write_problem,
)
from hayden_preskill_toy.recovery_verify import verify_recovery


SEED = 20260802
SCRAMBLE_DEPTH = 6
CASES = (
    ("a1", 1, 2, "chain"),
    ("a8", 8, 8, "chain"),
    ("a12", 12, 14, "grid_2d"),
)


def _named_gate(gate, names: dict[int, str]) -> GateSpec:
    return GateSpec(
        gate.name,
        (names[gate.a],) if gate.b is None else (names[gate.a], names[gate.b]),
    )


def build_fixtures(output: Path) -> list[dict[str, object]]:
    output.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []
    for case_id, message, t, architecture in CASES:
        layout = SystemLayout(n_message=message, n_black_hole=4)
        scrambler = random_stabilizer_scrambler(
            layout, np.random.default_rng(SEED), SCRAMBLE_DEPTH
        )
        problem = hayden_preskill_to_recovery_problem(
            layout,
            scrambler,
            t,
            architecture=architecture,
            router=RouterParameters(lookahead=16, candidate_budget=64),
            metadata={
                "fixture_id": case_id,
                "seed": str(SEED),
                "scramble_depth": str(SCRAMBLE_DEPTH),
            },
        )
        artifact = compile_recovery(problem)
        report = verify_recovery(problem, artifact)
        if not report.verified:
            raise AssertionError((case_id, report))

        channel = stabilizer_channel_at_time(layout, scrambler, t)
        old_gates, _, old_output, _ = signed_dilation(layout, channel, scrambler, t)
        old_route = route_graph_lookahead(
            layout,
            t,
            old_gates,
            coupling_graph(architecture, len(layout.X(t))),
            lookahead=16,
            candidate_budget=64,
        )
        names = {}
        for index, wire in enumerate(layout.A_register):
            names[wire] = f"A{index}"
        for index, wire in enumerate(layout.B):
            names[wire] = f"B{index}"
        for index, wire in enumerate(layout.E):
            names[wire] = f"E{index}"
        old_named = tuple(_named_gate(gate, names) for gate in old_gates)
        old_routed_named = tuple(_named_gate(gate, names) for gate in old_route.gates)
        expected_resources = {
            "logical_depth": two_qubit_depth(old_gates, layout.n_qubits),
            "routed_depth": old_route.two_qubit_depth,
            "logical_cnot": sum(gate.name == "CNOT" for gate in old_gates),
            "routed_cnot": old_route.cnot_count,
            "movement_swaps": old_route.movement_swap_count,
            "restoration_swaps": old_route.restoration_swap_count,
            "environment_qubits": len(old_output) - channel.tau_support.logical_qubits,
        }
        actual_resources = {
            key: getattr(artifact.resources, key) for key in expected_resources
        }
        discrete_regression = (
            artifact.logical_circuit.gates == old_named
            and artifact.routed_circuit.gates == old_routed_named
            and actual_resources == expected_resources
            and artifact.final_permutation
            == tuple(names[wire] for wire in old_route.final_wire_at_site)
        )
        if not discrete_regression:
            raise AssertionError((case_id, expected_resources, actual_resources))

        problem_name = f"{case_id}.problem.json"
        artifact_name = f"{case_id}.artifact.json"
        write_problem(output / problem_name, problem)
        write_artifact(output / artifact_name, artifact)
        manifest.append(
            {
                "case_id": case_id,
                "message_qubits": message,
                "black_hole_qubits": 4,
                "seed": SEED,
                "scramble_depth": SCRAMBLE_DEPTH,
                "emission_time": t,
                "architecture": architecture,
                "router_algorithm": problem.router.algorithm,
                "lookahead": problem.router.lookahead,
                "candidate_budget": problem.router.candidate_budget,
                "problem_file": problem_name,
                "artifact_file": artifact_name,
                "semantic_problem_hash": semantic_problem_hash(problem),
                "problem_document_hash": problem_document_hash(problem),
                "artifact_document_hash": artifact_document_hash(artifact),
                "logical_circuit_hash": circuit_hash(artifact.logical_circuit),
                "routed_circuit_hash": circuit_hash(artifact.routed_circuit),
                "resources": actual_resources,
                "compiler_certificate": artifact.certificate.compiler_declared_valid,
                "independent_verification": report.verified,
                "historical_discrete_regression": discrete_regression,
            }
        )
    (output / "manifest.json").write_bytes(canonical_json_bytes(manifest) + b"\n")
    return manifest


def main() -> None:
    manifest = build_fixtures(Path("tests/fixtures/recovery_v1"))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
