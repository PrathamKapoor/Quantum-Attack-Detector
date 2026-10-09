"""Parallel feature computation for fast, deterministic extraction."""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from quantumattack.features import (
    compute_features, feature_metadata, derived_feature_names, FEATURE_SCHEMA_VERSION,
)
from quantumattack.feature_config import FeatureConfig
import pandas as pd


def _process_one(args_tuple):
    data_path, out_path = args_tuple
    df = pd.read_parquet(data_path)
    cfg = FeatureConfig()
    feat = compute_features(df, cfg)
    feat.to_parquet(out_path, index=False)
    return data_path.stem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(REPO / "data" / "phase5"))
    ap.add_argument("--out", default=str(REPO / "artifacts" / "phase5" / "features"))
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    data_dir = Path(args.data)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))

    tasks = []
    for s in manifest["scenarios"]:
        sid = s["scenario_id"]
        in_p = data_dir / f"{sid}.parquet"
        out_p = out_dir / f"{sid}.parquet"
        if not out_p.exists():
            tasks.append((in_p, out_p))

    print(f"Computing features for {len(tasks)} scenarios using {args.workers} workers...")
    if tasks:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for i, done_id in enumerate(pool.map(_process_one, tasks), 1):
                if i % 20 == 0 or i == len(tasks):
                    print(f"[{i}/{len(tasks)}] finished {done_id}")

    cfg = FeatureConfig()
    schema = {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "derived_features": len(derived_feature_names(cfg)),
        "feature_metadata": feature_metadata(cfg),
        "config": cfg.to_dict(),
        "missing_history_policy": "explicit NaN until minimum history (warmup); never future samples",
        "causality": "all statistics trailing; derivatives backward; CUSUM reference = scenario warmup only",
    }
    (out_dir / "feature_schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"Features complete. Schema written to {out_dir / 'feature_schema.json'}")


if __name__ == "__main__":
    main()
