"""Layout-driven channel construction; legacy channels remain untouched."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from .layout import SystemLayout
from .simulator import Gate, X, apply_1q, apply_circuit, bell_pair, zero_state


@dataclass(frozen=True)
class ChannelData:
    kraus: tuple[np.ndarray, ...]
    output: tuple[int, ...]
    complement: tuple[int, ...]


def environment_state(layout: SystemLayout) -> np.ndarray:
    state = zero_state(layout.n_qubits)
    for b, e in zip(layout.B, layout.E): state = bell_pair(state, b, e, layout.n_qubits)
    return state


def random_scrambler(layout: SystemLayout, rng: np.random.Generator, layers: int) -> list[Gate]:
    gates: list[Gate] = []
    qubits = list(layout.scrambled)
    for _ in range(layers):
        for qubit in qubits:
            gates.append(Gate(('H', 'S')[int(rng.integers(2))], qubit))
        rng.shuffle(qubits)
        for control, target in zip(qubits[::2], qubits[1::2]):
            gates.append(Gate('CNOT', control, target))
    return gates


def channel_at_time(layout: SystemLayout, scrambler: list[Gate], t: int) -> ChannelData:
    output, complement = layout.X(t), layout.C(t)
    states=[]; base=environment_state(layout)
    input_dimension = 1 << layout.n_message
    for basis_index in range(input_dimension):
        source = base
        for offset, qubit in enumerate(layout.A_register):
            if basis_index >> (layout.n_message - offset - 1) & 1:
                source = apply_1q(source, X, qubit, layout.n_qubits)
        states.append(apply_circuit(source, scrambler, layout.n_qubits))
    matrices=[]
    for state in states:
        index = tuple(0 if q in layout.R_register else slice(None) for q in range(layout.n_qubits))
        tensor=state.reshape((2,)*layout.n_qubits)[index]
        remaining = tuple(q for q in range(layout.n_qubits) if q not in layout.R_register)
        axes=tuple(remaining.index(q) for q in (*output,*complement))
        matrices.append(np.transpose(tensor,axes).reshape(2**len(output),2**len(complement)))
    kraus=tuple(np.stack([m[:,c] for m in matrices],axis=1) for c in range(2**len(complement)))
    complete=sum((k.conj().T@k for k in kraus),start=np.zeros((input_dimension,input_dimension),complex))
    assert np.linalg.norm(complete-np.eye(input_dimension)) < 1e-10
    return ChannelData(kraus,output,complement)


def channel_at_time_compact(
    layout: SystemLayout, scrambler: list[Gate], t: int
) -> ChannelData:
    """Build the same channel without allocating the untouched R register.

    The scientific register labels in ``ChannelData`` remain those of
    ``SystemLayout``. Only the internal state-vector workspace is compacted to
    A+B+E, which is exactly equivalent because the scrambler never acts on R.
    """
    output, complement = layout.X(t), layout.C(t)
    active = (*layout.A_register, *layout.B, *layout.E)
    local = {wire: index for index, wire in enumerate(active)}
    n_active = len(active)
    base = zero_state(n_active)
    for black_hole, early in zip(layout.B, layout.E):
        base = bell_pair(base, local[black_hole], local[early], n_active)
    compact_scrambler = [
        Gate(
            gate.name,
            local[gate.a],
            None if gate.b is None else local[gate.b],
        )
        for gate in scrambler
    ]
    input_dimension = 1 << layout.n_message
    states = []
    for basis_index in range(input_dimension):
        source = base
        for offset, qubit in enumerate(layout.A_register):
            if basis_index >> (layout.n_message - offset - 1) & 1:
                source = apply_1q(source, X, local[qubit], n_active)
        states.append(apply_circuit(source, compact_scrambler, n_active))
    axes = tuple(local[qubit] for qubit in (*output, *complement))
    matrices = [
        np.transpose(state.reshape((2,) * n_active), axes).reshape(
            2 ** len(output), 2 ** len(complement)
        )
        for state in states
    ]
    kraus = tuple(
        np.stack([matrix[:, column] for matrix in matrices], axis=1)
        for column in range(2 ** len(complement))
    )
    complete = sum(
        (operator.conj().T @ operator for operator in kraus),
        start=np.zeros((input_dimension, input_dimension), dtype=complex),
    )
    if np.linalg.norm(complete - np.eye(input_dimension)) >= 1e-10:
        raise AssertionError("compact channel is not trace preserving")
    return ChannelData(kraus, output, complement)
