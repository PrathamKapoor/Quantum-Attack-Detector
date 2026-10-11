# Reliability Evaluation Protocol

Pre-registered protocol for the metric-integrity and telemetry-robustness
workstream. This document is **normative for every experiment described in
`docs/reliability-research-report.md`**. It is written and frozen BEFORE the
confirmatory evaluation is executed.

Status: FROZEN (v1). Date: 2026-10-11. Supersedes nothing; extends
`docs/evaluation-protocol.md` (Phase 2) and `docs/phase5-protocol.md` (Phase 5).

---

## 1. Motivation (why this protocol exists)

Three defects were established by inspection and measurement before this protocol
was written (evidence in `docs/reliability-research-report.md` §2):

1. **Time-unit error.** Lead times were reported using 0.1 s/block instead of the
   project's actual `BLOCK_MS = 10.0` (0.01 s/block), inflating every Phase 5
   lead time by 10x.
2. **Horizon-validity error.** Warnings whose lead exceeded the declared horizon
   H were credited as successful H-forecasts. A forecaster for
   `P(onset within (t, t+H])` is provably wrong at any time where the true lead
   exceeds H.
3. **Noise-unit error.** A single absolute sigma was added to a feature matrix
   whose training spread spans ~17 orders of magnitude, producing an
   artificial "robustness cliff" that does not exist in properly-scaled units.

Each defect individually inflates the apparent strength of the system. This
protocol exists to make the corrected measurement reproducible and to prevent
selection of favourable conditions after the fact.

---

## 2. Research questions

| ID | Question | Primary metric |
|---|---|---|
| RQ1 | What are the horizon-valid forecast rates per attack family at each H? | `horizon_valid_forecast_rate` |
| RQ2 | What lead-time distribution do horizon-valid forecasts actually achieve? | lead time in blocks AND seconds |
| RQ3 | Does performance degrade gracefully or catastrophically under telemetry noise in physically meaningful units? | AUROC vs. standardized sigma |
| RQ4 | Which features dominate the degradation? | per-feature ablation AUROC delta |
| RQ5 | Why do NORMAL scenarios raise false warnings when BENIGN_DRIFT does not? | scenario-level false-alarm analysis |
| RQ6 | Are the multi-horizon probabilities monotone in H? | violation rate of P(H1)<=P(H2)<=... |
| RQ7 | Is P>=0.5 a justified operating point? | validation-set ROC-based selection |

---

## 3. Primary and secondary metrics

**Primary (pre-registered, must all be reported):**

