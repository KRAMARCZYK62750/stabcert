# Régression de synthèse paramétrique

Statut : **validé — 3/3 cas passent**. Tolérance numérique : `1e-12`.

| Cas | rang support | logiques | env. Petz | F Petz | F circuit | F Choi | erreur op. | profondeur | CNOT | verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| no_scrambling_t1 | 32 | 5 | 4 | 0.9999999999999996 | 0.9999999999999984 | 0.9999999999999987 | 4.46e-16 | 12 | 12 | True |
| deep_t2 | 16 | 4 | 3 | 0.9999999999999957 | 0.9999999999999928 | 0.9999999999999938 | 1.98e-15 | 12 | 14 | True |
| seed4000_depth9_t2 | 16 | 4 | 3 | 0.9999999999999956 | 0.9999999999999909 | 0.999999999999992 | 5.25e-15 | 25 | 32 | True |

## Égalités vérifiées

- Les sous-groupes Choi signés historiques et paramétriques sont comparés comme
  ensembles complets, indépendamment de l'ordre des générateurs.
- Le rang numérique de `tau_X`, calculé avec le seuil singulier relatif Petz,
  égale `2^(n_X-s)` pour chaque code stabilisateur.
- Profondeur logique, CNOT et nombre de fils d'environnement coïncident
  exactement avec l'oracle historique.
- Fidélités et normes d'erreur satisfont la tolérance `1e-12`.

## Séparation des chemins

Le chemin paramétrique construit canal, Petz, corrélations Choi, tableau,
circuit et métriques entièrement en mémoire. Il n'importe ni CSV, ni module
`experiment`, ni constantes `N_QUBITS`/`SCRAMBLED`. Le chemin historique est
appelé après le calcul paramétrique, uniquement comme oracle de régression des
ressources et du sous-groupe Choi. Il conserve ses dépendances B=4 et CSV ;
elles ne participent pas à la construction paramétrique.

Le routage n'est pas migré et aucune instance B=5 n'est exécutée.
