# Un mécanisme garantit exactement ce qu'il dit

**Date :** 4 août 2026.

Le danger ne vient pas des mécanismes qui échouent. Il vient de ce qu'on leur
prête en plus de ce qu'ils promettent. Six instances du même schéma sont
apparues en une seule journée de travail sur ce dépôt, dans des domaines sans
rapport entre eux. Elles sont consignées ici parce que le schéma est plus
utile que chacun des cas.

## Les six

**Le `.get()` qui rendait `None`.** `compare_density_cost.py` contrôlait que
les deux bras partageaient le même rang de support. Les CSV du bras dense
étaient antérieurs à l'instrumentation : la colonne n'existait pas, `.get()`
rendait `None`, comparé à un entier — divergence à toutes les largeurs. Le
contrôle n'a pas eu lieu, et le script a **quand même émis un verdict**. Ce
qu'on lui prêtait : « il vérifie l'appariement ». Ce qu'il faisait : « il
compare deux valeurs, quelles qu'elles soient ».

**Le jackknife.** Ajuster `e(n) = d + K/n` pour extrapoler le degré
asymptotique donnait, sur l'étalon dont le degré vaut exactement 2 et sur
`n = 9…30`, une valeur de 1,929 avec un intervalle de [1,927 ; 1,930] — la
vérité exclue, l'intervalle trente fois trop serré. Ce qu'on lui prêtait : « il mesure l'incertitude sur
`d` ». Ce qu'il faisait : « il mesure la stabilité de l'ajustement », qui ne
voit pas un biais systématique.

**La profondeur fixe.** Le protocole densité tenait la profondeur du brouilleur
constante en croyant tenir la densité constante. À profondeur fixe, les CNOT
croissent en `n` et les entrées de matrice en `n²` : la densité normalisée
décroît nécessairement. Ce qu'on lui prêtait : « la densité est neutralisée ».
Ce qu'il faisait : « un paramètre corrélé à la densité est fixé ».

**Le synchroniseur de compteurs.** `sync_test_counts.py` garantit que les
documents correspondent à la suite **locale**. Le 124 publié était vrai dans le
répertoire de travail et faux partout ailleurs : 20 tests échouaient depuis un
clone propre, parce que des artefacts qu'ils lisent n'étaient pas suivis. Ce
qu'on lui prêtait : « le chiffre publié est correct ». Ce qu'il faisait : « le
chiffre publié correspond à ma machine ».

**Le statut de sortie lu à travers un tube.** Deux fois dans la même journée.
`pytest -q | tee out.txt` dans la CI : sans `pipefail`, le pipeline rend le
statut de `tee`, donc une suite en échec produisait un badge vert. Et
`sync_test_counts.py --check | tail -4 ; echo $?` dans une vérification
manuelle : le `$?` était celui de `tail`. Ce qu'on lui prêtait : « la commande
a réussi ». Ce qu'il disait : « la dernière commande du pipeline a réussi ».

> **Un statut de sortie lu à travers un tube n'est pas celui de la commande qui
> compte.** C'est la dernière du pipeline qui répond.

La formulation vaut mieux que « ajouter `pipefail` », qui ne donne que le
correctif d'un cas. Le cas grave n'était pas la CI mais la vérification
manuelle : elle a certifié comme correct un chemin qui sortait en erreur, et
c'est cette fausse confirmation qui a laissé la CI rouge une soirée.

**Deux générateurs pour un fichier.**
`CHANNEL_CERTIFIED_IMPLEMENTATION.md` est réémis en entier par le runner de
campagne. Une correction manuelle y avait été appliquée le matin — un compteur
de tests périmé — et la régénération du soir l'a effacée, faisant échouer le
contrôle de compteurs. Ce qu'on lui prêtait : « le fichier porte ce que j'y
ai écrit ». Ce qu'il faisait : « le fichier porte ce que le générateur émet ».
Toute édition manuelle d'un fichier généré est temporaire par construction.

