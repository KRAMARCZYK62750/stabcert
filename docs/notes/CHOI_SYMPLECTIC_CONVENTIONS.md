# Conventions Choi–symplectiques : calibration signée

## Portée

Ce document calibre la reconstruction symplectique sur le contrôle exact
« sans brouillage, `t=1` ». Il ne synthétise pas le cas profond `t=2` et ne
rapporte aucune profondeur pour ce cas. Les calculs emploient des chaînes de
Pauli **signées** de Stim, et non seulement les vecteurs binaires `(x|z)`.

## Convention retenue

Pour une dilatation de Kraus `V = sum_j K_j tensor |j>_E`, le vecteur de Choi
normalisé est

```text
|J_V> = 1/sqrt(d_X) sum_(a,j) K_j|a>_(A') |a>_Ref |j>_(E_Petz).
```

L'ordre big-endian des fils est donc `A' | Ref | E_Petz`. La relation utilisée
est exactement

```text
(M tensor I)|Phi> = (I tensor M^T)|Phi>,
```

et, par conséquent,

```text
(V P V^dagger tensor P^T)|J_V> = |J_V>.
```

Pour un Pauli hermitien tensoriel, `P^T = (-1)^(nombre de Y) P`. Le même signe
apparaît avec la conjugaison complexe dans cette base (`P*=P^T`); ces deux
variantes ne se distinguent donc pas sur les seuls Paulis hermitiens. Elles ne
sont pas deux conventions concurrentes ici : elles sont la même opération sur
la base auditée.

Les phases sont stockées comme un signe `+/-` devant chaque Pauli. Une matrice
symplectique seule ne contient pas cette donnée : elle fixe les commutations,
mais pas l'action `U P U^dagger = (-1)^s P'`.

## Contrôle sans brouillage, t=1

Le Petz déterministe connu est la permutation qui déplace `D0` vers `E0` par
quatre SWAP voisins sur la chaîne `E0-E1-E2-E3-D0` (12 CNOT). La reconstruction
Choi signée donne les mêmes images :

```text
X_E0 -> X_E1, ..., X_E3 -> X_D0, X_D0 -> X_E0,
Z_E0 -> Z_E1, ..., Z_E3 -> Z_D0, Z_D0 -> Z_E0,
```

avec signe `+` dans chaque cas. Le tableau symplectique et son vecteur de
phases coïncident donc avec le tableau Clifford connu. Le circuit reconstruit
obtient `F_e = 0.9999999999999984` (erreur d'arrondi), soit 1 à la précision
machine.

Les comparaisons par générateur, y compris `X`, `Y` et `Z`, sont dans
[`results/choi_convention_generator_comparison.csv`](results/choi_convention_generator_comparison.csv).
Le premier point de divergence est `Y` sur le premier fil : la lecture directe
prédit `-Y` au lieu de `+Y`, car elle omet `Y^T=-Y`. Elle peut néanmoins donner
une fidélité 1 sur ce contrôle si l'on ne reconstruit qu'à partir de `X,Z` :
c'est précisément pourquoi ce test de phase est nécessaire.

| Lecture des corrélations Choi | Tableau signé | Fidélité de contrôle | Décision |
| --- | --- | ---: | --- |
| directe, `P_Ref` | faux dès `Y_1` | 1 sur la base X/Z seulement | rejetée |
| transposée, `P_Ref^T` | exact | 1 | retenue |
| conjuguée, `P_Ref*` | identique sur les Paulis | 1 | équivalente ici |
| symplectique inverse | mauvaise direction | 0.25 | rejetée |

Les valeurs sont exportées dans
[`results/choi_convention_fidelity.csv`](results/choi_convention_fidelity.csv).
L'inverse est exclu indépendamment : il envoie le message loin de `E0` et
retombe au plancher de Bell `1/4`.

## Réapplication limitée à t=2

La convention retenue a été réappliquée **uniquement** à l'extraction des
images logiques de l'instance profonde (`layers=6`, `t=2`). Les signes ne sont
pas tous triviaux : par exemple les images extraites de `Z2`, `X3`, `Z3` et
`Z4` portent un signe négatif. Elles figurent dans
[`results/petz_logical_action_layers6_t2.csv`](results/petz_logical_action_layers6_t2.csv).

La forme symplectique binaire entrée/sortie y est égale, mais ce constat ne
valide pas encore une dilatation : la construction du tableau complet doit
incorporer ces phases, les stabilisateurs de support eux-mêmes signés, et être
vérifiée sur une base complète d'opérateurs après trace de l'environnement.
La synthèse t=2 et toute mesure de profondeur restent donc suspendues.

## Contrôles automatisés

`tests/test_choi_symplectic_conventions.py` vérifie que la convention
transposée reproduit le contrôle signé, que la lecture directe échoue sur les
phases, et que l'inverse donne une fidélité strictement inférieure à `0.251`.
La suite complète contient actuellement 13 tests.
