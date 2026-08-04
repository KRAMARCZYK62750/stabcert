"""The certified path must stay inside its declared module closure.

``recovery_verify`` rebuilds the Petz target by GF(2) elimination only.  The
``parametric_*`` lineage still contains the pre-migration constructions, in
particular the 2**n stabilizer-group enumeration of
``parametric_petz.signed_stabilizers``.  These tests turn the closure audit
into an invariant: reimporting that lineage from the verifier, the compiler or
the verifier-only CLI fails here instead of silently changing what "polynomial"
covers.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "hayden_preskill_toy"
ENTRY_POINTS = ("recovery_verify", "recovery_verifier_cli", "recovery_compile")
CERTIFIED_CLOSURE = {
    "gf2",
    "recovery_artifact",
    "recovery_compile",
    "recovery_exit_codes",
    "recovery_problem",
    "recovery_routing",
    "recovery_run_report",
    "recovery_serialization",
    "recovery_stabilizer",
    "recovery_verify",
    "recovery_verifier_cli",
}


def _direct_imports(module: str) -> set[str]:
    tree = ast.parse((PACKAGE / f"{module}.py").read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
            found.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("hayden_preskill_toy."):
                    found.add(alias.name.split(".")[1])
    return found


def _closure(entry: str) -> set[str]:
    seen: set[str] = set()
    pending = [entry]
    while pending:
        module = pending.pop()
        if module in seen or not (PACKAGE / f"{module}.py").exists():
            continue
        seen.add(module)
        pending.extend(_direct_imports(module))
    return seen


@pytest.mark.parametrize("entry", ENTRY_POINTS)
def test_certified_closure_excludes_parametric_lineage(entry: str) -> None:
    reachable = _closure(entry)
    assert not {name for name in reachable if name.startswith("parametric_")}


@pytest.mark.parametrize("entry", ENTRY_POINTS)
def test_certified_closure_is_declared(entry: str) -> None:
    assert _closure(entry) <= CERTIFIED_CLOSURE


def test_closure_declaration_has_no_unreachable_module() -> None:
    reachable = set().union(*(_closure(entry) for entry in ENTRY_POINTS))
    assert reachable == CERTIFIED_CLOSURE


def test_enumerating_lineage_is_still_outside_the_closure() -> None:
    """Guard the audit itself: the 2**n enumeration must remain findable."""
    source = (PACKAGE / "parametric_petz.py").read_text(encoding="utf-8")
    assert "for mask in range(1 << len(generators))" in source
    assert "parametric_petz" not in set().union(
        *(_closure(entry) for entry in ENTRY_POINTS)
    )
