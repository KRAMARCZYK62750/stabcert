# Note de jalon — Première certification d'une route SABRE

**Date :** 3 août 2026  
**Projet :** ORELIA Recovery  
**Statut :** régression validée sur `A=1`, `A=8` et `A=12`

## Résumé

ORELIA a certifié avec succès un circuit routé par Qiskit SABRE qui diffère du
circuit produit par le routeur ORELIA.

Le test établit, sur l'instance considérée, que le vérificateur ne contrôle pas
seulement la reproduction de son propre compilateur. Il peut évaluer un circuit
tiers et décider indépendamment s'il réalise le canal de récupération de Petz
demandé.

## Test décisif

| Expérience | Verdict attendu | Verdict obtenu |
|---|---:|---:|
| Route ORELIA avec `reproducible-route` | acceptée | acceptée |
| Route SABRE différente avec `reproducible-route` | rejetée | rejetée |
| Route SABRE avec `channel-certified` | acceptée | acceptée |
| Route SABRE avec phase `Z` ajoutée sur la sortie | rejetée | rejetée |
| Route SABRE avec permutation finale falsifiée | rejetée | rejetée |

La suite complète contient désormais <!-- TEST_COUNT:BEGIN fmt="**{passed} tests passants sur {passed}**" -->**124 tests passants sur 124**<!-- TEST_COUNT:END -->.

## Résultat technique

Configuration :

- Qiskit `2.5.1` ;
- algorithme `SabreSwap` ;
- heuristique `decay` ;
- graine `20260803` ;
- un essai SABRE ;
- layout initial fixé à l'ordre physique du problème ;
- ordre final restauré par inversion exacte des SWAP insérés par SABRE ;
- SWAP développés en trois CNOT.

Ressources observées :

| Route | Profondeur deux-qubits | CNOT | SWAP mouvement | SWAP restitution |
|---|---:|---:|---:|---:|
| ORELIA | 46 | 62 | 12 | 4 |
| SABRE avec restauration v1 | 49 | 68 | 9 | 9 |

Ces nombres portent sur une seule instance. Ils ne permettent pas de conclure
qu'un routeur est généralement meilleur que l'autre.

## Extension de la régression

Le protocole a ensuite été rejoué sans modification sur les fixtures `A=8` et
`A=12` :

| A | Profondeur ORELIA | Profondeur SABRE | CNOT ORELIA | CNOT SABRE | Canal certifié |
|---:|---:|---:|---:|---:|---:|
| 1 | 46 | 49 | 62 | 68 | oui |
| 8 | 391 | 584 | 687 | 939 | oui |
| 12 | 464 | 668 | 751 | 1 177 | oui |

Pour les trois tailles :

- la route SABRE diffère de la route ORELIA ;
- `reproducible-route` la refuse ;
- `channel-certified` l'accepte ;
- la mutation de phase est rejetée ;
- la permutation falsifiée est rejetée ;
- deux exécutions à paramètres identiques produisent exactement le même
  artefact.

SABRE est plus coûteux sur ces trois fixtures avec la restauration v1
conservatrice. Ce résultat n'établit aucune supériorité générale d'ORELIA.

## Ce qui est démontré

Pour cette instance stabilisatrice Clifford :

1. SABRE produit une route réellement différente ;
2. le mode historique détecte qu'elle ne provient pas du routeur ORELIA ;
3. le mode `channel-certified` établit néanmoins l'égalité exacte du canal
   réduit avec la cible Petz reconstruite indépendamment ;
4. les phases et l'ordre final des fils participent effectivement au verdict ;
5. une altération plausible n'est pas acceptée sous prétexte que la topologie
   reste valide.

## Ce qui n'est pas démontré

Ce jalon ne démontre pas :

- qu'ORELIA accepte encore tous les résultats SABRE sur d'autres tailles ;
- qu'ORELIA ou SABRE possède la meilleure heuristique de routage ;
- que les profondeurs observées sont minimales ;
- que tout circuit Qiskit peut déjà être importé ;
- que le système couvre les circuits non-Clifford ou le bruit physique ;
- que les nombres de SWAP sont certifiés depuis le seul artefact v1.

Le circuit logique de Petz reste synthétisé par ORELIA. SABRE intervient ici
uniquement comme routeur tiers.

## Signification pour le produit

La proposition suivante possède maintenant un premier exemple exécuté et
reproductible :

> Un outil tiers route le circuit. ORELIA vérifie indépendamment que le circuit
> physique obtenu réalise bien le canal de récupération stabilisateur demandé.

La valeur différenciante n'est donc pas seulement le routeur ORELIA. C'est la
séparation entre :

```text
production du circuit
        ≠
certification du canal obtenu
```

## Décision suivante

Les régressions SABRE et pytket `A=1/8/12` sont terminées. La prochaine étape
autorisée est :

1. figer le contrat d'import des circuits tiers ;
2. construire un benchmark comparatif multi-instance ;
3. conserver séparément profondeur, CNOT, temps et mémoire ;
4. ne produire aucun classement global sans fonction de coût explicitée.

## Fichiers de preuve

- `SABRE_CHANNEL_CERTIFIED_INTEGRATION.md` ;
- `results/sabre_a1.artifact.json` ;
- `results/sabre_a1_phase_mutation.artifact.json` ;
- `results/sabre_a1_permutation_mutation.artifact.json` ;
- `results/sabre_channel_certified_integration.json` ;
- `tests/test_sabre_channel_certified.py`.
- `SABRE_REGRESSION_A1_A12.md` ;
- `results/sabre_regression_a1_a12.csv` ;
- `results/sabre_regression_a1_a12.json`.
- `PYTKET_REGRESSION_A1_A12.md` ;
- `results/pytket_regression_a1_a12.csv` ;
- `results/pytket_regression_a1_a12.json`.
