# Message collectif de deux qubits

## Construction

Cette expérience utilise une seule dynamique Clifford collective sur
`A0,A1,B0,B1,B2,B3`. Les deux qubits-message sont chacun initialement intriqués
avec un qubit de référence, puis les deux font partie du même brouilleur. Le
graphe des CNOT de la graine 20260802 est connecté sur les six qubits
brouillés. Il ne s'agit donc pas de deux usages indépendants assemblés après
le calcul.

Configuration : `|A|=2`, `|B|=|E|=4`, 12 qubits
simulés, profondeur de brouillage 6. La compilation
complète est évaluée à `t=3`, avant l'émission totale
(`t=6`).

## Disponibilité et Petz abstrait

| t | I(R:C) bits | distance en trace | fidélité Petz | rang supp(tau_X) |
|---:|---:|---:|---:|---:|
| 0 | 4 | 0.9375 | 0.0624999999999997 | 16 |
| 1 | 3 | 0.875 | 0.125 | 16 |
| 2 | 1 | 0.5 | 0.499999999999998 | 32 |
| 3 | 8.881784197e-15 | 5.55111512313e-17 | 0.999999999999997 | 32 |
| 4 | 1.33226762955e-14 | 1.38777878078e-15 | 0.999999999999998 | 16 |
| 5 | 4.4408920985e-15 | 1.66533453694e-16 | 0.999999999999988 | 8 |
| 6 | 0 | 0 | 0.999999999999999 | 4 |

À `t=3`, `I(R:C)=8.88e-15` et la
distance en trace vaut `5.55e-17`.
Ce sont des indicateurs quantitatifs de découplage dans ce modèle fini ; ils ne
constituent pas une équivalence générale sans borne.

## Canal collectif construit

Le support d'entrée a le rang 32, soit
5 qubits logiques et
2 stabilisateurs indépendants. La dilatation
rejette 3 qubits d'environnement.

| réalisation | fidélité d'intrication | fidélité Choi | erreur opératorielle | profondeur 2q | CNOT | SWAP |
|---|---:|---:|---:|---:|---:|---:|
| Petz abstrait | 0.999999999999997 | 1 | 0 |  |  |  |
| Clifford direct | 0.999999999999991 | 0.99999999999999 | 3.95e-15 | 31 | 40 | 0 |
| Clifford route chaine | 0.999999999999991 | 0.99999999999999 | 3.95e-15 | 136 | 196 | 52 |

La chaîne physique est `8-9-10-11-2-3-4` et sa permutation finale
est restituée exactement. Le routage multiplie ici la profondeur observée par
`4.387`.

## États vérifiés

La base complète `|00>`, `|01>`, `|10>`, `|11>`, deux superpositions avec
intrication ou phase relative, la superposition uniforme et un état complexe
aléatoire ont été transmis. Les fidélités minimales sont :

- Petz abstrait : `0.999999999999996` ;
- Clifford direct : `0.999999999999991` ;
- Clifford routé : `0.999999999999991`.

La validation opératorielle porte en plus sur toute la base d'opérateurs du
support d'entrée, pas seulement sur ces états exemples.

## Limites

Il s'agit d'une instance Clifford idéale, sans bruit, avec B=4 et une seule
graine. Cette réussite ne fournit ni loi d'échelle, ni profondeur minimale, ni
résultat sur un message classique long. Elle établit seulement que le pipeline
paramétrique sait traiter un message de deux qubits réellement brouillé et
récupéré collectivement. Aucun calcul `|A|=3` n'a été lancé.
