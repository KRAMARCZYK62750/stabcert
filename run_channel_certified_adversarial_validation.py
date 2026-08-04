#!/usr/bin/env python3
"""Deterministic adversarial qualification of channel-certified policy."""
from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import platform
import time

import numpy as np
import stim

from hayden_preskill_toy.recovery_adversarial import (
    CAMPAIGN_SEED,
    _resource_claim,
    build_invalid_case,
    build_valid_case,
    load_default_context,
)
from hayden_preskill_toy.recovery_run_report import CORE_VERSION
from hayden_preskill_toy.recovery_serialization import (
    artifact_document_hash,
    artifact_from_dict,
    problem_document_hash,
    semantic_problem_hash,
)
from hayden_preskill_toy.recovery_verify import verify_recovery


FORMAT_VERSION = "orelia.channel-certified-adversarial-campaign/v1"
ROOT = Path(__file__).resolve().parent
DEFAULT_RESULTS = ROOT / "results" / "channel_certified_adversarial.csv"
DEFAULT_SUMMARY = ROOT / "results" / "channel_certified_adversarial_summary.csv"
DEFAULT_REPORT = ROOT / "docs" / "notes" / "CHANNEL_CERTIFIED_IMPLEMENTATION.md"

INVALID_DEFINITIONS = (
    ("semantic_hash", "semantic_hash", "semantic_problem_hash"),
    ("document_hash", "document_hash", "document_hash"),
    ("topology_claim", "topology_claim", "topology"),
    ("tau_signed_generator", "tau_signed_generator", "tau_support_signed"),
    ("tau_dimensions", "tau_dimensions", "tau_support_dimensions"),
    ("petz_target_claim", "petz_target_claim", "artifact_target_claim"),
    ("wrong_channel", "wrong_channel_resealed", "reduced_choi_channel"),
    ("forbidden_edge", "forbidden_edge_identity", "coupling_graph"),
    ("observable_resource", "resource_accounting", "observable_resource_accounting"),
    ("final_order", "final_permutation", "restored_final_order_declaration"),
    ("certificate_claim", "certificate_claim", "certificate_signature_claims"),
    ("fidelity_claim", "fidelity_claim", "circuit_entanglement_fidelity"),
    ("malformed_json", "malformed_serialized_artifact", "artifact_model_validation"),
)

