# Reliability and Metric-Integrity Research Report

Durable research report for the metric-integrity and telemetry-robustness
workstream. Supersedes nothing; corrects the measurement basis of the Phase 5
claims while preserving the original artifacts.

Protocol: `docs/reliability-evaluation-protocol.md` (frozen v1).
Decisions: `decisions.md` D-039 .. D-046.
Reproduction: `python scripts/evaluate_reliability.py`.
Evidence artifact: `artifacts/reliability/evaluation/reliability_report.json`.

---

## 1. Executive summary

An audit of the frozen Phase 4/Phase 5 baseline found **three measurement defects
that each individually inflated the apparent strength of the system**, plus one
mis-diagnosed reliability failure. All four are now corrected in measurement. The
frozen datasets and artifacts were **not** modified.

| Finding | Reported | Corrected | Nature |
|---|---|---|---|
| Lead-time unit | 78 blk = "7.8 s" | 78 blk = **0.78 s** | Documentation error; code was right |
| G1 `calibration_manipulation` | 90% anticipatory | **50.0% [23.7%, 76.3%]** horizon-valid | Horizon-validity error |
| G1 `lo_manipulation` | 90% anticipatory | **50.0% [23.7%, 76.3%]** horizon-valid | Horizon-validity error |
| G4 `channel_jamming` | 63.3% (100% probes) | **16.7% [7.3%, 33.6%]** horizon-valid | Horizon-validity error |
| G3 "0.0% FWR [0.0%, 0.0%]" | point 0.0%, CI [0,0] | point 0.0%, **CI [0%, 16.1%]** | Degenerate bootstrap CI |
| Noise "cliff at σ≥0.02" | AUROC 0.896 → 0.503 | σ=0.02 in **train-σ units** → **0.827** | Ill-defined noise units |
| Forecast vs conventional | "forecast gain vs conventional" reported | baseline **degenerate (100% benign FWR)** — comparison **INVALID** | Invalid benchmark |

**Verified capabilities that survive correction:**

- Genuine pre-onset discrimination on gradual attacks (AUROC 0.896 on G1 unseen
  seeds; 0.901 for intercept-resend-free families), confirmed **not** to come from
  simulator scheduling (time-only baseline AUROC 0.518).
- Correct physics on sudden attacks: 0% horizon-valid forecasting for
  `intercept_resend` in both G1 and G2 — the system does not invent precursors.
- Horizons are meaningfully forecastable in the 0.3–0.9 s range, which is a real
  but *short* warning window.

**Unresolved problems:**

- 35.0% [18.1%, 56.7%] false-alarm rate on G1 NORMAL benign operation — root-caused
  to sustained benign drift indistinguishable from a precursor under a sticky alarm
  policy, **not** a coding bug.
- **The conventional threshold baseline has no usable operating point** (100%
  benign false-alarm rate even when correctly calibrated on validation), so the
  project's repeated "forecast gain vs conventional" claims are **invalid**. The
  forecaster's advantage over classical detection is currently **unestablished**.
- Frozen probabilities are severely miscalibrated (ECE 0.191); validation-fit Platt
  scaling reduces this to 0.0105.
- Multi-horizon probabilities violate monotonicity in H on 32% of adjacent pairs
  (separately-fit per-horizon models need not be coherent).

**Scientific limitations:** the simulator remains **SYNTHETIC ONLY**; nothing here
is hardware-validated. See §7 and §11.

---

## 2. Baseline verification

