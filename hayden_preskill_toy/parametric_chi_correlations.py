"""Signed logical Choi correlations derived in memory, with no CSV input."""
from __future__ import annotations
import numpy as np
import stim
from .gf2 import lexicographic_solution, rank
from .layout import SystemLayout
from .parametric_petz import choi_tableau


def _petz_choi_tableau(channel) -> stim.Tableau:
    structural = getattr(channel, "petz_choi_tableau", None)
    return structural if structural is not None else choi_tableau(channel)


def _input_qubits(channel) -> int:
    structural = getattr(channel, "input_qubits", None)
    if structural is not None:
        return int(structural)
    return int(np.log2(channel.kraus[0].shape[1]))


def _sign(p: stim.PauliString) -> int: return 1 if complex(p.sign).real > 0 else -1
def _label(p: stim.PauliString, wires: tuple[int,...]) -> str:
    text=str(p)[1:]; return ''.join(text[q].replace('_','I') for q in wires)
def _transpose(p: stim.PauliString) -> stim.PauliString:
    text=str(p)[1:]; return p * (-1 if text.count('Y') & 1 else 1)
def _make(label: str, sign: int=1) -> stim.PauliString:
    return stim.PauliString(('+' if sign==1 else '-')+label.replace('I','_'))


def _group(tableau: stim.Tableau) -> list[stim.PauliString]:
    generators=[tableau.z_output(i) for i in range(len(tableau))]; answer=[]
    for mask in range(1<<len(generators)):
        p=stim.PauliString('+'+'_'*len(generators))
        for i,g in enumerate(generators):
            if mask>>i&1:p*=g
        answer.append(p)
    return answer


def logical_correlations_exhaustive(layout: SystemLayout, channel, code: dict[str,object]) -> list[dict[str,object]]:
    """Return P^T_Ref tensor Q_out stabilizer correlations, including signs."""
    tableau=choi_tableau(channel); group=_group(tableau)
    # ChannelData already fixes the accessible register; avoid any B=4 index.
    nmessage = int(np.log2(channel.kraus[0].shape[1]))
    nref=len(channel.output); total=len(tableau)
    ref_wires=tuple(range(nmessage,nmessage+nref))
    out_wires=(*range(nmessage),*range(nmessage+nref,total))
    support=[_transpose(stim.PauliString(s.replace('I','_'))) for s in code['signed_stabilizer_labels']]
    gauges=[]
    for mask in range(1<<len(support)):
        p=stim.PauliString('+'+'_'*total)
        for i,s in enumerate(support):
            if mask>>i&1:
                text=str(s)
                p*=stim.PauliString(
                    text[0]+'_'*nmessage+text[1:]+'_'*(total-nmessage-nref)
                )
        gauges.append(p)
    rows=[]
    for family, labels in (('X',code['logical_X_labels']),('Z',code['logical_Z_labels'])):
        for index,label in enumerate(labels,1):
            target=_transpose(_make(label))
            found=None
            for g in group:
                for gauge in gauges:
                    candidate=g*gauge
                    if _label(candidate,ref_wires)==_label(target,tuple(range(nref))):
                        out_sign=_sign(candidate)*_sign(target)
                        found=_make(_label(candidate,out_wires),out_sign);break
                if found is not None:break
            if found is None: raise ValueError(f'no signed Choi correlation for {family}{index}')
            rows.append({'logical_pauli':f'{family}{index}','input':str(_make(label)),
                         'reference_transpose':str(target),'output':str(found)})
    return rows


def _binary_on_wires(pauli: stim.PauliString, wires: tuple[int, ...]) -> np.ndarray:
    x, z = pauli.to_numpy()
    return np.concatenate((x[list(wires)], z[list(wires)])).astype(np.uint8)


def logical_correlations(
    layout: SystemLayout, channel, code: dict[str, object]
) -> list[dict[str, object]]:
    """Signed Choi correlations from one affine GF(2) solve per generator."""
    tableau = _petz_choi_tableau(channel)
    generators = [tableau.z_output(index) for index in range(len(tableau))]
    nmessage = _input_qubits(channel)
    nref = len(channel.output)
    total = len(tableau)
    ref_wires = tuple(range(nmessage, nmessage + nref))
    out_wires = (*range(nmessage), *range(nmessage + nref, total))
    support = [
        _transpose(stim.PauliString(label.replace("I", "_")))
        for label in code["signed_stabilizer_labels"]
    ]
    embedded_support = []
    for item in support:
        text = str(item)
        embedded_support.append(
            stim.PauliString(
                text[0]
                + "_" * nmessage
                + text[1:]
                + "_" * (total - nmessage - nref)
            )
        )
    ref_rows = [_binary_on_wires(generator, ref_wires) for generator in generators]
    ref_rows.extend(
        _binary_on_wires(item, tuple(range(len(item)))) for item in support
    )
    system = np.asarray(ref_rows, dtype=np.uint8).T
    n_generators = len(generators)
    n_variables = n_generators + len(support)
    # Exhaustive order was Choi mask first, then support-gauge mask. Preserve
    # that deterministic gauge by minimizing the two integer masks in order.
    priority = [*reversed(range(n_generators)), *reversed(range(n_generators, n_variables))]
    rows = []
    for family, labels in (("X", code["logical_X_labels"]), ("Z", code["logical_Z_labels"])):
        for index, label in enumerate(labels, 1):
            target = _transpose(_make(label))
            coefficients = lexicographic_solution(
                system,
                _binary_on_wires(target, tuple(range(nref))),
                n_variables,
                priority=priority,
            )
            candidate = stim.PauliString("+" + "_" * total)
            for position, generator in enumerate(generators):
                if coefficients[position]:
                    candidate *= generator
            for offset, gauge in enumerate(embedded_support):
                if coefficients[n_generators + offset]:
                    candidate *= gauge
            if _label(candidate, ref_wires) != _label(target, tuple(range(nref))):
                raise AssertionError("GF(2) Choi solve produced the wrong Ref restriction")
            out_sign = _sign(candidate) * _sign(target)
            found = _make(_label(candidate, out_wires), out_sign)
            rows.append(
                {
                    "logical_pauli": f"{family}{index}",
                    "input": str(_make(label)),
                    "reference_transpose": str(target),
                    "output": str(found),
                    "gf2_variables": n_variables,
                    "gf2_constraints": int(system.shape[0]),
                    "gf2_constraint_rank": rank(system),
                    "gf2_affine_kernel_dimension": n_variables - rank(system),
                    "stabilizer_group_elements_enumerated": 0,
                }
            )
    return rows
