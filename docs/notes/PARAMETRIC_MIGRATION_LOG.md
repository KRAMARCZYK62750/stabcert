# Journal de migration paramétrique

## Couche 1 — registres et canal

Migrés : `SystemLayout`, canal paramétrique, état d'environnement.

## Couche 2 — Choi et Petz

Migrés : `tau_X`, rang de support, Petz, fidélité et purification Choi dans
l'ordre `A'|Ref|E_Petz`, avec seuil de pseudo-inverse `1e-12` inchangé.
Les tests couvrent B=4 sans brouillage, faible et profond, aux temps 1,2,4,5.

Restent volontairement sur le chemin historique : extraction stabilisatrice,
synthèse, validation opératorielle, routage et rapports. Aucune instance B=5.

## Couche 3a — extraction stabilisatrice

Migrée : extraction canonique du support `tau_X` derrière `SystemLayout`, avec
assertions d'alignement binaire/signé. La synthèse symplectique, la validation
opératorielle et le routage restent à migrer séparément.

## Couche 3b — synthèse et validation opératorielle

Migrés : corrélations Choi signées en mémoire, tableau Clifford, synthèse avant
routage, fidélité Choi, fidélité d'intrication et validation sur la base
complète du support. Les trois régressions B=4 passent à `1e-12`; groupes Choi,
profondeur, CNOT et environnement coïncident exactement avec l'oracle ancien.
La couche synthèse paramétrique est validée. Le routage reste historique.

## Couche 4 — routage local

Migrés : chaîne physique, voisinage, insertion des SWAP, suivi de permutation,
restitution de l'ordre de sortie, CNOT et profondeur locale. La régression des
60 instances B=4 passe exactement sur les ressources discrètes et à `1e-12`
sur les métriques numériques. Le routage paramétrique est validé.
