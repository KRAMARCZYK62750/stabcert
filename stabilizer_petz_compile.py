#!/usr/bin/env python3
"""Direct Clifford control for Petz without dense-unitary synthesis."""
from pathlib import Path
import csv
from hayden_preskill_toy.experiment import A, E, N_QUBITS, R, initial_state
from hayden_preskill_toy.simulator import Gate, apply_circuit, bell_fidelity

# Physical chain E0--E1--E2--E3--D0.  Four adjacent SWAPs route D0 to E0.
chain = (*E, A)
gates=[]
for left in range(len(chain)-2, -1, -1):
    a,b=chain[left],chain[left+1]
    gates += [Gate('CNOT',a,b),Gate('CNOT',b,a),Gate('CNOT',a,b)]
state=apply_circuit(initial_state(),gates,N_QUBITS)
row={'case':'no_scrambling_t1','petz_abstract_fidelity':1.0,'direct_stabilizer_fidelity':bell_fidelity(state,R,E[0],N_QUBITS),
     'direct_clifford_two_qubit_depth':12,'direct_cnot_count':12,'direct_swap_count':4,'ancillas':0,'pauli_measurements':0,
     'conditional_corrections':0,'routing':'explicit adjacent SWAP chain','status':'deterministic exact Clifford realization'}
out=Path('results');out.mkdir(exist_ok=True)
with (out/'stabilizer_petz_resources.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(row));w.writeheader();w.writerow(row)
print(row)
