# Reproductibilité multi-graines du coût géométrique

Cette campagne conserve exactement le même routeur et le même budget sur
20 circuits logiques : A=9…12, cinq graines par taille, quatre architectures.
Elle contient 80 routages. Aucune instance n'est filtrée selon sa fidélité Petz.

## Distributions de profondeur

| A | architecture | min | Q1 | médiane | Q3 | max | rapport médian routé/logique |
|---:|---|---:|---:|---:|---:|---:|---:|
| 9 | chain | 398 | 426.0 | 451.0 | 455.0 | 493 | 4.68 |
| 9 | ring | 372 | 387.0 | 402.0 | 418.0 | 453 | 4.25 |
| 9 | grid_2d | 244 | 254.0 | 278.0 | 285.0 | 346 | 2.99 |
| 9 | all_to_all | 84 | 85.0 | 91.0 | 101.0 | 111 | 1.00 |
| 10 | chain | 555 | 564.0 | 600.0 | 628.0 | 635 | 4.98 |
| 10 | ring | 474 | 500.0 | 558.0 | 588.0 | 600 | 4.89 |
| 10 | grid_2d | 358 | 367.0 | 374.0 | 383.0 | 395 | 3.27 |
| 10 | all_to_all | 114 | 115.0 | 117.0 | 126.0 | 130 | 1.00 |
| 11 | chain | 540 | 547.0 | 558.0 | 568.0 | 587 | 4.19 |
| 11 | ring | 572 | 580.0 | 594.0 | 596.0 | 597 | 4.61 |
| 11 | grid_2d | 339 | 364.0 | 371.0 | 372.0 | 405 | 2.99 |
| 11 | all_to_all | 124 | 124.0 | 129.0 | 132.0 | 143 | 1.00 |
| 12 | chain | 647 | 755.0 | 795.0 | 869.0 | 932 | 5.16 |
| 12 | ring | 656 | 755.0 | 776.0 | 785.0 | 915 | 4.82 |
| 12 | grid_2d | 411 | 462.0 | 464.0 | 470.0 | 487 | 2.87 |
| 12 | all_to_all | 145 | 154.0 | 154.0 | 161.0 | 177 | 1.00 |

## Comparaisons appariées à la chaîne

| A | architecture | profondeur inférieure à la chaîne | réduction médiane | étendue |
|---:|---|---:|---:|---:|
| 9 | ring | 5/5 | 8.1 % | 5.6…14.2 % |
| 9 | grid_2d | 5/5 | 36.2 % | 29.8…45.9 % |
| 9 | all_to_all | 5/5 | 78.6 % | 77.5…80.3 % |
| 10 | ring | 5/5 | 5.5 % | 1.1…20.4 % |
| 10 | grid_2d | 5/5 | 36.2 % | 33.7…43.0 % |
| 10 | all_to_all | 5/5 | 79.9 % | 76.6…81.9 % |
| 11 | ring | 1/5 | -6.8 % | -10.6…2.6 % |
| 11 | grid_2d | 5/5 | 34.8 % | 26.0…37.2 % |
| 11 | all_to_all | 5/5 | 76.1 % | 74.4…78.9 % |
| 12 | ring | 3/5 | 1.8 % | -4.0…10.7 % |
| 12 | grid_2d | 5/5 | 40.9 % | 35.5…50.2 % |
| 12 | all_to_all | 5/5 | 80.6 % | 76.6…83.5 % |

Les comparaisons sont appariées : même A, même graine et même circuit logique.
Une réduction négative signifie que l'architecture comparée a été plus coûteuse
pour cette instance avec le routeur fixé.

## Validation

- Routages validés : 80/80.
- Fidélité Petz observée : 0.25…1.
- Écart maximal circuit/Petz : 0.000e+00.
- Temps total : 187.685 s.
- RSS maximale : 79.7 Mio.

## Interprétation autorisée

La campagne mesure si l'avantage géométrique observé persiste au-delà d'une
seule graine dans cette famille finie. Elle ne démontre ni une profondeur
minimale, ni une loi d'échelle, ni les performances d'un dispositif réel.
Le bruit, la correction d'erreurs et les contraintes matérielles de parallélisme
ne sont pas modélisés.
