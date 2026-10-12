# -*- coding: utf-8 -*-
"""Regroup confirmatory results by the frozen seed allocation and compute the
per-group metrics + negative controls declared in the protocol.

Writes confirmatory_analysis.json into the SAME stamp directory (additive; the
raw run outputs are not modified).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import numpy as np
from quantumattack.statistics import wilson_interval
from quantumattack.forecast_horizons import (
    HORIZON_VALID, EXTENDED_ALERT, ONSET_DETECTION,
    POST_ONSET_CONFIRMATION, NO_WARNING,
)

stamp_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else \
    max((REPO / "artifacts" / "confirmatory").glob("*"), key=lambda p: p.name)
report = json.load(open(stamp_dir / "confirmatory_report.json", encoding="utf-8"))

# seed -> group from the frozen allocation (authoritative)
seed_to_group = {}
for group, seeds in report["seed_allocation"].items():
    for s in seeds:
        seed_to_group[int(s)] = group

def group_of(sid: str) -> str:
    seed = int(sid.rsplit("-s", 1)[1])
    return seed_to_group.get(seed, "UNKNOWN")

per = report["per_scenario"]
for r in per:
    r["group"] = group_of(r["scenario_id"])
groups = sorted({r["group"] for r in per})
print("groups:", {g: sum(1 for r in per if r["group"] == g) for g in groups})


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


analysis = {"stamp": stamp_dir.name, "protocol": report["protocol"],
            "source_commit": report["source_commit"], "groups": {}}
all_rows = per
for g in groups + ["ALL"]:
    rows = all_rows if g == "ALL" else [r for r in all_rows if r["group"] == g]
    benign = [r for r in rows if r["onset"] < 0]
    attacks = [r for r in rows if r["onset"] >= 0]
    entry = {"n_benign": len(benign), "n_attacks": len(attacks)}

    f_cats = {k: 0 for k in (HORIZON_VALID, EXTENDED_ALERT, ONSET_DETECTION,
                             POST_ONSET_CONFIRMATION, NO_WARNING)}
    f_leads = []
    for r in attacks:
        oc = outcome(r["forecaster_first_emission"], r["onset"])
        f_cats[oc] += 1
        if r["forecaster_first_emission"] is not None:
            f_leads.append(r["onset"] - r["forecaster_first_emission"])
    n_bw = sum(1 for r in benign if r["forecaster_first_emission"] is not None)
    entry["forecaster"] = {
        "outcome_counts": f_cats,
        "benign_false_alarm_rate": wilson_interval(n_bw, len(benign)).to_dict(),
        "horizon_valid_rate": wilson_interval(f_cats[HORIZON_VALID], len(attacks)).to_dict(),
        "median_first_emission_lead": float(np.median(f_leads)) if f_leads else None,
        "median_horizon_valid_lead": (
            float(np.median([r["onset"] - r["forecaster_first_emission"]
                             for r in attacks
                             if outcome(r["forecaster_first_emission"], r["onset"]) == HORIZON_VALID]))
            if f_cats[HORIZON_VALID] else None),
    }
    d_cats = {"pre_onset_detection": 0, "at_onset_detection": 0,
              "post_onset_detection": 0, "no_detection": 0}
    d_leads, before_precursor, pre_leads = [], 0, []
    for r in attacks:
        e = r["detector_first_emission"]
        if e is None:
            d_cats["no_detection"] += 1
            continue
        lead = r["onset"] - e
        if lead < 0:
            d_cats["post_onset_detection"] += 1
        elif lead <= 5:
            d_cats["at_onset_detection"] += 1
        else:
            d_cats["pre_onset_detection"] += 1
            d_leads.append(lead)
            pre_leads.append(e)
            if r["precursor_start"] is not None and e < r["precursor_start"]:
                before_precursor += 1
    n_bd = sum(1 for r in benign if r["detector_first_emission"] is not None)
    entry["detector"] = {
        "outcome_counts": d_cats,
        "benign_false_alarm_rate": wilson_interval(n_bd, len(benign)).to_dict(),
        "sensitivity": wilson_interval(
            d_cats["pre_onset_detection"] + d_cats["at_onset_detection"]
            + d_cats["post_onset_detection"], len(attacks)).to_dict(),
        "pre_onset_rate": wilson_interval(d_cats["pre_onset_detection"], len(attacks)).to_dict(),
        "median_pre_onset_lead": float(np.median(d_leads)) if d_leads else None,
        "pre_onset_before_precursor_start": before_precursor,
        "earliest_pre_onset_emission": min(pre_leads) if pre_leads else None,
    }
    # episodes / occupancy from the scenario ledger
    led = [x for x in report["scenario_ledger"]
           if g == "ALL" or group_of(x["scenario_id"]) == g]
    benign_led = [x for x in led if x["attack_onset"] < 0]
    n_eps = sum(x["n_episodes"] for x in benign_led)
    occ = sum(x["alert_blocks"] for x in benign_led)
    tot = sum(x["n_blocks"] for x in benign_led)
    entry["operational_burden_benign"] = {
        "n_episodes": n_eps,
        "episodes_per_1000_seconds": (n_eps / (tot * 0.01) * 1000.0) if tot else None,
        "occupancy_fraction": (occ / tot) if tot else None,
    }
    analysis["groups"][g] = entry

# negative controls on C1 attacks (time-only vs telemetry model)
from sklearn.metrics import roc_auc_score
import pandas as pd
feat_dir = stamp_dir / "features"
m4 = json.load(open(REPO / "data" / "phase4" / "manifest.json", encoding="utf-8"))
from quantumattack.baselines.splits import SplitConfig, split_scenarios
from quantumattack.dataset import FEATURE_COLUMNS
from quantumattack.baselines.logistic import (
    ModelConfig, build_xy, fit_horizon_model, predict_proba, feature_group_columns,
)
split4 = split_scenarios(m4["scenarios"], SplitConfig(
    seed=42, counterfactual_to_train=True, ood_holdout_family="channel_jamming"))
mc = ModelConfig(feature_group="D")
train_frames = {sid: pd.read_parquet(REPO / "artifacts" / "phase4" / "features" / f"{sid}.parquet")
                for sid in split4.train}
base_cols = [c for c in FEATURE_COLUMNS if c in next(iter(train_frames.values())).columns]
feature_cols = feature_group_columns("D", base_cols)
X, y, _ = build_xy(train_frames, split4.train, 100, mc, feature_cols)
model = fit_horizon_model(X, y, 100, feature_cols, mc)

c1_attacks = [r for r in all_rows
              if r["group"].startswith("C1") and r["onset"] >= 0]
ys, ts, ys2, ps2 = [], [], [], []
for r in c1_attacks:
    df = pd.read_parquet(feat_dir / f"{r['scenario_id']}.parquet")
    b = df["block_index"].to_numpy(int)
    valid = b >= 100
    y = ((b < r["onset"]) & (b + 100 >= r["onset"])).astype(int)
    ys.extend(y[valid]); ts.extend(b[valid] / 2000.0)
    Xv = df[feature_cols].to_numpy(float)
    nm = np.isnan(Xv).any(axis=1)
    pv = np.zeros(len(df))
    g2 = valid & ~nm
    if g2.any():
        pv[g2] = predict_proba(model, Xv[g2])
    ys2.extend(y[g2]); ps2.extend(pv[g2])
analysis["negative_controls"] = {
    "n_c1_attack_scenarios": len(c1_attacks),
    "time_only_auroc": float(roc_auc_score(ys, ts)) if len(set(ys)) > 1 else None,
    "model_auroc": float(roc_auc_score(ys2, ps2)) if len(set(ys2)) > 1 else None,
    "interpretation": ("time-only ~0.5 => onsets are not trivially scheduled on the "
                       "untouched population; the model-vs-time gap is telemetry-driven"),
}
# operational state-machine confirmation check (evidence-driven; on ledger)
confirmed = [x for x in report["scenario_ledger"] if x.get("confirmed")]
analysis["confirmations"] = {
    "n_scenarios_confirmed": len(confirmed),
    "note": ("confirmations arise from detector evidence (D-050 contract); "
             "list the first few for inspection"),
    "examples": [x["scenario_id"] for x in confirmed[:8]],
}

out = stamp_dir / "confirmatory_analysis.json"
out.write_text(json.dumps(analysis, indent=2, default=str), encoding="utf-8")
print(f"Wrote {out}")

print("\n================ CONFIRMATORY (regrouped) ================")
for g in groups:
    e = analysis["groups"][g]
    f, d = e["forecaster"], e["detector"]
    bf, bd = f["benign_false_alarm_rate"], d["benign_false_alarm_rate"]
    print(f"\n--- {g} (benign={e['n_benign']}, attacks={e['n_attacks']}) ---")
    print(f"  forecaster: FWR={bf['point']:.3f} [{bf['ci_low']:.3f},{bf['ci_high']:.3f}] "
          f"hv={f['horizon_valid_rate']['point']:.3f} medLead={f['median_first_emission_lead']}")
    print(f"  detector:   FWR={bd['point']:.3f} [{bd['ci_low']:.3f},{bd['ci_high']:.3f}] "
          f"sens={d['sensitivity']['point']:.3f} pre={d['pre_onset_rate']['point']:.3f} "
          f"medLead={d['median_pre_onset_lead']} beforePrecursor={d['pre_onset_before_precursor_start']}")
    b = e["operational_burden_benign"]
    print(f"  benign burden: episodes={b['n_episodes']} "
          f"per1000s={b['episodes_per_1000_seconds'] and round(b['episodes_per_1000_seconds'],1)} "
          f"occupancy={b['occupancy_fraction'] and round(b['occupancy_fraction'],4)}")
nc = analysis["negative_controls"]
print(f"\nNegative controls: time-only AUROC={nc['time_only_auroc']}, "
      f"model AUROC={nc['model_auroc']}")
print(f"Confirmations (evidence-driven): {analysis['confirmations']['n_scenarios_confirmed']}")