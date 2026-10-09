"""Phase 4 evaluation runner: logistic + conventional on the phase4 dataset with
pre-registered protocol (docs/phase4-protocol.md v1) + scenario-level bootstrap CIs.

Usage:
    python scripts/evaluate_phase4.py --split-seed 42 --out artifacts/phase4/eval-logistic
    python scripts/evaluate_phase4.py --split-seed 0  --out artifacts/phase4/eval-s0 ...
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

from quantumattack.evaluation.harness import run_evaluation, classification_metrics, calibration_error
from quantumattack.baselines.logistic import ModelConfig
from quantumattack.baselines.splits import SplitConfig, split_scenarios, pair_isolation_check
from quantumattack.baselines.warnings import (
    WarningPolicy, evaluate_scenario_warnings, warning_blocks_for_scenario,
    summarize_lead_times, false_warning_analysis, false_early_warning_rate,
)
from quantumattack.baselines.conventional import ThresholdPolicy


def scenario_bootstrap_ci(values: list[float], n_boot: int = 2000, seed: int = 2026,
                          stat: str = "mean") -> dict:
    """Scenario-level bootstrap CI (docs/phase4-protocol.md §9): resample scenarios
    with replacement; 95% percentile interval. Unit of independence = scenario."""
    rng = np.random.default_rng(seed)
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    if len(arr) == 0:
        return {"n": 0, "point": None, "ci_low": None, "ci_high": None}
    stats = []
    for _ in range(n_boot):
        sample = arr[rng.integers(0, len(arr), len(arr))]
        stats.append(sample.mean() if stat == "mean" else np.median(sample))
    point = float(arr.mean() if stat == "mean" else np.median(arr))
    return {
        "n": int(len(arr)),
        "point": point,
        "ci_low": float(np.percentile(stats, 2.5)),
        "ci_high": float(np.percentile(stats, 97.5)),
    }


def rate_ci(successes: int, n: int, n_boot: int = 2000, seed: int = 2026) -> dict:
    """Bootstrap CI for a proportion (scenario-level resampling of Bernoulli)."""
    if n == 0:
        return {"n": 0, "point": None, "ci_low": None, "ci_high": None}
    rng = np.random.default_rng(seed)
    arr = np.zeros(n)
    arr[:successes] = 1.0
    stats = [arr[rng.integers(0, n, n)].mean() for _ in range(n_boot)]
    return {"n": n, "point": successes / n,
            "ci_low": float(np.percentile(stats, 2.5)),
            "ci_high": float(np.percentile(stats, 97.5))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Phase 4 logistic + conventional evaluation")
    ap.add_argument("--data", default=str(REPO / "data" / "phase4"))
    ap.add_argument("--features", default=str(REPO / "artifacts" / "phase4" / "features"))
    ap.add_argument("--counterfactual-data", default=str(REPO / "data" / "phase1"))
    ap.add_argument("--counterfactual-features", default=str(REPO / "artifacts" / "phase2" / "features"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--split-seed", type=int, default=42,
                    help="multi-split robustness seed (protocol §3: 42/7/101/2024/31337)")
    ap.add_argument("--feature-group", default="D", choices=("A", "B", "C", "D"))
    ap.add_argument("--no-counterfactual", action="store_true")
    args = ap.parse_args(argv)

    # frozen protocol configuration (phase4-protocol.md §5-§7)
    mc = ModelConfig(feature_group=args.feature_group)
    wp = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50,
                       grace_blocks=5, sustained_until_onset=True)
    tp = ThresholdPolicy()

    res = run_evaluation(
        data_dir=Path(args.data),
        features_dir=Path(args.features),
        out_dir=Path(args.out),
        model_config=mc,
        split_config=SplitConfig(seed=args.split_seed, counterfactual_to_train=not args.no_counterfactual,
                                 ood_holdout_family="channel_jamming"),
        warning_policy=wp,
        threshold_policy=tp,
        experiment_id=f"phase4-{args.feature_group}-split{args.split_seed}",
        counterfactual_data_dir=None if args.no_counterfactual else Path(args.counterfactual_data),
        counterfactual_features_dir=None if args.no_counterfactual else Path(args.counterfactual_features),
    )

    # ---- scenario-level statistics + bootstrap CIs (protocol §9) ----
    preds = res.predictions
    test_preds = preds[preds["split"] == "test"]
    wpolicy = wp
    h_max = max(mc.horizons)

    # per-scenario warning results on TEST at each horizon
    warning_results = []
    for sid in res.split.test:
        df_s = test_preds[test_preds["scenario_id"] == sid]
        if df_s.empty:
            continue
        for h in mc.horizons:
            warning_results.append(evaluate_scenario_warnings(df_s, h, wpolicy))

    # bootstrap CIs per attack family at each horizon
    ci_report: dict = {}
    for h in mc.horizons:
        fam_stats: dict = {}
        for atype in ("lo_manipulation", "calibration_manipulation",
                      "intercept_resend", "channel_jamming"):
            rows = [r for r in warning_results if r.horizon == h and r.attack_type == atype]
            n = len(rows)
            succ = sum(1 for r in rows if r.category == "anticipatory")
            leads = [r.lead_time_blocks for r in rows if r.category == "anticipatory"
                     and r.lead_time_blocks is not None]
            fam_stats[atype] = {
                "n": n,
                "warning_rate": rate_ci(succ, n),
                "median_lead": scenario_bootstrap_ci(leads, stat="median"),
                "mean_lead": scenario_bootstrap_ci(leads, stat="mean"),
            }
        # benign FWR CIs
        for bclass in ("NORMAL", "BENIGN_DRIFT"):
            rows = [r for r in warning_results if r.horizon == h
                    and r.scenario_class == bclass]
            n = len(rows)
            fw = sum(1 for r in rows if r.n_warnings > 0)
            fam_stats[f"FWR_{bclass}"] = rate_ci(fw, n)
        ci_report[str(h)] = fam_stats

    # forecast-vs-conventional gain CI (paired scenario differences)
    gain_rows = []
    conv_by_sid = {c["scenario_id"]: c for c in
                   res.conventional_summary.get("scenarios", [])}
    for r in warning_results:
        if r.horizon != h_max or r.category != "anticipatory":
            continue
        conv = conv_by_sid.get(r.scenario_id)
        if conv is None or conv["warning_blocks"] is None or not conv["warning_blocks"]:
            continue
        # gain = forecast warning time − conventional warning time (positive = earlier)
        gain_rows.append(float(conv["warning_blocks"][0]) - float(r.warning_time))
    gain_ci = scenario_bootstrap_ci(gain_rows, stat="median")

    out = Path(args.out)
    report = {
        "protocol": "phase4-protocol v1",
        "split_seed": args.split_seed,
        "feature_group": args.feature_group,
        "bootstrap": {"method": "scenario bootstrap (resample scenarios with replacement)",
                      "n_boot": 2000, "seed": 2026},
        "ci_report": ci_report,
        "forecast_gain_ci": gain_ci,
        "false_warning_analysis": false_warning_analysis(warning_results),
        "horizon_metrics": {str(k): v for k, v in res.horizon_metrics.items()},
        "lead_time_summary": res.lead_time_summary,
    }
    (out / "phase4_metrics.json").write_text(json.dumps(report, indent=2, default=str),
                                             encoding="utf-8")

    # console summary
    print(f"== phase4 logistic (split {args.split_seed}, group {args.feature_group}) ==")
    for h, m in res.horizon_metrics.items():
        auroc = m["auroc"]
        auprc = m["auprc"]
        print(f"H={h}: AUROC={auroc:.3f} AUPRC={auprc:.3f} Brier={m['brier']:.3f} "
              f"warn={m['warning_rate_scenarios']}")
    for h in ("50", "100"):
        for atype, s in res.lead_time_summary.get(h, {}).items():
            med = s["median_lead_blocks"]
            print(f"H={h} {atype}: succ={s['warning_success_rate']:.2f} med={med}")
    fwr = false_early_warning_rate(warning_results)
    print("FWR:", {k: round(v, 3) for k, v in fwr.items()})
    print(f"wrote {out}/phase4_metrics.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
