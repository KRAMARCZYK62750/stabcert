# Pré-vols structurels séquentiels A=9 à A=12

Statut : **4/4 instances validées**.
Une graine par taille, B=4, budget individuel
120 s / 1024 Mio. Aucun ajustement du
compilateur entre les tailles et aucun A=13.

| A | alphabet | t favorable | I(R:C) | rang support | F | profondeur logique | profondeur routée | CNOT logiques | CNOT routés | SWAP | secondes | RSS Mio |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 9 | 512 | 9 | 0 | 8192 | 1.0 | 85 | 598 | 114 | 1092 | 326 | 5.692 | 40.6 |
| 10 | 1024 | 12 | 0 | 4096 | 1.0 | 126 | 959 | 171 | 1833 | 554 | 8.100 | 40.9 |
| 11 | 2048 | 12 | 0 | 16384 | 1.0 | 129 | 879 | 190 | 1642 | 484 | 10.384 | 41.0 |
| 12 | 4096 | 14 | 0 | 16384 | 1.0 | 154 | 1209 | 229 | 2107 | 626 | 13.992 | 41.2 |

Aucune obstruction dans les quatre pré-vols.

Pour chaque ligne validée, Petz, le circuit direct et le circuit routé ont une
fidélité certifiée égale à 1 ; les Choi réduits et les phases signées
coïncident. Les alphabets sont couverts par le certificat du canal complet sans
énumération des états de base.

## Limites

Il s'agit de quatre instances Clifford pures idéales et non d'une campagne
statistique. Les tailles de message dépassent B=4 et s'éloignent du régime
Hayden--Preskill à petit message. Ces résultats ne définissent aucune loi
d'échelle, aucune profondeur minimale et aucune propriété cryptographique.
