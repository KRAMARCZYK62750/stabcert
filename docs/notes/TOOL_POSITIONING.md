# Positionnement face aux outils de vérification existants

**Date :** 4 août 2026. Note de positionnement, distincte de
`NOVELTY_AUDIT.md` qui porte sur le résultat mathématique et non sur l'outil.

Rédigée en se demandant, pour chaque phrase, ce qu'un auteur de l'outil décrit
en penserait. Une comparaison qui cesse d'être juste quand la partie comparée
la lit ne vaut rien.

## L'axe qui sépare

Il tient à la nature de l'**entrée** :

| outil | ce qu'il faut lui fournir | question à laquelle il répond |
|---|---|---|
| Qbricks | un programme écrit dans son DSL, spécifié | ce programme construit-il le circuit qu'il prétend construire ? |
| QCEC | deux circuits | ces deux circuits font-ils la même chose ? |
| StabCert | une spécification de canal et un circuit | ce circuit réalise-t-il le canal spécifié ? |

Les trois questions sont légitimes et différentes. Aucune ne subsume les
autres.

## Qbricks

Vérification déductive sur Why3, obligations de preuve déchargées par
solveurs SMT. Périmètre général — Shor, QPE, Grover, non-Clifford inclus — au
prix d'un effort de spécification et de preuve. Ce n'est pas une procédure de
décision, et ça ne cherche pas à l'être : c'est le compromis assumé de la
vérification déductive, qui achète la généralité par du travail humain.

**Il n'y a pas de comparaison chiffrée honnête à construire.** Ré-exprimer une
fixture StabCert comme programme Qbricks mesurerait l'effort de preuve requis ;
faire tourner StabCert sur un circuit Qbricks mesurerait autre chose encore. Les
deux nombres n'ont pas la même unité, et les mettre dans une table donnerait une
apparence de commensurabilité qui n'existe pas.

Cette non-comparabilité tient à la nature des deux outils. Elle ne dépend
d'aucune limitation datée susceptible d'être levée : même si Qbricks élargit
son périmètre, il faudra toujours écrire son programme chez eux pour être
vérifié par eux, et c'est précisément ce que StabCert ne demande pas.

## QCEC

Prend deux circuits `G` et `G'`, forme `G G'†` et décide si le résultat est
l'identité. Deux moteurs complémentaires — diagrammes de décision, exacts, et
réécriture ZX, plus rapide sur les cas où les DD gonflent — combinés
délibérément, la réécriture ZX servant à établir l'équivalence là où les DD
peinent. L'exploitation de la structure `G G'†` est leur apport publié : c'est
ce qui maintient les diagrammes petits en pratique là où le pire cas théorique
est exponentiel.

**Correction d'une erreur que cette note portait dans sa première version.**
QCEC gère les qubits ancilla et les qubits *garbage*, y compris deux circuits
de largeurs différentes, et propose une équivalence partielle définie sur les
distributions de mesure. La tolérance à des conventions d'ancilla différentes
n'est donc **pas** un facteur distinctif — j'avais affirmé le contraire sans
l'avoir testé.

Ce qui subsiste, et c'est un seul point :

> QCEC compare un circuit à un **autre circuit**. StabCert compare un circuit à
> une **spécification mathématique**, dont il reconstruit la cible lui-même.

Ce n'est pas un défaut de QCEC : dans son cas d'usage — vérifier qu'un
compilateur a préservé le circuit source — la référence *est* la spécification,
et la question est bien posée. C'est un cas d'usage différent, pas un cas
d'usage moins bon.

Le cas où l'écart compte est celui où aucune référence n'existe encore : quand
la cible est définie mathématiquement, en l'occurrence un récupérateur de Petz
dérivé d'un problème stabilisateur, et qu'aucun circuit correct n'est
disponible pour servir de témoin.

Sur les fixtures `A=1/8/12`, un circuit de référence existe — celui d'ORELIA.
**Une comparaison avec QCEC y est donc constructible**, contrairement à
Qbricks. Je n'ai pas exécuté QCEC : je ne fais aucune prédiction sur son
verdict ni sur ses temps. Toute table exigera sa spécification pré-enregistrée,
répondant à la même question que partout ailleurs dans ce dépôt — que tient-on
fixe, et comment le sait-on fixe.

## Base de confiance

Une comparaison de tableaux signés sur GF(2) est auditable ligne à ligne par un
humain. Une trace de solveur SMT ou une réécriture de diagramme de décision ne
l'est pas de la même façon.

C'est une différence de nature de l'objet vérifiable, et rien de plus. Elle
n'implique **pas** que ce code soit plus fiable que Z3 ou que les DD de MQT :
ces bibliothèques sont éprouvées par un grand nombre d'utilisateurs depuis des
années, celle-ci ne l'est pas. Le rapport de maturité est dans l'autre sens, et
toute formulation qui le masquerait serait fausse.

## Ce que cette note ne fait pas

Elle ne classe pas les outils, n'affirme aucune supériorité, et ne rapporte
aucune mesure d'un outil tiers qui n'ait pas été exécutée. Les seules
différences retenues sont celles qu'un auteur de l'outil concerné
reconnaîtrait comme des descriptions exactes de ce qu'il a conçu.
