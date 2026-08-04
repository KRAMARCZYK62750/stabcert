# Audit de l’assertion Rényi-2 / Petz

## Conventions

Soit `A` de dimension `d`, `N: L(A) -> L(X)` et une isométrie de Stinespring `V: A -> X⊗C`. Le canal complémentaire est `N^c(rho)=Tr_X(V rho V†)`. Avec `|Phi>_RA=d^-1/2 sum_i |i>_R|i>_A`, on pose `omega_RC=(id_R⊗N^c)(|Phi><Phi|)`.

La fidélité d’intrication est `F_e=<Phi|(id_R⊗R∘N)(|Phi><Phi|)|Phi>`.

Le Petz transpose à `sigma_A=I_A/d` est, sur `supp N(sigma_A)`,

`R_Petz(Y)=sigma_A^1/2 N†(N(sigma_A)^-1/2 Y N(sigma_A)^-1/2) sigma_A^1/2`,

avec pseudo-inverse de Moore--Penrose et extension nulle hors support.

La seule entropie appelée ici collision conditionnelle sandwiched est

`H2(R|C)_omega=-log2 Tr[(I_R⊗omega_C^-1/4) omega_RC (I_R⊗omega_C^-1/4)]^2`.

Elle n’est ni une optimisation sur les états de C, ni une autre entropie Rényi conditionnelle.

## Résultat de l’audit

L’égalité `F_e=2^(H2(R|C)-log2 d)` n’est **pas** une identité générale avec cette convention. Elle doit donc être retirée comme prémisse de démonstration. Le programme enregistre désormais sa différence numérique, sans la présenter comme une identité.

Contre-exemple : déphasage purifié `K0=sqrt(1-p) I`, `K1=sqrt(p) Z`. On obtient exactement

`I(R:C)=h2(p)` et `F_e(Petz∘N)=(1-p)^2+p^2`.

Pour `p=1/4`, `F_e=5/8=0.625`, tandis que le H2 ci-dessus donne

`Tr[...]^2=(1+2 sqrt(p(1-p)))/2`,

donc `2^(H2-1)=1/(1+2 sqrt(p(1-p)))≈0.5359`. Les deux côtés diffèrent. Aux points `p=0` et `p=1/2`, ils coïncident accidentellement.

En conséquence, le corollaire stabilisateur `F_e=2^-I` reste une observation à démontrer séparément ou à réfuter, et ne découle pas de l’identité Rényi-2 auditée ci-dessus.
