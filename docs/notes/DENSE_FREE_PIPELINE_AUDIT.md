# Audit du pipeline entièrement stabilisateur

Statut : **validé pour A=1 à A=7 ; A=8 non exécuté**.

La régression dense/structurelle complète est documentée dans
`DENSE_FREE_CHAIN_REGRESSION.md`. Cette confirmation utilise uniquement
`dense_free_pipeline.run_structural_instance` pour l'instance A=7.

## Confirmation A=7

- temps sélectionné : `t=8` ;
- alphabet collectif : 128 ;
- fidélités Petz/directe/routée : `1.0` /
  `1.0` / `1.0` ;
- profondeur : `65 -> 413` ;
- CNOT : `93 -> 603` ;
- SWAP : `170` ;
- temps total : `3.122 s` ;
- RSS maximale : `40.1 Mio`.

Objets denses construits par le chemin : canal=`False`,
tau_X=`False`, Choi=`False`,
validation=`False`.

## Portée

Cette absence d'objets denses vaut pour la sous-classe pure Clifford auditée.
Les anciens constructeurs NumPy/SVD sont conservés uniquement dans les scripts
de régression. Aucun pré-vol A=8 n'est inclus dans cette clôture.
