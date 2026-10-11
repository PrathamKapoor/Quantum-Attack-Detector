# handoff.md

Exact current implementation state for continuation. Updated 2026-10-12
(workstream: causal warning repair + conventional detector implementation +
fair benchmark). All statements are traceable to source, tests, or artifacts;
all negative results are preserved.

---

## 1. Current Workstream & Verified Verdict

- **Workstream:** Causal Warning Correction, Event-Accounting Reconciliation and
  Conventional Detector Implementation (D-049 .. D-053).
- **Status:** COMPLETE for the implementation and the measured comparison; the
  scientific conclusion is NEGATIVE for the forecasting system and is reported
  as such.
- **Scientific verdict (downgraded):** the operational-forecasting claim is
  **NOT supported** once look-ahead selection is removed.
  - Frozen forecaster (P>=0.5, K=3) operational behaviour on 160 scenarios:
    benign false-alarm rate **51.7% [39.3%, 63.8%]**; horizon-valid (H=100)
    first alarms **1.0% (1/100)**; median first-emission lead 916 blocks
    (9.16 s) -- i.e. far outside the declared horizon, so most "pre-onset
    alerts" are extended alerts, not forecasts.
  - G1 alone: benign FPR **63.3%**, horizon-valid **0/30**, median lead 908
    blocks.
  - At the highest tested threshold (P>=0.95): G1 FPR 20% with horizon-valid
    30% and sensitivity 66.7% -- no defensible operating point reaches the
    conventional detector's false-alert budget with useful horizon-validity.
  - **Scientific gate: `WEAK SIGNAL`** for the operational-forecasting claim
    (real discrimination AUROC 0.897 remains; time-only AUROC 0.518 rules out
    schedule leakage; the signal simply does not convert into within-horizon
    operational warnings at any tested, defensible budget).
- **Conventional detector:** a real, non-degenerate causal CUSUM baseline now
  exists (D-052): benign FPR **5.0% [1.7%, 13.7%]** across 60 benign scenarios,
  sensitivity 100%, pre-onset detection 51%, median lead 7.5 blocks (0.075 s);
  G1 benign FPR 0% [0%, 11.4%]. It is an early-malicious-activity / active-attack
  detector, not a predictor.
- **Comparison verdict (D-053):** no matched false-alert budget is reachable at
  which the forecaster outperforms the detector. The detector dominates on this
  evaluation population. Every prior "forecast gain vs conventional" number is
  invalidated.
- **Simulator evidence status:** `SYNTHETIC ONLY` (unchanged; no hardware claim).
- **Graph-model gate:** `HOLD` (unchanged; no evidence for cross-node structure).

---

## 2. Initial State Actually Found (repository reconciliation)

The previous session left FIVE uncommitted modifications; HEAD (`2d9caff`) did
NOT contain them, which explains the earlier 194-vs-192 test-count confusion
(the committed archive lacked `tests/test_statistics.py`'s added tests and the
`logistic.py` solver pin):

```
 M decisions.md            (D-045..D-048 text, uncommitted)
 M handoff.md              (previous session's update, uncommitted)
 M scripts/evaluate_reliability.py
 M src/quantumattack/baselines/logistic.py   (liblinear solver pin, D-048)
 M tests/test_statistics.py
```

All five were inspected, preserved, and committed together with this
workstream's changes. The uncommitted diff was saved before editing to
`artifacts/verification/` (evidence bundle).

---

## 3. Defects Fixed (verified in source before editing)

| # | Verified defect | Correction | Decision |
|---|---|---|---|
| 1 | `warnings.warning_blocks_for_scenario` returned `t_idx[i-K+1]` (run start) as the warning time although persistence is satisfied at `i` | canonical `WarningEvent` (`excursion_start_block` / `persistence_satisfied_block` / `emission_block`); `warning_events_for_scenario` emits at `t_idx[i] + processing_delay`; `warning_blocks_for_scenario` returns emission blocks | D-049 |
| 2 | `sustained_until_onset` used future onset / scenario end to decide which emitted alerts survived | moved to `retrospective_sustained_retention` (classification only; never deletes); operational ledger keeps every emission | D-049 |
| 3 | `ACTIVE_ATTACK_CONFIRMED` entered from sustained forecast probability alone | requires an independent `confirmation_evidence` mask sustained for `confirmation_evidence_persistence` blocks; probability-only yields `PRE_ATTACK_WARNING` ("unconfirmed"); evidence-driven confirmation works without any prior forecast (sudden attacks) | D-050 |
| 4 | `false_alarm_episodes_per_1000_simulated_seconds` computed from affected-SCENARIO counts | `alert_episodes_from_trace` + `summarize_alert_burden` (episode-based) | D-051 |
| 5 | `warning_load_fraction` computed from first-to-last firing span | per-block alert-state occupancy from the state timeline | D-051 |

