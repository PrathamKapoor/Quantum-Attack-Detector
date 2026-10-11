"""Reliability & Metric-Integrity Evaluation Runner.

Executes the corrected measurements defined in
`docs/reliability-evaluation-protocol.md`:

  * horizon-valid forecasting (a lead <= H forecast is credited only as an
    H-forecast; longer leads are reported separately as extended alerts),
  * correct block<->second conversion everywhere,
  * Wilson intervals for event rates, scenario-clustered bootstrap for
    continuous metrics,
  * noise sensitivity in explicitly-scaled units (with the legacy unit retained
    only for reproduction),
  * feature-fragility ablation,
  * multi-horizon probability coherence,
  * NORMAL vs BENIGN_DRIFT false-alarm accounting.

Reads frozen Phase 4/Phase 5 artifacts; writes corrected results. It never
modifies the frozen Phase 5 artifacts or datasets.
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
from quantumattack.baselines.logistic import (
    ModelConfig, build_xy, fit_horizon_model, predict_proba, feature_group_columns,
)
from quantumattack.baselines.splits import SplitConfig, split_scenarios
from quantumattack.baselines.warnings import (
    WarningPolicy, warning_blocks_for_scenario, warning_time,
)
from quantumattack.forecast_horizons import (
    classify_warning_outcome, HORIZON_VALID, EXTENDED_ALERT, ONSET_DETECTION,
    POST_ONSET_CONFIRMATION, NO_WARNING,
)
from quantumattack.evaluation.harness import classification_metrics, calibration_error
from quantumattack.statistics import wilson_interval, scenario_cluster_bootstrap
from quantumattack.noise_models import (
    PerturbationSpec, feature_scale_from_train, apply_perturbation,
    TRAIN_SIGMA, RAW_ABSOLUTE,
)
from quantumattack.temporal_units import blocks_to_seconds, verify_time_base


def _warn_probs(df_feat, feature_cols, models, mc):
    """Online per-block P(attack within H) for every horizon; causal only."""
    b = df_feat["block_index"].to_numpy(int)
    valid = b >= mc.min_history_blocks
    X = df_feat[feature_cols].to_numpy(dtype=float)
    out = {}
    for h, model in models.items():
        p = np.zeros(len(df_feat))
        if valid.any():
            Xv = X[valid]
            nm = np.isnan(Xv).any(axis=1)
            pv = np.zeros(len(Xv))
            if (~nm).any():
                pv[~nm] = predict_proba(model, Xv[~nm])
            p[valid] = pv
        out[h] = p
    return out


def _scenario_pred_frame(sid, df_feat, probs, meta):
    n = len(df_feat)
    row = {
        "scenario_id": [sid] * n,
        "block_index": df_feat["block_index"].to_numpy(int),
        "attack_onset": [int(df_feat["attack_onset"].iloc[0])] * n,
        "attack_type": [str(df_feat["attack_type"].iloc[0])] * n,
        "scenario_class": [str(df_feat["scenario_class"].iloc[0])] * n,
    }
    for h, p in probs.items():
        row[f"p_attack_future_h{h}"] = p
    return pd.DataFrame(row)


def evaluate_scenario_horizons(df_pred, wp, horizon):
    """Classify the FIRST warning into the three-way outcome taxonomy."""
    onset = int(df_pred["attack_onset"].iloc[0])
    fires = warning_blocks_for_scenario(df_pred, horizon, wp,
                                        sustained_until_onset=wp.sustained_until_onset)
    wt = warning_time(fires)
    outcome = classify_warning_outcome(
        None if wt is None else int(wt), onset, horizon, grace_blocks=wp.grace_blocks)
    return outcome, len(fires)


def _ci_rate(successes, n):
    return wilson_interval(successes, n).to_dict()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase4-data", default=str(REPO / "data" / "phase4"))
    ap.add_argument("--phase4-features", default=str(REPO / "artifacts" / "phase4" / "features"))
    ap.add_argument("--phase5-data", default=str(REPO / "data" / "phase5"))
    ap.add_argument("--phase5-features", default=str(REPO / "artifacts" / "phase5" / "features"))
    ap.add_argument("--out", default=str(REPO / "artifacts" / "reliability" / "evaluation"))
    ap.add_argument("--feature-group", default="D", choices=("A", "B", "C", "D"))
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    mc = ModelConfig(feature_group=args.feature_group)
    wp = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50,
                       grace_blocks=5, sustained_until_onset=True)

    # ------------------------------------------------------------------
    # Fit frozen Phase 4 baseline (unchanged configuration)
    # ------------------------------------------------------------------
    m4 = json.load(open(Path(args.phase4_data) / "manifest.json", encoding="utf-8"))
    split4 = split_scenarios(m4["scenarios"], SplitConfig(seed=42, counterfactual_to_train=True,
                                                         ood_holdout_family="channel_jamming"))
    train_frames = {}
    for sid in split4.train:
        train_frames[sid] = pd.read_parquet(Path(args.phase4_features) / f"{sid}.parquet")
    ref_df = next(iter(train_frames.values()))
    base_cols = [c for c in FEATURE_COLUMNS if c in ref_df.columns]
    feature_cols = feature_group_columns(mc.feature_group, base_cols)

    t0 = time.time()
    models = {}
    X_by_h = {}
    for h in mc.horizons:
        X_tr, y_tr, _ = build_xy(train_frames, split4.train, h, mc, feature_cols)
        models[h] = fit_horizon_model(X_tr, y_tr, h, feature_cols, mc)
        X_by_h[h] = X_tr
    fit_s = time.time() - t0
    print(f"[fit] {len(mc.horizons)} horizon models on {len(split4.train)} train "
          f"scenarios in {fit_s:.1f}s ({len(feature_cols)} features)", flush=True)

    # Feature scale fit on TRAIN only (for scaled noise experiments)
    fscale = feature_scale_from_train(X_by_h[100])

    # ------------------------------------------------------------------
    # Load Phase 5 evaluation scenarios
    # ------------------------------------------------------------------
    m5 = json.load(open(Path(args.phase5_data) / "manifest.json", encoding="utf-8"))
    eval_frames = {}
    eval_meta = {}
    for s in m5["scenarios"]:
        sid = s["scenario_id"]
        seed = s["seed"]
        part = s.get("partition") or ("g1" if seed < 25000 else "g2" if seed < 30000
                                     else "g3" if seed < 35000 else "g4")
        s["partition"] = part
        eval_meta[sid] = {"partition": part, "seed": seed,
                          "scenario_class": s.get("scenario_class", ""),
                          "attack_type": s.get("attack_type", "")}
        eval_frames[sid] = pd.read_parquet(Path(args.phase5_features) / f"{sid}.parquet")

    def sids_in(part):
        return [sid for sid, m in eval_meta.items() if m["partition"] == part]

    pred_frames = {}
    for sid, df in eval_frames.items():
        probs = _warn_probs(df, feature_cols, models, mc)
        pred_frames[sid] = _scenario_pred_frame(sid, df, probs, eval_meta[sid])

    report = {
        "protocol": "reliability-evaluation-protocol v1",
        "time_base": verify_time_base(),
        "feature_group": mc.feature_group,
        "n_features": len(feature_cols),
        "warning_policy": wp.to_dict(),
        "model_config": mc.to_dict(),
        "frozen_baseline": {
            "source": "Phase 4 logistic, C=1.0, balanced, fit on Phase 4 train only",
            "fit_seconds": round(fit_s, 2),
        },
    }

    # ------------------------------------------------------------------
    # 1. Horizon-valid forecasting across partitions and horizons
    # ------------------------------------------------------------------
    print("\n[1/6] horizon-valid forecasting ...", flush=True)
    horizon_report = {}
    for part in ("g1", "g2", "g3", "g4"):
        sids = sids_in(part)
        for h in mc.horizons:
            by_type = {}
            by_class_false = {}
            for sid in sids:
                df_pred = pred_frames[sid]
                atype = str(df_pred["attack_type"].iloc[0])
                sclass = str(df_pred["scenario_class"].iloc[0])
                outcome, n_fires = evaluate_scenario_horizons(df_pred, wp, h)
                if sclass == "ATTACK":
                    d = by_type.setdefault(atype, [])
                    d.append((outcome, n_fires))
                else:
                    # benign: any warning is a false alarm
                    d = by_class_false.setdefault(sclass, [])
                    d.append((n_fires,))
            entry = {"attack_families": {}, "benign_classes": {}}
            for atype, rows in sorted(by_type.items()):
                n = len(rows)
                hv = sum(1 for o, _ in rows if o.outcome == HORIZON_VALID)
                ext = sum(1 for o, _ in rows if o.outcome == EXTENDED_ALERT)
                det = sum(1 for o, _ in rows if o.outcome == ONSET_DETECTION)
                post = sum(1 for o, _ in rows if o.outcome == POST_ONSET_CONFIRMATION)
                none = sum(1 for o, _ in rows if o.outcome == NO_WARNING)
                hv_leads = [o.lead_blocks for o, _ in rows if o.outcome == HORIZON_VALID]
                all_pre_leads = [o.lead_blocks for o, _ in rows
                                 if o.outcome in (HORIZON_VALID, EXTENDED_ALERT)]
                entry["attack_families"][atype] = {
                    "n_scenarios": n,
                    "horizon_valid": _ci_rate(hv, n),
                    "extended_pre_onset_alert": _ci_rate(ext, n),
                    "onset_detection": _ci_rate(det, n),
                    "post_onset_confirmation": _ci_rate(post, n),
                    "no_warning": _ci_rate(none, n),
                    "any_pre_onset_alert": _ci_rate(hv + ext + det, n),
                    "horizon_valid_lead_blocks": {
                        "median": float(np.median(hv_leads)) if hv_leads else None,
                        "mean": float(np.mean(hv_leads)) if hv_leads else None,
                        "min": float(np.min(hv_leads)) if hv_leads else None,
                        "max": float(np.max(hv_leads)) if hv_leads else None,
                    },
                    "horizon_valid_lead_seconds": {
                        "median": blocks_to_seconds(float(np.median(hv_leads))) if hv_leads else None,
                    },
                    "all_pre_onset_lead_blocks": {
                        "median": float(np.median(all_pre_leads)) if all_pre_leads else None,
                        "max": float(np.max(all_pre_leads)) if all_pre_leads else None,
                    },
                }
            for bclass, rows in sorted(by_class_false.items()):
                n = len(rows)
                fa = sum(1 for (nf,) in rows if nf > 0)
                entry["benign_classes"][bclass] = {
                    "n_scenarios": n,
                    "false_alarm_scenario_rate": _ci_rate(fa, n),
                    "n_false_alarm_scenarios": fa,
                }
            horizon_report.setdefault(part, {})[str(h)] = entry

    report["horizon_valid_forecasting"] = horizon_report

    # ------------------------------------------------------------------
    # 2. Window-level discrimination with scenario-clustered CIs (G1, G2)
    # ------------------------------------------------------------------
    print("[2/6] scenario-clustered discrimination metrics ...", flush=True)
    disc = {}
    from sklearn.metrics import roc_auc_score
    for part in ("g1", "g2"):
        sids = sids_in(part)
        for h in mc.horizons:
            scen = {}
            for sid in sids:
                df_pred = pred_frames[sid]
                onset = int(df_pred["attack_onset"].iloc[0])
                b = df_pred["block_index"].to_numpy(int)
                valid = b >= mc.min_history_blocks
                p = df_pred[f"p_attack_future_h{h}"].to_numpy(float)
                y = ((b < onset) & (b + h >= onset)).astype(int)
                scen[sid] = (y[valid], p[valid])
            ys = np.concatenate([scen[s][0] for s in sids])
            ps = np.concatenate([scen[s][1] for s in sids])
            met = classification_metrics(ys, ps)
            met.update(calibration_error(ys, ps))

            def auroc_from(sel, scen=scen):
                yy = np.concatenate([scen[s][0] for s in sel])
                pp = np.concatenate([scen[s][1] for s in sel])
                if len(np.unique(yy)) < 2:
                    return None
                return float(roc_auc_score(yy, pp))

            rng = np.random.default_rng(2026)
            aurocs = []
            n_failed = 0
            for _ in range(1000):
                sel = [sids[i] for i in rng.integers(0, len(sids), len(sids))]
                a = auroc_from(sel)
                if a is None:
                    n_failed += 1
                else:
                    aurocs.append(a)
            auroc_ci = {
                "point": met["auroc"],
                "ci_low": float(np.percentile(aurocs, 2.5)) if aurocs else None,
                "ci_high": float(np.percentile(aurocs, 97.5)) if aurocs else None,
                "n_scenarios": len(sids),
                "n_boot": 1000,
                "n_failed_resamples": n_failed,
                "seed": 2026,
                "method": "scenario_cluster_percentile_bootstrap",
            }
            disc.setdefault(part, {})[str(h)] = {
                "auroc": met["auroc"], "auroc_ci": auroc_ci,
                "auprc": met["auprc"], "brier": met["brier"],
                "ece": met["ece"], "n_windows": met["n"],
                "n_positive_windows": met["n_positive"],
            }
    report["discrimination"] = disc

    # ------------------------------------------------------------------
    # 3. Noise sensitivity in EXPLICITLY-SCALED units + legacy reproduction
    # ------------------------------------------------------------------
    print("[3/6] noise sensitivity (scaled units) ...", flush=True)
    g1_sids = sids_in("g1")
    model100 = models[100]

    def eval_on(model, subset_sids, cols, transform=None):
        """Predict + score with a (possibly perturbed) feature subset.

        Returns (y_true, p_pred) concatenated over the given scenarios. Rows
        whose features are non-finite after perturbation are EXCLUDED and counted
        by the caller — they are degraded telemetry, not valid measurements.
        """
        ys, ps = [], []
        for sid in subset_sids:
            df = eval_frames[sid]
            onset = int(df["attack_onset"].iloc[0])
            b = df["block_index"].to_numpy(int)
            valid = b >= mc.min_history_blocks
            X = df[cols].to_numpy(dtype=float).copy()
            if transform is not None:
                X = transform(X)
            Xv = X[valid]
            finite = np.isfinite(Xv).all(axis=1)
            y = ((b < onset) & (b + 100 >= onset)).astype(int)[valid]
            pv = np.zeros(len(Xv))
            if finite.any():
                pv[finite] = predict_proba(model, Xv[finite])
            ys.extend(y[finite]); ps.extend(pv[finite])
        return np.array(ys), np.array(ps)

    def eval_noise(spec):
        ys, ps = eval_on(model100, g1_sids, feature_cols,
                         lambda X: apply_perturbation(X, spec, fscale))
        return classification_metrics(ys, ps)

    noise = {}
    for sigma in (0.0, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0):
        spec = PerturbationSpec(kind="gaussian", units=TRAIN_SIGMA, magnitude=sigma, seed=2026)
        met = eval_noise(spec)
        noise[f"train_sigma_{sigma}"] = {
            "spec": spec.to_dict(), "auroc": met["auroc"], "auprc": met["auprc"],
            "brier": met["brier"], "n": met["n"]}
    # Legacy reproduction (raw_absolute) — documented as not physically meaningful
    for sigma in (0.02, 0.05):
        spec = PerturbationSpec(kind="gaussian", units=RAW_ABSOLUTE, magnitude=sigma, seed=2026)
        met = eval_noise(spec)
        noise[f"legacy_raw_absolute_{sigma}"] = {
            "spec": spec.to_dict(), "auroc": met["auroc"], "auprc": met["auprc"],
            "brier": met["brier"], "note": "unit-ambiguous; reproduces historical Test A only"}
    report["noise_sensitivity"] = noise

    # ------------------------------------------------------------------
    # 4. Feature fragility ablation: drop most-noise-sensitive features
    # ------------------------------------------------------------------
    print("[4/6] feature fragility ablation ...", flush=True)
    # rank by train std ascending (most fragile to raw noise), also the opposite
    order_fragile = np.argsort(fscale.std)
    keep_robust = sorted(order_fragile[int(0.5 * len(order_fragile)):].tolist())
    frag_report = {}
    for name, keep_idx in (("full_group_D", list(range(len(feature_cols)))),
                           ("drop_smallest_train_std_half", keep_robust)):
        sub = [feature_cols[i] for i in keep_idx]
        X_sub, y_sub, _ = build_xy(train_frames, split4.train, 100, mc, sub)
        model_sub = fit_horizon_model(X_sub, y_sub, 100, sub, mc)
        ys, ps = eval_on(model_sub, g1_sids, sub)
        met = classification_metrics(ys, ps)
        frag_report[name] = {
            "n_features": len(sub),
            "auroc": met["auroc"], "auprc": met["auprc"], "brier": met["brier"],
            "dropped_feature_count": len(feature_cols) - len(sub),
        }
    report["feature_fragility_ablation"] = frag_report

    # ------------------------------------------------------------------
    # 5. Multi-horizon probability coherence
    # ------------------------------------------------------------------
    print("[5/6] multi-horizon coherence ...", flush=True)
    coh = {}
    hs = sorted(mc.horizons)
    for part in ("g1", "g2"):
        sids = sids_in(part)
        viol = 0
        total = 0
        mean_p = {}
        for sid in sids:
            df_pred = pred_frames[sid]
            b = df_pred["block_index"].to_numpy(int)
            valid = b >= mc.min_history_blocks
            P = np.stack([df_pred[f"p_attack_future_h{h}"].to_numpy(float) for h in hs], axis=1)[valid]
            for j, h in enumerate(hs):
                mean_p.setdefault(h, []).append(float(P[:, j].mean()))
            for j in range(len(hs) - 1):
                viol += int((P[:, j] > P[:, j + 1]).sum())
                total += int(len(P))
        coh[part] = {
            "violation_rate": viol / total if total else None,
            "n_pairs_checked": total,
            "mean_p_by_horizon": {str(h): float(np.mean(mean_p[h])) for h in hs},
            "note": "separately-fit per-horizon models need not be monotone in H",
        }
    report["multi_horizon_coherence"] = coh

    # ------------------------------------------------------------------
    # 6. False-alarm operational burden: NORMAL vs BENIGN_DRIFT
    # ------------------------------------------------------------------
    print("[6/6] false-alarm burden ...", flush=True)
    burden = {}
    for part in ("g1", "g2", "g3"):
        sids = sids_in(part)
        for h in (100,):
            per_class = {}
            for sid in sids:
                df_pred = pred_frames[sid]
                sclass = str(df_pred["scenario_class"].iloc[0])
                onset = int(df_pred["attack_onset"].iloc[0])
                if onset >= 0:
                    continue  # only benign
                fires = warning_blocks_for_scenario(df_pred, h, wp,
                                                     sustained_until_onset=wp.sustained_until_onset)
                n_blocks = len(df_pred)
                dur = (max(fires) - min(fires) + 1) if fires else 0
                per_class.setdefault(sclass, []).append({
                    "n_warnings": len(fires), "duration_blocks": dur,
                    "first_fire": fires[0] if fires else None, "n_blocks": n_blocks})
            for sclass, rows in sorted(per_class.items()):
                n = len(rows)
                fa = sum(1 for r in rows if r["n_warnings"] > 0)
                warn_time = sum(r["duration_blocks"] for r in rows)
                total_time = sum(r["n_blocks"] for r in rows)
                # Simulated operating time (1 block = 10 ms = 0.01 s).
                sim_seconds = total_time * 0.01
                burden.setdefault(part, {})[sclass] = {
                    "n_scenarios": n,
                    "false_alarm_scenario_rate": _ci_rate(fa, n),
                    "n_false_alarm_scenarios": fa,
                    "mean_warnings_per_scenario": float(np.mean([r["n_warnings"] for r in rows])),
                    # Reported per 1000 s of SIMULATED operation. Normalising per
                    # simulated hour is not meaningful: each scenario is only 20 s
                    # of operation, so an hourly rate would extrapolate ~180x beyond
                    # the simulated window and its uncertainty would be enormous.
                    "false_alarm_episodes_per_1000_simulated_seconds":
                        (fa / sim_seconds * 1000.0) if sim_seconds > 0 else None,
                    "warning_load_fraction": (warn_time / total_time) if total_time else None,
                    "simulated_operating_seconds": sim_seconds,
                    "scenario_duration_seconds": blocks_to_seconds(rows[0]["n_blocks"]),
                }
    report["false_alarm_burden"] = burden

    # ------------------------------------------------------------------
    # 7. False-alarm root cause: does the above-threshold run reach the end?
    # ------------------------------------------------------------------
    print("[7/7] false-alarm root-cause analysis ...", flush=True)

    def longest_run_above(pv, thr=0.5):
        best = cur = end_at = 0
        for i, v in enumerate(pv):
            if v >= thr:
                cur += 1
            else:
                if cur > best:
                    best, end_at = cur, i
                cur = 0
        if cur > best:
            best, end_at = cur, len(pv)
        return best, end_at

    root = {}
    for part in ("g1", "g2", "g3"):
        rows_r = []
        for sid in sids_in(part):
            df_pred = pred_frames[sid]
            if int(df_pred["attack_onset"].iloc[0]) >= 0:
                continue
            pv = df_pred["p_attack_future_h100"].to_numpy(float)
            run, end_at = longest_run_above(pv)
            fires = warning_blocks_for_scenario(df_pred, 100, wp,
                                                sustained_until_onset=True)
            rows_r.append({
                "scenario_id": sid,
                "scenario_class": str(df_pred["scenario_class"].iloc[0]),
                "n_fires": len(fires),
                "longest_run_above_threshold": run,
                "run_ends_at_block": end_at,
                "n_blocks": len(df_pred),
                "run_reaches_scenario_end": end_at >= len(df_pred) - 1,
            })
        if not rows_r:
            continue
        fired = [x for x in rows_r if x["n_fires"] > 0]
        reach = [x for x in rows_r if x["run_reaches_scenario_end"]]
        root[part] = {
            "n_benign_scenarios": len(rows_r),
            "n_with_false_alarm": len(fired),
            "n_run_reaching_end": len(reach),
            "all_run_to_end_fired": all(x["n_fires"] > 0 for x in reach) if reach else None,
            "fired_with_run_reaching_end": sum(1 for x in fired if x["run_reaches_scenario_end"]),
            "interpretation": (
                "sustained_until_onset requires p>=threshold to hold until scenario "
                "end for benign runs; a benign trajectory whose probability stays "
                "elevated for hundreds of blocks is indistinguishable from a "
                "sustained precursor under this policy"
            ),
            "per_scenario": rows_r,
        }
    report["false_alarm_root_cause"] = root

    # ------------------------------------------------------------------
    # 8. Calibration on a TRAIN-derived calibration split (never on test)
    # ------------------------------------------------------------------
    print("[8/8] calibration ...", flush=True)
    from sklearn.isotonic import IsotonicRegression
    from sklearn.linear_model import LogisticRegression as LR

    cal_ids = [s for s in split4.val] or split4.train[: max(1, len(split4.train) // 5)]
    cal_frames = {s: pd.read_parquet(Path(args.phase4_features) / f"{s}.parquet") for s in cal_ids}
    cal = {}
    for h in mc.horizons:
        Xc, yc, _ = build_xy(cal_frames, cal_ids, h, mc, feature_cols)
        pc = predict_proba(models[h], Xc)
        ys_all, ps_all = [], []
        for sid in sids_in("g1"):
            df_pred = pred_frames[sid]
            onset = int(df_pred["attack_onset"].iloc[0])
            b = df_pred["block_index"].to_numpy(int)
            valid = b >= mc.min_history_blocks
            ys_all.extend((((b < onset) & (b + h >= onset)).astype(int))[valid])
            ps_all.extend(df_pred[f"p_attack_future_h{h}"].to_numpy(float)[valid])
        ys_all = np.array(ys_all); ps_all = np.array(ps_all)

        entry = {"n_calibration_rows": int(len(yc)),
                 "n_calibration_positives": int(yc.sum()),
                 "g1_n_windows": int(len(ys_all))}
        # uncalibrated
        m_raw = classification_metrics(ys_all, ps_all)
        entry["uncalibrated"] = {"brier": m_raw["brier"], "ece": calibration_error(ys_all, ps_all)["ece"]}
        # Platt
        platt = LR(max_iter=1000, random_state=0)
        platt.fit(pc.reshape(-1, 1), yc)
        p_platt = platt.predict_proba(ps_all.reshape(-1, 1))[:, 1]
        m_pl = classification_metrics(ys_all, p_platt)
        entry["platt"] = {"brier": m_pl["brier"], "ece": calibration_error(ys_all, p_platt)["ece"]}
        # Isotonic — only when the calibration split supports it
        if yc.sum() >= 200:
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(pc, yc)
            p_iso = iso.predict(ps_all)
            m_iso = classification_metrics(ys_all, p_iso)
            entry["isotonic"] = {"brier": m_iso["brier"],
                                 "ece": calibration_error(ys_all, p_iso)["ece"],
                                 "n_calibration_positives": int(yc.sum())}
        else:
            entry["isotonic"] = {"status": "INSUFFICIENT SAMPLE",
                                 "n_calibration_positives": int(yc.sum()),
                                 "required": 200}
        cal[str(h)] = entry
    report["calibration"] = {
        "calibration_split": "Phase 4 validation (falls back to held-out train slice)",
        "n_calibration_scenarios": len(cal_ids),
        "by_horizon": cal,
        "note": ("probabilities are calibrated to the SYNTHETIC attack distribution only; "
                 "they are NOT real-world attack probabilities"),
    }

    out_file = out_dir / "reliability_report.json"
    out_file.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {out_file}")

    # Console summary
    print("\n================ HORIZON-VALID FORECASTING (H=100) ================")
    for part in ("g1", "g2", "g4"):
        e = horizon_report[part]["100"]
        print(f"\n--- {part.upper()} ---")
        for atype, v in e["attack_families"].items():
            hv = v["horizon_valid"]["point"]
            hv_ci = v["horizon_valid"]
            ext = v["extended_pre_onset_alert"]["point"]
            med = v["horizon_valid_lead_blocks"]["median"]
            med_s = v["horizon_valid_lead_seconds"]["median"]
            print(f"  {atype:26s} n={v['n_scenarios']:2d} "
                  f"horizon-valid={hv:.3f} [{hv_ci['ci_low']:.3f},{hv_ci['ci_high']:.3f}] "
                  f"extended-alert={ext:.3f} medLead={med} blk ({med_s} s)" if hv is not None else
                  f"  {atype:26s} n={v['n_scenarios']:2d} (no warnings)")
        for bclass, v in e["benign_classes"].items():
            print(f"  FALSE-ALARM {bclass:14s} n={v['n_scenarios']:2d} "
                  f"rate={v['false_alarm_scenario_rate']['point']:.3f} "
                  f"[{v['false_alarm_scenario_rate']['ci_low']:.3f},"
                  f"{v['false_alarm_scenario_rate']['ci_high']:.3f}]")

    print("\n================ NOISE (explicit units) ================")
    for k, v in noise.items():
        print(f"  {k:28s} AUROC={v['auroc']:.3f} Brier={v['brier']:.3f}")


if __name__ == "__main__":
    main()