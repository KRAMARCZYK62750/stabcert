"""Hayden--Preskill instance adapter for the model-independent recovery core.

This is the only new v1 module allowed to know the A/B/E register names.
"""
from __future__ import annotations

from .layout import SystemLayout
from .parametric_graph_routing import coupling_graph
from .recovery_problem import (
    ALLOWED_CLIFFORD_GATES,
    FORMAT_VERSION,
    CertificationThresholds,
    CouplingGraphSpec,
    GateSpec,
    PauliSpec,
    RecoveryProblem,
    RouterParameters,
)
from .simulator import Gate


def hayden_preskill_to_recovery_problem(
    layout: SystemLayout,
    scrambler: list[Gate] | tuple[Gate, ...],
    t: int,
    *,
    architecture: str = "chain",
    router: RouterParameters | None = None,
    metadata: dict[str, str] | None = None,
) -> RecoveryProblem:
    """Translate one existing toy-model instance without changing its science."""
    layout._check_t(t)
    names: dict[int, str] = {}
    for index, wire in enumerate(layout.A_register):
        names[wire] = f"A{index}"
    for index, wire in enumerate(layout.B):
        names[wire] = f"B{index}"
    for index, wire in enumerate(layout.E):
        names[wire] = f"E{index}"
    source_order = tuple(names[wire] for wire in (*layout.A_register, *layout.B, *layout.E))
    channel_input = tuple(names[wire] for wire in layout.A_register)
    ancillas = tuple(names[wire] for wire in (*layout.B, *layout.E))
    ancilla_stabilizers: list[PauliSpec] = []
    # Preserve the historical interleaved Bell-pair generator order.
    for index in range(layout.n_black_hole):
        for pauli_name in ("X", "Z"):
            body = ["I"] * len(ancillas)
            body[index] = body[layout.n_black_hole + index] = pauli_name
            ancilla_stabilizers.append(PauliSpec(ancillas, "".join(body), 0))
    source_gates = tuple(
        GateSpec(
            gate.name,
            (names[gate.a],) if gate.b is None else (names[gate.a], names[gate.b]),
        )
        for gate in scrambler
    )
    accessible = tuple(names[wire] for wire in layout.X(t))
    inaccessible = tuple(names[wire] for wire in layout.C(t))
    integer_graph = coupling_graph(architecture, len(accessible))
    edges = []
    for left, neighbours in enumerate(integer_graph.neighbours):
        for right in neighbours:
            if left < right:
                edges.append(tuple(sorted((accessible[left], accessible[right]))))
    graph = CouplingGraphSpec(
        sites=accessible,
        edges=tuple(sorted(edges)),
        directed=False,
    )
    origin = {
        "adapter": "hayden_preskill_toy",
        "architecture": architecture,
        "emission_time": str(t),
        **(metadata or {}),
    }
    return RecoveryProblem(
        format_version=FORMAT_VERSION,
        qubit_order=source_order,
        channel_input=channel_input,
        source_clifford=source_gates,
        ancilla_qubits=ancillas,
        ancilla_initial_stabilizers=tuple(ancilla_stabilizers),
        accessible_partition=accessible,
        inaccessible_partition=inaccessible,
        requested_output=accessible[: layout.n_message],
        logical_qubit_order=channel_input,
        physical_initial_order=accessible,
        coupling_graph=graph,
        allowed_gates=ALLOWED_CLIFFORD_GATES,
        depth_convention="asap_two_qubit_layers_single_qubit_free",
        router=router or RouterParameters(),
        certification_thresholds=CertificationThresholds("1e-12"),
        metadata=tuple(sorted((str(key), str(value)) for key, value in origin.items())),
    )
