#!/usr/bin/env python3
"""Run and report the deterministic verifier adversarial qualification."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np
import stim

from hayden_preskill_toy.recovery_adversarial import (
    CAMPAIGN_FORMAT_VERSION,
    CAMPAIGN_SEED,
    INVALID_CATEGORY_COUNTS,
    VALID_CATEGORY_COUNTS,
    build_invalid_case,
    build_valid_case,
    evaluate_case,
    load_default_context,
)
from hayden_preskill_toy.recovery_run_report import CORE_VERSION
from hayden_preskill_toy.recovery_serialization import (
    artifact_document_hash,
    problem_document_hash,
    semantic_problem_hash,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_RESULTS = ROOT / "results" / "verifier_adversarial_validation.csv"
DEFAULT_SUMMARY = ROOT / "results" / "verifier_adversarial_summary.csv"
DEFAULT_REPORT = ROOT / "VERIFIER_ADVERSARIAL_VALIDATION.md"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rss_mib() -> float | None:
    try:
        import resource
    except ImportError:
        return None
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() != "Darwin":
        value *= 1024
    return value / 2**20


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _category_rows(results) -> list[dict[str, object]]:
    grouped = defaultdict(list)
    for item in results:
        grouped[item.category].append(item)
    rows = []
    for category in (
        *[name for name, _, _ in INVALID_CATEGORY_COUNTS],
        *[name for name, _ in VALID_CATEGORY_COUNTS],
    ):
        items = grouped[category]
        expected_valid = items[0].expected_valid
        rows.append(
            {
                "category": category,
                "expected_valid": expected_valid,
                "cases": len(items),
                "accepted": sum(item.observed_valid for item in items),
                "rejected": sum(not item.observed_valid for item in items),
                "false_accepts": sum(item.false_accept for item in items),
                "false_rejects": sum(item.false_reject for item in items),
                "expected_first_control_hits": sum(item.expected_control_hit for item in items),
                "clean_rejections": sum(item.clean_rejection for item in items if not expected_valid),
                "elapsed_seconds": format(sum(item.elapsed_seconds for item in items), ".9f"),
            }
        )
    return rows


def _markdown(
    metadata: dict[str, object], category_rows: list[dict[str, object]], verdict: str
) -> str:
    invalid = int(metadata["invalid_cases"])
    valid = int(metadata["valid_cases"])
    upper = 3 / invalid if invalid else float("nan")
    lines = [
        "# Qualification adversariale reproductible du vérificateur",
        "",
        "## Périmètre",
        "",
        "Cette campagne qualifie localement le vérificateur v1 sur des cas dérivés de la fixture immuable collective `A=1`. Elle ne constitue ni une preuve formelle d'absence de faille, ni une garantie générale de sécurité.",
        "",
        f"- Format : `{metadata['format_version']}`",
        f"- Graine : `{metadata['seed']}`",
        f"- Artefacts corrompus : `{invalid}`",
        f"- Artefacts valides équivalents : `{valid}`",
        f"- Durée totale : `{metadata['elapsed_seconds']}` s",
        f"- RSS maximale observée : `{metadata['peak_rss_mib']}` Mio",
        f"- Verdict : **{verdict}**",
        "",
        "Les mutations sémantiques sont structurellement valides et re-scellées : elles ne dépendent pas d'un échec superficiel de parsing ou de hash pour être rejetées. Les cas JSON malformés sont mesurés séparément.",
        "",
        "## Résultats par catégorie",
        "",
        "| Catégorie | Validité attendue | Cas | Acceptés | Rejetés | Faux acceptés | Faux rejetés | Contrôle attendu atteint |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in category_rows:
        lines.append(
            f"| {row['category']} | {row['expected_valid']} | {row['cases']} | {row['accepted']} | {row['rejected']} | {row['false_accepts']} | {row['false_rejects']} | {row['expected_first_control_hits']} |"
        )
    lines.extend(
        [
            "",
            "## Correspondance mutation–contrôle",
            "",
            "- hash sémantique ou documentaire → contrôles de provenance ;",
            "- générateurs ou dimensions de `tau_X` → support stabilisateur signé ;",
            "- Choi Petz faux mais structurellement valide → reconstruction indépendante de la cible ;",
            "- canal re-scellé mais faux → égalité des Choi réduits ;",
            "- action logique, arête interdite et route non déterministe → contrôles Clifford, topologique et de routage ;",
            "- ressources, permutation, certificat et fidélité → recomptages indépendants ;",
            "- JSON incomplet, inconnu ou non conforme → validation stricte du modèle.",
            "",
            "Les variantes valides couvrent le changement de base du même sous-groupe de stabilisateurs, la jauge de purification sur l'environnement, une Clifford finale sur l'environnement rejeté et des réécritures de circuit identitaires.",
            "",
            "## Incident découvert pendant la qualification",
            "",
            "Le pré-échantillonnage a montré que `logical_action_signature` n'était pas reconstruite par le vérificateur. Le contrôle a été ajouté avant la campagne complète, puis les fixtures A=1, A=8 et A=12 ont été rejouées avec succès.",
            "",
            "## Conclusion locale",
            "",
        ]
    )
    if verdict == "VALIDÉ":
        lines.extend(
            [
                f"Sur `{invalid}` artefacts corrompus générés selon les catégories documentées, le vérificateur a rejeté les `{invalid}` cas. Sur `{valid}` artefacts valides équivalents, aucun faux rejet n'a été observé.",
                "",
                f"La règle indicative `3/N` donne `{upper:.6g}` (soit `{100 * upper:.4g} %`) à 95 %, uniquement relativement au processus de mutation testé. Elle ne mesure pas une probabilité générale de compromission.",
            ]
        )
    else:
        lines.append("Au moins une assertion de campagne a échoué ; aucune conclusion positive n'est autorisée.")
    lines.extend(
        [
            "",
            "## Reproductibilité",
            "",
            f"- Python : `{metadata['python_version']}`",
            f"- NumPy : `{metadata['numpy_version']}`",
            f"- Stim : `{metadata['stim_version']}`",
            f"- Noyau : `{metadata['core_version']}`",
            f"- Hash du problème : `{metadata['semantic_problem_hash']}`",
            f"- Hash documentaire du problème : `{metadata['problem_document_hash']}`",
            f"- Hash documentaire de l'artefact de base : `{metadata['base_artifact_hash']}`",
            f"- Hash du générateur : `{metadata['generator_sha256']}`",
            f"- Hash du vérificateur : `{metadata['verifier_sha256']}`",
            "",
            "Commande :",
            "",
            "```bash",
            ".venv/bin/python run_verifier_adversarial_validation.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def run(*, smoke: bool, results_path: Path, summary_path: Path, report_path: Path) -> int:
    context = load_default_context()
    started = time.perf_counter()
    results = []
    cases_total = 0
    invalid_total = 0
    valid_total = 0

    definitions = []
    for category, count, _ in INVALID_CATEGORY_COUNTS:
        definitions.append((False, category, 1 if smoke else count))
        invalid_total += 1 if smoke else count
    for category, count in VALID_CATEGORY_COUNTS:
        definitions.append((True, category, 1 if smoke else count))
        valid_total += 1 if smoke else count

    for expected_valid, category, count in definitions:
        for index in range(count):
            case = (
                build_valid_case(context, category, index)
                if expected_valid
                else build_invalid_case(context, category, index)
            )
            result = evaluate_case(context, case)
            results.append(result)
            cases_total += 1
            if not smoke and cases_total % 250 == 0:
                print(
                    json.dumps(
                        {
                            "completed": cases_total,
                            "total": invalid_total + valid_total,
                            "false_accepts": sum(item.false_accept for item in results),
                            "false_rejects": sum(item.false_reject for item in results),
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )

    elapsed = time.perf_counter() - started
    false_accepts = sum(item.false_accept for item in results)
    false_rejects = sum(item.false_reject for item in results)
    bad_controls = sum(not item.expected_control_hit for item in results)
    unclean = sum(
        not item.clean_rejection for item in results if not item.expected_valid
    )
    verdict = (
        "VALIDÉ"
        if not false_accepts and not false_rejects and not bad_controls and not unclean
        else "NON VALIDÉ"
    )

    rows = []
    for item in results:
        row = asdict(item)
        row["elapsed_seconds"] = format(item.elapsed_seconds, ".9f")
        rows.append(row)
    category_rows = _category_rows(results)
    _write_csv(results_path, rows)
    _write_csv(summary_path, category_rows)

    metadata = {
        "format_version": CAMPAIGN_FORMAT_VERSION,
        "seed": CAMPAIGN_SEED,
        "invalid_cases": invalid_total,
        "valid_cases": valid_total,
        "false_accepts": false_accepts,
        "false_rejects": false_rejects,
        "unexpected_first_controls": bad_controls,
        "unclean_rejections": unclean,
        "elapsed_seconds": format(elapsed, ".9f"),
        "peak_rss_mib": None if _rss_mib() is None else format(_rss_mib(), ".6f"),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "stim_version": getattr(stim, "__version__", "unknown"),
        "core_version": CORE_VERSION,
        "semantic_problem_hash": semantic_problem_hash(context.problem),
        "problem_document_hash": problem_document_hash(context.problem),
        "base_artifact_hash": artifact_document_hash(context.artifact),
        "generator_sha256": _sha256(ROOT / "hayden_preskill_toy" / "recovery_adversarial.py"),
        "verifier_sha256": _sha256(ROOT / "hayden_preskill_toy" / "recovery_verify.py"),
        "verdict": verdict,
    }
    report_path.write_text(_markdown(metadata, category_rows, verdict), encoding="utf-8")
    metadata_path = summary_path.with_suffix(".metadata.json")
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if verdict == "VALIDÉ" else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    arguments = parser.parse_args()
    raise SystemExit(
        run(
            smoke=arguments.smoke,
            results_path=arguments.results,
            summary_path=arguments.summary,
            report_path=arguments.report,
        )
    )


if __name__ == "__main__":
    main()
