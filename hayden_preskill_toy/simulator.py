"""Small state-vector simulator for a fixed, ten-qubit toy channel."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

H = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)
S = np.array([[1, 0], [0, 1j]], dtype=complex)
SDG = S.conj().T
X = np.array([[0, 1], [1, 0]], dtype=complex)


@dataclass(frozen=True)
class Gate:
    name: str
    a: int
    b: int | None = None


def zero_state(n: int) -> np.ndarray:
    state = np.zeros(2**n, dtype=complex)
    state[0] = 1
    return state


def apply_1q(state: np.ndarray, gate: np.ndarray, q: int, n: int) -> np.ndarray:
    tensor = state.reshape((2,) * n)
    tensor = np.moveaxis(tensor, q, 0)
    tensor = np.tensordot(gate, tensor, axes=(1, 0))
    return np.moveaxis(tensor, 0, q).reshape(-1)


def apply_cnot(state: np.ndarray, control: int, target: int, n: int) -> np.ndarray:
    tensor = state.reshape((2,) * n)
    tensor = np.moveaxis(tensor, (control, target), (0, 1)).copy()
    tensor[1] = tensor[1, ::-1]
    return np.moveaxis(tensor, (0, 1), (control, target)).reshape(-1)


def apply_gate(state: np.ndarray, op: Gate, n: int, inverse: bool = False) -> np.ndarray:
    if op.name == "H":
        return apply_1q(state, H, op.a, n)
    if op.name == "S":
        return apply_1q(state, SDG if inverse else S, op.a, n)
    if op.name == "X":
        return apply_1q(state, X, op.a, n)
    if op.name == "CNOT":
        assert op.b is not None
        return apply_cnot(state, op.a, op.b, n)
    raise ValueError(f"unknown gate {op.name}")


def apply_circuit(state: np.ndarray, circuit: list[Gate], n: int, inverse: bool = False) -> np.ndarray:
    gates = reversed(circuit) if inverse else circuit
    for gate in gates:
        state = apply_gate(state, gate, n, inverse=inverse)
    return state


def apply_unitary(state: np.ndarray, unitary: np.ndarray, qubits: tuple[int, ...], n: int) -> np.ndarray:
    """Apply a dense unitary whose tensor order follows the supplied qubit order."""
    rest = tuple(q for q in range(n) if q not in qubits)
    view = np.transpose(state.reshape((2,) * n), (*qubits, *rest)).reshape(2**len(qubits), -1)
    return np.transpose((unitary @ view).reshape((2,) * n), np.argsort((*qubits, *rest))).reshape(-1)


def bell_pair(state: np.ndarray, a: int, b: int, n: int) -> np.ndarray:
    return apply_cnot(apply_1q(state, H, a, n), a, b, n)


def bell_fidelity(state: np.ndarray, r: int, output: int, n: int) -> float:
    """Fidelity of rho_(r,output) with |Phi+>; exact partial trace contraction."""
    tensor = state.reshape((2,) * n)
    rest = [q for q in range(n) if q not in (r, output)]
    view = np.transpose(tensor, (r, output, *rest)).reshape(4, -1)
    bell = np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2)
    return float(np.real(np.vdot(bell, view @ view.conj().T @ bell)))
