# Audit du routeur et du coût géométrique

Les circuits logiques A=9…12, les graines et les temps d'émission sont figés.
Le routeur principal utilise le même budget (`lookahead=16`,
`candidate_budget=64`) sur chaîne, anneau, grille 2D et
tout-à-tout. Il conserve le placement entre CNOT et restaure finalement les
sorties par le même algorithme de placement de jetons sur graphe connecté.

## Résultats du routeur commun amélioré

| A | géométrie | profondeur logique | profondeur routée | SWAP mouvement | SWAP restitution | SWAP total | borne causale | borne congestion du circuit compilé |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 9 | chain | 85 | 398 | 183 | 63 | 246 | 12 | 241 |
| 9 | ring | 85 | 372 | 167 | 7 | 174 | 6 | 138 |
| 9 | grid_2d | 85 | 254 | 78 | 20 | 98 | 6 | 139 |
| 9 | all_to_all | 85 | 85 | 0 | 0 | 0 | 1 | 23 |
| 10 | chain | 126 | 628 | 244 | 88 | 332 | 15 | 245 |
| 10 | ring | 126 | 500 | 207 | 39 | 246 | 8 | 220 |
| 10 | grid_2d | 126 | 358 | 106 | 20 | 126 | 6 | 183 |
| 10 | all_to_all | 126 | 126 | 0 | 0 | 0 | 1 | 36 |
| 11 | chain | 129 | 540 | 224 | 60 | 284 | 15 | 260 |
| 11 | ring | 129 | 597 | 266 | 60 | 326 | 8 | 202 |
| 11 | grid_2d | 129 | 339 | 102 | 22 | 124 | 6 | 208 |
| 11 | all_to_all | 129 | 129 | 0 | 0 | 0 | 1 | 32 |
| 12 | chain | 154 | 932 | 439 | 101 | 540 | 17 | 346 |
| 12 | ring | 154 | 915 | 410 | 98 | 508 | 9 | 320 |
| 12 | grid_2d | 154 | 464 | 148 | 26 | 174 | 7 | 250 |
| 12 | all_to_all | 154 | 154 | 0 | 0 | 0 | 1 | 37 |

Avec cette politique commune, la grille réduit la profondeur par rapport à la
chaîne de 36.2 % (A=9), 43.0 % (A=10), 37.2 % (A=11) et 50.2 % (A=12).
Pour A=12, le tout-à-tout supprime entièrement le routage : 154 couches, soit
exactement la profondeur logique, contre 464 sur grille et 932 sur chaîne.

## Audit de l'écart A=12 sur chaîne

| stratégie | profondeur | SWAP mouvement | SWAP restitution | SWAP total |
|---|---:|---:|---:|---:|
| historical_target_move | 1209 | 563 | 63 | 626 |
| shortest_path_inverse_replay | 2169 | 563 | 563 | 1126 |
| common_lookahead_token_restore | 932 | 439 | 101 | 540 |

Le routeur naïf et l'ancien routeur effectuent les mêmes 563 SWAP de
mouvement. L'écart 2169/1209 venait donc principalement du rejeu inverse des
563 SWAP, contre 63 SWAP pour une restitution directe. Le routeur à regard en
avant réduit en plus le mouvement à 439 SWAP ; sa restitution en demande 101,
pour une profondeur finale de 932.

Ces deux comparaisons séparent donc deux contributions observées : la nouvelle
heuristique fait passer la chaîne de 1209 à 932, puis le changement de chaîne à
grille, à heuristique fixée, fait passer 932 à 464. Cette séparation est
expérimentale et les coûts ne sont pas supposés additifs.

## Portée des bornes

`causal_lightcone_depth_bound` est une borne démontrée pour le Clifford cible :
un circuit local de profondeur K ne peut étendre le support d'un Pauli au-delà
de la distance K. `logical_depth_baseline` est la profondeur du circuit logique
imposé, pas une borne fondamentale sur toute resynthèse. Les bornes de congestion s'appliquent au multiensemble de
portes du circuit déjà compilé. Les charges de chemins statiques sont seulement
des indicateurs descriptifs et ne sont pas annoncées comme bornes globales.

## Validation et limites

Chaque circuit routé restitue l'ordre des fils, réalise exactement le même
Clifford signé et conserve la fidélité Petz. Les profondeurs sont les meilleures
observées avec ces trois stratégies, sans preuve de minimalité. Quatre circuits
idéaux seulement sont étudiés ; aucune loi d'échelle n'est ajustée.

Temps total : `59.291 s` ; mémoire RSS maximale :
`42.9 Mio`.
