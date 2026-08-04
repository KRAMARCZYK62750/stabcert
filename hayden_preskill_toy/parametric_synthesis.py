"""In-memory signed Clifford-tableau construction; no CSV or routing."""
from __future__ import annotations
import numpy as np
import stim
from .layout import SystemLayout
from .gf2 import canonical_kernel_image_basis
from .parametric_chi_correlations import (
    _group,
    _input_qubits,
    _petz_choi_tableau,
    logical_correlations,
    logical_correlations_exhaustive,
)
from .parametric_petz import choi_tableau
from .parametric_stabilizer import (
    complete_destabilizers,
    complete_destabilizers_exhaustive,
    input_support_code,
    input_support_code_exhaustive,
)
from .simulator import Gate


def tableau_gates(tableau: stim.Tableau, wires: tuple[int,...]) -> list[Gate]:
    result=[]
    for inst in tableau.to_circuit():
        t=[q.value for q in inst.targets_copy()]
        if inst.name=='H': result += [Gate('H',wires[q]) for q in t]
        elif inst.name=='S': result += [Gate('S',wires[q]) for q in t]
        elif inst.name=='CX': result += [Gate('CNOT',wires[a],wires[b]) for a,b in zip(t[::2],t[1::2])]
        elif inst.name=='X': result += [Gate('X',wires[q]) for q in t]
        elif inst.name=='Z': result += [Gate('S',wires[q]) for q in t for _ in range(2)]
        else: raise ValueError(inst.name)
    return result


def _binary(text: str) -> np.ndarray:
    text = text[1:] if text[:1] in '+-' else text
    text = text.replace('_', 'I')
    x = np.array([c in 'XY' for c in text], dtype=np.uint8)
    z = np.array([c in 'ZY' for c in text], dtype=np.uint8)
    return np.concatenate((x, z))


def _label(vector: np.ndarray) -> str:
    n = len(vector) // 2
    return ''.join('IXZY'[int(vector[i]) + 2 * int(vector[n+i])] for i in range(n))


def _rank(rows: list[np.ndarray]) -> int:
    if not rows: return 0
    matrix = np.asarray(rows, dtype=np.uint8).copy(); rank = 0
    for column in range(matrix.shape[1]):
        pivots = np.flatnonzero(matrix[rank:, column])
        if not len(pivots): continue
        pivot = rank + pivots[0]; matrix[[rank, pivot]] = matrix[[pivot, rank]]
        for row in range(rank + 1, len(matrix)):
            if matrix[row, column]: matrix[row] ^= matrix[rank]
        rank += 1
    return rank


def _output_support_stabilizers_exhaustive(channel) -> list[str]:
    tableau = choi_tableau(channel); group = _group(tableau)
    nmessage = int(np.log2(channel.kraus[0].shape[1]))
    nref = len(channel.output); total = len(tableau)
    output_wires = (*range(nmessage), *range(nmessage + nref, total)); basis=[]; result=[]
    for item in group:
        text = str(item)
        if any(text[1 + nmessage + q] != '_' for q in range(nref)): continue
        local = ''.join(text[1 + q] for q in output_wires)
        vector = _binary(local)
        if _rank(basis + [vector]) > len(basis):
            basis.append(vector); result.append(text[0] + local)
    return result


def _restricted_binary(pauli: stim.PauliString, wires: tuple[int, ...]) -> np.ndarray:
    x, z = pauli.to_numpy()
    return np.concatenate((x[list(wires)], z[list(wires)])).astype(np.uint8)


def _output_support_stabilizers(channel) -> list[str]:
    """Output-only Choi stabilizers from a kernel, without group expansion."""
    tableau = _petz_choi_tableau(channel)
    generators = [tableau.z_output(index) for index in range(len(tableau))]
    nmessage = _input_qubits(channel)
    nref = len(channel.output)
    total = len(tableau)
    ref_wires = tuple(range(nmessage, nmessage + nref))
    output_wires = (*range(nmessage), *range(nmessage + nref, total))
    constraints = np.asarray(
        [_restricted_binary(generator, ref_wires) for generator in generators],
        dtype=np.uint8,
    ).T
    mapping = np.asarray(
        [_restricted_binary(generator, output_wires) for generator in generators],
        dtype=np.uint8,
    ).T
    selected = canonical_kernel_image_basis(constraints, len(generators), mapping)
    result = []
    for coefficients, _ in selected:
        item = stim.PauliString("+" + "_" * total)
        for position, generator in enumerate(generators):
            if coefficients[position]:
                item *= generator
        text = str(item)
        if any(text[1 + wire] != "_" for wire in ref_wires):
            raise AssertionError("output-support kernel retained a Ref Pauli")
        local = "".join(text[1 + wire] for wire in output_wires)
        result.append(text[0] + local)
    return result


def _signed_dilation_from_parts(
    layout: SystemLayout,
    channel,
    t: int,
    code,
    rows,
    output_stabilizers,
    destabilizer_builder,
):
    rows = [
        {
            **row,
            "output_support_stabilizers": tuple(output_stabilizers),
        }
        for row in rows
    ]
    xs=[stim.PauliString(r['output']) for r in rows if r['logical_pauli'].startswith('X')]
    zs=[stim.PauliString(r['output']) for r in rows if r['logical_pauli'].startswith('Z')]
    if len(xs)!=code['logical_qubits']:
        raise ValueError('logical correlation count does not match input support')
    output_width = len(xs[0])
    expected_stabilizers = output_width - code['logical_qubits']
    if len(output_stabilizers) != expected_stabilizers:
        raise ValueError('output support stabilizer count is dimensionally inconsistent')
    logical_pairs = list(zip((_binary(str(p)) for p in xs), (_binary(str(p)) for p in zs)))
    output_destabilizers = [
        stim.PauliString(_label(vector))
        for vector in destabilizer_builder(
            [_binary(s) for s in output_stabilizers], logical_pairs, output_width
        )
    ]
    encoder=stim.Tableau.from_conjugated_generators(
        xs=[stim.PauliString(s) for s in code['logical_X_labels']+code['destabilizer_labels']],
        zs=[stim.PauliString(s) for s in code['logical_Z_labels']+code['signed_stabilizer_labels']])
    output=stim.Tableau.from_conjugated_generators(
        xs=xs + output_destabilizers,
        zs=zs + [stim.PauliString(s) for s in output_stabilizers],
    )
    wires=layout.X(t)
    return tableau_gates(encoder.inverse(),wires)+tableau_gates(output,wires[:output_width]), encoder, output, rows


def signed_dilation(layout: SystemLayout, channel, scrambler: list[Gate], t: int):
    code = input_support_code(layout, scrambler, t)
    rows = logical_correlations(layout, channel, code)
    return _signed_dilation_from_parts(
        layout,
        channel,
        t,
        code,
        rows,
        _output_support_stabilizers(channel),
        complete_destabilizers,
    )


def signed_dilation_exhaustive(
    layout: SystemLayout, channel, scrambler: list[Gate], t: int
):
    """Frozen exponential oracle used only for A<=4 regression."""
    code = input_support_code_exhaustive(layout, scrambler, t)
    rows = logical_correlations_exhaustive(layout, channel, code)
    return _signed_dilation_from_parts(
        layout,
        channel,
        t,
        code,
        rows,
        _output_support_stabilizers_exhaustive(channel),
        complete_destabilizers_exhaustive,
    )
