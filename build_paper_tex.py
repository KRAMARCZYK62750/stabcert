#!/usr/bin/env python3
"""Generate docs/paper/stabcert.tex from the markdown source.

The markdown is the source and the .tex is generated, never edited by hand.
That keeps both review passes valid: they search the source, and a hand-kept
.tex would drift from it silently.

Two things this script does not do, and says so rather than implying
otherwise.

It does not compile. Typesetting is a separate control, and it is the control
that matters: reading the output found seven classes of defect, compiling it
found four more that reading had passed over -- a superscript that TeX rejects,
an en-dash standing in for a minus, and two overfull boxes. The paper job of
.github/workflows/clean-clone.yml runs it on every push and fails on an error,
an undefined reference, or an overfull box beyond docs/paper/overfull_budget.txt.

As of 6 August 2026 the generated .tex typesets in 15 pages with no error, no
undefined citation or reference, and no overfull box. Nothing here guarantees
the next regeneration does -- that is what the job is for.

The seven results become theorem environments with labels, and prose
references become \\ref. Manual numbering in two places -- the heading and the
prose that names "Theorem 1" -- was two sources of truth for one number. The
generator now checks the source instead of trusting it: if a result is not the
nth of its kind in document order, it refuses to build.

And it guesses, in one place. The source uses backticks for two different
things: mathematics (`tau_X`, `Pi`, `k = |X| - |S_X|`) and literal code
(`channel-certified`, `sync_test_counts.py`). A span becomes math when it
contains mathematical unicode or reads like a formula, and \\texttt otherwise.
Every span where that decision was not obvious is listed in the report, so the
author reviews a short list instead of the whole file.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent

PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb,amsthm}
\usepackage{booktabs}
\usepackage[hidelinks]{hyperref}
\usepackage[margin=1in]{geometry}

\newtheorem{theorem}{Theorem}
\newtheorem{lemma}{Lemma}
\newtheorem{proposition}{Proposition}
\theoremstyle{definition}
\newtheorem{definition}{Definition}
\newtheorem{hypothesis}{Hypothesis}

\title{StabCert: translation validation for stabilizer channels}
\author{Frédéric Kramarczyk\\Independent researcher\\\texttt{fkra62@gmail.com}}
\date{}

\begin{document}
\maketitle
"""

# Mathematical unicode to LaTeX. Applied inside math mode only.
MATH: dict[str, str] = {
    # Multi-character keys first: these are applied in order, so a key whose
    # components appear below it never matches. F2 sat after the subscript and
    # was dead for exactly that reason -- the entry existed, read correctly,
    # and produced nothing, because the subscript had already consumed it.
    "F₂": r"\mathbb{F}_2", "ℂ": r"\mathbb{C}",
    "⁻⁴": "^{-4}", "⁻³": "^{-3}", "⁻²": "^{-2}",
    "Δ": r"\Delta ", "Λ": r"\Lambda ", "Π": r"\Pi ", "β": r"\beta ", "γ": r"\gamma ",
    "δ": r"\delta ", "ρ": r"\rho ", "σ": r"\sigma ", "τ": r"\tau ", "ψ": r"\psi ",
    "→": r"\to ", "↦": r"\mapsto ", "⇐": r"\Leftarrow ", "⇒": r"\Rightarrow ",
    "⟺": r"\iff ", "∈": r"\in ", "∉": r"\notin ", "∏": r"\prod ", "∖": r"\setminus ",
    "∪": r"\cup ", "≈": r"\approx ", "≤": r"\le ", "≥": r"\ge ", "⊆": r"\subseteq ",
    "⊗": r"\otimes ", "⟨": r"\langle ", "⟩": r"\rangle ", "·": r"\cdot ",
    "×": r"\times ", "±": r"\pm ", "−": "-", "†": r"^\dagger", "′": "'",
    "²": "^2", "³": "^3", "ᵢ": "_i", "ⱼ": "_j", "₀": "_0", "₂": "_2",
    "⁻": "^-", "⁴": "^4",
    "⁵": "^5", "Φ": r"\Phi ", "Θ": r"\Theta ", "∎": r"\qed ", "Ē": r"\overline{E}",
    "≠": r"\ne ", "…": r"\dots ", "‑": "-",
}
# Text-mode unicode, outside formulas.
TEXT: dict[str, str] = {
    # U+2212 is a minus, not a dash. Mapped to "--" it set an en-dash, which is
    # how the verdict table came to read --0.400 for a trend of -0.400.
    "−": "$-$",
    "–": "--", "—": "---", "…": r"\dots ", "ł": r"\l{}", "′": "'", "…": r"\dots{}",
    "\u0304": "", "\u0303": "",
}
# Mathematics met outside a span must still enter math mode, or the command
# lands in text mode and the error surfaces somewhere else entirely.
TEXT_MATH = ("⁻³", "×", "≈", "≥", "≤", "²", "³", "⁴", "⁵", "∈", "∉", "⊆", "⊗",
             "→", "↦", "⇐", "⇒", "⟺", "∏", "∖", "∪", "·", "±", "†", "Φ", "Θ",
             "Π", "Λ", "Δ", "σ", "τ", "ρ", "ψ", "β", "γ", "δ", "ᵢ", "ⱼ", "₀",
             "₂", "⟨", "⟩", "∎", "Ē", "≠")
