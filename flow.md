# flow.md

HOW the system works and HOW data moves through it. Updated continuously.
Status markers distinguish verified behavior from design intent.

## 0. Current status

Metric-integrity & telemetry-robustness workstream (2026-10-11). Three defects
established by inspection and measurement, all corrected in measurement (the
frozen Phase 4/5 datasets and artifacts are UNCHANGED):

1. **Time units** — the simulator time base (`BLOCK_MS = 10.0`, i.e. 0.01 s/block)
   was correct in code; Phase 5 *report prose* used 0.1 s/block, inflating every
   reported lead-time by 10x. Single authority now `src/quantumattack/temporal_units.py` (D-039).
2. **Horizon validity** — warnings with lead > H were credited as H-forecasts.
   29 of 79 anticipatory warnings (37%) exceeded their horizon. Now classified
   into `horizon_valid_forecast` / `extended_pre_onset_alert` / `onset_detection` /
   `post_onset_confirmation` (D-040).
3. **Noise units** — the "robustness cliff at sigma>=0.02" was an artifact of
   absolute noise on features spanning ~17 orders of magnitude. Re-measured in
   train-sigma units the degradation is gradual (0.896 -> 0.549) (D-042).

Also: Wilson intervals replace degenerate bootstrap event-rate CIs (D-041);
NORMAL false alarms root-caused to sustained benign drift (D-043); frozen
probabilities found miscalibrated (ECE 0.191) and corrected by validation-fit
Platt scaling (D-044).

Protocol: `docs/reliability-evaluation-protocol.md` (frozen v1).
Evidence: `docs/reliability-research-report.md`.

## 0b. Prior status (preserved research record)

Phase 5 COMPLETE (2026-10-09): Independent Generalization, Simulator Validity & Forecasting Robustness.
Pre-registered protocol (docs/phase5-protocol.md v1) with 160 scenarios across 4 disjoint generalization partitions:
- G1 (Scenario Generalization): unseen seeds (H=100 AUROC 0.901, gradual warn rate 90.0%, median lead 78–99 blk).
- G2 (Parameter Extrapolation): fast/slow ramps, steep biases (AUROC 0.863, gradual warn rate 71–86%).
- G3 (Environmental Stress): extreme drift, intense disturbance, thermal stress (FWR = 0.00% across all 30 scenarios).
- G4 (Attack Stress / Hybrid): dense probe jamming (100% warning, median lead 147 blk) vs sudden jamming (26.7%, median lead 0 blk).
- G5 (Simulator Validity): comprehensive audit (docs/simulator-validity-audit.md); simulator declared SYNTHETIC ONLY.
Controlled stress testing (Tests A–I) completed (docs/phase5-robustness-report.md).
Scientific gate: **ATTACK-SPECIFIC ROBUST GENERALIZATION**.
Simulator Evidence Status: **SYNTHETIC ONLY** (no hardware validation claimed).
Graph-model gate: **HOLD** (precursors remain single-component temporal dynamics; no cross-node dependency gap).
113 unit/integration tests passing (pytest tests/).

## 1. Implemented flow (VERIFIED — Phase 1)

```text
Scenario config (configs/simulation/phase1.yaml or ScenarioConfig)
    ↓  generate.load_config(...)            WHY: config-first design (D-009; §20)
    ↓  generate.build_scenario_configs(...) WHY: expand batch → validated ScenarioConfigs
    ↓  ScenarioConfig.validate()            WHY: invalid physical configs fail loudly (§20)
    ↓
run_scenario(config)                        [simulator/scenario.py]
    ↓  Clock(n_blocks)                      WHY: seeded block clock; 1 block = 10 ms (§14)
    ↓  ChannelState.create(...)             WHY: fiber loss/tap/background/excess-noise state
    ↓  DetectorState.create(...)            WHY: gain/offset/imbalance/efficiency + LO state
    ↓  EnvironmentState.create(...)         WHY: benign confounders, seeded env stream (D-013)
    ↓  create_attack(config)                WHY: attack module instantiation (D-011)
    ↓  per block:
    │    env.step(env_rng)                  WHY: benign drift evolution (temperature, LO thermal,
    │    │                                      fiber loss, calibration wander, clock, background)
    │    │                                      → coupled into channel/detector state
    │    attack.step(state_view, block)     WHY: attack intervention at/after onset (D-010);
    │    │                                      modifies ONLY its physically-affected subsystem
    │    collector.collect(clock, ...)      WHY: raw telemetry record from state (§22);
    │    │                                      measurement (homodyne.measure_block) +
    │    │                                      parameter estimation (cvqkd.parameter_estimate)
    │    clock.step()
    ↓
labels.build_labels(...)                    [simulator/labels/builder.py]
    WHY: labels derived AFTER simulation from onset metadata only (D-014; §16) —
    state_label, current_attack, y_H per horizon, drift-episode ids
    ↓
export.export_batch(results, out_dir)       [simulator/export/parquet.py]
    WHY: per-scenario Parquet + manifest.json with schema/column classes (§35)
    ↓
data/phase1/<scenario_id>.parquet + manifest.json
```

