#!/usr/bin/env python3
"""Compile one specified B=4 Petz dilation on the local chain and verify it exactly."""
import argparse, csv
from pathlib import Path
import numpy as np
from hayden_preskill_toy.channels import channel_at_time, petz_entanglement_fidelity
from hayden_preskill_toy.experiment import A, E, N_QUBITS, R, initial_state, random_scrambler
from hayden_preskill_toy.local import chain_layout, compile_unitary_on_linear_chain, light_cone_bound, stinespring_unitary_extension
from hayden_preskill_toy.simulator import apply_circuit, apply_unitary, bell_fidelity

p=argparse.ArgumentParser();p.add_argument('--seed',type=int,default=20260802);p.add_argument('--layers',type=int,default=0);p.add_argument('--t',type=int,default=1);args=p.parse_args()
rng=np.random.default_rng(args.seed); scramble=random_scrambler(rng,args.layers); state=apply_circuit(initial_state(),scramble,N_QUBITS)
channel=channel_at_time(scramble,args.t); abstract,_=petz_entanglement_fidelity(channel); unitary,extension=stinespring_unitary_extension(channel)
compiled,metrics=compile_unitary_on_linear_chain(unitary)
qubits=(*E,*((A,2,3,4,5)[:args.t]))
implemented=apply_unitary(state,unitary,qubits,N_QUBITS)
row={'seed':args.seed,'scrambler_layers':args.layers,'t':args.t,'layout':'-'.join(chain_layout(args.t)),
     'petz_abstract_fidelity':abstract,'stinespring_exact_fidelity':bell_fidelity(implemented,R,E[0],N_QUBITS),
     **extension,**metrics,**light_cone_bound(args.t)}
out=Path('results');out.mkdir(exist_ok=True); path=out/'local_decoding_results.csv'
write_header=not path.exists()
with path.open('a',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(row));
 if write_header:w.writeheader()
 w.writerow(row)
print(row)