MATH_MARKERS = set("ΔΛΠβγδρστψ→↦⇐⇒⟺∈∉∏∖∪≈≤≥⊆⊗⟨⟩·×±−†′²³ᵢⱼ₀₂⁻")


# Function names, not products of single-letter variables. Left alone, TeX sets
# supp as s.u.p.p in maths italic and spaces it as a product; \operatorname sets
# it upright and spaces it as an operator. This is a closed set of names, which
# is what makes it a rule rather than a list of places to patch.
#
# The boundary is spelled out rather than \b: an underscore is a word character
# to the regex engine, so \bTr\b does not fire in Tr_Ref -- the one occurrence
# that most needed it.
OPERATORS = re.compile(r"(?<![A-Za-z])(supp|sig|Ref|Tr|RREF)(?![A-Za-z])")

# A subscript of two or more letters is a word, not a product of variables, and
# is set upright: N_sys, not N times s times y times s.
SUBSCRIPT_WORD = re.compile(r"_([A-Za-z]{2,})")


def to_math(span: str) -> str:
    out = SUBSCRIPT_WORD.sub(r"_{\\mathrm{\1}}", span)
    out = OPERATORS.sub(r"\\operatorname{\1}", out)
    # An operator reached as a subscript needs its own group, or the subscript
    # takes only the first token of the command.
    out = re.sub(r"_\{\\mathrm\{(supp|sig|Ref|Tr|RREF)\}\}",
                 r"_{\\operatorname{\1}}", out)
    for base, target in (("X̄", r"\bar{X}"), ("Z̄", r"\bar{Z}"), ("Ē", r"\overline{E}"),
                         # \widetilde on the uppercase Greek: \tilde sets a
                         # narrow accent that does not span \Lambda.
                         ("Λ̃", r"\widetilde{\Lambda}"), ("σ̃", r"\tilde{\sigma}")):
        out = out.replace(base, target)
    out = out.replace("\u0304", "").replace("\u0303", "")
    for source, target in MATH.items():
        out = out.replace(source, target)
    # A bar closed by a ket bracket opens a Dirac ket; it has no partner and
    # must not enter the count below. Counting it is what made |0> and |X| an
    # odd three bars, sending all of them to \mid -- including the two that
    # genuinely paired.
    out = re.sub(r"\|([^|]*?)\\rangle", r"\\lvert \1\\rangle", out)
    if out.count("|") % 2 == 0:
        out = re.sub(r"\|([^|]*)\|", r"\\lvert \1\\rvert", out)
    else:
        out = out.replace("|", r"\mid ")
    # No regex here. An earlier attempt inserted a space after "a control
    # sequence followed by a letter", and backtracked: \lvert failed the
    # lookahead on the following space, so the engine retried at \lver and
    # split a valid command. Each substitution carries its own trailing space.
    return f"${out}$"


