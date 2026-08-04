# ORELIA — spécification du mode `channel-certified`

## Statut

Spécification validée et implémentée le 3 août 2026. La qualification est
documentée dans `CHANNEL_CERTIFIED_IMPLEMENTATION.md`.

`RecoveryProblem v1`, `RecoveryArtifact v1`, leurs hashes et les résultats
scientifiques existants restent inchangés.

## Objectif

Permettre à ORELIA de certifier un circuit routé produit par un outil externe sans exiger qu'il soit textuellement identique au résultat du routeur ORELIA.

Le mode doit répondre à la question :

> Le circuit candidat réalise-t-il exactement, dans la sous-classe stabilisatrice v1, le canal de récupération dérivé de `RecoveryProblem`, tout en respectant la topologie et l'ordre de sortie déclarés ?

## Non-objectifs immédiats

- optimiser le circuit externe ;
- démontrer la minimalité de sa profondeur ;
- certifier un circuit non-Clifford ;
- modéliser le bruit matériel ;
- appeler SABRE ou pytket pendant la première implémentation ;
- modifier les algorithmes de construction de Petz ;
- reconstruire un SWAP à partir d'une séquence arbitraire de CNOT sans preuve de routage.

## Deux politiques de vérification

### `reproducible-route`

Politique historique.

Elle vérifie :

- le canal Petz cible ;
- l'action Clifford signée ;
- la topologie ;
- la permutation finale ;
- les ressources ;
- et l'égalité exacte avec le routage déterministe produit par les paramètres ORELIA déclarés.

Une route différente mais correcte est rejetée par cette politique.

### `channel-certified`

Nouvelle politique.

Elle ne reconstruit pas le circuit attendu avec le routeur ORELIA. Elle évalue directement le circuit candidat non fiable.

Elle doit accepter des circuits textuellement différents lorsqu'ils réalisent le même canal réduit et satisfont les contraintes matérielles déclarées.

## Position du choix de politique

La politique de vérification ne définit pas le problème scientifique. Elle ne doit donc pas modifier le hash sémantique de `RecoveryProblem`.

Le choix est un paramètre explicite de l'invocation du vérificateur et doit être enregistré dans `RecoveryRunReport` :

```text
verification_policy = reproducible-route | channel-certified
```

Le rapport doit toujours indiquer la politique réellement appliquée.

## Modèle de confiance

Le vérificateur ne fait confiance à aucun des éléments suivants :

- verdict déclaré par le compilateur ;
- cible Petz contenue dans l'artefact ;
- circuit logique ;
- circuit routé ;
- phases ;
- compteurs de ressources ;
- trace de routage ;
- permutation finale ;
- identité ou version du routeur externe.

Il reconstruit la cible depuis `RecoveryProblem` et recalcule tout ce qui peut l'être depuis les données structurelles.

## Contrôles obligatoires du mode `channel-certified`

### 1. Provenance

- hash sémantique du problème ;
- hash documentaire du problème ;
- versions de formats ;
- dimensions et ordres de fils.

### 2. Cible mathématique

- reconstruction indépendante du Choi Petz ;
- support exact de `tau_X` ;
- convention `A' | Ref | E_Petz` ;
- transposition `Pᵀ` sur la référence ;
- phases signées, dont `Yᵀ = −Y`.

### 3. Canal candidat

- reconstruction de l'action du circuit candidat ;
- réduction après élimination de l'environnement ;
- égalité canonique des sous-groupes stabilisateurs signés des Choi réduits ;
- action correcte sur les Pauli logiques ;
- indépendance par rapport à la jauge de Stinespring.

### 4. Contraintes matérielles

- chaque porte à deux qubits utilise une arête autorisée ;
- chaque porte appartient à la base autorisée ou possède une décomposition normative ;
- aucune porte ne référence un fil inconnu ;
- l'ordre initial est explicite ;
- l'ordre final ou la permutation finale est explicite et vérifié.

### 5. Ressources directement recalculables

