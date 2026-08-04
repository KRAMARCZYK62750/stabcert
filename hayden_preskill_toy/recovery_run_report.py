"""Non-normative execution report kept outside RecoveryArtifact."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation


FORMAT_VERSION = "orelia.recovery-run-report/v2"
CORE_VERSION = "orelia-recovery-core/0.3.0"


def _decimal(value: str, name: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"invalid {name}") from error
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return parsed


def _optional_hash(value: str, name: str) -> None:
    if value and (len(value) != 64 or any(char not in "0123456789abcdef" for char in value)):
        raise ValueError(f"invalid {name}")


@dataclass(frozen=True)
class RuntimeEnvironment:
    core_version: str
    python_version: str
    numpy_version: str
    stim_version: str
    os_name: str
    os_release: str
    architecture: str
    processor: str
    hostname: str


@dataclass(frozen=True)
class RecoveryRunReport:
    format_version: str
    command: str
    status: str
    exit_code: int
    semantic_problem_hash: str
    problem_document_hash: str
    artifact_document_hash: str
    started_at_utc: str
    finished_at_utc: str
    wall_seconds: str
    peak_rss_mib: str | None
    iterations: int
    verification_policy: str
    environment: RuntimeEnvironment
    logs: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.format_version != FORMAT_VERSION:
            raise ValueError("unsupported RecoveryRunReport version")
        if self.command not in ("compile", "verify", "benchmark"):
            raise ValueError("invalid recovery command")
        if self.status not in ("success", "input_invalid", "unsupported_version", "compilation_failed", "verification_rejected", "internal_error"):
            raise ValueError("invalid run status")
        if self.exit_code < 0 or self.exit_code > 255:
            raise ValueError("exit code must be in [0,255]")
        for value, name in (
            (self.semantic_problem_hash, "semantic problem hash"),
            (self.problem_document_hash, "problem document hash"),
            (self.artifact_document_hash, "artifact document hash"),
        ):
            _optional_hash(value, name)
        for value, name in (
            (self.started_at_utc, "started_at_utc"),
            (self.finished_at_utc, "finished_at_utc"),
        ):
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as error:
                raise ValueError(f"invalid {name}") from error
        _decimal(self.wall_seconds, "wall_seconds")
        if self.peak_rss_mib is not None:
            _decimal(self.peak_rss_mib, "peak_rss_mib")
        if self.iterations < 1:
            raise ValueError("iterations must be positive")
        if self.verification_policy not in (
            "not_applicable",
            "reproducible-route",
            "channel-certified",
        ):
            raise ValueError("invalid verification policy")
        if any(not isinstance(item, str) for item in self.logs):
            raise ValueError("logs must be strings")
