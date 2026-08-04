"""Immutable register layout for finite Hayden--Preskill toy instances."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class SystemLayout:
    n_message: int = 1
    n_black_hole: int = 4
    n_early_radiation: int | None = None

    def __post_init__(self) -> None:
        if self.n_message < 1:
            raise ValueError('n_message must be positive')
        if self.n_black_hole < 1:
            raise ValueError('n_black_hole must be positive')
        if self.n_early_radiation not in (None, self.n_black_hole):
            raise ValueError('this model pairs each B qubit with one E qubit')

    @property
    def R_register(self) -> tuple[int, ...]: return tuple(range(self.n_message))
    @property
    def A_register(self) -> tuple[int, ...]: return tuple(range(self.n_message, 2 * self.n_message))
    @property
    def R(self) -> int:
        """Backward-compatible one-qubit alias; generic code uses R_register."""
        if self.n_message != 1:
            raise ValueError('layout.R is only defined for n_message=1; use R_register')
        return self.R_register[0]
    @property
    def A(self) -> int:
        """Backward-compatible one-qubit alias; generic code uses A_register."""
        if self.n_message != 1:
            raise ValueError('layout.A is only defined for n_message=1; use A_register')
        return self.A_register[0]
    @property
    def B(self) -> tuple[int, ...]: return tuple(range(2 * self.n_message, 2 * self.n_message + self.n_black_hole))
    @property
    def E(self) -> tuple[int, ...]: return tuple(range(2 * self.n_message + self.n_black_hole, 2 * self.n_message + 2 * self.n_black_hole))
    @property
    def scrambled(self) -> tuple[int, ...]: return (*self.A_register, *self.B)
    @property
    def n_qubits(self) -> int: return 2 * self.n_message + 2 * self.n_black_hole
    def X(self, t: int) -> tuple[int, ...]:
        self._check_t(t); return (*self.E, *self.scrambled[:t])
    def C(self, t: int) -> tuple[int, ...]:
        self._check_t(t); return self.scrambled[t:]
    def chain(self, t: int) -> tuple[int, ...]: return self.X(t)
    def _check_t(self, t: int) -> None:
        if not 0 <= t <= len(self.scrambled): raise ValueError('invalid emission time')
