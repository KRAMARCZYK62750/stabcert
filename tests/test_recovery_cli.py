from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

from hayden_preskill_toy.recovery_artifact import MetricEntry
from hayden_preskill_toy.recovery_exit_codes import RecoveryExitCode
from hayden_preskill_toy.recovery_serialization import (
    artifact_document_hash,
    read_artifact,
    read_run_report,
    write_artifact,
)


PROBLEM = "tests/fixtures/recovery_v1/a1.problem.json"
ARTIFACT = "tests/fixtures/recovery_v1/a1.artifact.json"


def _cli(*arguments: str, cwd: Path | None = None):
    return subprocess.run(
        [sys.executable, "-m", "hayden_preskill_toy.recovery_cli", *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_compile_is_byte_deterministic_and_run_report_is_separate(tmp_path):
    first = tmp_path / "first.artifact.json"
    second = tmp_path / "second.artifact.json"
    report_path = tmp_path / "compile.run-report.json"
    one = _cli("compile", PROBLEM, "--output", str(first), "--run-report", str(report_path))
    two = _cli("compile", PROBLEM, "--output", str(second))
    assert one.returncode == two.returncode == RecoveryExitCode.SUCCESS
    assert first.read_bytes() == second.read_bytes()
    parsed = json.loads(first.read_text())
    assert "tool_versions" not in parsed
    assert all(item["name"] != "compile_seconds" for item in parsed["metrics"])
    report = read_run_report(report_path)
    assert report.command == "compile" and report.status == "success"
    assert report.wall_seconds and report.peak_rss_mib
    assert report.environment.python_version
    assert report.artifact_document_hash == artifact_document_hash(read_artifact(first))


def test_verify_and_benchmark_commands_have_stable_success_codes(tmp_path):
    verify_report = tmp_path / "verify.run-report.json"
    verified = _cli("verify", PROBLEM, ARTIFACT, "--run-report", str(verify_report))
    assert verified.returncode == RecoveryExitCode.SUCCESS
    payload = json.loads(verified.stdout)
    assert payload["verified"] is True and payload["status"] == "success"
    assert read_run_report(verify_report).command == "verify"

    benchmark_report = tmp_path / "benchmark.run-report.json"
    benchmarked = _cli(
        "benchmark", PROBLEM, "--iterations", "2", "--output", str(benchmark_report)
    )
    assert benchmarked.returncode == RecoveryExitCode.SUCCESS
    report = read_run_report(benchmark_report)
    assert report.command == "benchmark" and report.iterations == 2
    assert report.status == "success"


def test_cli_distinguishes_unsupported_input_and_rejected_artifact(tmp_path):
    invalid_problem = tmp_path / "unsupported.problem.json"
    value = json.loads(Path(PROBLEM).read_text())
    value["format_version"] = "orelia.recovery-problem/v999"
    invalid_problem.write_text(json.dumps(value))
    invalid = _cli("compile", str(invalid_problem), "--output", str(tmp_path / "unused.json"))
    assert invalid.returncode == RecoveryExitCode.UNSUPPORTED_VERSION

    artifact = read_artifact(ARTIFACT)
    metrics = tuple(
        MetricEntry(item.name, "0" if item.name == "circuit_entanglement_fidelity" else item.value, item.unit)
        for item in artifact.metrics
    )
    tampered = replace(
        artifact,
        metrics=metrics,
        certificate=replace(artifact.certificate, compiler_declared_valid=True),
    )
    tampered_path = tmp_path / "tampered.artifact.json"
    write_artifact(tampered_path, tampered)
    rejected = _cli("verify", PROBLEM, str(tampered_path))
    assert rejected.returncode == RecoveryExitCode.VERIFICATION_REJECTED
    assert json.loads(rejected.stdout)["verified"] is False