- `horizon_valid_forecast_rate` = (# attack scenarios whose first warning satisfies
  `0 < lead <= H` and lead > grace) / (# attack scenarios of that family).
  Reported with a **Wilson 95% interval**, never a degenerate bootstrap.
- `horizon_valid_median_lead_blocks` and `_seconds`, over horizon-valid warnings
  only, with scenario-clustered bootstrap CI.

**Secondary:**

- `extended_pre_onset_alert_rate` — warned pre-onset but lead > H (a real alert,
  but not an H-forecast).
- `post_onset_confirmation_rate` — warning fired after onset (detection).
- `auroc`, `auprc`, `brier`, `ece` at window level, with scenario-clustered CIs.
- `scenario_false_alarm_rate` per benign class, Wilson CI.
- `false_alarm_episodes_per_operating_hour`.
- `warning_load_fraction` — fraction of operating time spent in a warning state.

**Explicitly NOT a primary metric:** any "anticipatory rate" that mixes horizon
validity, extended alerts and post-onset confirmation. That merged quantity is
what this protocol retires.

---

## 4. Forecast horizons and physical time conversions

Horizons: `H ∈ {10, 25, 50, 100}` blocks (unchanged; `simulator.config.DEFAULT_HORIZONS`).

Authoritative conversion (`quantumattack.temporal_units`, single source):

```
seconds = blocks × BLOCK_MS / 1000 = blocks × 0.01
BLOCK_MS = 10.0   (1 block = 10 ms = 1e6 symbols @ 100 MBaud)
```

Every reported lead time and horizon duration MUST carry its unit. Any artifact
whose lead-time seconds disagree with this conversion is invalid and must be
regenerated, not reinterpreted.

---

## 5. Populations, scenario counts and seed partitions

| Partition | Seed range | Scenarios | Role |
|---|---|---|---|
| Phase 4 train | < 15000, disjoint stride-7 | 234 | Model fitting, scaler, threshold/calibration fit |
| Phase 4 val | disjoint | — | Policy + calibration selection only |
| G1 | 20000–20413 | 60 | Scenario generalization (unseen seeds) |
| G2 | 25000–25273 | 40 | Parameter extrapolation |
| G3 | 30000–30203 | 30 | Environmental stress (benign) |
| G4 | 35000–35203 | 30 | Attack stress / hybrid |

**The statistical unit is the SCENARIO.** Windows inside one scenario are
strongly correlated and are NEVER counted as independent observations.
Every reported rate must state its scenario denominator.

---

## 6. Noise distributions and severities (RQ3)

**Units are mandatory.** Every condition records its `units` string
(`train_sigma`, `feature_range`, or `raw_absolute`) and the per-feature scale
vector used. The legacy `raw_absolute` definition is retained ONLY to reproduce
the historical experiment and MUST be reported with that caveat.

Gaussian noise, `units = train_sigma`, sigma ∈ {0.0, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0}.

Structured conditions (each with its own declared units):

| Condition | Parameters | Units |
|---|---|---|
| Temporally correlated | rho-equivalent 5 blocks | train_sigma |
| Impulsive | 1% blocks, 3× scale | train_sigma |
| Quantization | step = 0.5 × feature IQR | feature_range |
| Missing samples | 1% and 5% of blocks | rate |
| Consecutive dropout | 5-block runs, 1% of starts | rate |
| Dead channels | 5 of 189 columns | count |

These are **exploratory engineering stress levels**, chosen to span a wide range
of degradation. They are NOT calibrated to any measured hardware tolerance —
no hardware data exists for this project. This limitation is carried into the
final report.

---

## 7. Model configuration and calibration

Frozen baseline (unchanged, must remain reproducible):

- Logistic regression, `C=1.0`, `class_weight='balanced'`, `max_iter=1000`.
- Feature group D (189 features), schema v2.
- `min_history_blocks = 100`.
- Scaler fit on TRAIN scenarios only.

Calibration variants evaluated (fit on a held-out calibration split carved from
TRAIN only, never from G1/G2/G3/G4):

1. None (raw logistic probability).
2. Platt scaling.
3. Isotonic — only if the calibration split supports it (≥ 200 positives);
   otherwise recorded as INSUFFICIENT SAMPLE.

---

## 8. Threshold selection and false-alarm budget

Operating point selection uses the **validation partition only**.

False-alarm budget: report the operating characteristic at
`P ≥ 0.5, K = 3` (the frozen baseline) AND at the validation-selected threshold
that attains a comparable false-alarm rate to the conventional detector
(`docs/evaluation-protocol.md` §1). Comparing against an artificially weak
conventional detector is prohibited; the comparison must be at a **matched
false-alarm budget**.

---

## 9. Confidence intervals and statistical uncertainty

- Event rates (warning success, false-alarm): **Wilson score interval**, 95%.
  Non-degenerate at 0 and 1 by construction.
- Continuous metrics (AUROC, AUPRC, Brier, lead time): **scenario-clustered
  percentile bootstrap**, B=2000, seed 2026, recorded in every artifact.
- Empty groups report `None` (undefined), never `0.0`.
- Failed/undefined resamples are counted and surfaced, not silently dropped.
- Every table states n_scenarios, n_successes, n_failures.

---

## 10. Baseline comparisons

Any proposed improvement MUST be compared against the frozen logistic baseline
under identical data, splits, horizons, warning policy, and confidence method.
Clean-condition regressions are reported alongside noisy-condition improvements.
The original model and policy remain runnable and reproducible.

---

## 11. Acceptance criteria

A candidate robustness intervention is **accepted** only if ALL hold:

1. Horizon-valid forecast rate on G1/G2 does not decrease.
2. G1 NORMAL scenario false-alarm rate does not increase by more than the
   Wilson-interval overlap permits.
3. Improvement appears at σ ≥ 0.2 train-sigma units (i.e. the regime that was
   previously untested because the legacy units saturated it).
4. It does not improve by weakening the evaluation (no threshold retuning on
   test, no changed splits, no changed horizon semantics).

---

## 12. Failure conditions

The workstream FAILS (and the finding is reported honestly) if:

- Horizon-valid forecast rates collapse once horizon validity is enforced.
- The model proves to be learning simulation schedule rather than telemetry.
- Multi-horizon probabilities are incoherent and cannot be repaired by a
  validation-fitted correction.
- A sudden-onset attack is shown to be predictable for a reason that does not
  exist in the simulator.

---

## 13. Disclosure of prior partition exposure

G1–G4 were generated and (partially) inspected during Phase 5, and their
aggregate statistics were reported publicly in `docs/phase5-final-report.md`.
They are therefore **NOT a pristine untouched partition** and must not be
described as one.

Accordingly:

- Any NEW confirmatory claim in this workstream uses the **corrected metrics**
  on these partitions and is labelled as *re-analysis of an exposed partition*.
- The frozen Phase 4 validation partition remains the selection set.
- No claim of first-contact confirmation is made for G1–G4.

---

## 14. Scope limits (complexity gate)

No GNN, Transformer, QML model or additional temporal neural architecture is
introduced under this protocol. The graph-model gate remains **HOLD**. Increased
model complexity is not itself an improvement, and the Phase 3/4 evidence
(GRU/TCN did not beat logistic at matched false-alarm budget) is unchanged.