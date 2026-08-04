#!/usr/bin/env python3
"""Build a verifier-only zipapp containing no recovery compiler."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipapp

import numpy as np
import stim

from hayden_preskill_toy.recovery_run_report import CORE_VERSION


MODULES = (
    "__init__.py",
    "gf2.py",
    "recovery_artifact.py",
    "recovery_exit_codes.py",
    "recovery_problem.py",
    "recovery_routing.py",
    "recovery_run_report.py",
    "recovery_serialization.py",
    "recovery_stabilizer.py",
    "recovery_verifier_cli.py",
    "recovery_verify.py",
)
SCHEMAS = (
    "recovery_problem.schema.json",
    "recovery_artifact.schema.json",
    "recovery_run_report.schema.json",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(output: Path) -> dict[str, object]:
    project_root = Path(__file__).resolve().parent
    source_root = project_root / "hayden_preskill_toy"
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="orelia-verifier-build-") as temporary:
        stage = Path(temporary)
        package = stage / "hayden_preskill_toy"
        package.mkdir()
        files = []
        for name in MODULES:
            source = source_root / name
            destination = package / name
            shutil.copyfile(source, destination)
            files.append({"path": f"hayden_preskill_toy/{name}", "sha256": _sha256(destination)})
        schema_stage = stage / "schemas"
        schema_stage.mkdir()
        for name in SCHEMAS:
            source = project_root / "schemas" / name
            destination = schema_stage / name
            shutil.copyfile(source, destination)
            files.append({"path": f"schemas/{name}", "sha256": _sha256(destination)})
        (stage / "__main__.py").write_text(
            "from hayden_preskill_toy.recovery_verifier_cli import verifier_main\n"
            "raise SystemExit(verifier_main())\n",
            encoding="utf-8",
        )
        files.append({"path": "__main__.py", "sha256": _sha256(stage / "__main__.py")})
        manifest = {
            "format_version": "orelia.verifier-only-manifest/v1",
            "core_version": CORE_VERSION,
            "entrypoint": "orelia-recovery verify",
            "contains_compiler": False,
            "external_dependencies": {
                "numpy": np.__version__,
                "stim": getattr(stim, "__version__", "unknown"),
            },
            "files": sorted(files, key=lambda item: item["path"]),
        }
        (stage / "VERIFIER_MANIFEST.json").write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        zipapp.create_archive(stage, target=output, compressed=True)
    result = {**manifest, "package_sha256": _sha256(output)}
    Path(str(output) + ".manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dist/orelia-recovery-verifier.pyz")
    arguments = parser.parse_args()
    result = build(Path(arguments.output))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
