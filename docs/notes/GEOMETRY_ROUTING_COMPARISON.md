# Comparaison du coût de routage par géométrie

Même circuit logique, même graine et même temps d'émission pour chaque ligne A.
Les quatre comparaisons principales — `chain`, `ring`, `grid_2d` et
`all_to_all` — utilisent exactement le même routeur par plus court chemin avec
rejeu inverse des SWAP. `chain_historical` conserve séparément l'ancien routeur
spécialisé. Toutes les lignes restaurent l'ordre final et reproduisent
exactement le Clifford signé d'origine.

| A | architecture | diamètre | profondeur logique | profondeur routée | rapport | CNOT routés | SWAP | distance CNOT moyenne initiale |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 9 | chain_historical | 12 | 85 | 598 | 7.04 | 1092 | 326 | 4.22 |
| 9 | chain | 12 | 85 | 1078 | 12.68 | 1806 | 564 | 4.22 |
| 9 | ring | 6 | 85 | 759 | 8.93 | 1296 | 394 | 3.18 |
| 9 | grid_2d | 6 | 85 | 590 | 6.94 | 846 | 244 | 2.32 |
| 9 | all_to_all | 1 | 85 | 85 | 1.00 | 114 | 0 | 1.00 |
| 10 | chain_historical | 15 | 126 | 959 | 7.61 | 1833 | 554 | 3.52 |
| 10 | chain | 15 | 126 | 1614 | 12.81 | 3021 | 950 | 3.52 |
| 10 | ring | 8 | 126 | 1523 | 12.09 | 2517 | 782 | 3.31 |
| 10 | grid_2d | 6 | 126 | 784 | 6.22 | 1227 | 352 | 2.09 |
| 10 | all_to_all | 1 | 126 | 126 | 1.00 | 171 | 0 | 1.00 |
| 11 | chain_historical | 15 | 129 | 879 | 6.81 | 1642 | 484 | 3.64 |
| 11 | chain | 15 | 129 | 1548 | 12.00 | 2914 | 908 | 3.64 |
| 11 | ring | 8 | 129 | 1313 | 10.18 | 2338 | 716 | 3.21 |
| 11 | grid_2d | 6 | 129 | 848 | 6.57 | 1342 | 384 | 2.35 |
| 11 | all_to_all | 1 | 129 | 129 | 1.00 | 190 | 0 | 1.00 |
| 12 | chain_historical | 17 | 154 | 1209 | 7.85 | 2107 | 626 | 3.67 |
| 12 | chain | 17 | 154 | 2169 | 14.08 | 3607 | 1126 | 3.67 |
| 12 | ring | 9 | 154 | 1886 | 12.25 | 3463 | 1078 | 3.45 |
| 12 | grid_2d | 7 | 154 | 1192 | 7.74 | 1849 | 540 | 2.46 |
| 12 | all_to_all | 1 | 154 | 154 | 1.00 | 229 | 0 | 1.00 |

Temps total : `36.346 s` ; RSS maximale :
`41.9 Mio`.

## Lecture

Le cas tout-à-tout constitue le contrôle : aucun SWAP et profondeur routée
égale à la profondeur logique. Les différences `chain`/`ring`/`grid_2d`
isolent la géométrie sous une heuristique identique, mais pas une profondeur
minimale. La ligne historique montre aussi combien une heuristique spécialisée
peut changer le résultat à géométrie fixe.

## Limites

Quatre circuits Clifford idéaux seulement sont comparés. Les routeurs ne sont
pas annoncés optimaux et les résultats ne constituent ni une loi d'échelle ni
une borne fondamentale liée à la géométrie.
