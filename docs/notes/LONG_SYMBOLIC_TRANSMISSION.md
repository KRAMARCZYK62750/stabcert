# Transmission symbolique longue

## Résultat numérique

Instance inchangée : B=4, t=2, graine=20260802,
profondeur de brouillage=6. Le texte est traité comme
une suite de 18 symboles sans signification particulière.

| décodeur | sortie | caractères corrects | taux correct | fidélité moyenne des symboles | fidélité d'intrication par caractère |
|---|---|---:|---:|---:|---:|
| Petz abstrait | `ORELIA EST VIVANTE` | 18/18 | 1 | 0.999999999999984 | 0.999999999999983 |
| Clifford direct | `ORELIA EST VIVANTE` | 18/18 | 1 | 0.999999999999971 | 0.999999999999971 |
| Clifford route chaine | `ORELIA EST VIVANTE` | 18/18 | 1 | 0.999999999999971 | 0.999999999999971 |

Entrée : `ORELIA EST VIVANTE`  
Sortie Petz abstrait : `ORELIA EST VIVANTE`  
Sortie Clifford direct : `ORELIA EST VIVANTE`  
Sortie Clifford routé : `ORELIA EST VIVANTE`

## Encodage effectivement utilisé

Le message contient 11 symboles distincts. Trois usages
indépendants ne fournissent que 8 états orthogonaux ; ils sont donc
dimensionnellement insuffisants. Après validation explicite, cette expérience
emploie **quatre usages parallèles indépendants du canal un-qubit par caractère**,
soit 16 mots de code possibles :

`O=0000`  `R=0001`  `E=0010`  `L=0011`  `I=0100`  `A=0101`  `ESPACE=0110`  `S=0111`  `T=1000`  `V=1001`  `N=1010`

Ce changement ne crée pas un message de quatre qubits dans une seule dynamique
Hayden--Preskill. Chaque caractère mobilise quatre exemplaires indépendants de
l'instance B=4 déjà validée.

## Coûts observés

Les quatre usages d'un caractère sont parallèles : leurs profondeurs ne
s'additionnent pas, tandis que CNOT et SWAP sont des comptes agrégés. Les 18
caractères sont comptés successivement pour le coût total du message.

| réalisation | profondeur/caractère | CNOT/caractère | SWAP/caractère | profondeur totale séquentielle | CNOT totaux | SWAP totaux |
|---|---:|---:|---:|---:|---:|---:|
| Clifford direct | 12 | 56 | 0 | 216 | 1008 | 0 |
| Clifford routé | 84 | 392 | 112 | 1512 | 7056 | 2016 |

Pour chaque colonne de coût applicable, le total a été recalculé comme somme
des 18 coûts élémentaires et l'égalité est vérifiée automatiquement. Petz
abstrait n'a pas de coût de circuit attribué.

## Portée

Cette expérience vérifie uniquement que le pipeline paramétrique déjà validé
fonctionne sur une séquence plus longue. Elle ne démontre aucune propriété
nouvelle du canal, aucun stockage de document, aucun chiffrement et aucun
brouillage collectif d'un message de quatre qubits.

Les valeurs par caractère sont dans
`results/long_symbolic_transmission.csv`; les agrégats sont dans
`results/long_symbolic_transmission_summary.csv`.
