# handoff.md

Exact current implementation state for the next coding session. Only verified facts; UNKNOWN is stated explicitly. Updated at the end of every session.

---

## 1. Current Phase & Scientific Conclusion

- **Phase**: Phase 4 — Large-Scale Robustness, Statistical Validation & Graph-Model Decision.
- **Status**: **COMPLETE** as of 2026-10-09.
- **Scientific Gate Outcome**: **`ATTACK-SPECIFIC ROBUST SIGNAL`**
  - Gradual attacks exhibit statistically robust, independently attributable pre-onset early warning (85–100% warning rate, median lead times 103–124 blocks / 1.0–1.2 seconds, 95% CIs well above 0).
  - Sudden attacks correctly register **0% pre-onset warning** (NO PRE-ONSET SIGNAL OBSERVED, class C — physically sound).
  - Benign drift confusion is resolved: **`FWR(BENIGN_DRIFT)` = 0.0%** identically across all 5 independent split seeds.
  - `FWR(NORMAL)` is 0.226 ± 0.118 across split seeds (0.231 on split 42).
- **Graph Model Gate Outcome**: **`HOLD`**
  - Evaluated per pre-registered criteria (`docs/graph-hypothesis.md`).
  - Precursors in the current CV-QKD digital twin are single-component ramps whose signals are fully captured by per-column temporal features.
  - Linear models on causal features match or exceed deep sequence models (H=100 AUROC 0.847 vs GRU H=10 AUROC 0.625 on test); no cross-component information gap exists in the data-generating process.
  - In accordance with the cardinal rule (*"Do not build a GNN simply to satisfy the original architecture idea"*), GNN implementation is held until a multi-component distributed simulator is introduced.

---

## 2. Exact Dataset Protocol (`phase4-v1`)

Pre-registered in `docs/phase4-protocol.md` v1 before test evaluation:
- **Total Scenarios**: **284 scenarios** (234 independent unpaired + 50 counterfactual paired).
- **Seed Pools** (Disjoint, stride 7, collision-free):
  - `TRAIN`: 1000..1833 (120 seeds, 20 per definition × 6 definitions)
  - `VAL`: 5000..5287 (42 seeds, 7 per definition × 6 definitions)
  - `TEST`: 9000..9287 (42 seeds, 7 per definition × 6 definitions)
  - `OOD`: 13000..13203 (30 seeds, 15 per jamming definition × 2 definitions)
- **Partitions**: Partition assignment is fixed by seed pool by construction (never hash-assigned).
- **OOD Family**: `channel_jamming` (held out: 0 train, 0 val, 44 test-only).
- **Counterfactual Pairs**: Retained as train-only diagnostic category (50 scenarios).
- **Data Directory**: `data/phase4/` (234 scenarios) + `data/phase1/` (50 counterfactual).
- **Feature Directory**: `artifacts/phase4/features/` (154 causal features, schema v2).

---

## 3. Best Baseline Model

- **Model**: Logistic Regression with standard scaling (fit on train only), `C=1.0`, `class_weight='balanced'`, `min_history_blocks=100`.
- **Feature Group**: Group D (or Group C; Group C achieves 0.848 AUROC, Group D achieves 0.847 AUROC).
- **Warning Policy (Frozen)**: `WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50, grace_blocks=5, sustained_until_onset=True)`.
- **Performance**:
  - H=10 (0.10 s): AUROC 0.792, AUPRC 0.038, Brier 0.099
  - H=25 (0.25 s): AUROC 0.820, AUPRC 0.071, Brier 0.095
  - H=50 (0.50 s): AUROC 0.846, AUPRC 0.113, Brier 0.101
  - H=100 (1.00 s): AUROC 0.847, AUPRC 0.190, Brier 0.121
  - Multi-split stability (5 seeds): Mean AUROC 0.830 ± 0.015 (range [0.816, 0.847]).

---

## 4. Attack-Specific Findings (H=100, B=2000 Scenario Bootstrap CIs)

| Attack Family | Precursor Class | Warning Rate (95% CI) | Median Lead Time (95% CI) | Status |
|---|---|---|---|---|
| `lo_manipulation` | Class A (Gradual) | 1.00 [1.00, 1.00] | 103.0 blocks [62.0, 208.0] | Forecastable |
| `calibration_manipulation` | Class A (Gradual) | 1.00 [1.00, 1.00] | 124.0 blocks [103.0, 142.5] | Forecastable |
| `intercept_resend` | Class C (Sudden) | 0.00 [0.00, 0.00] | *None (null)* | No pre-onset signal (physical reality) |
| `channel_jamming` (OOD) | Class B / C (Hybrid) | 0.367 [0.20, 0.533] | 73.0 blocks [21.0, 128.0] | Probe variant warns; sudden variant 0% |

