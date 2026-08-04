"""Stable process exit codes for the recovery v1 command line."""
from enum import IntEnum


class RecoveryExitCode(IntEnum):
    SUCCESS = 0
    CLI_USAGE = 2
    INPUT_INVALID = 10
    UNSUPPORTED_VERSION = 11
    COMPILATION_FAILED = 20
    VERIFICATION_REJECTED = 30
    INTERNAL_ERROR = 70

