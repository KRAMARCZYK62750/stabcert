#!/usr/bin/env python3
"""Extract signed Petz logical-Pauli images using the frozen Choi convention.

Convention (validated by ``choi_symplectic_conventions.py``):
|J_V>=(V tensor I)|Phi>, with wire order A'|Ref|E_Petz and
(P_out tensor P_ref^T)|J_V>=|J_V>.  Thus a Y on Ref carries a minus sign.
"""
from __future__ import annotations
from pathlib import Path
import argparse
import csv
import numpy as np
import stim

from hayden_preskill_toy.channels import channel_at_time, petz_recovery
from hayden_preskill_toy.experiment import A, B, E, N_QUBITS, random_scrambler
from hayden_preskill_toy.support_code import support_code


def binary_from_label(label: str) -> np.ndarray:
    x=np.array([c in 'XY' for c in label], dtype=np.uint8); z=np.array([c in 'ZY' for c in label], dtype=np.uint8)
    return np.concatenate((x,z))


def label(vector: np.ndarray) -> str:
    n=len(vector)//2; return ''.join('IXZY'[int(vector[i])+2*int(vector[n+i])] for i in range(n))


def symp(a,b):
    n=len(a)//2; return int((a[:n]@b[n:]+a[n:]@b[:n])&1)


def _signed_group(tableau: stim.Tableau) -> list[stim.PauliString]:
    generators=[tableau.z_output(i) for i in range(len(tableau))]
    answer=[]
    for mask in range(1 << len(generators)):
        p=stim.PauliString('+'+'_'*len(generators))
        for i, g in enumerate(generators):
            if mask>>i & 1: p *= g
        answer.append(p)
    return answer


def _local_label(p: stim.PauliString, indices: tuple[int, ...]) -> str:
    text=str(p)[1:]
    return ''.join(text[i].replace('_','I') for i in indices)


def _sign(p: stim.PauliString) -> int:
    return 1 if complex(p.sign).real > 0 else -1


def _embed_reference(p: stim.PauliString, total: int, nref: int) -> stim.PauliString:
    text=str(p)[1:]
    return stim.PauliString(str(p)[0] + '_' + text + '_' * (total - nref - 1))


def _transpose(p: stim.PauliString) -> stim.PauliString:
    return stim.PauliString(('+' if _sign(p) == 1 else '-') + str(p)[1:].replace('_','I').replace('Y','Y')) * ((-1) if str(p)[1:].count('Y') & 1 else 1)


def _from_label(label_: str, sign: int = 1) -> stim.PauliString:
    return stim.PauliString(('+' if sign == 1 else '-') + label_.replace('I','_'))


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--layers',type=int,default=6); parser.add_argument('--t',type=int,default=2); parser.add_argument('--seed',type=int,default=20260802); args=parser.parse_args()
    circuit=[] if args.layers==0 else random_scrambler(np.random.default_rng(args.seed),args.layers); t=args.t
    code=support_code(circuit,N_QUBITS,0,A,B,E,t); logical=[]
    for x,z in zip(code['logical_X_labels'],code['logical_Z_labels']): logical += [('X',_from_label(x)),('Z',_from_label(z))]
    channel=channel_at_time(circuit,t); kraus,_=petz_recovery(channel); dx=kraus[0].shape[1]; rank=len(kraus)
    vector=np.stack(kraus,axis=0).transpose(1,2,0).reshape(-1)/np.sqrt(dx)
    tableau=stim.Tableau.from_state_vector(vector,endian='big'); group=_signed_group(tableau)
    nref=int(np.log2(dx)); total=nref+1+int(np.log2(rank))
    # The reference support stabilizers must themselves be transposed in Choi space.
    support_stabilizers=[_transpose(stim.PauliString(s.replace('I','_'))) for s in code['signed_stabilizer_labels']]
    reference_gauge=[]
    for mask in range(1 << len(support_stabilizers)):
        p=stim.PauliString('+'+'_'*total)
        for i,s in enumerate(support_stabilizers):
            if mask>>i & 1: p *= _embed_reference(s,total,nref)
        reference_gauge.append(p)
    rows=[]; selected=[]
    for name,target in logical:
        desired=_transpose(target); found=None
        for g in group:
            for gauge in reference_gauge:
                candidate=g * gauge
                if _local_label(candidate,tuple(range(1,1+nref))) != _local_label(desired,tuple(range(nref))):
                    continue
                out_indices=(0,*range(1+nref,total))
                # sign(candidate)=sign(P_ref)*sign(Q_out), after the factors are ordered.
                out_sign=_sign(candidate) * _sign(desired)
                found=_from_label(_local_label(candidate,out_indices),out_sign)
                break
            if found is not None: break
        selected.append((binary_from_label(_local_label(target,tuple(range(nref)))), binary_from_label(_local_label(found,tuple(range(len(found))))) if found is not None else None))
        rows.append({'logical_pauli':name+str((len(rows)//2)+1),
                     'input_label':str(target), 'choi_reference_operator':str(desired),
                     'output_label_Aprime_E':str(found) if found is not None else 'NOT_FOUND'})
    for i in range(0,len(rows),2): rows[i]['pair_symplectic']=symp(selected[i][1],selected[i+1][1])
    input_gram=[[symp(selected[i][0],selected[j][0]) for j in range(len(selected))] for i in range(len(selected))]
    output_gram=[[symp(selected[i][1],selected[j][1]) for j in range(len(selected))] for i in range(len(selected))]
    for i,row in enumerate(rows): row['input_gram_row']=''.join(map(str,input_gram[i])); row['output_gram_row']=''.join(map(str,output_gram[i]))
    out=Path('results');out.mkdir(exist_ok=True); suffix=f'seed{args.seed}_layers{args.layers}_t{t}'
    with (out/f'petz_logical_action_{suffix}.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    print(rows)


if __name__=='__main__': main()
