# Implementation Checklist

States: `[ ]` not started · `[-]` in progress · `[x]` verified complete · `[!]` blocked.
Rule (master prompt §4): never mark `[x]` without actual verification; record evidence
references (file, command, output) when marking.

## Per-feature verification template (applied when a phase starts a component)

```text
[ ] Requirement defined
[ ] Design defined
[ ] Dependencies verified
[ ] Implementation completed
[ ] Unit tests written
[ ] Integration tests written
[ ] Edge cases tested
[ ] Documentation updated
[ ] Flow documented
[ ] Decision recorded
[ ] UI represented if applicable
[ ] Demo path verified
[ ] Failure behavior verified
[ ] Reproducibility verified
```

## Phase 0 — Repository audit (complete)

- [x] Repository inspected: empty (0 entries incl. hidden), not a Git repo before init — evidence: docs/phase0-audit.md §1
- [x] Dependency audit — evidence: docs/phase0-audit.md §3
- [x] Environment audit (Python 3.13.12; numpy/scipy/pandas/matplotlib/qiskit present; sklearn/torch/networkx/xgboost/fastapi missing) — evidence: docs/phase0-audit.md §3
- [x] Architecture assessment written — docs/phase0-audit.md
- [x] decisions.md created — evidence: this commit
- [x] flow.md created — evidence: this commit
- [x] handoff.md created — evidence: this commit
- [x] docs/research-landscape.md created (snippet-level, UNKNOWN-marked) — evidence: docs/research-landscape.md
- [x] Git initialized, initial commit with mandated author identity — evidence: `git log --format=full`
- [x] Research sources read at full-text level (Phase 1 opener) — evidence: docs/research-landscape.md (Phase 1 update)
- [x] Phase 1 proposal approved by project owner (gate for all implementation work) — evidence: owner-issued Phase 1 master prompt (2026-10-07)

## Phase 4 — Large-scale robustness, statistical validation & graph-model decision (current)

Order follows the Phase 4 execution steps (§50). Evidence added as items complete.

- [x] Phase 3 regression suite passes — evidence: pytest 109 passed (2026-10-09)
- [x] environment revalidated — evidence: Python 3.13.14, numpy 2.4.4, scikit-learn 1.8.0, torch 2.13.0
- [x] Phase 4 dataset protocol documented — evidence: docs/phase4-protocol.md v1 (pre-registered 2026-10-09)
- [x] scenario generation scale determined — evidence: 284 scenarios (234 independent unpaired + 50 counterfactual)
- [x] independent seed pools expanded — evidence: configs/simulation/phase4.yaml (stride-7 disjoint ranges: train 1000..1833, val 5000..5287, test 9000..9287, ood 13000..13203)
- [x] train/validation/test split pre-registered — evidence: docs/phase4-protocol.md §3 (partition fixed by seed pool)
- [x] OOD attack family pre-registered — evidence: docs/phase4-protocol.md §3 (`channel_jamming`, test-only, 0 train/val)
- [x] dataset generated — evidence: data/phase4/ (234 scenarios, 2000 blocks each) + data/phase1 (50 counterfactual)
- [x] manifest validated — evidence: data/phase4/manifest.json + tests/test_phase4_dataset.py
- [x] scenario isolation validated — evidence: tests/test_phase4_dataset.py (14 tests passed)
- [x] pair isolation validated — evidence: tests/test_phase4_dataset.py + SplitConfig counterfactual_to_train=True
- [x] logistic baseline rerun — evidence: artifacts/phase4/eval-logistic/ (primary model)
- [x] conventional baseline rerun — evidence: artifacts/phase4/eval-logistic/metrics.json (conventional_summary)
- [x] GRU baseline rerun where justified — evidence: artifacts/phase4/eval-gru/ (H=10 evaluated, AUROC 0.625 vs 0.792 logistic; complexity gate applied)
- [x] TCN baseline rerun where justified — evidence: Phase 3 / Phase 4 complexity gate applied (§16/§42: no attributable lead-time advantage over logistic)
- [x] multi-horizon evaluation completed — evidence: H=10, 25, 50, 100 in phase4_metrics.json
- [x] multi-seed evaluation completed — evidence: artifacts/phase4/multisplit-summary.json (splits 42, 7, 101, 2024, 31337)
- [x] confidence intervals computed — evidence: artifacts/phase4/eval-logistic/phase4_metrics.json (B=2000 scenario bootstrap)
- [x] attack-specific confidence intervals computed — evidence: phase4_metrics.json (ci_report per attack family)
- [x] bootstrap/scenario-level uncertainty evaluated — evidence: scripts/evaluate_phase4.py (scenario_bootstrap_ci)
- [x] false-warning analysis completed — evidence: phase4_metrics.json (NORMAL FWR=0.231, BENIGN_DRIFT FWR=0.0)
- [x] attributed lead-time analysis completed — evidence: phase4_metrics.json (lo_manipulation: 83.5 blocks, cal_manipulation: 109.0 blocks)
- [x] conventional-vs-forecast comparison completed — evidence: metrics.json (forecast_vs_conventional)
- [x] OOD evaluation completed — evidence: channel_jamming warning rate 36.7% (probe variant), 0% (sudden variant)
- [x] feature ablation completed — evidence: artifacts/phase4/ablation/ablation_summary.json (Groups A, B, C, D)
- [x] robustness analysis completed — evidence: multisplit-summary.json + feature_freeze_analysis.py
- [x] graph hypothesis formally specified — evidence: docs/graph-hypothesis.md
- [x] graph decision gate evaluated — evidence: docs/graph-hypothesis.md (Gate Decision: HOLD)
- [x] GNN implemented ONLY if gate criteria satisfied — evidence: GNN not implemented as gate criteria resulted in HOLD (§42/§43)
- [x] GNN evaluated using identical harness if implemented — evidence: N/A (Gate HOLD)
- [x] graph ablation completed if applicable — evidence: N/A (Gate HOLD)
- [x] leakage audit completed — evidence: test_sequence_invariance_to_future + test_features.py + split isolation tests pass
- [x] reproducibility verified — evidence: deterministic seed pools, configs/simulation/phase4.yaml
- [x] documentation updated — evidence: docs/phase4-protocol.md, docs/graph-hypothesis.md, docs/feature-freeze-v1.md, decisions.md, flow.md, handoff.md
- [x] Phase 4 report produced — evidence: docs/phase4-final-report.md

