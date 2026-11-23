# StabCert: translation validation for stabilizer channels

> **Assembly note.** Every figure in sections 6 and 7 is regenerated from the
> published artifacts named in the traceability table of
> `docs/notes/REVIEW_PASSES.md`, never copied from an earlier message. Review
> pass 1 has run; its mechanical checks are automated in
> `check_paper_consistency.py`. Pass 2 — recomputing each figure from its
> artifact — has not.

---

## Abstract

Quantum routing compilers rewrite circuits to satisfy hardware connectivity
constraints, but the resulting circuits are seldom verified against the channel
they are meant to implement. We present a decision procedure for the equality
of stabilizer channels — Clifford unitaries with stabilizer ancilla preparation
and partial trace — restricted to a specified input subspace.

Our procedure compares the canonical signed signatures of code-Choi states,
relative to a support determined by the specification, and is both sound and
complete: two such channels agree on the code subspace if and only if their
signatures coincide. It runs in polynomial time, avoids dense matrix
representations and basis state enumeration, and its verdict is invariant under
any change of Stinespring dilation.

We implement this in StabCert, a tool that treats the compiler as an untrusted
black box and certifies routed circuits produced by Qiskit SABRE and pytket
against targets reconstructed from a specification rather than from a reference
circuit. On the families studied, our measurements identify generator density —
not circuit width alone — as a key factor in verification cost.

---

## 1. Introduction

Quantum programs written for hardware must be routed: a compiler inserts SWAP
gates and relabels qubits so that every two-qubit operation acts on an edge of
the device coupling map. This transformation is substantial, and it is
performed by heuristic search procedures that are not themselves verified.
Qiskit's SABRE and pytket's routing passes are widely deployed and largely
trusted on the strength of testing.

Existing verification approaches address adjacent problems.

Compiler certification — proving the transformation itself, once and for all —
requires a proof about the compiler's code, kept up as that code changes. The
approach taken here needs none: an artifact is verified without inspecting
the compiler that produced it.

Equivalence checking, as implemented for example in QCEC
\cite{burgholzer2021advanced}, compares a compiled circuit against a reference
circuit. Like our approach it relies on canonical
representations; the distinction is not canonicity but the object represented
and the input required. Section 8 states it precisely, together with the
capabilities and limits of the engines involved.

Deductive verification proves properties of programs written in a dedicated
language, reaching algorithms as complex as Shor's order finding, but takes its
input as a program rather than as an artifact produced elsewhere.

None of these answers the question a routing pass raises in practice: given a
circuit produced by an untrusted compiler, does it implement the channel the
specification calls for? The distinction matters because the reference circuit
is itself an artifact. Comparing against it certifies faithfulness to a
possibly wrong starting point.

One line of work is closer than these three. Kliuchnikov, Beverland and
Paetznick \cite{kliuchnikov2023stabilizer} verify stabilizer circuits
containing measurements and outcome-conditioned Pauli corrections,
exhaustively over outcomes, and compute the logical action of a circuit
between two stabilizer codes. They compare quantum instruments, outcome
records included, where we compare one reduced channel on a code subspace, and
their normal form is not unique. Section 8 states both points, and states also
where the two works do not differ.

**Contribution.** We restrict attention to stabilizer channels, as defined in
Section 2, and show that within this class the question is decidable in
polynomial time. Specifically:

- We define the code-Choi state, a possibly mixed stabilizer state — a state stabilized
  by a signed subgroup — encoding a channel's action on a specified input
  subspace, and prove that equality of its canonical signed signature is
  necessary and sufficient for equality of the channels on that subspace
  (Section 3).
- We show the verdict is invariant under any change of Stinespring dilation, so
  that circuits differing only in ancilla convention are correctly accepted
  (Section 3.4).
- We name the target a specification determines — its Petz recovery map — and
  prove that the recipe by which the verifier builds the target yields the
  signature of that map (Section 3.5).
- We implement the procedure in StabCert and certify routed circuits produced
  by SABRE and pytket, with adversarial campaigns reporting no false accepts
  and no false rejects (Sections 5–6).
- We measure verification cost and separate the contribution of circuit width
  from that of generator density (Section 7).

The property is proved of the decision procedure; the adversarial campaigns of
Section 6 test the implementation that realises it, and no finite corpus could
establish the former.

**Scope.** The class is narrow by design. Gottesman–Knill makes stabilizer
circuits classically simulable, which is what permits an exact decision
procedure; it also means our results say nothing about non-Clifford gates,
noise, or timing. Section 4 states the boundary precisely.

---

## 2. Preliminaries

We assume familiarity with the stabilizer formalism and fix notation.

An `n`-qubit **stabilizer group** is an abelian subgroup of the Pauli group not
containing `−I`. It is represented by a **tableau**: for each generator, a
binary vector `(x|z) ∈ F₂^{2n}` together with a sign. Group operations
correspond to `F₂` row operations on the binary parts, with signs carried
along. The word *tableau* is reserved for this representation throughout.

A **Clifford unitary** maps Pauli operators to Pauli operators under
conjugation, and is fully specified by the images of `2n` generators. A
**stabilizer channel** is a Clifford unitary composed with stabilizer ancilla
preparation and partial trace over a discarded register. This is the class
studied by Yashin and Elovenkova \cite{yashin2025characterization} under the
name of non-adaptive Clifford channels, which they show to be the channels
whose Choi state is a possibly mixed stabilizer state.

By the **Gottesman–Knill theorem** \cite{gottesman1997,aaronson2004improved},
stabilizer circuits admit efficient
classical simulation: a tableau of `2n` signed generators determines the state,
and each gate updates it in polynomial time. This is what makes the decision
procedure of Section 3 possible, and it also bounds it — everything below is
confined to the stabilizer fragment.

### Registers and symbols

| symbol | object |
|---|---|
| `R` | purifying reference for the message, `|M|` wires |
| `M` | message, channel input |
| `X` | accessible partition, channel output |
| `C` | inaccessible complement, traced |
| `O ⊆ X` | requested output, with `|O| = |M|` |
| `Λ`, `Λ′` | stabilizer channels under comparison |
| `N`, `N^c` | the channel from `M` to `X`, and its complement to `C` |
| `S` | stabilizer group of the source Choi state |
| `S_X` | subgroup of `S` surviving the partial trace onto `X` |
| `τ_X` | marginal `N(I/d)` on `X`, with `d = 2^{|M|}` |
| `Π` | projector onto `supp(τ_X)` |
| `k` | logical qubits, `k = |X| − |S_X|` |
| `E` | support encoder (Definition 1) |
| `Ref(X)` | reference register of the code subspace, `|X|` wires |
| `sig(·)` | canonical signed signature (Definition 3) |

`R` and `Ref(X)` are distinct registers of different widths and are never
interchanged.

---

## 3. Deciding equality of stabilizer channels

### 3.1 Setting

