#!/usr/bin/env python3
"""Exhaustive audit of all 11,520 two-qubit Cliffords (A+B, modulo phase)."""
from __future__ import annotations
from collections import deque
import csv
from pathlib import Path
import numpy as np

from hayden_preskill_toy.channels import ChannelData, petz_entanglement_fidelity
from hayden_preskill_toy.simulator import Gate, X, apply_1q, apply_circuit, bell_pair, zero_state
from hayden_preskill_toy.stabilizer import diagnostics

N, R, A, B, E = 4, 0, 1, (2,), (3,)
H = np.array([[1, 1], [1, -1]], complex) / np.sqrt(2); S = np.diag([1, 1j])
C01 = np.array([[1,0,0,0],[0,1,0,0],[0,0,0,1],[0,0,1,0]], complex)
C10 = np.array([[1,0,0,0],[0,0,0,1],[0,0,1,0],[0,1,0,0]], complex)
GENERATORS = [(np.kron(H, np.eye(2)), Gate("H", A)), (np.kron(S, np.eye(2)), Gate("S", A)),
              (np.kron(np.eye(2), H), Gate("H", B[0])), (np.kron(np.eye(2), S), Gate("S", B[0])),
              (C01, Gate("CNOT", A, B[0])), (C10, Gate("CNOT", B[0], A))]


def key(u):
    pivot = next(x for x in u.flat if abs(x) > 1e-10); v = u * np.exp(-1j * np.angle(pivot))
    return tuple(np.round(v.real, 10).flat) + tuple(np.round(v.imag, 10).flat)


def cliffords():
    identity = np.eye(4, dtype=complex); seen = {key(identity): []}; queue = deque([(identity, [])])
    while queue:
        u, circuit = queue.popleft()
        for matrix, gate in GENERATORS:
            new = matrix @ u; candidate = circuit + [gate]; marker = key(new)
            if marker not in seen:
                seen[marker] = candidate; queue.append((new, candidate))
    return list(seen.values())


def environment(): return bell_pair(zero_state(N), B[0], E[0], N)

def case_metrics(state, t):
    c=(A,*B)[t:]
    def reduced(keep):
        rest=tuple(q for q in range(N) if q not in keep)
        v=np.transpose(state.reshape((2,)*N),(*keep,*rest)).reshape(2**len(keep),-1); return v@v.conj().T
    rc,rho_r=reduced((R,*c)),reduced((R,)); rho_c=reduced(c) if c else np.ones((1,1),complex)
    def entropy(rho):
        values=np.linalg.eigvalsh(rho); values=values[values>1e-12]; return float(-sum(values*np.log2(values)))
    return {'mutual_information_bits':entropy(rho_r)+entropy(rho_c)-entropy(rc),
            'rank_rho_RC':int(sum(np.linalg.eigvalsh(rc)>1e-12)), 'rank_rho_C':int(sum(np.linalg.eigvalsh(rho_c)>1e-12))}


def channel(circuit, t):
    slots = (A, *B); out, comp = (*E, *slots[:t]), slots[t:]; columns=[]
    for bit in range(2):
        state = environment() if bit == 0 else apply_1q(environment(), X, A, N)
        state = apply_circuit(state, circuit, N); tensor = state.reshape((2,)*N)[0]
        axes = tuple(q-1 for q in (*out,*comp)); columns.append(np.transpose(tensor, axes).reshape(2**len(out),2**len(comp)))
    return ChannelData(tuple(np.stack([m[:,c] for m in columns],axis=1) for c in range(2**len(comp))),out,comp)


def main():
    circuits = cliffords(); assert len(circuits) == 11520, len(circuits)
    rows=[]
    for index, circuit in enumerate(circuits):
        state=apply_circuit(bell_pair(environment(),R,A,N), circuit, N)
        for t in (1,2):
            metrics=case_metrics(state,t); fidelity,_=petz_entanglement_fidelity(channel(circuit,t))
            diag=diagnostics(circuit,N,R,A,B,E,t); predicted=metrics['rank_rho_RC']/(2*metrics['rank_rho_C'])
            rows.append({'clifford_index':index,'t':t,'I':metrics['mutual_information_bits'],'r':diag['stabilizer_correlation_rank_r'],
                         'F_petz':fidelity,'rank_formula':predicted,'error_I_r':metrics['mutual_information_bits']-diag['stabilizer_correlation_rank_r'],
                         'error_F_rank':fidelity-predicted})
    out=Path('results'); out.mkdir(exist_ok=True)
    with (out/'exhaustive_clifford_b1.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print('cliffords',len(circuits),'cases',len(rows),'max_I_r',max(abs(r['error_I_r']) for r in rows),'max_F_rank',max(abs(r['error_F_rank']) for r in rows))

if __name__=='__main__': main()