## Phase 3 — Unpaired forecasting, attributed early warning & temporal model benchmark (complete; commit c9cb1a8)

- [x] Phase 2 regression suite passes — evidence: pytest output
- [x] Unpaired dataset design documented — evidence: docs/dataset-spec.md + config
- [x] Independent benign scenarios generated — evidence: dataset manifest
- [x] Independent attack scenarios generated — evidence: dataset manifest
- [x] Pair structure retained for diagnostic experiments (COUNTERFACTUAL category) — evidence: config + docs
- [x] Train/validation/test scenario isolation verified — evidence: tests
- [x] Attack-family OOD split implemented (pre-registered) — evidence: config + tests
- [x] Larger multi-seed dataset generated — evidence: manifest scenario counts
- [x] Logistic baseline rerun — evidence: metrics output
- [x] Conventional baseline rerun (same calibration policy) — evidence: metrics output
- [x] Attribution policy verified (Metric A independent / Metric B counterfactual) — evidence: metrics
- [x] False-warning rate measured — evidence: metrics
- [x] Lead-time distribution measured (percentiles, nulls) — evidence: metrics
- [x] Attack-specific lead time measured — evidence: per-attack results
- [x] Sudden-attack behavior reported separately — evidence: results
- [x] GRU/LSTM implemented — evidence: src/quantumattack/models/
- [x] TCN implemented (causal convolutions) — evidence: src/quantumattack/models/
- [x] TCN causality test added — evidence: tests
- [x] Identical evaluation harness used — evidence: harness runs
- [x] Model parameters/configuration recorded — evidence: experiment manifests
- [x] Temporal leakage tests extended (sequence invariance) — evidence: tests
- [x] Sequence construction tested (ordering, boundaries) — evidence: tests
- [x] Ablations completed (feature/model/attack) — evidence: ablation outputs
- [x] Multi-seed evaluation completed — evidence: outputs
- [x] OOD experiment completed — evidence: outputs
- [x] Statistical uncertainty reported — evidence: report
- [x] Results reproduced — evidence: rerun equality
- [x] decisions.md updated — evidence: decisions.md
- [x] flow.md updated — evidence: flow.md
- [x] handoff.md updated — evidence: handoff.md
- [x] Phase 3 report generated — evidence: docs/phase3-final-report.md

## Phase 2 — Causal feature layer, forecasting baselines & lead-time evaluation (complete; commits 2f5bf74, 8b30de0)

Order follows the Phase 2 execution steps (§61). Evidence added as items complete.

