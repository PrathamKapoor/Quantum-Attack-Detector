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

## Phase 1 — Research, threat model, simulation & precursor design (current)

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
