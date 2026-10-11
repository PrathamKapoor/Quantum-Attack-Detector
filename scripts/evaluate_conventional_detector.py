"""Forecast-vs-conventional fair comparison (decisions.md D-052, D-053).

Evaluates the causal sequential (CUSUM) conventional detector and the frozen
forecast warning pipeline on the SAME scenario populations and time base.

Comparison principles (repair specification sec.14):
  * identical scenario populations (G1/G2/G3/G4) and ground-truth onsets;
  * actual emitted alert events for both systems (emission timestamps only);
  * the conventional detector is calibrated on Phase-4 validation benign to a
    declared scenario-level false-alert budget (<= 10%);
  * the forecaster is the frozen baseline at its frozen policy (P>=0.5, K=3);
  * a MATCHED-budget line is additionally reported by sweeping the forecaster
    threshold to the operating point whose G1 benign false-alarm rate is
    closest to the detector's;
  * outcomes are separated: horizon-valid forecast, extended pre-onset alert,
    at-onset, post-onset, no warning -- for the forecaster; and
    pre-onset detection / at-onset / post-onset / no detection -- for the
    detector using the same emission semantics.

Writes artifacts/reliability/evaluation/conventional_comparison.json
Never modifies frozen artifacts or datasets.
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
from quantumattack.baselines.warnings import WarningPolicy, warning_events_for_scenario
from quantumattack.baselines.conventional import (
    CusumConfig, calibrate_cusum_threshold, detect_warnings_cusum,
)
from quantumattack.forecast_horizons import classify_warning_outcome, HORIZON_VALID
from quantumattack.operational_states import (
    OperationalPolicy, operational_state_series, summarize_alert_burden,
)
from quantumattack.statistics import wilson_interval


def _first_emission(events):
    return events[0].emission_block if events else None


def _classify_detector_emission(emission, onset, grace):
    """Detector outcome taxonomy (mutually exclusive, emission-based)."""
    if emission is None:
        return "no_detection"
    lead = onset - emission
    if lead < 0:
        return "post_onset_detection"
    if lead <= grace:
        return "at_onset_detection"
    return "pre_onset_detection"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "artifacts" / "reliability" / "evaluation"))
    ap.add_argument("--target-fpr", type=float, default=0.10)
    ap.add_argument("--grace-blocks", type=int, default=5)
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    m4 = json.load(open(REPO / "data" / "phase4" / "manifest.json", encoding="utf-8"))
    m5 = json.load(open(REPO / "data" / "phase5" / "manifest.json", encoding="utf-8"))
    split4 = split_scenarios(m4["scenarios"], SplitConfig(
        seed=42, counterfactual_to_train=True, ood_holdout_family="channel_jamming"))

    load4 = lambda sid: pd.read_parquet(REPO / "artifacts" / "phase4" / "features" / f"{sid}.parquet")
    load5 = lambda sid: pd.read_parquet(REPO / "artifacts" / "phase5" / "features" / f"{sid}.parquet")

    # ---- conventional detector calibration (train ref + val budget) --------
    train_benign = [s["scenario_id"] for s in m4["scenarios"]
                    if s["scenario_id"] in set(split4.train) and s["scenario_class"] == "NORMAL"]
    val_benign = [s["scenario_id"] for s in m4["scenarios"]
                  if s["scenario_id"] in set(split4.val) and s["scenario_class"] == "NORMAL"]
    ref_df = pd.concat([load4(s) for s in train_benign], ignore_index=True)
    val_df = pd.concat([load4(s).assign(scenario_id=s) for s in val_benign], ignore_index=True)
    base_cfg = CusumConfig(persistence_k=3, cooldown_blocks=50, warmup_blocks=200)
    cal = calibrate_cusum_threshold(ref_df, val_df, base_cfg, target_fpr=args.target_fpr)
    det_cfg = CusumConfig(k_drift=cal.config["k_drift"], h_threshold=cal.h_threshold,
                          persistence_k=3, cooldown_blocks=50, warmup_blocks=200)
    print(f"[detector] calibrated k={det_cfg.k_drift} h={det_cfg.h_threshold} "
          f"val FPR={cal.achieved_scenario_fpr:.3f} (budget {args.target_fpr})", flush=True)

    # ---- frozen forecaster fit (Phase 4 train only) ------------------------
    mc = ModelConfig(feature_group="D")
    train_frames = {sid: load4(sid) for sid in split4.train}
    base_cols = [c for c in FEATURE_COLUMNS if c in next(iter(train_frames.values())).columns]
    feature_cols = feature_group_columns("D", base_cols)
    X, y, _ = build_xy(train_frames, split4.train, 100, mc, feature_cols)
    model = fit_horizon_model(X, y, 100, feature_cols, mc)
    print(f"[forecaster] fitted in {time.time() - t0:.1f}s", flush=True)

    # ---- per-scenario evaluation on G1..G4 ---------------------------------
    partitions = {"g1": (20000, 25000), "g2": (25000, 30000),
                  "g3": (30000, 35000), "g4": (35000, 40000)}
    per_scenario = []
    for part, (lo, hi) in partitions.items():
        for s in m5["scenarios"]:
            if not (lo <= s["seed"] < hi):
                continue
            sid = s["scenario_id"]
            df = load5(sid)
            onset = int(df["attack_onset"].iloc[0])
            b = df["block_index"].to_numpy(int)
            valid = b >= 100
            Xv = df[feature_cols].to_numpy(float)
            nm = np.isnan(Xv).any(axis=1)
            p = np.zeros(len(df))
            good = valid & ~nm
            if good.any():
                p[good] = predict_proba(model, Xv[good])
            dfp = pd.DataFrame({
                "scenario_id": sid, "block_index": b, "attack_onset": onset,
                "attack_type": str(df["attack_type"].iloc[0]),
                "scenario_class": str(df["scenario_class"].iloc[0]),
                "p_attack_future_h100": p,
            })
            # detector
            det = detect_warnings_cusum(df, cal, det_cfg)
            # forecaster at the frozen policy and at higher thresholds
            fc = {}
            for thr in (0.5, 0.7, 0.8, 0.9, 0.95):
                pol = WarningPolicy(prob_threshold=thr, persistence_k=3,
                                    cooldown_blocks=50, grace_blocks=5,
                                    sustained_until_onset=False)
                evs = warning_events_for_scenario(dfp, 100, pol)
                fc[thr] = _first_emission(evs)
            per_scenario.append({
                "partition": part, "scenario_id": sid,
                "scenario_class": str(df["scenario_class"].iloc[0]),
                "attack_type": str(df["attack_type"].iloc[0]),
                "onset": onset, "n_blocks": len(df),
                "detector_first_emission": _first_emission([]) if not det["warning_blocks"]
                else det["warning_blocks"][0],
                "forecaster_first_emission": {str(k): v for k, v in fc.items()},
            })
    print(f"[eval] {len(per_scenario)} scenarios in {time.time() - t0:.1f}s", flush=True)

    def _summarize(system: str, get_emission, part: str | None = None):
        rows = [r for r in per_scenario if (part is None or r["partition"] == part)]
        benign = [r for r in rows if r["onset"] < 0]
        attacks = [r for r in rows if r["onset"] >= 0]
        n_b_fired = sum(1 for r in benign if get_emission(r) is not None)
        out = {
            "n_benign": len(benign),
            "benign_false_alarm_rate": wilson_interval(n_b_fired, len(benign)).to_dict(),
            "n_attacks": len(attacks),
        }
        cats = {"pre_onset_detection": 0, "at_onset_detection": 0,
                "post_onset_detection": 0, "no_detection": 0}
        leads = []
        for r in attacks:
            e = get_emission(r)
            c = _classify_detector_emission(e, r["onset"], args.grace_blocks)
            if system == "forecaster" and e is not None:
                oc = classify_warning_outcome(e, r["onset"], 100, args.grace_blocks)
                c = {"horizon_valid_forecast": "pre_onset_detection",
                     "extended_pre_onset_alert": "pre_onset_detection",
                     "onset_detection": "at_onset_detection",
                     "post_onset_confirmation": "post_onset_detection",
                     "no_warning": "no_detection"}[oc.outcome]
                if oc.outcome == "horizon_valid_forecast":
                    cats.setdefault("horizon_valid_forecast", 0)
                    cats["horizon_valid_forecast"] += 1
            cats[c] += 1
            if e is not None:
                leads.append(r["onset"] - e)
        out["outcome_counts"] = cats
        out["sensitivity"] = wilson_interval(
            cats["pre_onset_detection"] + cats["at_onset_detection"] + cats["post_onset_detection"],
            len(attacks)).to_dict()
        out["pre_onset_only"] = wilson_interval(cats["pre_onset_detection"], len(attacks)).to_dict()
        out["lead_blocks"] = {
            "median": float(np.median(leads)) if leads else None,
            "min": float(min(leads)) if leads else None,
            "max": float(max(leads)) if leads else None,
            "n": len(leads),
        }
        if system == "forecaster":
            out["horizon_valid_rate"] = wilson_interval(
                out["outcome_counts"].get("horizon_valid_forecast", 0), len(attacks)).to_dict()
        return out

    comparison = {"detector_calibration": cal.to_dict(), "partitions": {}}
    for part in list(partitions) + ["all"]:
        p = None if part == "all" else part
        entry = {
            "detector": _summarize("detector",
                                   lambda r: r["detector_first_emission"], p),
            "forecaster_frozen_thr0.5": _summarize(
                "forecaster", lambda r: r["forecaster_first_emission"]["0.5"], p),
        }
        comparison["partitions"][part] = entry

    # matched-budget sweep on G1 benign -> choose the forecaster threshold whose
    # G1 benign FPR is closest to the detector's G1 benign FPR
    g1 = [r for r in per_scenario if r["partition"] == "g1"]
    g1_benign = [r for r in g1 if r["onset"] < 0]
    det_fpr = (sum(1 for r in g1_benign if r["detector_first_emission"] is not None)
               / max(len(g1_benign), 1))
    sweep = {}
    for thr in ("0.5", "0.7", "0.8", "0.9", "0.95"):
        fired = sum(1 for r in g1_benign
                    if r["forecaster_first_emission"][thr] is not None)
        fpr = fired / max(len(g1_benign), 1)
        sweep[thr] = {"g1_benign_fpr": fpr,
                      "summaries": {
                          "g1": _summarize("forecaster",
                                           lambda r, t=thr: r["forecaster_first_emission"][t],
                                           "g1"),
                          "all": _summarize("forecaster",
                                            lambda r, t=thr: r["forecaster_first_emission"][t],
                                            None)},
                      }
    best_thr = min(sweep, key=lambda t: abs(sweep[t]["g1_benign_fpr"] - det_fpr))
    comparison["matched_budget"] = {
        "detector_g1_benign_fpr": det_fpr,
        "chosen_forecaster_threshold": best_thr,
        "chosen_forecaster_g1_benign_fpr": sweep[best_thr]["g1_benign_fpr"],
        "sweep": sweep,
        "note": ("thresholds are compared on G1 benign only for budget matching; "
                 "attack results at each threshold are reported for transparency "
                 "and are not used to select the detector operating point"),
    }
    comparison["scenario_table"] = per_scenario
    comparison["runtime_seconds"] = round(time.time() - t0, 1)

    out_file = out_dir / "conventional_comparison.json"
    out_file.write_text(json.dumps(comparison, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {out_file}")
    print("\n=== SUMMARY (all partitions) ===")
    for name, getter in (("detector", "detector"),
                         ("forecaster_0.5", "forecaster_frozen_thr0.5")):
        e = comparison["partitions"]["all"][getter]
        print(f"{name:16s} benign FPR={e['benign_false_alarm_rate']['point']:.3f} "
              f"[{e['benign_false_alarm_rate']['ci_low']:.3f},{e['benign_false_alarm_rate']['ci_high']:.3f}] "
              f"sensitivity={e['sensitivity']['point']:.3f} "
              f"pre-onset={e['pre_onset_only']['point']:.3f} "
              f"median lead={e['lead_blocks']['median']}")


if __name__ == "__main__":
    main()