Fix a channel specification `P`, consisting of an input register `M`, a set of
ancilla qubits with initial stabilizers, a source Clifford `U`, and an
accessible partition `X`.

Let `S` be the stabilizer group generated by the specification's input
generators conjugated by `U`, and let

```latex
S_X = \{S\rvert_X : S \in \mathcal{S},\ \operatorname{supp}(S) \subseteq X\}.
```

be the subgroup surviving the partial trace onto `X`. Write
`Π = ∏ᵢ (I + Sᵢ)/2` for the projector onto the joint `+1` eigenspace of `S_X`,
and `k = |X| − |S_X|` for the number of logical qubits. The target subspace is
`supp(τ_X)` with `τ_X = Π / 2^k`.

**Hypothesis 1 (specification-determined support).** `Π` is a function of `P`
alone. No part of the candidate artifact contributes to its construction.

This is what the verdict below is relative to, and it is the hypothesis on
which the theorem's usefulness rests: a candidate may claim a support, but that
claim is compared against `Π`, never used to build it. `Π` is never
materialised; it is represented throughout by its signed generators.

### 3.2 The code-Choi state

**Definition 1 (support encoder).** Let `X̄ᵢ, Z̄ᵢ` (`i < k`) be canonical
logical representatives of the code defined by `S_X`, and `Dⱼ, Sⱼ` its
destabilizer–stabilizer pairs. The support encoder `E` is the Clifford on
`|X|` qubits determined by

```
E Xᵢ E† = X̄ᵢ ,      E Zᵢ E† = Z̄ᵢ        (i < k)
E X_{k+j} E† = Dⱼ ,  E Z_{k+j} E† = Sⱼ    (j ≥ 0)
```

Both families of labels are obtained by canonical `F₂` elimination, so `E` is
determined by `P` and involves no gauge choice. `E` maps
`|ψ⟩_k ⊗ |0⟩^{|X|−k}` into the code space, and carries the signs on the
stabilizer tail.

The problem format requires `O ⊆ X` with `|O| = |M|`, enforced at problem
construction; this is the condition under which the two sides of the comparison
below are of the same type.

**Definition 2 (code-Choi state).** Let `Ref(X)` be a reference register of
`|X|` qubits. Prepare `k` Bell pairs between `Ref(X)` and the first `k` wires
of `X`, with the remaining `|X| − k` wires of each half in `|0⟩`. Apply the
**complex conjugate** `Ē` to `Ref(X)` and the support encoder `E` to `X`. Pass
`X` through the candidate channel `Λ`. The code-Choi state `J_Π(Λ)` is the
result reduced onto `O ∪ Ref(X)`.

The conjugation on the reference is not a convention of convenience. It is the
same fact as the transpose appearing in the inversion of Theorem 1, seen from
the other side: `Ē` on `Ref(X)` is what makes the inversion formula of that
proof return `Λ̃(σ)` rather than `Λ̃(σ^T)`. Stating either without the other
leaves the definition and the proof inconsistent with each other.

Three remarks, each of which a reader will otherwise have to reconstruct.

*The reduction registers differ on the two sides.* The target is reduced onto
`R ∪ X`; the candidate onto `O ∪ Ref(X)`. They are comparable because
`|O| = |M|`, which Definition 1 requires. Section 3.5 defines the target and
proves that this comparison is the right one.

*Three distinct partial traces occur in the chain, and they must not be
conflated.* `R` and `C` are traced to form `τ_X`; `C` is traced to form the
reduced target; `X ∖ O` is traced to form the reduced candidate. Only the last
belongs to Definition 2.

*The state is in general mixed, on `|O| + |X|` wires.* Tracing `X ∖ O`
generally leaves fewer independent generators than wires. It is pure in
special cases: for the identity channel on one qubit, with `O = X` and the
whole space as code, it is a Bell state. What the construction avoids is a
product of projectors — it returns
an independent generating set directly, so no normalisation scalar propagates
through the canonical form.

The full reference register is kept, not truncated to `k` wires, because the
encoder mixes the `|X| − k` padding wires into the code. After encoding no
factor is separable, and no subset can be discarded.

### 3.3 Canonical form and the decision procedure

**Definition 3 (canonical signed signature).** For a set of independent signed
Pauli generators, put the binary vectors `(x|z)` in reduced row echelon form,
performing each row operation simultaneously on the binary vector and on the
corresponding Pauli string, so that phases follow the elimination rather than
being recomputed. The canonical signed signature `sig(·)` is the resulting
ordered tuple of signed generators.

**Lemma 1.** *Let the generators be independent and generate a group not
containing `−I`. Then the canonical signed signature is a normal form: two such
sets generate the same signed subgroup if and only if their signatures are
equal.*

*Proof.* RREF over `F₂` is unique for a given row space, so the binary parts
agree exactly when the subgroups agree as unsigned groups. Because each row
operation is applied to the Pauli strings in parallel, the phase attached to
each echelon generator is the phase of the unique group element with that
binary support — unique precisely because `−I ∉ S`, without which the group
would contain both `P` and `−P` for the same support. Hence equality of
signatures is equivalent to equality of the signed subgroups. ∎

The reduction is not ours. Signed row operations on the tableau of a channel,
and its reduction to echelon form, are described by Yashin
\cite{yashin2025streamlined}. The lemma records what that reduction yields
when the group is fixed: a canonical object, which Theorem 1 then compares.

The hypothesis `−I ∉ S` is not incidental: the implementation rejects any
specification whose generators fail it, together with commutation and
independence, before any comparison is attempted.

**Theorem 1 (soundness and completeness).** *Let `Λ`, `Λ′` be stabilizer
channels and `Π` as above. Then*

```latex
\operatorname{sig}(J_{\Pi}(\Lambda))
= \operatorname{sig}(J_{\Pi}(\Lambda'))
\iff
\Lambda(\rho)=\Lambda'(\rho)
\quad \forall \rho\ \text{such that}\
\operatorname{supp}(\rho)\subseteq\operatorname{supp}(\tau_X)
```

*Proof.* (⇐) Suppose the channels agree on the code subspace. The states `ρ`
supported in `supp(Π)` span the operator space on that subspace, so by
linearity the two channels agree on all of it, hence on the joint state of
Definition 2. The code-Choi states coincide, and by Lemma 1 their signatures
are equal.

(⇒) Equal signatures give equal signed stabilizer groups, hence
`J_Π(Λ) = J_Π(Λ′)` as states. Three steps then recover the channels.

First, `E` restricts to a unitary isomorphism between `ℂ^{2^k} ⊗ |0⟩^{|X|−k}`
and the code subspace. By Definition 1, `E` maps the stabilizer group of
`|0⟩^{|X|−k}` on the last `|X| − k` wires onto `S_X`, so it carries that
subspace onto the joint `+1` eigenspace of `S_X`, which is `supp(Π)`; being
Clifford it is unitary, hence a bijection between the two. Every `ρ` with
`supp(ρ) ⊆ supp(τ_X)` is therefore `E(σ ⊗ |0⟩⟨0|)E†` for a unique `σ` on `k`
qubits. Write `V` for the isometry `|ψ⟩ ↦ E(|ψ⟩ ⊗ |0⟩^{|X|−k})` from `k`
qubits into `X`, so that this `ρ` is `VσV†`.

