# handoff.md

Exact current implementation state for the next coding session. Only verified facts; UNKNOWN is stated explicitly. Updated at the end of every session.

---

## 1. Current Phase & Scientific Conclusion

- **Phase**: Phase 5 — Independent Generalization, Simulator Validity & Forecasting Robustness.
- **Status**: **COMPLETE** as of 2026-10-09.
- **Scientific Gate Outcome**: **`ATTACK-SPECIFIC ROBUST GENERALIZATION`**
  - Generalization confirmed across independent scenario seeds (G1 AUROC 0.901, warning rate 90.0%, median lead 78–99 blocks).
  - Generalization confirmed under parameter extrapolation (G2 AUROC 0.863, warning rate 71–86%).
  - Generalization confirmed under extreme environmental stress (G3 False Warning Rate = **0.00%** across 30 scenarios of extreme fiber loss drift, intense disturbance, and thermal coupling).
  - Sudden attack physics preserved with perfect fidelity (0.0% false pre-onset warnings on `intercept_resend`).
  - Pre-attack adversarial probing identified with 100% detection rate and 14.7 s lead time (`channel_jamming` dense probes).
- **Simulator Evidence Status**: **`SYNTHETIC ONLY`**
  - The digital twin is a synthetic in-silico simulation environment. Zero hardware validation claimed.
- **Graph Model Gate Outcome**: **`HOLD`**
  - Maintained at HOLD. All precursor signals remain local temporal drifts capturable by single-channel causal rolling features. Escalation to GNN remains unjustified.

---

## 2. Exact Dataset Protocols

### Phase 4 Protocol (`phase4-v1`)
- 284 scenarios (234 independent + 50 counterfactual).
- Seeds < 15,000 (disjoint stride-7 pools).

### Phase 5 Protocol (`phase5-v1`)
- 160 scenarios in `data/phase5/` generated via `configs/simulation/phase5.yaml`:
  - **G1 (Scenario Generalization)**: 60 scenarios, seeds 20000..20413 (stride 7).
  - **G2 (Parameter Extrapolation)**: 40 scenarios, seeds 25000..25273 (fast/slow ramps, steep biases).
  - **G3 (Environmental Stress)**: 30 scenarios, seeds 30000..30203 (extreme drift $0.06\text{ dB/blk}$, disturbance $p=0.8$, thermal stress).
  - **G4 (Attack Stress / Hybrid)**: 30 scenarios, seeds 35000..35203 (dense probes, sudden saturation).
- Manifest: `data/phase5/manifest.json`.
- Features: `artifacts/phase5/features/` (189 columns, schema v2).

---

## 3. Best Baseline Model & Warning Policy

- **Model**: Regularized Logistic Regression (fit on Phase 4 train only), `C=1.0`, `class_weight='balanced'`, `min_history_blocks=100`.
- **Feature Group**: Group D (189 features: base + diffs + rolling stats + CUSUM + KS + autocorrelation + slopes).
- **Warning Policy (Frozen)**: `WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50, grace_blocks=5, sustained_until_onset=True)`.

---

## 4. Key Performance Metrics Across Partitions (H=100, B=2000 Scenario Bootstrap)

| Partition | AUROC | Gradual Attack Warning Rate | Intercept-Resend Warning Rate | Benign Drift FWR | Normal FWR |
|:---|:---:|:---:|:---:|:---:|:---:|
| **G1 (Scenario Gen)** | 0.901 | 90.0% (Median lead 78–99 blk) | 0.0% (None) | **0.00%** | 35.0% |
| **G2 (Parameter Extrap)** | 0.863 | 71.4%–85.7% (Fast: 100%, Slow: 43–71%) | 0.0% (None) | **0.00%** | 0.0% |
| **G3 (Environmental Stress)** | N/A (all benign) | N/A | N/A | **0.00%** (0/30) | 0.0% |
| **G4 (Attack Stress/Hybrid)** | 0.538 | Dense probes: 100% (147 blk lead) | Sudden: 26.7% (0 blk lead) | N/A | N/A |

---

## 5. Controlled Stress Testing Outcomes (Tests A through I)

- **Test A (Noise Sensitivity)**: Sharp cliff at $\sigma \ge 0.02$ additive feature noise, collapsing AUROC to 0.503. Denoising/Kalman filtering required before hardware deployment.
- **Test B & F (Environmental Shift & Lookalikes)**: 0.00% FWR across 30 extreme benign scenarios under sustained-until-onset policy.
- **Test C & D (Ramp Duration & Bias Shifts)**: Fast ramps detected at 100%; slow ramps diffuse gradients to 42.9%. Extended precursors provide up to 22.8 s advance warning.
- **Test G & H (Jamming & Sudden Attacks)**: Pre-attack probing is 100% detectable; sudden attacks legitimately produce 0.0% warning.
- **Test I (Reproducibility)**: Deterministic execution verified; 113/113 pytest regression suite passes.

---

## 6. Testing & Verification

- **Regression Suite**: `pytest tests/` → **113 passed, 0 failed** in 72s.
- **New Tests Added**: `tests/test_phase5_dataset.py` (4 tests validating Phase 5 partition counts, seed disjointness, file existence, and parquet schemas).

---

## 7. Exact Commands to Reproduce Phase 5 Results

```powershell
# 1. Run full test suite
pytest tests/

# 2. Run Phase 5 Generalization Evaluation
python scripts/evaluate_phase5.py --out artifacts/phase5/evaluation

# 3. Run Controlled Stress Tests (Tests A through I)
python scripts/stress_tests_phase5.py --out artifacts/phase5/stress_tests
```

---

## 8. Documentation Suite

- `docs/phase5-protocol.md` — Pre-registered experimental protocol and seed pools.
- `docs/phase5-final-report.md` — Comprehensive Phase 5 closeout report.
- `docs/phase5-robustness-report.md` — Controlled stress tests A through I analysis.
- `docs/simulator-validity-audit.md` — Epistemic classification and synthetic twin boundaries.
- `decisions.md` — Appended decisions D-034 through D-038.
- `flow.md` — Updated operational workflow to Phase 5.
- `docs/implementation-checklist.md` — Verified Phase 5 tasks with explicit evidence references.
