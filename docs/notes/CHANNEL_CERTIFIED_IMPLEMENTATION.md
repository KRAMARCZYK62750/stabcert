# Implémentation et qualification du mode `channel-certified`

## Résultat

Statut : **VALIDÉ**.

Le vérificateur reconstruit la cible Petz depuis `RecoveryProblem`, compare les sous-groupes stabilisateurs signés des Choi réduits et ne reconstruit pas la route ORELIA attendue dans cette politique.

- cas invalides : `1300` ;
- représentations valides : `800` ;
- faux acceptés : `0` ;
- faux rejetés : `0` ;
- durée : `176.246987167` s.

> **Deux campagnes distinctes coexistent dans ce dépôt.** Celle-ci —
> `orelia.channel-certified-adversarial-campaign/v1` — porte sur la politique
> `channel-certified`. La campagne `orelia.verifier-adversarial-campaign/v1`
> (10 000 invalides et 1 000 valides) porte sur le vérificateur v1 et figure
> dans `VERIFIER_ADVERSARIAL_VALIDATION.md`. Les chiffres ne se contredisent
> pas : ils mesurent deux objets différents.

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
| outside_support_only | True | 100 | 100 | 0 | 0 | 0 | 100 |

Les réécritures identitaires et les jauges de Stinespring sur l'environnement sont acceptées lorsqu'elles préservent le canal réduit. Les canaux faux, arêtes interdites, ressources observables falsifiées et ordres finaux faux sont rejetés.

### Ce que `outside_support_only` établit

Cette famille préfixe le circuit par un élément du groupe stabilisateur de
`tau_X`. Tout état du sous-espace de code en est un vecteur propre `+1` :
l'action y est donc inchangée, alors que l'unitaire total diffère.

C'est la seule famille de la campagne qui sépare deux spécifications :

- comparaison du canal **sur le sous-espace de code** — ces artefacts doivent
  être acceptés, et ils le sont ;
- comparaison du **canal total** — ces mêmes artefacts devraient être rejetés.

Sans elle, aucun chiffre de cette campagne ne dit laquelle des deux est
implémentée. Le README affirme `on the specified input subspace` ; cette
ligne du tableau est ce qui le teste.

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