### Foundation & feature layer
- [x] Phase 1 regression tests pass — evidence: pytest 40 passed (2026-10-08, commit 16f8406)
- [x] Phase 1 dataset regeneration verified — evidence: data/phase1 manifest (65 scenarios, schema 1)
- [x] Environment revalidated (scikit-learn 1.8.0 re-probed before use) — evidence: probe output
- [x] Feature implementation mapped to feature spec — evidence: docs/feature-spec.md + features.py
- [x] Causal feature layer implemented (154 features, schema v2) — evidence: src/quantumattack/features.py
- [x] Feature unit tests added (tests/test_features.py, 23 tests) — evidence: tests/test_features.py
- [x] Feature causality tests added (historical invariance, per feature class) — evidence: tests/test_features.py
- [x] Feature schema versioned (v2; feature_schema.json) — evidence: FEATURE_SCHEMA_VERSION + docs

### Baselines
- [x] Threshold baseline implemented (baselines/conventional.py) — evidence: src/quantumattack/baselines/
- [x] Threshold calibration protocol defined (empirical quantile on benign train only, D-020) — evidence: docs/evaluation-protocol.md
- [x] Conventional warning policy defined (k=3 + cooldown, configurable, D-020) — evidence: baselines + docs
- [x] Logistic-regression forecasting baseline implemented (baselines/logistic.py, D-022) — evidence: src/quantumattack/baselines/
- [x] Future-horizon labels verified (y_H(t)=0 for t≥onset, tested) — evidence: tests
- [x] Train/validation/test split implemented (scenario-level, disjoint, D-021) — evidence: baselines/splits + tests
- [x] Scenario-level isolation verified (disjointness test) — evidence: tests
- [x] Matched-pair isolation verified (pair-isolation test + violation detection) — evidence: tests
- [x] Baseline evaluation harness implemented (evaluation/harness.py, D-024) — evidence: src/quantumattack/evaluation/
- [x] AUROC calculated (0.839-0.944 H=10; 0.638-0.804 H=100 across split seeds) — evidence: metrics output
- [x] AUPRC calculated (0.013-0.228) — evidence: metrics output
- [x] Calibration measured (Brier 0.010-0.213; ECE + reliability diagrams) — evidence: metrics output
- [x] False early-warning rate measured (scenario-level, 0.64-1.0) — evidence: metrics output
- [x] Lead time measured (raw + pair-gated attributed; attribution = 0% on paired data) — evidence: metrics output
- [x] Conventional-vs-forecast comparison measured (+77 blocks gain calibration/LO at H=100) — evidence: metrics output
- [x] Gradual attack performance measured (per-attack results in report) — evidence: per-attack results
- [x] Sudden attack performance measured (raw warnings unattributed = benign-drift responses) — evidence: per-attack results
- [x] Benign-drift performance measured (P(warning|drift) vs P(warning|normal), bimodal P) — evidence: results
- [x] Multiple seeds evaluated (split seeds 0-3; artifacts/phase2/multiseed-summary.json) — evidence: results
- [x] Ablation analysis performed (A/B/C/D; calibration improves, attribution unchanged) — evidence: ablation output
- [x] Results reproducible (identical re-run -> metrics.json identical) — evidence: repeat run equality
- [x] decisions.md updated (D-018..D-025) — evidence: decisions.md
- [x] flow.md updated (Phase 2 evaluation flow, actual names) — evidence: flow.md
- [x] handoff.md updated (Phase 3-ready, WEAK SIGNAL state) — evidence: handoff.md
- [x] Phase 2 report produced (docs/phase2-final-report.md, WEAK SIGNAL) — evidence: docs/phase2-final-report.md

## Phase 1 — Research, threat model, simulation & precursor design (complete; committed 16f8406)

Order follows the master prompt's execution steps (§63). Evidence references added as items complete.

