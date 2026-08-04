#!/usr/bin/env python3
"""Construct the candidate deterministic Clifford dilation from symplectic data."""
import argparse,csv
from pathlib import Path
import numpy as np
import stim
from hayden_preskill_toy.experiment import A,B,E,N_QUBITS,initial_state,random_scrambler
from hayden_preskill_toy.support_code import support_code
from hayden_preskill_toy.simulator import Gate,apply_circuit,bell_fidelity

def tableau_gates(tableau, physical):
    result=[]
    for inst in tableau.to_circuit():
        ts=[q.value for q in inst.targets_copy()]
        if inst.name=='H': result += [Gate('H',physical[q]) for q in ts]
        elif inst.name=='S': result += [Gate('S',physical[q]) for q in ts]
        elif inst.name=='S_DAG': result += [Gate('S',physical[q]) for q in ts for _ in range(3)]
        elif inst.name=='X': result += [Gate('X',physical[q]) for q in ts]
        elif inst.name=='Z': result += [Gate('S',physical[q]) for q in ts for _ in range(2)]
        elif inst.name=='CX': result += [Gate('CNOT',physical[a],physical[b]) for a,b in zip(ts[::2],ts[1::2])]
        else: raise ValueError(inst.name)
    return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--layers',type=int,default=6);p.add_argument('--t',type=int,default=2);p.add_argument('--seed',type=int,default=20260802);args=p.parse_args()
 c=[] if args.layers==0 else random_scrambler(np.random.default_rng(args.seed),args.layers);t=args.t;x=(*E,*((A,*B)[:t]));code=support_code(c,N_QUBITS,0,A,B,E,t)
 # Encoder: canonical logical qubits then zero syndrome qubits -> physical code X.
 enc=stim.Tableau.from_conjugated_generators(
  xs=[stim.PauliString(s) for s in code['logical_X_labels']+code['destabilizer_labels']],
  zs=[stim.PauliString(s) for s in code['logical_Z_labels']+code['signed_stabilizer_labels']])
 rows=list(csv.DictReader(open(f'results/petz_logical_action_seed{args.seed}_layers{args.layers}_t{t}.csv')))
 out=stim.Tableau.from_conjugated_generators(xs=[stim.PauliString(rows[i]['output_label_Aprime_E']) for i in range(0,2*code['logical_qubits'],2)],zs=[stim.PauliString(rows[i]['output_label_Aprime_E']) for i in range(1,2*code['logical_qubits'],2)])
 # The first k logical wires are A'|E_Petz.  Remaining physical wires hold
 # the fixed input syndrome and are discarded after the dilation.
 gates=tableau_gates(enc.inverse(),x)+tableau_gates(out,x[:code['logical_qubits']])
 state=apply_circuit(apply_circuit(initial_state(),c,N_QUBITS),gates,N_QUBITS)
 row={'case':f'layers{args.layers}_t{t}','input_code_dim':code['support_dimension'],'logical_qubits':code['logical_qubits'],'output_env_qubits':code['logical_qubits']-1,
      'clifford_gate_count':len(gates),'two_qubit_count':sum(g.name=='CNOT' for g in gates),'fidelity_candidate':bell_fidelity(state,0,x[0],N_QUBITS),
      'status':'candidate isometry; full operator-basis validation pending'}
 path=Path(f'results/petz_candidate_isometry_seed{args.seed}_layers{args.layers}_t{t}.csv')
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(row));w.writeheader();w.writerow(row)
 print(row)
if __name__=='__main__':main()
