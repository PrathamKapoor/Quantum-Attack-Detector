# handoff.md

Exact current implementation state for the next coding session. Only verified facts;
UNKNOWN is stated explicitly. Updated at the end of every session.

## 1. Current Phase

Phase 2 — Causal feature layer, forecasting baselines & lead-time evaluation.
COMPLETE as of 2026-10-08. Scientific gate: **WEAK SIGNAL** (row-level discrimination
exists and is reproducible; attack-specific pre-onset attribution does not clear the
warning-policy bar on the current dataset — benign-drift alarming dominates).

## 2. Work Completed

- Phase 1 committed (16f8406) before extension; 40 Phase 1 regression tests verified.
- Causal feature layer: `src/quantumattack/features.py` (schema v2, 154 derived
  features: d1/d2, trailing rolling mean/std {5,25,100}, OLS slopes {25,100}, EWMA
  {5,25}, two-sided CUSUM (warmup-only reference), two-sample KS (50/50), trailing
  lag-1 autocorrelation). All trailing; explicit-NaN warmup policy; `FeatureConfig`
  configurable; per-feature metadata machine-readable.
- Feature tests: 23 (incl. historical-invariance causality tests per feature class,
  determinism, NaN policy, no-inf, schema stability).
- Conventional threshold detector: `baselines/conventional.py` (7 CV-QKD indicators;
  qber_proxy excluded as degenerate; empirical-quantile calibration on benign TRAIN
  portions; persistence k=3 + cooldown; null lead semantics).
- Scenario-level splitting: `baselines/splits.py` (hash-seeded, pairs atomic, OOD
  holdout architecture ready; disjointness + pair-isolation tests).
- Logistic forecasting: `baselines/logistic.py` (per-horizon LogisticRegression,
  class_weight=balanced; scaler fit on TRAIN only; y_H(t)=1 iff t<onset≤t+H, y=0 for
  t≥onset; ablation groups A/B/C/D; feature memoization).
- Warning policy + evaluation: `baselines/warnings.py` (threshold + k-consecutive +
  cooldown; timing categories incl. grace period; scenario-level false early
  warnings; **pair-gated attribution** — warnings whose matched benign twin fired
  identically are NOT attack anticipation).
- Evaluation harness: `evaluation/harness.py` (full pipeline; metrics incl. AUROC/
  AUPRC/Brier/ECE/reliability; conventional comparison; experiment manifest;
  artifacts to git-ignored artifacts/phase2/).
- Ablations A/B/C/D run (artifacts/phase2/ablation/ablation_summary.json).
- Multi-seed evaluation (split seeds 0–3; artifacts/phase2/multiseed-summary.json).
- Reproducibility verified: identical re-run → identical metrics.json.
- decisions.md: D-018..D-025. flow.md, evaluation-protocol.md, feature-spec.md updated.

## 3. Files Changed (Phase 2)

- src/quantumattack/: features.py, feature_config.py, features_cli.py, ablation.py (new)
- src/quantumattack/baselines/: __init__.py, conventional.py, splits.py, logistic.py,
  warnings.py (new)
- src/quantumattack/evaluation/: __init__.py, harness.py (new)
- scripts/: evaluate_early_warning.py (new)
- tests/: test_features.py (23), test_baselines.py (23) (new)
- docs/: implementation-checklist.md, evaluation-protocol.md, feature-spec.md,
  flow.md, handoff.md (updated); decisions.md (D-018..D-025)
- .gitignore (artifacts/ + data/ ignored)

## 4. Current Architecture / State

```text
src/quantumattack/
    simulator/   (Phase 1: config, clock, rng, scenario, cvqkd, optical, homodyne,
                  drift, 4 attacks, collector, builder, parquet export, generate)
    features.py + feature_config.py + features_cli.py   (Phase 2: causal features)
    baselines/   (Phase 2: conventional.py, splits.py, logistic.py, warnings.py)
    evaluation/  (Phase 2: harness.py)
    dataset.py   (column classes)
```

## 5. Decisions Made (Phase 2)

D-018 Phase 1 committed first (16f8406) · D-019 causal feature layer (trailing,
explicit-NaN warmup, configurable, 154 features, schema v2) · D-020 conventional
thresholds = empirical quantile on benign TRAIN portions · D-021 scenario-level
splitting, pairs atomic, hash-seeded · D-022 logistic per-horizon, train-only scaler ·
D-023 warning policy (thr + k=3 + cooldown + grace categories) · D-024 experiment
manifest, artifacts git-ignored · D-025 policy selected on val (thr=0.5, k=3).

## 6. Requirements and Constraints

- Master prompt governs. Commits: `PrathamKapoor <prathamkapoor027@gmail.com>`, no
  co-author/AI lines. Never commit paper/, research/, *.tex, data/, artifacts/.