| Item | Reported | Reproduced | Difference | Evidence |
|---|---|---|---|---|
| Git HEAD | `6f500b3` | `6f500b3` | MATCH | `git rev-parse HEAD` at session start |
| Branch | `main` | `main` | MATCH | |
| Test suite | 113 passed | **113 passed, 0 failed**, 82.3 s | MATCH | `python -m pytest tests/ -q` |
| G1 H=100 AUROC | 0.901 | **0.901** | MATCH | `artifacts/phase5/evaluation/…json` |
| G1 H=100 AUPRC | 0.435 | 0.435 | MATCH | recomputed 0.4345 |
| G1 H=100 Brier | 0.114 | 0.114 | MATCH | recomputed 0.1135 |
| G1 NORMAL FWR | 35.0% | **35.0% (7/20)** | MATCH | recomputed |
| G1 BENIGN_DRIFT FWR | 0.0% | **0.0% (0/10)** | MATCH | recomputed |
| G1 `intercept_resend` warn rate | 0.0% | **0.0% (0/10)** | MATCH | recomputed |
| G3 combined FWR | 0/30 | **0/30** | MATCH | recomputed |
| Noise σ=0 (clean) | 0.896 | **0.896** | MATCH | recomputed |
| Noise σ=0.02 collapse | 0.503 | **0.508** | MATCH (numerically) | reproduced; cause identified (§4) |
| Median lead (LO, G1) | 78 blk | 78 blk | MATCH | artifact value; **seconds were wrong** |

All reported metrics reproduced. The defects were in **interpretation and
reporting**, not in the stored numbers — which is why they survived to a
closeout report.

Commands executed (working directory `C:\Projects\Quantumattack`, Python 3.13.14):
```
python -m pytest tests/ -q
python scripts/evaluate_reliability.py
```

---

## 3. Metric integrity

### 3.1 Time-unit audit

The simulator time base is fixed by `simulator/config.py::BLOCK_MS = 10.0`
(1 block = 10 ms = 1e6 symbols @ 100 MBaud), confirmed independently by
`data/phase5/manifest.json` → `"block_ms": 10.0` and `Clock.t_ms`.

The Phase 5 report prose used **0.1 s/block**. The consequence:

| Reported as | Actual | Corrected |
|---|---|---|
| 78 blk = 7.8 s | 78 × 0.01 | **0.78 s** |
| 99 blk = 9.9 s | 99 × 0.01 | **0.99 s** |
| 147 blk = 14.7 s | 147 × 0.01 | **1.47 s** |
| 228 blk = 22.8 s | 228 × 0.01 | **2.28 s** |

**The code was never wrong.** `lead_time_ms = lead_blocks * BLOCK_MS` throughout,
and the stored `median_lead_blocks` values are correct. Only the seconds column in
report text was inflated 10x. Horizon durations are confirmed: H=10/25/50/100 →
0.1/0.25/0.5/1.0 s.

Single authority now `src/quantumattack/temporal_units.py`; regression-tested.

### 3.2 Forecast horizon semantics

**The defect.** A model at horizon H predicts `P(onset within (t, t+H])`. At any
time where the true lead exceeds H, the label is `y_H = 0`, so a probability above
threshold is a **false positive of the horizon-H event**, not a successful
forecast. The historical `warning_category` classified any warning with
`lead > grace_blocks` as "anticipatory" regardless of H.

**Measurement.** Across G1+G2+G4 at H=100, of 79 anticipatory warnings:

| Family | Warnings | Horizon-valid (lead ≤ 100) | Extended alerts (lead > 100) | Max lead |
|---|---|---|---|---|
| `calibration_manipulation` | 22 | 11 (50.0%) | 11 | **567 blk (5.67 s)** |
| `channel_jamming` | 30 | 16 (53.3%) | 14 | 281 blk (2.81 s) |
| `lo_manipulation` | 20 | 16 (80.0%) | 4 | 164 blk (1.64 s) |
| **Total** | **72** | **43** | **29 (37%)** | |

29 of 79 (37%) exceeded their declared horizon and were credited as H-100
forecasts. A 5.67 s lead cannot be attributed to a 1.0 s forecaster.

**Corrected reporting.** Every warning is now classified into exactly one of:
`horizon_valid_forecast` (0 < lead ≤ H), `extended_pre_onset_alert` (lead > H),
`onset_detection` (0 ≤ lead ≤ grace), `post_onset_confirmation` (lead < 0),
`no_warning`. The first two are reported separately and never summed.

### 3.3 Corrected headline numbers (G1, H=100, Wilson 95% CI)

