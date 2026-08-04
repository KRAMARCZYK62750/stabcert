# Audit local Clifford pur — état actuel

Pour chaque canal de la campagne 4B+4E, `stabilizer_diagnostics.csv` enregistre les rangs spectraux, spectres non nuls, dimensions de sous-groupes stabilisateurs et l’entier

`r = dim(S_RC) - dim(S_R) - dim(S_C)`.

`S_X` désigne les éléments du stabilisateur global dont le support est entièrement dans X. Pour un état stabilisateur pur, `S(rho_X)=|X|-dim(S_X)` ; par soustraction, `I(R:C)=r` exactement. Cette première égalité est donc démontrée pour les isométries Clifford avec environnement stabilisateur pur et référence maximale.

Sur les 750 canaux testés (3 régimes, 50 circuits, 5 temps), les écarts maximaux calculés sont `|I-r|=9.77e-15` et `|F_Petz-2^-r|=2.54e-14`.

Le second énoncé est présentement une caractérisation numérique de cette sous-classe, pas encore un théorème : il reste à démontrer par forme canonique bipartite des stabilisateurs ou à réfuter par un contre-exemple Clifford pur. Les environnements mixtes, références non maximales, mélanges non uniformes et messages à deux qubits ne sont pas couverts par ce fichier.