## Ce que les six ont en commun

Aucun n'est un bug. Chacun fait exactement ce qui est écrit dans son code. Dans
les six cas l'écart est entre la portée réelle et la portée supposée, et il
est invisible tant que les deux coïncident par accident.

Quatre conséquences pratiques, toutes vérifiées à l'usage sur ce dépôt :

1. **Un contrôle qui échoue silencieusement est pire qu'un contrôle absent.**
   L'absence se voit. Un faux négatif qui laisse passer une réponse confiante
   ne se voit pas.
2. **Aucune méthode nouvelle n'est adoptée sans passer d'abord sur une
   quantité exactement connue.** L'étalon `28n² − 232n + 598` a attrapé le
   jackknife et a calibré la tolérance de densité. Sans lui, les deux
   auraient produit des chiffres crédibles.
3. **Un contrôle par déduction ne remplace pas un contrôle par exécution.**
   Améliorer le motif d'extraction des chemins de test ne pouvait pas trouver
   la famille de vingt graines ; exécuter depuis un clone l'a trouvée en trois
   itérations. Le motif cherchait ce qu'on savait déjà chercher.
4. **Une quantité mesurée exige un artefact ; une quantité dérivée exige sa
   formule ; un nombre qui n'a ni l'un ni l'autre n'est pas vérifiable, quelle
   que soit sa justesse.**
   La version naïve — « tout nombre doit venir d'un CSV » — produirait un
   artefact pour une table d'arithmétique : du théâtre de traçabilité, qui a
   l'apparence de la rigueur sans la substance. Une densité de code de surface
   se recalcule depuis sa formule en dix secondes ; la publier en CSV
   n'ajouterait rien qu'un fichier à croire.

   L'instance : le contrôle du jackknife était cité avec ses nombres —
   `d = 1,929`, intervalle `[1,927 ; 1,930]` — calculés dans un script jeté.
   Le chiffre n'était pas faux. Il était **sans provenance**, et sa plage a
   changé sous lui sans que rien ne le signale : le même contrôle sur
   `n = 9…40` rend `1,941` et `[1,939 ; 1,942]`. Les deux excluent la vérité,
   donc la conclusion tient — mais elle tenait par chance. Le contrôle est
   désormais émis avec l'analyse d'échelle.

   Cette règle est la plus transférable de la journée : elle ne dépend ni de
   ce projet ni de son domaine.

   Elle a mordu son propre texte en moins d'une minute. Le paragraphe sur le
   jackknife, deux écrans plus haut, citait ses nombres sans nommer la plage —
   exactement ce que la règle interdit. Corrigé. Gardé comme illustration :
   une règle qui ne trouve rien au moment où on l'écrit n'en est pas une.

## Où chacun est traité

| cas | correctif | garantie ajoutée |
|---|---|---|
| `.get()` → `None` | colonne absente lève ; verdict conditionné à l'appariement | `compare_density_cost.py` |
| jackknife | méthode rejetée, rejet écrit dans le code avec sa raison | `measure_gf2_scaling.py` |
| profondeur fixe | densité modélisée au lieu d'être neutralisée | `SPARSE_DENSE_COST_EXPERIMENT.md` |
| synchroniseur | portée divulguée dans la docstring, + exécution depuis un checkout | `sync_test_counts.py`, intégration continue |
| statut à travers un tube | `set -o pipefail` en CI ; ne plus lire `$?` derrière un tube | `.github/workflows/clean-clone.yml` |
| deux générateurs, un fichier | le fichier généré retiré de `DOCUMENTS`, avec la raison | `sync_test_counts.py` |

La divulgation et l'exécution depuis un checkout sont **deux contrôles
indépendants**, pas l'un le remplaçant de l'autre. Le second n'élargit pas ce
que le synchroniseur promet ; il ajoute une promesse distincte. Retirer la
divulgation parce que la CI existe reproduirait exactement le schéma décrit
ici.
