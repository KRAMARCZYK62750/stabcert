# Régression pytket certifiée — A=1, A=8 et A=12

## Verdict

**3/3 instances validées.**

Pour chaque fixture, pytket produit une route différente de la route ORELIA. `reproducible-route` la refuse, `channel-certified` certifie le canal réduit, et les mutations de phase et de permutation sont rejetées.

| A | Route différente | Strict | Canal certifié | Phase rejetée | Permutation rejetée |
|---:|---:|---:|---:|---:|---:|
| 1 | True | rejeté | accepté | True | True |
| 8 | True | rejeté | accepté | True | True |
| 12 | True | rejeté | accepté | True | True |

## Ressources observées

| A | Profondeur logique | Profondeur ORELIA | Profondeur pytket | CNOT ORELIA | CNOT pytket | SWAP + restitution | BRIDGE |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 12 | 46 | 34 | 62 | 41 | 6 + 0 | 3 |
| 8 | 82 | 391 | 401 | 687 | 694 | 117 + 117 | 15 |
| 12 | 154 | 464 | 454 | 751 | 808 | 110 + 110 | 15 |

Sur `A=12`, pytket donne une profondeur légèrement inférieure à ORELIA mais davantage de CNOT. Ce croisement confirme qu'aucun classement scalaire n'est justifié avant un benchmark multidimensionnel et multi-instance.

## Configuration

- pytket `2.18.1` ;
- layout initial identité via `place_with_map` ;
- `RoutingPass` avec `LexiLabellingMethod` et `LexiRouteRoutingMethod` ;
- SWAP et BRIDGE décomposés exactement en CNOT ;
- ordre v1 restauré seulement lorsque la permutation nette n'est pas identité ;
- chaque compilation répétée et comparée exactement ;
- durée totale : `49.674990041` s ;
- RSS maximale : `55.968750` Mio.

## Limites

Le circuit logique de Petz est toujours synthétisé par ORELIA. pytket intervient uniquement pour le routage. Trois fixtures ne définissent ni une loi d'échelle ni une hiérarchie générale des routeurs.

## Sorties

- `results/pytket_regression_a1_a12.csv` ;
- `results/pytket_regression_a1_a12.json` ;
- artefacts pytket et mutations dans `results/` ;
- `tests/test_pytket_channel_certified.py`.