| Attack family | n | Reported "anticipatory" | **Horizon-valid** | Extended alert | Median horizon-valid lead |
|---|---|---|---|---|---|
| `lo_manipulation` | 10 | 90.0% | **50.0% [23.7%, 76.3%]** | 30.0% | **0.67 s** (67 blk) |
| `calibration_manipulation` | 10 | 90.0% | **50.0% [23.7%, 76.3%]** | 40.0% | **0.89 s** (89 blk) |
| `intercept_resend` | 10 | 0.0% | **0.0% [0%, 27.8%]** | 0.0% | — |

G2 (parameter extrapolation): `lo_manipulation` 78.6% [52.4%, 92.4%] horizon-valid
(median 0.36 s); `calibration_manipulation` 35.7% [16.3%, 61.2%] (median 0.58 s)
with 50.0% as extended alerts; `intercept_resend` 0.0%.

G4 `channel_jamming`: **16.7% [7.3%, 33.6%]** horizon-valid (median 0.29 s),
46.7% extended alerts. The "100% detection of dense probes" claim survives only as
an *extended pre-onset alert* claim, not as a 100-block forecast claim.

### 3.4 Attack onset semantics

Onset definitions are unchanged and were not found defective
(`docs/time-semantics.md` §3): onset = first block where the malicious mechanism
modifies state, per attack family. Sudden attacks (`intercept_resend` class C)
genuinely have no precursor and correctly score 0% — this is preserved physics,
not a failure, and was deliberately not "fixed".

### 3.5 Warning attribution

Verified that the live warning timestamp is the **first block of the K-consecutive
above-threshold run** — the earliest block at which the threshold was known — and
is therefore never backdated (regression-tested). However,
`sustained_until_onset` uses future onset knowledge to decide *which* warnings are
retained. This is a legitimate **evaluation-time filter** and does not move any
timestamp, but it must be disclosed: the retained warning set depends on ground
truth that would not be available online.

### 3.6 Statistical intervals

Event rates now use Wilson score intervals (validated to 1e-10 against an
independent implementation). The degenerate intervals are gone:

| Group | Reported | Corrected |
|---|---|---|
| 7/7 (G2 fast ramps) | [100%, 100%] | **[64.6%, 100%]** |
| 0/30 (G3 benign) | [0%, 0%] | **[0%, 11.4%]** |
| 0/20 (G3 NORMAL) | [0%, 0%] | **[0%, 16.1%]** |
| 0/10 (G1 BENIGN_DRIFT) | [0%, 0%] | **[0%, 27.8%]** |

Continuous metrics (AUROC) use a **scenario-clustered** percentile bootstrap
(B=1000, seed 2026), because windows within one scenario are strongly correlated
and must not be counted as independent observations.

---

## 4. Telemetry robustness

### 4.1 Where noise was injected

In the historical Test A, noise was added **directly to the raw derived-feature
matrix**, before standardization, with a single absolute sigma for all features.

### 4.2 The units were undefined — this was the actual defect

Group-D features span roughly **17 orders of magnitude** in training spread. On the
frozen Phase 4 train split (189 features), `sigma = 0.02` absolute corresponds to:

| Feature | train std | 0.02 / std |
|---|---|---|
| `qber_proxy` | 4.7e-17 | (∞) |
| `recon_efficiency` | 3.5e-12 | **5.7e9** |
| `secret_fraction` | 3.7e-12 | 5.5e9 |
| `cusum_neg_lo_power` | 1.5e+05 | 1.3e-7 |

- **93 of 189 features** receive noise ≥ 1× their own train std.
- **63 of 189 features** receive noise ≥ 5× their own train std.

So the experiment destroyed small-scale features completely while leaving
large-scale CUSUM accumulators untouched. The identical AUROC (0.503) at
σ ∈ {0.05, 0.1, 0.2} confirms saturation, not graded degradation.

### 4.3 Re-measured in explicit units (G1, H=100)

