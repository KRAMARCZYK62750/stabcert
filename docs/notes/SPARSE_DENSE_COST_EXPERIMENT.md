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

### Ce que `|ρ| ≤ τ` autorise à conclure, et ce qu'il n'autorise pas

Le contraste de densité retenu vaut **1,8×** (profondeur 3 contre 6), alors
que la plage en `n` vaut **3,3×** (9 → 30). Le levier sur `ρ` est donc plus
court que celui dont on disposait pour les exposants de degré, et un `ρ` nul
ne se distinguera pas d'un `ρ` faible : les deux tomberont sous `τ`.

Formulation autorisée en cas de `|ρ| ≤ τ` :

> la densité ne change pas le degré **assez pour être visible sur un contraste
> de 1,8×**

Formulation interdite :

> la densité ne change pas le degré

Cette limite ne gêne pas la question qui a motivé le protocole. Un code de
surface est très largement plus creux que la profondeur 3 ; si l'effet ne se
voit pas sur 1,8×, l'extrapolation dense reste une **borne supérieure valide**
pour la projection FT — et c'est tout ce que cette projection demande. Un `ρ`
significatif, lui, invaliderait l'extrapolation et serait donc concluant dans
l'autre sens.

## Régression conjointe — enregistrée le 4 août 2026, avant lecture de la densité dense

### Pourquoi elle remplace le dispositif apparié

Le confondant s'est déplacé trois fois : profondeur variable le long de `n`
(écartée), puis profondeur fixe mais densité variable quand même. La cause est
mécanique et n'était pas dans le protocole : à profondeur constante, chaque
couche apparie un nombre fixe de qubits, donc le nombre de CNOT croît en `n`
tandis que le nombre d'entrées de la matrice croît en `n²`. **La densité
normalisée décroît nécessairement.** Fixer la profondeur ne fixe pas la
densité.

Un confondant qui se déplace à chaque fois qu'on le chasse indique un axe de
contrôle qui n'est pas le bon paramètre. La densité ne se laisse pas
neutraliser : elle doit être modélisée.

### Modèle

Les deux bras partagent la même structure d'élimination — `affine_systems_solved`
identique aux 22 largeurs — donc les 22 × 2 = 44 points sont poolables :

```text
log(row_xors) = a + b·log(n) + c·log(densité) + ε
```

- `b` — degré en `n` **à densité fixée**. C'est lui, et non l'exposant d'un
  bras isolé, qui se compare à la prédiction structurelle 5.
- `c` — élasticité du coût à la densité.

L'identification de `c` vient des deux valeurs de densité au **même** `n` ;
c'est ce qui casse la colinéarité entre `log n` et `log densité`. Le levier
reste court, et la précision sur `c` s'en ressentira.

### Cohérence exigée avec les mesures déjà acquises

Avec `densité ~ n^δ` par bras, l'exposant observé sur un bras isolé vaut
`b + c·δ`. Le modèle doit donc reproduire, à `τ` près, les exposants déjà
mesurés — dont `4,907` pour le bras dense sur `n = 9…40`. **S'il ne les
reproduit pas, la forme log-linéaire est inadéquate et aucun coefficient n'est
lu.** Ce contrôle passe avant toute interprétation.

### Contrôle du modèle sur une quantité exactement connue

Le même modèle est ajusté sur `affine_systems_solved`, dont la vérité est
connue : `28n² − 232n + 598`, identique dans les deux bras, donc **coefficient
de densité exactement nul** et degré asymptotique 2.

La valeur de `c` qu'il rend sur cette quantité est le **plancher de faux
positif de la méthode**, noté `c₀`. Elle ne mesure pas un effet, elle mesure
ce que la méthode invente quand il n'y a rien.

C'est la leçon du jackknife rejeté au tour précédent : une machinerie qui rend
un intervalle serré autour d'une mauvaise valeur ne se détecte que par un
étalon. Aucune méthode nouvelle n'est adoptée ici sans passer d'abord sur
l'étalon.

### Lecture

Seuil `τ` dérivé de l'étalon comme partout ailleurs, et plancher `|c₀|` :

- `|c| ≤ max(τ, |c₀|)` → la densité n'a **pas d'effet détectable** sur le coût
  au-delà de la largeur, avec le levier disponible. L'extrapolation dense reste
  une borne supérieure valide.
- `c > max(τ, |c₀|)` → la densité agit sur le coût. Le degré à densité fixée
  est `b` ; la dérive observée sur un bras isolé vaut `c·δ` et n'est **pas** un
  effet de degré, seulement la conséquence de la décroissance de densité.

Formulation interdite dans les deux cas : conclure quoi que ce soit sur un code
de surface. Cette famille reste une chaîne brouillée, pas un réseau local.

## Mode d'échec observé — contrôle silencieux

