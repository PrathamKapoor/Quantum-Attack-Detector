# Confirmatory Evaluation Protocol (frozen v1)

Status: **FROZEN 2026-10-12** — written and committed BEFORE any confirmatory
scenario was generated or inspected. This protocol binds the untouched-population
experiment defined in `scripts/evaluate_confirmatory.py`.

The historical G1–G4 populations (`data/phase5/`, seeds 20000–35203) are
**exposed**: they were generated and inspected during earlier workstreams. They
remain valid historical evidence; no new confirmatory claim is made from them.

---

## 1. Frozen configuration (hash-verified at run time)

| Item | Frozen value | Verified by |
|---|---|---|
| Simulator version | `quantumattack.simulator` at HEAD `8efa9b0` + confirmation-evidence commit | `git rev-parse HEAD` recorded in the run manifest |
| Forecast model | logistic, group D (189 features), `C=1.0`, `class_weight='balanced'`, `solver='liblinear'`, train-only scaler, `min_history_blocks=100`, horizons (10,25,50,100) | `ModelConfig.to_dict()` in manifest |
| Training population | Phase-4 train split (seed 42, counterfactuals to train, OOD family `channel_jamming`) — unchanged | split ids in manifest |
| Calibration split | Phase-4 validation benign only | split ids in manifest |
| Forecast warning policy | `P>=0.5, K=3, cooldown=50, grace=5, sustained_until_onset=False` (operational view) | manifest |
| Detector | one-sided CUSUM, per-scenario warmup normalization, `warmup_blocks=200`, Huber cap 10, missing-reset after 5 | manifest |
| Detector calibration | reference = Phase-4 train benign; (k, h) selected on Phase-4 **validation** benign only, budget FPR <= 0.10; (k=2.0, h=200.0) frozen BEFORE generation; grid and selection rule pre-declared | manifest + this document |
| Confirmation evidence | detector-derived (`confirmation_evidence_from_cusum`); the state machine confirms only from this mask | D-050 contract |
| Telemetry channels | the 7 monitor-visible CV-QKD indicators (INDICATORS) | `conventional.INDICATORS` |
| Onset semantics | unchanged per-attack definitions (docs/time-semantics.md §3) | reference |
| Event counting | emission timestamps only (D-049); episodes from `alert_episodes_from_trace`; occupancy from state timeline (D-051) | D-049/D-051 |
| Horizon validity | `0 < onset - emission <= H` for H=100; beyond-H is `extended_pre_onset_alert` | D-040 |
| Statistical methods | Wilson score intervals (95%) for rates; scenario-level independence | D-041 |
| Primary metrics | (a) benign false-alarm scenario rate; (b) attack horizon-valid forecast rate; (c) detector pre-onset detection rate; (d) detector sensitivity incl. post-onset; (e) episodes/1000 s; (f) occupancy fraction | this document |
| Acceptance criteria | none re-tuned after generation; all results reported regardless of favourability | this document |

**Frozen detector operating point:** `k_drift = 2.0`, `h_threshold = 200.0`,
`persistence_k = 3`, `cooldown_blocks = 50`, `warmup_blocks = 200`. These values
were measured on Phase-4 validation benign (19 scenarios) in the previous
workstream and are NOT re-selected here.

## 2. Confirmatory scenario populations (pre-registered)

Seed block **41000–42999** (stride 7; 286 available seeds for 148 scenarios),
globally disjoint across groups and disjoint from:
- Phase-4 train/val/test (< 15000, stride 7),
- G1 (20000–20413), G2 (25000–25273), G3 (30000–30203), G4 (35000–35203),
- all probe seeds used during development (40998/40999 excluded).

| Group | Population | Scenario definition | n |
|---|---|---|---|
| C1 NORMAL | `plain`, `channel-drift`, `disturbance` | identical to G1 benign definitions | 30 |
| C1 gradual attacks | `lo-manipulation`, `calibration-manipulation` | identical to G1 attack definitions (onset sampled 900–1400) | 20 |
| C1 sudden | `intercept-resend` | identical to G1 definition | 10 |
| C2 ramps | `lo-manipulation-fast-ramp`, `lo-manipulation-slow-ramp`, `calibration-manipulation-steep`, `calibration-manipulation-slow` | identical to G2 | 28 |
| C3 environmental stress | `normal-extreme-drift`, `normal-intense-disturbance`, `normal-thermal-stress` | identical to G3 | 30 |
| C4 jamming | `channel-jamming-dense-probes`, `channel-jamming-sudden-high` | identical to G4 | 30 |

Total: **148 scenarios** (~9 min generation + ~15 min features; measured probe:
1.0 s gen + 5.7 s features per scenario).

**Protocol amendment record (pre-generation):** the initially frozen seed block
(41000–41299, 43 seeds) was arithmetically insufficient for the 148 pre-registered
scenarios; this was discovered during a dry-run of scenario *construction* before
any confirmatory data was generated or inspected. The block was widened to
41000–42999 with globally disjoint per-group allocation. No evaluation outcome
was viewed before or during this amendment; no threshold, model, or metric
definition changed.

**Exclusions:** scenario ids `*-s40998`, `*-s40999` (used for a timing probe
during protocol design, disclosed here) are NOT part of any confirmatory group.

## 3. Pre-declared analysis plan

1. Load frozen model config and detector parameters from the run manifest; abort
   on mismatch with this document.
2. Verify seed disjointness against ALL historical manifests before evaluation.
3. Run the forecaster and detector per scenario; record emission-only events.
4. Outcomes per event (mutually exclusive, emission-based):
   `horizon_valid_forecast` / `extended_pre_onset_alert` / `onset_detection` /
   `post_onset_confirmation` / `no_warning`; detector: `pre_onset_detection` /
   `at_onset_detection` / `post_onset_detection` / `no_detection`.
5. Scenario-level outcomes use the FIRST emitted event only; episode counts and
   occupancy are reported separately from event counts.
6. Wilson 95% intervals on every rate. No bootstrap re-selection, no threshold
   changes, no re-runs.
7. Negative controls executed on the confirmatory set:
   - time-only predictor (block index as sole feature) on C1 attacks;
   - benign matched-envelope check (detector statistic distribution on C1/C3
     benign vs C1 attacks pre-onset);
   - onset-earliness control: fraction of detector pre-onset alerts emitted
     before `precursor_start` (i.e. before any modelled adversarial mechanism).
8. All results (favourable or not) are written to
   `artifacts/confirmatory/<utc-stamp>/` and are never overwritten.

## 4. Non-goals

- No hardware validation is claimed; all results remain SYNTHETIC ONLY.
- No model retraining, threshold tuning, or feature changes.
- No comparison of the forecaster against the detector is used to claim
  superiority; the measured trade-offs are reported with intervals.

## 5. Disclosure

- The timing probe (`*-s40998/40999`) measured generation/feature cost only;
  no forecast or detector output was computed on it.
- The detector operating point (k=2.0, h=200.0) was selected on Phase-4
  validation benign during the previous workstream and is treated here as frozen;
  its selection never used G1–G4 or confirmatory outcomes.
- The forecast model was trained on Phase-4 train only; its frozen hyper-parameters
  predate this protocol.