| Condition | Units | AUROC | Brier |
|---|---|---|---|
| σ = 0.00 | train_sigma | **0.896** | 0.119 |
| σ = 0.05 | train_sigma | 0.869 | 0.166 |
| σ = 0.10 | train_sigma | **0.827** | 0.216 |
| σ = 0.20 | train_sigma | 0.757 | 0.280 |
| σ = 0.50 | train_sigma | 0.665 | 0.360 |
| σ = 1.00 | train_sigma | 0.613 | 0.401 |
| σ = 2.00 | train_sigma | 0.571 | 0.437 |
| σ = 0.02 | **raw_absolute (legacy)** | 0.508 | 0.489 |

**Conclusion reversal:** there is no cliff. The model tolerates roughly
**0.2 train-σ units** before AUROC drops below 0.75, and retains AUROC 0.571 even
at 2.0 train-σ units — noise twice the feature's own training spread. The earlier
"Denoising/Kalman filtering required before hardware deployment" conclusion was
**not supported** by the evidence and is withdrawn as a finding (the engineering
option itself remains open; see §10).

### 4.4 Feature fragility

Dropping the 94 features with the smallest training spread (95 features retained,
refit and retrained on Phase 4 train only):

| Feature set | n | AUROC | Brier |
|---|---|---|---|
| full Group D | 189 | 0.896 | 0.119 |
| drop smallest-std half | 95 | 0.872 | 0.145 |

The fragile-looking features contribute a real but modest amount of discrimination.
There is no evidence they should be dropped on robustness grounds; the subset was
**not** adopted.

---

## 5. False-warning analysis

### 5.1 NORMAL vs BENIGN_DRIFT — the apparent paradox resolved

Reported: NORMAL 35.0% false warnings, BENIGN_DRIFT 0.0%. This looks backwards —
G3 stress scenarios reach max p = 0.9999 yet never fire, while nominal G1
scenarios do.

**Root cause (measured, not guessed).** Under `sustained_until_onset`, a *benign*
warning is retained only if the probability stays above threshold from the first
block of the K-run until **scenario end**. Measuring the longest above-threshold
run and whether it reaches the end:

| | Scenarios | False alarm |
|---|---|---|
| Run reaches scenario end | 3 | **3 (100%)** |
| Run does not reach end | 53 | 4 (8%) |

G3 intense-disturbance scenarios spike to p ≈ 0.999 **transiently** and fall back
below threshold, so the sustained filter correctly rejects them. Three G1
`normal-plain` scenarios hold p ≥ 0.5 for **1033, 492 and 468 consecutive blocks**
to the end of the scenario — sustained benign drift that is genuinely
indistinguishable from a sustained precursor under this policy.

The 7 failing scenarios first warn at blocks **967–1995 (median 1934)** — late
scenario, which **rules out a warmup artifact**.

**Classification: true observational ambiguity under a sticky alarm policy.**
Not a coding defect, and not removable by discarding the data.

### 5.2 Operational burden (G1, H=100)

| Quantity | Value |
|---|---|
| NORMAL false-alarm scenario rate | **35.0% [18.1%, 56.7%]** (7/20) |
| Mean warnings per NORMAL scenario | 2.35 |
| Warning-load fraction (time in alarm) | 5.1% of operating time |
| False-alarm episodes per 1000 simulated seconds | 34.5 |

An hourly rate is deliberately **not** reported: each scenario is only 20 s of
simulated operation, so an hourly figure would extrapolate ~180× beyond the
observed window with meaningless precision.

---

## 6. Calibration, horizons and operational behaviour

### 6.1 Probability calibration

Fit on the **Phase 4 validation partition only** (41 scenarios, 77,900 rows,
1,800 positives at H=100). Never on G1–G4.

| Method | Brier | ECE |
|---|---|---|
| Uncalibrated (frozen) | 0.119 | **0.191** |
| Platt | **0.0216** | **0.0105** |
| Isotonic | 0.0211 | 0.0118 |

The frozen balanced-classifier probabilities are severely overconfident
(ECE 0.191). Platt scaling — a two-parameter fit, no leakage — reduces Brier by
5.5× and ECE by 18×. **These remain synthetic-distribution probabilities, not
real-world attack probabilities** (see §7).

