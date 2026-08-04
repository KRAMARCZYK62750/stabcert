# Compilateur stabilisateur paramétrique — spécification de migration

## Registres

Une instance est décrite par `InstanceSpec(n_b, t, seed, scrambler_layers)` :

```text
R = 0
A = 1
B = 2 .. 1+n_b
E = 2+n_b .. 1+2*n_b
D = (A, *B)
X(t) = E + D[:t]
C(t) = D[t:]
chaîne locale = E0--...--E(n_b-1)--D0--...--D(t-1)
```

Toutes les dimensions doivent être dérivées de cette spécification : entrée
`dim(A)=2`, `dim(X)=2^(n_b+t)`, `dim(C)=2^(n_b+1-t)` avant fixation de R, rang
du support, qubits logiques, rang Kraus/environnement Petz et tailles des
tableaux entrée/sortie.

## Invariants de compilation

La synthèse est interdite si l'une des conditions suivantes échoue :

1. les stabilisateurs signés et binaires sont alignés générateur par générateur ;
2. le tableau d'entrée est symplectique complet ;
3. le Choi Petz est stabilisateur ;
4. les images logiques signées ont la même forme symplectique ;
5. le code de sortie inclut ses stabilisateurs/déstabilisateurs lorsque son
   nombre de fils dépasse le nombre de qubits logiques d'entrée.

Le critère final est toujours l'égalité de canal avec Petz sur une base complète
du support, même si sa fidélité d'intrication est inférieure à 1.
