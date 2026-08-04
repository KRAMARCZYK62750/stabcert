# Intégration SABRE avec `channel-certified`

## Verdict

**VALIDÉ sur la fixture A=1.**

Qiskit SABRE a routé le circuit Clifford logique de Petz avec un layout initial fixé. La route obtenue est différente de la route ORELIA historique. L'ordre v1 a été restauré en rejouant en sens inverse les SWAP explicitement insérés par SABRE.

| Test | Résultat |
|---|---:|
| Circuit SABRE différent du circuit ORELIA | oui |
| `reproducible-route` sur SABRE | rejeté |
| `channel-certified` sur SABRE | accepté |
| Mutation de phase `Z` sur la sortie | rejetée |
| Mutation de permutation finale | rejetée |

## Configuration figée

- Qiskit : `2.5.1` ;
- graine SABRE : `20260803` ;
- heuristique : `decay` ;
- essais SABRE : `1` ;
- layout initial : identité sur l'ordre physique de `RecoveryProblem` ;
- restauration : inverse exact de la séquence de SWAP SABRE ;
- SWAP : expansion normative en trois CNOT ;
- durée de construction mesurée : `0.395258416` s.

## Ressources observées

| Route | Profondeur 2Q | CNOT | SWAP mouvement | SWAP restitution |
|---|---:|---:|---:|---:|
| ORELIA | 46 | 62 | 12 | 4 |
| SABRE + restauration v1 | 49 | 68 | 9 | 9 |

Ces nombres décrivent une seule instance et ne constituent pas encore un benchmark. En politique `channel-certified`, les CNOT et la profondeur sont recalculés, mais le découpage des SWAP reste déclaré `not_certified` faute de trace normative dans `RecoveryArtifact v1`.

## Contrôles négatifs

- route SABRE en politique stricte : `deterministic_routing, resource_accounting` ;
- mutation de phase : `reduced_choi_channel, certificate_signature_claims, circuit_entanglement_fidelity` ;
- mutation de permutation : `restored_final_order_declaration`.

## Portée exacte

Ce test montre qu'ORELIA peut certifier une route produite par un véritable routeur tiers. Il ne montre pas encore qu'ORELIA importe tout circuit Qiskit, que SABRE est meilleur ou moins bon, ni que le résultat s'étend au non-Clifford.

Le circuit logique de Petz reste synthétisé par ORELIA ; SABRE intervient ici uniquement pour le placement implicite initial fixé et le routage.

## Références d'interface

- Documentation IBM sur les méthodes de routage et la reproductibilité : https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.4/transpiler
- Documentation IBM sur les permutations de layout : https://quantum.cloud.ibm.com/docs/en/api/qiskit/1.4/qiskit.transpiler.TranspileLayout

## Artefacts

- `results/sabre_a1.artifact.json` — `415f8a305f19c9aae417c792492b7d7efea95e09fea45dc75d64e1a504a69b89` ;
- `results/sabre_a1_phase_mutation.artifact.json` — `39405b992da588677fe2713f8ea40b4ce8595d8c79fff2da37373b47fb560649` ;
- `results/sabre_a1_permutation_mutation.artifact.json` — `93aeca096b1c7560648181f15b11cd1ca102ee4a1542d9a38d3b4f8d173a69b3` ;
- `results/sabre_channel_certified_integration.json` — `72c78a23e96a74de18240743da6c436801a947f5e7b1fc50bd04fcbb7828547a`.
