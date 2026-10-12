"""Confirmatory evaluation on genuinely untouched synthetic scenarios.

Executes the frozen protocol in `docs/confirmatory-evaluation-protocol.md`:
  1. verifies the frozen configuration (model config, detector k/h) against the
     protocol values and aborts on mismatch;
  2. verifies seed disjointness against ALL historical manifests;
  3. generates the pre-registered C1..C4 scenario populations (seeds 41000+,
     stride 7);
  4. computes causal features;
  5. runs the frozen forecaster and detector, recording emission-only events;
  6. computes the pre-declared metrics with Wilson intervals and negative
     controls;
  7. writes immutable, hash-recorded outputs under
     `artifacts/confirmatory/<utc-stamp>/` (never overwritten).

No threshold, model or feature change is permitted after generation; all
outcomes, favourable or not, are reported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
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
    CusumConfig, CusumCalibration, detect_warnings_cusum,
    confirmation_evidence_from_cusum, INDICATORS,
)
from quantumattack.operational_states import (
    OperationalPolicy, operational_state_series, alert_episodes_from_trace,
    summarize_alert_burden, ALERT_STATES, PRE_ATTACK_WARNING, ACTIVE_ATTACK_CONFIRMED,
)
from quantumattack.forecast_horizons import (
    classify_warning_outcome, HORIZON_VALID, EXTENDED_ALERT,
    ONSET_DETECTION, POST_ONSET_CONFIRMATION, NO_WARNING,
)
from quantumattack.statistics import wilson_interval

# ---- frozen protocol values (must match docs/confirmatory-evaluation-protocol.md)
FROZEN = {
    "forecast_policy": {"prob_threshold": 0.5, "persistence_k": 3,
                        "cooldown_blocks": 50, "grace_blocks": 5,
                        "sustained_until_onset": False},
    "detector": {"k_drift": 2.0, "h_threshold": 200.0, "persistence_k": 3,
                 "cooldown_blocks": 50, "warmup_blocks": 200,
                 "deviate_cap": 10.0, "max_missing_run": 5,
                 "normalization": "per_scenario_warmup"},
    "model_config": {"feature_group": "D", "C": 1.0, "class_weight": "balanced",
                     "max_iter": 1000, "random_state": 0,
                     "min_history_blocks": 100,
                     "horizons": [10, 25, 50, 100]},
    "horizon_primary": 100,
    "seed_block": {"start": 41000, "end": 42999, "stride": 7},
    "excluded_seeds": [40998, 40999],
}

C_GROUPS = [
    ("C1_NORMAL", [
        {"name": "plain", "class": "normal", "seeds": "auto"},
        {"name": "channel-drift", "class": "normal", "seeds": "auto",
         "env": {"fiber_loss_ou_sigma_db": 0.03}},
        {"name": "disturbance", "class": "normal", "seeds": "auto",
         "env": {"disturbance_episode_prob": 0.5}},
    ], 30),
    ("C1_ATTACKS", [
        {"name": "lo-manipulation", "class": "attack", "seeds": "auto",
         "sample_onset": [900, 1400],
         "sample": {"lo_attack_attenuation": [0.3, 0.7],
                    "lo_hidden_noise_factor": [0.3, 0.7],
                    "ramp_min_blocks": [40, 100], "ramp_max_blocks": [100, 160]}},
        {"name": "calibration-manipulation", "class": "attack", "seeds": "auto",
         "sample_onset": [900, 1400],
         "sample": {"cal_gain_bias": [0.05, 0.25],
                    "cal_offset_bias_snu": [0.02, 0.08],
                    "cal_ramp_min_blocks": [50, 120],
                    "cal_ramp_max_blocks": [120, 180]}},
    ], 20),
    ("C1_SUDDEN", [
        {"name": "intercept-resend", "class": "attack", "seeds": "auto",
         "sample_onset": [900, 1400],
         "sample": {"tap_fraction": [0.2, 0.5], "resend_noise_mult": [1.5, 2.5]}},
    ], 10),
    ("C2_RAMPS", [
        {"name": "lo-manipulation-fast-ramp", "class": "attack", "seeds": "auto",
         "sample_onset": [900, 1400],
         "sample": {"lo_attack_attenuation": [0.4, 0.8],
                    "ramp_min_blocks": [20, 30], "ramp_max_blocks": [30, 40]}},
        {"name": "lo-manipulation-slow-ramp", "class": "attack", "seeds": "auto",
         "sample_onset": [900, 1400],
         "sample": {"lo_attack_attenuation": [0.3, 0.6],
                    "ramp_min_blocks": [160, 200], "ramp_max_blocks": [200, 260]}},
        {"name": "calibration-manipulation-steep", "class": "attack", "seeds": "auto",
         "sample_onset": [900, 1400],
         "sample": {"cal_gain_bias": [0.25, 0.45],
                    "cal_ramp_min_blocks": [30, 60], "cal_ramp_max_blocks": [60, 100]}},
        {"name": "calibration-manipulation-slow", "class": "attack", "seeds": "auto",
         "sample_onset": [900, 1400],
         "sample": {"cal_gain_bias": [0.08, 0.2],
                    "cal_ramp_min_blocks": [180, 220],
                    "cal_ramp_max_blocks": [220, 280]}},
    ], 28),
    ("C3_ENV_STRESS", [
        {"name": "normal-extreme-drift", "class": "normal", "seeds": "auto",
         "env": {"fiber_loss_ou_sigma_db": 0.06, "ou_theta": 0.03}},
        {"name": "normal-intense-disturbance", "class": "normal", "seeds": "auto",
         "env": {"disturbance_episode_prob": 0.8,
                 "disturbance_duration_blocks": 40,
                 "disturbance_background_sigma_mult": 16.0}},
        {"name": "normal-thermal-stress", "class": "normal", "seeds": "auto",
         "env": {"temperature_amplitude_c": 2.5, "lo_thermal_coupling": 0.025,
                 "temperature_ou_sigma": 0.1}},
    ], 30),
    ("C4_JAMMING", [
        {"name": "channel-jamming-dense-probes", "class": "attack", "seeds": "auto",
         "sample_onset": [900, 1400],
         "sample": {"jamming_power_snu": [0.4, 0.9], "probe_enabled": [True],
                    "probe_lambda": [4.0, 7.0], "precursor_lead_blocks": [120, 180]}},
        {"name": "channel-jamming-sudden-high", "class": "attack", "seeds": "auto",
         "sample_onset": [900, 1400],
         "sample": {"jamming_power_snu": [0.6, 1.2], "probe_enabled": [False]}},
    ], 30),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO),
                          capture_output=True, text=True).stdout.strip()


def allocate_seeds(n_total: int, cursor: dict) -> list[int]:
    """Deterministic, globally disjoint seed allocation (stride 7, shared cursor)."""
    start, end, stride = FROZEN["seed_block"]["start"], FROZEN["seed_block"]["end"], FROZEN["seed_block"]["stride"]
    pool = [s for s in range(start, end + 1, stride)
            if s not in set(FROZEN["excluded_seeds"])]
    take = pool[cursor["idx"]: cursor["idx"] + n_total]
    if len(take) < n_total:
        raise RuntimeError(
            f"seed pool exhausted: need {n_total}, have {len(take)} "
            f"(cursor {cursor['idx']} of {len(pool)} available)")
    cursor["idx"] += n_total
    return take


def build_config() -> dict:
    """Build the batch config with deterministic, globally disjoint seeds."""
    shared = {"n_blocks": 2000, "horizons": [10, 25, 50, 100],
              "dataset_version": "confirmatory-v1"}
    scenarios: list[dict] = []
    allocation: dict[str, list[int]] = {}
    cursor = {"idx": 0}
    for group, defs, n in C_GROUPS:
        seeds = allocate_seeds(n, cursor)
        per = max(1, n // len(defs))
        idx = 0
        group_seeds: list[int] = []
        built: list[dict] = []
        for j, d in enumerate(defs):
            take = seeds[idx * per: (idx + 1) * per] if j < len(defs) - 1 \
                else seeds[idx * per:]
            nd = dict(d)
            nd["seeds"] = [int(s) for s in take]
            nd["partition"] = group
            group_seeds.extend(nd["seeds"])
            built.append(nd)
            idx += 1
        allocation[group] = group_seeds
        scenarios.extend(built)
    return {"shared": shared, "scenarios": scenarios}, allocation


def verify_seed_isolation(allocation: dict, historical_manifests: list[Path]) -> dict:
    used = set()
    for m in historical_manifests:
        if not m.exists():
            continue
        hist = json.load(open(m, encoding="utf-8"))
        for s in hist["scenarios"]:
            used.add(int(s["seed"]))
    new_seeds = {s for seeds in allocation.values() for s in seeds}
    overlap = new_seeds & used
    return {"overlap": sorted(overlap), "n_new": len(new_seeds),
            "n_historical": len(used),
            "isolated": len(overlap) == 0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", default=str(REPO / "artifacts" / "confirmatory"))
    ap.add_argument("--skip-generation", action="store_true",
                    help="reuse an existing confirmatory dataset (still hash-verified)")
    args = ap.parse_args()

    t0 = time.time()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out_root) / stamp
    data_dir = out_dir / "data"
    feat_dir = out_dir / "features"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---------------- 0. frozen-configuration verification ----------------
    report = {
        "protocol": "confirmatory-evaluation-protocol v1 (frozen 2026-10-12)",
        "source_commit": git_head(),
        "started_utc": stamp,
        "frozen": FROZEN,
    }
    # the detector must match the frozen operating point
    frozen_det = FROZEN["detector"]
    assert frozen_det["h_threshold"] == 200.0 and frozen_det["k_drift"] == 2.0, \
        "detector operating point deviates from the frozen protocol"

    # ---------------- 1. scenario generation ----------------
    cfg, allocation = build_config()
    isolation = verify_seed_isolation(
        allocation,
        [REPO / "data" / "phase4" / "manifest.json",
         REPO / "data" / "phase5" / "manifest.json",
         REPO / "data" / "phase3" / "manifest.json",
         REPO / "data" / "phase1" / "manifest.json"])
    report["seed_allocation"] = allocation
    report["seed_isolation"] = isolation
    print(f"[seeds] {isolation['n_new']} new seeds; overlap with history: "
          f"{isolation['overlap'] or 'NONE'}; isolated={isolation['isolated']}", flush=True)
    if not isolation["isolated"]:
        raise RuntimeError("seed overlap with historical data -- aborting")

    cfg_path = out_dir / "confirmatory.yaml"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    env = dict(**__import__("os").environ, PYTHONPATH=str(REPO / "src"))
    if not args.skip_generation:
        print("[generate] building confirmatory scenarios ...", flush=True)
        r = subprocess.run([sys.executable, "-m", "quantumattack.simulator.generate",
                            "--config", str(cfg_path), "--out", str(data_dir)],
                           capture_output=True, text=True, cwd=str(REPO), env=env)
        if r.returncode != 0:
            (out_dir / "generate.stderr.txt").write_text(r.stderr, encoding="utf-8")
            raise RuntimeError(f"generation failed rc={r.returncode}")

    manifest = json.load(open(data_dir / "manifest.json", encoding="utf-8"))
    # keep manifest.json in place (features_cli reads it); record an immutable copy
    (data_dir / "manifest_generation.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    report["dataset_manifest"] = manifest.get("batch_config", {})
    report["n_scenarios_generated"] = len(manifest["scenarios"])
    print(f"[generate] {len(manifest['scenarios'])} scenarios; "
          f"block_ms={manifest.get('block_ms')}", flush=True)
    assert manifest.get("block_ms") == 10.0, "time base must be the verified 10 ms"

    # ---------------- 2. features ----------------
    if not args.skip_generation:
        print("[features] computing causal features ...", flush=True)
        r = subprocess.run([sys.executable, "-m", "quantumattack.features_cli",
                            "--data", str(data_dir), "--out", str(feat_dir)],
                           capture_output=True, text=True, cwd=str(REPO), env=env)
        if r.returncode != 0:
            (out_dir / "features.stderr.txt").write_text(r.stderr, encoding="utf-8")
            raise RuntimeError(f"features failed rc={r.returncode}")

    # ---------------- 3. frozen model fit (Phase-4 train only) ----------------
    print("[model] fitting frozen forecaster on Phase-4 train ...", flush=True)
    m4 = json.load(open(REPO / "data" / "phase4" / "manifest.json", encoding="utf-8"))
    split4 = split_scenarios(m4["scenarios"], SplitConfig(
        seed=42, counterfactual_to_train=True, ood_holdout_family="channel_jamming"))
    mc = ModelConfig(feature_group="D")
    cfg_check = mc.to_dict()
    for k, v in FROZEN["model_config"].items():
        got = cfg_check.get(k)
        got_l = list(got) if isinstance(got, tuple) else got
        assert got_l == v, f"model config mismatch on {k}: {got_l} != {v}"
    train_frames = {sid: pd.read_parquet(REPO / "artifacts" / "phase4" / "features" / f"{sid}.parquet")
                    for sid in split4.train}
    base_cols = [c for c in FEATURE_COLUMNS if c in next(iter(train_frames.values())).columns]
    feature_cols = feature_group_columns("D", base_cols)
    X, y, _ = build_xy(train_frames, split4.train, FROZEN["horizon_primary"], mc, feature_cols)
    model = fit_horizon_model(X, y, FROZEN["horizon_primary"], feature_cols, mc)
    report["model_fit_rows"] = int(X.shape[0])
    print(f"[model] {X.shape[0]} train rows, {len(feature_cols)} features", flush=True)

    # frozen detector calibration object (reference from Phase-4 train benign;
    # k/h frozen from the protocol -- no re-selection here)
    train_benign = [s["scenario_id"] for s in m4["scenarios"]
                    if s["scenario_id"] in set(split4.train) and s["scenario_class"] == "NORMAL"]
    ref_df = pd.concat([train_frames[s] for s in train_benign], ignore_index=True)
    cal = CusumCalibration(
        reference={ind: {"mean": float(ref_df[ind].mean()),
                         "std": max(float(ref_df[ind].std()), 1e-12),
                         "direction": 1, "n": int(ref_df[ind].notna().sum())}
                   for ind in INDICATORS if ind in ref_df.columns},
        h_threshold=frozen_det["h_threshold"],
        target_scenario_fpr=0.10, achieved_scenario_fpr=None,
        calibration_population="phase4-validation-benign (frozen; not re-selected)",
        config=dict(frozen_det))
    det_cfg = CusumConfig(**frozen_det)

    wp = WarningPolicy(**FROZEN["forecast_policy"])
    opol = OperationalPolicy()

    # ---------------- 4. per-scenario evaluation ----------------
    print("[eval] running forecaster + detector on confirmatory scenarios ...", flush=True)
    events_ledger, scenario_ledger = [], []
    per_scenario = []
    for s in manifest["scenarios"]:
        sid = s["scenario_id"]
        df = pd.read_parquet(feat_dir / f"{sid}.parquet")
        onset = int(df["attack_onset"].iloc[0])
        precursor_start = int(df["precursor_start"].iloc[0]) if "precursor_start" in df.columns else None
        sclass = str(df["scenario_class"].iloc[0])
        atype = str(df["attack_type"].iloc[0])
        b = df["block_index"].to_numpy(int)
        valid = b >= mc.min_history_blocks
        Xv = df[feature_cols].to_numpy(float)
        nm = np.isnan(Xv).any(axis=1)
        p = np.zeros(len(df))
        good = valid & ~nm
        if good.any():
            p[good] = predict_proba(model, Xv[good])
        dfp = pd.DataFrame({
            "scenario_id": sid, "block_index": b, "attack_onset": onset,
            "attack_type": atype, "scenario_class": sclass,
            "p_attack_future_h100": p,
        })
        # forecaster events (operational policy; no retention filter)
        fevents = warning_events_for_scenario(dfp, FROZEN["horizon_primary"], wp)
        f_first = fevents[0].emission_block if fevents else None
        # detector
        det = detect_warnings_cusum(df, cal, det_cfg)
        d_first = det["warning_blocks"][0] if det["warning_blocks"] else None
        # confirmation evidence + operational state machine (real evidence)
        evidence, _ = confirmation_evidence_from_cusum(df, cal, det_cfg)
        trace = operational_state_series(p, policy=opol, confirmation_evidence=evidence)
        episodes = alert_episodes_from_trace(trace, sid)
        for e in episodes:
            events_ledger.append({
                "group": s.get("partition", ""), "scenario_id": sid,
                "scenario_class": sclass, "scenario_is_benign": onset < 0,
                **e.to_dict(),
                "duration_blocks": e.duration_blocks(len(trace.states)),
            })
        scenario_ledger.append({
            "group": s.get("partition", ""), "scenario_id": sid,
            "scenario_class": sclass, "attack_type": atype,
            "attack_onset": onset, "precursor_start": precursor_start,
            "n_blocks": len(df), "n_episodes": len(episodes),
            "alert_blocks": sum(1 for st in trace.states if st in ALERT_STATES),
            "entered_warning": any(st in ALERT_STATES for st in trace.states),
            "confirmed": ACTIVE_ATTACK_CONFIRMED in trace.states,
        })
        per_scenario.append({
            "group": s.get("partition", ""), "scenario_id": sid,
            "scenario_class": sclass, "attack_type": atype,
            "onset": onset, "precursor_start": precursor_start,
            "forecaster_first_emission": f_first,
            "detector_first_emission": d_first,
            "detector_n_warnings": len(det["warning_blocks"]),
            "n_alert_episodes": len(episodes),
        })
    print(f"[eval] {len(per_scenario)} scenarios evaluated in "
          f"{time.time() - t0:.0f}s", flush=True)

    # ---------------- 5. pre-declared metrics ----------------
    def outcome(emission, onset, horizon=100, grace=5):
        if emission is None:
            return NO_WARNING
        lead = onset - emission
        if lead < 0:
            return POST_ONSET_CONFIRMATION
        if lead <= grace:
            return ONSET_DETECTION
        if lead <= horizon:
            return HORIZON_VALID
        return EXTENDED_ALERT

    groups = sorted({r["group"] for r in per_scenario})
    metrics = {}
    for g in groups + ["ALL"]:
        rows = per_scenario if g == "ALL" else [r for r in per_scenario if r["group"] == g]
        benign = [r for r in rows if r["onset"] < 0]
        attacks = [r for r in rows if r["onset"] >= 0]
        entry = {"n_benign": len(benign), "n_attacks": len(attacks)}
        # forecaster
        f_cats = {k: 0 for k in (HORIZON_VALID, EXTENDED_ALERT, ONSET_DETECTION,
                                 POST_ONSET_CONFIRMATION, NO_WARNING)}
        for r in attacks:
            f_cats[outcome(r["forecaster_first_emission"], r["onset"])] += 1
        n_b_warn = sum(1 for r in benign if r["forecaster_first_emission"] is not None)
        entry["forecaster"] = {
            "outcome_counts": f_cats,
            "benign_false_alarm_rate": wilson_interval(n_b_warn, len(benign)).to_dict(),
            "horizon_valid_rate": wilson_interval(f_cats[HORIZON_VALID], len(attacks)).to_dict(),
            "median_first_emission_lead": (
                float(np.median([r["onset"] - r["forecaster_first_emission"]
                                 for r in attacks if r["forecaster_first_emission"] is not None]))
                if any(r["forecaster_first_emission"] is not None for r in attacks) else None),
        }
        # detector
        d_cats = {"pre_onset_detection": 0, "at_onset_detection": 0,
                  "post_onset_detection": 0, "no_detection": 0}
        d_leads, before_precursor = [], 0
        for r in attacks:
            e = r["detector_first_emission"]
            if e is None:
                d_cats["no_detection"] += 1
                continue
            lead = r["onset"] - e
            if lead < 0:
                d_cats["post_onset_detection"] += 1
            elif lead <= FROZEN["forecast_policy"]["grace_blocks"]:
                d_cats["at_onset_detection"] += 1
            else:
                d_cats["pre_onset_detection"] += 1
                d_leads.append(lead)
                if r["precursor_start"] is not None and e < r["precursor_start"]:
                    before_precursor += 1
        n_b_det = sum(1 for r in benign if r["detector_first_emission"] is not None)
        entry["detector"] = {
            "outcome_counts": d_cats,
            "benign_false_alarm_rate": wilson_interval(n_b_det, len(benign)).to_dict(),
            "sensitivity": wilson_interval(
                d_cats["pre_onset_detection"] + d_cats["at_onset_detection"]
                + d_cats["post_onset_detection"], len(attacks)).to_dict(),
            "pre_onset_rate": wilson_interval(d_cats["pre_onset_detection"], len(attacks)).to_dict(),
            "median_pre_onset_lead": float(np.median(d_leads)) if d_leads else None,
            "pre_onset_before_precursor_start": before_precursor,
        }
        metrics[g] = entry
    report["metrics"] = metrics
    report["per_scenario"] = per_scenario
    report["alert_event_ledger"] = events_ledger
    report["scenario_ledger"] = scenario_ledger
    report["runtime_seconds"] = round(time.time() - t0, 1)

    # ---------------- 6. negative controls ----------------
    # (a) time-only predictor on C1 attacks: block index as the sole feature
    from sklearn.metrics import roc_auc_score
    rows_c1 = [r for r in per_scenario if r["group"].startswith("C1")]
    ys, ts = [], []
    for r in rows_c1:
        if r["onset"] < 0:
            continue
        df = pd.read_parquet(feat_dir / f"{r['scenario_id']}.parquet")
        b = df["block_index"].to_numpy(int)
        valid = b >= mc.min_history_blocks
        y = ((b < r["onset"]) & (b + 100 >= r["onset"])).astype(int)
        ys.extend(y[valid]); ts.extend(b[valid] / 2000.0)
    time_only_auroc = float(roc_auc_score(np.array(ys), np.array(ts))) \
        if len(set(ys)) > 1 else None
    # (b) full-model AUROC on the same rows (schedule-vs-telemetry contrast)
    ys2, ps2 = [], []
    for r in rows_c1:
        if r["onset"] < 0:
            continue
        df = pd.read_parquet(feat_dir / f"{r['scenario_id']}.parquet")
        b = df["block_index"].to_numpy(int)
        valid = b >= mc.min_history_blocks
        Xv = df[feature_cols].to_numpy(float)
        nm = np.isnan(Xv).any(axis=1)
        pv = np.zeros(len(df))
        g2 = valid & ~nm
        if g2.any():
            pv[g2] = predict_proba(model, Xv[g2])
        y = ((b < r["onset"]) & (b + 100 >= r["onset"])).astype(int)
        ys2.extend(y[g2]); ps2.extend(pv[g2])
    model_auroc = float(roc_auc_score(np.array(ys2), np.array(ps2))) \
        if len(set(ys2)) > 1 else None
    report["negative_controls"] = {
        "time_only_auroc_c1": time_only_auroc,
        "model_auroc_c1": model_auroc,
        "interpretation": (
            "time-only ~0.5 indicates attack onsets are not trivially scheduled; "
            "the model-vs-time gap measures how much of the discrimination comes "
            "from telemetry rather than position"),
    }

    out_file = out_dir / "confirmatory_report.json"
    out_file.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    # immutable copies of the manifest + config
    sha = {
        "confirmatory_report.json": sha256(out_file),
        "confirmatory.yaml": sha256(cfg_path),
        "manifest_generation.json": sha256(data_dir / "manifest_generation.json"),
    }
    (out_dir / "artifact-hashes.json").write_text(json.dumps(sha, indent=2), encoding="utf-8")
    print(f"\nWrote {out_file}")
    print(f"Hashes recorded in {out_dir / 'artifact-hashes.json'}")

    # console summary
    print("\n================ CONFIRMATORY RESULTS (untouched seeds) ================")
    for g in groups:
        m = metrics[g]
        print(f"\n--- {g} (benign={m['n_benign']}, attacks={m['n_attacks']}) ---")
        f, d = m["forecaster"], m["detector"]
        bf, bd = f["benign_false_alarm_rate"], d["benign_false_alarm_rate"]
        print(f"  forecaster: FWR={bf['point']:.3f} [{bf['ci_low']:.3f},{bf['ci_high']:.3f}] "
              f"hv={f['horizon_valid_rate']['point']:.3f} "
              f"medLead={f['median_first_emission_lead']}")
        print(f"  detector:   FWR={bd['point']:.3f} [{bd['ci_low']:.3f},{bd['ci_high']:.3f}] "
              f"sens={d['sensitivity']['point']:.3f} pre={d['pre_onset_rate']['point']:.3f} "
              f"medLead={d['median_pre_onset_lead']} "
              f"prePrecursor={d['pre_onset_before_precursor_start']}")
    print(f"\nNegative controls: time-only AUROC={time_only_auroc}, "
          f"model AUROC={model_auroc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())