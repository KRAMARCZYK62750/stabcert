# Régression du routage paramétrique

Statut : **validé — 60/60 cas passent**.
Tolérance numérique : `1e-12`.

| Ressource | minimum | maximum |
|---|---:|---:|
| profondeur locale | 36 | 112 |
| CNOT routés | 55 | 146 |
| SWAP | 8 | 40 |

Pour chaque instance, fidélité routée et erreur opératorielle coïncident avec
l'oracle historique à moins de `1e-12`. Profondeur, CNOT, SWAP et ordre final
des fils coïncident exactement. Le routeur paramétrique utilise uniquement
`SystemLayout.chain(t)` et restitue cette permutation à l'identité.

Le chemin historique est exécuté seulement après le calcul de toutes les
métriques paramétriques. Le chemin paramétrique n'importe ni CSV, ni module
`experiment`, ni constantes B=4. Aucune instance B=5 n'est exécutée.
