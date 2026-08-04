"""Layout-driven stabilizer support extraction (no routing, no dense synthesis)."""
from __future__ import annotations
from .layout import SystemLayout
from .simulator import Gate
from .support_code import (
    destabilizers_exhaustive,
    destabilizers_structural,
    support_code_exhaustive,
    support_code_structural,
)


def input_support_code(layout: SystemLayout, scrambler: list[Gate], t: int) -> dict[str, object]:
    """Canonical signed support code for tau_X on layout.X(t)."""
    code = support_code_structural(
        scrambler,
        layout.n_qubits,
        layout.R_register,
        layout.A_register,
        layout.B,
        layout.E,
        t,
    )
    assert code['physical_qubits'] == layout.X(t)
    assert len(code['signed_stabilizer_labels']) == code['independent_stabilizers']
    assert [item[1:] for item in code['signed_stabilizer_labels']] == code['stabilizer_labels']
    assert len(code['logical_X_labels']) == code['logical_qubits']
    assert len(code['logical_Z_labels']) == code['logical_qubits']
    return code


def complete_destabilizers(stabilizers, logical_pairs, n: int):
    """Complete a signed-output support code using binary symplectic data."""
    return destabilizers_structural(stabilizers, logical_pairs, n)


def input_support_code_exhaustive(
    layout: SystemLayout, scrambler: list[Gate], t: int
) -> dict[str, object]:
    return support_code_exhaustive(
        scrambler,
        layout.n_qubits,
        layout.R_register,
        layout.A_register,
        layout.B,
        layout.E,
        t,
    )


def complete_destabilizers_exhaustive(stabilizers, logical_pairs, n: int):
    return destabilizers_exhaustive(stabilizers, logical_pairs, n)