- nombre de portes à un qubit ;
- nombre de portes à deux qubits ;
- nombre de CNOT physiques ;
- profondeur totale selon la convention déclarée ;
- profondeur en couches à deux qubits ;
- diamètre maximal des interactions utilisées ;
- conformité au graphe.

## Problème particulier des SWAP

Dans `RecoveryArtifact v1`, un SWAP est décomposé en trois CNOT. À partir du seul circuit CNOT final, il est généralement impossible de déterminer de façon unique si ces portes représentent :

- un déplacement de routage ;
- une opération logique ;
- une simplification produite par le compilateur ;
- ou une autre séquence Clifford équivalente.

Le mode `channel-certified` ne doit donc jamais annoncer un nombre de SWAP certifié en l'absence d'une preuve de routage explicite.

## Niveaux de certification des ressources

### Niveau A — canal et topologie

Disponible pour tout circuit candidat :

- canal réduit certifié ;
- action logique certifiée ;
- topologie certifiée ;
- CNOT et profondeur physique recalculés ;
- SWAP : `not_certified`.

### Niveau B — trace de routage explicite

Disponible lorsque le candidat fournit une trace rejouable :

- tous les contrôles du niveau A ;
- déplacements SWAP rejoués ;
- permutation suivie après chaque déplacement ;
- SWAP de mouvement et de restitution recomptés ;
- égalité entre la trace développée et le circuit physique vérifiée.

Le verdict de canal et le verdict de ressources doivent rester séparés.

## Future structure de preuve de routage

Cette structure n'est pas encore ajoutée aux schémas. Une future version pourrait contenir :

```text
RoutingEvidence
    format_version
    logical_wire_order
    physical_site_order
    initial_logical_to_physical_map
    operations[]
        operation
        physical_sites
        role = logical | movement | restoration
    final_logical_to_physical_map
    swap_expansion_convention
```

Le vérificateur devra :

1. rejouer chaque opération ;
2. vérifier chaque arête ;
3. suivre la permutation ;
4. développer les SWAP selon la convention ;
5. comparer le circuit développé au circuit candidat ;
6. recalculer toutes les ressources.

Une simple déclaration de nombres de SWAP ne constitue jamais une preuve.

## Gestion de la permutation finale

### Première implémentation

La première version de `channel-certified` exigera la restitution explicite de l'ordre logique final. Cette restriction permet de comparer directement le canal sans ambiguïté de relabellisation.

### Extension ultérieure

Une route non restaurée pourra être acceptée seulement si :

- la permutation finale est fournie ;
- elle est dérivée d'une trace rejouable ;
- les sorties demandées sont relabellisées avant la comparaison Choi ;
- la permutation déclarée et la permutation reconstruite coïncident exactement.

## Interface CLI proposée

Sans modifier immédiatement les fichiers v1 :

```text
orelia-recovery verify \
    problem.json \
    artifact.json \
    --policy reproducible-route
```

```text
orelia-recovery verify \
    problem.json \
    candidate-artifact.json \
    --policy channel-certified
```

Le JSON de sortie doit distinguer :

```text
channel_verified
topology_verified
logical_action_verified
final_order_verified
resource_counts_verified
swap_accounting_status
overall_verdict
```

Un champ `overall_verdict = valid` n'est autorisé que si tous les contrôles obligatoires pour le niveau demandé passent.

## Compatibilité avec les formats v1

### Garantie

Tous les artefacts v1 historiques doivent continuer à produire exactement le même verdict en politique `reproducible-route`.

### Transition

La première implémentation peut lire `RecoveryArtifact v1` en mode `channel-certified`, avec les restrictions suivantes :

- ordre final restauré obligatoire ;
- CNOT et profondeur recalculés ;
- compteurs SWAP explicitement classés `not_certified` ;
- aucune modification du fichier ou de son hash.

Une future version de schéma ne sera créée qu'après validation de cette première étape.

## Tests fonctionnels minimaux

### Cas 1 — route historique

- Petz correct ;
- route ORELIA historique ;
- accepté par `reproducible-route` ;
- accepté par `channel-certified`.