## 2. Flow call tree (actual names)

```text
python -m quantumattack.simulator.generate --config configs/simulation/phase1.yaml --out data/phase1
└── generate.main(argv)
    └── generate.load_config(path)               WHY: YAML/JSON batch spec
    └── generate.build_scenario_configs(batch)   WHY: batch → ScenarioConfigs (pairs expanded)
        └── generate._attack_from_dict(d)        WHY: attack kwargs filtered to dataclass fields
        └── generate._env_from_dict(d)           WHY: env overrides filtered to dataclass fields
    └── scenario.run_scenario(cfg)               WHY: one deterministic run end-to-end
        ├── ScenarioConfig.validate()            WHY: fail loudly on invalid configs (§20)
        ├── rng.make_rng(seed, stream)           WHY: separate env/attack streams (D-015; §18)
        ├── Clock(n_blocks)                      WHY: monotonic block clock (§14)
        ├── channel.optical.ChannelState.create  WHY: channel baseline state
        ├── detectors.homodyne.DetectorState.create WHY: detector + LO state
        ├── environment.drift.EnvironmentState.create WHY: benign confounder state
        ├── create_attack(cfg) → attacks.<type>  WHY: attack module (base.AttackModule)
        ├── loop over blocks:
        │   ├── environment.drift.EnvironmentState.step   WHY: benign OU/sinusoid/spike evolution
        │   ├── (coupling into channel/detector state)    WHY: drift must reach telemetry (§12)
        │   ├── attacks.<AttackModule>.step(state_view, block) WHY: onset semantics (D-010)
        │   ├── telemetry.collector.TelemetryCollector.collect
        │   │   ├── detectors.homodyne.measure_block      WHY: heterodyne Gaussian statistics
        │   │   └── protocols.cvqkd.parameter_estimate    WHY: T̂/ε̂/SNR/SKR from current state only
        │   └── Clock.step()
        ├── labels.builder.build_labels(...)      WHY: causal labels from onset metadata (§16)
        └── metadata dict (scenario_id, pair_id, attack_onset, ...) WHY: traceability (§33)
    └── export.parquet.export_batch(results, out_dir)
        ├── export.parquet.export_scenario(...)   WHY: one Parquet per scenario
        └── manifest.json                         WHY: schema version + column classes + configs (§21)
```

## 3. Data flow per stage (VERIFIED for Phase 1 stages)

- **Config → Scenario**: `ScenarioConfig` dataclasses (protocol/channel/environment/
  attack/horizons) validated at construction; `config_hash` for reproducibility (§21).
- **Scenario → Telemetry**: per block, `TelemetryCollector.collect` emits 35 raw
  feature columns + 8 eval-only ground-truth columns (`true_*`) + timestamp fields.
  Attacks/ drift modify state; telemetry is a pure function of state.
- **Telemetry → Labels**: `build_labels` derives `state_label` (ATTACK > PRECURSOR >
  BENIGN_DRIFT > NORMAL), `current_attack`, `future_attack_h{H}` (y_H(t)=1 iff
  t < onset ≤ t+H), `drift_episode_id` — from onset metadata ONLY (no future info
  in features; leakage risks in docs/dataset-spec.md §4).
- **Export**: Parquet per scenario + manifest with column classes (metadata/labels/
  eval_only/features — machine-readable, `src/quantumattack/dataset.py`).