Second, `J_Π(Λ)` is the ordinary Choi state of the induced logical channel
`Λ̃ : σ ↦ Λ(E(σ ⊗ |0⟩⟨0|)E†)`. The prepared state of Definition 2 is
`(Ē ⊗ E)(Φ_k ⊗ |0⟩⟨0|)(Ē ⊗ E)†`, whose reduction on `X` is `Π/2^k` and whose
correlations with `Ref(X)` are those of `Φ_k` transported by `Ē ⊗ E`. Applying
`Λ` to `X` and reducing onto `O ∪ Ref(X)` therefore yields `(id ⊗ Λ̃)(Φ_k)` up
to the relabelling `Ē` performs on the reference — which is precisely the
transpose carried in the inversion below.

Third, Choi–Jamiołkowski \cite{choi1975completely,jamiolkowski1972linear}
inverts explicitly:

```latex
\widetilde{\Lambda}(\sigma)
= 2^k\,\operatorname{Tr}_{\operatorname{Ref}}\!\left[
(\bar{V}\sigma^{T}V^{T} \otimes I)\,J_{\Pi}(\Lambda)
\right].
```

where the transpose on the reference is the convention the construction
applies, with `Y^T = −Y`. The operator on the reference cannot be `σ^T`
itself: `σ` acts on `k` qubits and `Ref(X)` has `|X|` wires. The reference
half of the prepared state lives in the image of the conjugate isometry, and
`σ^T` is carried there by it. Since `V^T` is the adjoint of that conjugate,
their product is the identity on `k` qubits, and the expression reduces to
the ordinary inversion applied to `(id ⊗ Λ̃)(Φ_k)`. Equal Choi states therefore give `Λ̃ = Λ̃′`, and by
the first step `Λ = Λ′` on every state supported in `supp(τ_X)`.

Equality of the induced logical channels determines `Λ` only on the image of
`E`, which is `supp(τ_X)` — precisely the domain the theorem asserts. ∎

The implementation compares canonical signatures. An equivalent double-inclusion
test exists in the same module but has no caller; Lemma 1 makes the two
equivalent, and the signature form is retained because it is a normal form —
one comparison rather than `2·|generators|` membership solves.

### 3.4 Gauge invariance

**Proposition 1.** *The verdict is invariant under any transformation acting
only on the discarded environment.*

*Proof.* `J_Π` is obtained by partial trace over the environment, and the trace
is invariant under isometries acting on the traced factor alone. ∎

Consequently two circuits differing only in ancilla convention or Stinespring
dilation receive the same verdict — a property required for accepting output
from compilers that do not share the reference implementation's conventions.

The family singled out in Section 6.2 exercises a different property: its
members act on the input side, inside the stabilizer group of `τ_X`, and test
the restriction to the code subspace. Invariance on the output side is
exercised by a regression test of the implementation, which appends gates to
accessible wires outside the requested output and checks that the verdict
does not move.

### 3.5 The target

Sections 3.2 to 3.4 compare a candidate with a target without saying which
channel the target is. This section names it, states the recipe by which the
verifier builds it, and proves that the two agree. The chain is then complete:
the specification defines one channel, Lemma 2 identifies its signature, and
Theorem 1 says what equality with that signature certifies.

Let `N` be the channel from `M` to `X` that the specification defines: the
input is adjoined to the ancillas, `U` is applied, and the inaccessible
register `C` is traced out. Write `d = 2^{|M|}` and `r = 2^k`. The state
`τ_X` of Section 3.1 is the image of the maximally mixed input, and it is flat
on its support:

```latex
\tau_X = N(I_M/d) = \Pi/r .
```

**Definition 4 (target channel).** The target `Λ₀` is the Petz recovery map
of `N` with respect to the maximally mixed input
\cite{khatri2020principles}. Its input space for certification is the code subspace of `X`, and its output is `M`:

```latex
\Lambda_0(A)
= \frac{1}{d}\,N^{\dagger}\!\left(
\tau_X^{-1/2}\,A\,\tau_X^{-1/2}\right) ,
```

where the inverse is taken on the support of `τ_X`. Flatness removes the
square roots: for every operator `A` supported in `supp(τ_X)`,

```latex
\Lambda_0(A) = \frac{r}{d}\,N^{\dagger}(A) .
```

*The recipe of the verifier.* Take the signed generators of the Choi state of
the source on the registers `R`, `X` and `C`. Replace each by its complex
conjugate in the computational basis: in a tableau, the sign of every
generator containing an odd number of `Y` is flipped, and nothing else
changes. Trace out `C`. Read `R` as `O` and `X` as `Ref(X)`.

**Lemma 2 (signature of the target).** *Let `J(N) = (id ⊗ N)(Φ)` be the
normalised Choi state of `N`, written in the order `R`, `X`. The code-Choi
state `J_Π(Λ₀)` of the target, written in the order `O`, `Ref(X)`, is the
complex conjugate of `J(N)` once `R` is read as `O` and `X` as `Ref(X)`.
Consequently `sig(J_Π(Λ₀))` is the signature the recipe produces.*

*Proof.* Let the `K_i`, from `M` to `X`, be Kraus operators of `N`. Then

```latex
\tau_X = \frac{1}{d}\sum_i K_i K_i^{\dagger} ,
```

so the range of every `K_i` lies in `supp(τ_X)` and `Π K_i = K_i`. By the flat
form of Definition 4, Kraus operators of the target on `supp(τ_X)` are

```latex
\sqrt{r/d}\;K_i^{\dagger} ,
```

writing these operators as `L_i` gives

```latex
\sum_i L_i^\dagger L_i=\frac{r}{d}\sum_i K_iK_i^\dagger
=r\tau_X=\Pi .
```

Thus the map preserves trace on the code. With the support inverse its trace
on a positive operator on the full register is the weight of that operator
in the code.

Write `V` for the isometry `|ψ⟩ ↦ E(|ψ⟩ ⊗ |0⟩^{|X|−k})`, so that `VV† = Π`.
The state prepared in Definition 2 is

```latex
\frac{1}{\sqrt r}\sum_{a}\bar{V}|a\rangle\otimes V|a\rangle
= \frac{1}{\sqrt r}\,(I\otimes\Pi)
\sum_{x}|x\rangle_{\operatorname{Ref}}|x\rangle_{X} ,
```

the canonical purification of `τ_X`: the conjugate on the reference is what
makes the right-hand side independent of the choice of `E`. Applying the
target to `X` gives