Confirmed defects that were NOT present (no change made): the `liblinear` pin was
a real improvement already present uncommitted (D-048); the horizon-classification
boundaries were already exclusive (`0 < lead <= H`); the pqt feature pipeline was
already temporally causal (verified by existing invariance tests).

---

## 4. Measured Results (v2, all artifact-backed)

### 4.1 Operational forecasting (v2, look-ahead removed)

`artifacts/reliability/evaluation/reliability_report_v2.json`
(v1 `reliability_report.json` preserved unchanged).

| Metric | v1 (retention view, future-informed) | v2 (operational, causal) |
|---|---|---|
| G1 `lo_manipulation` horizon-valid H=100 | 50.0% | **0.0%** (median first-alarm lead 874 blk) |
| G1 `calibration_manipulation` horizon-valid | 50.0% | **0.0%** |
| G1 `intercept_resend` horizon-valid | 0.0% | 0.0% (correct physics preserved) |
| G4 `channel_jamming` horizon-valid | 16.7% | **0.0%** (96.7% extended alerts) |
| G1 NORMAL false-alarm rate | 35.0% | **80.0% [58.4%, 91.9%]** |
| G1 NORMAL episodes / occupancy | span-based | **109 episodes, 36.2% occupancy**, 272.5/1000 s |
| G3 BENIGN_DRIFT false-alarm rate | 0.0% | **100% (10/10)** -- transient alarms do fire operationally |
| `ACTIVE_ATTACK_CONFIRMED` counts | probability-derived (invalid) | **0** (no independent evidence supplied) |
| Missing-telemetry behaviour | n/a | 13,200 DEGRADED + 11,460 ABSTAINING blocks; never silent NORMAL |

Calibration (validation-fit, unchanged): uncalibrated ECE 0.190 / Brier 0.118;
Platt ECE 0.010 / Brier 0.022; isotonic ECE 0.012 / Brier 0.021. NOISE
(train-sigma units): 0.897 / 0.864 / 0.819 / 0.747 / 0.655 / 0.603 / 0.560 for
0 / 0.05 / 0.1 / 0.2 / 0.5 / 1.0 / 2.0.

### 4.2 Conventional CUSUM detector (D-052)

Calibrated on Phase-4 train reference + Phase-4 validation benign budget:
**k=2.0, h=200.0, achieved validation FPR 5.3% (budget <= 10%)**.

| Partition | benign FPR | attack sensitivity | pre-onset | median lead |
|---|---|---|---|---|
| G1 | **0/30 = 0.0% [0%, 11.4%]** | 30/30 | 16/30 | +15.0 blk (0.15 s) |
| G2 | (no benign) | 40/40 | 47.5% | +0.5 blk |
| G3 (extreme stress benign) | **3/30 = 10.0%** | (no attacks) | -- | -- |
| G4 | (no benign) | 30/30 | 53.3% | +47.5 blk |
| All | **5.0% [1.7%, 13.7%]** (60 benign) | 100/100 | 51.0% | +7.5 blk |

Outcome split (all attacks): 51 pre-onset / 2 at-onset / 47 post-onset. The
detector is an early-malicious-activity and active-attack detector.

### 4.3 Fair comparison (D-053)

`artifacts/reliability/evaluation/conventional_comparison.json`, same
populations/onsets/time base, emission timestamps for both systems.

| System | benign FPR | horizon-valid (H=100) | median lead |
|---|---|---|---|
| CUSUM detector | **5.0% [1.7%, 13.7%]** | n/a (not a forecaster) | 7.5 blk |
| Frozen forecaster P>=0.5 | **51.7% [39.3%, 63.8%]** | **1.0%** | 916 blk (>H) |
| Forecaster P>=0.90 (sweep) | 36.7% (G1) | 33.3% (G1) | 101 blk |
| Forecaster P>=0.95 (sweep) | 20.0% (G1) | 30.0% (G1) | 103.5 blk |

No threshold reaches the detector's budget; superiority is NOT established for
the forecaster. Higher forecaster thresholds trade sensitivity (100% -> 67%) for
modest horizon-validity while remaining far above the detector's FPR.

### 4.4 Scenario reconciliation (D-051 context; `normal_scenario_audit.json`)

The 7-vs-3 NORMAL contradiction is fully explained by measurement:
- 7 = scenarios warned under the v1 retrospective-retention policy;
- 3 = of those, scenarios whose LONGEST above-threshold run geometrically reaches
  the scenario end (s20042: 1033 blk; s20063: 492; s20070: 467);
