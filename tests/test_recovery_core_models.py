from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from hayden_preskill_toy.recovery_serialization import (
    artifact_document_hash,
    canonical_json_bytes,
    problem_document_hash,
    read_artifact,
    read_problem,
    semantic_problem_hash,
)


FIXTURES = Path("tests/fixtures/recovery_v1")


def test_recovery_json_schemas_are_versioned_draft_2020_12_documents():
    problem = json.loads(Path("schemas/recovery_problem.schema.json").read_text())
    artifact = json.loads(Path("schemas/recovery_artifact.schema.json").read_text())
    run_report = json.loads(Path("schemas/recovery_run_report.schema.json").read_text())
    assert problem["$schema"].endswith("draft/2020-12/schema")
    assert artifact["$schema"].endswith("draft/2020-12/schema")
    assert run_report["$schema"].endswith("draft/2020-12/schema")
    assert problem["properties"]["format_version"]["const"] == "orelia.recovery-problem/v1"
    assert artifact["properties"]["format_version"]["const"] == "orelia.recovery-artifact/v1"
    assert run_report["properties"]["format_version"]["const"] == "orelia.recovery-run-report/v2"
    assert "verification_policy" in run_report["required"]


def test_fixture_json_round_trips_and_hashes_are_stable():
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    for row in manifest:
        problem = read_problem(FIXTURES / row["problem_file"])
        artifact = read_artifact(FIXTURES / row["artifact_file"])
        assert semantic_problem_hash(problem) == row["semantic_problem_hash"]
        assert problem_document_hash(problem) == row["problem_document_hash"]
        assert artifact_document_hash(artifact) == row["artifact_document_hash"]


def test_semantic_and_document_hashes_have_distinct_domains():
    problem = read_problem(FIXTURES / "a1.problem.json")
    changed = replace(problem, metadata=(*problem.metadata, ("z_non_normative", "value")))
    assert semantic_problem_hash(changed) == semantic_problem_hash(problem)
    assert problem_document_hash(changed) != problem_document_hash(problem)
    assert semantic_problem_hash(problem) != problem_document_hash(problem)


def test_canonical_json_rejects_non_finite_float():
    with pytest.raises(ValueError):
        canonical_json_bytes({"invalid": float("nan")})


def test_generic_core_has_no_experiment_or_csv_dependency():
    modules = (
        "recovery_problem.py",
        "recovery_artifact.py",
        "recovery_serialization.py",
        "recovery_stabilizer.py",
        "recovery_routing.py",
        "recovery_compile.py",
        "recovery_verify.py",
    )
    forbidden = (
        "from .layout import",
        "from .parametric_",
        "from .support_code import",
        "recovery_hayden_preskill_adapter",
        "import csv",
        "B_register",
        "E_register",
        "D_register",
    )
    for name in modules:
        source = (Path("hayden_preskill_toy") / name).read_text()
        for token in forbidden:
            assert token not in source, (name, token)
    verifier = Path("hayden_preskill_toy/recovery_verify.py").read_text()
    assert "from .recovery_compile import" not in verifier
    assert "import hayden_preskill_toy.recovery_compile" not in verifier