```latex
J_{\Pi}(\Lambda_0)
= \frac{1}{r}\cdot\frac{r}{d}\sum_i |\kappa_i\rangle\langle\kappa_i| ,
\qquad
|\kappa_i\rangle
= \sum_{x,m}\overline{\langle x|K_i|m\rangle}\;
|x\rangle_{\operatorname{Ref}}|m\rangle_{O} .
```

The factor `r/d` of the target meets the normalisation `1/r` of the code and
leaves `1/d`, the normalisation of the source. On the other side,

```latex
J(N) = \frac{1}{d}\sum_i |k_i\rangle\langle k_i| ,
\qquad
|k_i\rangle = \sum_{x,m}\langle x|K_i|m\rangle\;|m\rangle_{R}|x\rangle_{X} .
```

The two families of vectors have complex-conjugate coefficients once `R` is
read as `O` and `X` as `Ref(X)`, which is the first claim.

For the second, conjugation in the computational basis commutes with the
partial trace over `C`, so conjugating the pure state on the three registers
and then tracing out `C` gives the conjugate of `J(N)`. And the conjugate of a
stabilizer state is the stabilizer state whose generators are conjugated: `X`
and `Z` are real, `Y` is imaginary, so a Pauli string changes sign exactly
when it contains an odd number of `Y`. ∎

**Corollary 1 (semantic check).** *A candidate `Λ` passes the reduced-channel
signature check if and only if
`Λ(ρ) = Λ₀(ρ)` for every `ρ` supported in `supp(τ_X)`.*

*Proof.* Lemma 2 identifies the signature of the recipe with `sig(J_Π(Λ₀))`,
and Theorem 1 applies: its proof uses of the two channels only their code-Choi
states, and that of the target is a stabilizer state by Lemma 2. ∎

The smallest instance on which the conjugation matters is a one-qubit message
beside an ancilla prepared in `|+i⟩`, with `U` the identity and both wires
accessible. The source Choi state carries `+Y` on the ancilla; the target
carries `−Y`, and so does the reference of the candidate, which `Ē` prepares
in `|−i⟩`. Returning the message and discarding the ancilla is accepted. A
target compared without conjugation would carry `+Y` and reject this correct
recovery.

---

## 4. Scope

The class we treat is narrow, and the boundary is a design choice rather than
an artifact of the implementation. We state it before reporting results so that
every subsequent claim is read within it.

### 4.1 What the procedure covers

Stabilizer channels, as defined in Section 2. Within this class the decision
of Section 3 is exact.

Gottesman–Knill is what makes this possible, and the same fact bounds the
result: nothing here transfers to non-Clifford gates, and the procedure says
nothing about circuits containing `T` gates or arbitrary rotations.

### 4.2 What is out of scope by construction

Noise, calibration, real-time decoding, and scheduling. These are physical or
temporal properties; a stabilizer Choi state does not express them. Verifying
that a circuit implements the intended channel is separable from verifying that
a device executes it faithfully, and we address only the former.

### 4.3 Measurement and feed-forward

The recovery circuits verified here are coherent isometric dilations: they
contain no mid-circuit measurement, and consequently no branching on
measurement outcomes.

The class **admits** a symbolic treatment of the general case: a Pauli
correction that is an `F₂`-linear function of a syndrome is a linear map, which
a stabilizer formalism can verify once rather than per branch. The current
implementation **contains no syndrome handling at all** — its recovery circuits
are measurement-free, so no branch arises and no such matrix is constructed. We
**claim nothing** about that path and report no results for it.

That path is the subject of Kliuchnikov, Beverland and Paetznick
\cite{kliuchnikov2023stabilizer}, whose algorithms verify circuits with Pauli
corrections conditioned on parities of measurement outcomes, over all outcomes
at once. Section 8 compares the two works.

Yoshida and Kitaev \cite{yoshida2017efficient} give two decoders for the same
recovery task, one probabilistic, by post-selection, and one deterministic. We
claim no correspondence between either construction and the circuits verified
here.

### 4.4 What is verified and what is reported

The verdict covers semantic equality of the reduced channel on the specified
subspace, conformance to the coupling map — every two-qubit gate is checked
against an edge of the device graph — and invariance under change of
Stinespring dilation.

Depth and two-qubit gate counts are recomputed by the verifier from the final
gate list and **enter the verdict**. SWAP attribution — how many SWAPs serve
movement versus restoration — is not reconstructible from the artifact format
and participates in no verdict; the tables of Section 6 report it as a
measurement.

### 4.5 Bounds on the cost measurements

The scaling results of Section 7 are measured on one family of instances: a
chain architecture with random stabilizer scramblers, a single seed, and two
scrambling depths. Two consequences.

First, the exponent we measure is an exponent of that family. Because the
family's generator density drifts with `n`, it is not a degree at fixed
density; Section 7.6 separates the two.

Second, no extrapolation to surface-code circuits is warranted. The densities
measured range from **0.149 to 0.578**. For a surface code the same metric is
derived rather than measured: a code of distance `Δ` has `Δ²` data qubits and
stabilizer generators of weight at most four, so mean weight `w̄` gives density
`w̄ / Δ²`, and `Δ = 5` sits at `3.33 / 25 ≈ 0.133` — at the edge of the measured
range rather than beyond it. The order-of-magnitude gap appears only at
`Δ ≥ 13`, where constant-weight generators over a growing lattice drive the
density as `1/n`. Cost projections beyond the measured range are upper bounds
on a family chosen to be unfavourable, not predictions.

### 4.6 Two adversarial campaigns

We report two campaigns with different objects, and the figures are not
interchangeable:

- `orelia.verifier-adversarial-campaign/v1` targets the verifier as a whole.
- `orelia.channel-certified-adversarial-campaign/v1` targets the
  `channel-certified` policy specifically.

Section 6.2 states which is which; a reader encountering either figure in a
published CSV can identify it by these strings, which are the `format_version`
recorded in the artifacts and retained from an earlier name of the project.
Conflating them would suggest an inconsistency where there is none.

---

## 5. Implementation

StabCert implements the procedure of Section 3. It is a Python package with two
runtime dependencies, NumPy and Stim \cite{gidney2021stim}, the latter
providing the tableau engine
on which canonical comparison rests. It is available under Apache 2.0.

The package also contains a routing procedure. It exists because the
`reproducible-route` policy below requires a reference route to compare
against; it is not offered as a compiler and no claim is made about its output
relative to other routers.

### 5.1 Two policies

The tool exposes two verification policies, and the distinction is the point of
the design.

`reproducible-route` requires bit-for-bit equality with the reference route. It
answers *did this run reproduce the reference implementation?* and is used for
regression testing.

`channel-certified` reconstructs the target from the channel specification and
accepts any synthesis, routing, or Stinespring dilation whose canonical signed
signature matches. It answers the question of Section 1: *does this artifact,
however produced, realise the specified channel on the specified subspace?*

Circuits routed by third-party compilers fail the first policy and pass the
second. That is the intended behaviour, and Section 6 reports it as such.

### 5.2 The certified closure

