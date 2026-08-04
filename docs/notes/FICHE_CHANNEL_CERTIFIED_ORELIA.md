# Fiche — ORELIA `channel-certified`

## Objet

ORELIA peut vérifier qu'un circuit Clifford routé réalise exactement le canal
de récupération de Petz défini par un problème stabilisateur v1, sans exiger
que ce circuit ait été produit par le routeur ORELIA ni qu'il soit
textuellement identique au circuit de référence.

La question certifiée est :

> Le circuit candidat réalise-t-il le canal réduit demandé, avec les bonnes
> phases, sur la topologie et dans l'ordre de fils déclarés ?

## Deux politiques distinctes

### `reproducible-route`

- politique historique et politique par défaut ;
- reconstruit la route déterministe ORELIA ;
- exige l'égalité avec cette route ;
- certifie aussi les nombres de SWAP produits par ce routage.

### `channel-certified`

- évalue directement un circuit candidat non fiable ;
- reconstruit indépendamment la cible Petz depuis `RecoveryProblem` ;
- accepte une autre synthèse, une autre route ou une autre jauge de
  Stinespring si le canal réduit est exactement le même ;
- ne fait pas confiance au verdict annoncé dans l'artefact.

## Contrôles indépendants

Le vérificateur contrôle :

- les empreintes sémantique et documentaire du problème ;
- le support stabilisateur signé de `tau_X` ;
- la convention Choi `A' | Ref | E_Petz` ;
- la transposition sur la référence, notamment `Y^T = -Y` ;
- l'égalité canonique des Choi réduits signés ;
- l'action logique complète et les phases Pauli ;
- les portes autorisées et le graphe de couplage ;
- l'ordre final restauré des fils ;
- les ressources directement recalculables ;
- la fidélité d'intrication annoncée.

L'égalité des Choi réduits rend la certification indépendante d'une
transformation agissant uniquement sur l'environnement rejeté.

## Résultats acquis

État au 3 août 2026 :

- suite automatique après régressions SABRE et pytket : <!-- TEST_COUNT:BEGIN fmt="**{passed}/{passed} tests passants**" -->**124/124 tests passants**<!-- TEST_COUNT:END --> ;
- fixtures immuables validées : `A=1`, `A=8`, `A=12` ;
- artefacts adversariaux invalides : **1 300/1 300 rejetés** ;
- représentations valides équivalentes : **800/800 acceptées** ;
- dont `outside_support_only` : **100/100 acceptées** — la famille qui sépare
  la comparaison sur le sous-espace de code de celle du canal total ;
- faux acceptés observés : **0** ;
- faux rejetés observés : **0** ;
- exceptions non contrôlées pendant la campagne : **0**.

Cette qualification est locale au corpus documenté. Elle ne constitue pas une
garantie générale de sécurité ni une preuve formelle d'absence de défaut.

**Ce que cette réserve qualifie, et ce qu'elle ne qualifie pas.** Elle porte
sur l'implémentation, pas sur la procédure de décision. La correction de
celle-ci est un théorème : deux canaux stabilisateurs sont égaux sur le
sous-espace de code si et seulement si leurs formes canoniques signées
coïncident — c'est ce qu'affirme le README. La campagne adversariale teste le
code qui réalise cette procédure ; aucun corpus fini ne prouve l'absence d'un
défaut d'implémentation. Les deux énoncés portent sur des objets différents et
ne se contredisent pas.

Les nombres 1 300 / 800 sont ceux de la campagne
`orelia.channel-certified-adversarial-campaign/v1` (3 août 2026). Une seconde
campagne, `orelia.verifier-adversarial-campaign/v1` (même date, 10 000
invalides et 1 000 valides), porte sur le vérificateur v1 et figure dans
`VERIFIER_ADVERSARIAL_VALIDATION.md`. Deux objets distincts, deux corpus
distincts.

## Ressources et limite des SWAP

