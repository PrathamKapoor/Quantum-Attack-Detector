# flow.md

HOW the system works and HOW data moves through it. Updated continuously.
Status markers distinguish designed-but-not-implemented from verified behavior.

## 0. Current status

No executable code exists yet (Phase 0, audit only). Sections 1–2 describe the designed
pipeline; every stage will gain a verified WHAT/WHY/HOW/WHEN block as it is implemented.
Per master prompt §5, each implemented action must document WHAT / WHY / HOW / WHEN using
actual file and function names — never invented ones.

## 1. System pipeline (DESIGNED — not yet implemented)

```text
Quantum System Simulation (CV-QKD digital twin)
        ↓
Physical Telemetry (time-indexed measurements)
        ↓
Temporal State Construction (windows, temporal features)
        ↓
Quantum System Graph (physics-informed nodes/edges)
        ↓
Trajectory Representation
        ↓
Future-State Prediction (expected next state)
        ↓
Precursor Pattern Detection (prediction residuals + trajectory anomaly)
        ↓
Future Attack Probability P(attack within horizon H)
        ↓
Known / Unknown Attack Assessment (classification + open-set)
        ↓
Risk Estimation
        ↓
Explainable Early Warning (PREDICTED vs CONFIRMED)
        ↓
Quantum Security Operations Dashboard
```

The critical distinction (master prompt §1/§51):

```text
Conventional detector:  current state → attack?
Our system:             past trajectory → expected next state → divergence +
                        precursor resemblance → P(attack in next H windows)
```

## 2. Planned module layout (PROPOSED — created only when implemented)

```text
qkd_twin/        CV-QKD digital twin + attack injection
telemetry/       time-indexed telemetry capture and storage
features/        physical, temporal, security feature extraction
datasets/        scenario generation, windowing, labeling (current + future-horizon)
models/          benchmark ladder (threshold → classical → temporal → graph → QML)
evaluation/      lead time, precision@horizon, AUROC/AUPRC, calibration, leakage tests
serving/         API layer (only when dashboard phase requires it)
dashboard/       security-operations UI
scripts/         simulate / generate-dataset / train / evaluate / benchmark / demo
docs/            implementation-checklist.md, research-landscape.md, audits
```

The final layout is decided during Phase 1/2 and recorded in decisions.md. Names above are
proposals, not claims of existing files.

## 3. Data flow per stage (DESIGN INTENT — verify on implementation)

Each block will be expanded into verified WHAT/WHY/HOW/WHEN entries as code lands.

- Simulation → Telemetry: the twin advances in fixed timesteps and emits per-timestep
  physical measurements (source, LO, quadratures, detector, timing, channel, security
  metrics). Attack modules inject deviations at defined onsets, with per-attack precursor
  behavior documented (gradual vs sudden, master prompt §9).
- Telemetry → Features: windows are aggregated; temporal features (delta, rolling stats,
  CUSUM, EWMA, …) are computed only from past-and-current samples.
- Features → Prediction: a model predicts the expected next state; residuals
  (actual − expected) are tracked over time as surprise signals.
- Prediction → Early warning: trajectory features feed P(attack within H) for multiple
  configurable horizons; a warning is emitted only from information available at time t.
- Warning → Explanation: top contributing signals, precursor onset time, and the explicit
  PREDICTED vs CONFIRMED distinction accompany every alert.
- All stages → Persistence: every experiment records seed, configs, dataset version,
  software versions, and timestamp (reproducibility rule §30).

## 4. Documentation flow (process loop, ACTIVE)

Every phase: inspect → implement → test → verify → update decisions.md (D-NNN entries),
flow.md (execution paths with WHAT/WHY/HOW/WHEN), handoff.md (12-section state),
docs/implementation-checklist.md (evidence-backed statuses only).

## 5. Current execution flow of record

Phase 0 executed 2026-10-07: filesystem audit (empty repository observed) → environment
probes (versions recorded in docs/phase0-audit.md §3) → web research for the landscape doc
(queries and sources listed in docs/research-landscape.md) → this documentation set →
initial Git commit on `main`. No code paths exist yet.