VALID_DEFINITIONS = (
    ("target_environment_gauge", "target_environment_gauge"),
    ("tau_equivalent_basis", "tau_equivalent_basis"),
    ("deterministic_environment_gauge", "circuit_environment_gauge"),
    ("deterministic_identity_rewrite", "circuit_identity_rewrite"),
    ("external_environment_gauge", "logical_routed_mismatch"),
    ("external_identity_rewrite", "nondeterministic_route_identity"),
    ("uncertified_swap_claim", "resource_accounting"),
    # The only family that distinguishes comparison on the code subspace from
    # comparison of the total channel: accepted by the first, rejected by the
    # second. Without it the campaign counts are silent on which is implemented.
    ("outside_support_only", "outside_support_only"),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _case(context, category: str, source_category: str, index: int, expected_valid: bool):
    if expected_valid and source_category in {
        "target_environment_gauge",
        "tau_equivalent_basis",
        "circuit_environment_gauge",
        "circuit_identity_rewrite",
        "outside_support_only",
    }:
        return build_valid_case(context, source_category, index)
    if category == "observable_resource":
        # Only v1 fields observable directly from the circuits are corrupted.
        field = (0, 1, 2, 3, 6)[index % 5]
        artifact = _resource_claim(context, 7 * index + field)
        return artifact, None
    if category == "uncertified_swap_claim":
        # Movement/restoration claims cannot be reconstructed from a bare CNOT
        # circuit and must neither be certified nor affect the channel verdict.
        field = 4 + (index & 1)
        artifact = _resource_claim(context, 7 * index + field)
        return artifact, None
    built = build_invalid_case(context, source_category, index)
    return built.artifact, built.serialized_artifact


def _normalize_case(value):
    if isinstance(value, tuple):
        return value
    return value.artifact, value.serialized_artifact


def _evaluate(context, case_id, category, source_category, index, expected_valid, expected_first):
    started = time.perf_counter()
    artifact, serialized = _normalize_case(
        _case(context, category, source_category, index, expected_valid)
    )
    clean = True
    try:
        if serialized is not None:
            try:
                artifact = artifact_from_dict(deepcopy(serialized))
            except (KeyError, TypeError, ValueError) as error:
                observed = False
                first = "artifact_model_validation"
                digest = hashlib.sha256(repr(serialized).encode()).hexdigest()
                detail = f"{type(error).__name__}: {error}"
            else:
                report = verify_recovery(context.problem, artifact, policy="channel-certified")
                observed = report.verified
                failed = next((item for item in report.checks if not item.passed), None)
                first = "none" if failed is None else failed.name
                digest = artifact_document_hash(artifact)
                detail = "all checks passed" if failed is None else failed.detail
        else:
            report = verify_recovery(context.problem, artifact, policy="channel-certified")
            observed = report.verified
            failed = next((item for item in report.checks if not item.passed), None)
            first = "none" if failed is None else failed.name
            digest = artifact_document_hash(artifact)
            detail = "all checks passed" if failed is None else failed.detail
    except Exception as error:
        observed = False
        first = f"verification_exception:{type(error).__name__}"
        digest = ""
        detail = str(error)
        clean = False
    return {
        "case_id": case_id,
        "category": category,
        "local_index": index,
        "expected_valid": expected_valid,
        "observed_valid": observed,
        "expected_first_control": expected_first,
        "observed_first_control": first,
        "expected_control_hit": first == expected_first,
        "false_accept": (not expected_valid) and observed,
        "false_reject": expected_valid and (not observed),
        "clean_rejection": clean,
        "artifact_hash": digest,
        "elapsed_seconds": format(time.perf_counter() - started, ".9f"),
        "detail": detail,
    }


def _summary(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["category"]].append(row)
    result = []
    for category in (
        *[item[0] for item in INVALID_DEFINITIONS],
        *[item[0] for item in VALID_DEFINITIONS],
    ):
        items = grouped[category]
        result.append({
            "category": category,
            "expected_valid": items[0]["expected_valid"],
            "cases": len(items),
            "accepted": sum(item["observed_valid"] for item in items),
            "rejected": sum(not item["observed_valid"] for item in items),
            "false_accepts": sum(item["false_accept"] for item in items),
            "false_rejects": sum(item["false_reject"] for item in items),
            "expected_first_control_hits": sum(item["expected_control_hit"] for item in items),
        })
    return result


def _markdown(metadata, summary):
    lines = [
        "# Implémentation et qualification du mode `channel-certified`",
        "",
        "## Résultat",
        "",
        f"Statut : **{metadata['verdict']}**.",
        "",
        "Le vérificateur reconstruit la cible Petz depuis `RecoveryProblem`, compare les sous-groupes stabilisateurs signés des Choi réduits et ne reconstruit pas la route ORELIA attendue dans cette politique.",
        "",
        f"- cas invalides : `{metadata['invalid_cases']}` ;",
        f"- représentations valides : `{metadata['valid_cases']}` ;",
        f"- faux acceptés : `{metadata['false_accepts']}` ;",
        f"- faux rejetés : `{metadata['false_rejects']}` ;",
        f"- durée : `{metadata['elapsed_seconds']}` s.",
        "",
        "> **Deux campagnes distinctes coexistent dans ce dépôt.** Celle-ci —",
        "> `orelia.channel-certified-adversarial-campaign/v1` — porte sur la politique",
        "> `channel-certified`. La campagne `orelia.verifier-adversarial-campaign/v1`",
        "> (10 000 invalides et 1 000 valides) porte sur le vérificateur v1 et figure",
        "> dans `VERIFIER_ADVERSARIAL_VALIDATION.md`. Les chiffres ne se contredisent",
        "> pas : ils mesurent deux objets différents.",
        "",
        "## Résultats adversariaux",
        "",
        "| Catégorie | Valide attendu | Cas | Acceptés | Rejetés | Faux acceptés | Faux rejetés | Premier contrôle correct |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            f"| {row['category']} | {row['expected_valid']} | {row['cases']} | {row['accepted']} | {row['rejected']} | {row['false_accepts']} | {row['false_rejects']} | {row['expected_first_control_hits']} |"
        )
    lines.extend([
        "",
        "Les réécritures identitaires et les jauges de Stinespring sur l'environnement sont acceptées lorsqu'elles préservent le canal réduit. Les canaux faux, arêtes interdites, ressources observables falsifiées et ordres finaux faux sont rejetés.",
        "",
        "### Ce que `outside_support_only` établit",
        "",
        "Cette famille préfixe le circuit par un élément du groupe stabilisateur de",
        "`tau_X`. Tout état du sous-espace de code en est un vecteur propre `+1` :",
        "l'action y est donc inchangée, alors que l'unitaire total diffère.",
        "",
        "C'est la seule famille de la campagne qui sépare deux spécifications :",
        "",
        "- comparaison du canal **sur le sous-espace de code** — ces artefacts doivent",
        "  être acceptés, et ils le sont ;",
        "- comparaison du **canal total** — ces mêmes artefacts devraient être rejetés.",
        "",
        "Sans elle, aucun chiffre de cette campagne ne dit laquelle des deux est",
        "implémentée. Le README affirme `on the specified input subspace` ; cette",
        "ligne du tableau est ce qui le teste.",
        "",
        "## Ressources certifiées",
        "",
        "En `channel-certified` v1, CNOT, profondeur à deux qubits, nombre de fils d'environnement, topologie et ordre final restauré sont recalculés. Les nombres de SWAP de mouvement et de restitution sont `not_certified`, faute de trace de routage rejouable.",
        "",
        "## Compatibilité",
        "",
        "`RecoveryProblem v1` et `RecoveryArtifact v1` sont inchangés. La politique historique `reproducible-route` reste la valeur par défaut. `RecoveryRunReport` passe en v2 afin d'enregistrer explicitement la politique appliquée.",
        "",
        "## Limites",
        "",
        "Ce résultat porte sur la sous-classe v1 : isométries Clifford, ancillas stabilisatrices pures, référence Petz maximally mixed et pseudo-inverse exacte sur support. Il ne certifie ni les circuits non-Clifford, ni le bruit, ni la minimalité des ressources.",
        "",
        "## Reproductibilité",
        "",
        f"- format : `{metadata['format_version']}` ;",
        f"- graine : `{metadata['seed']}` ;",
        f"- Python : `{metadata['python_version']}` ;",
        f"- NumPy : `{metadata['numpy_version']}` ;",
        f"- Stim : `{metadata['stim_version']}` ;",
        f"- noyau : `{metadata['core_version']}` ;",
        f"- hash problème : `{metadata['semantic_problem_hash']}` ;",
        f"- hash artefact : `{metadata['base_artifact_hash']}` ;",
        f"- hash vérificateur : `{metadata['verifier_sha256']}`.",
        "",
        "Commande :",
        "",
        "```bash",
        ".venv/bin/python run_channel_certified_adversarial_validation.py",
        "```",
        "",
    ])
    return "\n".join(lines)


def run(*, cases_per_category: int, results: Path, summary: Path, report: Path) -> int:
    context = load_default_context()
    started = time.perf_counter()
    rows = []
    for category, source, first in INVALID_DEFINITIONS:
        for index in range(cases_per_category):
            rows.append(_evaluate(
                context, f"invalid-{category}-{index:04d}", category, source,
                index, False, first,
            ))
    for category, source in VALID_DEFINITIONS:
        for index in range(cases_per_category):
            rows.append(_evaluate(
                context, f"valid-{category}-{index:04d}", category, source,
                index, True, "none",
            ))
    category_summary = _summary(rows)
    false_accepts = sum(row["false_accept"] for row in rows)
    false_rejects = sum(row["false_reject"] for row in rows)
    wrong_control = sum(not row["expected_control_hit"] for row in rows)
    unclean = sum(not row["clean_rejection"] for row in rows if not row["expected_valid"])
    verdict = "VALIDÉ" if not (false_accepts or false_rejects or wrong_control or unclean) else "NON VALIDÉ"
    _write_csv(results, rows)
    _write_csv(summary, category_summary)
    metadata = {
        "format_version": FORMAT_VERSION,
        "seed": CAMPAIGN_SEED,
        "cases_per_category": cases_per_category,
        "invalid_cases": cases_per_category * len(INVALID_DEFINITIONS),
        "valid_cases": cases_per_category * len(VALID_DEFINITIONS),
        "false_accepts": false_accepts,
        "false_rejects": false_rejects,
        "unexpected_first_controls": wrong_control,
        "unclean_rejections": unclean,
        "elapsed_seconds": format(time.perf_counter() - started, ".9f"),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "stim_version": getattr(stim, "__version__", "unknown"),
        "core_version": CORE_VERSION,
        "semantic_problem_hash": semantic_problem_hash(context.problem),
        "problem_document_hash": problem_document_hash(context.problem),
        "base_artifact_hash": artifact_document_hash(context.artifact),
        "verifier_sha256": _sha256(ROOT / "hayden_preskill_toy" / "recovery_verify.py"),
        "verdict": verdict,
    }
    report.write_text(_markdown(metadata, category_summary), encoding="utf-8")
    summary.with_suffix(".metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if verdict == "VALIDÉ" else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-per-category", type=int, default=100)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    if args.cases_per_category < 1:
        parser.error("--cases-per-category must be positive")
    raise SystemExit(run(
        cases_per_category=args.cases_per_category,
        results=args.results,
        summary=args.summary,
        report=args.report,
    ))


if __name__ == "__main__":
    main()
