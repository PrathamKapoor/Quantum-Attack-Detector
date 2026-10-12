# handoff.md

Exact current implementation state for continuation. Updated 2026-10-12
(workstream: public release preparation on top of independent scientific
validation, adversarial reproducibility audit and the untouched confirmatory
evaluation). All statements traceable to source, tests, or hash-recorded
artifacts; negative results preserved.

---

## 0. Publication Status (release preparation, D-055/D-056)

- **Published:** `https://github.com/PrathamKapoor/Quantum-Attack-Detector`
  (branch `main`, full history preserved, non-force push).
- **Credential audit:** 120 tracked files + 187 unique blobs across 21 commits
  scanned (GitHub tokens, AWS key IDs, PEM private-key headers, bearer tokens,
  password/secret assignments, Slack webhooks): **0 hits**, working tree and
  reachable history.
- **Local-only by design:** `data/` and `artifacts/` (datasets, features,
  evaluation JSON, evidence bundles, confirmatory runs) remain git-ignored and
  are regenerated from `configs/simulation/*.yaml` (commands in README
  "Reproducibility"). Largest tracked file is 94 KB.
- **Fresh-clone verified:** clone into an empty directory → venv → `pip install -e .`
  + `requirements-dev.txt` → documented quick-start commands, all without
  access to the original working tree.
- **Full local suite:** `255 passed in 117.09 s`. Dataset-independent CI subset
  passes from a clean clone.
- **OPEN — license:** no license file exists and none was invented. `pyproject.toml`
  declares `license = { text = "Proprietary" }`; the README states that the code is
  publicly viewable but not licensed, and reuse/redistribution requires the author's
  permission. Selecting an OSI license remains an author decision (D-056).

---

## 1. Current Workstream & Verified Verdict

- **Workstream:** Independent validation of the causal-warning repair, adversarial
  audit of the conventional detector, and the first genuinely untouched
  confirmatory evaluation (D-054).
- **Scientific gate: `WEAK SIGNAL`** (unchanged by the untouched experiment —
  the experiment CONFIRMED the downgrade rather than reversing it).
  - On 148 untouched synthetic scenarios (seeds 41000–42999, verified disjoint
    from all 439 historical seeds): frozen forecaster horizon-valid H=100 =
    **0/88 (0.000)** on every attack group; benign FWR 51.7% [39.3%, 63.8%];
    median first-emission lead 887 blocks (8.87 s), far outside the horizon.
  - Conventional CUSUM detector: benign FPR **6.7% [2.6%, 15.9%]** (within the
    frozen 10% budget; C1_NORMAL 3.3%, C3 extreme stress 10.0%), sensitivity
    100% (88/88), pre-onset 55.7% (49/88), median pre-onset lead 96 blocks
    (0.96 s).
  - **Lifecycle finding: 0 detector alerts preceded `precursor_start`** — every
    pre-onset detection occurred during modeled attacker preparation. The system
    performs early malicious-activity detection, NOT prediction before hostile
    action. `intercept_resend`: 0% pre-onset (correct physics preserved).
  - **Confirmation honesty:** `ACTIVE_ATTACK_CONFIRMED` now has a REAL production
    evidence source (the calibrated detector). On untouched data: 88/88 attacks
    confirmed, **4/60 benign confirmed (6.7%)** — the confirmation state
    inherits the detector's false-alert rate by construction.
  - Negative control on untouched data: time-only AUROC **0.525** vs model
    **0.880** — onsets are not trivially scheduled; discrimination is
    telemetry-driven.
- **Simulator evidence status:** `SYNTHETIC ONLY` (unchanged).
- **Graph-model gate:** `HOLD` (unchanged).

---

## 2. What This Workstream Added (all verified)

1. **Confirmation-evidence production path** (`conventional.confirmation_evidence_from_cusum`):
   closes the disclosed integration gap — the state machine's evidence mask now
   comes from the calibrated detector on causal telemetry, not a test parameter.
   10 regression tests (`tests/test_confirmation_evidence.py`), including a
   real-simulator check that evidence never precedes `precursor_start`.
2. **Frozen confirmatory protocol** (`docs/confirmatory-evaluation-protocol.md`)
   committed at `e6bfb22` BEFORE generation; seed block widened 41000–41299 →
   41000–42999 in a documented pre-generation amendment (43 seeds were
   arithmetically insufficient for 148 scenarios; no outcome was viewed before
   or during the amendment).
