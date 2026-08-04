# Qualification adversariale reproductible du vérificateur

## Périmètre

Cette campagne qualifie localement le vérificateur v1 sur des cas dérivés de la fixture immuable collective `A=1`. Elle ne constitue ni une preuve formelle d'absence de faille, ni une garantie générale de sécurité.

> **Deux campagnes distinctes coexistent dans ce dépôt.** Celle-ci —
> `orelia.verifier-adversarial-campaign/v1`, 3 août 2026, 10 000 artefacts
> corrompus et 1 000 représentations valides — porte sur le vérificateur v1.
> La campagne `orelia.channel-certified-adversarial-campaign/v1`, même date,
> 1 300 invalides et 700 valides, porte sur la politique `channel-certified`
> et est documentée dans `CHANNEL_CERTIFIED_IMPLEMENTATION.md`. Les chiffres
> ne se contredisent pas : ils mesurent deux objets différents.

- Format : `orelia.verifier-adversarial-campaign/v1`
- Graine : `20260803`
- Artefacts corrompus : `10000`
- Artefacts valides équivalents : `1000`
- Durée totale : `1077.369117750` s
- RSS maximale observée : `51.609375` Mio
- Verdict : **VALIDÉ**

Les mutations sémantiques sont structurellement valides et re-scellées : elles ne dépendent pas d'un échec superficiel de parsing ou de hash pour être rejetées. Les cas JSON malformés sont mesurés séparément.

## Résultats par catégorie

| Catégorie | Validité attendue | Cas | Acceptés | Rejetés | Faux acceptés | Faux rejetés | Contrôle attendu atteint |
|---|---:|---:|---:|---:|---:|---:|---:|
| semantic_hash | False | 700 | 0 | 700 | 0 | 0 | 700 |
| document_hash | False | 700 | 0 | 700 | 0 | 0 | 700 |
| topology_claim | False | 700 | 0 | 700 | 0 | 0 | 700 |
| tau_signed_generator | False | 700 | 0 | 700 | 0 | 0 | 700 |
| tau_dimensions | False | 700 | 0 | 700 | 0 | 0 | 700 |
| petz_target_claim | False | 700 | 0 | 700 | 0 | 0 | 700 |
| wrong_channel_resealed | False | 700 | 0 | 700 | 0 | 0 | 700 |
| logical_routed_mismatch | False | 700 | 0 | 700 | 0 | 0 | 700 |
| forbidden_edge_identity | False | 700 | 0 | 700 | 0 | 0 | 700 |
| nondeterministic_route_identity | False | 700 | 0 | 700 | 0 | 0 | 700 |
| resource_accounting | False | 700 | 0 | 700 | 0 | 0 | 700 |
| final_permutation | False | 600 | 0 | 600 | 0 | 0 | 600 |
| certificate_claim | False | 500 | 0 | 500 | 0 | 0 | 500 |
| fidelity_claim | False | 500 | 0 | 500 | 0 | 0 | 500 |
| malformed_serialized_artifact | False | 700 | 0 | 700 | 0 | 0 | 700 |
| target_environment_gauge | True | 250 | 250 | 0 | 0 | 0 | 250 |
| tau_equivalent_basis | True | 250 | 250 | 0 | 0 | 0 | 250 |
| circuit_environment_gauge | True | 250 | 250 | 0 | 0 | 0 | 250 |
| circuit_identity_rewrite | True | 250 | 250 | 0 | 0 | 0 | 250 |

## Correspondance mutation–contrôle

- hash sémantique ou documentaire → contrôles de provenance ;
- générateurs ou dimensions de `tau_X` → support stabilisateur signé ;
- Choi Petz faux mais structurellement valide → reconstruction indépendante de la cible ;
- canal re-scellé mais faux → égalité des Choi réduits ;
- action logique, arête interdite et route non déterministe → contrôles Clifford, topologique et de routage ;
- ressources, permutation, certificat et fidélité → recomptages indépendants ;
- JSON incomplet, inconnu ou non conforme → validation stricte du modèle.

Les variantes valides couvrent le changement de base du même sous-groupe de stabilisateurs, la jauge de purification sur l'environnement, une Clifford finale sur l'environnement rejeté et des réécritures de circuit identitaires.

## Incident découvert pendant la qualification

Le pré-échantillonnage a montré que `logical_action_signature` n'était pas reconstruite par le vérificateur. Le contrôle a été ajouté avant la campagne complète, puis les fixtures A=1, A=8 et A=12 ont été rejouées avec succès.

## Conclusion locale

Sur `10000` artefacts corrompus générés selon les catégories documentées, le vérificateur a rejeté les `10000` cas. Sur `1000` artefacts valides équivalents, aucun faux rejet n'a été observé.

La règle indicative `3/N` donne `0.0003` (soit `0.03 %`) à 95 %, uniquement relativement au processus de mutation testé. Elle ne mesure pas une probabilité générale de compromission.

## Reproductibilité

- Python : `3.14.6`
- NumPy : `2.5.1`
- Stim : `1.16.0`
- Noyau : `orelia-recovery-core/0.2.0`
- Hash du problème : `b326bf2c8457884a13059c1c4c296a51c9669f3e565ced871f75d6abed0d678d`
- Hash documentaire du problème : `b2228ed0fcc30fef7c47bc8ddb58de30cc82e957c33d6af55f6fda44cbd56622`
- Hash documentaire de l'artefact de base : `445d3aa216eee1dbe5fdf69b6e01793a973e70101461e01bcaf13d4dddf20927`
- Hash du générateur : `6b663e8514cff6fef7fc825a16604756e9fcb90d7a453d54829e5ffa1476e549`
- Hash du vérificateur : `b3987e836215778106d0088b20fed1726eb6ff6325631eb2b450aa931f02bb43`

Commande :

```bash
.venv/bin/python run_verifier_adversarial_validation.py
```
