# flow.md

HOW the system works and HOW data moves through it. Updated continuously.
Status markers distinguish verified behavior from design intent.

## 0. Current status

Phase 2 COMPLETE (2026-10-08): causal feature layer + forecasting baselines +
lead-time evaluation implemented and verified (63 tests passing; results in
`artifacts/phase2/`, git-ignored). Sections 1–4 use ACTUAL file/function names from
`src/quantumattack/`. Deep temporal models, GNN, dashboard remain design-only.

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