- **Analysis**: `scripts/analyze_precursors.py` compares attack vs matched benign
  runs across all seeds (effect sizes in benign σ units; Cat 1–4 classification).

## 3b. Phase 2 evaluation flow (VERIFIED)

```text
data/phase1/*.parquet (Phase 1 telemetry)
    ↓  harness.run_evaluation(...)                       [evaluation/harness.py]
    ↓  features precomputed or computed here             WHY: causal features (D-019)
    ↓  splits.split_scenarios(entries, SplitConfig)      WHY: scenario-level, pairs atomic (D-021)
    ↓  pair_isolation_check(split, entries)              WHY: matched pairs never cross splits (§21)
    ↓  logistic.train_forecaster(frames, split, mc)      WHY: per-horizon LogisticRegression (D-022)
    │    └── build_xy(...)                               WHY: y_H(t)=1 iff t<onset≤t+H; y=0 for t≥onset (§19)
    │    └── fit_horizon_model(...)                      WHY: scaler fit on TRAIN only (§24)
    ↓  logistic.predict_frames(frames, eval_ids, models) WHY: P(attack within H) per block (§26)
    ↓  metrics: classification_metrics + calibration_error  WHY: AUROC/AUPRC/Brier/ECE (§27/§28)
    ↓  warnings.evaluate_scenario_warnings(...)          WHY: warning policy → warning times (D-023)
    ↓  warnings.attribute_warnings(...)                  WHY: pair-gated attribution — warnings whose
    │                                                       matched benign twin fired identically are
    │                                                       NOT attack anticipation (Phase 2 gate fix, §53)
    ↓  conventional: calibrate_thresholds (benign TRAIN only) + detect_warnings
    ↓  forecast-vs-conventional comparison               WHY: lead-time gain, not accuracy (§36)
    ↓
artifacts/phase2/eval/{predictions.parquet, metrics.json, experiment_manifest.json}
```

Commands (all reproducible; artifacts git-ignored):

```powershell
PYTHONPATH=src python -m quantumattack.features_cli --data data/phase1 --out artifacts/phase2/features
PYTHONPATH=src python -m quantumattack.ablation --out artifacts/phase2/ablation
python scripts/evaluate_early_warning.py   # thin wrapper over harness.run_evaluation
```

Key Phase 2 findings (evidence: artifacts/phase2/eval/metrics.json + ablation):

- Row-level discrimination exists (AUROC 0.70–0.84 by horizon/split seed).
- Attributed anticipatory warnings (benign-twin-gated) = 0% at H=100, thr=0.5/k=3:
  on PAIRED scenarios the benign twin fires identically pre-onset (bit-identical
  benign trajectory), so pre-onset warnings are benign-drift alarming, not attack
  anticipation. Policy selection on VAL (thr=0.5/k=3) keeps 100% pre-onset attack
  warnings at 64–79% benign false-warning rate — the model does not separate
  benign drift from precursor drift at this policy/dataset scale.
- Ablation: group D (all features) best at H=10 (AUROC 0.839 vs 0.813 base);
  differences help H=10; temporal stats improve calibration (Brier 0.010–0.08 vs
  0.19 base) but not lead-time attribution.

## 3c. Phase 3 flow (IMPLEMENTED — unpaired forecasting + temporal models)

```text
Scenario generator (simulator/generate.py: unpaired seed pools + per-scenario
                    parameter sampling + name→attack_type mapping)
    ↓  INDEPENDENT scenario assignment (seeds 100–119 attacks / 200–219 benign)
    ↓  splits.split_scenarios(SplitConfig(seed=42, counterfactual_to_train=True,
    │     ood_holdout_family="channel_jamming"))     WHY: pre-registered (D-027);
    │                                                pairs atomic; OOD to test
    ↓  Telemetry (data/phase3; 160 scenarios)
    ↓  features (features.py, schema v2; artifacts/phase3/features)
    ↓  Sequence construction (models/sequences.py: build_sequences — L=100,
    │     ordered, no future telemetry; NaN windows skipped)
    ↓  Baselines (baselines/logistic.py re-run) | GRU (models/gru.py) | TCN
    │     (models/tcn.py: causal left-padded dilated convolutions)
    ↓  Future attack probability P(attack within H) (models/temporal_eval.py)
    ↓  Warning policy (baselines/warnings.py: WarningPolicy.sustained_until_onset —
    │     transient spikes are not warnings; D-028)
    ↓  INDEPENDENT early-warning evaluation (Metric A: metric_a_independent)
    ↓  COUNTERFACTUAL attribution evaluation (Metric B: metric_b_counterfactual —
    │     paired runs train-only; warnings attack AND NOT twin = attributable)
    ↓  Lead-time analysis (median/p25/p75/p90/std/min/max; nulls preserved)
    ↓  OOD analysis (held-out channel_jamming family)
    ↓  Model comparison (harness metrics; same input/splits/policy for all models)
```

