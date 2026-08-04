"""Deterministic adversarial qualification cases for the recovery verifier.

This module is intentionally outside the verifier-only package.  It produces
untrusted artifacts and equivalent valid representations; it is never used by
``verify_recovery`` itself.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
from pathlib import Path
from typing import Any

import stim

from .recovery_artifact import (
    CertificateSpec,
    CircuitSpec,
    MetricEntry,
    PetzTargetSpec,
    RecoveryArtifact,
    ResourceSpec,
    TauSupportSpec,
)
from .recovery_problem import CouplingGraphSpec, GateSpec, PauliSpec, RecoveryProblem
from .recovery_routing import route_named_circuit
from .recovery_serialization import (
    artifact_document_hash,
    artifact_from_dict,
    artifact_to_dict,
    read_artifact,
    read_problem,
)
from .recovery_stabilizer import (
    candidate_reduced_choi_generators,
    canonical_signed_signature,
    gate_specs_to_stim,
    pauli_spec_to_stim,
    stim_to_pauli_spec,
    support_code_from_source_choi,
    two_qubit_depth,
)
from .recovery_verify import (
    _entanglement_fidelity,
    _verifier_source_choi,
    verify_recovery,
)


CAMPAIGN_FORMAT_VERSION = "orelia.verifier-adversarial-campaign/v1"
CAMPAIGN_SEED = 20260803

INVALID_CATEGORY_COUNTS: tuple[tuple[str, int, str], ...] = (
    ("semantic_hash", 700, "semantic_problem_hash"),
    ("document_hash", 700, "document_hash"),
    ("topology_claim", 700, "topology"),
    ("tau_signed_generator", 700, "tau_support_signed"),
    ("tau_dimensions", 700, "tau_support_dimensions"),
    ("petz_target_claim", 700, "artifact_target_claim"),
    ("wrong_channel_resealed", 700, "reduced_choi_channel"),
    ("logical_routed_mismatch", 700, "logical_routed_action"),
    ("forbidden_edge_identity", 700, "coupling_graph"),
    ("nondeterministic_route_identity", 700, "deterministic_routing"),
    ("resource_accounting", 700, "resource_accounting"),
    ("final_permutation", 600, "final_permutation"),
    ("certificate_claim", 500, "certificate_signature_claims"),
    ("fidelity_claim", 500, "circuit_entanglement_fidelity"),
    ("malformed_serialized_artifact", 700, "artifact_model_validation"),
)

VALID_CATEGORY_COUNTS: tuple[tuple[str, int], ...] = (
    ("target_environment_gauge", 250),
    ("tau_equivalent_basis", 250),
    ("circuit_environment_gauge", 250),
    ("circuit_identity_rewrite", 250),
    # outside_support_only is deliberately absent: this tuple drives the
    # verifier campaign, whose published counts are 10000/1000. The family
    # discriminates the channel-certified specification and is enrolled by
    # run_channel_certified_adversarial_validation.py, which sources builders
    # through build_valid_case rather than through this tuple.
)


@dataclass(frozen=True)
class AdversarialCase:
    case_id: str
    category: str
    local_index: int
    expected_valid: bool
    expected_first_control: str
    artifact: RecoveryArtifact | None = None
    serialized_artifact: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if (self.artifact is None) == (self.serialized_artifact is None):
            raise ValueError("case must contain exactly one artifact representation")


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    category: str
    local_index: int
    expected_valid: bool
    observed_valid: bool
    expected_first_control: str
    observed_first_control: str
    expected_control_hit: bool
    false_accept: bool
    false_reject: bool
    clean_rejection: bool
    artifact_hash: str
    elapsed_seconds: float
    detail: str


@dataclass(frozen=True)
class CampaignContext:
    problem: RecoveryProblem
    artifact: RecoveryArtifact
    source: stim.Tableau
    code: Any
    target_signature: tuple[str, ...]
    non_edges: tuple[tuple[str, str], ...]
    target_environment_indices: tuple[int, ...]
    circuit_environment_wires: tuple[str, ...]


def load_default_context() -> CampaignContext:
    root = Path(__file__).resolve().parents[1]
    fixture = root / "tests" / "fixtures" / "recovery_v1"
    problem = read_problem(fixture / "a1.problem.json")
    artifact = read_artifact(fixture / "a1.artifact.json")
    source = _verifier_source_choi(problem)
    code = support_code_from_source_choi(
        source,
        len(problem.channel_input),
        problem.qubit_order,
        problem.accessible_partition,
    )
    report = verify_recovery(problem, artifact)
    if not report.verified:
        raise AssertionError("the frozen A=1 campaign fixture must verify")
    edges = {tuple(sorted(edge)) for edge in problem.coupling_graph.edges}
    non_edges = tuple(sorted({
        tuple(sorted((left, right)))
        for left_index, left in enumerate(problem.accessible_partition)
        for right in problem.accessible_partition[left_index + 1 :]
        if tuple(sorted((left, right))) not in edges
    }))
    target_environment_indices = tuple(
        index
        for index, wire in enumerate(artifact.petz_target.choi_qubit_order)
        if wire.startswith("env:")
    )
    circuit_environment_wires = tuple(
        wire for wire in problem.accessible_partition if wire not in problem.requested_output
    )
    if not non_edges or not target_environment_indices or not circuit_environment_wires:
        raise AssertionError("campaign fixture lacks a required adversarial degree of freedom")
    return CampaignContext(
        problem=problem,
        artifact=artifact,
        source=source,
        code=code,
        target_signature=report.target_reduced_choi_signature,
        non_edges=non_edges,
        target_environment_indices=target_environment_indices,
        circuit_environment_wires=circuit_environment_wires,
    )


def _digest(tag: str, index: int, nonce: int = 0) -> bytes:
    return hashlib.sha256(
        f"{CAMPAIGN_FORMAT_VERSION}:{CAMPAIGN_SEED}:{tag}:{index}:{nonce}".encode()
    ).digest()


def _different_hash(tag: str, index: int, original: str) -> str:
    candidate = hashlib.sha256(_digest(tag, index)).hexdigest()
    if candidate == original:
        candidate = hashlib.sha256(candidate.encode()).hexdigest()
    return candidate


def _identity_suffix(wires: tuple[str, ...], tag: str, index: int, units: int = 5) -> tuple[GateSpec, ...]:
    data = _digest(tag, index)
    result: list[GateSpec] = []
    for offset in range(units):
        wire = wires[data[2 * offset] % len(wires)]
        kind = data[2 * offset + 1] % 3
        if kind == 0:
            result.extend((GateSpec("H", (wire,)),) * 2)
        elif kind == 1:
            result.extend((GateSpec("X", (wire,)),) * 2)
        else:
            result.extend((GateSpec("S", (wire,)),) * 4)
    return tuple(result)


def _clifford_circuit(
    width: int,
    positions: tuple[int, ...],
    tag: str,
    index: int,
    *,
    length: int = 12,
) -> stim.Circuit:
    if not positions:
        raise ValueError("Clifford mutation needs at least one wire")
    circuit = stim.Circuit()
    for qubit in range(width):
        circuit.append("I", [qubit])
    for step in range(length):
        data = _digest(tag, index, step)
        if len(positions) > 1 and data[0] % 4 == 0:
            left = positions[data[1] % len(positions)]
            right = positions[data[2] % len(positions)]
            if left == right:
                right = positions[(positions.index(right) + 1) % len(positions)]
            circuit.append("CX", [left, right])
        else:
            circuit.append(("H", "S", "X", "Z")[data[0] % 4], [positions[data[1] % len(positions)]])
    return circuit


def _conjugated_specs(specs, qubit_order: tuple[str, ...], circuit: stim.Circuit):
    return tuple(
        stim_to_pauli_spec(pauli_spec_to_stim(spec).after(circuit), qubit_order)
        for spec in specs
    )


def _target_environment_gauge(ctx: CampaignContext, index: int, *, corrupt_output: bool) -> RecoveryArtifact:
    order = ctx.artifact.petz_target.choi_qubit_order
    circuit = _clifford_circuit(
        len(order), ctx.target_environment_indices, "target-env", index, length=14
    )
    if corrupt_output:
        prefix = stim.Circuit()
        for qubit in range(len(order)):
            prefix.append("I", [qubit])
        prefix.append("X", [0])
        prefix += circuit
        circuit = prefix
    generators = _conjugated_specs(
        ctx.artifact.petz_target.signed_generators, order, circuit
    )
    return replace(
        ctx.artifact,
        petz_target=PetzTargetSpec(order, generators),
    )


def _tau_invalid(ctx: CampaignContext, index: int) -> RecoveryArtifact:
    original = [pauli_spec_to_stim(item) for item in ctx.artifact.tau_support.signed_generators]
    original_signature = canonical_signed_signature(original)
    width = len(ctx.problem.accessible_partition)
    for nonce in range(128):
        circuit = _clifford_circuit(
            width, tuple(range(width)), "tau-invalid", index + 10_000 * nonce, length=10
        )
        generators = _conjugated_specs(
            ctx.artifact.tau_support.signed_generators,
            ctx.problem.accessible_partition,
            circuit,
        )
        if canonical_signed_signature([pauli_spec_to_stim(item) for item in generators]) != original_signature:
            return replace(
                ctx.artifact,
                tau_support=replace(ctx.artifact.tau_support, signed_generators=generators),
            )
    raise AssertionError("failed to construct a distinct tau stabilizer subgroup")


def _tau_equivalent_basis(ctx: CampaignContext, index: int) -> RecoveryArtifact:
    generators = [pauli_spec_to_stim(item) for item in ctx.artifact.tau_support.signed_generators]
    if len(generators) < 2:
        raise AssertionError("campaign fixture needs at least two tau generators")
    choices = (
        (generators[0], generators[1]),
        (generators[1], generators[0]),
        (generators[0] * generators[1], generators[1]),
        (generators[0], generators[0] * generators[1]),
        (generators[1], generators[0] * generators[1]),
        (generators[0] * generators[1], generators[0]),
    )
    selected = choices[index % len(choices)] + tuple(generators[2:])
    specs = tuple(
        stim_to_pauli_spec(item, ctx.problem.accessible_partition) for item in selected
    )
    artifact = replace(
        ctx.artifact,
        tau_support=replace(ctx.artifact.tau_support, signed_generators=specs),
    )
    # An independent environment gauge makes every block exercise both accepted
    # equivalences while leaving the reduced channel unchanged.
    gauged = _target_environment_gauge(ctx, index + 50_000, corrupt_output=False)
    return replace(artifact, petz_target=gauged.petz_target)


def _set_fidelity_metric(artifact: RecoveryArtifact, value: float) -> RecoveryArtifact:
    metrics = tuple(
        MetricEntry(item.name, format(value, ".17g"), item.unit)
        if item.name == "circuit_entanglement_fidelity"
        else item
        for item in artifact.metrics
    )
    return replace(artifact, metrics=metrics)


def _claimed_logical_signature(ctx: CampaignContext, gates: tuple[GateSpec, ...]) -> tuple[str, ...]:
    circuit = gate_specs_to_stim(gates, ctx.problem.accessible_partition)
    environment_width = ctx.code.logical_qubits - len(ctx.problem.requested_output)
    environment = tuple(
        wire
        for wire in ctx.problem.accessible_partition
        if wire not in ctx.problem.requested_output
    )[:environment_width]
    output_wires = (*ctx.problem.requested_output, *environment)
    positions = tuple(ctx.problem.accessible_partition.index(wire) for wire in output_wires)
    result: list[str] = []
    for logical_x, logical_z in zip(ctx.code.logical_x_labels, ctx.code.logical_z_labels):
        for label in (logical_x, logical_z):
            transformed = stim.PauliString(label).after(circuit)
            full = stim_to_pauli_spec(transformed, ctx.problem.accessible_partition)
            local = PauliSpec(
                output_wires,
                "".join(full.operators[position] for position in positions),
                full.phase_exponent_mod_4,
            )
            result.append(str(pauli_spec_to_stim(local)))
    return tuple(result)


def _with_rerouted_logical(
    ctx: CampaignContext,
    logical_gates: tuple[GateSpec, ...],
    *,
    compiler_declared_valid: bool,
) -> RecoveryArtifact:
    routed = route_named_circuit(logical_gates, ctx.problem.coupling_graph, ctx.problem.router)
    candidate = candidate_reduced_choi_generators(
        ctx.problem.accessible_partition,
        ctx.problem.requested_output,
        ctx.code,
        routed.gates,
    )
    candidate_signature = canonical_signed_signature(candidate)
    fidelity = _entanglement_fidelity(ctx.problem, ctx.source, routed.gates)
    artifact = replace(
        ctx.artifact,
        logical_circuit=CircuitSpec(ctx.problem.accessible_partition, logical_gates),
        routed_circuit=CircuitSpec(ctx.problem.accessible_partition, routed.gates),
        final_permutation=routed.final_wire_at_site,
        resources=ResourceSpec(
            logical_depth=two_qubit_depth(logical_gates),
            routed_depth=routed.two_qubit_depth,
            logical_cnot=sum(gate.operation == "CNOT" for gate in logical_gates),
            routed_cnot=routed.cnot_count,
            movement_swaps=routed.movement_swaps,
            restoration_swaps=routed.restoration_swaps,
            environment_qubits=ctx.artifact.resources.environment_qubits,
        ),
        certificate=replace(
            ctx.artifact.certificate,
            candidate_reduced_choi_signature=candidate_signature,
            logical_action_signature=_claimed_logical_signature(ctx, logical_gates),
            compiler_declared_valid=compiler_declared_valid,
        ),
    )
    return _set_fidelity_metric(artifact, fidelity)


def _wrong_channel(ctx: CampaignContext, index: int) -> RecoveryArtifact:
    logical = (
        *ctx.artifact.logical_circuit.gates,
        *_identity_suffix(ctx.problem.accessible_partition, "wrong-channel", index),
        GateSpec("X", (ctx.problem.requested_output[0],)),
    )
    return _with_rerouted_logical(ctx, tuple(logical), compiler_declared_valid=False)


def _valid_circuit_rewrite(ctx: CampaignContext, index: int, *, environment_gauge: bool) -> RecoveryArtifact:
    logical = list(ctx.artifact.logical_circuit.gates)
    logical.extend(_identity_suffix(ctx.problem.accessible_partition, "valid-rewrite", index))
    if environment_gauge:
        data = _digest("valid-circuit-environment", index)
        wire = ctx.circuit_environment_wires[data[0] % len(ctx.circuit_environment_wires)]
        logical.append(GateSpec(("H", "S", "X", "Z")[data[1] % 4], (wire,)))
    return _with_rerouted_logical(ctx, tuple(logical), compiler_declared_valid=True)


def _outside_support_only(ctx: CampaignContext, index: int) -> RecoveryArtifact:
    """A circuit differing from the reference only outside supp(tau_X).

    Prefixing the circuit with an element of the stabilizer group of tau_X
    leaves its action on the code subspace unchanged -- every state there is a
    +1 eigenstate -- while changing the total unitary.  A verifier comparing
    the channel on the code subspace must accept; one comparing the total
    channel must reject.  Without this family nothing in the campaign
    distinguishes the two specifications, and the counts are silent on which
    one is implemented.
    """
    generators = [pauli_spec_to_stim(item) for item in ctx.artifact.tau_support.signed_generators]
    if not generators:
        raise AssertionError("campaign fixture has no tau support generator")
    usable = min(len(generators), 10)
    mask = (index % ((1 << usable) - 1)) + 1
    element = stim.PauliString("+" + "_" * len(generators[0]))
    for position in range(usable):
        if (mask >> position) & 1:
            element *= generators[position]
    body = str(element)[-len(element) :]
    prefix: list[GateSpec] = []
    for wire, letter in zip(ctx.problem.accessible_partition, body):
        # X and Z generate the Pauli up to a global phase, which a channel drops.
        if letter in ("X", "Y"):
            prefix.append(GateSpec("X", (wire,)))
        if letter in ("Z", "Y"):
            prefix.append(GateSpec("Z", (wire,)))
    if not prefix:
        raise AssertionError("independent generators cannot multiply to the identity")
    logical = (
        *prefix,
        *ctx.artifact.logical_circuit.gates,
        *_identity_suffix(ctx.problem.accessible_partition, "outside-support", index),
    )
    return _with_rerouted_logical(ctx, logical, compiler_declared_valid=True)


def _topology_claim(ctx: CampaignContext, index: int) -> RecoveryArtifact:
    selected = {
        edge for offset, edge in enumerate(ctx.non_edges) if ((index + 1) >> offset) & 1
    }
    if not selected:
        selected.add(ctx.non_edges[0])
    edges = tuple(sorted({*ctx.problem.coupling_graph.edges, *selected}))
    topology = CouplingGraphSpec(
        sites=ctx.problem.coupling_graph.sites,
        edges=edges,
        directed=False,
        native_two_qubit_gate="CNOT",
    )
    return replace(ctx.artifact, topology=topology)


def _logical_routed_mismatch(ctx: CampaignContext, index: int) -> RecoveryArtifact:
    data = _digest("logical-routed", index)
    wire = ctx.circuit_environment_wires[data[0] % len(ctx.circuit_environment_wires)]
    operation = ("H", "S", "X", "Z")[data[1] % 4]
    gates = (
        *ctx.artifact.routed_circuit.gates,
        *_identity_suffix(ctx.circuit_environment_wires, "logical-routed-id", index),
        GateSpec(operation, (wire,)),
    )
    return replace(
        ctx.artifact,
        routed_circuit=CircuitSpec(ctx.problem.accessible_partition, tuple(gates)),
    )


def _forbidden_edge_identity(ctx: CampaignContext, index: int) -> RecoveryArtifact:
    result = list(ctx.artifact.routed_circuit.gates)
    data = _digest("forbidden-edge", index)
    for offset in range(1 + data[0] % 4):
        edge = ctx.non_edges[data[offset + 1] % len(ctx.non_edges)]
        result.extend((GateSpec("CNOT", edge), GateSpec("CNOT", edge)))
    return replace(
        ctx.artifact,
        routed_circuit=CircuitSpec(ctx.problem.accessible_partition, tuple(result)),
    )


def _nondeterministic_identity(ctx: CampaignContext, index: int) -> RecoveryArtifact:
    gates = (
        *ctx.artifact.routed_circuit.gates,
        *_identity_suffix(ctx.problem.accessible_partition, "route-identity", index, units=8),
    )
    return replace(
        ctx.artifact,
        routed_circuit=CircuitSpec(ctx.problem.accessible_partition, tuple(gates)),
    )


def _resource_claim(ctx: CampaignContext, index: int) -> RecoveryArtifact:
    fields = (
        "logical_depth",
        "routed_depth",
        "logical_cnot",
        "routed_cnot",
        "movement_swaps",
        "restoration_swaps",
        "environment_qubits",
    )
    field = fields[index % len(fields)]
    values = {
        name: getattr(ctx.artifact.resources, name) for name in fields
    }
    values[field] += 1 + index // len(fields)
    return replace(ctx.artifact, resources=ResourceSpec(**values))


def _permutation(ctx: CampaignContext, index: int) -> RecoveryArtifact:
    remaining = list(ctx.problem.physical_initial_order)
    value = index + 1
    result: list[str] = []
    while remaining:
        value, position = divmod(value, len(remaining))
        result.append(remaining.pop(position))
    permutation = tuple(result)
    if permutation == ctx.problem.physical_initial_order:
        permutation = (*permutation[1:], permutation[0])
    return replace(ctx.artifact, final_permutation=permutation)


def _certificate_claim(ctx: CampaignContext, index: int) -> RecoveryArtifact:
    subtype = index % 3
    marker = f"invalid-certificate-{index:04d}"
    certificate = ctx.artifact.certificate
    if subtype == 0:
        certificate = replace(
            certificate,
            target_reduced_choi_signature=(*certificate.target_reduced_choi_signature, marker),
        )
    elif subtype == 1:
        certificate = replace(
            certificate,
            candidate_reduced_choi_signature=(*certificate.candidate_reduced_choi_signature, marker),
        )
    else:
        certificate = replace(
            certificate,
            logical_action_signature=(*certificate.logical_action_signature, marker),
        )
    return replace(ctx.artifact, certificate=certificate)


def _fidelity_claim(ctx: CampaignContext, index: int) -> RecoveryArtifact:
    return _set_fidelity_metric(ctx.artifact, (index + 1) / 1001.0)


def _malformed_serialized(ctx: CampaignContext, index: int) -> dict[str, Any]:
    value = deepcopy(artifact_to_dict(ctx.artifact))
    subtype = index % 5
    if subtype == 0:
        value[f"unknown_top_level_{index}"] = "must be rejected"
    elif subtype == 1:
        value["tau_support"][f"unknown_nested_{index}"] = True
    elif subtype == 2:
        value.pop("certificate")
    elif subtype == 3:
        value["format_version"] = f"orelia.recovery-artifact/corrupt-{index}"
    else:
        value["tau_support"]["signed_generators"][0]["phase_exponent_mod_4"] = 1
    return value


def build_invalid_case(ctx: CampaignContext, category: str, index: int) -> AdversarialCase:
    expected = next(control for name, _, control in INVALID_CATEGORY_COUNTS if name == category)
    base = ctx.artifact
    serialized = None
    if category == "semantic_hash":
        artifact = replace(
            base,
            source_semantic_problem_hash=_different_hash(category, index, base.source_semantic_problem_hash),
        )
    elif category == "document_hash":
        artifact = replace(
            base,
            source_document_hash=_different_hash(category, index, base.source_document_hash),
        )
    elif category == "topology_claim":
        artifact = _topology_claim(ctx, index)
    elif category == "tau_signed_generator":
        artifact = _tau_invalid(ctx, index)
    elif category == "tau_dimensions":
        logical = (base.tau_support.logical_qubits + 1 + index) % (len(ctx.problem.accessible_partition) + 1)
        if logical == base.tau_support.logical_qubits:
            logical = (logical + 1) % (len(ctx.problem.accessible_partition) + 1)
        artifact = replace(
            base,
            tau_support=replace(base.tau_support, logical_qubits=logical, support_rank=1 << logical),
        )
    elif category == "petz_target_claim":
        artifact = _target_environment_gauge(ctx, index, corrupt_output=True)
    elif category == "wrong_channel_resealed":
        artifact = _wrong_channel(ctx, index)
    elif category == "logical_routed_mismatch":
        artifact = _logical_routed_mismatch(ctx, index)
    elif category == "forbidden_edge_identity":
        artifact = _forbidden_edge_identity(ctx, index)
    elif category == "nondeterministic_route_identity":
        artifact = _nondeterministic_identity(ctx, index)
    elif category == "resource_accounting":
        artifact = _resource_claim(ctx, index)
    elif category == "final_permutation":
        artifact = _permutation(ctx, index)
    elif category == "certificate_claim":
        artifact = _certificate_claim(ctx, index)
    elif category == "fidelity_claim":
        artifact = _fidelity_claim(ctx, index)
    elif category == "malformed_serialized_artifact":
        artifact = None
        serialized = _malformed_serialized(ctx, index)
    else:
        raise KeyError(category)
    return AdversarialCase(
        case_id=f"invalid-{category}-{index:04d}",
        category=category,
        local_index=index,
        expected_valid=False,
        expected_first_control=expected,
        artifact=artifact,
        serialized_artifact=serialized,
    )


def build_valid_case(ctx: CampaignContext, category: str, index: int) -> AdversarialCase:
    if category == "target_environment_gauge":
        artifact = _target_environment_gauge(ctx, index, corrupt_output=False)
    elif category == "tau_equivalent_basis":
        artifact = _tau_equivalent_basis(ctx, index)
    elif category == "circuit_environment_gauge":
        artifact = _valid_circuit_rewrite(ctx, index, environment_gauge=True)
    elif category == "circuit_identity_rewrite":
        artifact = _valid_circuit_rewrite(ctx, index, environment_gauge=False)
    elif category == "outside_support_only":
        artifact = _outside_support_only(ctx, index)
    else:
        raise KeyError(category)
    return AdversarialCase(
        case_id=f"valid-{category}-{index:04d}",
        category=category,
        local_index=index,
        expected_valid=True,
        expected_first_control="none",
        artifact=artifact,
    )


def iter_campaign_cases(ctx: CampaignContext):
    for category, count, _ in INVALID_CATEGORY_COUNTS:
        for index in range(count):
            yield build_invalid_case(ctx, category, index)
    for category, count in VALID_CATEGORY_COUNTS:
        for index in range(count):
            yield build_valid_case(ctx, category, index)


def evaluate_case(ctx: CampaignContext, case: AdversarialCase) -> CaseResult:
    import time

    started = time.perf_counter()
    detail = ""
    clean_rejection = True
    try:
        if case.serialized_artifact is not None:
            try:
                artifact = artifact_from_dict(deepcopy(case.serialized_artifact))
            except (KeyError, TypeError, ValueError) as error:
                observed_valid = False
                first = "artifact_model_validation"
                artifact_hash = hashlib.sha256(
                    repr(case.serialized_artifact).encode("utf-8")
                ).hexdigest()
                detail = f"{type(error).__name__}: {error}"
            else:
                report = verify_recovery(ctx.problem, artifact)
                observed_valid = report.verified
                failed = next((item for item in report.checks if not item.passed), None)
                first = "none" if failed is None else failed.name
                artifact_hash = artifact_document_hash(artifact)
                detail = "all checks passed" if failed is None else failed.detail
        else:
            assert case.artifact is not None
            report = verify_recovery(ctx.problem, case.artifact)
            observed_valid = report.verified
            failed = next((item for item in report.checks if not item.passed), None)
            first = "none" if failed is None else failed.name
            artifact_hash = artifact_document_hash(case.artifact)
            detail = "all checks passed" if failed is None else failed.detail
    except Exception as error:  # A verifier exception is not a clean rejection.
        observed_valid = False
        first = f"verification_exception:{type(error).__name__}"
        artifact_hash = ""
        detail = str(error)
        clean_rejection = False
    expected_control_hit = first == case.expected_first_control
    return CaseResult(
        case_id=case.case_id,
        category=case.category,
        local_index=case.local_index,
        expected_valid=case.expected_valid,
        observed_valid=observed_valid,
        expected_first_control=case.expected_first_control,
        observed_first_control=first,
        expected_control_hit=expected_control_hit,
        false_accept=not case.expected_valid and observed_valid,
        false_reject=case.expected_valid and not observed_valid,
        clean_rejection=clean_rejection,
        artifact_hash=artifact_hash,
        elapsed_seconds=time.perf_counter() - started,
        detail=detail,
    )


def campaign_case_count() -> tuple[int, int]:
    return (
        sum(count for _, count, _ in INVALID_CATEGORY_COUNTS),
        sum(count for _, count in VALID_CATEGORY_COUNTS),
    )
