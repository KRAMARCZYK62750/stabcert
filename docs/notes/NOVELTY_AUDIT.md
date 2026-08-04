# Audit de nouveauté et vérification indépendante

## Résultat local audité

Pour `N:A->X`, `d=dim A`, `tau_X=N(I/d)`, et une dilatation pure vers `X⊗C`, la normalisation employée est : Choi normalisé `J_N=(id_R⊗N)(Phi_RA)`, avec `Phi_RA` de trace un et `F_e=<Phi|(id_R⊗R_P o N)(Phi)|Phi>`.

La seconde dérivation, indépendante des Kraus, part de

`R_P=(1/d)N† o Gamma_tau`, avec `Gamma_tau(Y)=tau^-1/2 Y tau^-1/2` sur `supp(tau)`.

Par l’adjonction de Choi,

`F_e=(1/d) Tr[J_N (id_R⊗Gamma_tau)(J_N)]`.

Si `tau=P_X/q_X`, alors `Gamma_tau(J_N)=q_X J_N`, car `J_N` est supporté dans `R⊗supp(tau)`. Ainsi

`F_e=(q_X/d)Tr(J_N^2)`.

La purification de Stinespring donne `Tr(J_N^2)=Tr(omega_C^2)` et les mêmes spectres non nuls pour `J_N=omega_RX` et `omega_RC`; ceci reproduit exactement la dérivation Kraus. Aucun facteur supplémentaire de d n’apparaît : le seul facteur vient des deux `sigma_A^1/2=I/sqrt(d)` du Petz.

Pour les réductions stabilisatrices plates, `q_X=rank(omega_RC)` et `Tr(omega_C^2)=1/rank(omega_C)`, donnant la formule de rang du document `THEOREM_CLIFFORD_PETZ.md`.

## Contrôles de normalisation

Les trois blocs atomiques sont vérifiés en rationnels exacts : identité `1`, déphasage Pauli uniforme `1/2`, reset/EPR complémentaire `1/4`. Les 10 tests automatiques vérifient aussi les conventions de Bell, d’inverse sur support, de complétude de Kraus, le contre-exemple non uniforme, et la formule de rang stabilisatrice.

## Littérature la plus proche

| Référence | Énoncé publié pertinent | Rapport avec notre formule | Statut |
|---|---|---|---|
| [Burri, *Entanglement fidelity of Petz decoder for one-shot entanglement transmission* (2025)](https://arxiv.org/abs/2502.17411) | Théorème 4 donne une expression fermée de la fidélité d’intrication du décodeur Petz; le corollaire 5 l’exprime par une information de Rényi Petz minimisée associée au canal complémentaire. | Notre identité Choi/Kraus est une spécialisation à `rho_A=I/d`; la formule de rang suit quand les états pertinents sont plats. | Corollaire/spécialisation d’un résultat plus général; pas de revendication de nouveauté. |
| [Yoshida, *Recovery algorithms for Clifford Hayden–Preskill problem* (2021)](https://arxiv.org/abs/2106.15628) | Donne des conditions nécessaires et suffisantes de récupérabilité Clifford, et des décodeurs déterministes à mesures de Bell/feedback, analysés par croissance d’opérateurs. | Même contexte Hayden–Preskill Clifford, mais décodeur et invariants différents; l’article ne fournit pas, dans les éléments vérifiés, notre formule Petz par rangs. | Contexte et résultats proches, pas une priorité établie pour la formulation exacte par rangs. |
| [Hu & Zou, *Petz map recovery for long-range entangled quantum many-body states* (2024)](https://doi.org/10.1103/PhysRevB.110.195107) | Étudie le Petz tourné après effacement et la dépendance de son infidélité à l’information mutuelle conditionnelle dans des états many-body. | Porte sur des lois de comportement et des phases physiques, non sur le calcul exact de la fidélité d’un canal stabilisateur plat. | Non équivalent; fournit un contexte de récupération Petz, pas une nouveauté pour notre résultat. |
| [Beigi, Datta & Leditzky, *Decoding quantum information via the Petz recovery map* (2016)](https://arxiv.org/abs/1504.04449) | Utilise le transpose/Petz comme décodeur pour obtenir des bornes de transmission one-shot. | Confirme la convention du transpose channel; ne suffit pas à elle seule à établir la formule de rang spécifique. | Antériorité générale de la méthode, pas de revendication nouvelle. |

## Correspondance de notations

Notre `X` est la sortie du canal, `C` son environnement complémentaire, `tau_X=N(I/d)`, et `omega_C=N^c(I/d)`. Le `J_N` normalisé est l’état `omega_RX` dans une purification `R-X-C`. La « platitude » signifie `rho=P/rank(rho)` sur son support.

## Statut honnête

Le résultat est **une spécialisation stabilisatrice et une preuve élémentaire indépendante** d’une expression fermée de fidélité Petz déjà étudiée dans la littérature one-shot. Le passage à un rapport de rangs est un corollaire direct de la platitude des réductions stabilisatrices. Aucune nouveauté publiable n’est revendiquée sans lecture intégrale et comparaison équation-par-équation avec la formule de Burri et la littérature sur les codes stabilisateurs/transpose channel.