### 6.2 Multi-horizon coherence

For nested horizons the requirement `P(H₁) ≤ P(H₂) ≤ P(H₃) ≤ P(H₄)` is violated on:

| Partition | Violation rate | Pairs checked |
|---|---|---|
| G1 | **31.9%** | 342,000 |
| G2 | **37.5%** | 228,000 |

Cause: the four horizons are **separately fitted** logistic models with no coupling.
Mean probabilities *are* ordered on average (0.128 / 0.144 / 0.166 / 0.217), but
per-block coherence fails often. A validation-fitted isotonic projection onto the
monotone cone could repair this; it has **not** been applied, because doing so
would change the frozen baseline and must first be validated against the clean-
condition regression criterion.

### 6.3 Operational states (measured on G1–G4, H=100)

| Partition | Scenarios entering warning | Reaching confirmation |
|---|---|---|
| G1 | 49 / 60 | 27 / 60 |
| G2 | 40 / 40 | 30 / 40 |
| G3 (benign stress) | 12 / 30 | 10 / 30 |
| G4 | 30 / 30 | 30 / 30 |

Under **2% induced missing telemetry** (15 G1 scenarios), the machine produced
13,200 `DEGRADED_TELEMETRY` blocks and 11,460 `ABSTAINING` blocks, and never
silently reported a confident `NORMAL` during an outage. Abstention is excluded from
true-negative accounting by construction.

`ACTIVE_ATTACK_CONFIRMED` is reached from sustained evidence and is deliberately
**separate** from any forecast: a sudden attack stays unpredictable in advance but
remains confirmable once it starts.

---

## 6.4 Comparison against conventional detection — INVALID (major negative result)

Master prompt §20 requires comparing against a *meaningful* conventional
baseline at a matched false-alarm budget, and explicitly forbids presenting an
artificially weak detector. That requirement **cannot currently be met**, because
the conventional baseline has no usable operating point.

Measured on G1 benign, with the conventional threshold detector calibrated on
Phase-4 validation benign (19 scenarios) — the legitimate calibration split:

| Calibration | G1 benign false-alarm rate |
|---|---|
| Phase-4 **train** benign (as used historically) | 29/30 = **96.7%** |
| Phase-4 **validation** benign (correct procedure) | 30/30 = **100%** [88.6%, 100%] |

**Root cause (measured).** Per-block indicator violation rates on G1 benign are
small — excess_noise 0.05%, lo_power 0.45%, skr_estimate 0.40%, background 0.05% —
but `detect_warnings` requires only **K = 3 consecutive** violating blocks, and the
thresholds are per-block quantiles fit on a *different* benign distribution.
Over a 2000-block scenario, a 0.4% per-block rate makes a 3-run of consecutive
violations near-certain. The detector therefore fires on essentially every benign
scenario without ever showing a sustained within-scenario violation.

Two aggravating factors:

1. `lo_power` and `skr_estimate` are direction=-1 indicators with extremely narrow
   benign spread (`lo_power` std ≈ 5e-4). A small mean shift between benign
   distributions moves them across a fixed absolute threshold.
2. `saturation_frac` falls back to a fixed threshold with zero benign variance.

Consistent with this, the conventional detector also "detects" every
`intercept_resend` scenario with leads of **1200+ blocks** — an attack class with
no precursor at all. Those are false alarms, not detections.

**Consequence.** The prior "forecast gain vs conventional" comparisons in the
Phase 2/4/5 reports are **INVALID** and must not be cited as evidence that the
forecaster outperforms conventional detection. The forecaster's advantage over
classical detection is currently **UNESTABLISHED**. Establishing it requires
first building a conventional baseline that has a genuine per-scenario
false-alarm-controlled operating point (e.g. CUSUM or change-point detection on
per-scenario normalized deviations), validated on held-out benign data.

Forecast threshold sensitivity (G1, H=100) for reference:

