# Protocole de mise à l’échelle — phase B=4

## Mesures séparées

`K_total` reste une grille de lecture, non une égalité : les ressources sont
enregistrées séparément comme profondeur/CNOT de synthèse Clifford logique,
surcoût de routage, et bruit (ici explicitement nul).

La campagne initiale garde `|B|=4`. Elle varie la profondeur du brouilleur
`d_scr in {3,6,9}`, trois graines et `t in {1,2}`. Seules les instances t=2
sont compilées : t=1 sert de point d'information Petz, sans attribuer un coût
de circuit à une instance non construite.

## Architectures

Les mêmes circuits validés sont comparés sur :

1. un niveau logique tout-à-tout, diamètre 1, sans SWAP ;
2. la chaîne `E0-E1-E2-E3-D0-D1`, diamètre 5, avec routage explicite qui
   restitue les fils de sortie.

La borne causale enregistrée est le rayon du cône de lumière arrière de `A'`
sur cette chaîne. C'est une borne locale démontrée pour la géométrie donnée,
pas une borne de complexité du décodage.

## Limites

Le routeur est volontairement simple et non optimal. Les résultats ne prouvent
donc ni une profondeur minimale ni une croissance asymptotique. L'augmentation
de `|B|` reste conditionnée à la validation de cette base B=4 reproductible.

## Grille B=4 élargie exécutée

La grille contient 20 graines et `d_scr={3,6,9}`, soit 60 instances `t=2`.
Après correction de l'alignement signé et complétion du code de sortie lorsque
son environnement Petz ajoute un fil, les 60 dilatations sont validées. Pour
ces 60 instances :

| Mesure | min | médiane | max |
|---|---:|---:|---:|
| profondeur logique | 12 | 22 | 29 |
| profondeur routée sur chaîne | 36 | 72 | 112 |
| SWAP ajoutés | 8 | 22 | 40 |

Le rapport médian profondeur routée/logique est 3.27. C'est une observation
sur ce routeur, cette géométrie et B=4, non une loi d'échelle.

L'ancienne obstruction de l'instance (`seed=4000`, `d_scr=9`, `t=2`)
a été résolue : c'était un mauvais appariement entre une base stabilisatrice
binaire et une seconde base indépendante signée. Le diagnostic complet est
dans `COMPILER_OBSTRUCTION_SEED4000.md`. La condition de compilation B=4 est
maintenant satisfaite pour cette grille ; une grille à taille B supérieure reste
conditionnée à cette validation.

Les corrélations de Pearson observées sur ces 60 instances sont : profondeur
du brouilleur/profondeur logique `0.060`, profondeur logique/profondeur routée
`0.200`, distance moyenne des CNOT logiques/SWAP `0.266`, borne de cône de
lumière/profondeur routée `0.208`. Elles sont trop faibles pour justifier une
tendance ; elles servent uniquement de ligne de base pour de futures tailles.

Les données reproductibles sont dans `results/b4_scaling_baseline.csv` et le
lanceur est `run_b4_scaling.py`.
