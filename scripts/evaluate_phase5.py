"""Phase 5 Generalization & Robustness Evaluation Runner.

Evaluates the frozen Phase 4 logistic baseline and retrained baseline across:
- Partition G1: Scenario Generalization (unseen seeds & trajectories)
- Partition G2: Parameter Generalization (fast/slow ramps, steep biases)
- Partition G3: Environmental Generalization (extreme drift, thermal coupling)
- Partition G4: Attack Generalization (hybrid probes, sudden jamming)

Outputs comprehensive scenario-level bootstrap CIs (B=2000) and conventional detector comparisons.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import numpy as np
import pandas as pd

from quantumattack.dataset import FEATURE_COLUMNS
from quantumattack.features import derived_feature_names
from quantumattack.baselines.logistic import (
    ModelConfig, build_xy, fit_horizon_model, predict_proba, feature_group_columns,
)
from quantumattack.baselines.splits import SplitConfig, split_scenarios
from quantumattack.baselines.warnings import (
    WarningPolicy, evaluate_scenario_warnings, summarize_lead_times,
    false_warning_analysis, false_early_warning_rate,
)
from quantumattack.baselines.conventional import (
    ThresholdPolicy, calibrate_thresholds, detect_warnings,
)
from quantumattack.evaluation.harness import classification_metrics, calibration_error


def scenario_bootstrap_ci(values: list[float], n_boot: int = 2000, seed: int = 2026, stat: str = "mean") -> dict:
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
    if n == 0:
        return {"n": 0, "point": None, "ci_low": None, "ci_high": None}
    rng = np.random.default_rng(seed)
    arr = np.zeros(n)
    arr[:successes] = 1.0
    stats = [arr[rng.integers(0, n, n)].mean() for _ in range(n_boot)]
    return {
        "n": n,
        "point": successes / n,
        "ci_low": float(np.percentile(stats, 2.5)),
        "ci_high": float(np.percentile(stats, 97.5)),
    }


def evaluate_partition_warnings(warning_results, horizon, attack_types, bclasses):
    report = {}
    for atype in attack_types:
        rows = [r for r in warning_results if r.horizon == horizon and atype in r.attack_type]
        n = len(rows)
        succ = sum(1 for r in rows if r.category == "anticipatory")
        leads = [r.lead_time_blocks for r in rows if r.category == "anticipatory" and r.lead_time_blocks is not None]
        report[atype] = {
            "n": n,
            "warning_rate": rate_ci(succ, n),
            "median_lead": scenario_bootstrap_ci(leads, stat="median"),
            "mean_lead": scenario_bootstrap_ci(leads, stat="mean"),
        }
    for bclass in bclasses:
        rows = [r for r in warning_results if r.horizon == horizon and r.scenario_class == bclass]
        n = len(rows)
        fw = sum(1 for r in rows if r.n_warnings > 0)
        report[f"FWR_{bclass}"] = rate_ci(fw, n)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase4-data", default=str(REPO / "data" / "phase4"))
    ap.add_argument("--phase4-features", default=str(REPO / "artifacts" / "phase4" / "features"))
    ap.add_argument("--phase5-data", default=str(REPO / "data" / "phase5"))
    ap.add_argument("--phase5-features", default=str(REPO / "artifacts" / "phase5" / "features"))
    ap.add_argument("--out", default=str(REPO / "artifacts" / "phase5" / "evaluation"))
    ap.add_argument("--feature-group", default="D", choices=("A", "B", "C", "D"))
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    mc = ModelConfig(feature_group=args.feature_group)
    wp = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50,
                       grace_blocks=5, sustained_until_onset=True)
    tp = ThresholdPolicy()

    # Load Phase 4 training data for fitting the frozen baseline
    m4 = json.load(open(Path(args.phase4_data) / "manifest.json", encoding="utf-8"))
    split4 = split_scenarios(m4["scenarios"], SplitConfig(seed=42, counterfactual_to_train=True, ood_holdout_family="channel_jamming"))
    
    print("Loading Phase 4 training frames...")
    train_frames = {}
    for sid in split4.train:
        train_frames[sid] = pd.read_parquet(Path(args.phase4_features) / f"{sid}.parquet")

    # Feature columns
    ref_df = next(iter(train_frames.values()))
    base_cols = [c for c in FEATURE_COLUMNS if c in ref_df.columns]
    feature_cols = feature_group_columns(mc.feature_group, base_cols)

    print("Fitting frozen Phase 4 logistic models (H=10, 25, 50, 100)...", flush=True)
    models = {}
    for h in mc.horizons:
        t0 = time.time()
        X_tr, y_tr, _ = build_xy(train_frames, split4.train, h, mc, feature_cols)
        models[h] = fit_horizon_model(X_tr, y_tr, h, feature_cols, mc)
        print(f"  Fitted H={h} model in {time.time()-t0:.1f}s", flush=True)

    # Conventional detector calibration on Phase 4 benign train
    print("Calibrating conventional detector on Phase 4 benign train...", flush=True)
    benign_dfs = [train_frames[s["scenario_id"]] for s in m4["scenarios"]
                  if s["scenario_id"] in split4.train and s["scenario_class"] == "NORMAL"]
    ref_benign = pd.concat(benign_dfs, ignore_index=True)
    conv_cal = calibrate_thresholds(ref_benign, tp)

    # Load Phase 5 generalization dataset
    m5 = json.load(open(Path(args.phase5_data) / "manifest.json", encoding="utf-8"))
    p5_scenarios = m5["scenarios"]
    print(f"Loading Phase 5 evaluation frames ({len(p5_scenarios)} scenarios)...", flush=True)
    p5_frames = {}
    for s in p5_scenarios:
        p5_frames[s["scenario_id"]] = pd.read_parquet(Path(args.phase5_features) / f"{s['scenario_id']}.parquet")

    # Predict Phase 5 scenarios
    print("Running inference across Phase 5 scenarios...")
    pred_dfs = []
    for s in p5_scenarios:
        sid = s["scenario_id"]
        df_feat = p5_frames[sid]
        onset = int(df_feat["attack_onset"].iloc[0])
        atype = str(df_feat["attack_type"].iloc[0])
        sclass = str(df_feat["scenario_class"].iloc[0])
        part = s.get("partition", "")
        # fallback partition resolution from seed if not in metadata
        if not part:
            seed = s["seed"]
            if seed < 25000: part = "g1"
            elif seed < 30000: part = "g2"
            elif seed < 35000: part = "g3"
            else: part = "g4"

        n_rows = len(df_feat)
        X_sc = df_feat[feature_cols].to_numpy(dtype=float)
        ts = df_feat["timestamp_ms"].to_numpy(dtype=float)
        b_idx = df_feat["block_index"].to_numpy(dtype=int)

        row_dict = {
            "scenario_id": [sid] * n_rows,
            "block_index": b_idx,
            "timestamp_ms": ts,
            "attack_onset": [onset] * n_rows,
            "attack_type": [atype] * n_rows,
            "scenario_class": [sclass] * n_rows,
            "partition": [part] * n_rows,
        }

        # Warmup mask
        valid_mask = b_idx >= mc.min_history_blocks
        for h in mc.horizons:
            p_vec = np.zeros(n_rows, dtype=float)
            if valid_mask.any():
                X_val = X_sc[valid_mask]
                # mask NaNs if any
                nan_mask = np.isnan(X_val).any(axis=1)
                p_valid = np.zeros(len(X_val), dtype=float)
                if (~nan_mask).any():
                    p_valid[~nan_mask] = predict_proba(models[h], X_val[~nan_mask])
                p_vec[valid_mask] = p_valid
            row_dict[f"p_attack_future_h{h}"] = p_vec
            row_dict[f"y_true_h{h}"] = ((b_idx < onset) & (b_idx + h >= onset)).astype(int)

        pred_dfs.append(pd.DataFrame(row_dict))

    all_preds = pd.concat(pred_dfs, ignore_index=True)

    # Conventional detector evaluation on Phase 5 scenarios
    print("Evaluating conventional detector on Phase 5 scenarios...")
    conv_results = []
    for s in p5_scenarios:
        sid = s["scenario_id"]
        res_d = detect_warnings(p5_frames[sid], conv_cal, tp)
        conv_results.append({
            "scenario_id": sid,
            "scenario_class": s["scenario_class"],
            "warning_blocks": res_d["warning_blocks"],
            "n_warnings": len(res_d["warning_blocks"]),
            "partition": s.get("partition", ""),
        })

    # Per-scenario warning evaluation
    print("Evaluating warning policy across horizons...")
    warning_results = []
    for s in p5_scenarios:
        sid = s["scenario_id"]
        df_s = all_preds[all_preds["scenario_id"] == sid]
        part = df_s["partition"].iloc[0]
        for h in mc.horizons:
            wr = evaluate_scenario_warnings(df_s, h, wp)
            # attach partition
            object.__setattr__(wr, "partition", part) if hasattr(wr, "__dict__") else setattr(wr, "partition", part)
            warning_results.append(wr)

    # Evaluate by partition
    partitions = ["g1", "g2", "g3", "g4", "all"]
    partition_reports = {}
    attack_types_to_eval = [
        "lo_manipulation", "calibration_manipulation", "intercept_resend", "channel_jamming"
    ]
    bclasses_to_eval = ["NORMAL", "BENIGN_DRIFT"]

    for part in partitions:
        sub_preds = all_preds if part == "all" else all_preds[all_preds["partition"] == part]
        sub_warns = warning_results if part == "all" else [r for r in warning_results if getattr(r, "partition", "") == part]

        # Horizon metrics
        h_metrics = {}
        for h in mc.horizons:
            y = sub_preds[f"y_true_h{h}"].to_numpy()
            p = sub_preds[f"p_attack_future_h{h}"].to_numpy()
            m = classification_metrics(y, p)
            m.update(calibration_error(y, p))
            h_metrics[str(h)] = m

        # Bootstrap CIs per attack and benign class at each horizon
        part_ci = {}
        for h in mc.horizons:
            part_ci[str(h)] = evaluate_partition_warnings(sub_warns, h, attack_types_to_eval, bclasses_to_eval)

        # Forecast vs Conventional Gain at H=100
        gain_values = []
        conv_map = {c["scenario_id"]: c for c in conv_results}
        for r in sub_warns:
            if r.horizon == 100 and r.category == "anticipatory":
                conv = conv_map.get(r.scenario_id)
                if conv and conv.get("warning_blocks"):
                    gain = float(conv["warning_blocks"][0]) - float(r.warning_time)
                    gain_values.append(gain)

        gain_ci = scenario_bootstrap_ci(gain_values, stat="median")

        partition_reports[part] = {
            "n_scenarios": len(sub_preds["scenario_id"].unique()),
            "horizon_metrics": h_metrics,
            "ci_report": part_ci,
            "forecast_gain_ci": gain_ci,
            "false_warning_analysis": false_warning_analysis(sub_warns),
            "lead_time_summary": summarize_lead_times(sub_warns, category_filter="anticipatory"),
        }

    # Conventional detector summary
    conv_fwr = {}
    for part in partitions:
        sub_conv = conv_results if part == "all" else [c for c in conv_results if c.get("partition") == part]
        norm_sc = [c for c in sub_conv if c["scenario_class"] == "NORMAL"]
        drift_sc = [c for c in sub_conv if c["scenario_class"] == "BENIGN_DRIFT"]
        fwr_norm = sum(1 for c in norm_sc if c.get("n_warnings", 0) > 0) / max(len(norm_sc), 1)
        fwr_drift = sum(1 for c in drift_sc if c.get("n_warnings", 0) > 0) / max(len(drift_sc), 1)
        conv_fwr[part] = {"NORMAL": fwr_norm, "BENIGN_DRIFT": fwr_drift, "n_normal": len(norm_sc), "n_drift": len(drift_sc)}

    final_report = {
        "protocol": "phase5-protocol v1",
        "evaluator": "frozen_phase4_logistic",
        "feature_group": args.feature_group,
        "partitions": partition_reports,
        "conventional_detector_fwr": conv_fwr,
    }

    report_path = out_dir / "phase5_generalization_report.json"
    report_path.write_text(json.dumps(final_report, indent=2, default=str), encoding="utf-8")
    print(f"Phase 5 evaluation complete! Wrote {report_path}")

    # Console summary print
    print("\n================ PHASE 5 GENERALIZATION SUMMARY ================")
    for part in ["g1", "g2", "g3", "g4"]:
        rep = partition_reports[part]
        ci_h100 = rep["ci_report"]["100"]
        print(f"\n--- Partition {part.upper()} (N={rep['n_scenarios']}) ---")
        h100_m = rep["horizon_metrics"]["100"]
        auroc_str = f"{h100_m['auroc']:.3f}" if h100_m['auroc'] is not None else "N/A (all benign)"
        auprc_str = f"{h100_m['auprc']:.3f}" if h100_m['auprc'] is not None else "N/A"
        brier_str = f"{h100_m['brier']:.3f}" if h100_m['brier'] is not None else "N/A"
        print(f"H=100: AUROC={auroc_str} AUPRC={auprc_str} Brier={brier_str}")
        for atype in ["lo_manipulation", "calibration_manipulation", "intercept_resend", "channel_jamming"]:
            if atype in ci_h100 and ci_h100[atype]["n"] > 0:
                s = ci_h100[atype]
                pt = s["warning_rate"]["point"]
                med = s["median_lead"]["point"]
                print(f"  {atype:26s}: Rate={pt:.2f} [{s['warning_rate']['ci_low']:.2f}, {s['warning_rate']['ci_high']:.2f}] | MedianLead={med} blk")
        for bclass in ["NORMAL", "BENIGN_DRIFT"]:
            k = f"FWR_{bclass}"
            if k in ci_h100 and ci_h100[k]["n"] > 0:
                s = ci_h100[k]
                print(f"  {k:26s}: {s['point']:.3f} [{s['ci_low']:.3f}, {s['ci_high']:.3f}]")
        print(f"  Forecast Gain vs Conv (median): {rep['forecast_gain_ci']['point']} blk")
        print(f"  Conventional FWR: NORMAL={conv_fwr[part]['NORMAL']:.2f}, DRIFT={conv_fwr[part]['BENIGN_DRIFT']:.2f}")


if __name__ == "__main__":
    main()