Key Phase 3 findings so far (evidence: artifacts/phase3/eval-logistic/metrics.json,
eval-gru/metrics_gru.json):

- Logistic (unpaired, sustained policy): calibration/lo attacks 67–100% independent
  success, median lead 78–127 blocks (0.8–1.3 s); jamming (OOD) 3–12%; intercept-
  resend 0% (correct physics); FWR NORMAL 0.21, BENIGN_DRIFT 0.0.
- GRU (2,561 params, 10 epochs, batch 128, pos_weight auto=32.2): AUROC 0.724/0.829/
  0.825/0.836 (H=10/25/50/100); independent success 0.58–0.92, median lead
  108–137 blocks; ATTRIBUTED (counterfactual, 6-pair test subset) 0.67–0.83.
- The sustained-until-onset policy fixed the Phase 2/3 artifact (warmup-noise
  warnings); results are now physically coherent.

## 3d. Metric-integrity & reliability evaluation flow (VERIFIED 2026-10-11)

```text
FROZEN inputs (unchanged)
    data/phase4/{manifest.json,*.parquet}   + artifacts/phase4/features/
    data/phase5/{manifest.json,*.parquet}   + artifacts/phase5/features/
    ↓  splits.split_scenarios(manifest, SplitConfig(seed=42, …))
    WHY: scenario-level isolation; pairs atomic; OOD family → test (D-021/D-027)
    ↓  logistic.build_xy(train_frames, train, H, ModelConfig, feature_cols)
    WHY: y_H(t)=1 iff t<onset<=t+H; train-only rows (t>=min_history_blocks)
    ↓  logistic.fit_horizon_model(X, y, H, …)   WHY: scaler fit on TRAIN ONLY
    ↓  feature_scale_from_train(X_train)
    WHY: per-feature TRAIN std/IQR for scaled noise (never fit on eval data)
    ↓
    ── per evaluation scenario (G1/G2/G3/G4) ──
    ↓  predict_proba(model, X)  →  p_attack_future_h{H} per block
    WHY: sigmoid over train-standardized features; causal (uses only t and past)
    ↓
    ├─ [1] warnings.warning_blocks_for_scenario(df_pred, H, WarningPolicy)
    │      WHY: K-consecutive runs above threshold; sustained_until_onset
    │           filters transients (retained set uses onset — EVALUATION ONLY)
    │      ↓  warnings.warning_time(fires) → first causal block of the run
    │      ↓  forecast_horizons.classify_warning_outcome(warn_block, onset, H, grace)
    │      WHY: enforces lead<=H; returns ONE of five exclusive outcomes (D-040)
    │      ↓  statistics.wilson_interval(successes, n)   WHY: non-degenerate CI (D-041)
    │
    ├─ [2] classification_metrics + calibration_error
    │      ↓  scenario-clustered bootstrap over SCENARIOS for AUROC CI (B=1000, seed 2026)
    │
    ├─ [3] noise_models.apply_perturbation(X, PerturbationSpec, FeatureScale)
    │      WHY: explicit units (train_sigma | feature_range | raw_absolute); (D-042)
    │      ↓  re-predict → AUROC/AUPRC/Brier per condition
    │
    ├─ [4] feature-subset refit → AUROC delta (fragility ablation)
    │
    ├─ [5] P(H1) <= P(H2) <= … coherence violation rate across horizons
    │
    ├─ [6] benign-only false-alarm burden: scenario rate / warnings per scenario /
    │      warning-load fraction / episodes per 1000 simulated seconds
    │
    ├─ [7] longest_run_above(p) + run_ends_at_block
    │      WHY: tests whether a benign false alarm is sustained to scenario end (D-043)
    │
    └─ [8] Platt / isotonic calibration fit on Phase 4 VAL ONLY
           WHY: raw balanced-classifier probabilities are miscalibrated (D-044)

artifacts/reliability/evaluation/reliability_report.json
```

