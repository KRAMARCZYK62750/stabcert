#!/usr/bin/env python3
"""Audit of the former signed-symplectic completion failure (seed 4000)."""
from __future__ import annotations
import csv
from pathlib import Path
import numpy as np

from hayden_preskill_toy.experiment import A, B, E, N_QUBITS, random_scrambler
from hayden_preskill_toy.support_code import support_code


def run() -> list[dict[str, object]]:
    code = support_code(random_scrambler(np.random.default_rng(4000), 9), N_QUBITS, 0, A, B, E, 2)
    # Recorded from the deterministic legacy independent signed basis. Its
    # second element belongs to the same subgroup but is not the second binary
    # vector used by the logical-basis construction.
    legacy = ('-YZXXIX', '+ZXZYYI')
    rows = []
    for i, (binary, signed, old) in enumerate(zip(code['stabilizer_labels'], code['signed_stabilizer_labels'], legacy), 1):
        rows.append({'category': 'input_stabilizer', 'index': i, 'binary_generator': binary,
                     'legacy_signed_representative': old, 'aligned_signed_representative': signed,
                     'diagnostic': 'aligned' if old[1:] == binary else 'legacy representative mismatched binary generator'})
    for i, label in enumerate(code['logical_X_labels'], 1):
        rows.append({'category': 'logical_X', 'index': i, 'binary_generator': label,
                     'legacy_signed_representative': '', 'aligned_signed_representative': '+' + label,
                     'diagnostic': 'canonical logical generator'})
    for i, label in enumerate(code['logical_Z_labels'], 1):
        rows.append({'category': 'logical_Z', 'index': i, 'binary_generator': label,
                     'legacy_signed_representative': '', 'aligned_signed_representative': '+' + label,
                     'diagnostic': 'canonical logical generator'})
    for i, label in enumerate(code['destabilizer_labels'], 1):
        rows.append({'category': 'destabilizer', 'index': i, 'binary_generator': label,
                     'legacy_signed_representative': '', 'aligned_signed_representative': '+' + label,
                     'diagnostic': 'first legacy incompatibility: destabilizer 1 anticommutes with legacy stabilizer 2'})
    return rows


def main() -> None:
    rows = run(); Path('results').mkdir(exist_ok=True)
    with Path('results/compiler_obstruction_seed4000.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    print('wrote results/compiler_obstruction_seed4000.csv')


if __name__ == '__main__': main()
