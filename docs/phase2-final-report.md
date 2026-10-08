# Phase 2 Final Report — Causal Feature Layer, Forecasting Baselines & Lead-Time Evaluation

Created 2026-10-08. All numbers below are MEASURED (commands and evidence in §9);
nothing is claimed without execution (master prompt §48/§56 of Phase 1).

## Status

**COMPLETE** — all 18 Phase 2 checklist items done and verified.

## Environment

| Package | Version |
|---|---|
| Python | 3.13.14 (Windows Store, not a venv) |
| numpy / pandas | 2.4.4 / 3.0.2 |
| scikit-learn (used this phase) | 1.8.0 |
| pytest / PyYAML | 9.1.1 / 6.0.3 |
| New installs | none (dependency policy §49) |

## Feature layer

Implemented in `src/quantumattack/features.py` (schema v2, 154 derived features):

| Level | Features | Windows (blocks; 1 block = 10 ms) | Causality | Missing-history |
|---|---|---|---|---|
| differences | d1_/d2_ over 13 columns | 2 / 3 | backward differences | NaN t<1 / t<2 |
| rolling | rm{w}_/rv{w}_ over 14 columns | 5, 25, 100 | trailing | NaN until warmup |
| slopes | rs{w}_ over 5 columns | 25, 100 | trailing OLS | NaN until warmup |
| EWMA | ewma{span}_ over 5 columns | 5, 25 | streaming | runs from t=0 |
| CUSUM | pos/neg over 8 columns | ref=100 | μ0/σ0 from FIRST 100 blocks ONLY | NaN until t=100 |
| KS | ks_ over 5 columns | 50 vs 50 | two trailing windows | NaN until t=99 |
| autocorr | ac1_ over 3 columns | 100 | trailing lag-1 | NaN until t=99 |

- Causal policy (D-019): every statistic TRAILING (window ends at t); derivatives
  backward; CUSUM reference = scenario warmup only; missing-history = explicit NaN
  (never zeros, never future samples, never start-padding).
- `FeatureConfig` makes windows/spans/columns configurable (validated).
- Per-feature metadata machine-readable (`feature_metadata()` →
  artifacts/phase2/features/feature_schema.json).

## Baselines

- **Conventional threshold detector** (`baselines/conventional.py`): 7 CV-QKD
  indicators (ε̂, T̂, LO power, det_gain, SKR, saturation, background); qber_proxy
  EXCLUDED (degenerate per Phase 1). Calibration: empirical quantile q=0.995 on
  benign TRAIN portions only (normal-σ 5σ and fixed methods supported). Warning
  policy: k=3 consecutive violations + 50-block cooldown. Missing warnings = null.
- **Logistic regression** (`baselines/logistic.py`): one LogisticRegression per
  horizon (H∈{10,25,50,100}; class_weight=balanced; C=1.0); StandardScaler fit on
  TRAIN only; y_H(t)=1 iff t<onset≤t+H, y_H=0 for t≥onset (§19); rows with t<100
  skipped; ablation groups A/B/C/D; feature memoization (no recomputation).

## Dataset

- Phase 1 dataset (65 scenarios; 5 seeds; 2000 blocks each): 25 ATTACK runs, 35
  NORMAL, 5 BENIGN_DRIFT; ALL attack scenarios are PAIRED (matched benign twins).
- Split (seed 0): train 37 / val 18 / test 10 scenarios; pairs atomic (verified).
- Multi-seed: split seeds 0–3 (4 disjoint partitions).

## Horizon results (TEST, group D, split seed 0)

| Horizon | AUROC | AUPRC | Brier | ECE | Scenario pre-onset warn rate |
|---|---|---|---|---|---|
| H=10 (0.1 s) | 0.839 | 0.175 | 0.010 | low | 0.6 |
| H=25 (0.25 s) | 0.774 | 0.089 | 0.028 | low | 0.8 |
| H=50 (0.5 s) | 0.726 | 0.110 | 0.053 | low | 1.0 |
| H=100 (1.0 s) | 0.701 | 0.158 | 0.081 | low | 1.0 |

