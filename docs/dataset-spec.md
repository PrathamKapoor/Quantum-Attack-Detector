# Dataset Specification — Schema, Labels, Counterfactuals, Splits

Created 2026-10-08 (Phase 1). Defines the dataset schema, per-record column classes,
matched-counterfactual protocol, and partition strategy for later phases. Normative
parts are enforced by tests (`tests/test_metadata_isolation.py`,
`tests/test_labels.py`, `tests/test_counterfactual.py`).

## 1. Dataset schema (v1, `schema_version: "1"`)

Each record = one telemetry block of one scenario run. Records are traceable to their
scenario via metadata columns. Column classes are machine-readable (see §2).

| Column | Type | Class | Meaning |
|---|---|---|---|
| `scenario_id` | str | metadata | `<class>-<attacktype or drift>-s<seed>` unique per run |
| `pair_id` | str | metadata | matched-counterfactual pair identifier (empty if unmatched) |
| `arm` | str | metadata | `normal` or `attack` (within a pair); empty if unmatched |
| `seed` | int | metadata | global seed of the run |
| `protocol` | str | metadata | `cvqkd-heterodyne` (only value in Phase 1) |
| `sim_version` | str | metadata | simulator package version |
| `config_hash` | str | metadata | sha256 of the scenario config (first 12 hex) |
| `block_index` | int | evaluation-only | 0..N−1; block t covers `[t·10ms, (t+1)·10ms)` |
| `timestamp_ms` | float | evaluation-only | block start in ms (= block_index × 10) |
| `scenario_class` | str | metadata | NORMAL / BENIGN_DRIFT / ATTACK |
| `attack_type` | str | metadata | `none` / `intercept_resend` / `lo_manipulation` / `calibration_manipulation` / `channel_jamming` / (composite ids later) |
| `attack_onset` | int | metadata | block index of attack onset (−1 if no attack) |
| `precursor_start` | int | metadata | block index where precursor starts (== attack_onset for class C; −1 if no attack) |
| `precursor_class` | str | metadata | `none`/`A`/`B`/`C` — per docs/precursor-taxonomy.md |
| `state_label` | str | label | ATTACK / PRECURSOR / BENIGN_DRIFT / NORMAL (precedence per docs/time-semantics.md §5) |
| `current_attack` | int | label | 1 if attack operational during block t |
| `future_attack_h10` | int | label | y_H(t), H=10 blocks (0.1 s) |
| `future_attack_h25` | int | label | y_H(t), H=25 (0.25 s) |
| `future_attack_h50` | int | label | y_H(t), H=50 (0.5 s) |
| `future_attack_h100` | int | label | y_H(t), H=100 (1.0 s) |
| `drift_episode_id` | int | label | episode index active during block t (−1 if none); ground-truth event id |
| telemetry columns | float | feature (candidates) | per docs/telemetry-spec.md §Implemented features |
| `true_T`, `true_xi`, `true_lo_power`, `true_det_gain`, `true_det_offset`, `true_background`, `true_clock_offset`, `true_channel_condition` | float/int | evaluation-only | ground-truth simulator state — the real monitor would NOT see these; never model inputs |

## 2. Machine-readable column classes

`src/quantumattack/dataset.py` exposes:

- `METADATA_COLUMNS`, `LABEL_COLUMNS`, `EVAL_ONLY_COLUMNS`, `FEATURE_COLUMNS` —
  derived as: all telemetry-spec feature names minus metadata/label/eval-only sets.
- `RESTRICTED_COLUMNS` = metadata + label + eval-only sets.
- Invariant: `FEATURE_COLUMNS ∩ RESTRICTED_COLUMNS = ∅` (tested).

`attack_type`, `attack_onset`, `precursor_start`, `current_state`(=`state_label`),
future labels, `scenario_class`, `pair_id` NEVER become model inputs (master prompt
§34; tested).

## 3. Matched-counterfactual protocol (master prompt §18)

For a given configuration, a PAIR consists of two runs:

- **Run A (`arm=normal`)**: benign system, no attack.
- **Run B (`arm=attack`)**: same initial conditions and same benign-condition
  trajectory, attack introduced.

