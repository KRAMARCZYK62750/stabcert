# Pré-vol structurel collectif |A|=6

Statut : **validé**. Instance unique, budget strict
120 s / 1024 Mio. Aucun A=7 n'est lancé.

## Configuration

- message collectif : 6 qubits, dimension 64 ;
- B=4, graine 20260802, profondeur de brouillage 6 ;
- un seul brouilleur Clifford connecté et une seule dynamique collective ;
- construction du canal dans l'espace compact A+B+E, préalablement régressée
  contre le chemin incluant le registre R inutilisé.

## Chronologie

| t | I(R:C) | distance trace | fidélité Petz | rang support | secondes | RSS Mio |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 12 | 0.999755859375 | 0.000244140624999978 | 16 | 6.752 | 169.4 |
| 1 | 10 | 0.9990234375 | 0.000976562499999997 | 32 | 2.271 | 265.9 |
| 2 | 8 | 0.99609375 | 0.00390624999999998 | 64 | 0.968 | 316.2 |
| 3 | 6 | 0.984375 | 0.015625 | 128 | 0.597 | 365.2 |
| 4 | 4 | 0.9375 | 0.0624999999999996 | 256 | 0.478 | 400.4 |
| 5 | 2 | 0.75 | 0.249999999999998 | 512 | 0.481 | 475.4 |
| 6 | 2 | 0.75 | 0.249999999999999 | 256 | 0.522 | 569.9 |
| 7 | 1 | 0.5 | 0.499999999999999 | 256 | 0.356 | 595.9 |
| 8 | 0 | 0 | 0.999999999999999 | 256 | 0.311 | 633.0 |
| 9 | 0 | 0 | 0.999999999999969 | 128 | 0.309 | 641.0 |
| 10 | 0 | 0 | 0.999999999999956 | 64 | 0.249 | 673.0 |

## Résultat

Le premier temps avec `F_Petz>0,99` est
`t=8`. À ce temps :

- `I(R:C)=0` ;
- distance de trace `0.0` ;
- fidélité Petz `1` ;
- fidélité directe `1` ;
- fidélité routée `1` ;
- profondeur `55 -> 349` ;
- CNOT `88 -> 496`,
  SWAP `136`.

Le certificat compare 16 générateurs
signés. Les Choi réduits sont égaux : `True` ; dans
la jauge fixée, l'isométrie d'environnement est
`identity_in_fixed_purification_gauge`. Les anciennes énumérations théoriques de
1048576 éléments et
65536 opérateurs sont remplacées par zéro
énumération exhaustive.


## Ressources

Temps total : `19.381 s` ; RSS maximale :
`673.5 Mio`. Synthèse :
`5.301 s` ; certification directe/routée :
`0.214 s` /
`0.272 s` ; routage :
`0.000450 s`.

Premier nouveau goulot : `none_within_fixed_budget`.
La RSS atteint 65.8% du budget, avec
seulement 350.5 Mio de marge. Il s'agit
d'une pression de calcul du modèle fini, pas d'une difficulté physique démontrée.

## Limites

Ce pré-vol ne concerne qu'une instance idéale. Il ne montre pas que toutes les
instances A=6 passent, ne définit aucune loi de coût et ne prédit pas A=7. La
dimension 64 décrit un alphabet logique possible ; aucun contenu sémantique,
chiffrement ou avantage physique général n'est revendiqué.