def to_texttt(span: str) -> str:
    out = span
    for source, target in TEXT.items():
        out = out.replace(source, target)
    return r"\texttt{" + out.replace("_", r"\_").replace("^", r"\^{}") + "}"


# The source uses backticks for mathematics far more often than for code, so
# the default is mathematics and code is recognised by explicit pattern. The
# reverse default sent (x|z), 2n and A = 1 to \texttt on the first attempt.
CODE_PATTERNS = (
    r"\.(py|md|json|csv|yml)$",              # file names
    r"/.*\.|/$",                             # paths
    r"^--",                                  # command-line flags
    r"^[a-z]+(-[a-z]+)+$",                   # policy names: channel-certified
    r"^[a-z][a-z0-9]*_[a-z0-9_]+$",          # snake_case identifiers
    r"^[A-Z][a-zA-Z]{3,}$",                  # class names: LexiRouteRoutingMethod
    r"^orelia\.",                            # campaign format identifiers
)
CODE_LITERALS = {"reference", "chain", "grid_2d", "arch", "TEST_COUNT",
                 "NumPy", "Stim", "SABRE", "pytket", "Qiskit"}


def is_code(span: str) -> bool:
    if set(span) & MATH_MARKERS:
        return False
    if span in CODE_LITERALS:
        return True
    return any(re.search(pattern, span) for pattern in CODE_PATTERNS)


def convert_spans(line: str, judged: list[dict[str, str]]) -> str:
    def one(match: re.Match[str]) -> str:
        span = match.group(1)
        code = is_code(span)
        # Flag spans that neither carry mathematical unicode nor match a code
        # pattern: the classifier defaulted, and the default deserves a look.
        if not code and not (set(span) & MATH_MARKERS):
            judged.append({"span": span, "rendered": "math (by default)"})
        return to_texttt(span) if code else to_math(span)

    return re.sub(r"`([^`\n]+)`", one, line)


def cross_references(text: str) -> str:
    for kind, prefix in LABEL.items():
        text = re.sub(rf"(?<!\\begin{{)\b{kind} (\d+)\b",
                      lambda m, k=kind, p=prefix: f"{k}~\\ref{{{p}:{m.group(1)}}}", text)
    return text


def escape_text(line: str) -> str:
    for source, target in TEXT.items():
        line = line.replace(source, target)
    for symbol in TEXT_MATH:
        if symbol in line:
            line = line.replace(symbol, "$" + MATH.get(symbol, symbol) + "$")
    line = re.sub(r"(?<!\\)([&%#_])", r"\\\1", line)
    return line


def render(line: str, judged: list[dict[str, str]]) -> str:
    """Convert spans, escape the rest, and keep the escaping off the spans.

    escape_text used to run over output that convert_spans had already turned
    into mathematics, which is how O(n^4) became $O(n$^4$)$ -- math mode opened
    and closed inside one expression. Converted spans are now held behind
    placeholders while the surrounding text is escaped.
    """
    held: list[str] = []

    def hold(match):
        held.append(convert_spans(match.group(0), judged))
        return "@@S" + str(len(held) - 1) + "@@"

    masked = re.sub(r"`[^`\n]+`", hold, line)
    escaped = escape_text(masked)
    return re.sub(r"@@S(\d+)@@", lambda m: held[int(m.group(1))], escaped)


ENV = {"Theorem": "theorem", "Lemma": "lemma", "Proposition": "proposition",
       "Definition": "definition", "Hypothesis": "hypothesis"}
LABEL = {"Theorem": "thm", "Lemma": "lem", "Proposition": "prop",
         "Definition": "def", "Hypothesis": "hyp"}
RESULT = re.compile(r"^\*\*(Theorem|Lemma|Proposition|Definition|Hypothesis) (\d+)"
                    r"(?: \(([^)]+)\))?\.\*\*\s*(.*)$")