Multi-seed (group D): H=10 AUROC 0.839–0.944; H=100 0.638–0.804.
Small-sample caveat (§41): 10 test scenarios per split seed — raw counts and
per-scenario results reported; no significance claims.

## Lead-time results (per attack, policy thr=0.5/k=3, TEST)

| Attack | Scenarios | Raw anticipatory rate | Attributed anticipatory rate | Median lead (raw) | Median lead (attributed) |
|---|---|---|---|---|---|
| lo_manipulation | 1–4/split | 1.00 | **0.00** | 483 blocks (4.8 s) | — |
| calibration_manipulation | 3/split | 0.92 | **0.00** | 806 blocks (8.1 s) | — |
| intercept_resend | 1–4/split | 0.50 | **0.00** | 813 blocks (8.1 s) | — |
| channel_jamming | 0–2/split | 0.50–1.00 | **0.00** | ~833 blocks | — |

**The attributed rates are the honest ones**: on paired scenarios the benign twin
fires identically pre-onset (bit-identical benign trajectory → identical features →
identical probabilities), so raw anticipatory warnings are benign-drift alarming,
not attack anticipation. `warnings.attribute_warnings` gates this (retained as the
mandatory gate for future phases).

## Conventional comparison

- Conventional detector fires post-onset on all attack families (success 1.00;
  negative median lead on gradual attacks — reactive by construction).
- Forecast-vs-conventional at H=100 (5 paired test scenarios where both warned):
  median gain **+77 blocks (0.77 s)** for calibration/LO manipulation (forecast
  warned earlier); **−121 blocks** for intercept-resend. Evidence, not significance.
- False early warnings: conventional 0.2–1.0 (NORMAL) across split seeds; forecast
  0.64–1.0 under the val-selected policy.

## Benign drift

- P(warning | benign drift) and P(warning | normal) measured separately (§35):
  benign warning rate 0.64–1.0 across split seeds under policy thr=0.5/k=3.
- The benign P series is BIMODAL under OU drift — threshold policy cannot reduce it
  without losing attack coverage (verified on VAL; higher thresholds lose 25–50%
  attack coverage at the same benign rate).
- Benign-drift scenarios (channel-drift env) contaminate nothing: their labels are
  ground-truth episode events (tested).

## Ablations (group A/B/C/D; artifacts/phase2/ablation/ablation_summary.json)

| Group | H=10 AUROC | H=100 AUROC | Brier H=10 | Brier H=100 |
|---|---|---|---|---|
| A base only | 0.813 | 0.769 | 0.189 | 0.205 |
| B +diffs | 0.828 | 0.773 | 0.169 | 0.203 |
| C +temporal | 0.829 | 0.745 | 0.014 | 0.078 |
| D all | 0.839 | 0.701 | 0.010 | 0.081 |

- Temporal features (C/D) improve CALIBRATION dramatically (Brier 0.010–0.08 vs
  0.19 base) and H=10 AUROC (+0.026 over base), but AUROC at long horizons slightly
  DEGRADES (D 0.701 vs A 0.769) — temporal statistics pick up benign drift that
  raises false alarms at long horizons.
- Differences (B) help short horizons only.
- Lead-time attribution: 0% for ALL groups at H=100/thr=0.5/k=3 (pair-gated) —
  feature engineering does NOT fix the paired-dataset attribution problem.

## Leakage audit (exact tests and outcomes)

