#!/usr/bin/env python3
"""Mechanical checks of review pass 1 over the paper.

Pass 1 catches form: a symbol used for two objects, one object under two names,
a definition repeated across sections, a cross-reference that does not resolve.
It does **not** validate a figure, and must not be asked to — it reads figures
as consistent because they are consistent with each other. That is pass 2's
job, and pass 2 recomputes from artifacts.

Every check runs on the **flattened** text. Markdown wraps sentences across
lines, so a line-oriented search reports a phrase as absent when it is present
merely because a newline falls inside it. That false negative was produced
twice by hand while drafting; flattening here closes the class rather than
fixing the two occurrences.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

DEFAULT_PAPER = "docs/paper/stabcert.md"

# One letter, one object. Each entry lists patterns that would indicate the
# symbol being used for a second, unrelated object.
SYMBOL_USES: dict[str, list[tuple[str, str]]] = {
    "d": [
        ("dimension 2^|M|", r"d = 2\^\{\|M\|\}"),
        ("code distance", r"`d²` data qubits|distance-\d code sits"),
        ("asymptotic degree", r"e\(n\) = d \+ K/n"),
    ],
    "S": [
        ("source stabilizer group", r"`S` \| stabilizer group"),
        ("elimination count", r"[^_]S\(n\) = 28n²"),
    ],
    "b": [
        ("finite-size bias", r"b\(n\) = \(232n"),
        ("degree at fixed density", r"b = 6\.313"),
    ],
}

# Names that must not appear: one object under a second name.
FORBIDDEN_NAMES = ("code-Choi tableau", "canonical signed code-Choi")

# Claims whose absence would be a defect, checked on flattened text.
REQUIRED_PHRASES = {
    "abstract: support is specification-determined":
        "relative to a support determined by the specification",
    "intro: the state is mixed": "a mixed stabilizer state",
    "intro: theorem separated from campaign":
        "no finite corpus could establish the former",
    "4.3: admits": "The class **admits** a symbolic treatment",
    "4.3: contains no": "**contains no syndrome handling at all**",
    "4.3: claim nothing": "**claim nothing** about that path",
    "4.4: depth and gate counts enter the verdict": "enter the verdict",
    "6.3: instruction covers both tables": "Both tables are to be read across",
    "7.4: trend column present": "| trend |",
    "8: non-execution disclosed": "We have not executed any of the tools",
}

# Phrases that must have been removed.
FORBIDDEN_PHRASES = {
    "4.4: superseded cautious wording": "reported, not certified",
}


def flatten(text: str) -> str:
    return " ".join(text.split())


def sections(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for block in re.split(r"\n(?=## )", text):
        match = re.match(r"## ([^\n]+)", block)
        if match:
            found[match.group(1)] = block
    return found


def check(paper: Path) -> dict[str, object]:
    raw = paper.read_text(encoding="utf-8")
    flat = flatten(raw)
    blocks = sections(raw)
    findings: list[str] = []

    for symbol, uses in SYMBOL_USES.items():
        hit = [name for name, pattern in uses if re.search(pattern, flat)]
        if len(hit) > 1:
            findings.append(f"symbol `{symbol}` used for {len(hit)} objects: {', '.join(hit)}")

    for name in FORBIDDEN_NAMES:
        if name in flat:
            findings.append(f"second name in use: {name!r}")

    for label, phrase in REQUIRED_PHRASES.items():
        if phrase not in flat:
            findings.append(f"missing: {label}")

    for label, phrase in FORBIDDEN_PHRASES.items():
        if phrase in flat:
            findings.append(f"still present: {label}")

    # A long sentence appearing in two sections is a duplication.
    seen: dict[str, list[str]] = {}
    for name, block in blocks.items():
        for sentence in re.split(r"(?<=\.)\s+", flatten(block)):
            if len(sentence) > 70:
                seen.setdefault(sentence.strip(), []).append(name)
    for sentence, where in seen.items():
        if len(set(where)) > 1:
            findings.append(f"sentence repeated across {sorted(set(where))}: {sentence[:70]}...")

    # Every "Section N" must resolve to a heading that exists.
    for reference in sorted(set(re.findall(r"Sections? (\d+(?:\.\d+)?)", flat))):
        anchor = f"### {reference}" if "." in reference else f"## {reference}."
        if anchor not in raw:
            findings.append(f"cross-reference to Section {reference} does not resolve")

    return {"paper": str(paper), "findings": findings, "clean": not findings}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper", default=DEFAULT_PAPER)
    arguments = parser.parse_args()
    result = check(Path(arguments.paper))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
