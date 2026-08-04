# Un mécanisme garantit exactement ce qu'il dit

**Date :** 4 août 2026.

Le danger ne vient pas des mécanismes qui échouent. Il vient de ce qu'on leur
prête en plus de ce qu'ils promettent. Quatre instances du même schéma sont
apparues en une seule journée de travail sur ce dépôt, dans quatre domaines
sans rapport entre eux. Elles sont consignées ici parce que le schéma est plus
utile que chacun des cas.

## Les quatre

**Le `.get()` qui rendait `None`.** `compare_density_cost.py` contrôlait que
les deux bras partageaient le même rang de support. Les CSV du bras dense
étaient antérieurs à l'instrumentation : la colonne n'existait pas, `.get()`
rendait `None`, comparé à un entier — divergence à toutes les largeurs. Le
contrôle n'a pas eu lieu, et le script a **quand même émis un verdict**. Ce
qu'on lui prêtait : « il vérifie l'appariement ». Ce qu'il faisait : « il
compare deux valeurs, quelles qu'elles soient ».

**Le jackknife.** Ajuster `e(n) = d + K/n` pour extrapoler le degré
asymptotique donnait, sur l'étalon dont le degré vaut exactement 2, une valeur
de 1,929 avec un intervalle de [1,927 ; 1,930] — la vérité exclue, l'intervalle
trente fois trop serré. Ce qu'on lui prêtait : « il mesure l'incertitude sur
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

## Ce que les quatre ont en commun

Aucun n'est un bug. Chacun fait exactement ce qui est écrit dans son code. Dans
les quatre cas l'écart est entre la portée réelle et la portée supposée, et il
est invisible tant que les deux coïncident par accident.

Trois conséquences pratiques, toutes vérifiées à l'usage sur ce dépôt :

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

## Où chacun est traité

| cas | correctif | garantie ajoutée |
|---|---|---|
| `.get()` → `None` | colonne absente lève ; verdict conditionné à l'appariement | `compare_density_cost.py` |
| jackknife | méthode rejetée, rejet écrit dans le code avec sa raison | `measure_gf2_scaling.py` |
| profondeur fixe | densité modélisée au lieu d'être neutralisée | `SPARSE_DENSE_COST_EXPERIMENT.md` |
| synchroniseur | portée divulguée dans la docstring, + exécution depuis un checkout | `sync_test_counts.py`, intégration continue |

La divulgation et l'exécution depuis un checkout sont **deux contrôles
indépendants**, pas l'un le remplaçant de l'autre. Le second n'élargit pas ce
que le synchroniseur promet ; il ajoute une promesse distincte. Retirer la
divulgation parce que la CI existe reproduirait exactement le schéma décrit
ici.