# Lines opening structure rather than prose. \textbf and \emph are deliberately
# absent: a paragraph may open with one -- "\textbf{Reproducibility.} The routed
# artifacts..." is the paragraph that overflowed by 42pt -- and treating it as
# structure is what hid that paragraph from the first version of this rule.
STRUCTURE = re.compile(r"^\\(begin|end|section|subsection|item|bibliograph"
                       r"|maketitle|title|author|date|small|toprule|midrule|bottomrule)")

# TeX will not hyphenate inside \texttt, so a long identifier is one unbreakable
# box. Past this width it can no longer be placed on a justified line without
# pushing past the margin, and the compiler reports an overfull hbox. Measured:
# 4 of 104 paragraphs, among them the two that overflowed. This loosens
# interword spacing in those paragraphs and nowhere else.
UNBREAKABLE = 18


def loosen(body: str) -> str:
    """Wrap top-level prose paragraphs carrying long \\texttt spans in sloppypar.

    Scope, stated exactly: this reduces overfull boxes, it does not eliminate
    them. A single \\texttt wider than the column still overflows, and material
    inside an environment -- table cells above all -- is never touched here.
    The guarantee lives in the CI overfull count, not in this function.
    """
    out: list[str] = []
    depth = 0
    paragraph: list[str] = []

    def flush() -> None:
        if not paragraph:
            return
        text = "\n".join(paragraph)
        spans = re.findall(r"\\texttt\{([^{}]*)\}", text)
        if any(len(s) >= UNBREAKABLE for s in spans):
            out.extend([r"\begin{sloppypar}", text, r"\end{sloppypar}"])
        else:
            out.append(text)
        paragraph.clear()

    for line in body.split("\n"):
        stripped = line.strip()
        if not stripped:
            flush()
            out.append(line)
        elif depth == 0 and not STRUCTURE.match(stripped):
            paragraph.append(line)
        else:
            flush()
            out.append(line)
        # After the test: a line carrying \begin belongs to what it opens, and
        # judging it by the depth it leaves behind would misfile the opener.
        #
        # document is excluded, and not as a nicety. This runs before
        # \end{document} is appended, so counting it leaves the whole body at
        # depth 1 from the preamble onward and the rule matches nothing --
        # silently, with a clean build and an empty result.
        depth += len(re.findall(r"\\begin\{(?!document\})", stripped))
        depth -= len(re.findall(r"\\end\{(?!document\})", stripped))
    flush()
    return _loosen_lists("\n".join(out))


def _loosen_lists(text: str) -> str:
    """Same policy inside itemize, where the paragraph rule cannot reach.

    A list item is a paragraph, but it sits at depth 1, so the walk above skips
    it -- and a list indents, leaving less room than the prose that qualified.
    Measured: the 4.6 items overflowed by 1.4pt after the paragraph rule had
    cleared the other four boxes. \\sloppy is scoped by the environment's own
    group, so it stops at \\end{itemize}.
    """
    def fix(match: re.Match) -> str:
        block = match.group(0)
        spans = re.findall(r"\\texttt\{([^{}]*)\}", block)
        if any(len(s) >= UNBREAKABLE for s in spans):
            return block.replace(r"\begin{itemize}", "\\begin{itemize}\n\\sloppy", 1)
        return block

    return re.sub(r"\\begin\{itemize\}.*?\\end\{itemize\}", fix, text, flags=re.S)


