#!/usr/bin/env python3
"""Regenerate the automatic-suite test counts quoted in the documentation.

What this guarantees, exactly: that the ``TEST_COUNT`` spans in the documents
listed below match the suite **as it runs in this working directory**, and
that they are never written by hand.

What it does not guarantee, and cannot: anything about the suite a reader
gets. It does not know what is tracked by git. On 4 August 2026 the published
count of 124 was true here and false everywhere else -- 20 tests failed from a
clean clone because artifacts they read were untracked, and this script had
faithfully synchronised a number reachable only locally. It was not wrong; it
was asked for less than was assumed of it.

The clone-and-run guarantee belongs to CI (``.github/workflows/clean-clone.yml``),
which checks out only tracked content. That job and this script are
independent controls: CI does not make this promise wider, it adds another
one. Keep both.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import re
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
COUNT_PATH = PROJECT_ROOT / "results" / "test_suite_count.json"
DOCUMENTS = (
    "docs/notes/CHANNEL_CERTIFIED_IMPLEMENTATION.md",
    "docs/notes/FICHE_CHANNEL_CERTIFIED_ORELIA.md",
    "docs/notes/NOTE_CERTIFICATION_ROUTEURS_TIERS.md",
    "docs/notes/NOTE_JALON_SABRE_ORELIA.md",
)
SPAN = re.compile(
    r"(?P<open><!-- TEST_COUNT:BEGIN fmt=\"(?P<fmt>[^\"]*)\" -->)"
    r"(?P<body>.*?)"
    r"(?P<close><!-- TEST_COUNT:END -->)",
    re.DOTALL,
)
OUTCOME = re.compile(r"(?P<count>\d+) (?P<outcome>passed|failed|error|errors|xfailed|xpassed|skipped)")


def run_suite(python: str) -> str:
    command = [python, "-m", "pytest", "-q"]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout + completed.stderr


def parse_outcomes(report: str) -> dict[str, int]:
    lines = [line for line in report.splitlines() if OUTCOME.search(line)]
    if not lines:
        raise SystemExit("no pytest summary line found in the report")
    outcomes: dict[str, int] = {}
    for match in OUTCOME.finditer(lines[-1]):
        outcome = "error" if match.group("outcome") == "errors" else match.group("outcome")
        outcomes[outcome] = int(match.group("count"))
    return outcomes


def record(report: str, python: str) -> dict[str, object]:
    outcomes = parse_outcomes(report)
    passed = outcomes.get("passed", 0)
    unsuccessful = outcomes.get("failed", 0) + outcomes.get("error", 0)
    if unsuccessful:
        raise SystemExit(f"suite is not green ({outcomes}); documentation left untouched")
    if not passed:
        raise SystemExit(f"no passing test reported ({outcomes})")
    return {
        "format_version": "orelia.test-suite-count/v1",
        "command": f"{python} -m pytest -q",
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "outcomes": dict(sorted(outcomes.items())),
        "passed": passed,
    }


def render(document: str, passed: int) -> tuple[str, list[str]]:
    stale: list[str] = []

    def substitute(match: re.Match[str]) -> str:
        body = match.group("fmt").format(passed=passed)
        if body != match.group("body"):
            stale.append(match.group("body"))
        return match.group("open") + body + match.group("close")

    return SPAN.sub(substitute, document), stale


def synchronise(passed: int, check: bool) -> int:
    divergent = 0
    for name in DOCUMENTS:
        path = PROJECT_ROOT / name
        original = path.read_text(encoding="utf-8")
        if not SPAN.search(original):
            raise SystemExit(f"{name} carries no TEST_COUNT span")
        updated, stale = render(original, passed)
        if not stale:
            continue
        divergent += len(stale)
        for body in stale:
            print(f"{name}: {body!r} -> {passed} passants")
        if not check:
            path.write_text(updated, encoding="utf-8")
    return divergent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--report", help="reuse an existing pytest -q output instead of running the suite")
    parser.add_argument("--no-run", action="store_true", help="reuse the recorded count without running the suite")
    parser.add_argument("--check", action="store_true", help="report divergences without rewriting the documents")
    arguments = parser.parse_args()

    if arguments.no_run:
        if arguments.report:
            raise SystemExit("--no-run and --report are mutually exclusive")
        counted = json.loads(COUNT_PATH.read_text(encoding="utf-8"))
    else:
        report = (
            Path(arguments.report).read_text(encoding="utf-8")
            if arguments.report
            else run_suite(arguments.python)
        )
        counted = record(report, arguments.python)
        if not arguments.check:
            COUNT_PATH.parent.mkdir(parents=True, exist_ok=True)
            COUNT_PATH.write_text(
                json.dumps(counted, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    divergent = synchronise(int(counted["passed"]), arguments.check)
    print(json.dumps({**counted, "divergent_spans": divergent}, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if (arguments.check and divergent) else 0


if __name__ == "__main__":
    raise SystemExit(main())
