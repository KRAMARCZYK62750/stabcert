# Protocole — le coût de vérification suit-il la densité ou la dimension ?

**Statut :** conçu, non exécuté. Enregistré le 4 août 2026, avant toute mesure.

## Question

La série `results/gf2_scaling_*.csv` mesure une famille **dense** : brouilleur
Clifford aléatoire de profondeur 6, générateurs stabilisateurs de poids élevé,
systèmes affines pleins. L'extrapolation vers la cible FT en hérite.

Or un code de surface a des stabilisateurs de poids 4. Si le coût de
l'élimination GF(2) suit le remplissage des systèmes plutôt que leur
dimension, l'extrapolation dense **surestime**, et la ligne « n ≈ 200 et un
mur » est une borne supérieure sur la famille la plus hostile possible.

Une famille creuse à un `n` arbitraire ne répond pas. Il faut **deux familles
au même `n`**.

## Axe de densité — déjà présent dans le dépôt

`experiment.py` définit `regimes = {"none": 0, "weak": 1, "deep": 6}` : le
nombre de couches de brouillage est l'axe de densité historique du projet. Le
protocole le réutilise au lieu d'introduire un construit nouveau.

`random_stabilizer_scrambler(layout, rng, layers)` prend la profondeur en
paramètre. À `layers = 1`, les générateurs restent de poids faible ; à
`layers = 6`, ils sont denses.

**Ce que cet axe fait varier, et ce qu'il ne fait pas varier.** Le brouilleur
appaire les qubits après `rng.shuffle`, donc les CNOT sont sur des paires
aléatoires, jamais voisines. La profondeur gouverne donc le **poids** des
générateurs, pas leur **localité**. C'est le bon choix pour cette question :
le coût mesuré est celui de l'élimination GF(2), qui dépend du remplissage de
la matrice. La localité gouverne le routage, pas l'élimination — elle est de
second ordre ici, et relève de l'étape 2.

## Dispositif

Deux balayages, **tout identique sauf la profondeur** :

| | dense (acquis) | creux (à mesurer) |
|---|---|---|
| profondeur | 6 | 1 |
| `n` | 9 → 30 | 9 → 30 |
| graine | 20260802 | 20260802 |
| architecture | `chain` | `chain` |
| `t` | A + 4 | A + 4 |
| politique | `channel-certified` | `channel-certified` |

Le côté dense est déjà mesuré : la comparaison est donc gratuite d'un facteur
deux, et exempte de toute différence de harnais.

`n = 4 + t` ne dépend que de `t`, donc l'appariement en `n` est exact par
construction.

## Métrique de densité — mesurée, pas supposée

Pour chaque instance, poids de Pauli moyen et maximal des générateurs dérivés
`code.signed_stabilizer_labels`, normalisés par `n`. « Creux » doit être un
nombre reporté, pas un adjectif.

## Observable

**`row_xors`**, primaire. Il est déterministe : il ne dépend ni de la charge
machine ni de l'ordonnancement. Ce balayage peut donc tourner en concurrence
d'une autre mesure sans se contaminer — contrairement à `verify_seconds`, qui
est la seule quantité de ce projet exigeant une machine au repos.

## Lecture enregistrée à l'avance

Soit `R(n) = row_xors_dense(n) / row_xors_creux(n)` aux `n` appariés, ajusté
par `R(n) ~ n^ρ`. Avec `τ` la tolérance dérivée de l'étalon exact, comme dans
`measure_gf2_scaling.evaluate_prediction` :

- `|ρ| ≤ τ` → la densité agit sur la **constante**, pas sur le degré. La
  dimension gouverne l'échelle, et l'extrapolation dense reste valide en
  degré. La projection FT ne change pas d'ordre.
- `ρ > τ` → la densité agit sur le **degré**. L'extrapolation dense
  surestime asymptotiquement, la projection FT doit être refaite sur une
  famille creuse, et « n ≈ 200 et un mur » tombe.

Aucune autre lecture ne sera produite après coup.

## Confusion à contrôler

`code.logical_qubits` et `support_rank` dépendent du canal, donc de la
profondeur. À `n` égal, les deux familles peuvent ne pas avoir le même rang de
support — auquel cas « même `n` » n'est pas « même taille de problème ».

Traitement : reporter `logical_qubits` par instance. Si les valeurs coïncident
aux `n` appariés, la comparaison est directe. Sinon, `R(n)` est lu comme
régression avec `logical_qubits` en covariable, et la comparaison appariée est
abandonnée plutôt que forcée.

Second risque : à `layers = 1`, le brouilleur peut ne pas connecter tous les
qubits — le préflight A9–A12 teste déjà cette condition (`_connected`). Une
instance non connectée est écartée et signalée, pas rattrapée en changeant la
graine.

## Ce que ce protocole ne répond pas

Une chaîne à profondeur 1 n'est pas un code de surface. Ce dispositif isole le
poids des générateurs ; il ne teste ni la structure de réseau, ni les
stabilisateurs de poids 4 exactement, ni un graphe de couplage 2D.

Étape 2, seulement si l'étape 1 montre `ρ > τ` : construire un problème dont
les générateurs sont des plaquettes de poids 4 sur un réseau, avec graphe de
couplage `grid_2d`. Plus lourd, et confondant plusieurs variables à la fois —
d'où l'ordre.

## Coût attendu

La famille creuse devrait être **moins** chère que la dense à `n` égal. Le
balayage creux `n = 9 → 30` coûte donc au plus ce qu'a coûté le dense, soit
une quinzaine de minutes.
