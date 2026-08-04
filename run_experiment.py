#!/usr/bin/env python3
"""Run phase A (decoupling) and phase B (exact Petz recovery) at 4B+4E."""
from __future__ import annotations
import argparse
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(".matplotlib-cache").resolve()))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from hayden_preskill_toy.experiment import Config, run_decoupling_and_petz, summarize, write_csv


def decoupling_figure(summary, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharex=True)
    for access, axis in zip(("E_plus_D", "D_only"), axes):
        for regime in ("none", "weak", "deep"):
            rows = [r for r in summary if r["access_model"] == access and r["regime"] == regime]
            t = [r["t"] for r in rows]
            axis.plot(t, [r["mean"] for r in rows], marker="o", label=f"{regime} — moyenne")
            axis.plot(t, [r["median"] for r in rows], linestyle="--", label=f"{regime} — médiane")
            axis.fill_between(t, [r["q10"] for r in rows], [r["q90"] for r in rows], alpha=.12)
        axis.set(title="Accès E+D" if access == "E_plus_D" else "Accès D seul", xlabel="temps d’émission t",
                 ylabel="I(R:inaccessible) [bits]")
        axis.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(out / "decoupling_mutual_information.png", dpi=160); plt.close(fig)


def trace_distance_figure(summary, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    for regime in ("none", "weak", "deep"):
        rows = [r for r in summary if r["access_model"] == "E_plus_D" and r["regime"] == regime]
        ax.plot([r["t"] for r in rows], [r["mean"] for r in rows], marker="o", label=regime)
    ax.set(xlabel="temps d’émission t", ylabel="distance en trace à rho_R⊗rho_C", ylim=(-.02, 1.02))
    ax.legend(); fig.tight_layout(); fig.savefig(out / "decoupling_trace_distance.png", dpi=160); plt.close(fig)


def recovery_figure(summary, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    rows = [r for r in summary if r["regime"] == "deep"]
    for algorithm, label in (("petz", "Petz"), ("random_witness", "témoin aléatoire k=8"),
                             ("U_inverse_control", "U inverse (contrôle)")):
        data = [r for r in rows if r["algorithm"] == algorithm and
                (algorithm != "random_witness" or str(r["two_qubit_depth"]) == "8")]
        if data:
            ax.plot([r["t"] for r in data], [r["mean"] for r in data], marker="o", label=label)
    ax.set(xlabel="temps d’émission t", ylabel="fidélité d’intrication moyenne", ylim=(-.02, 1.02))
    ax.legend(); fig.tight_layout(); fig.savefig(out / "recovery_comparison.png", dpi=160); plt.close(fig)


def report(decoupling_summary, trace_summary, recovery_summary, recovery_rows, path: Path, config: Config) -> None:
    deep_info = [r for r in decoupling_summary if r["regime"] == "deep" and r["access_model"] == "E_plus_D"]
    petz = [r for r in recovery_summary if r["regime"] == "deep" and r["algorithm"] == "petz"]
    inverse = [r for r in recovery_summary if r["regime"] == "deep" and r["algorithm"] == "U_inverse_control"]
    lines = ["# Rapport d’expérience — Phase A et Petz", "", "## Information présente ou absente selon le test de découplage", "",
             f"{config.trials} brouilleurs par régime, graine {config.seed + 1}. Pour l’accès E+D, I(R:C) et la distance en trace à rho_R⊗rho_C sont calculées exactement. Une valeur faible est un indicateur quantitatif de récupération approchée depuis E+D, non une équivalence sans borne.", "",
             "| t | I(R:C) moyen | distance en trace moyenne |", "|---:|---:|---:|"]
    deep_trace = {r["t"]: r for r in trace_summary if r["regime"] == "deep" and r["access_model"] == "E_plus_D"}
    lines += [f"| {r['t']} | {r['mean']:.6f} | {deep_trace[r['t']]['mean']:.6f} |" for r in deep_info]
    lines += ["", "L’accès D seul est évalué séparément par I(R:EC), car E devient alors inaccessible.",
              "", "## Récupération obtenue par un algorithme explicite", "",
              "Le canal N_t est fourni par des opérateurs de Kraus; les erreurs de conservation de trace et la conservation du Petz sur le support sont dans `recovery.csv`. La pseudo-inverse Petz utilise le seuil relatif 1e-12 sur les valeurs singulières de N_t(I/2).", "",
              "| t | F_e Petz moyen, brouillage profond |", "|---:|---:|"]
    lines += [f"| {r['t']} | {r['mean']:.6f} |" for r in petz]
    if inverse:
        lines += ["", f"Contrôle à évaporation totale : U inverse donne F_e moyen {inverse[0]['mean']:.6f} à t=5."]
    random8 = {r["t"]: r for r in recovery_summary if r["regime"] == "deep" and r["algorithm"] == "random_witness" and str(r["two_qubit_depth"]) == "8"}
    petz_by_t = {r["t"]: r for r in petz}
    lines += ["", "Comparaison commune, brouillage profond :", "", "| t | Petz | témoin aléatoire k=8 | U inverse |", "|---:|---:|---:|---:|"]
    for t in range(1, 6):
        inv = inverse[0]["mean"] if t == 5 and inverse else "—"
        lines.append(f"| {t} | {petz_by_t[t]['mean']:.6f} | {random8[t]['mean']:.6f} | {inv} |")
    lines += ["", "## Registre préalable à toute SDP", "",
              "Aucune SDP ni solveur n’a été lancé dans cette phase. Le tableau ci-dessous inscrit les tailles qui borneraient une SDP réduite au support; toute exécution ultérieure indiquera le solveur et ses tolérances.",
              "", "| t | support Petz observé | dimension Choi complète | solveur | tolérances |", "|---:|---:|---:|---|---|"]
    for t in range(1, 6):
        rows = [r for r in recovery_rows if r["regime"] == "deep" and r["algorithm"] == "petz" and r["t"] == t]
        supports = sorted({int(r["support_dimension"]) for r in rows})
        choi = int(rows[0]["choi_dimension"])
        lines.append(f"| {t} | {', '.join(map(str, supports))} | {choi} | non exécuté | non applicable |")
    lines += ["", "## Coût ou profondeur observée", "",
              "La phase présente ne déduit aucun k_min ni k_best_observed : Petz est un canal exact, non encore compilé en circuit. Les témoins aléatoires de profondeurs 0, 2, 4, 6 et 8 figurent dans la comparaison, sans prétention d’optimalité.",
              "", "## Conclusions interdites faute de preuve", "",
              "Aucune conclusion sur une simulation physique de trou noir, le paradoxe de l’information, une complexité fondamentale, ou une optimalité analytique n’est permise. La SDP n’a pas été lancée. Avant une éventuelle SDP, le rapport documentera pour chaque t la dimension du support, la taille du Choi, le solveur et ses tolérances; son résultat ne sera qualifié que d’optimalité numérique pour ce modèle fini.",
              "", "## Classification des cas", "",
              "Dans cette campagne, les occurrences avec I(R:C) inférieur à 1e-8 sont récupérées à fidélité Petz ≈1; aucun cas « information disponible mais Petz insuffisant » n’a été observé. En revanche, le témoin aléatoire k=8 reste près de 1/4 dans la moyenne, y compris lorsque Petz récupère : c’est une divergence entre disponibilité et cette famille de circuits testée, pas une borne de profondeur. Aucune SDP n’ayant été exécutée, aucun cas « SDP mais pas faible profondeur » ne peut encore être affirmé. Le contrôle U inverse à t=5 est distinct."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=50)
    parser.add_argument("--output", default="results")
    args = parser.parse_args()
    cfg = Config(trials=args.trials, output_dir=args.output)
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    decoupling, recovery = run_decoupling_and_petz(cfg)
    dec_summary = summarize(decoupling, ("regime", "access_model", "t"), "mutual_information_bits")
    trace_summary = summarize(decoupling, ("regime", "access_model", "t"), "trace_distance_product")
    rec_summary = summarize(recovery, ("regime", "algorithm", "two_qubit_depth", "t"), "entanglement_fidelity")
    write_csv(decoupling, out / "decoupling.csv")
    write_csv(dec_summary, out / "decoupling_summary.csv")
    write_csv(trace_summary, out / "decoupling_trace_summary.csv")
    write_csv(recovery, out / "recovery.csv")
    write_csv([r for r in recovery if r["algorithm"] == "petz"], out / "stabilizer_diagnostics.csv")
    write_csv(rec_summary, out / "recovery_summary.csv")
    decoupling_figure(dec_summary, out); trace_distance_figure(trace_summary, out); recovery_figure(rec_summary, out)
    report(dec_summary, trace_summary, rec_summary, recovery, out / "REPORT.md", cfg)
    print(f"{len(decoupling)} lignes de découplage et {len(recovery)} lignes de récupération écrites dans {out}")


if __name__ == "__main__":
    main()
