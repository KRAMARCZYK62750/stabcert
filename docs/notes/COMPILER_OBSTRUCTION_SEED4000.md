# Diagnostic de compilation — seed 4000, profondeur 9, t=2

## Reproduction

L'échec était déterministe : Petz avait une fidélité d'intrication
`0.9999999999999956`, mais `stim.Tableau.from_conjugated_generators` refusait
le tableau d'entrée avant toute synthèse. La première relation incorrecte était
le déstabilisateur 1, qui devait anticommuer avec le stabilisateur 1 seulement
mais anticommutaient aussi avec le second stabilisateur fourni au tableau.

## Cause exacte

Deux bases indépendantes du même sous-groupe stabilisateur avaient été
construites :

1. une base binaire, utilisée pour les paires logiques et déstabilisateurs ;
2. une base signée indépendante, choisie séparément pour les phases.

La seconde entrée signée de cette deuxième base était `+ZXZYYI`, tandis que le
second générateur binaire auquel elle avait été associée était `XYYZYX`.
L'appartenance au même sous-groupe ne permet pas cet appariement position par
position : le tableau complet exige les mêmes vecteurs binaires, avec leurs
signes physiques.

Le correctif cherche maintenant le représentant signé de **chaque vecteur
binaire déjà sélectionné**. Les deux générateurs utilisés sont donc
`-YZXXIX` et `+XYYZYX`.

## Classification

| Hypothèse | Verdict |
|---|---|
| convention Choi ou jauge incorrecte | écartée : convention inchangée |
| base logique/déstabilisateurs incomplets | écartée après alignement |
| ancilla stabilisatrice supplémentaire nécessaire | non : dilatation à 6 fils validée |
| canal non stabilisateur | écartée : Choi signé stabilisateur et identique |
| bug du compilateur | confirmé : mauvais appariement base binaire/base signée |

## Validation après correctif

La dilatation Clifford t=2 est désormais validée sans ancilla supplémentaire :

| Quantité | Valeur |
|---|---:|
| erreur opératorielle maximale | 5.25e-15 |
| fidélité Choi | 0.999999999999992 |
| profondeur logique | 25 |
| profondeur routée | 65 |

Les données complètes de générateurs et le premier conflit sont dans
`results/compiler_obstruction_seed4000.csv`. La grille B=4 peut maintenant
être relancée ; elle reste une étude de coût observé, sans preuve de minimalité.

## Cas de dimension de sortie différente

La grille élargie a aussi rencontré des supports d'entrée à trois qubits
logiques dont la dilatation Petz a quatre fils de sortie (`A'` plus trois fils
d'environnement). Ce n'était pas une nouvelle obstruction : l'image est alors
un code stabilisateur à un stabilisateur sur ces quatre fils. Le compilateur
extrait ce stabilisateur signé du Choi et ajoute son déstabilisateur au tableau
de sortie. Aucun qubit physique supplémentaire n'est ajouté : le fil est déjà
dans l'environnement de Petz. Les 60 instances B=4 t=2 passent après cette
complétion.
