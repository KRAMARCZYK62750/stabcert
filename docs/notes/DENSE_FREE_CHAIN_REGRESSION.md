# Régression de la chaîne Petz entièrement stabilisatrice

Statut : **validé — 7/7**.
Tolérance numérique : `1e-12`.

| A | rang tau_X | qubits Choi | écart fidélité max | temps dense s | temps structurel s | accélération | RSS dense Mio | RSS structurelle Mio |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 16 | 10 | 4.11e-15 | 0.115 | 0.148 | 0.78 | 41.4 | 41.0 |
| 2 | 32 | 12 | 2.89e-15 | 0.200 | 0.241 | 0.83 | 41.7 | 41.1 |
| 3 | 128 | 14 | 4e-15 | 0.322 | 0.294 | 1.09 | 46.2 | 41.1 |
| 4 | 128 | 16 | 8.22e-15 | 0.830 | 0.521 | 1.59 | 51.9 | 41.1 |
| 5 | 512 | 18 | 2.22e-15 | 2.419 | 0.670 | 3.61 | 112.2 | 41.3 |
| 6 | 256 | 20 | 1.33e-15 | 8.930 | 1.122 | 7.96 | 238.7 | 41.4 |
| 7 | 1024 | 22 | 8.66e-15 | 41.655 | 1.521 | 27.38 | 961.2 | 41.3 |

Pour A=1 à A=7, les objets suivants coïncident exactement : partitions X/C,
supports signés de `tau_X`, groupes Choi Petz signés sous forme RREF canonique,
tableaux encodeur/sortie, circuits, profondeurs, CNOT, SWAP, environnement et
ordre final. Les fidélités concordent à moins de `1e-12`.

Le nouveau chemin représente le canal par son isométrie stabilisatrice pure,
`tau_X` par son projecteur stabilisateur normalisé, et le Choi Petz par la
conjugaison complexe du Choi global après permutation `R|X|C` vers
`A'|Ref|E_Petz`. Il ne construit ni Kraus dense, ni matrice `tau_X`, ni vecteur
Choi dense.

Les chemins NumPy/SVD restent présents uniquement dans les travailleurs de
régression dense. Ces mesures ne constituent pas une loi d'échelle.
