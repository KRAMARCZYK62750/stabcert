"""End-to-end pure-Clifford Petz pipeline with no dense quantum state objects."""
from __future__ import annotations

from dataclasses import dataclass
import time

import stim

from .layout import SystemLayout
from .parametric_certificate import (
    canonical_signed_stabilizer_signature,
    certify_routed_equivalence,
    structural_validation,
)
from .parametric_petz_stabilizer import stabilizer_channel_at_time
from .parametric_routing import route_line, two_qubit_depth
from .parametric_synthesis import signed_dilation
from .simulator import Gate
from .stabilizer import pure_stabilizer_decoupling


@dataclass(frozen=True)
class DenseFreeResult:
    metrics: dict[str, object]
    gates: tuple[Gate, ...]
    routed_gates: tuple[Gate, ...]


def structural_timeline(
    layout: SystemLayout, scrambler: list[Gate] | tuple[Gate, ...]
) -> list[dict[str, object]]:
    rows = []
    for t in range(len(layout.scrambled) + 1):
        started = time.perf_counter()
        channel = stabilizer_channel_at_time(layout, scrambler, t)
        decoupling = pure_stabilizer_decoupling(
            list(scrambler),
            layout.n_qubits,
            layout.R_register,
            layout.A_register,
            layout.B,
            layout.E,
            t,
        )
        support = channel.tau_support
        rows.append(
            {
                "t": t,
                "mutual_information_R_C_bits": decoupling[
                    "mutual_information_bits"
                ],
                "trace_distance_rhoRC_product": decoupling[
                    "trace_distance_product"
                ],
                "petz_fidelity": channel.petz_entanglement_fidelity,
                "support_rank": support.rank,
                "support_logical_qubits": support.logical_qubits,
                "elapsed_seconds": time.perf_counter() - started,
            }
        )
    return rows


def run_structural_instance(
    layout: SystemLayout,
    scrambler: list[Gate] | tuple[Gate, ...],
    t: int,
) -> DenseFreeResult:
    """Synthesize, route and certify Petz using stabilizer objects only."""
    started = time.perf_counter()
    channel = stabilizer_channel_at_time(layout, scrambler, t)
    support = channel.tau_support
    choi = channel.petz_choi_tableau
    gates, encoder, output, rows = signed_dilation(
        layout, channel, list(scrambler), t
    )
    direct = structural_validation(
        layout, channel, list(scrambler), t, gates, encoder, output, rows
    )
    routed = route_line(layout, t, gates)
    routed_metrics = structural_validation(
        layout,
        channel,
        list(scrambler),
        t,
        routed.gates,
        encoder,
        output,
        rows,
    )
    routed_equal = certify_routed_equivalence(layout, t, gates, routed.gates)
    choi_signature = canonical_signed_stabilizer_signature(
        [choi.z_output(index) for index in range(len(choi))]
    )
    metrics = {
        "message_qubits": layout.n_message,
        "alphabet_size": 1 << layout.n_message,
        "t": t,
        "support_rank": support.rank,
        "support_logical_qubits": support.logical_qubits,
        "tau_signed_generator_count": len(support.signed_generators),
        "choi_qubits": len(choi),
        "choi_signed_generator_count": len(choi_signature),
        "petz_fidelity": channel.petz_entanglement_fidelity,
        "direct_fidelity": direct["circuit_fidelity"],
        "routed_fidelity": routed_metrics["circuit_fidelity"],
        "reduced_choi_equal": direct["reduced_choi_equal"],
        "signed_phases_validated": direct[
            "entanglement_phases_match_on_intersection"
        ],
        "logical_depth": two_qubit_depth(gates, layout.n_qubits),
        "logical_cnot": sum(gate.name == "CNOT" for gate in gates),
        "routed_depth": routed.two_qubit_depth,
        "routed_cnot": routed.cnot_count,
        "swap": routed.swap_count,
        "environment_qubits": len(output) - support.logical_qubits,
        "routed_clifford_equal": routed_equal,
        "final_order_restored": routed.final_wire_at_site == layout.chain(t),
        "dense_channel_constructed": False,
        "dense_tau_constructed": False,
        "dense_choi_constructed": False,
        "dense_state_validation_constructed": False,
        "elapsed_seconds": time.perf_counter() - started,
        "validated": bool(direct["validated"])
        and bool(routed_metrics["validated"])
        and routed_equal,
    }
    return DenseFreeResult(metrics, tuple(gates), tuple(routed.gates))