- **Conventional Gain**: Forecast detector warns **463.5 blocks (4.64 s) earlier** on `calibration_manipulation` and **498.0 blocks (4.98 s) earlier** on `lo_manipulation` than the conventional detector.
- **Conventional Detector Defect**: Conventional 5-sigma detector has a catastrophic **100% false warning rate** on `BENIGN_DRIFT`. Our forecast detector achieves **0% FWR** on `BENIGN_DRIFT`.

---

## 5. Feature Freeze v1 Summary (`docs/feature-freeze-v1.md`)

- **Schema Version**: `FEATURE_SCHEMA_VERSION = 2` (154 derived causal features, 35 raw telemetry features).
- **Core Forecast Features**: `transmittance`, `det_gain`, `lo_sig_ratio`, multi-scale rolling means (`rm5`, `rm25`, `rm100`), CUSUM drift indicators (`cusum_neg_transmittance`, `cusum_neg_x_var`, `cusum_neg_skr_estimate`).
- **Post-Onset Only (Confirmation Features)**: `qber_proxy`, `p_attack_present`, sudden quadrature variance steps, SKR collapse to 0. (Essential for post-onset attack confirmation; zero pre-onset predictive utility).
- **Redundant Features**: 246 pairs with |r| > 0.95 (primarily `rm` vs `ewma` at matched scales).
- **Unstable Features**: 33 features with near-zero mean coefficients and CV > 1.5.

---

## 6. Testing & Verification

- **Regression Suite**: `pytest` → **109 passed, 0 failed, 0 skipped** (includes 14 Phase 4 dataset isolation & seed disjointness tests, 23 feature causality tests, 23 baseline tests, 40 Phase 1 tests, 8 temporal tests, 1 Phase 4 label-window bug test).
- **Leakage Audits**: `test_sequence_invariance_to_future` and historical-invariance feature tests pass cleanly.

---

## 7. Exact Commands to Reproduce Phase 4 Results

```powershell
# 1. Run full test suite
pytest

# 2. Run primary Phase 4 logistic + conventional evaluation (split 42)
python scripts/evaluate_phase4.py --split-seed 42 --out artifacts/phase4/eval-logistic

# 3. Run multi-split robustness across 5 seeds
python scripts/evaluate_phase4.py --split-seed 7 --out artifacts/phase4/eval-s7
python scripts/evaluate_phase4.py --split-seed 101 --out artifacts/phase4/eval-s101
python scripts/evaluate_phase4.py --split-seed 2024 --out artifacts/phase4/eval-s2024
python scripts/evaluate_phase4.py --split-seed 31337 --out artifacts/phase4/eval-s31337

# 4. Run feature ablation experiments (Groups A, B, C, D)
python scripts/ablate_phase4.py --out artifacts/phase4/ablation

# 5. Run feature redundancy & stability analysis
python scripts/feature_freeze_analysis.py --out artifacts/phase4/feature-analysis
```

---

## 8. Known Limitations

1. **Synthetic Telemetry**: Telemetry is produced by a high-fidelity digital twin of GMCS CV-QKD (Gaussian optics, homodyne detection, Ornstein-Uhlenbeck drift); not yet validated on physical hardware experimental testbeds.
2. **Precursor Taxonomy**: Gradual attack precursors represent physical actuator ramps and probe pulses (labeled `PROJECT INFERENCE` in taxonomy); sudden attacks remain physically unforecastable.
3. **Normal Class False Warnings**: `FWR(NORMAL)` is ~22.6% due to occasional baseline noise excursions crossing the conservative 0.5 probability threshold.

---

## 9. Next Recommended Phase

**Phase 5: Dual-Engine Early-Warning & Confirmation Fusion Architecture**
1. Implement the dual-engine operational pipeline:
   - **`PREDICTED`** channel: Early-warning probability $P(\text{attack within } H)$ from frozen Core forecast features.
   - **`CONFIRMED`** channel: Reactive threshold verification from frozen Confirmation features (`qber_proxy`, SKR collapse, post-onset steps).
2. Multi-Component Simulator Extension (if GNN is to be revisited): Extend the simulator to multi-component coordinated attacks (e.g. synchronized LO attenuation + phase modulator bias) to generate genuine cross-component interaction precursors.
3. Explainability & Alert Attribution: Implement per-alert explanation reports detailing which telemetry component drove the pre-onset warning.