The verification path is a closed import closure, computed by AST traversal
from the three entry points — compiler, verifier, command line — and enforced
by the test suite. The closure comprises eleven modules; the verifier alone
reaches eight. No module within it constructs a dense matrix or enumerates
basis states.

The distribution also ships exploratory and instance-construction code outside
this closure, including a dense stabilizer-group enumeration. No verification
path can reach it, and the closure test fails if that changes. We state this
because the claim of Section 3 — polynomial time, no enumeration — is a claim
about the closure, not about every file in the package; a reader who greps the
installed package will find the enumeration and should know why it is harmless.

The closure assertion is bidirectional: it fails both if an unreachable module
becomes reachable and if a declared module is no longer reached, so the
declaration cannot decay into a wish list.

### 5.3 What the verdict aggregates

A single invocation checks, and reports separately:

- Semantic equality of the reduced channel on the code subspace, by canonical
  signature comparison (Section 3).
- Coupling-map conformance: every two-qubit gate in the routed circuit is
  checked against an edge of the device graph, gate by gate, on the final gate
  list. No routing trace is required, since the final gate list is what the
  device executes.
- Metadata consistency: the artifact's claimed support is compared against the
  reconstructed `Π`, never used to build it (Hypothesis 1).

These are independent conditions, not components of a score: a failure in any
one produces a failing verdict, and no success elsewhere compensates for it.

Resource figures are recorded alongside the verdict; Section 4.4 states which
of them enter it.

### 5.4 Reproducibility

Published test counts are not written by hand. A synchronisation script replays
the suite, parses the summary, and rewrites the counted spans in the
documentation; it refuses to touch the documentation if the suite is not green,
and a `--check` mode exits non-zero on divergence for use in CI.

The script guarantees that the documentation matches the local suite. It does
not, by itself, guarantee anything about what a reader obtains from a checkout.
That is established separately: a continuous-integration job runs the suite
from a checkout on each push, under Python 3.10 and 3.12, with core
dependencies only and then with every optional backend. The suite passes: 124
tests with all backends, 104 passing and 2 modules skipped without them.

---

## 6. Evaluation

### 6.1 Third-party routes

We compile reference recovery circuits for three fixtures and route them with
two external compilers, Qiskit SABRE and pytket. Six routed artifacts result.
For each, the verdict is identical:

| check | result |
|---|---|
| route differs from reference | yes |
| `reproducible-route` | rejected |
| `channel-certified` | accepted |
| phase mutation | rejected |
| falsified final permutation | rejected |
| deterministic replay | byte-identical artifact |

The first three lines are the intended behaviour of the two policies: a route
produced elsewhere is not the reference route, and is nonetheless the specified
channel. The last three establish that acceptance is not vacuous — a single
sign flip in the tableau, or a permutation claimed but not realised, is caught.

**Reproducibility.** The routed artifacts reported here were produced with
Qiskit 2.5.1 (SABRE \cite{li2019sabre}, `decay` heuristic, seed 20260803, one trial) and pytket 2.18.1
\cite{sivarajah2020tket} (`RoutingPass` with `LexiLabellingMethod` and `LexiRouteRoutingMethod`),
on the fixtures published under `tests/fixtures/recovery_v1/`. SABRE is a
stochastic search: a different seed or version yields a different route, which
`channel-certified` accepts and `reproducible-route` rejects — the verdicts of
this section are stable under that variation, the resource figures are not.

### 6.2 Adversarial campaigns

Two campaigns, with distinct objects and non-interchangeable figures.

| campaign | invalid | valid | false accepts | false rejects |
|---|---:|---:|---:|---:|
| `orelia.verifier-adversarial-campaign/v1` | 10 000 | 1 000 | 0 | 0 |
| `orelia.channel-certified-adversarial-campaign/v1` | 1 300 | 800 | 0 | 0 |

One family in the second campaign deserves mention, because it is the only one
that separates the two possible specifications. Its members prefix the circuit
by an element of the stabilizer group of `τ_X`: every state of the code
subspace is a `+1` eigenvector, so the action there is unchanged while the
total unitary differs. These artifacts must be accepted under the
subspace-restricted specification of Section 3 and would be rejected under a
total-channel specification. **All 100 are accepted.** Without this family, no
measurement in either campaign would distinguish the two readings of the
theorem.

Mutation testing is reported by family rather than in aggregate: 10 000 sign
flips is one class tested 10 000 times, not 10 000 classes.

### 6.3 Resources

Depth and two-qubit gate counts are recomputed by the verifier from the final
gate list and enter the verdict; they are certified quantities. The `reference`
column is the route the verifier reconstructs and against which difference is
established — it is a baseline, not a scored competitor.

| A | arch | logical | reference | SABRE | pytket |
|---:|---|---:|---:|---:|---:|
| 1 | chain | 12 / 14 | 46 / 62 | 49 / 68 | 34 / 41 |
| 8 | chain | 82 / 111 | 391 / 687 | 584 / 939 | 401 / 694 |
| 12 | grid_2d | 154 / 229 | 464 / 751 | 668 / 1177 | 454 / 808 |

Routing overhead, relative to the logical circuit:

| A | arch | reference | SABRE | pytket |
|---:|---|---:|---:|---:|
| 1 | chain | 3.83 / 4.43 | 4.08 / 4.86 | 2.83 / 2.93 |
| 8 | chain | 4.77 / 6.19 | 7.12 / 8.46 | 4.89 / 6.25 |
| 12 | grid_2d | 3.01 / 3.28 | 4.34 / 5.14 | 2.95 / 3.53 |

**Both tables are to be read across, not down.** Overhead rises from `A = 1` to
`A = 8` and falls at `A = 12`; the fall is a topology effect, not a size effect
— the grid offers better connectivity than the chain. Rows compare routers at a
fixed instance; they compare nothing to each other.

On `A = 12`, pytket produces a circuit shallower than the reference by 10
layers while using 57 more CNOTs. Which of the two is preferable has no answer
independent of a stated cost function — and this is a fact about routing, not a
comparison of tools.

Between the two external routers, pytket produces both the shallower and the
cheaper circuit on all three fixtures. Three instances, two topologies, one
SABRE seed and one configuration each: this is what was observed, not a
ranking.

### 6.4 Time

| measurement | value |
|---|---|
| SABRE regression, 3 fixtures, end to end | 50.06 s, peak RSS 88.95 MiB |
| pytket regression, 3 fixtures | 49.67 s, peak RSS 55.97 MiB |
| verification alone, 2 100 campaign cases | median 77.3 ms, mean 83.9 ms, max 172.1 ms |
| verification at `n = 9 / 20 / 40` | 0.24 s / 10.43 s / 272.23 s |

The last row cross-checks Section 7.5 without having been fitted to it:
doubling `n` from 20 to 40 multiplies time by **26.1**, against **27.5**
predicted by the exponent of 4.78 measured on the upper-half window over
`n = 9…40`.

---

## 7. Cost