- 5 = of the 7, scenarios where an OPERATIONALLY EMITTED event also satisfies the
  v1 sustained test (s20007/s20021 differ because recent transient emissions
  armed the cooldown window that suppressed an event inside their 5-8 block
  final segments);
- 16/20 = the true operational false-alarm burden (v2), larger than 7 because the
  v1 policy suppressed all transient emissions by design.
The previous handoff prose ("0 of 53 non-end-reaching fired") was WRONG on two
counts and is superseded by the machine-generated audit table.

---

## 5. Files Changed

New source/tests/scripts:
- `tests/test_causal_warning_semantics.py` (33 independent acceptance tests: A-F + adversarial)
- `tests/test_conventional_detector.py` (17 tests incl. 2 real end-to-end scenarios)
- `scripts/evaluate_conventional_detector.py` (fair benchmark)
- `scripts/audit_normal_scenarios.py` (per-scenario reconciliation)
- `scripts/package_verification_evidence.py` (evidence bundle)

Modified:
- `src/quantumattack/baselines/warnings.py` (WarningEvent; causal emission; retrospective filter)
- `src/quantumattack/operational_states.py` (confirmation evidence; episodes; burden)
- `src/quantumattack/baselines/conventional.py` (CUSUM detector + calibration)
- `src/quantumattack/baselines/logistic.py` (liblinear pin, inherited D-048)
- `scripts/evaluate_reliability.py` (v2 outputs + ledgers; episode/occupancy accounting)
- `tests/test_baselines.py`, `tests/test_metric_integrity.py`, `tests/test_operational_states.py`,
  `tests/test_statistics.py` (corrected expectations for the repair; added reproducibility tests)
- `decisions.md` (D-045..D-053), `flow.md` (sections 0c, 0d, 0e), `docs/reliability-research-report.md` (section 15)

## 6. Verification

- Full suite: `python -m pytest tests/ -q -ra` -> **245 passed, 0 failed** (~100 s).
- Acceptance tests: `tests/test_causal_warning_semantics.py` -> 33/33.
- Detector tests: `tests/test_conventional_detector.py` -> 17/17.
- v2 evaluation: `python scripts/evaluate_reliability.py` -> exit 0; writes
  `reliability_report_v2.json` (440 KB), `alert_event_ledger.json` (604 episodes),
  `scenario_ledger.json` (160 scenarios); v1 artifact NOT overwritten.
- Benchmark: `python scripts/evaluate_conventional_detector.py` -> exit 0; ~10 min.
- Scenario audit: `python scripts/audit_normal_scenarios.py` -> exit 0.
- Evidence bundle: `python scripts/package_verification_evidence.py --with-tests`.

## 7. Known Issues / Risks

1. The frozen forecaster operating point (P>=0.5, K=3) is not operationally
   viable (52-80% benign FPR). Its horizon-valid rate is 0-1% on unseen data.
2. The uncalibrated probabilities (ECE 0.19) make the threshold semantically
   meaningless; Platt calibration exists but was NOT adopted into the inference
   path (out of scope for this repair; D-044).
3. The CUSUM detector requires a 200-block warmup baseline per scenario; an
   attack active during warmup contaminates the baseline (documented, tested).
4. G3 extreme environmental stress gives the detector 10% benign FPR.
5. The comparison uses the exposed G1-G4 partitions; no untouched confirmatory
   evaluation was performed (would need new scenario generation, ~hours).
6. Multi-horizon probabilities remain incoherent (~32-38% of adjacent pairs).

## 8. Unfinished Work / Next Priority

1. Operating-point re-selection WITH Platt calibration adopted (the current
   threshold is meaningless while probabilities remain uncalibrated).
2. An untouched confirmatory evaluation partition (pre-registered) before any
   new generalisation claim.
3. Slow-ramp multi-scale features (D-046) — only if the operating point issue
   is resolved first; the current bottleneck is the operating point, not the
   feature set.
4. NOT recommended: larger models, GNN, denoising — none addresses the measured
   bottlenecks (operating point, calibration, false-alarm budget).

## 9. Critical Context / Instructions

- Author identity for commits: `PrathamKapoor <prathamkapoor027@gmail.com>`.
- No remote exists; do not push. artifacts/ is git-ignored (regenerable).
- v1 evidence (`reliability_report.json`, phase2-5 artifacts) must never be
  overwritten; corrected numbers go to `*_v2.json` / new ledger files.
- Any claim of forecast superiority requires a matched false-alert budget; the
  current measured result is the opposite (detector dominates at reachable
  budgets). Do not revive the old "forecast gain" language without new evidence.
- Reproduce everything with:
  `python -m pytest tests/ -q`;
  `python scripts/evaluate_reliability.py`;
  `python scripts/evaluate_conventional_detector.py`;
  `python scripts/audit_normal_scenarios.py`.