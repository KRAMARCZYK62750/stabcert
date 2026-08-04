# Pré-vol structurel collectif |A|=7

Statut : **validé**.
Instance unique, budget strict 120 s / 1024 Mio.
Aucun A=8 n'est lancé.

## Configuration

- message collectif : 7 qubits, dimension 128 ;
- B=4, graine 20260802, profondeur 6 ;
- brouilleur Clifford unique et connecté ;
- chronologie calculée uniquement par rangs stabilisateurs ;
- canal dense construit seulement au temps finalement sélectionné.

## Chronologie structurelle

| t | I(R:C) | distance trace | fidélité Petz par rangs | rang support | secondes |
|---:|---:|---:|---:|---:|---:|
| 0 | 14 | 0.999938964844 | 6.103515625e-05 | 16 | 0.0229 |
| 1 | 12 | 0.999755859375 | 0.000244140625 | 32 | 0.0253 |
| 2 | 10 | 0.9990234375 | 0.0009765625 | 64 | 0.0347 |
| 3 | 8 | 0.99609375 | 0.00390625 | 128 | 0.0479 |
| 4 | 7 | 0.9921875 | 0.0078125 | 128 | 0.0674 |
| 5 | 5 | 0.96875 | 0.03125 | 256 | 0.0938 |
| 6 | 3 | 0.875 | 0.125 | 512 | 0.1593 |
| 7 | 1 | 0.5 | 0.5 | 1024 | 0.1738 |
| 8 | 0 | 0 | 1 | 1024 | 0.2306 |
| 9 | 0 | 0 | 1 | 512 | 0.2639 |
| 10 | 0 | 0 | 1 | 256 | 0.2854 |
| 11 | 0 | 0 | 1 | 128 | 0.3043 |

Le premier temps avec `F_Petz>0,99` est `t=8` :
`I(R:C)=0` et distance
`0.0`.

## Validation du récupérateur

| quantité | valeur |
|---|---:|
| Petz par rangs stabilisateurs | 1 |
| Petz dense, contrôle indépendant | 0.999999999999991 |
| circuit Clifford direct | 1 |
| circuit Clifford routé | 1 |
| fidélité Choi certifiée | 1.0 |

La validation d'intrication construit
`0` amplitude dense et
`0` entrée de matrice réduite.
Les phases signées sont compatibles : `True` ;
les Choi réduits sont égaux : `True`.

Les anciennes énumérations théoriques de
4194304 éléments de groupe et
1048576 opérateurs sont évitées.

## Ressources construites

| réalisation | profondeur 2q | CNOT | SWAP |
|---|---:|---:|---:|
| Clifford direct | 65 | 93 | 0 |
| chaîne locale | 413 | 603 | 170 |

Temps total : `30.844 s` ; RSS maximale :
`960.4 Mio` (93.8%
du budget). Marge : `63.6 Mio`.

Premier nouveau goulot : `dense_channel_and_choi_synthesis_memory`.

## Limites

La validation est entièrement stabilisatrice et sans état dense. En revanche,
le contrôle Petz indépendant et l'extraction Choi utilisée pendant la synthèse
emploient encore des matrices/vecteurs denses au seul temps sélectionné. Cette
instance ne prouve ni que toutes les instances A=7 passent, ni une loi de coût,
ni la faisabilité de A=8, ni une propriété cryptographique.
