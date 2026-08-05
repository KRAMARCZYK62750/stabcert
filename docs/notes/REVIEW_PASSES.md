# Les deux passes de relecture

**Date :** 4 août 2026. Plan d'exécution pour la relecture finale du papier.

Deux passes, **non commutatives**, et qui ne cherchent pas la même chose.

La passe 1 lit. Elle attrape les écarts de forme : un symbole employé sans
avoir été posé, deux noms pour un objet, une définition en double, une
instruction de lecture orpheline, deux sections qui s'opposent sur la nature
d'une affirmation.

La passe 2 recalcule. Elle est la seule à pouvoir contredire un chiffre.

**La passe 1 ne validera aucun nombre, et il ne faut pas le lui demander.**
Elle lira les chiffres comme cohérents parce qu'ils le sont entre eux : un
nombre faux propagé dans trois sections est parfaitement cohérent. Attendre
d'elle une validation, c'est reproduire le schéma de
`MECHANISM_SCOPE.md` — prêter à un mécanisme plus qu'il ne promet.

L'ordre : passe 1 d'abord, parce qu'elle est rapide et voit ce que la passe 2
ne regarde pas. Passe 2 ensuite, parce qu'elle seule juge les affirmations.

---

## Passe 1 — relecture

### 1.1 Symboles

- [ ] Tout symbole employé dans une section figure dans la table des
      préliminaires, **ou** est défini là où il apparaît (`E`, `X̄ᵢ`, `Z̄ᵢ`,
      `Dⱼ` en Définition 1 ; `Ref(X)` en Définition 2).
- [ ] Entrées connues comme manquantes ou incomplètes dans la table :
  - [ ] `Λ`, `Λ′` — les canaux du Théorème 1, absents ;
  - [ ] `k` — entrée tronquée, vaut `|X| − |S_X|` ;
  - [ ] `S`, `S_X` — groupe source et sous-groupe survivant à la trace ;
  - [ ] `d` — vaut `2^|M|`, employé dans `τ_X = N(I/d)` ;
  - [ ] `sig(·)` — signature canonique signée ;
  - [ ] `Ref(X)` — référence du sous-espace de code, `|X|` fils.
- [ ] Aucun symbole posé n'est inutilisé.
- [ ] `R` ne désigne que la référence purifiante — les canaux sont `Λ`, `Λ′`.
      Deux références distinctes coexistent, `R` sur `|M|` fils et `Ref(X)`
      sur `|X|` : vérifier qu'aucun passage ne les confond.

### 1.2 Nommage — un objet, un nom

Deux objets seulement, trois noms en circulation :

| objet | nom retenu | noms à éliminer |
|---|---|---|
| l'état | *code-Choi state*, `J_Π(Λ)` | *code-Choi tableau* |
| sa forme canonique | *canonical signed signature*, `sig(·)` | *canonical form*, *tableau* |

- [ ] *tableau* reste réservé aux préliminaires, pour la représentation
      binaire d'un groupe stabilisateur.
- [ ] Passe sur les quatre textes : abstract, introduction, §3, §7.

### 1.3 Duplications

- [ ] « canal stabilisateur » est défini en §2 **et** en §4.1. Une seule
      définition ; l'autre renvoie.
- [ ] Gottesman–Knill est posé en §2 comme fondement, pas cité en §4.1 comme
      concession.

### 1.4 Instructions de lecture orphelines

- [ ] §6.3 : « à lire horizontalement, pas verticalement » doit être attaché
      **aux deux tableaux**, pas au premier seulement.
- [ ] §6.3 : la colonne d'architecture est présente dans les deux tableaux —
      sans elle la non-monotonie du surcoût se lit comme un effet de taille.
- [ ] §7.4 : la colonne de tendance est présente. Le verdict « confirmé » a
      deux conditions ; sans elle le lecteur n'en vérifie qu'une.

### 1.5 Contradictions de nature entre sections

- [ ] **§4.4 contre §6.3** — le §4.4 doit dire que profondeur et compte de
      portes à deux qubits sont recalculés et **entrent dans le verdict** ;
      seule l'attribution des SWAP ne participe à rien. La version prudente
      (« reported, not certified ») contredit le §6.3.
- [ ] **« sound and complete », quatre occurrences** — abstract, introduction,
      §4.1, README. Vérifier que chacune attribue la propriété à la **procédure
      de décision**, et que l'introduction porte la phrase qui la sépare des
      chiffres de campagne du §6.
- [ ] **Abstract** — l'incise sur la relativité à `Π` est présente. Sans elle,
      l'énoncé attribue une forme canonique aux canaux et l'Hypothèse 1
      disparaît.
- [ ] **Introduction** — l'état est décrit comme **mixte**. « stabilizer
      state » seul suggère pur, et c'est l'erreur corrigée en Définition 2 ;
      la première occurrence rencontrée par le lecteur est celle-ci.
- [ ] **§4.3** — `admits` / `contains no` / `claim nothing`. Aucun mécanisme
      de syndrome décrit au présent de l'indicatif.
- [ ] **§5.4** — formulation opérationnelle depuis que la CI est verte.

### 1.6 Renvois

- [ ] Toute référence à une section pointe vers celle qui porte le contenu.
- [ ] Le §4.5 renvoie au §7.6 pour les régimes de dérive plutôt que de
      réargumenter.

---

## Passe 2 — recalcul

Un seul principe, et il est déjà écrit dans `MECHANISM_SCOPE.md` :

> Une quantité **mesurée** exige un artefact. Une quantité **dérivée** exige sa
> formule. Un nombre qui n'a ni l'un ni l'autre n'est pas vérifiable, quelle
> que soit sa justesse.

Chaque nombre du papier est repris **depuis son artefact**, jamais depuis un
message ou une version antérieure du texte. La table de correspondance
section → artefact sert de plan.

Deux points d'attention hérités de la rédaction :

- [ ] Tout exposant cité nomme **sa plage et sa fenêtre**. Trois valeurs
      circulent pour le temps — 4,67 global sur `n ≤ 20`, 4,83 fenêtre haute
      sur `n ≤ 30`, 4,78 fenêtre haute sur `n ≤ 40` — toutes justes pour la
      leur.
- [ ] Les densités de codes de surface sont **dérivées** : la formule est
      écrite, pas le seul résultat.
