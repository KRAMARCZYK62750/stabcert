# Noyau générique de compilation et de certification de récupération

Statut : **MVP interne v1 implémenté et validé sur trois fixtures figées**.

Ce travail ne modifie aucun algorithme scientifique ni aucun résultat du
modèle Hayden–Preskill fini. Il extrait du prototype un contrat générique pour
les canaux stabilisateurs purs et les récupérateurs de Petz avec
`sigma = I/d`.

## Séparation normative

```text
RecoveryProblem ──> recovery_compile ──> RecoveryArtifact
       │                                      │
       └──> recovery_verify ── cible Petz ─────┘
                 indépendante
```

Le compilateur construit la cible à partir d'une préparation stabilisatrice,
puis exécute le Clifford source. Le vérificateur ne l'importe pas : il part
des générateurs initiaux signés et les propage directement. Les deux chemins
partagent uniquement les primitives de Pauli, d'élimination sur GF(2), de
réduction stabilisatrice et de routage.

Le verdict inscrit dans l'artefact est ignoré. Le vérificateur recalcule :

- la cohérence dimensionnelle et les empreintes du problème ;
- le support signé de `tau_X` ;
- le Choi Petz cible depuis le problème ;
- le Choi du circuit routé sur une purification canonique du support ;
- l'égalité des sous-groupes stabilisateurs signés après trace de
  l'environnement ;
- les phases, l'action Clifford, le graphe de couplage, le routage, les
  ressources et la permutation finale ;
- la fidélité d'intrication annoncée.

La comparaison porte sur les Choi **réduits**. Elle accepte donc deux
dilatations de Stinespring qui diffèrent seulement par une isométrie de jauge
sur l'environnement.

## Contrats v1

`RecoveryProblem` contient uniquement les données normatives : entrée du
canal, ancillas et stabilisateurs initiaux, Clifford source, partition
accessible/inaccessible, sortie demandée, conventions Petz/Choi/transposée,
ordre des fils, graphe matériel, portes, profondeur, routeur et tolérance. Le
support de `tau_X` est dérivé ; `expected_tau_support` est une assertion
facultative non normative.

`RecoveryArtifact` contient les résultats du compilateur : support dérivé,
cible Petz annoncée, circuits logique et routé, topologie, permutation,
ressources, certificat et métriques scientifiques déterministes. Tous ces
champs restent non fiables jusqu'à vérification. Les durées, la mémoire, la
machine, l'OS, les versions et les logs sont isolés dans `RecoveryRunReport`.

Fichiers principaux :

- `hayden_preskill_toy/recovery_problem.py` ;
- `hayden_preskill_toy/recovery_artifact.py` ;
- `hayden_preskill_toy/recovery_serialization.py` ;
- `hayden_preskill_toy/recovery_compile.py` ;
- `hayden_preskill_toy/recovery_verify.py` ;
- `hayden_preskill_toy/recovery_stabilizer.py` ;
- `hayden_preskill_toy/recovery_routing.py` ;
- `schemas/recovery_problem.schema.json` ;
- `schemas/recovery_artifact.schema.json`.
- `schemas/recovery_run_report.schema.json`.

L'adaptateur `recovery_hayden_preskill_adapter.py` est séparé. Aucun nom de
registre A/B/E/D ni aucun indice fixe du modèle expérimental n'apparaît dans
le noyau.

## Canonicalisation

- JSON UTF-8, clés triées et séparateurs canoniques ;
- aucune valeur flottante JSON dans les contrats v1 : tolérances et métriques
  sont des chaînes décimales finies ;
- ordre des qubits toujours explicite ;
- Pauli sous forme `I/X/Y/Z` avec phase `i^k`, `k modulo 4` ;
- arêtes non dirigées triées et graphe connexe ;
- préfixes de domaine SHA-256 distincts.

`semantic_problem_hash` exclut seulement les métadonnées et l'assertion
facultative de support. `document_hash` couvre la représentation canonique
complète du document, métadonnées incluses. Un hash séparé est disponible pour
chaque circuit.

## Fixtures immuables

| Fixture | A | graine | profondeur brouilleur | t | topologie | profondeur logique/routée | CNOT logique/routé | SWAP mouvement/restauration |
|---|---:|---:|---:|---:|---|---:|---:|---:|
| a1 | 1 | 20260802 | 6 | 2 | chaîne | 12 / 46 | 14 / 62 | 12 / 4 |
| a8 | 8 | 20260802 | 6 | 8 | chaîne | 82 / 391 | 111 / 687 | 143 / 49 |
| a12 | 12 | 20260802 | 6 | 14 | grille 2D | 154 / 464 | 229 / 751 | 148 / 26 |

Pour les trois cas, les circuits, supports, cibles signées, ressources et
permutations sont exactement égaux au chemin historique. Les fichiers sont
dans `tests/fixtures/recovery_v1/`, avec leurs empreintes dans `manifest.json`.

Un test lance la compilation dans un processus neuf qui interdit les imports
expérimentaux, écrit l'artefact, puis lance la vérification dans un second
processus qui interdit en plus l'import du compilateur.

Le CLI, ses codes de sortie, le déterminisme byte-à-byte et le paquet
`verifier-only` sont documentés dans `RECOVERY_CLI_TRUST_MODEL.md`.

## Domaine et limites

La v1 couvre les isométries Clifford avec ancillas stabilisatrices pures, la
référence Petz maximally mixed et la pseudo-inverse exacte sur support
stabilisateur. Elle ne couvre pas encore les environnements mixtes, les canaux
non stabilisateurs, le bruit non uniforme, les mesures/feedback généraux ni
les approximations numériques de synthèse.

Le vérificateur est indépendant au niveau des constructions centrales, mais
utilise les mêmes primitives Stim et GF(2). Il s'agit d'une vérification
algorithmique reproductible, pas d'une preuve formelle dans un assistant de
preuve et pas d'une garantie cryptographique. Le routeur demeure une
heuristique déterministe ; les profondeurs ne sont pas annoncées minimales.

Aucun résultat de ce document ne constitue une simulation réelle de trou
noir, une solution du paradoxe de l'information ou un système de chiffrement.
