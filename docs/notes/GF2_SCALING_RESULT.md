# Coût GF(2) de la vérification — résultat et portée exacte

**Date :** 4 août 2026. **Artefacts :** `results/gf2_scaling*.{csv,json}`,
`results/density_cost_comparison.json`.

## Le résultat exact

Sur 32 instances, `n = 9 → 40`, le nombre d'éliminations GF(2) effectuées par
une vérification `channel-certified` vaut **exactement** :

```text
affine_systems_solved = 28 n² − 232 n + 598      résidu nul, 32 points
```

Ce n'est pas un ajustement, c'est une identité : différences secondes
constantes à 56. Un lecteur peut la recalculer depuis le CSV.

Les compteurs de travail satisfont la composition structurelle
`n² × n³ × n` au seuil pré-enregistré :

| compteur | cible | observé (fenêtre haute, n ≤ 40) | verdict |
|---|---:|---:|---|
| `affine_systems_solved` | 2 | 2.290 | étalon |
| `row_xors` | 5 | 4.907 | confirmé |
| `scalar_bit_xors` | 6 | 6.106 | confirmé |

Tolérance 0,290, dérivée du biais de taille finie que l'étalon exhibe sur les
mêmes instances. Critère enregistré avant la tranche `n = 21…30`, non modifié
ensuite.

## De quoi ces exposants sont les exposants

**C'est la précision qui manque si on lit le tableau seul.**

Ces nombres sont les exposants de **cette famille telle que paramétrée** —
brouilleur de profondeur 6, `t = A + 4`, chaîne — et la densité des
générateurs de cette famille **n'est pas constante le long de `n`** : elle
décroît en `n^−0,24`.

La régression conjointe sur les deux bras de densité
(`docs/notes/SPARSE_DENSE_COST_EXPERIMENT.md`) donne une élasticité du coût à
la densité de **c ≈ 1,41**, avec un plancher de faux positif mesuré sur
l'étalon de 0,006. La densité agit donc réellement sur le coût.

Par conséquent, un exposant confirmé ici vaut `b + c·δ` :

- `b` — degré à **densité fixée** ;
- `δ` — dérive de la densité le long de `n`, ici −0,238 ;
- `c·δ` — la part de l'exposant qui vient de la décroissance de densité, pas
  de l'algorithme.

Le degré à densité fixée est plus élevé : `b ≈ 6,3` en ajustement sur tous les
points, soit **≈ 5,7 après correction du biais de taille finie** que l'étalon
mesure à +0,61 sur le même ajustement.

**La confirmation reste vraie ; son objet est la famille, pas l'algorithme
dans l'abstrait.** Deux nombres différents pour deux questions différentes :

| question | quantité | valeur |
|---|---|---:|
| que coûte cette famille quand `n` croît ? | exposant de famille | ≈ 5 |
| quel est le degré à densité fixée ? | `b` corrigé | ≈ 5,7 |

Les deux sont dans ce dépôt. Les confondre est l'erreur que cette section
existe pour empêcher.

## Ce que la mesure ne dit pas

- Rien sur un code de surface : la plage de densité mesurée va de 0,16 à 0,58,
  un code de surface à `n = 200` est à 0,02, et cette famille est une chaîne
  brouillée, pas un réseau local.
- Rien sur le temps machine asymptotique : `verify_seconds` croît moins vite
  que les compteurs parce que NumPy vectorise les XOR de lignes. Le temps
  converge par le bas vers `row_xors`, il ne le mesure pas.
- Rien sur une v2 à mesure et rétroaction, qui n'existe pas.

## Documents liés

- `SPARSE_DENSE_COST_EXPERIMENT.md` — protocole densité, régression conjointe,
  contrôles et modes d'échec ;
- `measure_gf2_scaling.py` — mesure, critère et règle d'arrêt enregistrés ;
- `compare_density_cost.py` — régression conjointe et contrôle sur l'étalon.
