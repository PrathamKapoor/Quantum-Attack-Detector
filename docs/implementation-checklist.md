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

## Phase 0 — Repository audit (current)

- [x] Repository inspected: empty (0 entries incl. hidden), not a Git repo before init — evidence: docs/phase0-audit.md §1
- [x] Dependency audit — evidence: docs/phase0-audit.md §3
- [x] Environment audit (Python 3.13.12; numpy/scipy/pandas/matplotlib/qiskit present; sklearn/torch/networkx/xgboost/fastapi missing) — evidence: docs/phase0-audit.md §3
- [x] Architecture assessment written — docs/phase0-audit.md
- [x] decisions.md created — evidence: this commit
- [x] flow.md created — evidence: this commit
- [x] handoff.md created — evidence: this commit
- [x] docs/research-landscape.md created (snippet-level, UNKNOWN-marked) — evidence: docs/research-landscape.md
- [x] Git initialized, initial commit with mandated author identity — evidence: `git log --format=full`
- [ ] Research sources read at full-text level (Phase 1 opener)
- [ ] Phase 1 proposal approved by project owner (gate for all implementation work)

## Phase 1 — Research specification

- [ ] Research landscape completed at full-text level (fill UNKNOWN columns)
- [ ] Attack taxonomy (CV-QKD-first) with per-attack precursor profile: gradual / sudden / adaptive / stealth, and physical justification
- [ ] Feature taxonomy with the §12 documentation block per feature
- [ ] Evaluation methodology: chronological/scenario splits, matched counterfactual runs, metrics (lead time, precision@horizon, AUROC/AUPRC, calibration, false-warning rate, secret-key impact)
- [ ] Horizon selection method defined (H1..H4 configurable; values derived from simulation timestep + attack durations)
- [ ] Architecture proposal (benchmark ladder from §16; QML only after classical baselines)
- [ ] PHASE CHECKLIST (master prompt §39) completed

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
