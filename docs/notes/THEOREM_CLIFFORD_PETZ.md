# Proposition Clifford pur–Petz — démonstration auditée

## Hypothèses

Soient `A` et `R` de dimension `d=2^m`, et `|Phi>_RA=d^-1/2 sum_a |a>_R|a>_A`. Un environnement `G` est dans un état stabilisateur pur `|g>`. Une isométrie Clifford sur `A⊗G`, suivie d’une partition `X⊗C`, définit une isométrie `V:A -> X⊗C` et le canal `N(rho)=Tr_C(V rho V†)`.

Le Petz transpose est construit à l’état de référence `sigma_A=I_A/d` :

`R_P(Y) = (1/d) N†(tau_X^-1/2 Y tau_X^-1/2)`, avec `tau_X=N(I_A/d)` et pseudo-inverse de Moore--Penrose sur `supp(tau_X)`.

Le complément est `N^c(rho)=Tr_X(V rho V†)`. On pose `omega_RC=(id_R⊗N^c)(|Phi><Phi|)` et `omega_C=N^c(I_A/d)`.

## Proposition

Sous ces hypothèses,

`F_e(R_P o N) = rank(omega_RC) / [d rank(omega_C)] = 2^(-I(R:C)_omega)`.

La première égalité ne requiert, au-delà d’une isométrie pure, que la platitude de `tau_X` et de `omega_C`. La seconde requiert aussi la platitude de `omega_RC` et `omega_R=I/d`. Une isométrie Clifford avec environnement stabilisateur pur satisfait ces platitudes, car toute réduction d’un état stabilisateur pur est un projecteur stabilisateur normalisé.

## Démonstration de la première égalité

Choisissons une base orthonormée `|c>` de C et écrivons l’isométrie

`V = sum_c K_c ⊗ |c>`,

où `K_c:A -> X` et `sum_c K_c† K_c=I_A`. Les Kraus de Petz sont

`L_c=(1/sqrt(d)) K_c† tau_X^-1/2`.

La fidélité d’intrication, avec la convention ci-dessus, est

`F_e=(1/d^2) sum_(c,c') |Tr(L_c K_c')|^2`

`=(1/d^3) sum_(c,c') |Tr(K_c† tau_X^-1/2 K_c')|^2`.  (1)

Posons `q_X=rank(tau_X)`. La platitude de `tau_X` donne `tau_X=P_X/q_X`; donc `tau_X^-1/2=sqrt(q_X)P_X`. Comme `P_X K_c=K_c` pour tout c (le support de `tau_X` contient les supports de tous les `K_c`), (1) devient

`F_e=(q_X/d^3) sum_(c,c') |Tr(K_c†K_c')|^2`.  (2)

Or

`omega_C=(1/d) sum_(c,c') Tr(K_c'†K_c)|c><c'|`.

En prenant sa pureté dans cette base,

`Tr(omega_C^2)=(1/d^2) sum_(c,c') |Tr(K_c†K_c')|^2`.  (3)

Les équations (2) et (3) donnent exactement

`F_e=(q_X/d) Tr(omega_C^2)`.  (4)

La platitude de `omega_C=P_C/q_C`, avec `q_C=rank(omega_C)`, donne `Tr(omega_C^2)=1/q_C`. Enfin, `|Omega>_RXC=(I_R⊗V)|Phi>` est pur : les réductions `omega_RC` et `tau_X` ont les mêmes spectres non nuls, donc `q_X=rank(omega_RC)`. En substituant dans (4),

`F_e=rank(omega_RC)/[d rank(omega_C)]`.

Chaque inverse est restreint au support indiqué ; aucune hypothèse de plein rang n’est utilisée.

## Corollaire stabilisateur

Pour une réduction stabilisatrice plate `rho_Y=P_Y/rank(rho_Y)`,

`S(rho_Y)=log2 rank(rho_Y)=|Y|-dim S_Y`.

Puisque `omega_R=I_R/d`,

`I(R:C)=log2(d)+log2 rank(omega_C)-log2 rank(omega_RC)`.

La formule de rang précédente donne donc, ligne par ligne,

`F_e=2^[log2 rank(omega_RC)-log2(d)-log2 rank(omega_C)]=2^-I(R:C)`.

L’entier stabilisateur est `r=dim S_RC-dim S_R-dim S_C`; ainsi `I=r` et `F_e=2^-r`.

## Portée exacte

Le résultat vaut pour toute isométrie Clifford avec environnement stabilisateur pur, toute dimension `d=2^m`, et toute partition `X|C` issue d’une trace partielle, donc tout ordre d’émission. Il ne dépend pas spécifiquement de Hayden–Preskill.

Il peut aussi valoir hors Clifford si les trois platitudes utilisées sont vérifiées, mais cela n’est pas une généralisation revendiquée ici. Il ne s’applique pas automatiquement aux environnements mixtes, références non maximales, mélanges non uniformes de canaux ou évolutions non-Clifford.

## Vérifications indépendantes

`exhaustive_clifford_b1.py` énumère les 11 520 Cliffords sur A+B pour B=1, pour deux partitions, soit 23 040 cas : `max |I-r|=2.00e-15` et `max |F-rank_formula|=2.67e-15`. La campagne 4B+4E fournit 750 vérifications supplémentaires. Ces calculs contrôlent les équations, ils ne remplacent pas la démonstration ci-dessus.