Le mode recalcule directement :

- les CNOT logiques et physiques ;
- les portes à un qubit ;
- la profondeur en couches de portes à deux qubits ;
- la distance maximale des interactions ;
- le nombre de qubits d'environnement ;
- la conformité à la topologie.

Dans `RecoveryArtifact v1`, les SWAP sont décomposés en CNOT. Sans trace de
routage rejouable, leur rôle ne peut pas être reconstruit de façon unique :

```text
swap_accounting_status = not_certified
```

Une future preuve de routage explicite permettra de certifier séparément les
SWAP de mouvement et de restitution.

## Périmètre scientifique exact

La version actuelle couvre :

- les isométries Clifford ;
- les ancillas stabilisatrices pures ;
- la référence Petz `I/d` ;
- la pseudo-inverse exacte sur le support stabilisateur ;
- les portes `H`, `S`, `X`, `Z` et `CNOT` ;
- une topologie explicite, sans bruit physique.

Elle ne couvre pas encore :

- les circuits non-Clifford généraux ;
- les références Petz arbitraires ;
- le bruit matériel ;
- les instruments généraux avec mesures et feedback ;
- la preuve de minimalité de la profondeur ;
- la certification des SWAP sans trace de routage.

## Interface

Route ORELIA reproductible :

```bash
orelia-recovery verify problem.json artifact.json \
  --policy reproducible-route
```

Circuit candidat externe :

```bash
orelia-recovery verify problem.json candidate-artifact.json \
  --policy channel-certified
```

Le verdict distingue :

```text
channel_verified
topology_verified
logical_action_verified
final_order_verified
resource_counts_verified
swap_accounting_status
overall_verdict
```

## Intérêt universitaire et industriel

Un laboratoire peut utiliser son propre compilateur ou routeur, puis demander
à ORELIA de vérifier le résultat sans faire confiance à l'outil qui l'a
produit :

```text
problème stabilisateur
        ↓
compilateur ou routeur quelconque
        ↓
circuit candidat non fiable
        ↓
vérificateur ORELIA indépendant
        ↓
canal certifié ou rejet documenté
```

ORELIA ne remplace donc pas nécessairement SABRE, pytket ou un compilateur de
laboratoire. Il peut fournir une vérification indépendante commune pour
comparer leurs résultats sur la même cible mathématique.

## Prochaine étape

L'adaptateur SABRE est validé sur les fixtures `A=1`, `A=8` et `A=12` : chaque
route externe est refusée par `reproducible-route`, acceptée par
`channel-certified`, puis rejetée après mutation de phase ou de permutation.

L'adaptateur pytket est validé avec exactement les mêmes fixtures et contrôles.

1. figer le format d'import déterministe des circuits externes ;
2. comparer ORELIA, SABRE et pytket sur un corpus multi-instance figé ;
3. séparer profondeur, CNOT, SWAP déclarés, temps et mémoire ;
4. préparer un paquet `verifier-only` v0.3 pour un test extérieur ;
5. soumettre ensuite l'outil et le protocole à une équipe universitaire.

Il ne faut pas encore conclure qu'ORELIA route mieux que SABRE ou pytket. Le
prochain objectif est une comparaison reproductible et certifiée.

## Documents associés

- `CHANNEL_CERTIFIED_MODE_SPEC.md` ;
- `CHANNEL_CERTIFIED_IMPLEMENTATION.md` ;
- `RECOVERY_CORE_ARCHITECTURE.md` ;
- `RECOVERY_CLI_TRUST_MODEL.md` ;
- `VERIFIER_ADVERSARIAL_VALIDATION.md` ;
- `SABRE_CHANNEL_CERTIFIED_INTEGRATION.md` ;
- `SABRE_REGRESSION_A1_A12.md` ;
- `PYTKET_REGRESSION_A1_A12.md` ;
- `results/channel_certified_adversarial.csv`.
