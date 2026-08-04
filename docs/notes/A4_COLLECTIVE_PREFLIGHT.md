# Pré-vol collectif |A|=4

Statut : **validé dans le budget fixé**. Budget : 1024 Mio RSS et
120 s pour cette instance unique. Aucun calcul `|A|=8` n'est lancé.

## Configuration

- message collectif : 4 qubits, dimension 16 ;
- B=4, E=4, total : 16 qubits ;
- brouilleur Clifford unique et connecté sur 8 qubits ;
- graine 20260802, profondeur 6 ;
- plancher attendu sans information : `1/16² = 1/256`.

## Chronologie avant synthèse

Le découplage est calculé exactement par les rangs des sous-groupes
stabilisateurs. Dans ce cas pur à spectres plats, les projecteurs de support
sont emboîtés et la distance en trace vaut exactement `1-2^(-I)` ; aucune
matrice `rho_RC` dense n'est construite.

| t | I(R:C) | distance trace | fidélité Petz | rang support | opérateurs² | secondes | RSS Mio |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 8 | 0.99609375 | 0.00390625 | 16 | 256 | 0.560 | 67.1 |
| 1 | 6 | 0.984375 | 0.0156249999999998 | 32 | 1024 | 0.445 | 74.5 |
| 2 | 4 | 0.9375 | 0.0625 | 64 | 4096 | 0.391 | 79.8 |
| 3 | 3 | 0.875 | 0.125 | 64 | 4096 | 0.372 | 84.8 |
| 4 | 1 | 0.5 | 0.5 | 128 | 16384 | 0.391 | 89.9 |
| 5 | 0 | 0 | 1.00000000000001 | 128 | 16384 | 0.356 | 91.9 |
| 6 | 0 | 0 | 0.999999999999997 | 64 | 4096 | 0.332 | 92.9 |
| 7 | 0 | 0 | 1.00000000000001 | 32 | 1024 | 0.326 | 93.9 |
| 8 | 0 | 0 | 1.00000000000005 | 16 | 256 | 0.291 | 95.9 |

Le premier temps tel que `F_Petz>0,99` est `t=5`. Son
support a le rang 128 et exige
16384 contrôles opératoriels.

Les valeurs de fidélité légèrement supérieures à 1 sont conservées brutes et
proviennent des arrondis flottants. À `t=8`, l'erreur de conservation de la
trace sur support atteint `1.03e-12`, légèrement au-dessus de `1e-12`; ce temps
n'est pas utilisé pour la synthèse. À `t=5`, cette erreur vaut `1.36e-13`.

## Faisabilité et évitement des objets denses

- Choi Petz stabilisateur : `True` ;
- purification Choi : 16 qubits,
  1.0 Mio comme vecteur ;
- groupe stabilisateur signé : 65536 éléments ;
- espace candidat symplectique actuel : 262144 vecteurs ;
- projecteur dense de purification évité :
  64.0 Gio ;
- matrice Choi dense de validation évitée :
  4.0 Gio.

La pseudo-inverse de Petz et les comparaisons Choi utilisent leurs facteurs de
support exacts. Il ne s'agit ni d'un échantillonnage, ni d'une validation
partielle.

## Récupérateur construit à t=5

| réalisation | fidélité intrication | fidélité Choi | erreur opératorielle | profondeur 2q | CNOT | SWAP | validation s |
|---|---:|---:|---:|---:|---:|---:|---:|
| Petz abstrait | 1.00000000000001 | 1 | 0 |  |  |  |  |
| Clifford direct | 0.999999999999989 | 0.999999999999995 | 3.23e-15 | 57 | 62 | 0 | 10.832054666941985 |
| Clifford route chaine | 0.999999999999989 | 0.999999999999995 | 3.23e-15 | 213 | 338 | 92 | 11.16774991597049 |

Chaîne : `12-13-14-15-4-5-6-7-8` ; ordre final restauré :
`True`. Temps total :
`40.010 s`. RSS maximale :
`132.5 Mio`.

## Alphabet de 16 symboles

Les codes binaires restent les données primaires. La table emoji est seulement
une couche d'affichage :

`0000=😀`  `0001=🚀`  `0010=🧠`  `0011=🌙`  `0100=☀️`  `0101=🔥`  `0110=💧`  `0111=🌱`  `1000=🎵`  `1001=🐈`  `1010=🍎`  `1011=⚙️`  `1100=🧩`  `1101=🛰️`  `1110=🌈`  `1111=⭐`

Les 16 états de base, `(0000+1111)/sqrt(2)`,
`(0001+i1110)/sqrt(2)`, un état complexe aléatoire et l'état maximal
`Phi_16(R:A)` sont testés. Fidélités minimales :

- Petz abstrait : `0.999999999999996` ;
- Clifford direct : `0.999999999999989` ;
- Clifford routé : `0.999999999999989`.

## Limites

Une seule instance Clifford idéale est validée. Les coûts ne constituent pas
une loi d'échelle et aucune minimalité n'est prouvée. Le compilateur emploie
encore des espaces exponentiels de taille 65536
et 262144 ; cela interdit d'extrapoler
directement à un alphabet de 256 symboles.