### Timing, availability and failure handling

- **WHEN**: steps 1–8 run at evaluation time only. Nothing here executes inside the
  simulator loop or during training.
- **Availability**: `temporal_units` is a pure constant lookup — no I/O, no state.
  `forecast_horizons.classify_warning_outcome` is pure and total over its inputs.
- **Failure handling**: `classify_warning_outcome` raises `ValueError` for
  `horizon < 1`; `wilson_interval` raises on impossible counts (k > n, negatives)
  and returns all-`None` for `n == 0` (undefined, never 0.0); the clustered
  bootstrap records `n_failed_resamples` rather than silently shrinking the interval.
- **Reproducibility**: bootstrap seed 2026 is recorded in every CI block; AUROC
  resampling counts failed resamples explicitly.

### Unit discipline (normative)

Every reported duration MUST name its unit. The conversion is
`seconds = blocks × 0.01` via `temporal_units.blocks_to_seconds`. Horizon
durations: H=10 → 0.1 s, H=25 → 0.25 s, H=50 → 0.5 s, H=100 → 1.0 s.
Warning lead times are reported in BOTH blocks and seconds from the same source
value; a mismatch between them is a bug (regression-tested).

## 4. Downstream flow (DESIGN — not yet implemented)

```text
Telemetry (Phase 1 export) → feature engine (Phase 4: features.py expansion)
    → next-state prediction (Phase 7) → residuals
    → P(attack within H) multi-horizon (Phase 11 fusion)
    → known/unknown assessment (Phase 9 open-set)
    → explainable early warning (Phase 12) → dashboard (Phase 13)
```

The critical distinction:

```text
Conventional detector:  current state → threshold crossed?   (docs/evaluation-protocol.md §1)
Our system:             past trajectory → expected next state → divergence +
                        precursor resemblance → P(attack in next H windows)
```

## 5. Documentation flow (process loop, ACTIVE)

Every phase: inspect → implement → test → verify → update decisions.md (D-NNN),
flow.md (this file), handoff.md, docs/implementation-checklist.md (evidence-backed
statuses only).

## 6. Current execution flow of record

Phase 0 (2026-10-07): audit → docs → initial commit (59892a9). Phase 1 (2026-10-08):
research + simulator + causal labels → commit 16f8406. Phase 2 (2026-10-08): causal
feature layer (154 features, schema v2) → conventional threshold detector →
scenario-level splits with pair isolation → logistic per-horizon forecaster (train-only
scaling) → warning policy + lead-time + false-warning evaluation → pair-gated
attribution (Phase 2 gate fix) → ablations A/B/C/D → multi-seed evaluation (split
seeds 0–3) → reproducibility verified (metrics identical) → decisions D-018..D-025.
Phase 3 (2026-10-08): unpaired dataset (160 scenarios) → pre-registered split + OOD
(channel_jamming held out) → sustained-until-onset policy (D-028) → GRU/TCN benchmark →
Phase 3 report (commit c9cb1a8). Phase 4 (2026-10-09): protocol pre-registration
(docs/phase4-protocol.md v1) → scale-up to 284 scenarios with disjoint stride-7 seed pools
(train/val/test/ood) → label window bug fix on disturbance episodes → multi-split evaluation
(5 seeds: 42, 7, 101, 2024, 31337) → scenario-level bootstrap CIs (B=2000) → attack-specific
lead times & FWR → feature redundancy analysis & Feature Freeze v1 (docs/feature-freeze-v1.md) →
graph hypothesis evaluation & Graph Gate: HOLD (docs/graph-hypothesis.md) → Scientific Gate:
ATTACK-SPECIFIC ROBUST SIGNAL → 109 tests passing → decisions D-029..D-033.
