"""Operator-basis validation for an in-memory parametric signed dilation."""
from __future__ import annotations
import numpy as np
from .layout import SystemLayout
from .parametric_petz import entanglement_fidelity, petz
from .parametric_stabilizer import input_support_code
from .parametric_synthesis import signed_dilation
from .simulator import Gate, apply_circuit, bell_pair, zero_state


def _cross(a,b,keep,n):
    rest=tuple(q for q in range(n) if q not in keep)
    x=np.transpose(a.reshape((2,)*n),(*keep,*rest)).reshape(2**len(keep),-1)
    y=np.transpose(b.reshape((2,)*n),(*keep,*rest)).reshape(2**len(keep),-1)
    return x@y.conj().T


def _two_qubit_depth(gates: list[Gate], n: int) -> int:
    last = [0] * n
    for gate in gates:
        if gate.name == 'CNOT':
            assert gate.b is not None
            layer = max(last[gate.a], last[gate.b]) + 1
            last[gate.a] = last[gate.b] = layer
    return max(last, default=0)


def _maximally_entangled_fidelity(state, reference, output, n):
    keep = tuple(reference) + tuple(output)
    view = np.transpose(
        state.reshape((2,) * n),
        (*keep, *(q for q in range(n) if q not in keep)),
    ).reshape(2 ** len(keep), -1)
    dimension = 1 << len(reference)
    bell = np.zeros(dimension * dimension, dtype=complex)
    for index in range(dimension): bell[index * dimension + index] = 1 / np.sqrt(dimension)
    return float(np.real(np.vdot(bell, view @ view.conj().T @ bell)))


def _reduced_choi_metrics(candidate, target, n, nout, logical):
    """Exact F and spectral error using the low-rank Stinespring factors."""
    total = n + logical
    keep = tuple(range(nout)) + tuple(range(n, total))
    discard = tuple(q for q in range(total) if q not in keep)
    factor = np.transpose(
        candidate.reshape((2,) * total), (*keep, *discard)
    ).reshape(len(target), -1)
    projected = target.conj() @ factor
    fidelity = float(np.real(np.vdot(projected, projected)))

    # rho_candidate - |target><target| has support in the span of the
    # Stinespring columns and target. Diagonalize only that small span.
    vectors = np.column_stack((factor, target))
    basis, singular_values, _ = np.linalg.svd(vectors, full_matrices=False)
    cutoff = 1e-13 * max(float(singular_values[0]), 1.0)
    basis = basis[:, singular_values > cutoff]
    reduced_factor = basis.conj().T @ factor
    reduced_target = basis.conj().T @ target
    difference = reduced_factor @ reduced_factor.conj().T - np.outer(
        reduced_target, reduced_target.conj()
    )
    error = float(np.max(np.abs(np.linalg.eigvalsh(difference))))
    return fidelity, error


def validate(layout: SystemLayout, channel, scrambler, t: int, *, physical_gates_override=None) -> dict[str,float|int|bool]:
    synthesized_gates,encoder,_,_=signed_dilation(layout,channel,scrambler,t); code=input_support_code(layout,scrambler,t)
    physical_gates = synthesized_gates if physical_gates_override is None else list(physical_gates_override)
    recovery,_=petz(channel); n=len(layout.X(t)); logical=code['logical_qubits']; dim=1<<logical
    message_qubits = layout.n_message; message_dimension = 1 << message_qubits
    physical=layout.X(t); local={q:i for i,q in enumerate(physical)}
    gates=[Gate(g.name,local[g.a],None if g.b is None else local[g.b]) for g in physical_gates]
    from .parametric_synthesis import tableau_gates
    enc=tableau_gates(encoder,tuple(range(n))); states=[]; outputs=[]; maxerr=0.
    petz_outputs=[]
    for i in range(dim):
        b=np.zeros(1<<n,complex);b[i<<(n-logical)]=1; s=apply_circuit(b,enc,n);states.append(s);outputs.append(apply_circuit(s,gates,n));petz_outputs.append(np.stack([r@s for r in recovery],axis=1).reshape(-1))
    nout=int(np.log2(len(petz_outputs[0])))
    for i in range(dim):
      for j in range(dim):
        a=_cross(outputs[i],outputs[j],tuple(range(message_qubits)),n)
        # Contract the already-built Petz Stinespring vectors. This is exactly
        # the same Kraus sum, without rebuilding a rank-one support operator
        # and multiplying it by every recovery Kraus for every (i,j).
        e=_cross(
            petz_outputs[i],petz_outputs[j],tuple(range(message_qubits)),nout
        )
        maxerr=max(maxerr,float(np.linalg.norm(a-e,2)))
    petz_f,_=entanglement_fidelity(channel)
    ref=np.eye(dim)
    candidate_choi=sum((np.kron(outputs[i],ref[:,i]) for i in range(dim)),start=np.zeros(1<<(n+logical),complex))/np.sqrt(dim)
    target_choi=sum((np.kron(petz_outputs[i],ref[:,i]) for i in range(dim)),start=np.zeros(1<<(nout+logical),complex))/np.sqrt(dim)
    choi_f, choi_error = _reduced_choi_metrics(
        candidate_choi, target_choi, n, nout, logical
    )
    state=zero_state(layout.n_qubits)
    for r,a in zip(layout.R_register,layout.A_register): state=bell_pair(state,r,a,layout.n_qubits)
    for b,e in zip(layout.B,layout.E): state=bell_pair(state,b,e,layout.n_qubits)
    final_state=apply_circuit(apply_circuit(state,scrambler,layout.n_qubits),physical_gates,layout.n_qubits)
    circuit_f=_maximally_entangled_fidelity(
        final_state, layout.R_register, layout.X(t)[:message_qubits], layout.n_qubits
    )
    return {'operator_error':maxerr,'petz_fidelity':petz_f,'circuit_fidelity':circuit_f,'choi_fidelity':choi_f,'choi_error':choi_error,'cnot_count':sum(g.name=='CNOT' for g in gates),'logical_depth':_two_qubit_depth(gates,n),'validated':maxerr<1e-12 and choi_f>1-1e-12 and choi_error<1e-12 and abs(circuit_f-petz_f)<1e-12}
