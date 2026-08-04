#!/usr/bin/env python3
"""Write exact support-code data for the two stipulated B=4 instances."""
from pathlib import Path
import csv
import numpy as np
from hayden_preskill_toy.experiment import A, B, E, N_QUBITS, random_scrambler
from hayden_preskill_toy.support_code import support_code

rows=[]
for name,layers,t in (("no_scrambling_t1",0,1),("deep_t2",6,2)):
    circuit=[] if layers==0 else random_scrambler(np.random.default_rng(20260802),layers)
    data=support_code(circuit,N_QUBITS,0,A,B,E,t)
    rows.append({"case":name,"t":t,"physical_chain":"-".join([f"E{i}" for i in range(4)]+[f"D{i}" for i in range(t)]),
                 "support_dimension":data["support_dimension"],"independent_stabilizers":data["independent_stabilizers"],
                 "logical_qubits":data["logical_qubits"],"stabilizer_generators":";".join(data["stabilizer_labels"]),
                 "logical_X":";".join(data["logical_X_labels"]),"logical_Z":";".join(data["logical_Z_labels"])})
out=Path('results');out.mkdir(exist_ok=True)
with (out/'stabilizer_petz_stinespring_resources.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(rows)
