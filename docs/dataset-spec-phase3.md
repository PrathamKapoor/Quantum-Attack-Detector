# Phase 3 Dataset Configuration — Unpaired Forecasting Dataset

Created 2026-10-08, PRE-REGISTERED before any Phase 3 test results were generated
(Phase 3 prompt §4/§11: document the split and OOD choice BEFORE evaluating; do not
choose the held-out attack based on favorable results).

## Design change from Phase 2 (core change, §5)

Phase 2's test population was paired-only: every attack run had a benign twin with
the same seed → bit-identical pre-onset telemetry → pre-onset warnings were
benign-drift alarming by construction. Phase 3 adds INDEPENDENT UNPAIRED scenarios
as the main test population, while RETAINING matched pairs as a separate
COUNTERFACTUAL experiment category (§8).

## Scenario plan (config: configs/simulation/phase3.yaml)

Seeds: 20 independent seeds per unpaired scenario definition (seeds 100–119 for
attacks, 200–219 for benign — disjoint seed ranges so no accidental reuse of a
benign trajectory). Matched pairs: the Phase 2 batch (data/phase1) is RETAINED as
the COUNTERFACTUAL category, regenerated identically from configs/simulation/phase1.yaml.

| Definition | Class | Count | Pair | Seeds |
|---|---|---|---|---|
| normal-plain | NORMAL | 20 | no | 200–219 |
| normal-channel-drift | BENIGN_DRIFT | 20 | no | 200–219 (drift env: fiber_loss_ou_sigma 0.03) |
| normal-disturbance | BENIGN_DRIFT | 20 | no | 200–219 (disturbance_episode_prob 0.5) |
| attack-intercept-resend | ATTACK | 20 | no | 100–119 |
| attack-lo-manipulation | ATTACK | 20 | no | 100–119 |
| attack-calibration-manipulation | ATTACK | 20 | no | 100–119 |
| attack-channel-jamming-probes | ATTACK | 20 | no | 100–119 |
| attack-channel-jamming-sudden | ATTACK | 20 | no | 100–119 |
| (Phase 2 pairs) | COUNTERFACTUAL | 50 (25 pairs) | yes | 1–5 |

Total: 210 scenarios (160 unpaired + 50 counterfactual). Attack onset sampled
independently per scenario (uniform 900–1400, drawn from the scenario seed).

Attack parameters sampled independently per scenario (within Phase 1 taxonomy
ranges): tap_fraction U[0.2, 0.5]; lo_attack_attenuation U[0.3, 0.7];
cal_gain_bias U[0.05, 0.25]; jamming_power U[0.3, 0.8].

## Pre-registered split (BEFORE evaluation)

- Split by SCENARIO, hash-seeded (SplitConfig seed=42, fixed BEFORE evaluation);
  train 0.6 / val 0.2 / test 0.2;
- matched-pair COUNTERFACTUAL scenarios: assigned to TRAIN ONLY (diagnostic
  category, never the test population — §8);
- OOD holdout family (pre-registered, before evaluation): **channel_jamming**
  (both probe and sudden variants) → TEST entirely. Rationale for the choice
  (recorded before evaluating, §11): channel jamming is the availability-asset
  attack with a distinct variance/saturation signature — it tests cross-family
  generalization on a DIFFERENT telemetry surface (variance/saturation) than the
  gradual mean-shift attacks (LO/calibration) that dominate training. NOT chosen
  for favorable results (its Phase 2 behavior was weak/unreliable).

Expected partition sizes (approx., verified after generation): train ≈ 110
(≈ 60 unpaired + 50 counterfactual), val ≈ 32, test ≈ 68 (incl. 40 OOD jamming).

## Metric definitions (pre-registered)

- **Metric A — Independent early warning** (primary): on unpaired test scenarios,
  a warning before attack onset (policy: thr=0.5, k=3, cooldown=50, grace=5 —
  the Phase 2 val-selected policy, NOT retuned) is a genuine candidate early
  warning. Reported per attack family with lead-time distributions.
- **Metric B — Counterfactual attribution** (diagnostic, on COUNTERFACTUAL pairs):
  warning_attack AND NOT warning_benign_twin at overlapping blocks = attack-
  attributable (Phase 2 gate retained).

## Success criteria (pre-registered)

- Metric A: mean/median positive lead time with FWR(NORMAL)+FWR(BENIGN_DRIFT) ≤ 0.3
  is a usable early-warning signal; FWR > 0.5 is not useful regardless of lead time.
- Sudden attacks (intercept-resend, jamming-sudden) reported SEPARATELY (§21);
  "no reliable pre-onset prediction" is an acceptable result for them.
