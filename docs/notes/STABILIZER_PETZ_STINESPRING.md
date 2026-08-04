# Dilation stabilisatrice déterministe de Petz — validation t=2

## Code d’entrée extrait exactement

Les données de `stabilizer_petz_stinespring_resources.csv` sont obtenues directement du tableau symplectique du brouilleur, sans synthèse unitaire dense.

| Cas | dim supp(tau_X) | stabilisateurs indépendants | qubits logiques |
|---|---:|---:|---:|
| sans brouillage, t=1 | 32 | 0 | 5 |
| profond, t=2 | 16 | 2 | 4 |

Pour le cas profond t=2, dans l’ordre `E0,E1,E2,E3,D0,D1`, les générateurs de code sont `XIIIZI` et `IIXYIY`. Une base symplectique logique explicite est également enregistrée dans le CSV.

## Convention utilisée

La construction emploie strictement la convention calibrée dans
`CHOI_SYMPLECTIC_CONVENTIONS.md` : fils `A'|Ref|E_Petz`, image transposée sur
la référence et phases complètes (`Y^T=-Y`). Les stabilisateurs du code
d'entrée sont eux aussi signés. Aucune jauge n'a été changée pour t=2.

## Ce qui est établi

Le support de Petz est un code stabilisateur; la purification de Choi de Petz est stabilisatrice. Par la théorie des opérations stabilisatrices, le canal est réalisable avec ressources stabilisatrices, mais cela ne fournit pas automatiquement le circuit déterministe minimal ni l’identification de la sortie logique voulue.

## Étape nécessaire avant une profondeur complète

Il faut compléter les deux stabilisateurs par leurs déstabilisateurs, fixer la base logique de sortie imposée par Petz (et non une base logique arbitraire du code), puis synthétiser le tableau de l’isométrie `supp(tau_X)->A'⊗E_Petz`. Une simple préparation de Choi ou une téléportation post-sélectionnée ne satisfait pas cette exigence.

Cette réduction symplectique spécifique est donc la première étape encore non validée. Aucun coût de canal complet n’est rapporté avant sa vérification sur une base complète du support.

## Tentative de remontée par corrélations de Choi

La base logique d’entrée a été corrigée par Gram--Schmidt symplectique. Les huit corrélations Choi extraites préservent alors exactement la matrice symplectique entrée/sortie. Un tableau Clifford candidat a été construit à partir de ces images et de l’encodeur du support.

Après inclusion des phases et des stabilisateurs de support signés, le tableau
Clifford de t=2 est déterminé. L'isométrie agit de `supp(tau_X)` (quatre
qubits logiques encodés dans six fils) vers `A'|E_Petz` (quatre fils). Les deux
fils de syndrome restants sont fixes et sont rejetés après la dilatation.

La vérification est complète sur le support : les 256 opérateurs
`|i><j|`, huit superpositions aléatoires et l'état de Choi restreint ont été
comparés au Petz de Kraus. Résultats :

| Quantité | Valeur t=2 |
|---|---:|
| fidélité Petz abstrait | 0.9999999999999957 |
| fidélité du canal Clifford | 0.9999999999999928 |
| erreur opératorielle maximale | 1.98e-15 |
| fidélité du Choi après trace du syndrome | 0.9999999999999938 |
| pureté du Choi réduit | 0.9999999999999927 |
| ensembles de stabilisateurs signés du Choi | identiques |

Ainsi, pour cette instance précise, Petz admet une dilatation Clifford pure
déterministe : ni mesure de Pauli, ni post-sélection, ni feedback conditionnel
ne sont requis.

## Ressources observées, sans revendication de minimalité

Le tableau synthétisé directement contient 14 CNOT et une profondeur à deux
qubits de 12 avant routage. Un routeur explicite, non optimisé, sur la chaîne
`E0-E1-E2-E3-D0-D1` restaure la position des fils de sortie ; il emploie 28
SWAP (98 CNOT au total) et profondeur locale 84. Sa fidélité est encore
0.9999999999999928. Ce coût est celui de cette synthèse et de ce routage, pas
une borne minimale.

Le tableau comparatif t=1/t=2 est
`results/stabilizer_petz_stinespring_resources.csv`. La validation est
effectuée par `validate_petz_dilation_t2.py` sans construire de matrice
unitaire dense.
