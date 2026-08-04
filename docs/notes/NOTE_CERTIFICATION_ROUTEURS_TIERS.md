# Note — Certification indépendante de routeurs tiers

**Date :** 3 août 2026  
**Projet :** ORELIA Recovery  
**Statut :** jalon SABRE et pytket validé

## Résultat principal

ORELIA a certifié des circuits routés par deux outils tiers réels :

- Qiskit SABRE `2.5.1` ;
- pytket `2.18.1`.

Les tests portent sur les trois fixtures stabilisatrices immuables :

```text
A=1
A=8
A=12
```

Pour les six routes externes testées :

1. le circuit tiers diffère du circuit routé par ORELIA ;
2. `reproducible-route` le refuse correctement ;
3. `channel-certified` certifie exactement le canal de récupération ;
4. une phase `Z` ajoutée à la sortie provoque un rejet ;
5. une permutation finale falsifiée provoque un rejet ;
6. deux exécutions identiques produisent exactement le même artefact.

La suite complète contient <!-- TEST_COUNT:BEGIN fmt="**{passed} tests passants sur {passed}**" -->**124 tests passants sur 124**<!-- TEST_COUNT:END -->.

## Comparaison observée

| Message | ORELIA profondeur/CNOT | SABRE profondeur/CNOT | pytket profondeur/CNOT |
|---:|---:|---:|---:|
| `A=1` | 46 / 62 | 49 / 68 | **34 / 41** |
| `A=8` | **391 / 687** | 584 / 939 | 401 / 694 |
| `A=12` | 464 / **751** | 668 / 1 177 | **454** / 808 |

Ces trois cas ne permettent pas de classer généralement les routeurs.

Le résultat `A=12` illustre directement le problème :

- pytket obtient la meilleure profondeur ;
- ORELIA obtient le plus petit nombre de CNOT.

Le « meilleur » circuit dépend donc de la ressource prioritaire. Aucun score
global ne doit être publié sans fonction de coût explicite.

## Protocole SABRE

- `SabreSwap` ;
- heuristique `decay` ;
- graine `20260803` ;
- `trials=1` ;
- layout initial identité ;
- restauration de l'ordre v1 par inversion exacte des SWAP SABRE ;
- SWAP développés en trois CNOT.

## Protocole pytket

- layout initial identité avec `place_with_map` ;
- `RoutingPass` ;
- `LexiLabellingMethod` et `LexiRouteRoutingMethod` ;
- SWAP et BRIDGE décomposés exactement en CNOT ;
- restauration ajoutée uniquement lorsque la permutation nette n'est pas
  identité ;
- aucune optimisation sélectionnée après observation des résultats.

## Ce qui est démontré

Dans la sous-classe stabilisatrice v1 :

> ORELIA peut recevoir des circuits routés par des outils différents de son
> propre routeur et certifier indépendamment qu'ils réalisent le canal Petz
> demandé.

Le vérificateur n'exige donc plus une identité textuelle avec la route ORELIA.
Il contrôle le canal réduit, les phases, la topologie, les ressources
observables et l'ordre final.

## Ce qui n'est pas démontré

Cette régression ne démontre pas :

- la supériorité générale d'ORELIA, SABRE ou pytket ;
- une loi d'échelle ;
- la minimalité des profondeurs ;
- la certification des SWAP à partir du seul artefact v1 ;
- l'import de tout circuit Qiskit ou pytket ;
- la validité pour les circuits non-Clifford ;
- le comportement en présence de bruit physique.

Le circuit logique de Petz est synthétisé par ORELIA. SABRE et pytket sont ici
utilisés comme routeurs tiers, pas comme constructeurs du récupérateur.

## Signification pour le produit

La proposition devient concrète :

> Routez avec l'outil de votre choix. ORELIA vérifie indépendamment que le
> circuit obtenu réalise le récupérateur stabilisateur demandé.

Cette séparation est l'élément différenciant principal :

```text
compilateur ou routeur
        ≠
vérificateur du canal
```

Un laboratoire peut comparer plusieurs outils tout en utilisant le même
certificateur indépendant.

## Prochaine étape

Construire un benchmark reproductible multi-instance :

1. figer un corpus avant exécution ;
2. utiliser exactement les mêmes circuits logiques et topologies ;
3. conserver les résultats favorables et défavorables ;
4. enregistrer séparément profondeur, CNOT, temps et mémoire ;
5. certifier chaque circuit avec `channel-certified` ;
6. ne produire aucun classement global sans fonction de coût annoncée ;
7. faire relire le protocole et le vérificateur par une équipe universitaire.

## Fichiers associés

- `SABRE_REGRESSION_A1_A12.md` ;
- `PYTKET_REGRESSION_A1_A12.md` ;
- `results/sabre_regression_a1_a12.csv` ;
- `results/pytket_regression_a1_a12.csv` ;
- `hayden_preskill_toy/recovery_sabre.py` ;
- `hayden_preskill_toy/recovery_pytket.py` ;
- `tests/test_sabre_channel_certified.py` ;
- `tests/test_pytket_channel_certified.py`.
