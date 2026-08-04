from __future__ import annotations

import subprocess
import sys


def test_fixture_compiles_then_verifies_in_separate_hermetic_processes(tmp_path):
    compiled_path = tmp_path / "compiled.artifact.json"
    compile_script = r'''
import builtins
import sys

blocked = (
    "hayden_preskill_toy.layout",
    "hayden_preskill_toy.parametric_",
    "hayden_preskill_toy.channels",
    "hayden_preskill_toy.experiment",
    "hayden_preskill_toy.recovery_hayden_preskill_adapter",
)
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if any(name == prefix or name.startswith(prefix) for prefix in blocked):
        raise RuntimeError("forbidden experiment import: " + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded

from hayden_preskill_toy.recovery_compile import compile_recovery
from hayden_preskill_toy.recovery_serialization import read_problem, write_artifact

problem = read_problem(sys.argv[1])
write_artifact(sys.argv[2], compile_recovery(problem))
print("compiled")
'''
    compiled = subprocess.run(
        [
            sys.executable,
            "-c",
            compile_script,
            "tests/fixtures/recovery_v1/a1.problem.json",
            str(compiled_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert compiled.stdout.strip() == "compiled"

    verify_script = r'''
import builtins
import sys

blocked = (
    "hayden_preskill_toy.layout",
    "hayden_preskill_toy.parametric_",
    "hayden_preskill_toy.channels",
    "hayden_preskill_toy.experiment",
    "hayden_preskill_toy.recovery_hayden_preskill_adapter",
    "hayden_preskill_toy.recovery_compile",
)
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if any(name == prefix or name.startswith(prefix) for prefix in blocked):
        raise RuntimeError("forbidden experiment/compiler import: " + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded

from hayden_preskill_toy.recovery_serialization import read_artifact, read_problem
from hayden_preskill_toy.recovery_verify import verify_recovery

problem = read_problem(sys.argv[1])
artifact = read_artifact(sys.argv[2])
report = verify_recovery(problem, artifact)
if not report.verified:
    raise SystemExit(2)
print("verified")
'''
    verified = subprocess.run(
        [
            sys.executable,
            "-c",
            verify_script,
            "tests/fixtures/recovery_v1/a1.problem.json",
            str(compiled_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert verified.stdout.strip() == "verified"
