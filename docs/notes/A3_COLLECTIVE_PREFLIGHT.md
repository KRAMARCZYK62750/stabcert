# Pré-vol collectif |A|=3

Statut : **pré-vol unique validé**. Aucune campagne et aucun calcul `|A|=8`
n'ont été lancés.

## Configuration

- message collectif : 3 qubits, soit un alphabet choisi de 8 symboles
  orthogonaux ;
- B=4, E=4, total simulé : 14 qubits ;
- brouilleur unique connecté sur 7 qubits ;
- graine 20260802, profondeur 6 ;
- plancher sans information attendu : `1/8² = 1/64`.

## Pré-vol selon le temps d'émission

| t | I(R:C) bits | distance trace | fidélité Petz | rang support | opérateurs du support | secondes | RSS pic Mio |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 6 | 0.984375 | 0.015625 | 16 | 256 | 0.8396 | 124.0 |
| 1 | 4 | 0.9375 | 0.0624999999999996 | 32 | 1024 | 0.1391 | 145.0 |
| 2 | 2 | 0.75 | 0.249999999999999 | 64 | 4096 | 0.0424 | 148.8 |
| 3 | 1.59872115546e-14 | 1.11022302463e-16 | 0.999999999999996 | 128 | 16384 | 0.0454 | 149.3 |
| 4 | 1.24344978758e-14 | 1.11022302463e-16 | 0.999999999999996 | 64 | 4096 | 0.0385 | 150.7 |
| 5 | 1.59872115546e-14 | 8.32667268469e-16 | 0.999999999999994 | 32 | 1024 | 0.0437 | 154.8 |
| 6 | 4.4408920985e-15 | 5.55111512313e-16 | 0.999999999999988 | 16 | 256 | 0.0622 | 171.0 |
| 7 | 0 | 0 | 0.999999999999993 | 8 | 64 | 0.6573 | 311.7 |

Le premier temps dépassant `F_Petz>0,99` est `t=3`. À ce point,
`I(R:C)=1.6e-14` et la distance
en trace vaut `1.11e-16`.

## Synthèse et validation complètes à t=3

Le support a le rang 128 : la validation exhaustive
porte donc sur 16384 états et cohérences de base.
Le Choi purifié comporte 14 qubits. Sa
matrice dense carrée n'est jamais construite ; lorsque les deux Choi sont purs,
la fidélité et la norme de différence sont calculées exactement dans leur
sous-espace de dimension deux.

| réalisation | fidélité intrication | fidélité Choi | erreur opératorielle | profondeur 2q | CNOT | SWAP | validation s |
|---|---:|---:|---:|---:|---:|---:|---:|
| Petz abstrait | 0.999999999999996 | 1 | 0 |  |  |  |  |
| Clifford direct | 0.999999999999993 | 1 | 1.74e-15 | 31 | 33 | 0 | 2.351092749973759 |
| Clifford route chaine | 0.999999999999993 | 1 | 1.74e-15 | 147 | 195 | 54 | 2.606336416909471 |

Chaîne : `10-11-12-13-3-4-5`. Ordre final restauré :
`True`. Temps total du pré-vol :
`9.086 s`; RSS maximale observée :
`311.7 Mio`.

## Alphabet de huit symboles et cohérences

Les huit états `000` à `111` sont tous décodés correctement. Sont également
testés `(000+111)/sqrt(2)`, `(001+i110)/sqrt(2)` et un état complexe aléatoire.
Fidélités minimales :

- Petz abstrait : `0.999999999999995` ;
- Clifford direct : `0.999999999999992` ;
- Clifford routé : `0.999999999999992`.

Ces étiquettes constituent un alphabet choisi dans une base. La validation des
superpositions et de toute la base d'opérateurs certifie davantage que la seule
transmission de trois bits classiques.

## Limites

Une seule instance Clifford idéale est testée. Les temps et la mémoire ne sont
pas une loi d'échelle. Ce résultat n'autorise ni `|A|=8`, ni une affirmation de
profondeur minimale, ni une conclusion sur le bruit ou les circuits
non-Clifford.