Preserved across the pair (identical by construction):

- global seed,
- initial channel state (fiber loss, temperature phase),
- environmental trajectory (drift processes use the same seed stream),
- baseline detector characteristics,
- initial protocol parameters.

Only the attack intervention differs. Implementation: the simulator draws ALL
benign randomness from a seeded `numpy.random.Generator` derived from
`(seed, "environment")`; attack randomness (ramp noise, probe schedule) from
`(seed, "attack")`. Run A simply skips attack stepping — the benign streams are
bit-identical between arms, so the ONLY difference is the attack's contribution.

Pairing IDs: `pair_id = "pair-<n>"` assigned per generated pair;
`arm ∈ {"normal","attack"}` identifies the member. Unmatched scenarios have
empty pair_id/arm.

This enables the later analysis: is a purported precursor attack-specific or merely
environmental drift? (Compare Run A vs Run B telemetry, master prompt §36/§37.)

## 4. Leakage risks (master prompt §17) — checked at data-design level

| # | Risk | Mitigation | Test |
|---|---|---|---|
| 1 | secret-key values using future samples | SKR formula uses only state ≤ t (per-block asymptotic estimate) | `test_labels.py::test_skr_uses_only_current_state` |
| 2 | rolling windows centered on t | all rolling stats trailing; feature layer builds them from past-only buffers | `test_features.py` (trailing property) |
| 3 | normalization using complete scenario statistics | per-scenario normalization forbidden; Phase 1 features are raw + causal transforms only | design-level (no such code exists) |
| 4 | labels encoded in simulator state | labels derived from onset metadata AFTER simulation; state carries no label | `test_labels.py` |
| 5 | post-onset values in precursor samples | y_H(t)=0 for t ≥ attack_onset; PRECURSOR label strictly inside [precursor_start, onset) | `test_labels.py::test_future_label_definition` |
| 6 | derivatives using future points | backward differences only | `test_features.py` |
| 7 | attack IDs exposed as features | RESTRICTED_COLUMNS excluded from FEATURE_COLUMNS | `test_metadata_isolation.py` |
| 8 | sequence padding revealing onset position | padding at START (later phase, documented here) | design-level note in feature-spec |
| 9 | drift episodes inferred from telemetry (circular BENIGN_DRIFT labels) | episodes are named simulation events, exported as ground-truth ids | `test_labels.py::test_drift_episode_labels` |
| 10 | eval-only ground-truth state columns leaking into features | true_* in RESTRICTED_COLUMNS | `test_metadata_isolation.py` |

## 5. OOD partition concept (master prompt §42)

Later evaluation must hold out ENTIRE attack families. Concept (not exercised in
Phase 1):

```text
train scenarios:  attack families {lo_manipulation, calibration_manipulation, channel_jamming}
test (OOD):       attack family {intercept_resend}   ← never appears in train configs
```

Implementation note for later phases: the split is by `attack_type` at the SCENARIO
level, never by per-block rows; the held-out family's scenarios must not share
configs (beyond protocol constants) with training scenarios. Leakage tests for the
split belong to the dataset-generation phase.

## 6. Train/validation/test split strategy (master prompt §43)

No random splitting of adjacent windows. Planned strategy (later phases):

- split by SCENARIO (whole runs), never by block;
- within a class, split by seed-block: train seeds / validation seeds / test seeds
  are disjoint seed sets (same config, different seeds);
- matched pairs stay within one partition (both arms same partition);
- chronological block splitting (early vs late scenario segments) only as an
  additional robustness check;
- OOD test partition per §5.

Explicit leakage tests for splits belong to later phases (documented here as the
design contract).

## 7. Export format (master prompt §35)

- One Parquet file per scenario run: `data/phase1/<scenario_id>.parquet` —
  telemetry + labels + metadata per record.
- One manifest per batch: `data/phase1/manifest.json` — schema_version, simulator
  version, list of scenarios with configs, seeds, pair assignments, class counts.
- Generation command (Phase 1 standard):
  `python -m quantumattack.simulator.generate --config configs/simulation/phase1.yaml --out data/phase1`
  (small validation dataset only — master prompt §35: generate enough to validate
  behavior, not a giant dataset).
