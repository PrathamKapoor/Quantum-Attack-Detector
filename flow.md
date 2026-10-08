# flow.md

HOW the system works and HOW data moves through it. Updated continuously.
Status markers distinguish verified behavior from design intent.

## 0. Current status

Phase 1 COMPLETE (2026-10-08): the Phase 1 simulator pipeline is implemented and
verified (40 tests passing; 65-scenario validation dataset exported). Sections 1–4
below use ACTUAL file/function names from `src/quantumattack/`. Later-phase stages
(feature engine expansion, models, dashboard) remain design-only.

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

Phase 0 (2026-10-07): audit → environment probes → snippet-level research → docs →
initial commit. Phase 1 (2026-10-08): docs re-read → environment re-validation →
research landscape (20+ sources verified) → threat model/attack/precursor taxonomies →
time semantics → telemetry/feature/dataset specs → simulator package (src/quantumattack,
15 modules) → 40 tests passing → 65-scenario dataset (data/phase1) → precursor
analysis (docs/precursor-analysis.md) → decisions D-008..D-017.
