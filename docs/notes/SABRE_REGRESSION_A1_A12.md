# Régression SABRE certifiée — A=1, A=8 et A=12

## Verdict

**3/3 instances validées.**

Pour chaque fixture immuable, SABRE produit une route différente de la route ORELIA. La politique `reproducible-route` la refuse, tandis que `channel-certified` certifie exactement le canal réduit. Une phase `Z` ajoutée à la sortie et une permutation finale falsifiée sont rejetées pour chaque taille.

| A | Route SABRE différente | Strict | Canal certifié | Phase rejetée | Permutation rejetée |
|---:|---:|---:|---:|---:|---:|
| 1 | True | rejeté | accepté | True | True |
| 8 | True | rejeté | accepté | True | True |
| 12 | True | rejeté | accepté | True | True |

## Ressources observées

| A | Profondeur logique | Profondeur ORELIA | Profondeur SABRE | CNOT ORELIA | CNOT SABRE | SWAP SABRE |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 12 | 46 | 49 | 62 | 68 | 9 + 9 restitution |
| 8 | 82 | 391 | 584 | 687 | 939 | 138 + 138 restitution |
| 12 | 154 | 464 | 668 | 751 | 1177 | 158 + 158 restitution |

Sur ces trois fixtures et avec ce protocole figé, SABRE produit davantage de profondeur et de CNOT que le routeur ORELIA. Trois instances ne suffisent pas pour conclure à une supériorité générale. La restauration v1 par inversion de tous les SWAP SABRE est correcte mais volontairement conservatrice.

## Reproductibilité

- Qiskit `2.5.1` ;
- `SabreSwap`, heuristique `decay` ;
- graine `20260803` ;
- `trials=1` ;
- layout initial identité ;
- chaque compilation a été répétée et comparée exactement ;
- durée totale : `50.057439333` s ;
- RSS maximale : `88.953125` Mio.

## Limites

Le circuit logique de Petz est synthétisé par ORELIA ; SABRE assure uniquement le routage. Cette régression ne constitue ni une loi d'échelle, ni un benchmark statistique, ni une preuve de minimalité.

## Sorties

- `results/sabre_regression_a1_a12.csv` ;
- `results/sabre_regression_a1_a12.json` ;
- artefacts SABRE et mutations dans `results/` ;
- tests automatiques dans `tests/test_sabre_channel_certified.py`.
