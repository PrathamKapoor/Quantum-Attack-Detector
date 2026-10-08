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