Two different questions are answered here, and conflating them is the way this
section is most likely to be misread. **What does verification cost as
instances grow?** is a question about a family. **What is the degree at fixed
generator density?** is a question about the algorithm. The family we measure
has a density that drifts with `n`, so the two answers differ. Both are
stated; neither is the other. An upper bound is proved in 7.4 by counting
calls. The measured exponents are compatible with it; they do not identify the
asymptotic degree.

### 7.1 Counters, not seconds

Cost is reported as GF(2) operation counts, instrumented in the elimination
routines. Three counters matter: the number of affine systems solved, the
number of row XORs, and the number of scalar bit XORs. Row XORs are the
machine-relevant measure, since NumPy vectorises a row operation; scalar bit
XORs are a machine-model-independent upper bound that overcounts vectorised
work by about `n`.

Counters are deterministic: they do not vary with machine load, scheduling, or
repetition. Section 7.5 explains why wall-clock time, which does vary, is
reported but not used as the complexity.

### 7.2 An exact identity

Over 32 instances, `n = 9` to `40`, the number of affine systems solved is not
approximately but **exactly**

```
N_sys(n) = 28n² − 232n + 598
```

with zero residual. Second differences are constant at 56; the reader can
recompute this from the published CSV.

The identity is not an accident of the sweep. Proposition 2 (7.4) gives the
number of affine systems solved as a closed form in the dimensions of the
calls the verifier makes, with no dependence on the data beyond the ranks of
the reduced groups. On this family the inaccessible register is empty,
`k = n − 8`, and the source Choi tableau has width `W = 2n − 8`. In verifier order, the six
kernel-image ranks for the exact artifacts are `8, W, W, W, 2k, 2k`. The first
counts the support constraints; the next three are the ranks of pure Choi
states on the retained wires. The last two count the Bell stabilizers after
recovery and their intersection with the Bell target. The respective numbers
of variables are `W, W, 2n, W, W, 4k`; substituting gives
the polynomial above, term for term.

Affine solves are not the only eliminations. Testing whether a vector lies in
a span costs two rank reductions, and the same sweep records them:
`rank_reductions` grows from 3 940 at `n = 9` to 762 440 at `n = 40`, with
exponents of 3.636 and 3.292 on the lower and upper windows. The solves are
quadratic; the rank reductions are not.

### 7.3 A prediction, registered before measurement

Composing the nesting with the cost of one elimination gives the targets. That
second factor was assumed on a first pass and the assumption mixed units: it
took `n³`, the bit count of an elimination, for its row count. Measuring one
elimination against system size settles it — exponents 1.98 for row operations
and 2.96 for bit operations over sizes 16 to 128
(`results/elimination_cost.json`). So `Θ(n²)` eliminations, each `O(n²)` row
operations and `O(n³)` bit operations, predict degrees 2, **4** and **5**.
That composition counts the affine solves and no other elimination. It is
stated here as it was registered; 7.4 reports what the rank reductions of 7.2
do to it.

Three lines of measurement decided what 32 swept points had not, because the
factor had never been measured — only supposed.

Observed exponents cannot be compared to those targets directly: they are
inflated by lower-order terms. The counter whose degree is known exactly
calibrates that inflation on the same instances. The inflation is derivable in
closed form from the identity above — the tangent exponent is `n·N_sys′(n)/N_sys(n)`,
so the bias is

```latex
\beta(n) = \frac{232n - 1196}{28n^2 - 232n + 598}
\longrightarrow \frac{232}{28} = \frac{8.286}{n}.
```

matching the measured secant bias to within `1.2 × 10⁻³` across the range.

With `τ = max(observed(S) − 2, 0.1)` and `excess = observed − target`, the rule
registered before the sweep was: **confirmed** if `excess ≤ τ` and the exponent
is still falling; **rejected** if `excess > 2τ` or the exponent rises;
**undecided** otherwise, which alone justifies extending the range. The floor
of `0.1` prevents the test from degenerating as the bias vanishes; it did not
bind here, the measured bias being 0.2896.

Registering this mattered. At `n ≤ 30` the rule returned *undecided* for
`row_xors` by 0.007 — an excess of 0.3914 against a tolerance of 0.3843. A
threshold chosen after seeing that number would have been chosen differently.

### 7.4 Result

Windows are the lower and upper halves of `n = 9…40`, 16 points each.

| counter | target | lower | upper | trend | excess | tolerance | verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| `affine_systems_solved` | 2 | 2.690 | 2.290 | −0.400 | — | — | calibrator |
| `row_xors` | 4 | 6.285 | **4.907** | −1.378 | +0.907 | 0.290 | **rejected** |
| `scalar_bit_xors` | 5 | 7.643 | **6.106** | −1.536 | +1.106 | 0.290 | **rejected** |
| `verify_seconds` | — | 4.711 | 4.780 | **+0.068** | — | — | not a verdict |

**Both are rejected at the registered threshold**, and the earlier reading of
this table said the opposite. It compared the same measurements against
targets of 5 and 6, found excesses of −0.09 and +0.11, and recorded a
confirmation. Those targets came from the unit-mixed composition; a
pre-registered threshold can only validate the prediction it is given, and it
confirmed a wrong one with every appearance of rigour. The threshold did not
fail. The hypothesis did.

The measured exponents fail the registered criterion. The composition of 7.3
counted the affine solves and omitted the rank reductions of the
span-membership tests, which Proposition 2 below bounds by `O(W³)` and which
the sweep records growing faster than the solves (7.2). Counting them gives
upper bounds of degrees 5 and 6. Those are the figures the first reading of this table had
used, and they are not vindicated by it: they had been obtained by a
composition that mixed units, and a bound is owed to its derivation, not to
its value.

Proposition 2 is a bound in the width `W` of the source Choi tableau, and the
measured exponents are exponents in `n` of one family, on which `W = 2n − 8`.
A monomial of degree `p` in `W` has local exponent `p·n/(n − 4)` in `n`: over
the upper window `n = 25…40`, between 5.56 and 5.95 for `p = 5`, and between
6.67 and 7.14 for `p = 6`. The measured 4.907 and 6.106 sit below those
values and are still falling. The range does not identify their limits, and
we do not claim that it does.

Single-step exponents are not reported — at the top of the range they are
unstable enough to be meaningless.

**Proposition 2 (cost bound).** *Consider the completed semantic checks on
well-formed v1 inputs with a full independent set of pure target generators
in the prescribed registers. Write `W = |M| + |X| + |C|` for the source Choi
width, `n = |X|`, and `k` for the number of logical qubits. The
verifier reaches the elimination routines through `n + k + 6` calls, on
matrices of at most `4W` rows and `2W + 1` columns.*

*(i) A kernel-image call on `v` variables that returns `ρ` generators solves
exactly `1 + ρ(v + 2)` affine systems and performs at most `1 + 2ρ(v + 1)²`
rank reductions. A lexicographic search on `v` variables solves exactly
`v + 2` systems and performs at most `2(v + 1)²` rank reductions.*

