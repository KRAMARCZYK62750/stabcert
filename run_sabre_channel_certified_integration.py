#!/usr/bin/env python3
"""Produce the first independently certified Qiskit SABRE route."""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import time

from hayden_preskill_toy.recovery_artifact import CircuitSpec
from hayden_preskill_toy.recovery_problem import GateSpec
from hayden_preskill_toy.recovery_sabre import artifact_with_sabre_route
from hayden_preskill_toy.recovery_serialization import (
    artifact_document_hash,
    canonical_json_bytes,
    read_artifact,
    read_problem,
    write_artifact,
)
from hayden_preskill_toy.recovery_verify import verify_recovery


ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "tests" / "fixtures" / "recovery_v1"
RESULTS = ROOT / "results"
REPORT = ROOT / "SABRE_CHANNEL_CERTIFIED_INTEGRATION.md"


def _failed(report) -> list[str]:
    return [item.name for item in report.checks if not item.passed]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    problem = read_problem(FIXTURES / "a1.problem.json")
    base = read_artifact(FIXTURES / "a1.artifact.json")
    started = time.perf_counter()
    sabre, routing = artifact_with_sabre_route(problem, base)
    elapsed = time.perf_counter() - started

    phase_gates = (
        *sabre.routed_circuit.gates,
        GateSpec("Z", (problem.requested_output[0],)),
    )
    phase_mutation = replace(
        sabre,
        routed_circuit=CircuitSpec(problem.accessible_partition, phase_gates),
    )
    shifted = (*sabre.final_permutation[1:], sabre.final_permutation[0])
    permutation_mutation = replace(sabre, final_permutation=shifted)

    strict = verify_recovery(problem, sabre)
    channel = verify_recovery(problem, sabre, policy="channel-certified")
    phase = verify_recovery(problem, phase_mutation, policy="channel-certified")
    permutation = verify_recovery(
        problem, permutation_mutation, policy="channel-certified"
    )
    assertions = {
        "route_differs_from_orelia": sabre.routed_circuit.gates != base.routed_circuit.gates,
        "reproducible_route_rejects_sabre": not strict.verified,
        "channel_certified_accepts_sabre": channel.verified,
        "phase_mutation_rejected": not phase.verified and not phase.channel_verified,
        "permutation_mutation_rejected": not permutation.verified
        and not permutation.final_order_verified,
    }
    if not all(assertions.values()):
        raise AssertionError(f"SABRE integration assertion failed: {assertions}")

    RESULTS.mkdir(parents=True, exist_ok=True)
    sabre_path = RESULTS / "sabre_a1.artifact.json"
    phase_path = RESULTS / "sabre_a1_phase_mutation.artifact.json"
    permutation_path = RESULTS / "sabre_a1_permutation_mutation.artifact.json"
    write_artifact(sabre_path, sabre)
    write_artifact(phase_path, phase_mutation)
    write_artifact(permutation_path, permutation_mutation)

    summary = {
        "format_version": "orelia.sabre-channel-certified-integration/v1",
        "fixture": "a1",
        "qiskit_version": routing.qiskit_version,
        "seed": routing.seed,
        "heuristic": routing.heuristic,
        "trials": routing.trials,
        "elapsed_seconds": format(elapsed, ".9f"),
        "assertions": assertions,
        "orelia_resources": asdict(base.resources),
        "sabre_resources": asdict(sabre.resources),
        "qiskit_routing_permutation": routing.qiskit_routing_permutation,
        "final_wire_at_site_before_restoration": routing.final_wire_at_site_before_restoration,
        "final_wire_at_site": routing.final_wire_at_site,
        "strict_failed_checks": _failed(strict),
        "channel_failed_checks": _failed(channel),
        "phase_mutation_failed_checks": _failed(phase),
        "permutation_mutation_failed_checks": _failed(permutation),
        "orelia_artifact_hash": artifact_document_hash(base),
        "sabre_artifact_hash": artifact_document_hash(sabre),
        "phase_mutation_artifact_hash": artifact_document_hash(phase_mutation),
        "permutation_mutation_artifact_hash": artifact_document_hash(permutation_mutation),
    }
    summary_path = RESULTS / "sabre_channel_certified_integration.json"
    summary_path.write_bytes(canonical_json_bytes(summary) + b"\n")

    lines = [
        "# Intégration SABRE avec `channel-certified`",
        "",
        "## Verdict",
        "",
        "**VALIDÉ sur la fixture A=1.**",
        "",
        "Qiskit SABRE a routé le circuit Clifford logique de Petz avec un layout initial fixé. La route obtenue est différente de la route ORELIA historique. L'ordre v1 a été restauré en rejouant en sens inverse les SWAP explicitement insérés par SABRE.",
        "",
        "| Test | Résultat |",
        "|---|---:|",
        "| Circuit SABRE différent du circuit ORELIA | oui |",
        "| `reproducible-route` sur SABRE | rejeté |",
        "| `channel-certified` sur SABRE | accepté |",
        "| Mutation de phase `Z` sur la sortie | rejetée |",
        "| Mutation de permutation finale | rejetée |",
        "",
        "## Configuration figée",
        "",
        f"- Qiskit : `{routing.qiskit_version}` ;",
        f"- graine SABRE : `{routing.seed}` ;",
        f"- heuristique : `{routing.heuristic}` ;",
        f"- essais SABRE : `{routing.trials}` ;",
        "- layout initial : identité sur l'ordre physique de `RecoveryProblem` ;",
        "- restauration : inverse exact de la séquence de SWAP SABRE ;",
        "- SWAP : expansion normative en trois CNOT ;",
        f"- durée de construction mesurée : `{elapsed:.9f}` s.",
        "",
        "## Ressources observées",
        "",
        "| Route | Profondeur 2Q | CNOT | SWAP mouvement | SWAP restitution |",
        "|---|---:|---:|---:|---:|",
        f"| ORELIA | {base.resources.routed_depth} | {base.resources.routed_cnot} | {base.resources.movement_swaps} | {base.resources.restoration_swaps} |",
        f"| SABRE + restauration v1 | {sabre.resources.routed_depth} | {sabre.resources.routed_cnot} | {sabre.resources.movement_swaps} | {sabre.resources.restoration_swaps} |",
        "",
        "Ces nombres décrivent une seule instance et ne constituent pas encore un benchmark. En politique `channel-certified`, les CNOT et la profondeur sont recalculés, mais le découpage des SWAP reste déclaré `not_certified` faute de trace normative dans `RecoveryArtifact v1`.",
        "",
        "## Contrôles négatifs",
        "",
        f"- route SABRE en politique stricte : `{', '.join(_failed(strict))}` ;",
        f"- mutation de phase : `{', '.join(_failed(phase))}` ;",
        f"- mutation de permutation : `{', '.join(_failed(permutation))}`.",
        "",
        "## Portée exacte",
        "",
        "Ce test montre qu'ORELIA peut certifier une route produite par un véritable routeur tiers. Il ne montre pas encore qu'ORELIA importe tout circuit Qiskit, que SABRE est meilleur ou moins bon, ni que le résultat s'étend au non-Clifford.",
        "",
        "Le circuit logique de Petz reste synthétisé par ORELIA ; SABRE intervient ici uniquement pour le placement implicite initial fixé et le routage.",
        "",
        "## Références d'interface",
        "",
        "- Documentation IBM sur les méthodes de routage et la reproductibilité : https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.4/transpiler",
        "- Documentation IBM sur les permutations de layout : https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.4/qiskit.transpiler.TranspileLayout",
        "",
        "## Artefacts",
        "",
        f"- `{sabre_path.relative_to(ROOT)}` — `{artifact_document_hash(sabre)}` ;",
        f"- `{phase_path.relative_to(ROOT)}` — `{artifact_document_hash(phase_mutation)}` ;",
        f"- `{permutation_path.relative_to(ROOT)}` — `{artifact_document_hash(permutation_mutation)}` ;",
        f"- `{summary_path.relative_to(ROOT)}` — `{_sha256(summary_path)}`.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
