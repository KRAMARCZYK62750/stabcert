#!/usr/bin/env python3
"""Confirm the A=7 instance through the dense-free production entry point."""
from __future__ import annotations

import csv
from pathlib import Path
import platform
import resource
import time

import numpy as np

from hayden_preskill_toy.dense_free_pipeline import (
    run_structural_instance,
    structural_timeline,
)
from hayden_preskill_toy.layout import SystemLayout
from hayden_preskill_toy.parametric_petz_stabilizer import (
    random_stabilizer_scrambler,
)


SEED = 20260802
SCRAMBLE_DEPTH = 6
MAX_SECONDS = 120.0
MAX_RSS_MIB = 1024.0


def _rss_mib() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    byte_value = value if platform.system() == "Darwin" else value * 1024
    return float(byte_value / 2**20)


def run():
    started = time.perf_counter()
    initial_rss = _rss_mib()
    layout = SystemLayout(n_message=7, n_black_hole=4)
    scrambler = random_stabilizer_scrambler(
        layout, np.random.default_rng(SEED), SCRAMBLE_DEPTH
    )
    timeline = structural_timeline(layout, scrambler)
    selected = next(row for row in timeline if row["petz_fidelity"] > 0.99)
    result = run_structural_instance(layout, scrambler, int(selected["t"]))
    metadata = {
        **result.metrics,
        "seed": SEED,
        "scramble_depth": SCRAMBLE_DEPTH,
        "total_seconds": time.perf_counter() - started,
        "initial_rss_mib": initial_rss,
        "peak_rss_mib": _rss_mib(),
        "max_seconds_budget": MAX_SECONDS,
        "max_rss_budget_mib": MAX_RSS_MIB,
    }
    metadata["budget_pass"] = (
        metadata["total_seconds"] <= MAX_SECONDS
        and metadata["peak_rss_mib"] <= MAX_RSS_MIB
    )
    if not metadata["validated"] or not metadata["budget_pass"]:
        raise AssertionError(metadata)
    return timeline, metadata


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(timeline, metadata) -> None:
    output = Path("results")
    output.mkdir(exist_ok=True)
    _write_csv(output / "dense_free_pipeline_a7_timeline.csv", timeline)
    _write_csv(output / "dense_free_pipeline_a7_resources.csv", [metadata])
    report = f"""# Audit du pipeline entièrement stabilisateur

Statut : **validé pour A=1 à A=7 ; A=8 non exécuté**.

La régression dense/structurelle complète est documentée dans
`DENSE_FREE_CHAIN_REGRESSION.md`. Cette confirmation utilise uniquement
`dense_free_pipeline.run_structural_instance` pour l'instance A=7.

## Confirmation A=7

- temps sélectionné : `t={metadata['t']}` ;
- alphabet collectif : {metadata['alphabet_size']} ;
- fidélités Petz/directe/routée : `{metadata['petz_fidelity']}` /
  `{metadata['direct_fidelity']}` / `{metadata['routed_fidelity']}` ;
- profondeur : `{metadata['logical_depth']} -> {metadata['routed_depth']}` ;
- CNOT : `{metadata['logical_cnot']} -> {metadata['routed_cnot']}` ;
- SWAP : `{metadata['swap']}` ;
- temps total : `{metadata['total_seconds']:.3f} s` ;
- RSS maximale : `{metadata['peak_rss_mib']:.1f} Mio`.

Objets denses construits par le chemin : canal=`{metadata['dense_channel_constructed']}`,
tau_X=`{metadata['dense_tau_constructed']}`, Choi=`{metadata['dense_choi_constructed']}`,
validation=`{metadata['dense_state_validation_constructed']}`.

## Portée

Cette absence d'objets denses vaut pour la sous-classe pure Clifford auditée.
Les anciens constructeurs NumPy/SVD sont conservés uniquement dans les scripts
de régression. Aucun pré-vol A=8 n'est inclus dans cette clôture.
"""
    Path("docs/notes/DENSE_FREE_PIPELINE_AUDIT.md").write_text(report)


def main() -> None:
    timeline, metadata = run()
    write_outputs(timeline, metadata)
    print(
        f"dense-free A7: validated={metadata['validated']}; "
        f"elapsed={metadata['total_seconds']:.3f}s; "
        f"RSS={metadata['peak_rss_mib']:.1f}MiB"
    )


if __name__ == "__main__":
    main()
