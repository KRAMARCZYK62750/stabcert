"""Standalone verifier-only CLI with no dependency on the full command module."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
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


def _report(
    command,
    status,
    code,
    started_at,
    started_clock,
    problem,
    artifact,
    logs,
    verification_policy="not_applicable",
):
    peak_rss_mib = _rss_mib()
    return RecoveryRunReport(
        format_version=RUN_REPORT_FORMAT_VERSION,
        command=command,
        status=status,
        exit_code=int(code),
        semantic_problem_hash="" if problem is None else semantic_problem_hash(problem),
        problem_document_hash="" if problem is None else problem_document_hash(problem),
        artifact_document_hash="" if artifact is None else artifact_document_hash(artifact),
        started_at_utc=started_at,
        finished_at_utc=_utc_now(),
        wall_seconds=format(time.perf_counter() - started_clock, ".17g"),
        peak_rss_mib=None if peak_rss_mib is None else format(peak_rss_mib, ".17g"),
        iterations=1,
        verification_policy=verification_policy,
        environment=RuntimeEnvironment(
            core_version=CORE_VERSION,
            python_version=platform.python_version(),
            numpy_version=np.__version__,
            stim_version=getattr(stim, "__version__", "unknown"),
            os_name=platform.system(),
            os_release=platform.release(),
            architecture=platform.machine(),
            processor=platform.processor(),
            hostname=platform.node(),
        ),
        logs=logs,
    )


def _emit(value) -> None:
    sys.stdout.buffer.write(canonical_json_bytes(value) + b"\n")


def verifier_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stabcert")
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify_parser = subparsers.add_parser("verify", help="independently verify an untrusted artifact")
    verify_parser.add_argument("problem")
    verify_parser.add_argument("artifact")
    verify_parser.add_argument(
        "--policy",
        choices=tuple(item.value for item in VerificationPolicy),
        default=VerificationPolicy.REPRODUCIBLE_ROUTE.value,
    )
    verify_parser.add_argument("--run-report")
    args = parser.parse_args(argv)
    started_at, started_clock = _utc_now(), time.perf_counter()
    problem = artifact = None
    try:
        problem = read_problem(args.problem)
        artifact = read_artifact(args.artifact)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        unsupported = "unsupported" in str(error).lower() and "version" in str(error).lower()
        code = RecoveryExitCode.UNSUPPORTED_VERSION if unsupported else RecoveryExitCode.INPUT_INVALID
        status = "unsupported_version" if unsupported else "input_invalid"
        report = _report(
            "verify", status, code, started_at, started_clock, problem, artifact,
            (f"{type(error).__name__}: {error}",), args.policy,
        )
        if args.run_report:
            write_run_report(args.run_report, report)
        _emit({"command": "verify", "status": status, "exit_code": int(code), "verified": False})
        return int(code)
    try:
        result = verify_recovery(problem, artifact, policy=args.policy)
    except Exception as error:
        code = RecoveryExitCode.INTERNAL_ERROR
        report = _report(
            "verify", "internal_error", code, started_at, started_clock, problem,
            artifact, (f"{type(error).__name__}: {error}",), args.policy,
        )
        if args.run_report:
            write_run_report(args.run_report, report)
        _emit({"command": "verify", "status": "internal_error", "exit_code": int(code), "verified": False})
        return int(code)
    code = RecoveryExitCode.SUCCESS if result.verified else RecoveryExitCode.VERIFICATION_REJECTED
    status = "success" if result.verified else "verification_rejected"
    report = _report(
        "verify", status, code, started_at, started_clock, problem, artifact,
        tuple(f"{item.name}: {'pass' if item.passed else 'fail'}" for item in result.checks),
        args.policy,
    )
    if args.run_report:
        write_run_report(args.run_report, report)
    _emit(
        {
            "artifact_document_hash": artifact_document_hash(artifact),
            "checks": [{"name": item.name, "passed": item.passed} for item in result.checks],
            "command": "verify",
            "channel_verified": result.channel_verified,
            "exit_code": int(code),
            "final_order_verified": result.final_order_verified,
            "logical_action_verified": result.logical_action_verified,
            "overall_verdict": "valid" if result.verified else "invalid",
            "observed_resources": {
                "logical_one_qubit_gates": result.observed_resources.logical_one_qubit_gates,
                "routed_one_qubit_gates": result.observed_resources.routed_one_qubit_gates,
                "logical_two_qubit_gates": result.observed_resources.logical_two_qubit_gates,
                "routed_two_qubit_gates": result.observed_resources.routed_two_qubit_gates,
                "logical_two_qubit_depth": result.observed_resources.logical_two_qubit_depth,
                "routed_two_qubit_depth": result.observed_resources.routed_two_qubit_depth,
                "max_routed_interaction_distance": result.observed_resources.max_routed_interaction_distance,
            },
            "resource_counts_verified": result.resource_counts_verified,
            "semantic_problem_hash": semantic_problem_hash(problem),
            "status": status,
            "swap_accounting_status": result.swap_accounting_status,
            "topology_verified": result.topology_verified,
            "verification_policy": result.verification_policy,
            "verified": result.verified,
        }
    )
    return int(code)


if __name__ == "__main__":
    raise SystemExit(verifier_main())