def display(fence: str, block: list[str]) -> list[str]:
    """Render a fenced block standing in display position.

    A ```latex fence is passed through untouched. The alternative -- deriving
    the typeset form from hand-written pseudo-mathematics -- cannot be done by
    rule: nothing turns "(a) / (b)" into \\frac{a}{b} that stays safe on the
    other blocks, and nothing turns "for all rho with" into \\forall at all.
    Those are editorial choices, so the source states them rather than the
    generator guessing them.

    The two older paths are kept for blocks that carry no such choice.
    """
    rows = [row for row in block if row.strip()]
    if fence.strip() == "```latex":
        return [r"\begin{equation*}"] + rows + [r"\end{equation*}"]
    if any(set(row) & MATH_MARKERS for row in block):
        return ([r"\begin{equation*}\begin{split}"]
                + [to_math(row)[1:-1] + r" \\" for row in rows]
                + [r"\end{split}\end{equation*}"])
    return [r"\begin{verbatim}"] + block + [r"\end{verbatim}"]


def convert(markdown: str) -> tuple[str, list[dict[str, str]]]:
    judged: list[dict[str, str]] = []
    out: list[str] = [PREAMBLE]
    lines = markdown.split("\n")
    index = 0
    in_abstract = False
    seen: dict[str, int] = {}
    while index < len(lines):
        line = lines[index]

        result = RESULT.match(line)
        if result:
            kind, number, name, rest = result.groups()
            seen[kind] = seen.get(kind, 0) + 1
            if int(number) != seen[kind]:
                raise SystemExit(
                    f"{kind} {number} is the {seen[kind]} of its kind in the source: "
                    "the manual numbering and the document order disagree, and the "
                    "prose refers to these numbers by hand"
                )
            head = r"\begin{" + ENV[kind] + "}"
            if name:
                head += "[" + escape_text(name) + "]"
            out.append(head + r"\label{" + LABEL[kind] + ":" + number + "}")
            if rest:
                out.append(render(rest, judged))
            index += 1
            while index < len(lines) and lines[index].strip():
                out.append(render(lines[index], judged))
                index += 1
            # A display block immediately after belongs to the statement.
            if index + 1 < len(lines) and lines[index + 1].startswith("```"):
                fence = lines[index + 1]
                index += 2
                block = []
                while index < len(lines) and not lines[index].startswith("```"):
                    block.append(lines[index])
                    index += 1
                out += display(fence, block)
                index += 1
            out.append(r"\end{" + ENV[kind] + "}")
            continue

        if line.startswith("*Proof.*"):
            out.append(r"\begin{proof}")
            out.append(render(line[len("*Proof.*"):].strip(), judged))
            index += 1
            while index < len(lines) and "\u220e" not in lines[index]:
                if lines[index].startswith("```"):
                    fence = lines[index]
                    index += 1
                    block = []
                    while index < len(lines) and not lines[index].startswith("```"):
                        block.append(lines[index])
                        index += 1
                    out += display(fence, block)
                    index += 1
                    continue
                out.append(render(lines[index], judged))
                index += 1
            if index < len(lines):
                out.append(render(lines[index].replace("\u220e", "").rstrip(), judged))
                index += 1
            out.append(r"\end{proof}")
            continue

        if line.startswith("> "):  # internal assembly note, not part of the paper
            index += 1
            continue
        if line.strip() == "---":
            index += 1
            continue
        if line.startswith("```"):
            fence = line
            index += 1
            block = []
            while index < len(lines) and not lines[index].startswith("```"):
                block.append(lines[index])
                index += 1
            index += 1
            out += display(fence, block)
            continue
        if line.startswith("| "):
            block = []
            while index < len(lines) and lines[index].startswith("|"):
                block.append(lines[index])
                index += 1
            out.append(table(block, judged))
            continue
        if line.startswith("# "):
            index += 1
            continue  # title is in the preamble
        if line.startswith("## "):
            name = line[3:].strip()
            if name == "Abstract":
                out.append(r"\begin{abstract}")
                in_abstract = True
            else:
                if in_abstract:
                    out.append(r"\end{abstract}")
                    in_abstract = False
                out.append(r"\section{" + escape_text(re.sub(r"^\d+\.\s*", "", name)) + "}")
            index += 1
            continue
        if line.startswith("### "):
            name = re.sub(r"^\d+\.\d+\s*", "", line[4:].strip())
            out.append(r"\subsection{" + escape_text(name) + "}")
            index += 1
            continue
        if line.startswith("- "):
            out.append(r"\begin{itemize}")
            while index < len(lines) and (lines[index].startswith("- ") or lines[index].startswith("  ")):
                if lines[index].startswith("- "):
                    out.append(r"\item " + render(lines[index][2:], judged))
                else:
                    out.append(render(lines[index].strip(), judged))
                index += 1
            out.append(r"\end{itemize}")
            continue
        out.append(render(line, judged))
        index += 1

    if in_abstract:
        out.append(r"\end{abstract}")
    body = "\n".join(out)
    # Emphasis often spans a line break in the source, which a line-oriented
    # substitution cannot see. Applied here, over the assembled body, with
    # verbatim blocks held out.
    chunks = re.split(r"(\\begin\{verbatim\}.*?\\end\{verbatim\})", body, flags=re.S)
    for position, chunk in enumerate(chunks):
        if not chunk.startswith(r"\begin{verbatim}"):
            chunk = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", chunk, flags=re.S)
            # The opening star must not follow a word character, or equation*
            # and its siblings lose theirs -- which is how \begin{equation*}
            # became \begin{equation\emph{} on the first attempt.
            chunk = re.sub(r"(?<![\w*])\*(?!\*)(.+?)\*(?![\w*])",
                           r"\\emph{\1}", chunk, flags=re.S)
            chunks[position] = chunk
    out = [cross_references(loosen("".join(chunks)))]
    out.append(r"\bibliographystyle{plain}")
    out.append(r"\bibliography{stabcert}")
    out.append(r"\end{document}")
    return "\n".join(out), judged


