# CLI et modèle de confiance du noyau Recovery v1

Statut : **implémenté et testé localement**.

## Périmètre scientifique exact

La v1 compile et certifie uniquement la classe suivante :

- isométrie source Clifford ;
- ancillas dans un état stabilisateur pur ;
- référence de Petz `sigma = I/d` ;
- pseudo-inverse exacte sur le support stabilisateur ;
- circuit de récupération Clifford déterministe ;
- graphe de couplage non dirigé et routeur v1 déterministe.

Elle ne prétend pas couvrir tout canal stabilisateur.

## Séparation des objets

`artifact.json` est scientifique, canonique et déterministe. Il contient les
supports, générateurs signés, circuits, ressources, permutations, certificats
et métriques scientifiques déterministes. Il ne contient plus :

- durée ;
- mémoire ;
- nom de machine ;
- OS ;
- versions Python, NumPy ou Stim ;
- logs d'exécution.

Ces données se trouvent exclusivement dans `run-report.json`, au format
`orelia.recovery-run-report/v2`. Deux compilations du même problème ont été
comparées octet par octet et produisent le même `artifact.json`.

## Commandes

```bash
orelia-recovery compile problem.json --output artifact.json \
  --run-report compile-run-report.json

orelia-recovery verify problem.json artifact.json \
  --run-report verify-run-report.json

orelia-recovery benchmark problem.json --iterations 2 \
  --output benchmark-run-report.json
```

Les réponses stables destinées aux programmes sont écrites en JSON canonique
sur `stdout`. Les rapports volatils ne sont écrits que dans le fichier demandé.

## Codes de sortie figés

| Code | Nom | Signification |
|---:|---|---|
| 0 | `SUCCESS` | commande réussie ou artefact certifié |
| 2 | `CLI_USAGE` | syntaxe de commande invalide |
| 10 | `INPUT_INVALID` | JSON ou modèle de données invalide |
| 11 | `UNSUPPORTED_VERSION` | version de format non supportée |
| 20 | `COMPILATION_FAILED` | construction de l'artefact impossible |
| 30 | `VERIFICATION_REJECTED` | artefact bien formé mais non certifié |
| 70 | `INTERNAL_ERROR` | erreur interne inattendue du vérificateur |

Le verdict déclaré dans l'artefact n'intervient jamais dans le verdict final.

## Paquet verifier-only

Le paquet local est :

`dist/orelia-recovery-verifier.pyz`

Il contient uniquement le modèle de données, la sérialisation, les primitives
GF(2)/stabilisatrices, le routeur requis pour contrôler les ressources et le
vérificateur. Il ne contient ni `recovery_compile.py`, ni adaptateur
Hayden–Preskill, ni module expérimental. Son manifeste signé par hashes SHA-256
est embarqué sous `VERIFIER_MANIFEST.json` et copié à côté du paquet.

Utilisation :

```bash
python orelia-recovery-verifier.pyz verify problem.json artifact.json
```

NumPy et Stim restent des dépendances externes et leurs versions sont inscrites
dans le manifeste et dans chaque RunReport.

## Test hermétique réalisé

Le paquet est exécuté depuis un répertoire temporaire propre, sans
`PYTHONPATH`, sans installation du projet et sans module de compilation dans
l'archive. Il vérifie la fixture A=1 avec le même verdict et le même hash
d'artefact. La commande `compile` est absente et renvoie le code d'usage `2`.

Ce test isole le paquet et le code source du projet, mais utilise encore le
même interpréteur et les mêmes installations externes NumPy/Stim. Une exécution
sur une machine physique indépendante ou dans une image reconstruite depuis
zéro reste un jalon de distribution ultérieur ; elle n'est pas simulée ici.

## Proposition de confiance

Le modèle visé devient :

```text
compilateur propriétaire
        +
schémas documentés
        +
vérificateur distribuable et auditable
```

Le présent jalon valide l'architecture logicielle de ce modèle. Il ne constitue
ni un audit de sécurité externe, ni une preuve formelle, ni une garantie de
performance ou de profondeur minimale.
