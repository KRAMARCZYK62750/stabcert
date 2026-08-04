# Régression de la validation stabilisatrice sans état dense

Statut : **validé — 6/6**.
Tolérance : `1e-12`.

| A | t | écart fidélité max | amplitudes denses anciennes | temps structurel s | temps dense s | accélération | RSS dense Mio | RSS structurelle Mio |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2 | 7.22e-15 | 2048 | 0.0562 | 0.0026 | 0.05 | 41.2 | 41.2 |
| 2 | 3 | 8.99e-15 | 8192 | 0.0997 | 0.0079 | 0.08 | 41.5 | 41.5 |
| 3 | 3 | 7.44e-15 | 32768 | 0.1243 | 0.0212 | 0.17 | 46.2 | 46.2 |
| 4 | 5 | 1.09e-14 | 131072 | 0.2166 | 0.0794 | 0.37 | 51.8 | 51.8 |
| 5 | 5 | 1.18e-14 | 524288 | 0.3041 | 0.3629 | 1.19 | 132.8 | 112.1 |
| 6 | 8 | 1.61e-14 | 2097152 | 0.4832 | 7.7013 | 15.94 | 494.4 | 238.4 |

Pour chaque cas, les fidélités Petz, directe et routée concordent à moins de
`1e-12`, et les verdicts sont identiques. Le nouveau chemin vérifie :

- intersection exacte du stabilisateur réduit avec le stabilisateur de Bell ;
- compatibilité des phases sur cette intersection ;
- égalité des Choi réduits par groupes générateurs signés ;
- zéro amplitude de vecteur d'état et zéro entrée de matrice réduite dense
  construite par la validation.

La fidélité structurelle vaut `2^(ell-2A)` lorsque les phases sont compatibles,
où `ell` est le rang de l'intersection ; elle vaut zéro en cas de conflit de
phase. La référence Petz `2^(-I(R:C))` est utilisée seulement sous les
hypothèses déjà auditées : isométrie Clifford, environnement stabilisateur pur
et référence maximale.

Les processus dense et structurel sont isolés. Leurs RSS incluent le canal et
la synthèse communs déjà présents avant la validation ; les colonnes
d'incrément de RSS du CSV isolent mieux la couche remplacée.