Le premier passage de `compare_density_cost.py` a affiché
`pairing_valid: false` aux 22 largeurs, et **a tout de même émis un verdict**.
La divergence était fausse : les CSV denses étaient antérieurs à
l'instrumentation, `.get("logical_qubits")` rendait `None`, comparé à un
entier. Le contrôle du confondant n'avait pas eu lieu.

Un contrôle absent se voit. Un contrôle qui échoue silencieusement et laisse
passer une réponse confiante ne se voit pas — c'est le schéma exact du
jackknife. Corrigé deux fois : une colonne manquante lève une erreur explicite,
et le verdict est conditionné à la validité de l'appariement.

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

## Déviation enregistrée — 4 août 2026, avant le balayage

Le risque ci-dessus s'est réalisé immédiatement, et plus fortement que prévu.
Une couche de brouillage est **une seule mise en paires aléatoire** : elle ne
peut jamais connecter plus de deux qubits par composante. À `layers = 1`,
*toutes* les instances sont écartées, à tout `A`. Le régime `weak` de la Phase
A n'est donc pas utilisable comme bras creux.

Profondeur minimale connectante mesurée :

| A | 1 | 4 | 8 | 12 | 16 | 22 |
|---|---:|---:|---:|---:|---:|---:|
| couches | 3 | 3 | 2 | 3 | 2 | 2 |

Elle varie avec `A`. Prendre le minimum par instance ferait varier la
profondeur le long de `n` et confondrait densité et taille — ce que le
dispositif apparié doit justement éviter. **Le bras creux est donc fixé à
`layers = 3`**, plus petite profondeur uniforme qui connecte sur toute la
plage.

Contraste de densité vérifié à `n = 16` avant de lancer :

| couches | densité | poids moyen | `row_xors` |
|---:|---:|---:|---:|
| 2 | 0.219 | 3.50 | 597 858 |
| 3 | 0.328 | 5.25 | 1 185 068 |
| 4 | 0.422 | 6.75 | 1 880 689 |
| 6 | 0.578 | 9.25 | 2 052 234 |

À `n` constant, le coût varie d'un facteur 3,4 sur cet axe. La densité agit
donc au moins sur la constante ; la lecture enregistrée plus haut décide si
elle agit aussi sur le degré. Le contraste 3 contre 6 reste un facteur 1,8 en
densité, suffisant pour que `R(n)` soit lisible.

Aucune autre modification du protocole. La lecture `|ρ| ≤ τ` contre `ρ > τ`
est inchangée.

## Ce que ce protocole ne répond pas

Une chaîne à profondeur 1 n'est pas un code de surface. Ce dispositif isole le
poids des générateurs ; il ne teste ni la structure de réseau, ni les
stabilisateurs de poids 4 exactement, ni un graphe de couplage 2D.

Étape 2, seulement si l'étape 1 montre `ρ > τ` : construire un problème dont
les générateurs sont des plaquettes de poids 4 sur un réseau, avec graphe de
couplage `grid_2d`. Plus lourd, et confondant plusieurs variables à la fois —
d'où l'ordre.

### Condition d'entrée de l'étape 2 — quel facteur est tenu fixe ?

La condition scientifique est remplie : `c ≈ 1,41` contre un seuil de 0,384 et
un plancher de 0,006. Mais **l'étape 2 ne doit pas être lancée sur cette base
seule.**

Passer aux plaquettes de poids 4 sur `grid_2d` change **la densité et la
localité en même temps**. C'est exactement la structure qui a fait échouer le
dispositif apparié : deux facteurs qui bougent ensemble et dont aucun
coefficient ne peut être attribué. Ce serait le quatrième déplacement du même
confondant — profondeur variable, puis profondeur fixe à densité variable,
puis contraste dérivant, puis densité et localité liées.

L'étape 2 exige donc sa propre spécification pré-enregistrée, qui doit
répondre à une question avant toute mesure :

> **Qu'est-ce qui est tenu fixe cette fois, et par quel mécanisme le sait-on
> fixe plutôt que le suppose-t-on fixe ?**

Le protocole actuel a supposé la densité fixe parce qu'il tenait la profondeur
fixe. La supposition était fausse pour une raison mécanique dérivable
a priori. La spécification de l'étape 2 doit exhiber la quantité tenue fixe
**mesurée**, le long de `n`, avant d'interpréter quoi que ce soit — au même
titre que la porte de falsification exige de reproduire les exposants connus
avant de lire un coefficient.

Tant que cette question n'a pas de réponse écrite, l'étape 2 n'est pas prête,
quelle que soit la valeur de `c`.

## Coût attendu

La famille creuse devrait être **moins** chère que la dense à `n` égal. Le
balayage creux `n = 9 → 30` coûte donc au plus ce qu'a coûté le dense, soit
une quinzaine de minutes.
