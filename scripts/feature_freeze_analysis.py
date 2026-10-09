"""Phase 4 feature-redundancy analysis (master prompt §27): correlation, coefficient
stability for the feature freeze (§28).

Usage: python scripts/feature_freeze_analysis.py --out artifacts/phase4/feature-analysis
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import numpy as np
import pandas as pd


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default=str(REPO / "artifacts" / "phase4" / "features"))
    ap.add_argument("--out", default=str(REPO / "artifacts" / "phase4" / "feature-analysis"))
    args = ap.parse_args(argv)

    from quantumattack.dataset import FEATURE_COLUMNS
    from quantumattack.features import feature_metadata, derived_feature_names

    meta = {m["feature_name"]: m for m in feature_metadata()}
    derived = derived_feature_names()

    # ---- 1. correlation analysis on TRAIN scenario features (sample of files) ----
    import yaml
    manifest = json.loads((REPO / "data" / "phase4" / "manifest.json").read_text(encoding="utf-8"))
    batch = yaml.safe_load((REPO / "configs" / "simulation" / "phase4.yaml").read_text(encoding="utf-8"))
    train_seeds = set(batch["train_seeds"])
    train_ids = [s["scenario_id"] for s in manifest["scenarios"] if s["seed"] in train_seeds]

    sample_ids = train_ids[::4]
    cols = None
    acc = []
    for sid in sample_ids:
        df = pd.read_parquet(Path(args.features) / f"{sid}.parquet")
        if cols is None:
            cols = [c for c in df.columns if c in set(FEATURE_COLUMNS) | set(derived)]
        X = df[cols].to_numpy(dtype=float)
        mask = ~np.isnan(X).any(axis=1)
        acc.append(X[mask])
    X = np.vstack(acc)
    corr = np.corrcoef(X, rowvar=False)
    corr = np.nan_to_num(corr, nan=0.0)

    # high-correlation pairs (|r| > 0.95)
    hi_pairs = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            if abs(corr[i, j]) > 0.95:
                hi_pairs.append({"a": cols[i], "b": cols[j], "r": float(corr[i, j])})

    # ---- 2. coefficient stability across split seeds (logistic refit, H=100) ----
    from quantumattack.baselines.logistic import ModelConfig, build_xy, fit_horizon_model
    from quantumattack.baselines.splits import SplitConfig, split_scenarios

    mc = ModelConfig()
    feature_cols = [c for c in cols if c in set(FEATURE_COLUMNS) | set(derived)]
    coef_by_split: dict[int, np.ndarray] = {}
    for seed in (42, 7, 101, 2024, 31337):
        split = split_scenarios(manifest["scenarios"],
                                SplitConfig(seed=seed, counterfactual_to_train=True,
                                            ood_holdout_family="channel_jamming"))
        frames = {}
        for sid in split.train[:30]:  # subsample for speed
            frames[sid] = pd.read_parquet(Path(args.features) / f"{sid}.parquet")
        X_train, y_train, _ = build_xy(frames, split.train[:30], 100, mc, feature_cols)
        if len(np.unique(y_train)) < 2:
            continue
        model = fit_horizon_model(X_train, y_train, 100, feature_cols, mc)
        coef_by_split[seed] = model.coef

    coef_mat = np.vstack(list(coef_by_split.values()))
    coef_mean = coef_mat.mean(axis=0)
    coef_std = coef_mat.std(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        coef_cv = np.where(np.abs(coef_mean) > 1e-8, coef_std / np.abs(coef_mean), np.nan)

    order = np.argsort(-np.abs(coef_mean))
    top_features = [{"feature": cols[i], "mean_coef": float(coef_mean[i]),
                     "std_coef": float(coef_std[i]),
                     "cv": None if np.isnan(coef_cv[i]) else float(coef_cv[i]),
                     "category": meta.get(cols[i], {}).get("category", "base")}
                    for i in order[:25]]

    # unstable: tiny coefficient with huge cv, or sign flips across splits
    unstable = []
    for i, c in enumerate(cols):
        signs = np.sign(coef_mat[:, i])
        if (abs(coef_mean[i]) < 0.01) and (np.nan_to_num(coef_cv[i], nan=99.0) > 1.5):
            unstable.append({"feature": c, "mean_coef": float(coef_mean[i]),
                             "cv": None if np.isnan(coef_cv[i]) else float(coef_cv[i])})
        elif len(set(signs[signs != 0])) > 1 and abs(coef_mean[i]) < 0.02:
            unstable.append({"feature": c, "mean_coef": float(coef_mean[i]), "sign_flips": True})

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "method": {"correlation_sample": "every 4th train scenario",
                   "n_train_total": len(train_ids),
                   "coef_refit": "logistic H=100, 30 train scenarios per split seed, 5 splits"},
        "n_columns_analyzed": len(cols),
        "high_correlation_pairs_gt_0.95": hi_pairs,
        "n_high_correlation_pairs": len(hi_pairs),
        "top_features_by_coef": top_features,
        "unstable_features": unstable,
    }
    (out / "feature_analysis.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"analyzed {len(cols)} columns | {len(hi_pairs)} high-corr pairs | "
          f"{len(unstable)} unstable | top-5: {[t['feature'] for t in top_features[:5]]}")
    print(f"wrote {out}/feature_analysis.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