3. **Confirmatory execution** (`scripts/evaluate_confirmatory.py`,
   `scripts/analyze_confirmatory.py`): frozen-config verification, seed-isolation
   verification, immutable hash-recorded outputs
   (`artifacts/confirmatory/20261012T045123Z/`).
4. **Adversarial controls (measured):**
   - detector statistics bit-identical under label stripping/permutation;
   - no cross-scenario state contamination;
   - **benign-envelope overlap:** h=200 sits at the benign max-S p95 (189.7);
     45/100 attacks show no pre-onset statistic above the benign p95;
   - **warmup contamination quantified:** weak attacks (8–10σ) completely masked
     under contamination (0 vs 18–22 warnings); strongest family (~832σ) still
     detected. Invisible in G1–G4 (no onset < 200) until probed.

## 3. Verification Commands (all executed, exit 0)

```
python -m pytest tests/ -q -ra            # 255 passed (117.09 s, re-run 2026-10-12 at b5a2293)
python scripts/evaluate_confirmatory.py   # 148 scenarios, immutable outputs
python scripts/analyze_confirmatory.py    # regrouped metrics + negative controls
python -m pytest tests/test_confirmation_evidence.py -q   # 10 passed
```

Artifacts: `artifacts/confirmatory/20261012T045123Z/{confirmatory_report.json,
confirmatory_analysis.json, artifact-hashes.json, confirmatory.yaml,
manifest_generation.json, data/, features/}`.

## 4. Known Issues / Risks (cumulative, honest)

1. Forecaster operating point not viable (0% horizon-valid on untouched data;
   52–60% benign FWR); uncalibrated probabilities (ECE 0.19) make the threshold
   meaningless; Platt calibration evaluated but NOT adopted.
2. Detector pre-onset detection covers only the ramp subset (benign-envelope
   overlap); median pre-onset lead 0.96 s.
3. Warmup contamination masks weak attacks completely (documented + quantified).
4. Confirmation state inherits a 6.7% benign false-confirmation rate.
5. Confirmatory groups reuse G1–G4 scenario DEFINITIONS (new seeds only) —
   parameter-combination novelty is partial (disclosed in the protocol).
6. Multi-horizon probabilities remain incoherent (~32–38% adjacent violations).
7. No hardware validation; SYNTHETIC ONLY.

## 5. Unfinished Work / Next Priority

1. Adopt Platt calibration and re-select the forecaster operating point on
   validation against a stated false-alert budget (the current threshold is
   semantically meaningless).
2. Targeted feature work for the slow-ramp gradient limit — only after the
   operating point is fixed.
3. Monotone horizon projection (validation-fit) if multi-horizon outputs are
   needed operationally.
4. A confirmatory partition with NEW parameter combinations (not just new seeds)
   for stronger generalization claims.
5. NOT recommended: larger models, GNN, denoising — none addresses the measured
   bottlenecks.
6. **Publication:** choose a license (MIT/Apache-2.0/GPL or keep all-rights-reserved);
   this is an author decision and was deliberately not guessed (D-056).
7. The dataset-dependent integration tests only run after regenerating `data/` and
   `artifacts/` locally; CI covers the dataset-independent subset only.

## 6. Critical Context / Instructions

- Commit identity: `PrathamKapoor <prathamkapoor027@gmail.com>` (repo-local config).
- Remote: `origin` = `https://github.com/PrathamKapoor/Quantum-Attack-Detector.git`
  (public, branch `main`). Never force-push; push only from a clean, green state.
- `artifacts/` and `data/` are git-ignored; confirmatory outputs are local evidence
  (hashes recorded).
- Never overwrite v1 evidence or confirmatory stamp directories.
- Any future claim must respect: emission-based timestamps (D-049), evidence-driven
  confirmation (D-050), episode/occupancy accounting (D-051), and the lifecycle
  distinction (detection during preparation ≠ prediction before hostile action).
- Reproduce: `pytest tests/ -q`; `python scripts/evaluate_confirmatory.py`;
  `python scripts/analyze_confirmatory.py <stamp>`.
- Public documentation must keep the README's measured numbers in step with the
  decision log; no number may appear that was not produced by a recorded run.