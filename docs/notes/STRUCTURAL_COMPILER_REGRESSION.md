# Régression du compilateur structurel

Statut : **validé — 4/4 cas**.
Tolérance numérique : `1e-12`.

| A | ancien groupe | anciens opérateurs | générateurs vérifiés | temps ancien s | temps nouveau s | accélération | RSS ancien Mio | RSS nouveau Mio |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1024 | 256 | 8 | 0.208 | 0.079 | 2.63 | 42.1 | 41.4 |
| 2 | 4096 | 1024 | 10 | 0.583 | 0.145 | 4.02 | 44.4 | 41.6 |
| 3 | 16384 | 16384 | 14 | 1.986 | 0.264 | 7.51 | 53.3 | 46.6 |
| 4 | 65536 | 16384 | 14 | 7.728 | 0.825 | 9.37 | 99.2 | 65.9 |

Pour A=1 à A=4, les tableaux encodeur/sortie, corrélations signées,
circuits, profondeurs, CNOT, SWAP, routage et ordre final sont exactement
identiques. Les fidélités numériques concordent à moins de `1e-12`.

Le nouveau certificat vérifie l'égalité des purifications Choi dans la jauge
fixée ; l'isométrie d'environnement est donc `W_E=I`, ce qui implique l'égalité
des Choi réduits après trace. Aucun élément du groupe stabilisateur et aucun
opérateur de la base complète du support ne sont énumérés sur le nouveau chemin.

## Dimensions de l'algèbre binaire

| A | variables noyau support | contraintes | rang | dim noyau | rang stabilisateur | dim centralisateur | dim quotient logique | variables Choi | rang Choi | dim noyau affine | systèmes résolus | XOR scalaires instrumentés |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 10 | 8 | 8 | 2 | 2 | 10 | 8 | 12 | 10 | 2 | 312 | 124029 |
| 2 | 12 | 10 | 10 | 2 | 2 | 12 | 10 | 14 | 12 | 2 | 424 | 371814 |
| 3 | 14 | 14 | 14 | 0 | 0 | 14 | 14 | 14 | 14 | 0 | 508 | 379775 |
| 4 | 16 | 14 | 14 | 2 | 2 | 16 | 14 | 18 | 16 | 2 | 696 | 1454354 |

Le quotient logique est le centralisateur modulo le stabilisateur et possède
donc la dimension binaire `2k`. Le compteur couvre exactement les réductions de
lignes effectuées par `gf2.py` (systèmes affines, calculs de rang, pivots et
XOR de lignes). Il ne compte pas les opérations internes de Stim ni les
produits matriciels NumPy hors de ces éliminations ; la colonne ne doit donc
pas être interprétée comme un nombre total d'instructions machine.

Les mesures RSS proviennent de processus isolés. Les durées comprennent
synthèse, certification et les deux évaluations physiques de fidélité. Elles
ne constituent pas une loi d'échelle.
