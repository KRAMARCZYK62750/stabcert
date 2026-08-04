# Compilation stabilisatrice de Petz — état exact

## Canal stabilisateur

Dans la sous-classe étudiée, le Choi normalisé du Petz est un état stabilisateur mixte : sa purification par l’étiquette des Kraus est un état stabilisateur pur. Il admet donc une préparation Clifford avec ancillas stabilisatrices. Cette propriété ne suffit pas à identifier automatiquement une réalisation déterministe sur l’entrée X : la préparation de Choi et l’injection téléportée sont des objets distincts.

## Contrôle direct sans brouillage, t=1

Petz est l’identité logique sur D0. Sur la chaîne `E0-E1-E2-E3-D0`, le circuit direct applique quatre SWAP voisins pour amener D0 vers la sortie E0. Chaque SWAP vaut trois CNOT : profondeur locale 12, 12 CNOT, 4 SWAP, zéro ancilla, mesure ou correction conditionnelle. La fidélité exacte est 1.

Ce résultat est un compilateur Clifford direct, non une extension matricielle arbitraire.

## Instance profonde avant évaporation totale

La purification de Choi Petz à t=2 est stabilisatrice et sa préparation tableau a été routée séparément. Pour transformer cette ressource en canal déterministe, il faut synthétiser l’isométrie stabilisatrice du sous-espace `supp(tau_X)` vers `A'` et son environnement de Stinespring. Une téléportation par Choi avec post-sélection zéro est Clifford mais probabiliste; elle ne sera pas utilisée comme décodeur déterministe.

La synthèse demandée est donc une réduction symplectique de code : identifier les stabilisateurs de `supp(tau_X)`, choisir les paires de Pauli logiques de la sortie A', puis construire un tableau qui les envoie vers les Pauli physiques de A'. Cette étape n’est pas encore automatisée par Stim/Qiskit et ne doit pas être remplacée par une matrice dense.

## Comparaison honnête

| Niveau | Sans brouillage t=1 | Profond t=2 |
|---|---|---|
| Petz abstrait | 1 | ≈1 |
| Clifford direct déterministe | 1, profondeur 12 | synthèse symplectique à faire |
| Préparation Choi routée | non nécessaire | profondeur 78, ressource seulement |
| Synthèse dense générique | profondeur 703, contrôle négatif | non utilisée |

La profondeur 703 provient donc du compilateur universel et ne caractérise pas Petz. La profondeur 78 est le coût de préparer une ressource Choi, pas encore celui du canal de décodage.
