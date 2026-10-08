# handoff.md

Exact current implementation state for the next coding session. Only verified facts;
UNKNOWN is stated explicitly. Updated at the end of every session.

## 1. Current Phase

Phase 1 — Research, threat model, simulation & precursor design. COMPLETE as of
2026-10-08. Gate result: **PARTIALLY** (gradual attacks show strong pre-onset
structure; sudden-onset attacks show none — scientifically correct, by design).

## 2. Work Completed

- Docs re-read (all); environment re-validated (Phase 0 records stale: Python 3.13.14,
  numpy 2.4.4, qiskit 2.5.1; scikit-learn/torch/networkx/xgboost/fastapi now PRESENT
  globally — see D-016).
- qiskit-aer exact version resolved: **0.17.2**.
- Research landscape strengthened: 27 sources, most VERIFIED FROM SOURCE (full text or
  authoritative records); key negative finding: NO prior work on pre-onset prediction /
  lead-time for QKD attacks (the gap this project addresses).
- Threat model (docs/threat-model.md), attack taxonomy (docs/attack-taxonomy.md),
  precursor taxonomy (docs/precursor-taxonomy.md), time semantics
  (docs/time-semantics.md), telemetry spec (docs/telemetry-spec.md), feature spec
  (docs/feature-spec.md), dataset spec (docs/dataset-spec.md), evaluation protocol
  (docs/evaluation-protocol.md), architecture v1 (docs/architecture-v1.md).
- Simulator package implemented: src/quantumattack (15 modules; architecture in
  docs/architecture-v1.md Part A).
- 40 tests passing (tests/): config validation, reproducibility, physics invariants,
  attack semantics, precursor semantics, labels, metadata isolation, counterfactual.
- 65-scenario validation dataset exported (data/phase1; 5 seeds × 13 scenario
  definitions incl. matched counterfactual pairs).
- Precursor analysis across all seeds (docs/precursor-analysis.md; scripts/analyze_precursors.py).
- decisions.md updated: D-008..D-017.

## 3. Files Changed (Phase 1)

- docs/: threat-model.md, attack-taxonomy.md, precursor-taxonomy.md, time-semantics.md,
  telemetry-spec.md, feature-spec.md, dataset-spec.md, evaluation-protocol.md,
  architecture-v1.md, precursor-analysis.md (new); implementation-checklist.md,
  research-landscape.md (updated)
- src/quantumattack/: __init__.py, dataset.py (new)
- src/quantumattack/simulator/: __init__.py, config.py, clock.py, rng.py, scenario.py,
  generate.py (new)
- src/quantumattack/simulator/{protocols,channel,detectors,environment,attacks,telemetry,labels,export}/:
  __init__.py + cvqkd.py, optical.py, homodyne.py, drift.py, base.py,
  intercept_resend.py, lo_manipulation.py, calibration_manipulation.py,
  channel_jamming.py, collector.py, builder.py, parquet.py (new)
- configs/simulation/phase1.yaml (new)
- scripts/analyze_precursors.py (new)
- tests/: conftest.py, test_config.py, test_reproducibility.py, test_attack_semantics.py,
  test_precursor_semantics.py, test_labels_metadata.py (new)
- decisions.md, flow.md, handoff.md (updated)

## 4. Current Architecture / State

Modular simulator package (docs/architecture-v1.md Part A): config-first validated
dataclasses; per-block Clock (1 block = 10 ms); ChannelState/DetectorState/
EnvironmentState (benign confounders, separate seeded streams); 4 attack modules
(intercept_resend/lo_manipulation/calibration_manipulation/channel_jamming);
TelemetryCollector (35 feature + 8 eval-only columns); build_labels (causal y_H);
Parquet export + manifest. Graph representation DESIGNED only (architecture-v1.md
Part B; 7-node heterograph proposal; no GNN trained).

## 5. Decisions Made (Phase 1)

D-008 single protocol (GMCS CV-QKD heterodyne; confirms D-003) · D-009 temporal unit
chain (1 block = 10 ms; H ∈ {10,25,50,100} blocks) · D-010 onset = mechanism activation
per attack · D-011 four P0 attacks, families merged, precursor mixture · D-012
precursors = PROJECT INFERENCE, labeled, no universal ramp · D-013 environmental
confounders = same forms as attacks, smaller magnitude, no operating point · D-014
dataset schema v1 with machine-readable column classes · D-015 matched counterfactuals
via separate seeded RNG streams · D-016 no new dependencies, aer 0.17.2 resolved ·
D-017 conventional baseline = 5σ thresholds. See decisions.md for context/alternatives.

