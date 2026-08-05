# StabCert

[![clean clone](https://github.com/KRAMARCZYK62750/stabcert/actions/workflows/clean-clone.yml/badge.svg)](https://github.com/KRAMARCZYK62750/stabcert/actions/workflows/clean-clone.yml)

Sound and complete translation validation for stabilizer channels.

Quantum compilers rewrite circuits to fit hardware connectivity constraints.
StabCert checks, exactly, that the rewritten circuit still implements the
intended channel — treating the compiler as an untrusted black box.

## What it does

Given a target channel and a circuit produced by any compiler, StabCert
decides whether they are equal on the specified input subspace.

- **Sound and complete.** No false accepts, no false rejects.
- **Polynomial time.** No dense matrices, no enumeration of basis states.
- **Compiler-agnostic.** Validated against Qiskit SABRE and pytket; the
  compiler's internals are never inspected.
- **Gauge-invariant.** The verdict does not depend on the compiler's ancilla
  or Stinespring conventions.

The decision procedure compares canonical signed code-Choi tableaus. Two
stabilizer channels are equal on the code subspace if and only if their
canonical forms coincide.

Topological conformance is checked separately: every two-qubit gate in the
routed circuit is verified against the coupling map.

### Verified core

The certified path — compiler, verifier, and command line — is a closed
import closure of eleven modules, computed by AST traversal and enforced by
the test suite; the verifier alone reaches eight. No module in that closure
enumerates basis states or constructs dense matrices.

The distribution also ships exploratory and instance-construction code
outside this closure — including a dense stabilizer-group enumeration —
which no verification path can reach. The closure test fails if that
changes.

## Scope

StabCert applies to **stabilizer channels**: Clifford unitaries, stabilizer
ancilla preparation, partial trace, and Pauli corrections that are linear
functions of measurement outcomes.

Out of scope by construction: noise, calibration, real-time decoding, and
timing or scheduling constraints. These are physical and temporal properties
that a stabilizer Choi state does not express.

The current release verifies coherent isometric recovery circuits, which
contain no mid-circuit measurement. Circuits with genuine measurement
feed-forward are not yet covered.

## Install

```bash
pip install stabcert
```

Optional compiler backends:

```bash
pip install 'stabcert[sabre]'    # Qiskit
pip install 'stabcert[pytket]'   # pytket
```

## Usage

Compile a reference recovery artifact from a problem specification:

```bash
stabcert compile problem.json --output artifact.json
```

Verify an untrusted artifact against the problem — this is the part that
does not trust the compiler:

```bash
stabcert verify problem.json artifact.json --policy channel-certified
```

Two policies are available:

- `channel-certified` accepts any synthesis, routing, or Stinespring gauge
  whose canonical form matches the target. Use this for circuits produced by
  third-party compilers.
- `reproducible-route` additionally requires bit-for-bit equality with the
  reference route. Use this for regression testing.

Add `--run-report report.json` to record the verdict and measured resources.

Worked examples ship with the repository as `tests/fixtures/recovery_v1/`,
using the `<case>.problem.json` / `<case>.artifact.json` convention:

```bash
stabcert verify tests/fixtures/recovery_v1/a1.problem.json \
                tests/fixtures/recovery_v1/a1.artifact.json \
                --policy channel-certified
```

## Status

Early release. The verification core is covered by a test suite and an
adversarial campaign (1300 invalid artifacts rejected, 800 valid
representations accepted, no false accepts or rejects). One of those valid
families differs from the reference only outside the code subspace, which is
what distinguishes comparison on that subspace from comparison of the total
channel.

Resource figures reported by the tool are measured, not certified: SWAP
attribution does not participate in any verdict.

## Transparency

This project was developed with AI assistance. The author takes responsibility
for its content, but AI-assisted work can contain errors, omissions, and
questionable implementation choices that internal review may not catch.

Independent scrutiny is therefore welcome, and three places would benefit most:

- **the proof of Theorem 1** — [`docs/paper/stabcert.md`](docs/paper/stabcert.md),
  Section 3.3, in particular the reconstruction of the channel from its
  code-Choi state and the phase-uniqueness step of Lemma 1;
- **the certified import closure** — Section 5.2 of the same document, and the
  invariant that enforces it in
  [`tests/test_certified_import_closure.py`](tests/test_certified_import_closure.py);
- **the traceability of every reported figure to its artifact** — the mapping
  is in [`docs/notes/REVIEW_PASSES.md`](docs/notes/REVIEW_PASSES.md), and the
  artifacts are the tracked files under `results/`.

Contributions that confirm the results and contributions that find errors are
equally useful.

## Development

Test counts quoted in `docs/notes/` are generated, never written by hand.
They live in `TEST_COUNT` spans and are rewritten from the suite's own
output:

```bash
python sync_test_counts.py                     # re-run the suite, update counts
python sync_test_counts.py --no-run --check    # verify only, non-zero on drift
```

The first form refuses to touch documentation unless the suite is green — a
synchroniser that writes a number while tests fail would produce
documentation that is consistent and wrong. Editing a count by hand breaks
the invariant silently.

## License

Apache License 2.0. See [LICENSE](LICENSE).