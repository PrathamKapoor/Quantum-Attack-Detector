# -*- coding: utf-8 -*-
"""Per-scenario operational audit of the seven named G1 NORMAL scenarios.

Reconstructs, from the FROZEN features + FROZEN model configuration, the full
score and event timeline for each named scenario:

  - first threshold excursion (operational)
  - all qualifying K-runs and their emission blocks (operational policy)
  - the earliest index from which p stays >= threshold to the scenario end
    (this is the condition that v1's sustained retention actually tests)
  - alert episodes / occupancy from the sticky state machine
  - v1-retention verdict per emitted event

Writes artifacts/reliability/evaluation/normal_scenario_audit.json
Does NOT modify frozen artifacts.
"""
from __future__ import annotations
import json
import sys
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
    WarningPolicy, warning_events_for_scenario, retrospective_sustained_retention,
)
from quantumattack.operational_states import (
    operational_state_series, OperationalPolicy, alert_episodes_from_trace,
    PRE_ATTACK_WARNING, ACTIVE_ATTACK_CONFIRMED,
)

NAMED = [
    "normal-plain-s20007", "normal-plain-s20021", "normal-plain-s20042",
    "normal-plain-s20056", "normal-plain-s20063",
    "normal-channel-drift-s20070", "normal-channel-drift-s20133",
]


def main():
    m4 = json.load(open(REPO / "data" / "phase4" / "manifest.json", encoding="utf-8"))
    split4 = split_scenarios(m4["scenarios"], SplitConfig(
        seed=42, counterfactual_to_train=True, ood_holdout_family="channel_jamming"))
    mc = ModelConfig(feature_group="D")
    train_frames = {sid: pd.read_parquet(REPO / "artifacts" / "phase4" / "features" / f"{sid}.parquet")
                    for sid in split4.train}
    base = [c for c in FEATURE_COLUMNS if c in next(iter(train_frames.values())).columns]
    feature_cols = feature_group_columns("D", base)
    X, y, _ = build_xy(train_frames, split4.train, 100, mc, feature_cols)
    model = fit_horizon_model(X, y, 100, feature_cols, mc)

    wp_op = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50,
                          grace_blocks=5, sustained_until_onset=False)
    wp_retro = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50,
                             grace_blocks=5, sustained_until_onset=True)
    opol = OperationalPolicy()

    audit = []
    for sid in NAMED:
        df = pd.read_parquet(REPO / "artifacts" / "phase5" / "features" / f"{sid}.parquet")
        b = df["block_index"].to_numpy(int)
        valid = b >= mc.min_history_blocks
        Xv = df[feature_cols].to_numpy(float)
        nm = np.isnan(Xv).any(axis=1)
        p = np.zeros(len(df))
        good = valid & ~nm
        if good.any():
            p[good] = predict_proba(model, Xv[good])
        above = np.isfinite(p) & (p >= wp_op.prob_threshold)

        # first excursion (operational region)
        first_excursion = int(np.argmax(above)) if above.any() else None

        # all emission events under the operational policy
        dfp = pd.DataFrame({
            "scenario_id": sid, "block_index": b,
            "attack_onset": int(df["attack_onset"].iloc[0]),
            "attack_type": "none", "scenario_class": str(df["scenario_class"].iloc[0]),
            "p_attack_future_h100": p,
        })
        events = warning_events_for_scenario(dfp, 100, wp_op)
        retention = retrospective_sustained_retention(events, dfp, 100, wp_op)

        # final segment: earliest index from which p stays >= threshold to the end
        final_seg_start = None
        for i in range(len(p) - 1, -1, -1):
            if not above[i]:
                break
            final_seg_start = i

        # sticky state machine -> episodes and occupancy
        trace = operational_state_series(p, policy=opol)
        episodes = alert_episodes_from_trace(trace, sid)
        occupancy = sum(1 for s in trace.states if s in (PRE_ATTACK_WARNING, ACTIVE_ATTACK_CONFIRMED))

        audit.append({
            "scenario_id": sid,
            "scenario_class": str(df["scenario_class"].iloc[0]),
            "seed": int(sid.rsplit("-s", 1)[1]),
            "n_blocks": len(df),
            "duration_seconds": len(df) * 0.01,
            "first_threshold_excursion_block": first_excursion,
            "final_contiguous_segment_start": final_seg_start,
            "final_segment_reaches_end": final_seg_start is not None,
            "final_segment_length": (len(df) - final_seg_start) if final_seg_start is not None else 0,
            "n_emitted_events_operational": len(events),
            "emission_blocks": [e.emission_block for e in events],
            "excursion_starts": [e.excursion_start_block for e in events],
            "v1_retention_verdicts": {str(k): bool(v) for k, v in retention.items()},
            "n_v1_retained": int(sum(1 for v in retention.values() if v)),
            "n_alert_episodes": len(episodes),
            "episode_intervals": [[e.enter_block, e.exit_block] for e in episodes],
            "alert_occupancy_blocks": occupancy,
            "alert_occupancy_fraction": occupancy / len(df),
        })

    out = REPO / "artifacts" / "reliability" / "evaluation" / "normal_scenario_audit.json"
    out.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    print()
    hdr = f"{'scenario':34s} {'1stExc':>7s} {'finalSeg':>9s} {'segLen':>7s} {'events':>7s} {'retained':>9s} {'eps':>4s} {'occBlk':>7s}"
    print(hdr)
    for a in audit:
        print(f"{a['scenario_id']:34s} {str(a['first_threshold_excursion_block']):>7s} "
              f"{str(a['final_contiguous_segment_start']):>9s} {a['final_segment_length']:>7d} "
              f"{a['n_emitted_events_operational']:>7d} {a['n_v1_retained']:>9d} "
              f"{a['n_alert_episodes']:>4d} {a['alert_occupancy_blocks']:>7d}")


if __name__ == "__main__":
    main()