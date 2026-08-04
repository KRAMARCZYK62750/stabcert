# Pré-vol collectif |A|=5

Statut : **arrêté proprement avant synthèse**.

## Configuration et budget

- message collectif : 5 qubits, dimension 32 ;
- B=4, E=4, total : 18 qubits ;
- le message est désormais plus grand que B ; ce test s'éloigne donc du régime
  Hayden--Preskill à petit message ;
- budget hérité de A4 : 1024 Mio, 120 s,
  65536 contrôles opératoriels et
  131072 éléments Choi signés ;
- plancher attendu : `1/32² = 1/1024`.

## Chronologie calculée

| t | I(R:C) | distance trace | fidélité Petz | rang support | opérateurs² | secondes | RSS Mio |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 10 | 0.9990234375 | 0.000976562500000003 | 16 | 256 | 5.273 | 212.1 |
| 1 | 8 | 0.99609375 | 0.00390624999999998 | 32 | 1024 | 3.785 | 230.4 |
| 2 | 6 | 0.984375 | 0.0156249999999999 | 64 | 4096 | 3.305 | 242.9 |
| 3 | 4 | 0.9375 | 0.0624999999999997 | 128 | 16384 | 3.485 | 253.8 |
| 4 | 2 | 0.75 | 0.249999999999999 | 256 | 65536 | 2.973 | 276.1 |
| 5 | 0 | 0 | 0.999999999999998 | 512 | 262144 | 3.546 | 276.1 |
| 6 | 0 | 0 | 1 | 256 | 65536 | 3.229 | 280.9 |
| 7 | 0 | 0 | 0.999999999999997 | 128 | 16384 | 2.961 | 280.9 |
| 8 | 0 | 0 | 1.00000000000001 | 64 | 4096 | 3.402 | 280.9 |
| 9 | 0 | 0 | 1.00000000000001 | 32 | 1024 | 2.839 | 280.9 |

Le premier temps avec `F_Petz>0,99` est `t=5` :
`I(R:C)=0`,
distance `0.0` et fidélité Petz
`0.999999999999998`.

## Première limite exacte

À ce temps :

- rang du support : 512 ;
- contrôles requis : 262144, soit
  4 fois le budget ;
- Choi Petz stabilisateur : `True` ;
- purification Choi : 18 qubits,
  4.0 Mio comme vecteur ;
- groupe signé : 262144 éléments, soit
  2 fois le budget ;
- espace candidat symplectique : 262144 vecteurs.

L'extrapolation linéaire du seul contrôle opératoriel depuis A4 donne environ
`173.3 s` pour le
circuit direct et `178.7 s`
pour le routé, avant même de compter la synthèse. Cette estimation est un
indicateur de faisabilité, pas une mesure A5.

Motifs d'arrêt enregistrés : `operator_checks=262144>65536;signed_choi_group=262144>131072;estimated_two_validations_seconds=352.0>120.0`.

## Actions volontairement non exécutées

- synthèse Clifford : `False` ;
- validation opératorielle : `False` ;
- routage : `False` ;
- tests des 32 symboles et superpositions : `False`.

Ainsi, ce pré-vol établit seulement que le découplage et Petz abstrait sont
favorables pour cette instance. Il ne valide pas un canal Clifford A5 construit
et ne permet pas d'annoncer un alphabet collectif de 32 symboles transmis.

## Ressources du pré-vol

Chronologie et vérification stabilisatrice du Choi :
`35.884 s`, RSS maximale
`280.9 Mio`. Le projecteur Choi dense théorique de
1024 Gio n'est pas construit.

La prochaine étape n'est pas A6 : elle consiste à remplacer l'énumération du
groupe Choi et la validation opérateur par opérateur par des preuves sur
générateurs symplectiques signés.