### Cas 2 — route différente mais canal identique

- circuit textuellement différent ;
- action Clifford identique ;
- topologie respectée ;
- ordre final restauré ;
- refusé par `reproducible-route` ;
- accepté par `channel-certified`.

### Cas 3 — jauge environnementale différente

- Clifford supplémentaire sur l'environnement rejeté ;
- canal réduit identique ;
- accepté par `channel-certified`.

### Cas 4 — route topologiquement valide mais canal faux

- toutes les portes utilisent des arêtes autorisées ;
- ressources cohérentes ;
- Choi réduit différent ;
- rejeté par les deux politiques.

### Cas 5 — canal correct mais arête interdite

- action totale identique grâce à une séquence qui s'annule ;
- au moins un CNOT hors graphe ;
- rejeté par `channel-certified`.

### Cas 6 — ressource falsifiée

- canal correct ;
- compteur CNOT ou profondeur faux ;
- canal accepté ;
- certificat de ressources rejeté ;
- verdict global conforme au niveau demandé.

### Cas 7 — permutation finale incorrecte

- canal apparent correct avant interprétation des fils ;
- ordre de sortie faux ;
- rejeté.

## Régression obligatoire

- fixtures `A=1`, `A=8`, `A=12` ;
- tous les tests v1 existants ;
- mêmes hashes scientifiques ;
- même comportement par défaut : `reproducible-route` ;
- aucun changement silencieux du verdict historique.

## Campagne adversariale dédiée

Après l'implémentation, produire un corpus séparé couvrant :

- circuit alternatif valide ;
- identité insérée ;
- jauge environnementale ;
- CNOT hors graphe ;
- permutation incorrecte ;
- ressource falsifiée ;
- trace SWAP incohérente ;
- trace et circuit développés différents ;
- Choi candidat faux mais certificat interne cohérent ;
- changement de phase Pauli ;
- mélange de plusieurs mutations ;
- champs inconnus et formats non supportés.

Chaque mutation doit être reliée au premier contrôle attendu. Les faux acceptés et faux rejetés doivent être enregistrés séparément.

## Ordre d'implémentation

1. Ajouter une abstraction interne `VerificationPolicy` sans changer les schémas.
2. Extraire les contrôles communs aux deux politiques.
3. Conserver le contrôle de routage déterministe uniquement dans `reproducible-route`.
4. Recalculer les ressources directement observables dans `channel-certified`.
5. Introduire des verdicts séparés canal/topologie/ressources.
6. Construire manuellement une première route alternative indépendante.
7. Exécuter les tests minimaux et les régressions v1.
8. Lancer la campagne adversariale dédiée.
9. Ajouter ensuite seulement l'adaptateur SABRE.
10. Ajouter pytket après validation de SABRE.

## Critères de passage vers SABRE

L'adaptateur SABRE n'est autorisé que si :

- les deux politiques sont explicitement sélectionnables ;
- toutes les fixtures historiques passent ;
- une route alternative manuelle correcte est acceptée ;
- un canal faux mais topologiquement correct est rejeté ;
- le statut des SWAP non certifiables est honnêtement signalé ;
- la campagne adversariale ne révèle aucun contournement non résolu.

## Livrable destiné à une évaluation extérieure

Après validation technique :

- cette spécification ;
- un `RecoveryProblem` ;
- trois artefacts routés différemment ;
- un artefact faux mais plausible ;
- le verifier-only ;
- le rapport adversarial ;
- une question centrale :

> Les critères d'égalité de canal, de jauge environnementale et de conformité topologique sont-ils suffisants et correctement séparés ?

## Conclusion

Le mode `channel-certified` transforme ORELIA d'un pipeline auto-cohérent en un vérificateur susceptible d'évaluer le résultat d'autres compilateurs.

La première réussite attendue n'est pas une meilleure profondeur. Elle est la suivante :

> Une route externe correcte est acceptée sans être identique à la route ORELIA, tandis qu'une route plausible mais réalisant le mauvais canal est rejetée.
