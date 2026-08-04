from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

from build_verifier_only import build
from hayden_preskill_toy.recovery_exit_codes import RecoveryExitCode


def test_verifier_only_package_contains_no_compiler_and_runs_from_clean_cwd(tmp_path):
    package = tmp_path / "orelia-recovery-verifier.pyz"
    manifest = build(package)
    assert manifest["contains_compiler"] is False
    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
        assert "hayden_preskill_toy/recovery_compile.py" not in names
        assert "schemas/recovery_problem.schema.json" in names
        assert "schemas/recovery_artifact.schema.json" in names
        bundled = json.loads(archive.read("VERIFIER_MANIFEST.json"))
        assert bundled["contains_compiler"] is False

    clean = tmp_path / "clean-machine"
    clean.mkdir()
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    problem = Path("tests/fixtures/recovery_v1/a1.problem.json").resolve()
    artifact = Path("tests/fixtures/recovery_v1/a1.artifact.json").resolve()
    process = subprocess.run(
        [sys.executable, str(package), "verify", str(problem), str(artifact)],
        cwd=clean,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["verified"] is True

    unavailable = subprocess.run(
        [sys.executable, str(package), "compile", str(problem)],
        cwd=clean,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert unavailable.returncode == RecoveryExitCode.CLI_USAGE
    assert "invalid choice" in unavailable.stderr


def test_verifier_only_package_runs_when_resource_module_is_unavailable(tmp_path):
    package = tmp_path / "orelia-recovery-verifier.pyz"
    build(package)
    clean = tmp_path / "windows-like-machine"
    clean.mkdir()
    problem = Path("tests/fixtures/recovery_v1/a1.problem.json").resolve()
    artifact = Path("tests/fixtures/recovery_v1/a1.artifact.json").resolve()
    report = clean / "run-report.json"
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    launcher = """
import builtins
import runpy
import sys

real_import = builtins.__import__

def import_without_resource(name, *args, **kwargs):
    if name == "resource":
        raise ModuleNotFoundError("No module named 'resource'")
    return real_import(name, *args, **kwargs)

builtins.__import__ = import_without_resource
package, problem, artifact, report = sys.argv[1:]
sys.argv = [package, "verify", problem, artifact, "--run-report", report]
runpy.run_path(package, run_name="__main__")
"""
    process = subprocess.run(
        [sys.executable, "-c", launcher, str(package), str(problem), str(artifact), str(report)],
        cwd=clean,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["verified"] is True
    assert json.loads(report.read_text(encoding="utf-8"))["peak_rss_mib"] is None
