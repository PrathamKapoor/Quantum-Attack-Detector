"""Phase 4 feature ablation runner: logistic model across feature groups A/B/C/D
on the phase4 dataset (frozen protocol, split seed 42), with scenario-level CIs.

Usage: python scripts/ablate_phase4.py --out artifacts/phase4/ablation
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

from quantumattack.evaluation.harness import run_evaluation
from quantumattack.baselines.logistic import ModelConfig
from quantumattack.baselines.splits import SplitConfig
from quantumattack.baselines.warnings import WarningPolicy, evaluate_scenario_warnings, false_early_warning_rate
from quantumattack.baselines.conventional import ThresholdPolicy

sys.path.insert(0, str(REPO / "scripts"))
from evaluate_phase4 import scenario_bootstrap_ci, rate_ci


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "artifacts" / "phase4" / "ablation"))
    ap.add_argument("--split-seed", type=int, default=42)
    args = ap.parse_args(argv)

    wp = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50,
                       grace_blocks=5, sustained_until_onset=True)
    summary: dict = {}
    for group in ("A", "B", "C", "D"):
        res = run_evaluation(
            data_dir=Path(REPO / "data" / "phase4"),
            features_dir=Path(REPO / "artifacts" / "phase4" / "features"),
            out_dir=Path(args.out) / group,
            model_config=ModelConfig(feature_group=group),
            split_config=SplitConfig(seed=args.split_seed, counterfactual_to_train=True,
                                     ood_holdout_family="channel_jamming"),
            warning_policy=wp,
            threshold_policy=ThresholdPolicy(),
            experiment_id=f"phase4-ablation-{group}",
            counterfactual_data_dir=Path(REPO / "data" / "phase1"),
            counterfactual_features_dir=Path(REPO / "artifacts" / "phase2" / "features"),
        )
        # per-scenario warning stats at each horizon (for CI)
        preds = res.predictions
        test_preds = preds[preds["split"] == "test"]
        warning_results = []
        for sid in res.split.test:
            df_s = test_preds[test_preds["scenario_id"] == sid]
            if df_s.empty:
                continue
            for h in (10, 25, 50, 100):
                warning_results.append(evaluate_scenario_warnings(df_s, h, wp))
        per_h = {}
        for h in (10, 25, 50, 100):
            fam = {}
            for atype in ("lo_manipulation", "calibration_manipulation",
                          "intercept_resend", "channel_jamming"):
                rows = [r for r in warning_results if r.horizon == h and r.attack_type == atype]
                n = len(rows)
                succ = sum(1 for r in rows if r.category == "anticipatory")
                leads = [r.lead_time_blocks for r in rows if r.category == "anticipatory"
                         and r.lead_time_blocks is not None]
                fam[atype] = {"n": n, "warning_rate": rate_ci(succ, n),
                              "median_lead": scenario_bootstrap_ci(leads, stat="median")}
            per_h[str(h)] = fam
        summary[group] = {
            "horizon_metrics": {str(k): v for k, v in res.horizon_metrics.items()},
            "per_horizon_families": per_h,
            "fwr": false_early_warning_rate(warning_results),
        }
        print(f"group {group}: H=10 AUROC={res.horizon_metrics[10]['auroc']:.3f} "
              f"H=100 AUROC={res.horizon_metrics[100]['auroc']:.3f}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "ablation_summary.json").write_text(
        json.dumps({"protocol": "phase4-protocol v1", "split_seed": args.split_seed,
                    "summary": summary}, indent=2, default=str), encoding="utf-8")
    print(f"wrote {out}/ablation_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
