"""Dataset export (docs/dataset-spec.md §7).

One Parquet file per scenario + one batch manifest. Records carry telemetry +
labels + metadata; column classes per docs/dataset-spec.md §2.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..config import BLOCK_MS
from ..scenario import ScenarioResult
from ... import SCHEMA_VERSION
from ...dataset import METADATA_COLUMNS, LABEL_COLUMNS, EVAL_ONLY_COLUMNS, FEATURE_COLUMNS


def scenario_to_dataframe(result: ScenarioResult) -> pd.DataFrame:
    """Records + labels → per-record DataFrame with metadata columns."""
    df = pd.DataFrame(result.records)
    for col, values in result.labels.items():
        df[col] = values
    for col, value in result.metadata.items():
        df[col] = value
    # drift_episode_id: label column (ground-truth episode id per block)
    df["drift_episode_id"] = -1
    return df


def export_scenario(result: ScenarioResult, out_dir: Path) -> Path:
    """Write one scenario's Parquet file; returns the path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{result.metadata['scenario_id']}.parquet"
    scenario_to_dataframe(result).to_parquet(path, index=False)
    return path


def export_batch(results: list[ScenarioResult], out_dir: Path, batch_config: dict | None = None) -> Path:
    """Write all scenario Parquets + manifest.json; returns manifest path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    scenario_entries = []
    for r in results:
        export_scenario(r, out_dir)
        scenario_entries.append(
            {
                "scenario_id": r.metadata["scenario_id"],
                "pair_id": r.metadata["pair_id"],
                "arm": r.metadata["arm"],
                "seed": r.metadata["seed"],
                "scenario_class": r.metadata["scenario_class"],
                "attack_type": r.metadata["attack_type"],
                "attack_onset": r.metadata["attack_onset"],
                "precursor_start": r.metadata["precursor_start"],
                "precursor_class": r.metadata["precursor_class"],
                "n_blocks": r.n_blocks,
                "n_records": int(r.n_blocks),
            }
        )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "block_ms": BLOCK_MS,
        "sim_version": results[0].metadata["sim_version"] if results else None,
        "column_classes": {
            "metadata": sorted(METADATA_COLUMNS),
            "labels": sorted(LABEL_COLUMNS),
            "eval_only": sorted(EVAL_ONLY_COLUMNS),
            "features": sorted(FEATURE_COLUMNS),
        },
        "scenarios": scenario_entries,
        "batch_config": batch_config or {},
    }
    path = out_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path
