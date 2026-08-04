# Implémentation et qualification du mode `channel-certified`

## Résultat

Statut : **VALIDÉ**.

Le vérificateur reconstruit la cible Petz depuis `RecoveryProblem`, compare les sous-groupes stabilisateurs signés des Choi réduits et ne reconstruit pas la route ORELIA attendue dans cette politique.

- cas invalides : `1300` ;
- représentations valides : `700` ;
- faux acceptés : `0` ;
- faux rejetés : `0` ;
- durée : `163.064756500` s ;
- suite automatique complète : <!-- TEST_COUNT:BEGIN fmt="`{passed}/{passed}` tests passants" -->`124/124` tests passants<!-- TEST_COUNT:END -->.

> Ces chiffres sont ceux de la campagne
> `orelia.channel-certified-adversarial-campaign/v1` (3 août 2026), qui porte
> sur la politique `channel-certified`. Elle est distincte de la campagne
> `orelia.verifier-adversarial-campaign/v1` (même date, 10 000 invalides et
> 1 000 valides) documentée dans `VERIFIER_ADVERSARIAL_VALIDATION.md`, qui
> porte sur le vérificateur v1.

## Résultats adversariaux

| Catégorie | Valide attendu | Cas | Acceptés | Rejetés | Faux acceptés | Faux rejetés | Premier contrôle correct |
|---|---:|---:|---:|---:|---:|---:|---:|
| semantic_hash | False | 100 | 0 | 100 | 0 | 0 | 100 |
| document_hash | False | 100 | 0 | 100 | 0 | 0 | 100 |
| topology_claim | False | 100 | 0 | 100 | 0 | 0 | 100 |
| tau_signed_generator | False | 100 | 0 | 100 | 0 | 0 | 100 |
| tau_dimensions | False | 100 | 0 | 100 | 0 | 0 | 100 |
| petz_target_claim | False | 100 | 0 | 100 | 0 | 0 | 100 |
| wrong_channel | False | 100 | 0 | 100 | 0 | 0 | 100 |
| forbidden_edge | False | 100 | 0 | 100 | 0 | 0 | 100 |
| observable_resource | False | 100 | 0 | 100 | 0 | 0 | 100 |
| final_order | False | 100 | 0 | 100 | 0 | 0 | 100 |
| certificate_claim | False | 100 | 0 | 100 | 0 | 0 | 100 |
| fidelity_claim | False | 100 | 0 | 100 | 0 | 0 | 100 |
| malformed_json | False | 100 | 0 | 100 | 0 | 0 | 100 |
| target_environment_gauge | True | 100 | 100 | 0 | 0 | 0 | 100 |
| tau_equivalent_basis | True | 100 | 100 | 0 | 0 | 0 | 100 |
| deterministic_environment_gauge | True | 100 | 100 | 0 | 0 | 0 | 100 |
| deterministic_identity_rewrite | True | 100 | 100 | 0 | 0 | 0 | 100 |
| external_environment_gauge | True | 100 | 100 | 0 | 0 | 0 | 100 |
| external_identity_rewrite | True | 100 | 100 | 0 | 0 | 0 | 100 |
| uncertified_swap_claim | True | 100 | 100 | 0 | 0 | 0 | 100 |

Les réécritures identitaires et les jauges de Stinespring sur l'environnement sont acceptées lorsqu'elles préservent le canal réduit. Les canaux faux, arêtes interdites, ressources observables falsifiées et ordres finaux faux sont rejetés.

Les fixtures immuables `A=1`, `A=8` et `A=12` passent dans les deux politiques. Une route textuellement différente et une jauge d'environnement différente sont refusées par `reproducible-route` mais acceptées par `channel-certified` lorsque leur Choi réduit reste identique.

## Ressources certifiées

En `channel-certified` v1, CNOT, profondeur à deux qubits, nombre de fils d'environnement, topologie et ordre final restauré sont recalculés. Les nombres de SWAP de mouvement et de restitution sont `not_certified`, faute de trace de routage rejouable.

## Compatibilité

`RecoveryProblem v1` et `RecoveryArtifact v1` sont inchangés. La politique historique `reproducible-route` reste la valeur par défaut. `RecoveryRunReport` passe en v2 afin d'enregistrer explicitement la politique appliquée.

## Limites

Ce résultat porte sur la sous-classe v1 : isométries Clifford, ancillas stabilisatrices pures, référence Petz maximally mixed et pseudo-inverse exacte sur support. Il ne certifie ni les circuits non-Clifford, ni le bruit, ni la minimalité des ressources.

## Reproductibilité

- format : `orelia.channel-certified-adversarial-campaign/v1` ;
- graine : `20260803` ;
- Python : `3.14.6` ;
- NumPy : `2.5.1` ;
- Stim : `1.16.0` ;
- noyau : `orelia-recovery-core/0.3.0` ;
- hash problème : `b326bf2c8457884a13059c1c4c296a51c9669f3e565ced871f75d6abed0d678d` ;
- hash artefact : `445d3aa216eee1dbe5fdf69b6e01793a973e70101461e01bcaf13d4dddf20927` ;
- hash vérificateur : `5f2779d7fe1dabd5b0c760b4b95a7ec5b0d0051a8298b1ba2ad98bc93dbf78c1`.

Commande :

```bash
.venv/bin/python run_channel_certified_adversarial_validation.py
```
