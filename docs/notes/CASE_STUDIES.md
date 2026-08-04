# Étude de cas locale initiale

## Contrôle : B=4, sans brouillage, t=1

La dilatation Petz a une fidélité abstraite `1` et une extension de Stinespring vérifiée à `1`. La synthèse matricielle générique sur la chaîne de cinq qubits est exacte à `5.03e-15` après prise en compte de la permutation finale de routage.

Elle produit néanmoins 423 CNOT, 342 SWAP et une profondeur deux-qubits de 703. Ce chiffre ne caractérise pas intrinsèquement Petz : l’extension hors du support est arbitraire et la synthèse générique ignore la structure Clifford. Il est donc conservé comme contrôle d’outillage, pas comme mesure de coût de décodage.

La sortie logique est déplacée au site physique 2 par le routeur; la permutation finale et sa restauration éventuelle sont comptées séparément dans `local_decoding_results.csv`.

## Conséquence méthodologique

Une frontière opérationnelle utile exigera une synthèse stabilisatrice/tableau qui fixe une extension canonique, puis un routage local de ce circuit. Une décomposition d’unitaire dense générique est vérifiable mais trop dépendante du choix arbitraire hors support pour servir de comparaison scientifique.
