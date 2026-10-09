# Phase 4 Protocol — Large-Scale Robustness, Statistical Validation & Graph-Model Decision

Created 2026-10-09. **PRE-REGISTERED before any Phase 4 test dataset was generated**
(Phase 4 prompt §6: freeze seeds, splits, OOD family, horizons, feature schema,
warning policy, threshold calibration, model configurations, primary metrics — then
generate the final test results). Any post-hoc change requires a new version + WHY.

## 1. Question

> Does the observed early-warning signal remain statistically and operationally
> meaningful when evaluated over a substantially larger, more diverse, independently
> generated dataset?

Secondary (only if the primary holds): does explicit graph structure add measurable
value over the sequence/feature baselines?

## 2. Scenario plan (config: `configs/simulation/phase4.yaml`)

Scale: **284 scenarios** (234 independent unpaired + 50 counterfactual paired;
1.7× more attack scenarios per gradual family than Phase 3's 20: 34 vs 20).
Compute-verified: ~0.1 s/scenario generation (≈25 s for 284), ~3.6 s/scenario
features (≈15 min serial; parallelized across 4 workers).
Diversity over window count: parameter ranges are the SAME as Phase 3 (no widened
ranges, no precursor strengthening — §5 of the prompt).

### Seed pools (independent, disjoint, non-sequential across partitions)

Seeds are drawn from disjoint numeric ranges AND non-adjacent within each range
(stride 7, deterministic arithmetic documented below) so that no two partitions
share a seed and no accidental adjacency correlation exists. Each DEFINITION
consumes a DETERMINISTIC, NON-OVERLAPPING slice of its partition pool (definition
`i` of 8 takes `pool[i*slice : (i+1)*slice]`) — no seed is reused across
definitions (unlike Phase 3, where all attack definitions shared seeds 100–119;
that reuse correlates environment trajectories across definitions). The scheme is
deterministic and recorded here:

```text
pool(seed_start, size, stride=7): [seed_start + i*stride for i in range(size)]
TRAIN pool: 1000 + i*7,  i=0..119  → 1000..1833  (120 seeds, slice 20/def x 6 defs)
VAL pool:   5000 + i*7,  i=0..41   → 5000..5287  (42 seeds,  slice 7/def  x 6 defs)
TEST pool:  9000 + i*7,  i=0..41   → 9000..9287  (42 seeds,  slice 7/def  x 6 defs)
OOD pool:  13000 + i*7,  i=0..29   → 13000..13203 (30 seeds,  slice 15/def x 2 defs)
```

| Partition | Definitions | Seeds per def | Count |
|---|---|---|---:|
| TRAIN | normal-plain, normal-channel-drift, normal-disturbance, attack-intercept-resend, attack-lo-manipulation, attack-calibration-manipulation | 20 | 120 |
| VAL | same 6 definitions | 7 | 42 |
| TEST | same 6 definitions | 7 | 42 |
| TEST/OOD | attack-channel-jamming-probes, attack-channel-jamming-sudden (OOD family, test-only) | 15 | 30 |
| COUNTERFACTUAL | Phase 2 paired batch (25 pairs), regenerated identically from `configs/simulation/phase1.yaml` | — | 50 |

Total: **284 scenarios** (234 unpaired independent + 50 counterfactual paired).
Unpaired: 120 TRAIN + 42 VAL + 42 TEST + 30 OOD. Attack balance: intercept-resend
34, lo-manipulation 34, calibration-manipulation 34, channel-jamming 30 (OOD
test-only; 0 in train/val) — not forced equal; jamming carries the OOD burden
(§24). Benign: 102 (NORMAL 34, BENIGN_DRIFT 68: channel-drift 34 + disturbance 34).
Attack scenarios per gradual family: 34 (vs Phase 3's 20 — 1.7× scale-up; each
family has 20 train + 7 val + 7 test scenarios).

Benign populations kept SEPARATE (§10): NORMAL (plain) and BENIGN_DRIFT
(channel-drift env `fiber_loss_ou_sigma_db: 0.03`, disturbance env
`disturbance_episode_prob: 0.5`).

Onset: uniform 900–1400 per scenario (drawn from the scenario seed — same as
Phase 3). Attack parameters sampled independently per scenario (same ranges as
Phase 3: tap_fraction U[0.2,0.5]; lo_attack_attenuation U[0.3,0.7];
cal_gain_bias U[0.05,0.25]; jamming_power U[0.3,0.8]; ramp durations per
`configs/simulation/phase3.yaml` ranges).

Scenario record (§7 of prompt): scenario_id, seed, attack family, scenario_class,
environment config, attack configuration, onset, protocol, dataset_version —
all present in `manifest.json` (schema v1) + `generation_config` hash.

## 3. Split (pre-registered BEFORE evaluation)

- Partition assignment is FIXED BY SEED POOL (§2), not hash-assigned: train/val/test
  scenarios are disjoint by construction (seed pools never overlap). Verified
  programmatically (Step 6 tests).
- COUNTERFACTUAL pairs: TRAIN only (diagnostic category, never test — §11).
- OOD family: **`channel_jamming`** (retained from Phase 3, per §12 of the prompt;
  documented rationale unchanged: distinct variance/saturation telemetry surface,
  not favorable-result-driven). The OOD partition = the 30 OOD-seed jamming
  scenarios + all 14 TEST-pool jamming scenarios → 44 test-only jamming scenarios,
  0 in train, 0 in val. Verified programmatically.
- Split seeds for multi-split robustness (§25 of the prompt): hash-seeded
  scenario-level re-assignment within the SAME scenario universe using
  `SplitConfig(seed ∈ {42, 7, 101, 2024, 31337})` — 5 independent split seeds.
  Each split: train only on that split's scenarios, evaluate on its held-out test.
  OOD family still routed to test in every split; pairs atomic in every split.

## 4. Feature schema

UNCHANGED from Phase 3: `FEATURE_SCHEMA_VERSION = 2`, 154 derived features
(d1/d2, trailing rolling mean/std {5,25,100}, OLS slopes {25,100}, EWMA {5,25},
two-sided CUSUM (warmup-only reference), two-sample KS (50/50), trailing lag-1
autocorrelation). Missing-history policy: explicit NaN until warmup; rows with
t < min_history_blocks skipped. Ablation groups A/B/C/D unchanged (§26).

## 5. Warning policy (frozen)

UNCHANGED from Phase 3 (D-028, pre-declared):

```text
WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50,
              grace_blocks=5, sustained_until_onset=True)
```

Applies uniformly to ALL models. NOT retuned on Phase 4 test data. Policy
re-selection on VAL is permitted ONLY if the frozen policy produces degenerate
validation behavior; any such change is documented as a protocol version bump.

## 6. Threshold calibration (frozen)

Conventional detector: same calibration procedure as Phases 2–3 (§30): 7 CV-QKD
indicators (qber_proxy excluded), empirical-quantile q=0.995 calibrated on benign
TRAIN-portion blocks ONLY, persistence k=3, cooldown 50. Never tuned on Phase 4
test performance.

## 7. Model configurations (frozen)

- **Logistic (primary)**: `ModelConfig(horizons=(10,25,50,100), C=1.0,
  class_weight="balanced", max_iter=1000, random_state=0, feature_group="D",
  min_history_blocks=100)`; scaler fit on TRAIN only.
- **GRU (secondary)**: `SequenceModelConfig(model_type="gru", hidden_channels=16,
  num_layers=1, dropout=0.1, seq_length=100, batch_size=128, lr=1e-3, max_epochs=10,
  early_stopping_patience=4, seed=0)` — Phase 3 configuration, no sweep.
- **TCN (secondary)**: `SequenceModelConfig(model_type="tcn", hidden_channels=16,
  num_layers=2, dropout=0.1, seq_length=100, batch_size=128, lr=1e-3, max_epochs=10,
  early_stopping_patience=4, seed=0)` — Phase 3 configuration, no sweep.
- NO other architectures; NO hyperparameter sweep (§16). GRU/TCN rerun only if
  computationally practical at the 546-scenario scale.

## 8. Primary metrics (frozen; §17)

1. **Attributed lead time** (gradual attacks): `attack_onset − first valid
   attributable warning`, sustained-until-onset policy, pair-gated attribution
   (`warnings.attribute_warnings` — the mandatory gate).
2. **Early-warning success rate**: fraction of attack scenarios receiving valid
   pre-onset warning (per attack family; sudden attacks reported SEPARATELY — §23).
3. **False early-warning rate**: separate for NORMAL and BENIGN_DRIFT.
4. **Forecast gain** vs the conventional detector (identical scenarios).
5. **AUPRC** (class-imbalance-sensitive).

Secondary (§18): AUROC, Brier, ECE, precision, recall, F1, warning duration,
warnings per scenario.

## 9. Statistical method (frozen; §19/§20)

- **Unit of independence = the SCENARIO.** Windows are NOT independent.
- **Scenario bootstrap** (B=2000 resamples of scenarios with replacement,
  seed 2026) for CI on: warning success rate (attack scenarios), median/mean lead
  time (successful warnings), false-warning rate (benign scenarios), forecast gain
  (paired scenario differences). 95% percentile CIs.
- **Split-seed variability** (§25): 5 independent split seeds → mean, median,
  range, and 95% CI across split AUROC/success-rate values.
- Integer metrics reported at sample-justified precision; no fake precision (§20).
- Per-attack 95% CIs computed only where the family has ≥ 5 successful warnings;
  otherwise the raw count is reported with an explicit insufficient-sample note (§9).

## 10. Success criteria (pre-registered)

- **ROBUST early-warning signal**: gradual-attack warning success ≥ 0.7 with
  95% CI lower bound ≥ 0.5, median lead ≥ 50 blocks, FWR(NORMAL) ≤ 0.3 and
  FWR(BENIGN_DRIFT) ≤ 0.3, consistent across ≥ 4 of 5 split seeds.
- **ATTACK-SPECIFIC robust signal**: the above holds per gradual family
  (lo-manipulation AND calibration-manipulation individually), sudden attacks 0%
  (correct physics), OOD jamming reported as baseline (not required to succeed).
- **WEAK signal**: signal exists but CIs include operationally useless values
  (e.g. lower bound < 0.5) or FWR exceeds 0.3 on a benign class.
- **NO signal**: warning success ≈ 0 on gradual attacks at all horizons.
- **ARTIFACT/LEAKAGE**: signal collapses under the leakage audit or split-seed
  variation (Phase 2/3 pattern).
- Negative results (lead ↓ / FWR ↑ vs Phase 3) are reported honestly (§41).

## 11. Graph decision gate (pre-registered; §31–§43)

1. Write `docs/graph-hypothesis.md` BEFORE any GNN implementation: what the graph
   represents, why feature/sequence models cannot already capture that information,
   a concrete testable value hypothesis.
2. The GNN is implemented ONLY IF: (a) the sequence-model gate above yields a
   robust signal, AND (b) the hypothesis identifies a SPECIFIC cross-component
   information gap, AND (c) a first small model (heterogeneous temporal graph →
   message passing → temporal pooling → forecast head) can test it with the
   IDENTICAL harness (same splits, policy, metrics).
3. Success is NOT "GNN AUROC > logistic AUROC" alone: at least one PRIMARY
   operational dimension must improve (attributed lead time, early-warning success
   at comparable FWR, OOD detection, calibration, seed robustness) without
   substantial degradation elsewhere. Graph-ablation + graph-shuffle test required
   if implemented.
4. Gate outcome: exactly one of PROCEED / HOLD / REJECT. HOLD ≠ failure.

## 12. Reproducibility contract (§44)

Every experiment records: dataset manifest (+ generation_config hash), commit hash,
feature schema version, model config, seed, split, environment versions. Metrics
must reproduce exactly on rerun; divergence → investigate before continuing.

## 13. Version

`phase4-protocol v1` (this document, 2026-10-09, commit recorded at freeze time).
The final Phase 4 test results are generated AFTER this freeze.
