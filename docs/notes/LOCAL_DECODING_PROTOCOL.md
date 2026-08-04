# Protocole de décodage local — B=4

## Architecture

Au temps t, le registre accessible est disposé sur une chaîne dans l’ordre physique fixe

`E0 — E1 — E2 — E3 — D0 — ... — D(t-1) — ancillas`.

Une couche coûteuse contient des portes à deux qubits uniquement entre voisins; les portes à un qubit sont autorisées mais rapportées séparément. Un SWAP est décomposé en trois CNOT voisins et compte dans le nombre de SWAP et la profondeur locale. La sortie logique `A'` est le premier site après décodage.

## Ressources rapportées

La grandeur principale est `K`, profondeur totale en couches de deux-qubits voisines. Chaque circuit fournit aussi : CNOT, SWAP, portes à un qubit, ancillas, rang de Choi et fidélité obtenue.

## Petz abstrait et dilatation

Pour les Kraus `L_j:X->A'` du Petz, la dilatation est `W|psi>=sum_j L_j|psi>|j>`. Sa dimension d’environnement est le rang de Choi du canal Petz. Une extension unitaire sur `X+ancillas` est construite seulement si la dimension de sortie est compatible; son exactitude est vérifiée avant routage.

`F_Petz_abstrait`, `F_Stinespring_exact`, `F_circuit_local_exact` et `F_circuit_approxime` sont des colonnes distinctes. Aucune fidélité de compilation n’est assimilée à celle du canal abstrait.

## Comparateurs

Les familles sont : Petz compilé, Clifford local déterministe lorsque disponible, recherche locale heuristique, témoin aléatoire, et `U^-1` seulement à évaporation totale. Yoshida–Kitaev sera ajouté séparément avec U/U*, EPR supplémentaires, mesures de Bell, feedback, post-sélection et succès explicitement comptés.

## Bornes causales

Sur cette chaîne, une observable de sortie au site 0 possède après K couches un cône de lumière inclus dans les sites de distance au plus K. Un circuit dont la sortie doit dépendre d’un site q exige donc K>=q. Cette borne concerne ce circuit et cette géométrie, non tous les décodeurs imaginables.

## Interprétation

`F_best_observed(t,K)` est le maximum parmi les familles effectivement construites. `k_best_observed(epsilon,t)` est le premier budget testé atteignant `1-epsilon`; ce n’est jamais une profondeur minimale démontrée.
