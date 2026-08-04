#!/usr/bin/env python3
"""Synthesize the stabilizer Choi purification of Petz; no dense-unitary synthesis."""
from __future__ import annotations
import argparse, csv
from pathlib import Path
import numpy as np
import stim
from qiskit import QuantumCircuit, transpile
from qiskit.transpiler import CouplingMap

from hayden_preskill_toy.channels import channel_at_time, petz_entanglement_fidelity, petz_recovery
from hayden_preskill_toy.experiment import random_scrambler


def purified_choi(kraus: tuple[np.ndarray, ...]) -> np.ndarray:
    """|J_P> on A' + input-reference + Kraus environment, with all registers explicit."""
    d_a, d_x = kraus[0].shape; r = len(kraus)
    if r & (r - 1): raise ValueError("Kraus environment must be padded to a qubit power")
    return np.stack(kraus, axis=0).transpose(1, 2, 0).reshape(-1) / np.sqrt(d_x)


def qiskit_from_stim(circuit: stim.Circuit, n: int) -> QuantumCircuit:
    q = QuantumCircuit(n)
    for instruction in circuit:
        targets = [target.value for target in instruction.targets_copy()]
        if instruction.name == "H": q.h(targets)
        elif instruction.name == "S": q.s(targets)
        elif instruction.name == "CX":
            for a, b in zip(targets[::2], targets[1::2]): q.cx(a, b)
        else: raise ValueError(f"unsupported state-preparation gate {instruction.name}")
    return q


def main() -> None:
    p = argparse.ArgumentParser(); p.add_argument("--seed", type=int, default=20260802); p.add_argument("--layers", type=int, default=6); p.add_argument("--t", type=int, default=2)
    args = p.parse_args(); circuit = random_scrambler(np.random.default_rng(args.seed), args.layers)
    channel = channel_at_time(circuit, args.t); kraus, _ = petz_recovery(channel); vector = purified_choi(kraus)
    tableau = stim.Tableau.from_state_vector(vector, endian="little")
    source = tableau.to_circuit(); n = int(round(np.log2(len(vector))))
    qiskit_circuit = qiskit_from_stim(source, n)
    routed = transpile(qiskit_circuit, basis_gates=["h", "s", "cx", "swap"], coupling_map=CouplingMap.from_line(n, bidirectional=True),
                       initial_layout=list(range(n)), layout_method="trivial", routing_method="basic", optimization_level=0, seed_transpiler=7)
    counts = routed.count_ops(); fidelity, _ = petz_entanglement_fidelity(channel)
    row = {"seed": args.seed, "layers": args.layers, "t": args.t, "petz_abstract_fidelity": fidelity,
           "choi_purification_is_stabilizer": True, "stateprep_qubits": n, "stateprep_h": int(counts.get("h", 0)),
           "stateprep_s": int(counts.get("s", 0)), "stateprep_cx": int(counts.get("cx", 0)), "stateprep_swap": int(counts.get("swap", 0)),
           "stateprep_two_qubit_depth": int(routed.depth(lambda x: x.operation.num_qubits == 2)),
           "final_layout": "-".join(map(str, routed.layout.final_index_layout())),
           "decoder_status": "Choi resource compiled; deterministic channel injection not yet synthesized"}
    out = Path("results"); out.mkdir(exist_ok=True); path = out / "local_clifford_petz_resources.csv"; new = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row));
        if new: w.writeheader()
        w.writerow(row)
    print(row)


if __name__ == "__main__": main()
