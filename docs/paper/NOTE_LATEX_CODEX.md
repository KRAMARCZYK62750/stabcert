# Note pour Codex — résultat de la première compilation

**Le `.tex` compile.** 14 pages, zéro erreur, 5 dépassements de marge.

Compilé avec `pdflatex` sur une machine disposant de TeX Live. Le fichier
d'origine ne compilait pas : **sept classes de défauts** dans
`build_paper_tex.py`, toutes trouvées en compilant, aucune visible à la
lecture du `.tex`.

Les corrections vont dans le générateur, pas dans le `.tex`.

---

## Classe 1 — Tableaux : les spans backtick sont découpés sur `|`

La plus grave, et fatale dès la première passe.

Le générateur découpe les lignes de tableau sur `|` **avant** de traiter les
spans entre backticks. Un span contenant des barres verticales est donc
massacré :

| source markdown | produit | attendu |
|---|---|---|
| `` `\|M\|` wires `` | `` ` & M & ` wires `` | `$\|M\|$ wires` |
| `` `d = 2^{\|M\|}` `` | `` `d = 2^{ & M & }` `` | `$d = 2^{\|M\|}$` |
| `` `k = \|X\| - \|S_X\|` `` | `` `k = & X & - & S_X & ` `` | `$k = \|X\| - \|S_X\|$` |

**Correctif :** protéger les spans backtick par des placeholders avant de
découper la ligne sur `|`, restaurer et convertir après. Cinq occurrences
dans la table des registres du §2.

## Classe 2 — Caractères Unicode passés tels quels

Vingt-et-un caractères non-ASCII sortent bruts. `pdflatex` s'arrête sur chacun.

À traduire, **en mode math** (`$\in$` et non `\in` nu, sinon la commande tombe
hors mode et l'erreur se déplace) :

```
∈ \in      ⊆ \subseteq   ⇐ \Leftarrow   ⇒ \Rightarrow
⊗ \otimes  → \to         Φ \Phi         Π \Pi
Λ \Lambda  σ \sigma      Θ \Theta       β \beta
· \cdot    − -           ² ^2           ⁴ ^4       ⁵ ^5
```

Cas composés, à traiter avant les simples :

- `Ē` (U+0112) → `\bar{E}`
- `Λ` + tilde combinant (U+039B U+0303) → `\tilde{\Lambda}`
- macrons combinants résiduels (U+0304) à supprimer

Un test de non-régression utile : `assert not [c for c in tex if ord(c) > 127]`
en fin de génération, hors caractères accentués légitimes du nom d'auteur.

## Classe 3 — Barres verticales mal appariées dans les spans math

Le générateur convertit `|X|-k` en `^{ \rvertX|-k}` : la première barre devient
`\rvert` au lieu de `\lvert`, la seconde reste littérale. Deux occurrences dans
la preuve du Théorème 1, §3.3.

**Correctif :** apparier les barres par paires avant conversion, ou utiliser
`\lvert ... \rvert` seulement quand le nombre de barres est pair.

## Classe 4 — Blocs de code clôturés non convertis

Les délimiteurs ` ``` ` sortent littéralement dans le `.tex`. Un seul bloc dans
le papier, et il contient une formule d'inversion de Choi — il devrait être une
`equation*`, pas un verbatim.

**Correctif :** convertir les blocs fenced. Si le bloc contient des symboles
mathématiques, `equation*` ; sinon `verbatim`. Ce bloc-ci est un cas où la
source markdown devrait sans doute porter directement du LaTeX.

## Classe 5 — Underscore non échappé hors mode math

`grid_2d` dans les cellules du §6.3 provoque `Missing $ inserted`. Quatre
occurrences.

**Correctif :** échapper `_` en `\_` dans le texte, jamais en mode math.

## Classe 6 — Exposants mal formés

Trois formes distinctes, toutes produites par la conversion des spans :

- `$n\cdotN_sys'(n)$` — commande collée à l'identifiant suivant
- `$1.2 \times 10^-^3$` — double exposant, doit être `10^{-3}`
- `$O(n$^4$)$` — mode math ouvert et refermé au milieu d'une expression

Le troisième est le plus révélateur : il vient de la conversion `²`/`⁴`/`⁵` en
`$^4$` sans regarder si on est déjà en mode math.

## Classe 7 — Cinq dépassements de marge

Lignes 432–439, 553–560 (deux fois), 566–574, 735–745. Ce sont des
avertissements, pas des erreurs — mais ils correspondent aux tableaux larges du
§6 et du §7.

**Correctif possible :** `\small` ou `\resizebox` sur les tableaux à six et sept
colonnes. Décision de rendu, à voir sur le PDF.

---

## Ce qui reste à vérifier

**Les citations.** J'ai compilé sans `stabcert.bib` — douze citations sont
`undefined`. La compilation complète est `pdflatex` → `bibtex` → `pdflatex` ×2,
et il faut la refaire avec le `.bib` pour contrôler que les onze entrées
sortent et qu'aucune n'est orpheline.

**Les environnements de théorème.** Ils compilent et se numérotent. À vérifier
sur le PDF que la numérotation rendue correspond à ce que la prose annonce —
le garde-fou du générateur contrôle la source, pas le rendu.

**Un test de compilation en CI.** Sept classes de défauts qu'aucune relecture
n'aurait vues, trouvées par une seule exécution. C'est l'argument pour ajouter
`pdflatex` au pipeline : le `.tex` est régénéré à chaque modification de la
source, et rien ne garantit aujourd'hui qu'il compile encore.