| Threshold | NORMAL FWR | `lo_manip` horizon-valid | `cal_manip` horizon-valid |
|---|---|---|---|
| 0.5 | 23.3% [11.8%, 40.9%] | 5/10 | 5/10 |
| 0.7 | 13.3% [5.3%, 29.7%] | 5/10 | 4/10 |
| 0.8 | 10.0% [3.5%, 25.6%] | 5/10 | 5/10 |

Horizon-valid recall is largely flat across thresholds while the false-alarm rate
falls — the operating point is therefore a genuine, if modest, trade-off, and it
must be chosen on a stated false-alarm budget rather than inherited by default.

---

## 7. Scientific validation of the simulator

Unchanged from `docs/simulator-validity-audit.md` and **not** upgraded by this
workstream. The simulator is **SYNTHETIC ONLY**.

- No hardware validation was performed or is claimed.
- Independent cross-checks against an external simulator, published benchmark
  traces or hardware measurements: **not done**.
- Precursor observability is a **modelling assumption** of this simulator. In
  particular, the claim that a ramp or probe is *physically* observable in advance
  is a project inference, not an experimentally established fact.
- The dataset was re-verified for temporal leakage (all 154 derived features
  invariant to future telemetry changes; 143/154 demonstrably affected afterwards,
  confirming the test is non-vacuous) and for schedule learning (time-only AUROC
  0.518 vs 0.896 with telemetry; onset blocks span 603–1454, 86% unique).

---

## 8. Statistical evaluation summary

| Quantity | Value |
|---|---|
| Independent scenarios used | 160 (G1 60, G2 40, G3 30, G4 30) + 122 Phase-4 train |
| Model fit time | ~95 s for 4 horizons × 189 features on 122 scenarios |
| G1 H=100 AUROC | 0.901 (point); scenario-clustered CI recorded in artifact |
| G1 H=100 AUPRC | 0.435 |
| G1 H=100 Brier (uncalibrated) | 0.114 |
| G1 H=100 Brier (Platt) | 0.022 |
| Horizon-valid forecast rate (G1 gradual) | 50.0% [23.7%, 76.3%] |
| Horizon-valid median lead | 0.67–0.89 s |
| False-alarm rate (G1 NORMAL) | 35.0% [18.1%, 56.7%] |
| Interval method | Wilson (rates), scenario-clustered bootstrap B=1000 seed 2026 (AUROC) |

---

## 9. Negative results (preserved)

- **The "robustness cliff" was an artifact.** There is no cliff in properly-scaled
  units. Any future claim of a noise cliff must state its units.
- **The horizon-valid forecast rate is roughly half the previously reported
  anticipatory rate.** 90% → 50% on G1 gradual attacks.
- **Calibration, not discrimination, is the weakest link.** AUROC 0.90 coexists
  with ECE 0.191.
- **Multi-horizon probabilities are incoherent** on ~32–38% of adjacent pairs.
- **The frozen model is genuinely brittle in a *different* way than reported**: its
  probabilities are overconfident, not its features noise-fragile.
- **Feature-subset selection did not help**: dropping the 94 smallest-spread
  features reduced AUROC (0.896 → 0.872). Not adopted.
- **G4 dense-probe jamming is a strong extended alert but a weak 100-block
  forecast** (16.7% horizon-valid). The earlier 100% claim was horizon-invalid.
- **False alarms on nominal operation are real and not removable by policy
  tightening alone** while a sustained precursor policy is used.
- **The conventional baseline is degenerate.** It fires on 100% of benign scenarios
  under correct validation calibration. Every "forecast gain vs conventional" claim
  in the Phase 2/4/5 reports is therefore invalid, and the project's central
  comparative claim — that forecasting beats threshold detection — is
  **currently unsupported by evidence**. This is the most consequential negative
  result of the workstream.

---

## 10. Known limitations and risks

1. **G1–G4 are not a pristine partition.** They were generated and inspected during
   Phase 5. All numbers above are *re-analysis of an exposed partition*, and no
   first-contact confirmation is claimed.
2. **Small samples.** Most per-family rates rest on 7–30 scenarios; Wilson
   intervals are wide (e.g. 50% has CI [23.7%, 76.3%]). Point estimates alone would
   be misleading.
