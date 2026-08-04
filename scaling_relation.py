#!/usr/bin/env python3
"""Cross-check the empirical Petz--decoupling relation for 4B and 5B models."""
from __future__ import annotations
import argparse, csv, os
from pathlib import Path
import numpy as np
os.environ.setdefault("MPLCONFIGDIR", str(Path(".matplotlib-cache").resolve()))
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from hayden_preskill_toy.simulator import Gate, X, apply_1q, apply_circuit, bell_pair, zero_state


def model(bcount: int):
    return 0, 1, tuple(range(2, 2 + bcount)), tuple(range(2 + bcount, 2 + 2 * bcount)), 2 + 2 * bcount


def scrambler(rng, slots, layers):
    q = list(slots); out = []
    for _ in range(layers):
        out += [Gate(("H", "S")[int(rng.integers(2))], x) for x in q]
        rng.shuffle(q); out += [Gate("CNOT", c, d) for c, d in zip(q[::2], q[1::2])]
    return out


def env_state(bcount):
    r, a, b, e, n = model(bcount); state = zero_state(n)
    for x, y in zip(b, e): state = bell_pair(state, x, y, n)
    return state


def initial_bell_state(bcount):
    r, a, b, e, n = model(bcount); state = bell_pair(env_state(bcount), r, a, n)
    return state


def reduced(state, keep, n):
    rest = tuple(q for q in range(n) if q not in keep)
    view = np.transpose(state.reshape((2,) * n), (*keep, *rest)).reshape(2**len(keep), -1)
    return view @ view.conj().T


def entropy(rho):
    vals = np.linalg.eigvalsh((rho + rho.conj().T) / 2); vals = vals[vals > 1e-14]
    return float(-np.sum(vals * np.log2(vals)))


def mutual_info(state, bcount, t):
    r, a, b, e, n = model(bcount); c = (a, *b)[t:]
    rc, rr = reduced(state, (r, *c), n), reduced(state, (r,), n)
    cc = reduced(state, c, n) if c else np.ones((1, 1), complex)
    return max(0., entropy(rr) + entropy(cc) - entropy(rc))


def channel_kraus(circuit, bcount, t):
    r, a, b, e, n = model(bcount); slots = (a, *b); output, comp = (*e, *slots[:t]), slots[t:]
    cols = []
    for bit in range(2):
        state = env_state(bcount)
        if bit: state = apply_1q(state, X, a, n)
        state = apply_circuit(state, circuit, n)
        tensor = state.reshape((2,) * n)[0]
        axes = tuple(q - 1 for q in (*output, *comp))
        cols.append(np.transpose(tensor, axes).reshape(2**len(output), 2**len(comp)))
    return tuple(np.stack([mat[:, c] for mat in cols], axis=1) for c in range(2**len(comp)))


def petz_fidelity(kraus):
    stacked = np.concatenate(kraus, axis=1) / np.sqrt(2)
    u, s, _ = np.linalg.svd(stacked, full_matrices=False); keep = s > 1e-12 * s[0]
    q, sv = u[:, keep], s[keep]
    # Avoid a dense inverse square root: L_j = K_j^dagger Q diag(1/s) Q^dagger / sqrt(2).
    recovery = tuple(((k.conj().T @ q / sv) @ q.conj().T) / np.sqrt(2) for k in kraus)
    bell = np.array([1, 0, 0, 1], complex) / np.sqrt(2); value = 0.
    for k in kraus:
        for rec in recovery:
            value += abs(np.vdot(bell, np.kron(np.eye(2), rec @ k) @ bell)) ** 2
    return float(np.real(value))


def rankdata(values):
    order = np.argsort(values); ranks = np.empty(len(values), float); ranks[order] = np.arange(len(values))
    for value in np.unique(values): ranks[values == value] = ranks[values == value].mean()
    return ranks


def correlation_record(rows, bcount, regime, seed):
    data = [r for r in rows if r["black_hole_qubits"] == bcount and r["regime"] == regime and (seed is None or r["seed"] == seed)]
    raw_x = np.array([r["mutual_information_bits"] for r in data]); raw_y = np.array([r["petz_fidelity"] for r in data])
    x = np.round(raw_x, 10); y = np.round(raw_y, 10)
    pearson = np.corrcoef(x, y)[0, 1] if x.std() > 1e-12 and y.std() > 1e-12 else np.nan
    spearman = np.corrcoef(rankdata(x), rankdata(y))[0, 1] if x.std() > 1e-12 and y.std() > 1e-12 else np.nan
    return {"black_hole_qubits": bcount, "regime": regime, "seed": "all" if seed is None else seed,
            "count": len(data), "pearson": pearson, "spearman": spearman,
            "max_abs_F_minus_2_to_minus_I": max(abs(raw_y - 2**(-raw_x)))}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--trials", type=int, default=50); parser.add_argument("--output", default="results")
    args = parser.parse_args(); out = Path(args.output); out.mkdir(exist_ok=True)
    rows = []
    for bcount in (4, 5):
        for seed in (20260803, 20260804, 20260805):
            rng = np.random.default_rng(seed)
            for regime, depth in (("none", 0), ("weak", 1), ("deep", 6)):
                for trial in range(args.trials):
                    r, a, b, e, n = model(bcount); circuit = scrambler(rng, (a, *b), depth)
                    state = apply_circuit(initial_bell_state(bcount), circuit, n)
                    for t in range(1, bcount + 2):
                        info = mutual_info(state, bcount, t); fidelity = petz_fidelity(channel_kraus(circuit, bcount, t))
                        rows.append({"black_hole_qubits": bcount, "seed": seed, "regime": regime, "trial": trial,
                                     "t": t, "mutual_information_bits": info, "petz_fidelity": fidelity,
                                     "two_to_minus_I_residual": fidelity - 2**(-info)})
    with (out / "petz_vs_decoupling.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    summary = [correlation_record(rows, bcount, regime, seed)
               for bcount in (4, 5) for regime in ("none", "weak", "deep")
               for seed in (None, 20260803, 20260804, 20260805)]
    with (out / "petz_vs_decoupling_summary.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0])); writer.writeheader(); writer.writerows(summary)
    fig, ax = plt.subplots(figsize=(7, 5))
    for bcount, marker in ((4, "o"), (5, "x")):
        data = [r for r in rows if r["black_hole_qubits"] == bcount and r["regime"] == "deep"]
        ax.scatter([r["mutual_information_bits"] for r in data], [r["petz_fidelity"] for r in data], s=12, alpha=.45, marker=marker, label=f"{bcount} B, profond")
    x = np.linspace(0, max(r["mutual_information_bits"] for r in rows), 100); ax.plot(x, 2**(-x), "k--", label=r"$2^{-I}$")
    ax.set(xlabel="I(R:C) [bits]", ylabel="fidélité d’intrication Petz", ylim=(-.02, 1.02)); ax.legend(); fig.tight_layout(); fig.savefig(out / "petz_vs_decoupling.png", dpi=160)
    for bcount in (4, 5):
        data = [r for r in rows if r["black_hole_qubits"] == bcount]
        record = correlation_record(rows, bcount, "deep", None)
        print(f"B={bcount}, deep: Pearson={record['pearson']:.8f}, Spearman={record['spearman']:.8f}, max |F-2^-I|={record['max_abs_F_minus_2_to_minus_I']:.3e}")

if __name__ == "__main__": main()
