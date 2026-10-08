# Time Semantics — Temporal Unit Chain, Onset, Horizon, Labels

Created 2026-10-08 (Phase 1). Defines time BEFORE prediction (master prompt §14/§15).
All values are configurable in scenario configs; defaults below are the Phase 1
standard. Units are stated everywhere; never mix seconds, blocks, and windows without
the conversion factors in §2.

## 1. Realistic anchor (why 10 ms blocks)

Source 8 (Hajomer et al. 2024, VERIFIED FROM SOURCE): 100 MBaud symbol rate, 1e7 ADC
samples per parameter-estimation frame at 1 Gsample/s → **10 ms per frame**; 1e9
coherent states per measurement run. The Phase 1 simulator is a per-block closed-form
Gaussian model (not per-symbol), so the block is its minimum time unit, anchored to
the experimental per-frame parameter-estimation cadence.

## 2. Temporal unit chain (with units)

```text
raw physical process (continuous)
  → simulation block      : 1 block  = 10 ms  = 1e6 symbols @100 MBaud   [simulator timestep]
  → telemetry record      : 1 record per block (100 records/s)          [sampling rate]
  → aggregation window W  : W = 5 blocks = 50 ms (causal, trailing)     [rolling stats]
  → history sequence L    : L = 100 blocks = 1 s                        [model input span]
  → forecast horizon H    : H ∈ {10, 25, 50, 100} blocks                [label lookahead]
  → scenario duration     : default 2000 blocks = 20 s                  [one run]
```

Conversions: `seconds = blocks × 0.01`; `symbols = blocks × 1e6` (at 100 MBaud).
One window = W blocks; a history of L blocks contains L/W windows (Phase 1: 20).

## 3. Attack onset semantics (master prompt §15)

`attack_onset` = **first block in which the malicious mechanism modifies system state
according to the attack's definition** — NOT "first moment telemetry looks abnormal".
Per-attack definitions live in `docs/attack-taxonomy.md` §Detailed entries:

| Attack | attack_onset = first block where… |
|---|---|
| intercept-resend | tap inserted and resend begins (T_true, ε_true switch stepwise) |
| LO manipulation | LO attenuation reaches the configured attack operating point (ramp may have started earlier) |
| detector calibration manipulation | biased gain/offset crosses the configured operating point |
| channel jamming | full-power jamming begins (probe bursts, if any, never move it) |

`lead_time = attack_onset − warning_time` (warning policy in
`docs/evaluation-protocol.md`); a vague onset would make this meaningless, hence the
per-attack precision above.

## 4. Precursor interval semantics

`precursor_start` = first block of the precursor mechanism (class A ramp start or
class B first possible probe burst). Constraints:

- class A/B attacks (when precursor enabled): `precursor_start < attack_onset`;
- class C attacks: `precursor_start == attack_onset` (empty precursor interval);
- probe bursts (class B) live strictly in `[precursor_start, attack_onset)` and are
  telemetry events only — they never move `attack_onset` and are never labeled ATTACK.

## 5. Label semantics (master prompt §16; normative for dataset generation)

For block index t (t indexes the scenario's blocks; block t covers physical time
`[t·10ms, (t+1)·10ms)`):

| Label | Definition |
|---|---|
| `current_attack` | 1 if `attack_onset ≤ t` (attack mechanism operational during block t), else 0. This is the CLASSIFICATION target (later phase). |
| `y_H(t)` (per horizon H) | 1 if `t < attack_onset ≤ t + H` — an attack BEGINS strictly after t within the next H blocks. If the attack already began (`t ≥ attack_onset`), y_H = 0 (that is `current_attack`'s job). This is the FORECASTING target. |
| `state_label` (categorical) | ATTACK if `attack_onset ≤ t`; PRECURSOR if `precursor_start ≤ t < attack_onset` AND the attack has a class A/B precursor; BENIGN_DRIFT if the block falls inside an environment drift EPISODE (see below) in a benign scenario; NORMAL otherwise. Precedence: ATTACK > PRECURSOR > BENIGN_DRIFT > NORMAL. |
| `scenario_class` (metadata, not per-block) | NORMAL (no attack, no drift episodes) / BENIGN_DRIFT (no attack, ≥1 drift episode) / ATTACK (attack scenario, may also contain drift episodes — drift and attack co-occur by design) |

Drift EPISODES are named simulation events (start/end block known to the simulator;
exported as evaluation-only columns), never inferred from telemetry — so BENIGN_DRIFT
labels are ground truth, not a detector output.

Binary y_H semantics: `y_H(t) = 1 ⟺ ∃ attack with onset o: t < o ≤ t + H`, else 0.

## 6. Causality rule (master prompt §17, normative)

Features at time t must contain no information from after t. Concretely:

- every rolling statistic is TRAILING (window ends at t, inclusive);
- derivatives use backward differences only (`x[t] − x[t−1]`, `x[t] − 2x[t−1] + x[t−2]`);
- no normalization using full-scenario statistics (per-scenario normalization is a
  leakage vector; normalizers must be fit on train scenarios only, later phase);
- labels (y_H, current_attack, state_label) and attack metadata
  (attack_type, attack_onset, precursor_start, scenario_class, pair_id) are exported
  in separate, machine-classified columns and NEVER enter the feature set
  (enforced by `tests/test_metadata_isolation.py`);
- sequence padding (later phase) must pad at the START of histories, never the end,
  so padding cannot reveal onset position.

## 7. Horizon selection (master prompt §41)

Default horizons with both windows and physical time:

| Horizon | Blocks | Physical time | Rationale |
|---|---|---|---|
| H1 | 10 | 0.1 s | minimum actionable warning; comparable to a parameter-estimation reporting cadence (10 frames) |
| H2 | 25 | 0.25 s | short-horizon forecast; inside the weakest precursor ramps |
| H3 | 50 | 0.5 s | medium horizon; inside most class-A ramp durations (0.8–2.4 s) |
| H4 | 100 | 1.0 s | long horizon; spans the full history length L; upper bound for actionable warnings |

Rationale vs attack durations: class-A precursor ramps last 40–120 blocks (0.8–2.4 s);
H1–H4 all sit inside the ramp for most configurations, so a correct forecaster can in
principle fire during the ramp. Sudden-onset attacks (class C) make y_H hard by
construction: no telemetry changes before onset, so honest models score near-chance —
the dataset must keep this property (never "fix" it; master prompt §59).

All horizon values are configurable per scenario/config file; the defaults above are
the Phase 1 standard recorded in decisions.md (D-010).