- Phase gates: Phase 3 = sequence models ONLY if justified by the Phase 2 gate
  (WEAK SIGNAL — proceed with explicit expectations, see §10).
- Causality absolute: every feature trailing; historical-invariance tests are the gate.
- Pair-gated attribution MANDATORY for any early-warning claim (Phase 2 gate finding).

## 7. Testing and Verification

- `python -m pytest tests/ -q` → **86 passed** (0 failed, 0 skipped), 2026-10-08.
- Evaluation: `python scripts/evaluate_early_warning.py` → artifacts/phase2/eval/.
- Ablations: `PYTHONPATH=src python -m quantumattack.ablation` → artifacts/phase2/ablation/.
- Features: `PYTHONPATH=src python -m quantumattack.features_cli --data data/phase1
  --out artifacts/phase2/features` → 65 files + feature_schema.json.
- Reproducibility: identical eval re-run → metrics.json identical (verified).

## 8. Exact Results (Phase 2; evidence artifacts/phase2/eval/metrics.json)

Horizon metrics (test, group D, split seed 0): H=10 AUROC 0.839/AUPRC 0.175/Brier
0.010; H=25 0.774/0.089/0.028; H=50 0.726/0.110/0.053; H=100 0.701/0.158/0.081.
Multi-seed: H=10 AUROC 0.839–0.944; H=100 0.638–0.804. Conventional detector: fires
post-onset on all 4 attack families (success 1.00, negative lead on gradual attacks).
Raw anticipatory warnings (ungated): 0.5–1.0 by attack. ATTRIBUTED (benign-twin
gated): **0%** for all attack families at H=100/thr=0.5/k=3. Benign false-warning
rate: 0.64–1.0 across split seeds (val-selected policy does not reduce it; benign P
is bimodal under OU drift). Forecast-vs-conventional: median gain +77 blocks (0.77 s)
for calibration/LO at H=100 (5 paired test scenarios, both warned) — evidence, not
significance.

## 9. Known Issues / Limitations

- **All Phase 1 attack scenarios are PAIRED** (pair: true): each attack run has a
  benign twin with the same seed → bit-identical benign trajectory → identical
  pre-onset features → identical pre-onset warnings. Pre-onset "anticipation" on
  paired runs is benign-drift alarming BY CONSTRUCTION; the discriminator must come
  from cross-scenario generalization (unpaired new seeds). A larger, mixed
  paired/unpaired dataset is required before lead-time claims.
- Small sample: 10 test scenarios per split seed; 5 seeds total. No significance
  claims (master prompt §41).
- Benign false-warning rate 0.64–1.0: the logistic model does not separate benign
  calibration/OU drift from precursor drift on this dataset. Legitimate finding
  (master prompt §60): NOT fixed by tuning the simulator.
- qber_proxy degenerate (excluded). Simulator physics are approximations (per-block
  Gaussian, compact Holevo). Synthetic telemetry, not hardware-validated.

## 10. Unresolved UNKNOWNs & Next Recommendation

- UNKNOWN: whether deeper temporal models (GRU/TCN) improve attack-specific
  ATTRIBUTED lead time over the logistic baseline — the Phase 3 question.
- UNKNOWN: whether unpaired scenarios (new seeds without benign twins) yield
  positive attributed lead time — requires a larger dataset (Phase 3 dataset work).

**Recommended Phase 3**: (1) generate a LARGER mixed dataset (more seeds; unpaired
attack scenarios; OOD holdout family); (2) implement GRU/LSTM + TCN on the same
harness with the SAME pair-gated attribution gate; (3) compare attributed lead time
vs the logistic baseline; (4) only proceed to GNN/temporal-GNN if temporal models
demonstrate attributed-lead-time improvement.

## 11. Critical Context

- Phase 2 gate answered WEAK SIGNAL: causal features leak nothing (verified),
  warnings are reproducible, discrimination exists (AUROC 0.70–0.84), BUT
  attack-specific pre-onset attribution is 0% on paired data — the benign twin fires
  identically. Do NOT build deeper models on the SAME paired-only dataset without
  addressing this (§53: artifact check done — the artifact is in the DATASET DESIGN,
  not the pipeline; pipeline verified clean).
- The pair-gated attribution logic (`attribute_warnings`) is the mandatory gate for
  any future early-warning claim.
- Never fabricate; sudden attacks remain honest hard negatives.

## 12. Agent Instructions

- Maintain decisions.md / flow.md / handoff.md / docs/implementation-checklist.md.
- Run historical-invariance tests before any feature change; run the leakage suite
  before any predictive result.
- Any lead-time claim MUST use attributed warnings (benign-twin-gated).
- Dependency rule: re-probe versions before use; D-NNN entry per install.