def table(block: list[str], judged: list[dict[str, str]]) -> str:
    rows = [r for r in block if not re.fullmatch(r"\|[\s|:-]+\|", r.strip())]
    cells = []
    for row in rows:
        # A span may contain vertical bars -- `|M|`, `k = |X| - |S_X|`. Splitting
        # the row first cuts them into pieces that are no longer spans.
        held: list[str] = []

        def hold(match, held=held):
            held.append(match.group(0))
            return "@@C" + str(len(held) - 1) + "@@"

        masked = re.sub(r"`[^`\n]+`", hold, row)
        parts = [c.strip() for c in masked.strip().strip("|").split("|")]
        cells.append([re.sub(r"@@C(\d+)@@", lambda m, h=held: h[int(m.group(1))], c)
                      for c in parts])
    width = max(len(r) for r in cells)
    spec = "l" * width
    lines = [r"\begin{center}"]
    # Five columns is where the measured overflow starts: the campaign table has
    # five and ran 33pt wide at 11pt, the verdict table eight and ran 2.3pt wide.
    # \small is 9.1% at this size, against the 6.6% the wider of the two needed.
    if width >= 5:
        lines.append(r"\small")
    lines += [r"\begin{tabular}{" + spec + "}", r"\toprule"]
    for position, row in enumerate(cells):
        rendered = " & ".join(render(c, judged) for c in row)
        lines.append(rendered + r" \\")
        if position == 0:
            lines.append(r"\midrule")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{center}"]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(ROOT / "docs" / "paper" / "stabcert.md"))
    parser.add_argument("--output", default=str(ROOT / "docs" / "paper" / "stabcert.tex"))
    arguments = parser.parse_args()
    latex, judged = convert(Path(arguments.source).read_text(encoding="utf-8"))
    Path(arguments.output).write_text(
        "% Generated by build_paper_tex.py from stabcert.md. Do not edit by hand.\n"
        "% Typeset in CI by the paper job of .github/workflows/clean-clone.yml,\n"
        "% which fails on an overfull box beyond docs/paper/overfull_budget.txt.\n" + latex + "\n",
        encoding="utf-8",
    )
    unique = {j["span"]: j["rendered"] for j in judged}
    print(json.dumps({
        "output": arguments.output,
        "compiled": False,
        "spans_needing_review": [{"span": s, "rendered": r} for s, r in sorted(unique.items())],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