| Test | Outcome |
|---|---|
| historical invariance (differences/rolling/EWMA/CUSUM/KS/AC): future perturbation → features ≤ t unchanged | PASS (per feature class) |
| post-t features actually change (invariance test non-vacuity) | PASS |
| feature determinism (same input → same features) | PASS |
| warmup NaN policy (exact NaN counts per feature) | PASS |
| no infinite values | PASS |
| y_H(t)=0 for t≥onset; band [onset−H, onset) correct | PASS |
| scaler fit on train only (statistics match train) | PASS |
| split disjoint; deterministic; changes with seed | PASS |
| pair isolation: no pair crosses splits (incl. violation detection) | PASS |
| OOD holdout family entirely in test | PASS |
| warning persistence required (single spike never warns) | PASS |
| lead-time sign/null semantics | PASS |
| qber_proxy excluded from conventional indicators | PASS |
| restricted columns never model inputs (invariant) | PASS |
| sudden attack: no artificial pre-onset warning possible | PASS |

## Reproducibility (exact commands)

```powershell
PYTHONPATH=src python -m quantumattack.simulator.generate --config configs/simulation/phase1.yaml --out data/phase1
PYTHONPATH=src python -m quantumattack.features_cli --data data/phase1 --out artifacts/phase2/features
PYTHONPATH=src python -m quantumattack.ablation --out artifacts/phase2/ablation
python scripts/evaluate_early_warning.py --data data/phase1 --features artifacts/phase2/features --out artifacts/phase2/eval
python -m pytest tests/ -q   # 86 passed
```

Identical re-run → metrics.json identical (verified).

## Limitations

- **Synthetic telemetry** — physics-informed simulation (per-block Gaussian, compact
  Holevo approximations); NOT hardware-validated.
- **Sample size** — 65 scenarios; 10 test scenarios per split seed; 5 seeds. Raw
  counts and per-scenario results reported; no significance claims (§41).
- **Paired-only attack scenarios** — every attack run has a benign twin with the
  same seed: pre-onset features are bit-identical between arms, so pre-onset
  warnings are benign-drift responses BY CONSTRUCTION. Lead-time claims require a
  larger mixed paired/unpaired dataset.
- **Sudden attacks** — no pre-onset signal exists (Phase 1 gate); the correct
  scientific result is "no reliable early warning" (§34) — honored: raw warnings on
  intercept-resend are unattributed benign-drift responses.
- **Precursor assumptions** — all gradual precursors are PROJECT INFERENCE
  (docs/precursor-taxonomy.md), not literature-observed behavior.
- **qber_proxy** degenerate — excluded from baselines.

## Scientific gate

**WEAK SIGNAL** — evidence:

1. Causal features generate without leakage (invariance tests pass) — Q1 YES.
2. Conventional detector produces reproducible warning times (null semantics
   correct) — Q2 YES.
3. Logistic regression predicts future attack onset at ROW level (AUROC 0.70–0.94
   across horizons/split seeds) — Q3 YES (row-level).
4. Meaningful lead time: NOT demonstrated under pair-gated attribution (0%) — Q4 NO
   on this dataset.
5. Benign drift: excessive warnings (0.64–1.0 FWR) — Q5 NO (policy cannot reduce it).
6. Generalization: consistent across split seeds at short horizons; unstable at
   H=100 — Q6 PARTIAL.
7. Temporal feature engineering improves calibration (+H=10 AUROC) but not
   lead-time attribution — Q7 PARTIAL (calibration yes, attribution no).
8. Which attacks are forecastable: gradual attacks show raw pre-onset warnings;
   NONE survive benign-twin attribution on paired data — Q8 UNKNOWN (dataset-bound).

The observed "lead time" on intercept-resend was initially an **ARTIFACT** of the
paired-dataset design (identical warnings in both arms); corrected by pair-gated
attribution BEFORE proceeding — the pipeline is verified clean; the limitation is
the DATASET (§53: fix done at evaluation level; deeper models must NOT be built on
the same paired-only data).

## Recommendation

Phase 3 should FIRST generate a larger, mixed paired/unpaired dataset (more seeds;
unpaired attack scenarios; OOD holdout family exercised), THEN evaluate GRU/LSTM +
TCN on the same harness with the SAME pair-gated attribution gate. Only proceed to
GNN/temporal-GNN if temporal models demonstrate attributed-lead-time improvement
over the logistic baseline. Do not build deeper models on the current paired-only
dataset (§53).
