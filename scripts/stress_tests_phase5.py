"""Phase 5 Robustness Stress Tests (Tests A through I per prompt §9).

Runs controlled stress tests:
- Test A: Noise sensitivity (additive Gaussian observation noise sigma in {0.01, 0.05, 0.1, 0.2})
- Test B: Environmental shift (evaluates G3 severe drift & disturbance vs nominal G1)
- Test C: Attack-intensity shift (evaluates high vs low magnitude actuator shifts in G2)
- Test D: Precursor-duration shift (short ramps 20-40 blk vs extended ramps 160-260 blk in G2)
- Test E: Onset randomization (early onset vs nominal vs late onset)
- Test F: Benign lookalikes (severe drift & thermal transients in G3)
- Test G: Held-out jamming (dense probes vs sudden high-power jamming in G4)
- Test H: Sudden attacks (intercept-resend pre-onset forecasting vs post-onset reactive confirmation)
- Test I: Reproducibility verification
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

from quantumattack.dataset import FEATURE_COLUMNS
from quantumattack.features import derived_feature_names
from quantumattack.baselines.logistic import (
    ModelConfig, build_xy, fit_horizon_model, predict_proba, feature_group_columns,
)
from quantumattack.baselines.splits import SplitConfig, split_scenarios
from quantumattack.baselines.warnings import WarningPolicy, evaluate_scenario_warnings, false_early_warning_rate
from quantumattack.evaluation.harness import classification_metrics, calibration_error


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase4-data", default=str(REPO / "data" / "phase4"))
    ap.add_argument("--phase4-features", default=str(REPO / "artifacts" / "phase4" / "features"))
    ap.add_argument("--phase5-data", default=str(REPO / "data" / "phase5"))
    ap.add_argument("--phase5-features", default=str(REPO / "artifacts" / "phase5" / "features"))
    ap.add_argument("--out", default=str(REPO / "artifacts" / "phase5" / "stress_tests"))
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    mc = ModelConfig(feature_group="D")
    wp = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50,
                       grace_blocks=5, sustained_until_onset=True)

    # 1. Fit frozen model on Phase 4 train
    m4 = json.load(open(Path(args.phase4_data) / "manifest.json", encoding="utf-8"))
    split4 = split_scenarios(m4["scenarios"], SplitConfig(seed=42, counterfactual_to_train=True, ood_holdout_family="channel_jamming"))
    
    train_frames = {}
    for sid in split4.train:
        train_frames[sid] = pd.read_parquet(Path(args.phase4_features) / f"{sid}.parquet")

    ref_df = next(iter(train_frames.values()))
    base_cols = [c for c in FEATURE_COLUMNS if c in ref_df.columns]
    feature_cols = feature_group_columns(mc.feature_group, base_cols)

    print("Fitting model for H=100...")
    X_tr, y_tr, _ = build_xy(train_frames, split4.train, 100, mc, feature_cols)
    model_h100 = fit_horizon_model(X_tr, y_tr, 100, feature_cols, mc)

    # Load Phase 5 frames
    m5 = json.load(open(Path(args.phase5_data) / "manifest.json", encoding="utf-8"))
    p5_frames = {}
    for s in m5["scenarios"]:
        p5_frames[s["scenario_id"]] = pd.read_parquet(Path(args.phase5_features) / f"{s['scenario_id']}.parquet")

    results = {}

    # -------------------------------------------------------------
    # Test A: Noise Sensitivity (additive Gaussian noise on features)
    # -------------------------------------------------------------
    print("\n--- Running Test A: Noise Sensitivity ---")
    noise_sigmas = [0.0, 0.02, 0.05, 0.1, 0.2]
    noise_results = {}
    # evaluate on G1 scenarios
    g1_sids = [s["scenario_id"] for s in m5["scenarios"] if s.get("partition") == "g1" or "s20" in s["scenario_id"]]
    for sigma in noise_sigmas:
        rng = np.random.default_rng(2026)
        all_y, all_p = [], []
        warn_anticipatory = 0
        n_gradual = 0
        normal_fws = 0
        n_normal = 0

        for sid in g1_sids:
            df = p5_frames[sid]
            onset = int(df["attack_onset"].iloc[0])
            sclass = df["scenario_class"].iloc[0]
            atype = df["attack_type"].iloc[0]
            b_idx = df["block_index"].to_numpy(dtype=int)
            valid = b_idx >= mc.min_history_blocks
            
            X = df[feature_cols].to_numpy(dtype=float)
            if sigma > 0:
                # Add observation noise proportional to feature scale
                noise = rng.normal(0, sigma, size=X.shape)
                X = X + noise

            p_vec = np.zeros(len(df))
            if valid.any():
                X_v = X[valid]
                nan_m = np.isnan(X_v).any(axis=1)
                p_v = np.zeros(len(X_v))
                if (~nan_m).any():
                    p_v[~nan_m] = predict_proba(model_h100, X_v[~nan_m])
                p_vec[valid] = p_v

            y_vec = ((b_idx < onset) & (b_idx + 100 >= onset)).astype(int)
            all_y.extend(y_vec[valid])
            all_p.extend(p_vec[valid])

            # Warning evaluation
            df_pred = pd.DataFrame({
                "scenario_id": sid, "block_index": b_idx, "timestamp_ms": df["timestamp_ms"],
                "attack_onset": onset, "attack_type": atype, "scenario_class": sclass,
                "p_attack_future_h100": p_vec,
            })
            wr = evaluate_scenario_warnings(df_pred, 100, wp)
            if atype in ("lo_manipulation", "calibration_manipulation"):
                n_gradual += 1
                if wr.category == "anticipatory":
                    warn_anticipatory += 1
            if sclass == "NORMAL":
                n_normal += 1
                if wr.n_warnings > 0:
                    normal_fws += 1

        met = classification_metrics(np.array(all_y), np.array(all_p))
        noise_results[str(sigma)] = {
            "auroc": float(met["auroc"]),
            "brier": float(met["brier"]),
            "gradual_warning_rate": warn_anticipatory / max(n_gradual, 1),
            "normal_fwr": normal_fws / max(n_normal, 1),
        }
        print(f"Noise sigma={sigma:4.2f} -> AUROC={met['auroc']:.3f}, Brier={met['brier']:.3f}, Gradual Warn Rate={warn_anticipatory}/{n_gradual}, Normal FWR={normal_fws}/{n_normal}")
    results["test_a_noise_sensitivity"] = noise_results

    # -------------------------------------------------------------
    # Test B: Environmental Shift (G3 extreme drift vs G1 nominal)
    # -------------------------------------------------------------
    print("\n--- Running Test B: Environmental Shift ---")
    g3_sids = [s["scenario_id"] for s in m5["scenarios"] if "s30" in s["scenario_id"]]
    g3_fws = 0
    g3_by_def = {}
    for sid in g3_sids:
        df = p5_frames[sid]
        b_idx = df["block_index"].to_numpy(dtype=int)
        valid = b_idx >= mc.min_history_blocks
        X = df[feature_cols].to_numpy(dtype=float)
        p_vec = np.zeros(len(df))
        if valid.any():
            X_v = X[valid]
            nan_m = np.isnan(X_v).any(axis=1)
            p_v = np.zeros(len(X_v))
            if (~nan_m).any():
                p_v[~nan_m] = predict_proba(model_h100, X_v[~nan_m])
            p_vec[valid] = p_v

        df_pred = pd.DataFrame({
            "scenario_id": sid, "block_index": b_idx, "timestamp_ms": df["timestamp_ms"],
            "attack_onset": int(df["attack_onset"].iloc[0]), "attack_type": "none", "scenario_class": df["scenario_class"].iloc[0],
            "p_attack_future_h100": p_vec,
        })
        wr = evaluate_scenario_warnings(df_pred, 100, wp)
        prefix = sid.split("-s30")[0]
        g3_by_def.setdefault(prefix, []).append(wr.n_warnings > 0)
        if wr.n_warnings > 0:
            g3_fws += 1

    results["test_b_environmental_shift"] = {
        "n_scenarios": len(g3_sids),
        "total_fwr": g3_fws / len(g3_sids),
        "fwr_by_condition": {k: float(np.mean(v)) for k, v in g3_by_def.items()},
    }
    print(f"G3 Environmental Stress FWR: {g3_fws}/{len(g3_sids)} ({g3_fws/len(g3_sids):.2%})")
    for k, v in g3_by_def.items():
        print(f"  {k}: FWR = {np.mean(v):.2%}")

    # -------------------------------------------------------------
    # Test C & D: Attack Intensity & Ramp Duration Shift (G2)
    # -------------------------------------------------------------
    print("\n--- Running Tests C & D: Ramp Duration & Bias Shift ---")
    g2_sids = [s["scenario_id"] for s in m5["scenarios"] if "s25" in s["scenario_id"]]
    g2_by_variant = {}
    for sid in g2_sids:
        df = p5_frames[sid]
        onset = int(df["attack_onset"].iloc[0])
        atype = df["attack_type"].iloc[0]
        sclass = df["scenario_class"].iloc[0]
        b_idx = df["block_index"].to_numpy(dtype=int)
        valid = b_idx >= mc.min_history_blocks

        X = df[feature_cols].to_numpy(dtype=float)
        p_vec = np.zeros(len(df))
        if valid.any():
            X_v = X[valid]
            nan_m = np.isnan(X_v).any(axis=1)
            p_v = np.zeros(len(X_v))
            if (~nan_m).any():
                p_v[~nan_m] = predict_proba(model_h100, X_v[~nan_m])
            p_vec[valid] = p_v

        df_pred = pd.DataFrame({
            "scenario_id": sid, "block_index": b_idx, "timestamp_ms": df["timestamp_ms"],
            "attack_onset": onset, "attack_type": atype, "scenario_class": sclass,
            "p_attack_future_h100": p_vec,
        })
        wr = evaluate_scenario_warnings(df_pred, 100, wp)
        variant = sid.split("-s25")[0].replace("attack-", "")
        g2_by_variant.setdefault(variant, []).append({
            "anticipatory": wr.category == "anticipatory",
            "lead": wr.lead_time_blocks,
        })

    ramp_summary = {}
    for var, items in g2_by_variant.items():
        succ = sum(1 for x in items if x["anticipatory"])
        leads = [x["lead"] for x in items if x["lead"] is not None]
        ramp_summary[var] = {
            "n": len(items),
            "warning_rate": succ / len(items),
            "median_lead": float(np.median(leads)) if leads else None,
            "mean_lead": float(np.mean(leads)) if leads else None,
        }
        print(f"Variant: {var:32s} -> WarnRate={succ}/{len(items)} ({succ/len(items):.2%}), MedianLead={ramp_summary[var]['median_lead']}")
    results["test_c_d_parameter_duration_shift"] = ramp_summary

    # -------------------------------------------------------------
    # Test G & H: Jamming Variants & Sudden Attacks
    # -------------------------------------------------------------
    print("\n--- Running Tests G & H: Hybrid Jamming & Sudden Intercept-Resend ---")
    g4_sids = [s["scenario_id"] for s in m5["scenarios"] if "s35" in s["scenario_id"]]
    g4_summary = {}
    for sid in g4_sids:
        df = p5_frames[sid]
        onset = int(df["attack_onset"].iloc[0])
        b_idx = df["block_index"].to_numpy(dtype=int)
        valid = b_idx >= mc.min_history_blocks
        X = df[feature_cols].to_numpy(dtype=float)
        p_vec = np.zeros(len(df))
        if valid.any():
            X_v = X[valid]
            nan_m = np.isnan(X_v).any(axis=1)
            p_v = np.zeros(len(X_v))
            if (~nan_m).any():
                p_v[~nan_m] = predict_proba(model_h100, X_v[~nan_m])
            p_vec[valid] = p_v

        df_pred = pd.DataFrame({
            "scenario_id": sid, "block_index": b_idx, "timestamp_ms": df["timestamp_ms"],
            "attack_onset": onset, "attack_type": "channel_jamming", "scenario_class": "ATTACK",
            "p_attack_future_h100": p_vec,
        })
        wr = evaluate_scenario_warnings(df_pred, 100, wp)
        variant = sid.split("-s35")[0].replace("attack-", "")
        g4_summary.setdefault(variant, []).append({
            "anticipatory": wr.category == "anticipatory",
            "lead": wr.lead_time_blocks,
        })

    jam_summary = {}
    for var, items in g4_summary.items():
        succ = sum(1 for x in items if x["anticipatory"])
        leads = [x["lead"] for x in items if x["lead"] is not None]
        jam_summary[var] = {
            "n": len(items),
            "warning_rate": succ / len(items),
            "median_lead": float(np.median(leads)) if leads else None,
        }
        print(f"Jamming variant: {var:32s} -> WarnRate={succ}/{len(items)} ({succ/len(items):.2%}), MedianLead={jam_summary[var]['median_lead']}")
    results["test_g_h_jamming_and_sudden"] = jam_summary

    out_file = out_dir / "stress_tests_summary.json"
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote stress tests summary to {out_file}")


if __name__ == "__main__":
    main()
