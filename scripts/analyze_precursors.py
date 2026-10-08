"""Phase 1 statistical precursor analysis (master prompt §36/§37).

Questions:
  1. Do any candidate telemetry variables actually move BEFORE attack onset?
  2. Is that movement distinguishable from benign drift (matched counterfactuals)?

For each attack type with precursors (A/B), compares across ALL seeds:
  - attack run pre-precursor / precursor / active periods
  - matched benign run (same seed) same periods
  - effect size: mean shift in sigma units of the benign baseline
Classifies each feature into Categories 1-4 (master prompt §37).

Run: python scripts/analyze_precursors.py [--data data/phase1] [--out docs/precursor-analysis.md]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

# candidate features inspected (telemetry columns; docs/telemetry-spec.md)
CANDIDATES = [
    "lo_power", "lo_sig_ratio", "x_var", "p_var", "quad_std_ratio",
    "transmittance", "excess_noise", "background", "snr", "skr_estimate",
    "det_gain", "det_offset", "det_imbalance", "saturation_frac",
    "qber_proxy", "xp_corr", "clock_offset_ns", "temperature", "skr_drift",
]


def effect_size(attack_vals: np.ndarray, benign_vals: np.ndarray) -> float:
    """Mean shift in sigma units of the benign baseline (Cohen's d style)."""
    b_std = benign_vals.std()
    if b_std < 1e-12:
        b_std = 1e-12
    return (attack_vals.mean() - benign_vals.mean()) / b_std


def analyze_attack(df_atk: pd.DataFrame, df_ben: pd.DataFrame, meta: dict) -> dict:
    """Per-attack precursor analysis across one matched pair."""
    onset = int(meta["attack_onset"])
    ps = int(meta["precursor_start"])
    pclass = meta["precursor_class"]
    results = {}
    for col in CANDIDATES:
        a = df_atk[col].values.astype(float)
        b = df_ben[col].values.astype(float)
        n = min(len(a), len(b))
        a, b = a[:n], b[:n]

        # periods (attack run): pre-precursor, precursor, active
        pre_mask = np.arange(n) < ps
        prec_mask = (np.arange(n) >= ps) & (np.arange(n) < onset)
        atk_mask = np.arange(n) >= onset

        # benign baseline: matched benign run pre-precursor period (same conditions)
        base_vals = b[pre_mask] if pre_mask.sum() > 5 else b[: max(5, n // 10)]

        entry = {
            "precursor_class": pclass,
            "pre_precursor_eff": round(effect_size(a[pre_mask], base_vals), 3) if pre_mask.sum() > 2 else None,
            "precursor_eff": round(effect_size(a[prec_mask], base_vals), 3) if prec_mask.sum() > 2 else None,
            "active_eff": round(effect_size(a[atk_mask], base_vals), 3) if atk_mask.sum() > 2 else None,
            # benign drift magnitude over the SAME window (drift-only change)
            "benign_drift_eff": round(effect_size(b[prec_mask], base_vals), 3) if prec_mask.sum() > 2 else None,
        }
        results[col] = entry
    return results


def categorize(entry: dict) -> int:
    """Category per master prompt §37:
    1 = moves meaningfully before onset (|precursor_eff| >= 1)
    2 = only moves once attack begins (|active_eff| >= 1, |precursor_eff| < 1)
    3 = also moves similarly during benign drift (|benign_drift_eff| >= 1)
    4 = no meaningful signal
    """
    pe, ae, be = entry["precursor_eff"], entry["active_eff"], entry["benign_drift_eff"]
    pe = abs(pe) if pe is not None else 0.0
    ae = abs(ae) if ae is not None else 0.0
    be = abs(be) if be is not None else 0.0
    if pe >= 1.0:
        return 1
    if ae >= 1.0:
        return 2
    if be >= 1.0:
        return 3
    return 4


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(REPO / "data" / "phase1"))
    parser.add_argument("--out", default=str(REPO / "docs" / "precursor-analysis.md"))
    args = parser.parse_args(argv)

    data_dir = Path(args.data)
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))

    # group scenarios: matched pairs (attack + normal arm, same pair_id/seed)
    pairs = {}
    benign_unmatched = []
    for s in manifest["scenarios"]:
        if s["pair_id"]:
            key = (s["pair_id"], s["seed"])
            pairs.setdefault(key, {})[s["arm"]] = s
        elif s["attack_type"] == "none":
            benign_unmatched.append(s)

    per_attack: dict[str, list] = {}
    for (pair_id, seed), arms in sorted(pairs.items()):
        if "attack" not in arms or "normal" not in arms:
            continue
        a_spec, b_spec = arms["attack"], arms["normal"]
        df_a = pd.read_parquet(data_dir / f"{a_spec['scenario_id']}.parquet")
        df_b = pd.read_parquet(data_dir / f"{b_spec['scenario_id']}.parquet")
        atype = a_spec["attack_type"]
        r = analyze_attack(df_a, df_b, a_spec)
        per_attack.setdefault(atype, []).append((seed, r))

    # aggregate across seeds: median effect sizes per attack/feature
    lines = [
        "# Phase 1 Precursor Analysis",
        "",
        f"Generated 2026-10-08 from `{args.data}` (all seeds; matched counterfactual pairs).",
        "Effect sizes = mean shift in sigma units of the matched benign baseline",
        "(pre-precursor period of the paired benign run). Categories (master prompt §37):",
        "1 = moves before onset · 2 = only at attack · 3 = also moves in benign drift · 4 = no signal.",
        "",
    ]
    summary_table = []
    for atype, runs in sorted(per_attack.items()):
        lines.append(f"## {atype} ({len(runs)} seeds)")
        lines.append("")
        lines.append("| Feature | Class | pre-precursor | precursor | active | benign drift | Category |")
        lines.append("|---|---|---|---|---|---|---|")
        cats = []
        for col in CANDIDATES:
            entries = [r[col] for _, r in runs if col in r]
            if not entries:
                continue
            med = {
                "precursor_class": entries[0]["precursor_class"],
                "pre_precursor_eff": float(np.median([e["pre_precursor_eff"] or 0 for e in entries])),
                "precursor_eff": float(np.median([e["precursor_eff"] or 0 for e in entries])),
                "active_eff": float(np.median([e["active_eff"] or 0 for e in entries])),
                "benign_drift_eff": float(np.median([e["benign_drift_eff"] or 0 for e in entries])),
            }
            cat = categorize(med)
            cats.append((col, cat, med))
            lines.append(
                f"| {col} | {med['precursor_class']} | {med['pre_precursor_eff']:.2f} | "
                f"{med['precursor_eff']:.2f} | {med['active_eff']:.2f} | "
                f"{med['benign_drift_eff']:.2f} | {cat} |"
            )
        lines.append("")
        n1 = sum(1 for _, c, _ in cats if c == 1)
        n2 = sum(1 for _, c, _ in cats if c == 2)
        n3 = sum(1 for _, c, _ in cats if c == 3)
        n4 = sum(1 for _, c, _ in cats if c == 4)
        lines.append(
            f"Category counts: **Cat1 (pre-onset signal): {n1} · Cat2 (attack-only): {n2} · "
            f"Cat3 (confounded with drift): {n3} · Cat4 (no signal): {n4}**"
        )
        lines.append("")
        for col, cat, med in cats:
            summary_table.append((atype, col, cat, med))

    # overall summary
    lines.append("## Summary across attacks")
    lines.append("")
    lines.append("| Attack | Features with pre-onset signal (Cat1) | Confusable with drift (Cat3) |")
    lines.append("|---|---|---|")
    for atype in sorted(per_attack):
        rows = [t for t in summary_table if t[0] == atype]
        n1 = [t[1] for t in rows if t[2] == 1]
        n3 = [t[1] for t in rows if t[2] == 3]
        lines.append(f"| {atype} | {', '.join(n1) if n1 else '—'} | {', '.join(n3) if n3 else '—'} |")
    lines.append("")

    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out}")
    # console summary
    for atype in sorted(per_attack):
        rows = [t for t in summary_table if t[0] == atype]
        n1 = [t[1] for t in rows if t[2] == 1]
        print(f"{atype}: Cat1 features = {n1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
