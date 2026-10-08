# Evaluation Protocol — Conventional Baselines, Lead Time, Warning Policy, Metrics

Created 2026-10-08 (Phase 1). Defines the conventional detection baselines a
forecasting system must beat, the lead-time definition, the warning-policy design
constraints, and the metrics later phases must measure (none are reported until
actually measured — master prompt §40).

## 1. Conventional detection baseline (master prompt §38)

Conventional indicators = current-state thresholds on monitor-visible telemetry.
Rationale documented below; thresholds are NOT tuned to make the proposed model
look better (master prompt §59) — they are set from the parameter-estimation
statistics of the simulator's own operating point (docs/telemetry-spec.md §Ranges):

| Indicator | Threshold (Phase 1 default) | Rationale |
|---|---|---|
| excess-noise estimate ε̂ | ε̂ > ξ_base + 5·σ_ε̂ (per-scenario estimator std) | standard QKD practice: abort when excess noise exceeds the parameter-estimation confidence bound |
| secret-key-rate estimate K̂ | K̂ < 0.5·K̂_base (per-scenario baseline mean) | abort when key rate halves — a realistic operator policy |
| LO power | |ΔP_LO| > 5·σ_P (per-scenario estimator std) | LO monitors flag abnormal reference drift |
| detector imbalance | imbalance > 5·σ_imb | calibration monitors flag abnormal imbalance |
| saturation flag | saturation_frac > 0.01 | detector saturation alarms |
| SNR | SNR < SNR_base − 5·σ_SNR | measurement-quality alarms |

All "5·σ" thresholds follow the 5-sigma convention of QKD parameter estimation
(source 8 uses δ_fail = 1e-10 confidence bounds — ≈6.4σ; 5σ is the conventional
monitor analogue). Detection time of the conventional baseline = first block where
any indicator crosses its threshold (with the same persistence policy as §3, for a
fair comparison).

## 2. Lead time definition (master prompt §39)

```text
lead_time = attack_onset − first_valid_warning_time
```

- Positive lead time (warning BEFORE onset) = useful advance warning; measured in
  blocks and seconds (1 block = 10 ms).
- Zero/negative lead time = no useful advance warning (warning at/after onset is
  detection, not prediction).

`attack_onset` is the precise per-attack definition in `docs/attack-taxonomy.md`
(first block where the malicious mechanism modifies system state) — NOT the first
abnormal telemetry. A vague onset would make lead_time meaningless; per-attack
onset precision is therefore normative.

## 3. Warning policy (future design constraints)

A single random probability spike must NOT count as a successful warning. The
warning policy (applied to P(attack within H) in later phases) requires ALL of:

1. **probability threshold** on calibrated P(attack within H);
2. **minimum consecutive windows**: k consecutive blocks with P above threshold
   (Phase 1 design default k=3 = 30 ms of persistent alarm);
3. **cooldown** after a warning fires (suppresses re-arming noise);
4. **calibration requirement**: probabilities must be calibrated (reliability
   measured) BEFORE the threshold is meaningful.

Warning-policy parameters must be selected on VALIDATION scenarios only, never on
test (master prompt §39: "Do not optimize this policy on the test set later").

## 4. Metrics required by later phases (master prompt §40)

### Detection (classification of ongoing attacks)
accuracy (where useful) · precision · recall · F1 · AUROC · AUPRC

### Forecasting (P(attack within H))
precision at horizon · recall at horizon · AUROC by horizon · AUPRC by horizon ·
calibration (reliability diagrams / ECE) · Brier score

### Early warning
mean lead time · median lead time · lead-time distribution (per attack type) ·
successful pre-onset warning rate (fraction of attacks with positive lead time
under the §3 policy) · false early-warning rate (warnings on benign scenarios) ·
warning persistence (k-consecutive stability)

### Security impact (where defensible)
QBER impact (proxy) · secret-key-rate impact · secret-key loss avoided (integral of
K̂ over the lead-time interval) · potential impact (key material generated while
attacked, had no warning been issued)

NONE of these are reported in Phase 1 — no model exists yet. They are documented
here as the evaluation contract for later phases.

---

## 5. Phase 2 measured results (2026-10-08; evidence: artifacts/phase2/eval/metrics.json)

### Conventional detector (as measured, same scenarios/policy)

- Thresholds calibrated on benign TRAIN portions only (empirical quantile q=0.995;
  7 CV-QKD indicators; qber_proxy excluded as degenerate).
- Detection: calibration/LO attacks — warning success 1.00 (fires on the ε̂/SKR
  signature post-onset, as a reactive monitor should); intercept-resend — 1.00
  (T̂ step detected); median conventional lead time is NEGATIVE (post-onset) for
  gradual attacks — conventional detection happens at/after onset by construction.
- False early-warning rate (NORMAL scenarios): 0.2–1.0 across split seeds.

### Forecast baseline (logistic regression, per-horizon, group D features)

| Horizon | AUROC (test) | AUPRC (test) | Brier | Scenario warn rate (pre-onset) |
|---|---|---|---|---|
| H=10 (0.1 s) | 0.839 | 0.175 | 0.010 | 0.6 |
| H=25 (0.25 s) | 0.774 | 0.089 | 0.028 | 0.8 |
| H=50 (0.5 s) | 0.726 | 0.110 | 0.053 | 1.0 |
| H=100 (1.0 s) | 0.701 | 0.158 | 0.081 | 1.0 |

Multi-seed (split seeds 0–3, group D): H=10 AUROC 0.839–0.944; H=100 AUROC 0.638–0.804.
Small-sample caveat (master prompt §41): 10 test scenarios per split seed; raw counts
and per-scenario results reported; no significance claims.

### Warning policy selection (VALIDATION only, master prompt §29)

- Sweep (thr, k) on val scenarios: thr=0.5/k=3 keeps 100% pre-onset attack warning
  with the lowest benign warning rate achievable (0.64 at H=50, 0.79 at H=100).
  Higher thresholds do NOT reduce benign warnings (benign P is bimodal — OU drift
  either crosses the threshold or not) and lose attack coverage at thr=0.95.
- SELECTED (D-025): thr=0.5, persistence k=3, cooldown=50, grace=5. NOT tuned on test.

### Pair-gated attribution (Phase 2 gate finding)

Warnings on attack scenarios whose matched benign twin fired identically are benign-
drift alarming, NOT attack anticipation. On the Phase 1 dataset (all attack scenarios
paired), the benign twin fires identically pre-onset by construction (bit-identical
benign trajectory → identical features → identical probabilities). Result: attributed
anticipatory warnings = 0% at H=100/thr=0.5/k=3; raw (ungated) anticipatory rate
0.5–1.0 — inflated by the benign-drift responses. The attribution logic
(`warnings.attribute_warnings`) is retained as the mandatory gate for future phases.

### Conventional vs forecast (master prompt §36)

At H=100: median forecast-vs-conventional gain +77 blocks (0.77 s) for
calibration/LO manipulation (forecast warns earlier); −121 blocks for
intercept-resend. Comparison limited to 5 test scenarios where both warned —
evidence, not significance.

### Lead-time semantics as implemented

`lead_time = attack_onset − first_valid_warning_time` (blocks; ×10 ms).
Categories: anticipatory (lead > grace=5), immediate (0 ≤ lead ≤ 5), late (< 0),
none, false_early_warning (benign scenarios), unattributed (benign twin warned
identically). Missing warnings are null, never zero.