*(ii) Hence the number of affine systems solved is exactly*

```latex
N_{\mathrm{sys}}
= (n + k)(2n + 2) + \sum_{j=1}^{6}\bigl(1 + \rho_j\,(v_j + 2)\bigr) ,
```

*which is `O(W²)`; there are `O(W³)` rank reductions; and the instrumented eliminations cost
`O(W⁵)` row operations and `O(W^6)` bit operations over `F₂`. These upper bounds are uniform in generator density and gate count. The actual work can depend on the data.*

*Proof.* The counts of (i) are read off the routines. The kernel-image
routine solves one system, reduces one matrix, then runs a span-avoiding
search once per generator it returns. The search runs a feasibility test once,
then once per variable, then solves once. A feasibility test solves one
system and tests at most `v + 1` vectors — a particular solution and a basis
of the kernel — for membership in the span of the generators already chosen,
each test being two rank reductions. The loop over the kernel may stop early,
which is why the rank count is a bound and the solve count is not. The plain
lexicographic search is the same without the membership tests.

The calls are these. One kernel-image call reduces the source onto `X`.
Definition 1 then takes `2k` span-avoiding searches and `n − k` plain
searches, all on `2n` variables, for the logical operators and the
destabilizers. Five further kernel-image calls reduce the target, the
candidate and the target the artifact declares, and compute the entanglement
fidelity in two steps. The six `vⱼ` are `W`, `W`, `2n`, `W`, `W` and at most
`4|M|`, and every `ρⱼ` is at most `2W`. Summing (i) gives the identity and
the two orders of magnitude.

One solve performs at most `2W` pivots, each adding the pivot row to at most
`4W` rows, hence `O(W²)` row operations; `O(W²)` solves give `O(W⁴)`. One
rank reduction acts on `O(W)` rows and columns, hence `O(W²)` row operations;
`O(W³)` of them give `O(W⁵)`. A row spans at most `2W + 1` bits. ∎

The membership loop stops at its first witness, so tightness requires a
separate argument. If the declared target has a different width or generator
count, its reduction uses those actual dimensions; malformed inputs can
return before completing the listed calls.

For gate-dependent work, let `G` be the combined length of the supplied
source, logical and routed gate lists. Source propagation acts on `W` signed
generators; the logical-action check propagates up to `2k` Paulis and the
candidate and fidelity checks replay routed gates on tableaux of width at
most `2W`. With elementary Clifford tableau updates these passes take
`O(GW)` word or bit-position updates in the ordinary unpacked tableau model
\cite{aaronson2004improved}. Conversions between generators, tableaux and
synthesized preparation circuits have additional polynomial cost in `W`
\cite{gidney2021stim}. Reading and hashing the explicitly serialized input
also costs at least its length. These terms explain why elimination counts
alone cannot bound elapsed verification time.

The implementation additionally reports the greatest graph distance of a
routed interaction, by a breadth-first search that visits each site of the
coupling graph at most once per CNOT; the topology verdict itself uses direct
edge membership. In v0.1.1 the frontier of that search could hold a site once
per shortest path reaching it, which made the diagnostic exponential in the
distance on some rejected routes. Version 0.1.2 removes the repetition, and
the diagnostic is now linear in the size of the graph for each gate read.

The tests compare the per-call formula with instrumented runs; the CSV
provides a separate check on the measured family.

### 7.5 Wall time is not the complexity

Timing gives an exponent of **4.780** on the upper-half window over
`n = 9…40`. An unrelated instance family — four structural preflights over
`choi_qubits = 26…32` — gives a log-log exponent of 4.55 for its
construction-and-verification time. The agreement is a consistency check across
harnesses, not a second measurement of the same quantity: the ranges, the
parameters and the timed sections differ.

The fitted timing exponent rises from 4.711 to 4.780 across the two
windows, while the row-XOR exponent falls from 6.285 to 4.907. Their
upper-window difference is about 0.13. NumPy processes a row XOR as a
vector operation, whose elapsed cost also depends on row length. The two
finite-window fits do not determine a common limiting exponent.

### 7.6 Density, and what the exponent is an exponent of

The measured family's generator density is not constant: it drifts as
`n^{−0.238}`. This is mechanical rather than incidental — at fixed scrambler
depth the number of two-qubit gates grows linearly while the number of matrix
entries grows quadratically, so normalised density must fall.

A paired design was registered to neutralise density by holding scrambler depth
fixed. It failed on its own terms: the density contrast between the two depths
itself drifts from 1.259 to 2.455, an exponent of `n^{0.582}` against a
tolerance of 0.384, so the ratio exponent conflates a degree effect with a
widening gap and is not readable. Density does not stay neutralised; it must be
modelled.

Pooling both depths at 22 matched widths — where the elimination structure is
identical, the same `N_sys(n)` at every width — gives

```latex
\log(\mathrm{row\_xors}) = a + b\log n + c\log(\mathrm{density}),
\qquad b = 6.313,\quad c = 1.410.
```

Before reading those coefficients, two gates. The model must reproduce each
arm's observed exponent: it does, to `±0.077` against a tolerance of 0.384
(dense, observed 6.054 against 5.977; sparse, observed 5.079 against 5.156).
And the same model fitted to the exactly-known counter, whose true density
elasticity is zero, must return approximately zero: it returns `c₀ = 0.006`.
The method invents essentially nothing.

`c = 1.410` against a threshold of 0.384 and a false-positive floor of 0.006:
**density governs a real share of the cost.** `b = 6.313` is an all-points fit
and carries the same finite-size inflation the calibrator shows on that fit
(`b₀ = 2.611` against a true 2, so `+0.611`), giving a bias-corrected degree at
fixed density of about **5.7** — higher than the measured family exponent of
**4.907** on the upper-half window over `n = 9…40`, as it must be, since
density falls with `n` and cost rises with density. The relation that
reconciles the two is `family exponent = b + c·δ`, with `δ` the density drift
of the arm.

Proposition 2 makes a caveat on that figure unavoidable. 5.7 exceeds 5, the
degree by which the proposition bounds row operations, and no correct estimate
of an asymptotic degree can. The weak step is the subtraction: it removes from
a quantity of degree near 5 the inflation measured on a calibrator of degree
2. On this family the width of the source tableau is `2n − 8`, a monomial of
degree `p` in that width has local exponent `p·n/(n − 4)` in `n`, and the
inflation is therefore proportional to the degree, not additive. Scaling
rather than subtracting gives `2b/b₀ = 4.84`. We report both and rely on
neither: the first is known to be too high, and the second assumes the cost
is a single monomial in the width, which it is not.

The figure quoted here was 5 in an earlier draft. That was not a measurement
but the invalidated target of 7.3, left behind when the targets were corrected
— the kind of residue a stale prediction leaves in prose that once agreed with
it.

