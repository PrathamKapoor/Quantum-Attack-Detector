"""CLI entry: generate causal features for a dataset (master prompt §45).

Usage:
    python -m quantumattack.features_cli --data data/phase1 --out artifacts/phase2/features
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quantumattack.features import (  # noqa: E402
    compute_features, feature_metadata, derived_feature_names, FEATURE_SCHEMA_VERSION,
)
from quantumattack.feature_config import FeatureConfig  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate causal features for a dataset")
    parser.add_argument("--data", required=True, help="directory with scenario Parquets + manifest")
    parser.add_argument("--out", required=True, help="output directory for feature Parquets")
    args = parser.parse_args(argv)

    import pandas as pd

    data_dir = Path(args.data)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = FeatureConfig()

    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    count = 0
    for s in manifest["scenarios"]:
        df = pd.read_parquet(data_dir / f"{s['scenario_id']}.parquet")
        feat = compute_features(df, cfg)
        feat.to_parquet(out_dir / f"{s['scenario_id']}.parquet", index=False)
        count += 1
        print(f"features: {s['scenario_id']} ({len(feat.columns)} cols)")

    # schema + metadata manifest
    schema = {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "derived_features": len(derived_feature_names(cfg)),
        "feature_metadata": feature_metadata(cfg),
        "config": cfg.to_dict(),
        "missing_history_policy": "explicit NaN until minimum history (warmup); never future samples",
        "causality": "all statistics trailing; derivatives backward; CUSUM reference = scenario warmup only",
    }
    (out_dir / "feature_schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"exported {count} feature files; schema: {out_dir / 'feature_schema.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
