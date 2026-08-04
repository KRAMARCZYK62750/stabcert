"""Fully stabilizer representation of the pure-Clifford channel and Petz Choi."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import stim

from .layout import SystemLayout
from .parametric_stabilizer import input_support_code
from .simulator import Gate
from .stabilizer import pure_stabilizer_decoupling


def random_stabilizer_scrambler(
    layout: SystemLayout, rng: np.random.Generator, layers: int
) -> list[Gate]:
    """H/S/CNOT scrambler without importing a state-vector channel builder."""
    gates: list[Gate] = []
    qubits = list(layout.scrambled)
    for _ in range(layers):
        for qubit in qubits:
            gates.append(Gate(("H", "S")[int(rng.integers(2))], qubit))
        rng.shuffle(qubits)
        for control, target in zip(qubits[::2], qubits[1::2]):
            gates.append(Gate("CNOT", control, target))
    return gates


def _state_tableau(layout: SystemLayout, scrambler: tuple[Gate, ...]) -> stim.Tableau:
    circuit = stim.Circuit()
    for qubit in range(layout.n_qubits):
        circuit.append("I", [qubit])
    for left, right in (
        *zip(layout.R_register, layout.A_register),
        *zip(layout.B, layout.E),
    ):
        circuit.append("H", [left])
        circuit.append("CX", [left, right])
    for gate in scrambler:
        if gate.name == "CNOT":
            assert gate.b is not None
            circuit.append("CX", [gate.a, gate.b])
        else:
            circuit.append(gate.name, [gate.a])
    return stim.Tableau.from_circuit(circuit)


def _complex_conjugate_reordered(
    pauli: stim.PauliString, order: tuple[int, ...]
) -> stim.PauliString:
    text = str(pauli)
    body = "".join(text[1 + qubit] for qubit in order)
    negative = text[0] == "-"
    negative ^= body.count("Y") % 2 == 1
    return stim.PauliString(("-" if negative else "+") + body)


@dataclass(frozen=True)
class StabilizerSupport:
    physical_qubits: tuple[int, ...]
    signed_generators: tuple[str, ...]
    rank: int
    logical_qubits: int


@dataclass(frozen=True)
class StabilizerChannelData:
    """Channel N_t represented by its pure Clifford Stinespring stabilizer."""

    layout: SystemLayout
    scrambler: tuple[Gate, ...]
    t: int
    output: tuple[int, ...]
    complement: tuple[int, ...]
    input_qubits: int

    @property
    def petz_choi_tableau(self) -> stim.Tableau:
        """Normalized Petz Choi purification, order A'|Ref(X)|E_Petz(C).

        For flat tau_X, the support inverse square root acts as a scalar on the
        global channel Choi state. Vectorization of K_j^dagger then gives the
        complex conjugate of that state, with R relabelled A' and physical
        wires reordered as R|X|C.
        """
        global_tableau = _state_tableau(self.layout, self.scrambler)
        order = (*self.layout.R_register, *self.output, *self.complement)
        stabilizers = [
            _complex_conjugate_reordered(global_tableau.z_output(index), order)
            for index in range(self.layout.n_qubits)
        ]
        return stim.Tableau.from_stabilizers(stabilizers)

    @property
    def tau_support(self) -> StabilizerSupport:
        code = input_support_code(self.layout, list(self.scrambler), self.t)
        return StabilizerSupport(
            physical_qubits=tuple(code["physical_qubits"]),
            signed_generators=tuple(code["signed_stabilizer_labels"]),
            rank=int(code["support_dimension"]),
            logical_qubits=int(code["logical_qubits"]),
        )

    @property
    def petz_entanglement_fidelity(self) -> float:
        decoupling = pure_stabilizer_decoupling(
            list(self.scrambler),
            self.layout.n_qubits,
            self.layout.R_register,
            self.layout.A_register,
            self.layout.B,
            self.layout.E,
            self.t,
        )
        return 2.0 ** (-int(decoupling["mutual_information_bits"]))


def stabilizer_channel_at_time(
    layout: SystemLayout, scrambler: list[Gate] | tuple[Gate, ...], t: int
) -> StabilizerChannelData:
    layout._check_t(t)
    return StabilizerChannelData(
        layout=layout,
        scrambler=tuple(scrambler),
        t=t,
        output=layout.X(t),
        complement=layout.C(t),
        input_qubits=layout.n_message,
    )