One weakness to report: the maximum log residual is 0.408 for `row_xors`
against 0.104 for the calibrator. The model satisfies the exponent gate but
fits appreciably less well pointwise; `c = 1.41` has the right sign and order
of magnitude, and its second decimal does not.

This is why Section 4.5 forbids extrapolation to a surface code. The relevant
comparison is of drift regimes: the dense arm drifts as `n^{−0.238}`, the
sparse arm as `n^{−0.820}`, a surface code as `n^{−1}` — constant-weight
generators over a growing lattice. The sparse arm already approaches the
surface-code density regime without having its locality. What is captured is
density; what is not is locality.

### 7.7 One method tried and rejected

Fitting `e(n) = γ + K/n` to the sequence of local exponents extrapolates the
asymptotic degree directly and would have terminated the range question
cleanly. Run first against the calibrator, whose degree is exactly 2, it
returns `γ = 1.941` with a jackknife spread of `[1.939, 1.942]` over
`n = 9…40` — excluding the truth inside an interval some thirty times too
narrow.

The `1/n` form is only the leading correction, so its residuals are systematic,
and a jackknife measures the stability of a fit rather than its accuracy. The
method is not used. We record it because the failure is not specific to these
data: any resampling estimate of uncertainty will tighten around the wrong
value when the error is systematic, and only a quantity with a known answer
reveals it.

---

## 8. Related work

Two bodies of work are close to ours, and three further lines address adjacent
problems. We have not executed any of the tools discussed below; the
characterisations that follow are drawn from their published documentation and
papers.

**Stabilizer circuit verification.** Kliuchnikov, Beverland and Paetznick
\cite{kliuchnikov2023stabilizer} give classical algorithms that characterise
and verify stabilizer circuits exhaustively over measurement outcomes. Their
circuits allocate qubits in the zero state, measure Pauli operators, draw
random bits, and apply Pauli unitaries conditioned on parities of earlier
outcomes. A circuit is brought to a *general form*, two circuits are compared
through their general forms, and a further algorithm computes the logical
action of a circuit between an input and an output stabilizer code. This is
the closest published work to Section 3, and three points are worth stating
exactly.

The difference is not one of classes. Their primitives include measurement
and outcome-conditioned Pauli corrections, and ours include partial trace,
but neither list excludes the channels of the other. A destructive
measurement — measure, correct, deallocate — discards a qubit, and Pauli gates
controlled by affine functions of outcomes can be rewritten without classical
control \cite{yashin2025characterization}. What Section 4.3 places outside
this work is an input format of the implementation, not a class of channels.

The difference is the object compared. They compare quantum instruments:
every outcome is retained, and two circuits are equivalent when a relabelling
of outcomes matches their maps. We compare one channel — the candidate reduced
onto the requested outputs — on the inputs of a code subspace, and nothing of
the discarded register is retained.

The normal forms differ in kind. Their general form is not unique — equal
circuits can have different general forms — so equivalence is decided by a
comparison procedure that solves for the relation between the two outcome
records. The signature of Lemma 1 is canonical: equality of two channels on
the code subspace is equality of two tuples of signed generators.

The input, lastly, does not separate the two works. Their logical-action
algorithm takes a circuit and two codes, not a reference circuit, and to that
extent it is driven by a specification as ours is. What we add on that axis is
narrower: the support `Π` is derived from the specification alone
(Hypothesis 1), the candidate is an artifact of unknown provenance, and the
procedure is delivered as a tool whose implementation is tested adversarially
(Section 6.2). Their article discusses data structures for an implementation
and analyses running times, but releases no software that we could find; we
make no comparison of running times.

**Clifford channels.** Yashin and Elovenkova
\cite{yashin2025characterization} characterise the class of Section 2:
channels realised by stabilizer circuits without classical control,
equivalently channels whose Choi state is a possibly mixed stabilizer state,
equivalently channels admitting a Clifford Stinespring dilation. They also
give a normal form for such channels, up to Clifford unitaries on the input
and on the output. That form classifies channels; we test the equality of two
channels in registers the specification fixes, where no such freedom is left.

Yashin \cite{yashin2025streamlined} represents a channel of this class by a
signed tableau derived from its Choi state, reduces composition to Boolean
linear algebra, and describes the reduction of such a tableau to echelon form
by signed row operations, with its cost. Neither the representation nor its
signed reduction is therefore new here. As far as we could read, that work
does not state that the reduced form decides the equality of two channels,
and it does not restrict a channel to a subspace of inputs. Our contribution
on this side is the choice of the support from the specification, the
reconstruction of the target, and the certificate for a circuit supplied from
outside.

**Compiler certification.** Proving the transformation itself, once and for
all, is stronger where it applies. It requires a proof about the compiler's
code, kept up as that code changes. Translation validation certifies each
output rather than the producer: the artifact is verified without inspecting
the compiler that produced it. That is the route taken here, for the routing
passes of Qiskit and pytket as for any other.

**Equivalence checking.** QCEC \cite{burgholzer2021advanced} compares a
compiled circuit against a reference circuit. Its decision-diagram engines provide exact equivalence checking by
comparing canonical representations of the implemented operators, with support
for ancilla and garbage qubits and a notion of partial equivalence defined on
measurement distributions, although resource consumption can be exponential in
the worst case; a ZX-calculus engine \cite{peham2022zx} is often effective at
establishing equivalence but, being based on an incomplete rewriting procedure, cannot in
general establish inequivalence. The two engines are combined deliberately, and
exploiting the `G G′†` structure is the published contribution that keeps the
diagrams small in practice.

Like our approach, QCEC relies on canonical representations. The distinction is
not canonicity but the object represented and the input required: QCEC
canonically represents operators and compares two of them, whereas we
canonically represent a stabilizer channel restricted to a code subspace and
compare one against a target reconstructed from a channel specification. This
is not a deficiency of QCEC — in its own use case, checking that a compiler
preserved the source circuit, the reference *is* the specification and the
question is well posed. The gap matters only where no reference exists yet.

**Deductive verification.** Qbricks \cite{chareton2021qbricks} verifies
circuit-building quantum programs,
reaching parametric implementations of Shor's order finding, quantum phase
estimation and Grover's search, with high proof automation over parametrized
path sums in Why3. Its scope is far wider than ours in the class of circuits
reached; its documented workflow is to write a program in its own DSL, and we
found no documented import path for an artifact produced elsewhere. The two
tools therefore answer different questions and admit no meaningful quantitative
comparison: proof effort and verification time are not the same quantity, and
tabulating them side by side would suggest a commensurability that does not
exist.

**Summary.** The axis that separates this work from compiler certification,
equivalence checking and deductive verification is the input. Compiler
certification takes a compiler; equivalence checking takes two circuits;
deductive verification takes a program. We take an artifact of unknown
provenance and a channel specification. From stabilizer circuit verification
the separation is narrower and of a different kind: the object compared is one
reduced channel on a code subspace rather than an instrument with its outcome
record, the form is canonical rather than general, and the procedure is
released as a tool.
