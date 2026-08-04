# Démonstration symbolique « ORELIA »

## Ce qui est transmis

Le canal validé est `A` (un qubit) vers `A'` (un qubit). Bien que
`supp(tau_X)` ait quatre qubits logiques, ces degrés de liberté supplémentaires
comprennent l'environnement de la dilatation Petz et ne sont pas des qubits du
message récupéré. Une dilatation de Stinespring ne modifie pas le canal une fois
son environnement tracé.

Il est donc impossible de placer six états orthogonaux dans **une seule**
utilisation de ce canal binaire. La démonstration emploie trois utilisations
indépendantes et parallèles du même canal t=2, soit un registre symbolique de
trois qubits. Chaque utilisation conserve exactement le modèle à 10 qubits ;
une réalisation physique parallèle demanderait trois exemplaires, pas un
message à trois qubits dans l'exemplaire actuel.

## Alphabet

```text
O=000  R=001  E=010  L=011  I=100  A=101
```

Les tests comprennent ces six états, `(O+R)/sqrt(2)`, `(E+iL)/sqrt(2)` et la
superposition uniforme des six symboles. Ils comparent le Petz abstrait, la
dilatation Clifford directe et sa version routée sur chaîne.

## Interprétation

Une sortie `ORELIA -> ORELIA` signifie seulement que les six symboles ont été
transmis par six préparations indépendantes de ce registre à trois usages. Les
tests de superposition vérifient également les cohérences du canal produit.
Ce n'est ni du chiffrement, ni un stockage de document, ni un test d'un
message à trois qubits dans une seule instance Hayden--Preskill.

Les résultats chiffrés sont dans `results/orelia_symbolic_results.csv`.
