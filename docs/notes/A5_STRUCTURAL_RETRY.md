# Nouvelle tentative collective |A|=5 — compilateur structurel

Statut : **validated** sous le budget fixe de
120 s et 1024 Mio RSS.

## Instance

- message collectif : 5 qubits, dimension 32 ;
- B=4, graine 20260802, profondeur de
  brouillage 6, t=5 ;
- rang du support numérique/stabilisateur :
  512/512 ;
- qubits logiques du support : 9 ;
- qubits d'environnement de la dilatation : 0.

## Fidélités et certificat

| objet | valeur |
|---|---:|
| Petz abstrait | 0.999999999999998 |
| circuit Clifford direct | 0.999999999999988 |
| circuit Clifford routé | 0.999999999999988 |
| fidélité Choi directe certifiée | 1.0 |
| fidélité Choi routée certifiée | 1.0 |

Le certificat compare exactement 18
générateurs signés de la purification Choi cible et synthétisée. Dans la jauge
fixée, les purifications coïncident, donc `W_E=I` et les Choi réduits sont égaux
après trace de l'environnement : `True`.

Les anciennes énumérations de 262144 éléments de
groupe et 262144 opérateurs du support sont
évitées. Éléments/opérateurs effectivement énumérés :
0/0.

Dimensions GF(2) : noyau support
`18 variables / 18
contraintes / rang 18 / dimension
0` ; centralisateur
`18` ; quotient logique
`18`. Le solveur Choi utilise
`18` variables, un rang
`18` et un noyau affine de dimension
`0`. Les calculs ont résolu
1157 systèmes et effectué
1119059 XOR scalaires instrumentés dans les éliminations
de lignes.

## Coût construit

| réalisation | profondeur 2q | CNOT | SWAP |
|---|---:|---:|---:|
| Clifford direct | 43 | 51 | 0 |
| chaîne locale | 249 | 381 | 110 |

Ordre final restauré : `True` ; équivalence Clifford
direct/routé : `True`.

## Temps et mémoire

| étape | secondes |
|---|---:|
| canal | 0.852969 |
| Petz abstrait | 0.061711 |
| code support | 0.092593 |
| synthèse | 1.306680 |
| certification directe | 0.760058 |
| routage | 0.000411 |
| certification routée | 0.858374 |
| total | 4.037730 |

RSS maximale : 244.0 Mio. Premier nouveau goulot :
`none_within_fixed_budget`.

## Portée

Ce résultat porte sur une instance Clifford idéale unique. Le certificat sur
générateurs remplace exactement les énumérations dans cette sous-classe ; il ne
constitue ni une loi d'échelle, ni une borne de complexité minimale. Aucun test
A=6 n'est lancé.