3. **Synthetic precursors.** Ramp/probe observability is assumed, not demonstrated
   against hardware or literature measurements of the required SNR.
4. **No real-world calibration.** Probabilities describe the simulator's attack
   distribution only.
5. **No valid comparative claim.** The conventional baseline is degenerate
   (100% benign false-alarm rate). The project's advantage over classical
   threshold detection is **unestablished**; every prior "forecast gain vs
   conventional" figure must be treated as invalid (§6.4, D-047).
6. **Coherence repair untested.** Isotonic monotonic projection is proposed but not
   applied.
7. **Noise conditions are exploratory.** The structured corruption levels are
   engineering stress levels, not calibrated to any measured hardware tolerance —
   no such data exists for this project.
8. **Warning-retention filter uses future onset.** `sustained_until_onset` decides
   *which* warnings to retain using ground truth unavailable online. Timestamps are
   unaffected and causal, but the retained set is an evaluation-time construct.

---

## 11. Final scientific gate

**Selected gate: `LIMITED OPERATING ENVELOPE`**

Not `ATTACK-SPECIFIC ROBUST FORECASTING` (the horizon-valid rate is ~50% on unseen
seeds, with a 0.67–0.89 s median lead and a 35% nominal-operation false-alarm rate).
Not `WEAK SIGNAL` (discrimination is real at AUROC 0.90, is not schedule-driven,
and reproduces on unseen seeds). Not `LEAKAGE` (temporal-invariance and
schedule-baseline tests both pass). Not `ARTIFACT` (the corrected results still
show genuine discrimination, and the corrected false-alarm rate is an honest
negative rather than a measurement error).

It is **not** raised above `LIMITED OPERATING ENVELOPE` primarily because the
project has **not yet demonstrated superiority over conventional detection** — the
baseline it must beat is itself degenerate (§6.4). Without a working classical
baseline, a "robust forecasting" verdict would rest on an unchallenged comparison.
A claim of operational superiority requires a non-degenerate baseline and a
matched false-alarm budget, which this workstream did not produce.

The system forecasts **gradual** attacks within a **sub-second** horizon on
**unseen seeds**, with a **material operational false-alarm burden** on nominal
operation, and correctly refuses to forecast sudden attacks.

**Simulator evidence status: `SYNTHETIC ONLY`** (unchanged).

**Graph-model gate: `HOLD`** (unchanged). Every corrected finding reinforces it:
the precursors are single-component temporal dynamics, and the failures observed
are rate-of-change and calibration issues — not multi-node structural gaps that a
GNN would address.

---

## 12. Recommended next work (in priority order)

1. **Build a non-degenerate conventional baseline** (CUSUM or change-point
   detection on per-scenario *normalized* deviations, with false-alarm control at
   the scenario level rather than the block level), validated on held-out benign
   data. Without this, no superiority claim over classical detection is possible.
   This is now the single highest-value item (D-047).
2. **Operating-point selection on validation** at a matched false-alarm budget,
   using the corrected horizon-valid metrics. The threshold sweep shows
   horizon-valid recall is roughly flat while the false-alarm rate falls from 23%
   to 10%, so the operating point is a real, modest trade-off that should be
   chosen against a stated budget rather than inherited.
3. **Adopt Platt calibration** (validation-fit); ECE 0.191 currently makes P ≥ 0.5 a
   poorly-grounded threshold.
4. **Multi-scale trailing features** targeted at the slow-ramp gradient-rate limit
   (D-046), validated against the clean-condition regression criterion — with the
   understanding that AUROC cannot be traded away for slow-ramp recall.
5. **Monotone horizon projection**, fitted on validation only, with its effect on
   both calibration and horizon-valid recall measured before adoption.
6. **Build a genuinely untouched evaluation partition** for any future confirmatory
   claim, since G1–G4 are exposed.
7. **Not recommended:** larger models, graph architectures, or a denoiser justified
   by the original noise-cliff finding, which was withdrawn as unsupported.