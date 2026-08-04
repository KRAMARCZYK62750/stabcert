# Pré-vol structurel collectif |A|=8

Statut : **validé**.
Instance unique, B=4, budget 120 s / 1024 Mio.
Aucune campagne et aucun A=9 ne sont lancés.

## Chronologie

| t | I(R:C) | distance trace | fidélité Petz | rang support | secondes |
|---:|---:|---:|---:|---:|---:|
| 0 | 16 | 0.999984741211 | 1.52587890625e-05 | 16 | 0.0227 |
| 1 | 14 | 0.999938964844 | 6.103515625e-05 | 32 | 0.0282 |
| 2 | 12 | 0.999755859375 | 0.000244140625 | 64 | 0.0372 |
| 3 | 10 | 0.9990234375 | 0.0009765625 | 128 | 0.0506 |
| 4 | 8 | 0.99609375 | 0.00390625 | 256 | 0.0704 |
| 5 | 6 | 0.984375 | 0.015625 | 512 | 0.0976 |
| 6 | 4 | 0.9375 | 0.0625 | 1024 | 0.1332 |
| 7 | 2 | 0.75 | 0.25 | 2048 | 0.1827 |
| 8 | 0 | 0 | 1 | 4096 | 0.2448 |
| 9 | 0 | 0 | 1 | 2048 | 0.3011 |
| 10 | 0 | 0 | 1 | 1024 | 0.3615 |
| 11 | 0 | 0 | 1 | 512 | 0.3985 |
| 12 | 0 | 0 | 1 | 256 | 0.4260 |

Le premier temps favorable est `t=8` :
`I(R:C)=0`, distance
`0.0` et rang du support
`4096`.

## Canal construit et certifié

- fidélité Petz : `1.0` ;
- fidélité directe : `1.0` ;
- fidélité routée : `1.0` ;
- Choi réduits égaux : `True` ;
- phases signées validées : `True` ;
- générateurs Choi signés : 24 ;
- profondeur : `82 -> 572` ;
- CNOT : `111 -> 1041` ;
- SWAP : `310`.

## Alphabet de 256 états de base

Les 256 états ne sont pas énumérés. L'égalité du Choi réduit signé et la
fidélité d'intrication égale à 1 certifient l'identité du canal composé sur tout
l'espace de dimension 256. États certifiés collectivement :
`256` ; états parcourus :
`0`.

La démonstration visuelle conserve les données primaires :
`10101101 = 173`; `😀` est seulement une étiquette d'affichage.

| état représentatif | fidélité certifiée | phase complexe | état dense construit |
|---|---:|---:|---:|
| \|10101101> | 1.0 | False | False |
| (\|00000000>+\|11111111>)/sqrt(2) | 1.0 | False | False |
| (\|00000001>+i\|11111110>)/sqrt(2) | 1.0 | True | False |
| ((\|0>+i\|1>)/sqrt(2))^tensor8 | 1.0 | True | False |

Ces lignes sont des corollaires du certificat du canal complet, pas quatre
simulations indépendantes.

## Budget et constructions

- chronologie : `2.355 s` ;
- synthèse, certification et routage :
  `1.933 s` ;
- total : `4.298 s` ;
- RSS maximale : `40.6 Mio` ;
- marge mémoire : `983.4 Mio` ;
- chaîne sans objet dense : `True`.

## Limites

Une seule instance Clifford pure idéale est certifiée. Ce résultat ne montre
pas que toutes les instances A=8 passent, ne fournit aucune loi d'échelle,
aucune minimalité de profondeur et aucune sécurité cryptographique. Le symbole
peut représenter un octet ou un pixel 8 bits, mais le canal ne connaît pas sa
sémantique.