## 6. Requirements and Constraints

- Master prompt (owner-provided) governs. All commits: author
  `PrathamKapoor <prathamkapoor027@gmail.com>`, no co-author lines, no AI/tool names.
  Never commit paper/, research/, *.tex, or data/ outputs (gitignore data/).
- Phase gates: Phase 2 = quantum digital twin expansion (or per master prompt §63:
  next recommended step below). Do not jump to model training.
- Precursor honesty: all gradual precursors are PROJECT INFERENCE — keep labels in
  docs and code comments.
- Do NOT modify simulator behavior because model results are poor (§59).

## 7. Testing and Verification

- Command: `python -m pytest tests/ -q` → **40 passed** (0 failed, 0 skipped), on
  2026-10-08.
- Dataset generation: `PYTHONPATH=src python -m quantumattack.simulator.generate
  --config configs/simulation/phase1.yaml --out data/phase1` → 65 scenarios exported.
- Precursor analysis: `python scripts/analyze_precursors.py` → docs/precursor-analysis.md.
- Deterministic reproduction verified (test_same_seed_same_output: field-exact equality).

## 8. Known Issues / Risks

- benign OU processes have slow mean reversion (θ=0.05): over 2000-block runs,
  temperature/excess-noise wander up to ±0.4 °C/±0.004 SNU — plausible for lab
  conditions but worth revisiting if benign drift looks too strong for forecasting.
- The qber_proxy is currently constant ~0 (CV-QKD has no QBER; the proxy formula
  degenerates). It is documented as a proxy; a real distortion measure needs Phase 4 work.
- SPYDER-style pitfalls: the ε̂-estimator inversion in cvqkd.parameter_estimate is a
  compact approximation (documented in-module); the Holevo χ uses an approximate
  symplectic form — finite-key corrections are later-phase.
- data/phase1 is generated output: exclude from git (add data/ to .gitignore if not
  already).

## 9. Unfinished Work (explicitly deferred, not silently dropped)

- Derived temporal features are SPECIFIED (docs/feature-spec.md) but only partially
  implemented (the simulator emits two causal first-differences; the feature layer
  src/quantumattack/features.py is NOT yet written — Phase 4 per checklist).
- Conventional-detector baseline: thresholds defined (docs/evaluation-protocol.md §1)
  but no detector code (belongs with model phases).
- DV protocols / P2 attacks: documented, not implemented.
- OOD partitions and split leakage tests: design documented (dataset-spec §5/§6),
  implementation deferred to dataset-generation phase.

## 10. Next Subphase

Phase 2 — per the master prompt's phase sequence: expand the digital twin (protocol
fidelity, more telemetry, DV protocol only if justified) OR proceed to the dataset
generation phase at larger scale. Recommended first actions: (1) commit Phase 1;
(2) write src/quantumattack/features.py implementing docs/feature-spec.md candidates;
(3) conventional threshold detector + logistic-regression baseline to establish the
lead-time comparison harness (docs/evaluation-protocol.md).

## 11. Critical Context

- The central research question: can temporal telemetry patterns give statistically
  significant early warning before conventional indicators cross detection thresholds?
  Experiments must be allowed to answer NO (sudden-onset attacks are honest hard negatives).
- Phase 1 gate answered PARTIALLY: gradual attacks (lo_manipulation, calibration)
  show 5–9 features with strong pre-onset movement (|effect| ≥ 1σ, most ≥ 3σ); sudden
  attacks (intercept_resend, jamming) show ZERO pre-onset movement — correct physics,
  by design. Do not "fix" this (§59).
- Never fabricate: results, datasets, numbers, hardware claims.

## 12. Agent Instructions

- Maintain decisions.md / flow.md / handoff.md / docs/implementation-checklist.md in
  every session; use checklist states with evidence.
- Run the leakage tests before any predictive result (tests/test_labels_metadata.py).
- Keep PREDICTED vs CONFIRMED distinct in every warning path and UI string.
- Dependency rule: verify imports + Python 3.13 compatibility before ANY new install;
  record a D-NNN entry per install.