### Foundation
- [x] Repository/docs re-read (decisions.md, flow.md, handoff.md, docs/* complete) — evidence: session log
- [x] Environment re-validation (versions re-probed; stale Phase 0 records corrected) — evidence: probe output (§ Phase 1 report)
- [x] qiskit-aer exact version resolved — evidence: `importlib.metadata` probe
- [x] Research landscape strengthened (full-text sources; VERIFIED/SECONDARY/INFERENCE/UNKNOWN levels) — evidence: docs/research-landscape.md (27 sources, most VERIFIED 2026-10-08)
- [x] System boundary defined (protected QKD system, components, protocol scope) — evidence: docs/threat-model.md
- [x] Threat model defined — evidence: docs/threat-model.md (§1–§7)
- [x] Attack taxonomy defined (per-attack: applicability, subsystem, mechanism, telemetry, precursor, onset, priority) — evidence: docs/attack-taxonomy.md
- [x] Precursor taxonomy defined (per prioritized attack: A/B/C/D class, math form, distributions, confounders, confidence) — evidence: docs/precursor-taxonomy.md
- [x] Environmental confounders defined (prioritized subset with drift forms) — evidence: docs/precursor-taxonomy.md §Environmental confounders

### Temporal semantics & data design
- [x] Telemetry schema defined (per-feature name/type/units/cadence/causality) — evidence: docs/telemetry-spec.md
- [x] Temporal unit defined (timestep → sampling → window → sequence → horizon chain, with units) — evidence: docs/time-semantics.md
- [x] Attack onset semantics defined (per attack; NOT "first abnormal telemetry") — evidence: docs/attack-taxonomy.md + docs/time-semantics.md §3
- [x] Prediction horizon semantics defined (H1..H4 in windows AND seconds) — evidence: docs/time-semantics.md §7
- [x] Labeling protocol defined (NORMAL/BENIGN_DRIFT/PRECURSOR/ATTACK + y_H binary targets) — evidence: docs/dataset-spec.md + docs/time-semantics.md §5
- [x] Leakage risks documented (causal rolling stats; feature-at-t ≤ t rule) — evidence: docs/dataset-spec.md §4 + docs/feature-spec.md
- [x] Matched-counterfactual protocol defined (pair IDs, shared seeds/environment) — evidence: docs/dataset-spec.md §3 + D-015

### Architecture & design docs
- [x] Simulation architecture designed (modular package layout with rationale) — evidence: docs/architecture-v1.md Part A
- [x] Graph representation designed (nodes/edges/features/temporal update; design only) — evidence: docs/architecture-v1.md Part B
- [x] Conventional detection baseline + lead-time definition documented — evidence: docs/evaluation-protocol.md §1–§3

### Implementation
- [x] Initial simulator implemented (config-first, modular, seeded) — evidence: src/quantumattack/ (15 modules)
- [x] Normal-operation simulation validated (distributions, invariants, bounds) — evidence: tests/test_reproducibility.py + smoke output in session log
- [x] Environmental-drift simulation validated (drift without attack) — evidence: tests + benign-drift smoke output (transmittance std 0.0038 across run)
- [x] Initial attack scenarios implemented (small diverse prioritized subset) — evidence: src/quantumattack/simulator/attacks/ + tests/test_attack_semantics.py
- [x] Precursor scenarios implemented ONLY where physically defensible — evidence: docs/precursor-taxonomy.md (PROJECT INFERENCE labels) + tests/test_precursor_semantics.py
- [x] Sudden-onset scenarios included (no injected pre-warning) — evidence: tests/test_precursor_semantics.py (class C tests)
- [x] Deterministic seeding verified (same seed → same telemetry) — evidence: test_same_seed_same_output (field-exact equality)
- [x] Telemetry export verified (CLI, schema versioned, traceable) — evidence: data/phase1 manifest (65 scenarios, schema 1)

### Validation & analysis
- [x] Simulator tests added (config accept/reject, reproducibility, invariants, attack/precursor semantics, labels, metadata isolation, counterfactual) — evidence: 40 passed, 0 failed (pytest output)
- [x] Statistical sanity checks run (multi-seed; pre-onset movement analysis) — evidence: docs/precursor-analysis.md (5–10 seeds per attack)
- [x] Precursor usefulness analysis performed (Cat 1–4 classification per feature) — evidence: docs/precursor-analysis.md §Summary
- [x] Precursor behavior compared against matched benign trajectories — evidence: scripts/analyze_precursors.py (matched-pair effect sizes)

### Documentation & closure
- [x] docs updated (all new docs + existing docs kept consistent) — evidence: git diff
- [x] decisions.md updated (D-0NN entries for architectural/data decisions) — evidence: decisions.md D-008..D-017
- [x] flow.md updated (implemented names, call flow, call tree) — evidence: flow.md §1–§2
- [x] handoff.md updated (Phase 2-ready state) — evidence: handoff.md
- [x] Phase 1 completion report produced (status, gate result, evidence) — evidence: final report in session log

## Phase 2 — Quantum digital twin (CV-QKD)

- [ ] Per-feature template above applied to the twin
- [ ] Deterministic, seeded simulation (config-driven)
- [ ] Channel model: transmittance, excess noise, shot noise
- [ ] Source/LO/quadrature/detector/timing telemetry emission
- [ ] Attack injection framework with documented per-attack physics
- [ ] Matched counterfactual run support (same seed/environment ± attack)
- [ ] Unit tests: physics invariants, attack determinism, seed reproducibility
- [ ] decisions.md / flow.md updated; PHASE CHECKLIST completed

## Phase 3 — Telemetry pipeline

- [ ] Time-indexed storage schema; write/read path tested
- [ ] Failure behavior verified (corrupt/missing data handling)
- [ ] Throughput measured (baseline numbers recorded before optimization)

## Phase 4 — Feature engine

- [ ] Physical / temporal / security features with §12 doc block each
- [ ] Temporal features computed strictly from past+current (leakage-safe by construction)
- [ ] Unit tests per feature calculation (known-input → expected-output)
- [ ] Redundancy/correlation analysis tooling

## Phase 5 — Dataset generation

- [ ] Scenario generator: normal, environmental drift, degradation, attacks (prioritized subset from Phase 1 taxonomy)
- [ ] Precursor scenarios where physically justified; sudden-onset attacks included to prevent "gradual buildup ⇒ attack" shortcut
- [ ] Per-timestep labels: current-state AND future-horizon labels
- [ ] Leakage test implemented and passing (master prompt §32; regression test retained)
- [ ] Dataset version recorded; generation reproducible from one command

## Phase 6 — Classical baselines (installs scikit-learn, xgboost after §45 checks)

- [ ] Threshold detector; logistic regression; random forest; xgboost
- [ ] Open-set candidates: one-class SVM, isolation forest (unknown-attack detection §18)
- [ ] Chronological/scenario splits implemented; split documentation

## Phase 7 — Temporal models (installs torch after §45 checks)

- [ ] GRU/LSTM; TCN; lightweight temporal attention
- [ ] Next-state prediction head + residual tracking (§14)
- [ ] Multi-horizon prediction heads; calibration measured

## Phase 8 — Graph models

- [ ] Physics-informed graph construction (nodes = components/measurements; edges = dependencies/hypotheses, labeled as hypotheses)
- [ ] GNN and temporal GNN; ablation vs non-graph models

## Phase 9 — Open-set / unknown attack detection

- [ ] Benchmark candidates (§18) on unseen-attack scenarios
- [ ] KNOWN ATTACK / UNKNOWN ANOMALY / BENIGN / ENVIRONMENTAL DRIFT output taxonomy

## Phase 10 — Quantum ML (only after classical baselines)

- [ ] QSVM / quantum kernel / VQC on compact representation
- [ ] Comparison vs classical with full cost reporting (accuracy, latency, qubits, depth, shots, §17)
- [ ] No quantum-advantage claims unless demonstrated

## Phase 11 — Early-warning fusion

- [ ] Combine next-state prediction + trajectory anomaly + classification + OOD into P(attack within H)
- [ ] No-future-information test at fusion level (§19)

## Phase 12 — Explainability

- [ ] Per-warning WHAT/WHY/HOW/WHEN report; PREDICTED vs CONFIRMED distinction (§24)

## Phase 13 — Dashboard

- [ ] Live telemetry charts; attack timeline; investigation view; what-if simulator (§25)
- [ ] SIMULATED QUANTUM ENVIRONMENT labeling (§26); no faked live results (§49)

## Phase 14 — End-to-end demo

- [ ] Single-command reproducible demo (§27); lead-time comparison vs baseline (§48)

## Phase 15 — Benchmark/research evaluation

- [ ] Feature ablation (§36) and model ablation (§37) with recorded decisions
- [ ] Honest limitation write-up (§33)

## Phase 16 — Hardening

- [ ] Error handling per §44; performance measured then optimized (§46)

## Phase 17 — Final hackathon polish

- [ ] 30-second comprehensibility check (§47); repeatable demo verified

## Master acceptance criteria (master prompt §50 — all must be [x] before completion)

- [ ] Quantum system simulation works
- [ ] Attack injection works
- [ ] Normal conditions work
- [ ] Environmental drift works
- [ ] Temporal telemetry works
- [ ] Precursor scenarios exist
- [ ] Future prediction labels are correct
- [ ] No temporal leakage exists
- [ ] Baseline models work
- [ ] Temporal model works
- [ ] Graph model works
- [ ] Unknown attack detection works
- [ ] Early-warning probability works
- [ ] Lead time is measured
- [ ] Attack confirmation works
- [ ] Explainability works
- [ ] Dashboard works
- [ ] End-to-end demo works
- [ ] Tests pass
- [ ] Documentation is complete
- [ ] Reproducibility is documented
- [ ] Research limitations are documented
- [ ] No fabricated claims exist
- [ ] Hackathon demo is repeatable
