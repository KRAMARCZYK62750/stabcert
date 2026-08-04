"""Local command line for deterministic recovery artifacts and verification."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import sys
import time

try:
    import resource as _resource
except ImportError:  # The resource module is not available on Windows.
    _resource = None

import numpy as np
import stim

from .recovery_exit_codes import RecoveryExitCode
from .recovery_run_report import (
    CORE_VERSION,
    FORMAT_VERSION as RUN_REPORT_FORMAT_VERSION,
    RecoveryRunReport,
    RuntimeEnvironment,
)
from .recovery_serialization import (
    artifact_document_hash,
    canonical_json_bytes,
    problem_document_hash,
    read_artifact,
    read_problem,
    semantic_problem_hash,
    write_artifact,
    write_run_report,
)
from .recovery_verify import VerificationPolicy, verify_recovery


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _rss_mib() -> float | None:
    if _resource is None:
        return None
    value = _resource.getrusage(_resource.RUSAGE_SELF).ru_maxrss
    byte_value = value if platform.system() == "Darwin" else value * 1024
    return float(byte_value / 2**20)


def _environment() -> RuntimeEnvironment:
    return RuntimeEnvironment(
        core_version=CORE_VERSION,
        python_version=platform.python_version(),
        numpy_version=np.__version__,
        stim_version=getattr(stim, "__version__", "unknown"),
        os_name=platform.system(),
        os_release=platform.release(),
        architecture=platform.machine(),
        processor=platform.processor(),
        hostname=platform.node(),
    )


def _make_report(
    *,
    command: str,
    status: str,
    exit_code: RecoveryExitCode,
    started_at: str,
    started_clock: float,
    problem=None,
    artifact=None,
    iterations: int = 1,
    verification_policy: str = "not_applicable",
    logs: tuple[str, ...] = (),
) -> RecoveryRunReport:
    peak_rss_mib = _rss_mib()
    return RecoveryRunReport(
        format_version=RUN_REPORT_FORMAT_VERSION,
        command=command,
        status=status,
        exit_code=int(exit_code),
        semantic_problem_hash="" if problem is None else semantic_problem_hash(problem),
        problem_document_hash="" if problem is None else problem_document_hash(problem),
        artifact_document_hash="" if artifact is None else artifact_document_hash(artifact),
        started_at_utc=started_at,
        finished_at_utc=_utc_now(),
        wall_seconds=format(time.perf_counter() - started_clock, ".17g"),
        peak_rss_mib=None if peak_rss_mib is None else format(peak_rss_mib, ".17g"),
        iterations=iterations,
        verification_policy=verification_policy,
        environment=_environment(),
        logs=logs,
    )


def _emit(value: dict[str, object]) -> None:
    sys.stdout.buffer.write(canonical_json_bytes(value) + b"\n")


def _error_kind(error: Exception) -> RecoveryExitCode:
    if "unsupported" in str(error).lower() and "version" in str(error).lower():
        return RecoveryExitCode.UNSUPPORTED_VERSION
    return RecoveryExitCode.INPUT_INVALID


def _write_report_if_requested(path: str | None, report: RecoveryRunReport) -> None:
    if path:
        write_run_report(path, report)


def _compile_command(args) -> int:
    started_at, started_clock = _utc_now(), time.perf_counter()
    problem = artifact = None
    try:
        problem = read_problem(args.problem)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        code = _error_kind(error)
        status = "unsupported_version" if code == RecoveryExitCode.UNSUPPORTED_VERSION else "input_invalid"
        report = _make_report(
            command="compile", status=status, exit_code=code,
            started_at=started_at, started_clock=started_clock, logs=(f"{type(error).__name__}: {error}",)
        )
        _write_report_if_requested(args.run_report, report)
        _emit({"command": "compile", "status": status, "exit_code": int(code)})
        return int(code)
    try:
        # Lazy import: the verify command and verifier-only package never need
        # the proprietary compiler module.
        from .recovery_compile import compile_recovery

        artifact = compile_recovery(problem)
        write_artifact(args.output, artifact)
    except Exception as error:
        code = RecoveryExitCode.COMPILATION_FAILED
        report = _make_report(
            command="compile", status="compilation_failed", exit_code=code,
            started_at=started_at, started_clock=started_clock, problem=problem,
            logs=(f"{type(error).__name__}: {error}",)
        )
        _write_report_if_requested(args.run_report, report)
        _emit({"command": "compile", "status": "compilation_failed", "exit_code": int(code)})
        return int(code)
    report = _make_report(
        command="compile", status="success", exit_code=RecoveryExitCode.SUCCESS,
        started_at=started_at, started_clock=started_clock, problem=problem, artifact=artifact,
        logs=("deterministic scientific artifact written",),
    )
    _write_report_if_requested(args.run_report, report)
    _emit(
        {
            "artifact_document_hash": artifact_document_hash(artifact),
            "command": "compile",
            "exit_code": 0,
            "output": str(args.output),
            "semantic_problem_hash": semantic_problem_hash(problem),
            "status": "success",
        }
    )
    return 0


def _verify_command(args) -> int:
    started_at, started_clock = _utc_now(), time.perf_counter()
    problem = artifact = None
    try:
        problem = read_problem(args.problem)
        artifact = read_artifact(args.artifact)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        code = _error_kind(error)
        status = "unsupported_version" if code == RecoveryExitCode.UNSUPPORTED_VERSION else "input_invalid"
        report = _make_report(
            command="verify", status=status, exit_code=code,
            started_at=started_at, started_clock=started_clock, problem=problem,
            verification_policy=args.policy,
            logs=(f"{type(error).__name__}: {error}",)
        )
        _write_report_if_requested(args.run_report, report)
        _emit({"command": "verify", "status": status, "exit_code": int(code), "verified": False})
        return int(code)
    try:
        verification = verify_recovery(problem, artifact, policy=args.policy)
    except Exception as error:
        code = RecoveryExitCode.INTERNAL_ERROR
        report = _make_report(
            command="verify", status="internal_error", exit_code=code,
            started_at=started_at, started_clock=started_clock, problem=problem, artifact=artifact,
            verification_policy=args.policy,
            logs=(f"{type(error).__name__}: {error}",)
        )
        _write_report_if_requested(args.run_report, report)
        _emit({"command": "verify", "status": "internal_error", "exit_code": int(code), "verified": False})
        return int(code)
    code = RecoveryExitCode.SUCCESS if verification.verified else RecoveryExitCode.VERIFICATION_REJECTED
    status = "success" if verification.verified else "verification_rejected"
    report = _make_report(
        command="verify", status=status, exit_code=code,
        started_at=started_at, started_clock=started_clock, problem=problem, artifact=artifact,
        verification_policy=args.policy,
        logs=tuple(f"{item.name}: {'pass' if item.passed else 'fail'}" for item in verification.checks),
    )
    _write_report_if_requested(args.run_report, report)
    _emit(
        {
            "artifact_document_hash": artifact_document_hash(artifact),
            "checks": [{"name": item.name, "passed": item.passed} for item in verification.checks],
            "command": "verify",
            "channel_verified": verification.channel_verified,
            "exit_code": int(code),
            "final_order_verified": verification.final_order_verified,
            "logical_action_verified": verification.logical_action_verified,
            "overall_verdict": "valid" if verification.verified else "invalid",
            "observed_resources": {
                "logical_one_qubit_gates": verification.observed_resources.logical_one_qubit_gates,
                "routed_one_qubit_gates": verification.observed_resources.routed_one_qubit_gates,
                "logical_two_qubit_gates": verification.observed_resources.logical_two_qubit_gates,
                "routed_two_qubit_gates": verification.observed_resources.routed_two_qubit_gates,
                "logical_two_qubit_depth": verification.observed_resources.logical_two_qubit_depth,
                "routed_two_qubit_depth": verification.observed_resources.routed_two_qubit_depth,
                "max_routed_interaction_distance": verification.observed_resources.max_routed_interaction_distance,
            },
            "resource_counts_verified": verification.resource_counts_verified,
            "semantic_problem_hash": semantic_problem_hash(problem),
            "status": status,
            "swap_accounting_status": verification.swap_accounting_status,
            "topology_verified": verification.topology_verified,
            "verification_policy": verification.verification_policy,
            "verified": verification.verified,
        }
    )
    return int(code)


def _benchmark_command(args) -> int:
    started_at, started_clock = _utc_now(), time.perf_counter()
    try:
        problem = read_problem(args.problem)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        code = _error_kind(error)
        status = "unsupported_version" if code == RecoveryExitCode.UNSUPPORTED_VERSION else "input_invalid"
        report = _make_report(
            command="benchmark", status=status, exit_code=code,
            started_at=started_at, started_clock=started_clock, iterations=args.iterations,
            logs=(f"{type(error).__name__}: {error}",)
        )
        write_run_report(args.output, report)
        _emit({"command": "benchmark", "status": status, "exit_code": int(code)})
        return int(code)
    artifacts = []
    try:
        from .recovery_compile import compile_recovery

        for _ in range(args.iterations):
            artifact = compile_recovery(problem)
            if not verify_recovery(problem, artifact).verified:
                code = RecoveryExitCode.VERIFICATION_REJECTED
                report = _make_report(
                    command="benchmark", status="verification_rejected", exit_code=code,
                    started_at=started_at, started_clock=started_clock, problem=problem,
                    artifact=artifact, iterations=args.iterations,
                    logs=("an independently verified benchmark iteration was rejected",),
                )
                write_run_report(args.output, report)
                _emit({"command": "benchmark", "status": "verification_rejected", "exit_code": int(code)})
                return int(code)
            artifacts.append(artifact)
    except Exception as error:
        code = RecoveryExitCode.COMPILATION_FAILED
        report = _make_report(
            command="benchmark", status="compilation_failed", exit_code=code,
            started_at=started_at, started_clock=started_clock, problem=problem,
            artifact=artifacts[-1] if artifacts else None, iterations=args.iterations,
            logs=(f"{type(error).__name__}: {error}",),
        )
        write_run_report(args.output, report)
        _emit({"command": "benchmark", "status": "compilation_failed", "exit_code": int(code)})
        return int(code)
    hashes = tuple(artifact_document_hash(item) for item in artifacts)
    if len(set(hashes)) != 1:
        code = RecoveryExitCode.COMPILATION_FAILED
        report = _make_report(
            command="benchmark", status="compilation_failed", exit_code=code,
            started_at=started_at, started_clock=started_clock, problem=problem,
            artifact=artifacts[-1], iterations=args.iterations,
            logs=("non-deterministic artifact hashes across benchmark iterations",),
        )
        write_run_report(args.output, report)
        _emit({"command": "benchmark", "status": "compilation_failed", "exit_code": int(code)})
        return int(code)
    if args.artifact_output:
        write_artifact(args.artifact_output, artifacts[-1])
    report = _make_report(
        command="benchmark", status="success", exit_code=RecoveryExitCode.SUCCESS,
        started_at=started_at, started_clock=started_clock, problem=problem,
        artifact=artifacts[-1], iterations=args.iterations,
        logs=(f"{args.iterations} deterministic compile+verify iterations completed",),
    )
    write_run_report(args.output, report)
    _emit(
        {
            "artifact_document_hash": hashes[0],
            "command": "benchmark",
            "exit_code": 0,
            "iterations": args.iterations,
            "output": str(args.output),
            "status": "success",
        }
    )
    return 0


def _parser(*, verifier_only: bool) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stabcert")
    subparsers = parser.add_subparsers(dest="command", required=True)
    if not verifier_only:
        compile_parser = subparsers.add_parser("compile", help="compile a deterministic recovery artifact")
        compile_parser.add_argument("problem")
        compile_parser.add_argument("--output", default="artifact.json")
        compile_parser.add_argument("--run-report")
    verify_parser = subparsers.add_parser("verify", help="independently verify an untrusted artifact")
    verify_parser.add_argument("problem")
    verify_parser.add_argument("artifact")
    verify_parser.add_argument(
        "--policy",
        choices=tuple(item.value for item in VerificationPolicy),
        default=VerificationPolicy.REPRODUCIBLE_ROUTE.value,
    )
    verify_parser.add_argument("--run-report")
    if not verifier_only:
        benchmark_parser = subparsers.add_parser("benchmark", help="measure compile+verify without changing the artifact")
        benchmark_parser.add_argument("problem")
        benchmark_parser.add_argument("--output", default="run-report.json")
        benchmark_parser.add_argument("--artifact-output")
        benchmark_parser.add_argument("--iterations", type=int, default=1, choices=range(1, 101), metavar="1..100")
    return parser


def main(argv: list[str] | None = None, *, verifier_only: bool = False) -> int:
    args = _parser(verifier_only=verifier_only).parse_args(argv)
    if args.command == "compile":
        return _compile_command(args)
    if args.command == "verify":
        return _verify_command(args)
    if args.command == "benchmark":
        return _benchmark_command(args)
    return int(RecoveryExitCode.CLI_USAGE)


if __name__ == "__main__":
    raise SystemExit(main())
