# decisions.md

Decision log for the Quantum Cyberattack Early-Warning & Detection System.
Format follows master prompt §40. Entries are append-only; superseding entries reference
the earlier ID.

---

### D-001: Greenfield start; no prior architecture exists

- Date / phase / commit: 2026-10-07 / Phase 0 / initial docs commit
- Context: Master prompt warned not to assume a "friend's previous architecture" is correct.
- Decision: Verified by direct inspection — `C:\Projects\Quantumattack` was empty (0 entries incl. hidden) and not a Git repository. There is no prior code, simulator, model, dataset, or documentation to preserve or contradict.
- Why: Avoid designing against imagined legacy constraints.
- Alternatives considered: Searching sibling `C:\Projects` directories for a related repo — rejected as out of scope; the bound workspace is authoritative and was empty.
- Consequences: All master-prompt requirements are treated as "missing"; no migration work exists.
- Files: docs/phase0-audit.md

### D-002: Documentation-first Phase 0, no code changes

- Date / phase / commit: 2026-10-07 / Phase 0 / initial docs commit
- Context: Master prompt §38 Phase 0 mandates audit-only with no unnecessary code changes; §52 STEP 7 forbids implementing the detector before the audit + Phase 1 proposal.
- Decision: Produce the audit + docs set (decisions.md, flow.md, handoff.md, docs/implementation-checklist.md, docs/research-landscape.md, docs/phase0-audit.md) and stop at a Phase 1 proposal for user confirmation.
- Why: The prompt's own gate; also the cheapest point to catch scope/plan disagreement.
- Alternatives considered: Starting the simulator immediately — rejected (violates §52; predictive-label design depends on the Phase 1 attack taxonomy).
- Consequences: No executable deliverable yet; first code lands in Phase 2 after the Phase 1 spec is approved.
- Files: docs/phase0-audit.md, docs/implementation-checklist.md, handoff.md

### D-003: Primary research environment = CV-QKD; BB84/DV as secondary benchmark

- Date / phase / commit: 2026-10-07 / Phase 0 (proposal; revisit at Phase 1 freeze)
- Context: Master prompt §10 prefers CV-QKD "if repository and dependency inspection confirms it is practical".
- Decision: Adopt CV-QKD (Gaussian-modulated coherent-state, homodyne detection) as the primary digital twin. Rationale from inspection: the CV model is expressible with numpy/scipy Gaussian optics (quadrature means/variances/covariance, excess noise, transmittance), which the environment already supports — no new dependencies required for the physics core. BB84 may be added later as a second benchmark only if it does not destabilize scope.
- Why: CV-QKD telemetry (X/P quadratures, LO, covariance) is rich, continuous, and naturally temporal — ideal for trajectory/precursor modeling; attacks like calibration/wavelength/LO-manipulation map directly onto it.
- Alternatives considered: BB84-first — rejected as primary (discrete counting stats give a thinner feature basis); dual-protocol-first — rejected (scope risk, master prompt §10 warning).
- Consequences: Feature taxonomy (§11) will be CV-first; DV-specific features (decoy-state gains) become secondary.
- Files: docs/phase0-audit.md, flow.md

### D-004: Predictive early-warning is the primary product objective

- Date / phase / commit: 2026-10-07 / Phase 0
- Context: Master prompt §1/§6/§51: the product is P(attack within horizon H) from past trajectory, not post-onset classification.
- Decision: Every dataset, label, metric, and UI element is designed around the transition NORMAL → PRECURSOR → ATTACK, with multi-horizon probabilities and lead time as headline metrics. Classification of an ongoing attack is a secondary capability.
- Why: Prevents the common failure of building a static classifier and relabeling it "early warning".
- Alternatives considered: Detection-first with prediction added later — rejected; label design (§9, §19) must be fixed before dataset generation or it cannot be retrofitted cleanly.
- Consequences: Dataset generation (Phase 5) must emit, per timestep, both current-state labels and future-horizon labels; the leakage test (§32) is a first-class deliverable.
- Files: docs/implementation-checklist.md

### D-005: Dependencies installed per-phase, not upfront

- Date / phase / commit: 2026-10-07 / Phase 0 (standing rule)
- Context: Master prompt §45; environment probe shows missing scikit-learn, torch, networkx, xgboost, fastapi.
- Decision: Do not install anything now. Phase 6 installs scikit-learn (+xgboost); Phase 7 installs torch; Phase 8 evaluates and installs the graph stack; the API phase installs fastapi. Each install follows rule §45 (existing-dep check, version check against Python 3.13, decision entry, import verification).
- Why: Avoids version conflicts and unverified installs on Python 3.13; keeps the audit honest.
- Alternatives considered: Installing everything upfront — rejected (violates the spirit of §45; several wheels' 3.13 compatibility is UNKNOWN until tried).
- Consequences: Early phases use only numpy/scipy/pandas/matplotlib/qiskit(+aer).
- Files: docs/phase0-audit.md §3

### D-006: Research landscape is snippet-level until full texts are read

- Date / phase / commit: 2026-10-07 / Phase 0 / initial docs commit
- Context: Master prompt §34 requires a research-landscape document before the architecture is frozen.
- Decision: docs/research-landscape.md lists only sources actually returned by executed web searches this session, with per-row UNKNOWN fields where snippets don't answer a column. No paper is characterized beyond its snippet.
- Why: Rules §33/§0 — never fill gaps from memory or invention.
- Alternatives considered: Waiting until every paper is read before creating the file — rejected; §34 wants the document created and iterated.
- Consequences: Phase 1 must read the listed papers' full texts (or accessible preprints) before freezing the architecture; coverage is explicitly non-exhaustive until then.
- Files: docs/research-landscape.md

### D-007: Git initialized locally with owner-mandated identity; no remote assumed

- Date / phase / commit: 2026-10-07 / Phase 0 / initial docs commit
- Context: Master prompt §43 mandates all commits use `PrathamKapoor <prathamkapoor027@gmail.com>`; the directory had no Git repository.
- Decision: `git init -b main`, local-only `user.name`/`user.email` config as mandated, `core.autocrlf false` locally. No remote configured; none is known to exist (UNKNOWN until the owner provides one).
- Why: Preserves the mandated attribution and avoids inventing a remote.
- Alternatives considered: Global git config change — rejected (affects other projects); assuming a GitHub remote — rejected (unknown).
- Consequences: History starts at the docs commit; pushing requires the owner to provide a remote.
- Files: .git (repository metadata)

---

### D-008: Single-protocol simulator: GMCS CV-QKD with heterodyne detection (confirms D-003)

- Date / phase / commit: 2026-10-08 / Phase 1
- Context: Master prompt §13 requires a defensible first scope; D-003 proposed CV-QKD-first pending Phase 1 freeze. Research verification strengthened the case: the three closest prior works (Mao 2020 HMM, Jin 2024 GNN, Luo 2022 DL) are all CV-QKD.
- Decision: The Phase 1 simulator supports exactly ONE protocol family: Gaussian-modulated coherent-state (GMCS) CV-QKD with heterodyne detection, per-block closed-form Gaussian statistics (no per-symbol simulation). DV protocols (BB84, decoy-BB84, MDI, TF) are NOT supported; DV attacks documented as P2/RESEARCH ONLY in docs/attack-taxonomy.md.
- Why: one strong implementation beats shallow fake support for two protocols (§13); CV telemetry (quadratures, T̂, ε̂, SKR) is continuous and naturally temporal — the richest substrate for trajectory/precursor modeling; the Gaussian model needs no new dependencies.
- Alternatives considered: decoy-state BB84 first (thinner discrete feature basis); dual-protocol (scope risk, explicitly warned against).
- Consequences: feature taxonomy is CV-only; decoy-state features out of scope; protocol module (simulator/protocols/cvqkd.py) written so additional families can slot in later.
- Files: docs/threat-model.md, docs/attack-taxonomy.md, src/quantumattack/simulator/protocols/cvqkd.py

### D-009: Temporal unit chain anchored to experimental per-frame cadence

- Date / phase / commit: 2026-10-08 / Phase 1
- Context: Master prompt §14/§47: define time before prediction; Phase 0 UNKNOWN was target horizons.
- Decision: 1 block = 10 ms = 1e6 symbols @100 MBaud (anchored to source 8: Hajomer et al. 2024 — 1e7 samples/frame @1 Gsample/s = 10 ms parameter-estimation cadence). Chain: block (10 ms) → telemetry record (1/block) → aggregation window W=5 blocks → history L=100 blocks → horizons H∈{10,25,50,100} blocks = {0.1, 0.25, 0.5, 1.0} s. Scenario duration default 2000 blocks = 20 s. All values configurable.
- Why: the experimental anchor makes the synthetic cadence physically defensible; horizons sit inside class-A ramp durations (40–150 blocks) so a correct forecaster can in principle fire during the ramp.
- Alternatives considered: arbitrary H=[1,5,10,25] without unit definition (explicitly forbidden); 1 ms blocks (finer than needed for per-block statistics).
- Consequences: lead_time = attack_onset − warning_time is in blocks/seconds with unambiguous conversion; H defaults recorded here and in docs/time-semantics.md.
- Files: docs/time-semantics.md, src/quantumattack/simulator/config.py (BLOCK_MS, DEFAULT_HORIZONS)

### D-010: Attack onset = mechanism activation, per-attack precise definitions

- Date / phase / commit: 2026-10-08 / Phase 1
- Context: Master prompt §15: attack_onset must not mean "first abnormal telemetry"; lead_time depends on it.
- Decision: attack_onset = first block where the malicious mechanism modifies system state per the attack's definition: intercept-resend = tap insertion + resend begin; LO/calibration manipulation = first block where the ramp reaches the configured operating point (ε̂-bias effective); channel jamming = first full-power jamming block (probe bursts never move it). Encoded per attack module (simulator/attacks/*.py) and exported as metadata.
- Why: precise onset makes lead_time meaningful; "first abnormal telemetry" would conflate detection with onset.
- Alternatives considered: onset = first threshold crossing (rejected: that is the conventional detector's job).
- Consequences: lead time is computable per attack; PRECURSOR labels live strictly inside [precursor_start, attack_onset).
- Files: docs/attack-taxonomy.md, docs/time-semantics.md, src/quantumattack/simulator/attacks/

### D-011: Four P0 attacks; families merged; deliberate precursor-class mixture

- Date / phase / commit: 2026-10-08 / Phase 1
- Context: Master prompt §27/§11: diverse small set; never all-gradual.
- Decision: P0 set = intercept-resend (class C sudden), LO manipulation (class A gradual ramp), detector calibration manipulation (class A gradual ramp), channel jamming (class B optional probes then C sudden). Families 11 (HMM-studied calibration attack) and 13 (LO manipulation) merge into P0 #3/#2; family 12 (detector saturation) merges into #4 (same subsystem/telemetry surface). Benign sudden disturbance episodes (env shocks) added as hard negatives. Mixture: 2 gradual + 1 weak-probe + 2 sudden members; enforced by tests/test_precursor_semantics.py::test_mixture_check_not_all_attacks_gradual.
- Why: diversity of telemetry signatures (mean-shift vs variance/saturation vs T̂-step); the mixture prevents the "instability ⇒ attack" shortcut (§11).
- Alternatives considered: implementing all 13 families (rejected: 13 mediocre attacks vs 4 deep ones); all-gradual design (forbidden by §11).
- Consequences: P2 attacks (PNS, time-shift, blinding, Trojan horse, wavelength) documented but not simulated; calibration manipulation is deliberately confusable with benign calibration drift (the acid test).
- Files: docs/attack-taxonomy.md, src/quantumattack/simulator/attacks/, tests/test_precursor_semantics.py

### D-012: Precursor modeling policy — PROJECT INFERENCE, labeled; no universal ramp

- Date / phase / commit: 2026-10-08 / Phase 1
- Context: Master prompt §10/§32: never invent precursor behavior because it makes prediction easier.
- Decision: Class-A precursors (LO/calibration ramps) are stochastic OU ramps in ramp space (absorbed at 1, never deterministic linear ramps) with configurable duration/magnitude/jump-start; class-B probes are Poisson-scheduled weak blips, off by default; class-C attacks get NO injected pre-onset signal. ALL gradual precursor forms are labeled PROJECT INFERENCE (synthetic research assumption, physics-plausible) in docs/precursor-taxonomy.md — no literature evidence of measured pre-onset attacker telemetry exists (verified absence across ~16 queries).
- Why: scientific honesty (§56); the dataset must let a model conclude "no reliable early warning was possible" for sudden attacks.
- Alternatives considered: universal linear ramp (explicitly avoided); literature-claiming precursors (rejected: would fabricate evidence).
- Consequences: precursor semantics tests enforce interval boundaries and stochasticity; sudden attacks are honest hard negatives.
- Files: docs/precursor-taxonomy.md, src/quantumattack/simulator/attacks/lo_manipulation.py, calibration_manipulation.py, channel_jamming.py

### D-013: Environmental confounder strategy — same functional forms as attacks, smaller magnitude, no operating point

- Date / phase / commit: 2026-10-08 / Phase 1
- Context: Master prompt §12: benign drift must exist so the model cannot equate drift with malicious activity.
- Decision: Implemented benign confounders: temperature (sinusoid+OU) weakly coupled into LO power and excess noise; detector efficiency OU wander; benign calibration gain/offset OU wander (same form as the attack ramp, smaller magnitude, no target); background OU + occasional benign spikes; benign sudden disturbance episodes (prob-gated, one per scenario); clock drift (random walk) with arrival-residual telemetry; fiber-loss OU wander. NOT implemented: fiber aging (months-scale), dark counts (DV concept), shot-noise as independent axis (derived from LO).
- Why: mirrors precursor axes so drift alone cannot imply attack; hard negatives for the forecaster.
- Alternatives considered: implementing all 9 investigated candidates (rejected: dark counts are DV; aging exceeds scenario duration).
- Consequences: benign drift is bit-identical between matched-counterfactual arms (separate environment RNG stream).
- Files: docs/precursor-taxonomy.md §Environmental confounders, src/quantumattack/simulator/environment/drift.py

### D-014: Dataset schema v1 — machine-readable column classes; restricted columns never model inputs

- Date / phase / commit: 2026-10-08 / Phase 1
- Context: Master prompt §33/§34: traceable records; attack metadata must never become predictive inputs.
- Decision: Schema per docs/dataset-spec.md: metadata (scenario_id, pair_id, arm, seed, protocol, sim_version, config_hash, scenario_class, attack_type, attack_onset, precursor_start, precursor_class), labels (state_label, current_attack, future_attack_h10/h25/h50/h100, drift_episode_id), eval-only (true_* ground-truth state, block_index, timestamp_ms), features (35 telemetry columns). Classes machine-readable in src/quantumattack/dataset.py; invariant FEATURE_COLUMNS ∩ RESTRICTED_COLUMNS = ∅ enforced at import and tested.
- Why: prevents attack metadata leakage at the data-design level (§17); the split/OOD strategy builds on it.
- Alternatives considered: single flat table without classification (rejected: leakage-prone).
- Consequences: y_H(t) labels are causal by construction; padding-at-start rule documented for later sequence models.
- Files: docs/dataset-spec.md, src/quantumattack/dataset.py, tests/test_labels_metadata.py

### D-015: Matched-counterfactual protocol — separate seeded RNG streams

- Date / phase / commit: 2026-10-08 / Phase 1
- Context: Master prompt §18: paired runs isolating attack-specific signal from drift.
- Decision: All benign randomness draws from (seed, "environment") + (seed, "measurement") streams; attack randomness from (seed, "attack"). Run A (arm=normal) skips attack stepping; benign trajectories are bit-identical between arms (verified by test_counterfactual_pair_shares_baseline). pair_id = "pair-NNN-<name>", arm ∈ {normal, attack}.
- Why: the precursor-utility analysis requires the ONLY difference between arms to be the attack intervention.
- Alternatives considered: post-hoc telemetry matching (rejected: fragile, not bit-exact).
- Consequences: matched pairs generated by configs/simulation/phase1.yaml (pair: true); analysis scripts compare arms directly.
- Files: docs/dataset-spec.md §3, src/quantumattack/simulator/rng.py, scenario.py, tests/test_labels_metadata.py

### D-016: Phase 1 uses no new dependencies; qiskit-aer version resolved

- Date / phase / commit: 2026-10-08 / Phase 1
- Context: Master prompt §46/§47; Phase 0 records stale.
- Decision: No new packages installed (Phase 1 needs only pytest 9.1.1 + PyYAML 6.0.3 — both already present). qiskit-aer exact version resolved: 0.17.2 (importlib.metadata probe; qiskit 2.5.1). Environment re-probed: Python 3.13.14 (Windows Store, not a venv), numpy 2.4.4, scipy 1.17.1, pandas 3.0.2, matplotlib 3.10.3; scikit-learn 1.8.0, torch 2.13.0, networkx 3.6.1, xgboost 3.2.0, fastapi 0.129.0 now PRESENT (installed outside this project after Phase 0). Phase 0 audit records corrected by this entry; Phase 0 file not rewritten (append-only discipline).
- Why: honest environment documentation; §47 requires resolving the aer version without reinstalling.
- Alternatives considered: virtualenv creation (deferred: no install needed in Phase 1; record if later phases install packages).
- Consequences: later phases must verify wheel compatibility against THIS environment before relying on the pre-installed ML stack.
- Files: docs/phase0-audit.md (superseded by this entry), handoff.md

### D-017: Conventional detection baseline = 5σ thresholds on monitor-visible telemetry

- Date / phase / commit: 2026-10-08 / Phase 1
- Context: Master prompt §38/§39: conventional baselines and lead-time defined before model work.
- Decision: Conventional indicators: ε̂ > base+5σ_ε̂, K̂ < 0.5·K̂_base, |ΔP_LO| > 5σ, imbalance > 5σ, saturation_frac > 0.01, SNR floor — all with the same k-consecutive persistence policy the forecaster must satisfy (fair comparison). lead_time = attack_onset − first_valid_warning; warning policy requires threshold + 3 consecutive windows + cooldown + calibration, tuned on validation only.
- Why: 5σ follows QKD parameter-estimation convention (source 8 uses δ_fail=1e-10 ≈ 6.4σ); not tuned to favor the proposed model (§59).
- Alternatives considered: fixed 11% QBER threshold (DV-specific; our qber_proxy is a proxy).
- Consequences: later phases compare forecast warning time vs conventional detection time under one policy.
- Files: docs/evaluation-protocol.md

---

### D-018: Phase 1 committed before extension (baseline for regression testing)

- Date / phase / commit: 2026-10-08 / Phase 2 / commit 16f8406
- Context: Phase 2 prompt §2 requires verifying Phase 1 before extending it; Phase 1 work was uncommitted.
- Decision: Committed all Phase 1 work (52 files) as commit 16f8406 with mandated author identity; Phase 1 regression suite (40 tests) verified passing on the commit.
- Why: Phase 2 regression tests need a stable baseline; uncommitted work cannot be rolled back against.
- Alternatives considered: extending without committing — rejected (no rollback point).
- Consequences: Phase 2+ changes diff against 16f8406.
- Files: .git (commit 16f8406)

### D-019: Causal feature layer — configurable trailing statistics; explicit-NaN missing-history policy

- Date / phase / commit: 2026-10-08 / Phase 2
- Context: Master prompt §5-§11; Phase 1 feature-spec.md specified candidates without implementation.
- Decision: src/quantumattack/features.py implements 154 derived features (schema v2): backward d1/d2 differences; trailing rolling mean/std over windows {5, 25, 100} blocks; trailing OLS slopes {25, 100}; EWMA spans {5, 25}; two-sided CUSUM (reference = FIRST 100-block warmup window only); two-sample KS (50 vs 50 trailing windows); trailing lag-1 autocorrelation. ALL statistics trailing (window ends at t); derivatives backward. Missing-history policy: explicit NaN until minimum history — never zeros, never future samples. FeatureConfig dataclass makes every window/span/column configurable. Feature metadata (feature_name, source_columns, operation, lookback, causal, units, category) emitted for audits/explainability.
- Why: causality is absolute (§4); the warmup NaN policy is causal and documented; configuration-first design (§7).
- Alternatives considered: start-padding (rejected: would leak scenario start position); partial windows (rejected: biases means); pandas rolling with centered windows (rejected: future leakage).
- Consequences: features are NaN for the first ~100 blocks of every scenario (min_history_blocks=100 skips them for models); schema version 2 recorded.
- Files: src/quantumattack/features.py, feature_config.py, features_cli.py, docs/feature-spec.md, artifacts/phase2/features/feature_schema.json

### D-020: Conventional threshold calibration = empirical quantile on benign TRAIN portions only

- Date / phase / commit: 2026-10-08 / Phase 2
- Context: Master prompt §13-§16: real reactive monitoring baseline; thresholds never tuned on test.
- Decision: Conventional detector (baselines/conventional.py) uses 7 CV-QKD indicators (ε̂, T̂, LO power, det_gain, SKR, saturation, background; qber_proxy EXCLUDED as degenerate per Phase 1) with per-indicator thresholds calibrated on benign TRAIN-portion blocks only. Default method: empirical quantile q=0.995 (normal-σ 5σ and fixed-engineering methods also supported). Warning policy: K=3 consecutive violating blocks + 50-block cooldown, configurable.
- Why: represents a real reactive monitor without being a strawman; calibration-on-train prevents test-set tuning (§14/§25).
- Alternatives considered: fixed 11% QBER threshold (DV-specific, degenerate proxy); tuning thresholds for lead time (forbidden §14).
- Consequences: conventional warning times reproducible; missing warnings reported as null (never zero lead).
- Files: src/quantumattack/baselines/conventional.py, docs/evaluation-protocol.md

### D-021: Scenario-level splitting with hash-seeded assignment; pairs atomic

- Date / phase / commit: 2026-10-08 / Phase 2
- Context: Master prompt §21-§23: telemetry rows are highly correlated; the independence unit is the scenario.
- Decision: baselines/splits.py partitions by SCENARIO with matched pairs atomic (pair members always same partition); deterministic hash-seeded assignment (SplitConfig.seed); OOD holdout by attack family to test entirely (architecture ready, not exercised by default). SplitConfig: train 0.6 / val 0.2 / test 0.2.
- Why: random row splits would leak scenario identity; pair leakage would let the model memorize the environmental trajectory (§21).
- Alternatives considered: random row split (forbidden); seed-only grouping (insufficient — same-seed scenarios can differ by attack).
- Consequences: split validated (disjointness) + pair-isolation checked (both tested); 37/18/10 scenario split for seed 0.
- Files: src/quantumattack/baselines/splits.py, tests/test_baselines.py

### D-022: Logistic baseline = separate per-horizon models; scaler fit on train only

- Date / phase / commit: 2026-10-08 / Phase 2
- Context: Master prompt §17-§27.
- Decision: baselines/logistic.py trains one LogisticRegression per horizon (H∈{10,25,50,100}, class_weight=balanced, C=1.0) on causal features; StandardScaler statistics fit on TRAIN scenarios only, applied to val/test. y_H(t)=1 iff t < onset ≤ t+H; y_H=0 for t ≥ onset (attack no longer future — §19). Rows with t < 100 (insufficient history) skipped. Four ablation feature groups (A/B/C/D, §38) selectable via ModelConfig.feature_group.
- Why: deliberately simple first predictive baseline (§17); if it fails, that is evidence — do not hide it with deeper models.
- Alternatives considered: single multi-horizon model (deferred: separate models are simpler/clearer for Phase 2); fitting scaler on all data (forbidden §24).
- Consequences: predictions carry full metadata (scenario_id, block, per-horizon p, y_true, split, model/feature schema versions) stored to artifacts/phase2/eval/predictions.parquet (never overwritten).
- Files: src/quantumattack/baselines/logistic.py

### D-023: Warning policy = threshold + K=3 consecutive + cooldown + grace-period categories

- Date / phase / commit: 2026-10-08 / Phase 2
- Context: Master prompt §29-§35.
- Decision: Forecast warnings: P(attack within H) ≥ 0.5 for 3 consecutive prediction points → warning at the FIRST block of the satisfied run; 50-block cooldown suppresses re-arming. Timing categories (§32): anticipatory (lead > 5 blocks), immediate (0 ≤ lead ≤ 5), late (lead < 0), none; benign-scenario warnings classified false_early_warning. Policy parameters selected on validation only (default values fixed in Phase 2; not tuned on test).
- Why: a single probability spike must not count as a warning (§29); 1-block and 500-block warnings are different categories (§32).
- Alternatives considered: no persistence (rejected: one noisy sample would warn); collapsing benign warnings into negatives (forbidden §35).
- Consequences: scenario-level false-early-warning rate + per-attack lead-time distributions measured.
- Files: src/quantumattack/baselines/warnings.py

### D-024: Experiment manifest format; artifacts git-ignored

- Date / phase / commit: 2026-10-08 / Phase 2
- Context: Master prompt §44/§46.
- Decision: Machine-readable experiment manifest (experiment_id, phase, dataset, feature_schema, feature_group, split, model, warning_policy, threshold_policy, package_version, created_at) written per evaluation to artifacts/phase2/eval/experiment_manifest.json; predictions.parquet + metrics.json alongside. artifacts/ is generated output — added to .gitignore.
- Why: every result reproducible from (dataset, config, seed); outputs separate from source.
- Alternatives considered: committing artifacts (rejected: regenerable).
- Consequences: Phase 2 results reproducible via documented commands only.
- Files: src/quantumattack/evaluation/harness.py, .gitignore

### D-025: Warning policy selected on validation: thr=0.5, k=3, cooldown=50

- Date / phase / commit: 2026-10-08 / Phase 2
- Context: Master prompt §29: policy parameters must be selected on validation, never test.
- Decision: (thr, k) swept on VAL scenarios only: thr=0.5/k=3 keeps 100% pre-onset attack warning with the lowest benign warning rate achievable (0.64 at H=50, 0.79 at H=100); higher thresholds do not reduce benign warnings (benign P is bimodal under OU drift) and lose coverage at thr=0.95. Selected policy: prob_threshold=0.5, persistence_k=3, cooldown_blocks=50, grace_blocks=5. Applied unchanged to TEST.
- Why: single spikes must not warn (§29); policy tuned only where allowed.
- Alternatives considered: thr=0.95/k=2 (loses 25–50% attack coverage, same benign rate); no persistence (forbidden).
- Consequences: test results reported under the same policy; policy per-dataset re-selection on val required when the dataset changes.
- Files: docs/evaluation-protocol.md §5, src/quantumattack/baselines/warnings.py

---

### D-026: Unpaired dataset design; COUNTERFACTUAL category retained (Phase 3 core change)

- Date / phase / commit: 2026-10-08 / Phase 3 / commit c9cb1a8
- Context: Phase 2 gate (WEAK SIGNAL): paired-only test population made pre-onset warnings benign-drift alarming by construction. Phase 3 prompt §5-§8.
- Decision: docs/dataset-spec-phase3.md (PRE-REGISTERED before any Phase 3 test results): 160 independent unpaired scenarios (100 attacks on seeds 100–119, 60 benign on seeds 200–219 — disjoint seed ranges), per-scenario independent sampling of environment/channel/detector/noise AND attack parameters (within Phase 1 taxonomy ranges) AND onset (uniform 900–1400). Phase 2 paired dataset (65 scenarios) RETAINED as the COUNTERFACTUAL diagnostic category (train-only, never the test population). Feature count unchanged (154, schema v2).
- Why: Metric A (independent early warning) requires attack scenarios without benign twins; Metric B (counterfactual attribution) requires pairs; the two are separate metrics (§17).
- Alternatives considered: deleting pairs (forbidden); weakening the attribution gate (forbidden §2).
- Consequences: genuine unpaired evaluation possible; pairs still serve counterfactual diagnostics.
- Files: docs/dataset-spec-phase3.md, configs/simulation/phase3.yaml, src/quantumattack/simulator/generate.py (unpaired seed pools + per-scenario parameter sampling + name→attack_type mapping + int casting)

### D-027: Pre-registered split + OOD partition (channel_jamming held out)

- Date / phase / commit: 2026-10-08 / Phase 3 (recorded BEFORE evaluation)
- Context: Phase 3 prompt §4/§11: document the split and held-out attack BEFORE evaluating; not chosen for favorable results.
- Decision: SplitConfig(seed=42, counterfactual_to_train=True, ood_holdout_family="channel_jamming") fixed before any Phase 3 model run. OOD rationale: channel jamming is the availability-asset attack with a variance/saturation telemetry surface, distinct from the mean-shift gradual attacks dominating training — a real cross-family generalization test; its Phase 2 behavior was weak/unreliable, so the choice is not favorable-result-driven. Unit key fixed: unpaired scenarios split by (definition, seed) — the first implementation grouped by definition base, which put entire attack families in one partition (diagnosed and fixed before any evaluation used it).
- Why: seed-level splitting keeps the test population mixed (known + OOD families); definition-level grouping would have made the split degenerate.
- Alternatives considered: intercept_resend as OOD (rejected: its no-precursor behavior makes OOD results uninformative about cross-family generalization).
- Consequences: verified partition (train 72 / val 24 / test 64; all 40 jamming scenarios in test; 0 in train).
- Files: docs/dataset-spec-phase3.md, src/quantumattack/baselines/splits.py

### D-028: Sustained-until-onset warning policy (Phase 3 policy fix)

- Date / phase / commit: 2026-10-08 / Phase 3
- Context: First unpaired run showed 100% "anticipatory" success with median lead 900–1000 blocks for ALL attacks INCLUDING intercept-resend (no pre-onset signal — impossible physics) and FWR(NORMAL)=1.0. Diagnosis: the policy counted the FIRST k=3 run above threshold as the warning — warmup noise (t≈100–300, right after the feature warmup boundary) fired warnings on everything.
- Decision: WarningPolicy.sustained_until_onset (pre-declarable): a warning counts only when P stays above threshold from the k-run until onset (attack scenarios) or scenario end (benign). Transient spikes (warmup noise, drift blips) are not warnings. Applies uniformly to ALL models; not tuned on test.
- Why: a warning that fires and then dips is a transient, not a warning (master prompt §29 persistence intent); the inflated lead time was an evaluation artifact, fixed at policy level — NOT by touching the simulator or the attacks (§2).
- Alternatives considered: warmup-guard (discard warnings before block 200 — similar effect but less principled: the sustain requirement IS the persistence semantics); lowering thresholds (forbidden §2).
- Consequences: results became scientifically coherent (gradual attacks 67–100% success with median lead 78–127 blocks; FWR NORMAL 0.21, BENIGN_DRIFT 0.0; intercept-resend 0% — correct physics).
- Files: src/quantumattack/baselines/warnings.py

---

### D-029: Phase 4 Pre-registered Scale-Up Protocol & Disjoint Stride-7 Seed Pools

- Date / phase / commit: 2026-10-09 / Phase 4
- Context: Phase 4 prompt §6, §7, §8: Pre-register experiment before test evaluation; scale scenario diversity without relaxing threat model or precursor parameters; eliminate accidental seed overlap across definitions.
- Decision: Frozen protocol in `docs/phase4-protocol.md` v1. 284 scenarios total (234 independent unpaired + 50 counterfactual paired). Seed pools constructed with non-sequential stride-7 arithmetic across disjoint ranges: TRAIN [1000..1833] (120 seeds, 20/def), VAL [5000..5287] (42 seeds, 7/def), TEST [9000..9287] (42 seeds, 7/def), OOD [13000..13203] (30 seeds, 15/def). Partition fixed by seed pool by construction (never hash-assigned).
- Why: Eliminates cross-definition correlation present in Phase 3; guarantees strict disjointness across train, val, test, and OOD; expands gradual attack scenarios by 1.7× (34 vs 20).
- Alternatives considered: Pure random uniform seed generation (rejected: non-deterministic across platforms without seed lists; stride-7 arithmetic is fully deterministic and collision-free).
- Consequences: Disjointness and isolation verified programmatically; dataset manifest versioned `phase4-v1`.
- Files: docs/phase4-protocol.md, configs/simulation/phase4.yaml, src/quantumattack/simulator/generate.py, tests/test_phase4_dataset.py

### D-030: Scenario-Level Bootstrap Uncertainty Protocol (§19, §20)

- Date / phase / commit: 2026-10-09 / Phase 4
- Context: Master prompt §19: Telemetry windows are NOT independent observations. Primary uncertainty must be calculated at the scenario level.
- Decision: Scenario bootstrap protocol implemented with B=2000 resamples with replacement (fixed seed 2026) resampling entire scenario trajectories. 95% percentile confidence intervals computed for warning success rates, median lead times, mean lead times, false early-warning rates (NORMAL and BENIGN_DRIFT), and paired forecast gain. Multi-split variability evaluated across 5 independent split seeds (42, 7, 101, 2024, 31337).
- Why: Window-level sampling drastically underestimates standard errors and creates fake precision; scenario bootstrap preserves intra-scenario autocorrelation and provides honest operational uncertainty bounds.
- Alternatives considered: Window-level bootstrap (rejected: violates independence); parametric Gaussian CIs (rejected: lead-time distributions are skewed).
- Consequences: All headline metrics report valid 95% scenario CIs; fake precision avoided.
- Files: scripts/evaluate_phase4.py, artifacts/phase4/eval-logistic/phase4_metrics.json, artifacts/phase4/multisplit-summary.json

### D-031: Feature Freeze v1 & Forecast vs Confirmation Taxonomy (§27, §28, §29)

- Date / phase / commit: 2026-10-09 / Phase 4
- Context: Feature ablation and redundancy analysis across 189 features; distinction required between predictive pre-onset indicators and post-onset security monitors.
- Decision: Formalized `docs/feature-freeze-v1.md`. Retained `FEATURE_SCHEMA_VERSION = 2` (154 derived causal features). Classified features into CORE (transmittance, det_gain, lo_sig_ratio, rolling means, CUSUM drifts), USEFUL (auxiliary power/noise/slopes), REDUNDANT (246 pairs with |r| > 0.95), UNSTABLE (33 features with near-zero weight and CV > 1.5), POST-ONSET ONLY (QBER proxy, sudden variance step, SKR collapse), and FUTURE WORK.
- Why: Features like `qber_proxy` have zero predictive power for gradual precursors (precursor r=0) but are mandatory for post-onset attack confirmation; deleting post-onset features would destroy reactive confirmation capability.
- Alternatives considered: Blindly dropping all correlated features (rejected: preserves operational redundancy and non-linear model inputs).
- Consequences: Operational roles frozen; distinction between PREDICTED and CONFIRMED established in architecture.
- Files: docs/feature-freeze-v1.md, scripts/feature_freeze_analysis.py, artifacts/phase4/feature-analysis/feature_analysis.json

### D-032: Graph Model Decision Gate Outcome: HOLD (§31–§43)

- Date / phase / commit: 2026-10-09 / Phase 4
- Context: Phase 4 mandates deciding whether to implement a GNN only after evaluating whether graph structure provides measurable additional value over sequence/feature baselines.
- Decision: Graph Model Gate is formally set to **HOLD**. GNN implementation is NOT performed in Phase 4. Rationale recorded in `docs/graph-hypothesis.md`:
  1. Precursors in the current simulator are single-component ramp drifts (LO power ramp, calibration gain ramp, probe pulse train); their telemetry manifestations are column-wise mean shifts.
  2. The 154-feature causal layer already captures all available temporal drift signal (H=100 AUROC 0.847, 85-100% warning rate on gradual attacks).
  3. The physical graph is a shallow chain (source -> channel -> receiver -> detector) whose message passing represents a fixed linear combination of features already accessible to linear and recurrent models.
  4. Deep sequence models (GRU/TCN) showed no attributable lead-time advantage over logistic regression (GRU H=10 AUROC 0.625 on test vs logistic 0.792), raising the burden of proof for architectural escalation.
- Why: Master prompt §42 & cardinal rule: "Do not build a GNN simply to satisfy the original architecture idea. Build it only if evidence shows missing cross-component information." Escalating to GNN without empirical cross-component motivation would be unscientific.
- Alternatives considered: Implementing a GNN regardless (rejected: violates gate criteria and pre-registered protocol); REJECT (rejected: reserved if graph is proven useless across all simulators; a future multi-component simulator could benefit from graphs).
- Consequences: Architectural escalation prevented; findings remain honest; GNN requirements for future phases pre-specified.
- Files: docs/graph-hypothesis.md, docs/phase4-final-report.md

### D-033: Phase 4 Scientific Gate: ATTACK-SPECIFIC ROBUST SIGNAL (§46, §48)

- Date / phase / commit: 2026-10-09 / Phase 4
- Context: Final determination of early-warning signal validity across scale-up, multi-split evaluation, and ablation.
- Decision: Scientific gate declared as **`ATTACK-SPECIFIC ROBUST SIGNAL`**.
  - Gradual attacks exhibit high warning rates: `lo_manipulation` 100% (95% CI [1.0, 1.0], median lead 103 blocks, 5-split mean 85.1%), `calibration_manipulation` 100% (95% CI [1.0, 1.0], median lead 124 blocks, 5-split mean 87.1%).
  - Sudden attacks correctly yield 0% pre-onset warning: `intercept_resend` 0% (95% CI [0.0, 0.0], correct physical baseline).
  - Benign drift robustness: `FWR(BENIGN_DRIFT)` = 0.0% (identically zero across all 5 split seeds).
  - `FWR(NORMAL)` = 0.231 (95% CI [0.0, 0.462], 5-split mean 0.226).
  - Outperforms conventional detector: Forecast detector achieves 463-498 blocks earlier detection than conventional detector on gradual attacks, while conventional detector suffers catastrophic 100% FWR on BENIGN_DRIFT.
- Why: Signal is robust and reproducible across 284 scenarios and 5 independent split seeds; clearly differentiated between forecastable gradual attacks and sudden attacks.
- Alternatives considered: ROBUST EARLY-WARNING SIGNAL (rejected: cannot claim universal early warning when sudden attacks legitimately have no precursor); WEAK SIGNAL (rejected: 100% warning rates on gradual attacks with 0% FWR on benign drift over 1.7x scale-up exceeds weak signal threshold).
- Consequences: Phase 4 successfully validates statistical and operational robustness of the early-warning system.
- Files: docs/phase4-final-report.md, handoff.md

### D-034: Phase 5 Generalization Partitions & Pre-registered Seed Pools

- Date / phase / commit: 2026-10-09 / Phase 5
- Context: Phase 5 mandates evaluating generalization across five distinct axes: G1 (unseen scenario seeds), G2 (parameter extrapolation), G3 (environmental stress), G4 (attack stress/hybrid), G5 (simulator validity).
- Decision: Pre-registered 160 scenarios across disjoint seed pools in `configs/simulation/phase5.yaml`:
  - G1 (Scenario Generalization): 60 scenarios (seeds 20000..20413, stride 7)
  - G2 (Parameter Extrapolation): 40 scenarios (seeds 25000..25273, stride 7)
  - G3 (Environmental Stress): 30 scenarios (seeds 30000..30203, stride 7)
  - G4 (Attack Stress / Hybrid): 30 scenarios (seeds 35000..35203, stride 7)
  All seeds are strictly disjoint from Phase 4 (<15000). Stride-7 arithmetic guarantees collision freedom.
- Why: Tests whether early-warning signal survives out-of-distribution parameterizations, extreme environmental shifts, and adversarial variation without leaking test data into model fitting.
- Alternatives considered: Evaluating on randomized splits of Phase 4 data (rejected: fails to evaluate parameter and environmental extrapolation).
- Consequences: Independent generalization evaluated cleanly against frozen Phase 4 model.
- Files: docs/phase5-protocol.md, configs/simulation/phase5.yaml, tests/test_phase5_dataset.py

### D-035: Evaluation of Frozen Phase 4 Logistic Forecaster on Independent Generalization

- Date / phase / commit: 2026-10-09 / Phase 5
- Context: Testing whether the model trained on Phase 4 generalizes without retraining or tuning on Phase 5.
- Decision: Evaluated the frozen Phase 4 regularized logistic forecaster (Group D, 189 features, H=10, 25, 50, 100) using the frozen `sustained_until_onset` warning policy across Partitions G1–G4. Scenario bootstrap uncertainty computed with B=2000 resamples.
- Findings:
  - G1 (Scenario Generalization): AUROC = 0.901, LO Warn Rate = 90.0% (95% CI [0.70, 1.00], median lead 78 blk), Cal Warn Rate = 90.0% (95% CI [0.70, 1.00], median lead 99 blk), Intercept-Resend = 0.0%, Benign Drift FWR = 0.0%, Normal FWR = 35.0%.
  - G2 (Parameter Extrapolation): AUROC = 0.863, LO Warn Rate = 71.4% (fast ramp: 100%, slow ramp: 42.9%), Cal Warn Rate = 85.7% (steep: 100%, slow: 71.4%), Intercept-Resend = 0.0%, FWR = 0.0%.
  - G3 (Environmental Stress): Pure benign partition with extreme drift ($0.06\text{ dB/blk}$), high disturbance ($p=0.8$), thermal stress. Model achieved **0.00% FWR** (0/30 scenarios fired warnings).
  - G4 (Attack Stress / Hybrid): Jamming dense probes = 100% warning (median lead 147 blk); sudden high-power jamming = 26.7% warning (median lead 0 blk).
- Why: Establishes that gradual attack warning generalizes strongly to unseen seeds and varied parameters, and false alarm rejection is invariant to severe environmental drift.
- Alternatives considered: Retraining logistic forecaster on Phase 5 data (rejected: confirmatory evaluation requires testing the frozen model).
- Consequences: Confirms G1, G2, G3, and G4 hypotheses with quantified operational bounds.
- Files: scripts/evaluate_phase5.py, artifacts/phase5/evaluation/phase5_generalization_report.json

### D-036: Robustness Stress Testing Suite (Tests A through I)

- Date / phase / commit: 2026-10-09 / Phase 5
- Context: Controlled perturbation testing mandated to uncover failure modes and empirical boundaries.
- Decision: Implemented and executed `scripts/stress_tests_phase5.py` covering Tests A–I:
  - Test A (Noise Sensitivity): Sharp cliff observed. At $\sigma=0.00$, AUROC=0.896; at $\sigma=0.02$, AUROC collapses to 0.503 (random guessing). Unregularized causal feature linear combination is brittle to observation noise without denoising.
  - Test B & F (Environmental Shift & Lookalikes): 0.00% FWR across 30 extreme benign scenarios.
  - Test C & D (Ramp Duration & Bias Shift): Fast ramps detected at 100%; slow ramps diffuse gradients to 42.9% warning. Extended precursors yield median lead of 228 blocks (22.8 s).
  - Test G (Jamming Variants): Pre-attack dense probing is 100% detectable (147 blk lead); sudden high-power jamming is unheralded (26.7%, 0 blk lead).
  - Test H (Sudden Attacks): Intercept-resend yields exactly 0.0% pre-onset warnings across all parameterizations.
  - Test I (Reproducibility): 113/113 pytest regression suite passes.
- Why: Provides honest engineering bounds on where early warning succeeds (structured precursors, environmental shifts) and where it fails (additive noise, sudden unheralded attacks).
- Consequences: Documented in `docs/phase5-robustness-report.md`.
- Files: scripts/stress_tests_phase5.py, artifacts/phase5/stress_tests/stress_tests_summary.json, docs/phase5-robustness-report.md

### D-037: Simulator Validity Audit & Epistemic Boundary (G5)

- Date / phase / commit: 2026-10-09 / Phase 5
- Context: Epistemic evaluation of the digital twin; mandatory declaration regarding physical hardware validity.
- Decision: Completed comprehensive audit in `docs/simulator-validity-audit.md`. Categorized every component into established physical mechanism (Beer-Lambert, Poissonian statistics, sudden intercept-resend), literature-supported model (polarization drift, SPAD/SNSPD efficiency, LO blinding), engineering approximation (control loop feedback hunting, spatial jamming), project inference (causal rolling features, warning policy), and unvalidated assumption (linear saturation curve, Gaussian actuator noise).
- Declaration: The digital twin is **SYNTHETIC ONLY**. No hardware validation is claimed or implied.
- Consequences: Scientific integrity maintained; production prerequisites explicitly defined.
- Files: docs/simulator-validity-audit.md

### D-038: Phase 5 Gate Outcomes: ATTACK-SPECIFIC ROBUST GENERALIZATION & Graph Gate HOLD

- Date / phase / commit: 2026-10-09 / Phase 5
- Context: Formal phase closeout gates.
- Decision:
  1. Scientific Gate declared as **`ATTACK-SPECIFIC ROBUST GENERALIZATION`**: The early-warning signal generalizes to unseen scenario seeds (G1 AUROC 0.901, warning rate 90%), parameter variations (G2 warning rate 71–86%), extreme environmental shifts (G3 FWR 0.0%), and hybrid attack probing (G4 probe warning rate 100%), while strictly maintaining 0.0% false alarms on sudden attacks.
  2. Simulator Evidence Status declared as **`SYNTHETIC ONLY`**.
  3. Graph Model Gate formally maintained at **`HOLD`**: The early warning signal remains governed by single-component temporal dynamics and local control-loop hunting. Graph escalation remains unjustified in the absence of multi-node spatial dependencies.
- Consequences: Phase 5 successfully closed out; repository in clean, fully verified state.
- Files: docs/phase5-final-report.md, handoff.md

### D-039: Single authoritative temporal-unit conversion (`temporal_units`)

- Date / workstream / commit: 2026-10-11 / Metric integrity / uncommitted
- Context: Phase 5 reports stated lead times as "78 blocks = 7.8 s", "99 blocks = 9.9 s", "147 blocks = 14.7 s", "228 blocks = 22.8 s". These imply 0.1 s/block, contradicting `docs/time-semantics.md` (1 block = 10 ms) and the code constant `simulator.config.BLOCK_MS = 10.0`.
- Observed symptom: Reported lead times were 10x larger than the simulator's actual time base.
- Verified root cause: The conversion in the *code* is correct (`lead_time_ms = blocks * BLOCK_MS`; `manifest.json` records `block_ms: 10.0`; `Clock.t_ms = block_index * BLOCK_MS`). The defect was confined to **human-readable report text** in `docs/phase5-final-report.md` and `docs/phase5-robustness-report.md`, which used 0.1 s/block. No stored numeric metric was corrupted; `median_lead_blocks` is correct and the seconds column was wrong.
- Decision: (a) Confirm the code time base is authoritative and unchanged. (b) Introduce `src/quantumattack/temporal_units.py` as the single conversion authority (`blocks_to_seconds`, `seconds_to_blocks`, `blocks_to_ms`, `blocks_to_symbols`, `horizon_seconds`, `verify_time_base`) so the factor-of-ten class of error cannot recur in machine-readable outputs. (c) Correct the Phase 5 report seconds values by *superseding annotation*, not by rewriting the stored artifacts.
- Why: Duplicated ad-hoc time constants are the root cause; a single authority plus regression tests removes the failure mode.
- Alternatives considered: Changing `BLOCK_MS` to 100 ms — rejected: the simulator's cadence is anchored to a 10 ms parameter-estimation frame (docs/time-semantics.md §1) and changing it would corrupt every dataset. Editing historical reports in place — rejected: they are research evidence; superseded values are added with explicit traceability instead.
- Consequences: 78 blocks = 0.78 s; 99 = 0.99 s; 147 = 1.47 s; 228 = 2.28 s. Horizon table H=10/25/50/100 = 0.1/0.25/0.5/1.0 s confirmed by test.
- Bug-fix metadata — Observed symptom: factor-of-ten inflation of all reported lead-time seconds. Verified root cause: ad-hoc 0.1 s/block literal in report prose while code used `BLOCK_MS`. Regression test: `tests/test_metric_integrity.py::test_blocks_to_seconds_regression_values`, `::test_horizon_durations_match_documented_table`, `::test_block_is_ten_milliseconds_not_one_hundred`.
- Files: src/quantumattack/temporal_units.py, tests/test_metric_integrity.py, docs/reliability-research-report.md

### D-040: Horizon-valid forecasting accounting (supersedes the merged "anticipatory rate")

- Date / workstream / commit: 2026-10-11 / Metric integrity / uncommitted
- Context: A model at horizon H predicts `P(onset within (t, t+H])`. `docs/time-semantics.md` §5 defines `y_H(t)=1` only when `t < onset <= t+H`. The evaluator (`baselines/warnings.py::warning_category`) nevertheless classified ANY warning with `lead > grace_blocks` as "anticipatory", regardless of H, and counted it as an H-forecast success.
- Observed symptom: Phase 5 reported G1 `calibration_manipulation` at 90% and `channel_jamming` (dense probes) at 100% "anticipatory warning rate" at H=100, with median leads of 99 and 147 blocks — the latter exceeding H=100 outright. Lead times up to **567 blocks** (5.67 s) were credited to a 100-block (1.0 s) forecaster.
- Verified root cause: No horizon-validity constraint existed in the success accounting. Measured on G1+G2+G4 at H=100: **29 of 79 anticipatory warnings (37%) exceeded the horizon**. At those times the true label was `y_100 = 0`, so a probability above threshold is a false positive of the horizon-100 event, not a successful forecast.
- Decision: Introduce `src/quantumattack/forecast_horizons.py` with `classify_warning_outcome` returning exactly one of five mutually exclusive outcomes: `horizon_valid_forecast` (0 < lead <= H), `extended_pre_onset_alert` (lead > H), `onset_detection`, `post_onset_confirmation`, `no_warning`. Only `horizon_valid_forecast` earns horizon-forecast credit. The historical `warning_category` is left intact for backwards compatibility with frozen artifacts; new reporting uses the new taxonomy.
- Why: Prediction, extended alerting and post-onset confirmation are different security capabilities; merging them inflates the headline claim. The three measurements are now reported separately, never summed.
- Alternatives considered: (a) Relabel warnings instead of re-scoring — rejected, would leave the counts wrong. (b) Restrict evaluation to horizons large enough to cover observed leads — rejected, that would redefine the forecaster to fit the data. (c) Treat over-horizon warnings as invalid experiments — rejected, they are genuine alerts and are reported as `extended_pre_onset_alert`.
- Consequences (measured, G1, H=100, Wilson 95% CI): `calibration_manipulation` 90% -> **50.0% [23.7%, 76.3%]**; `lo_manipulation` 90% -> **50.0% [23.7%, 76.3%]**. G4 `channel_jamming` 63.3% -> **16.7% [7.3%, 33.6%]** with 46.7% as extended alerts. Horizon-valid median leads: 0.89 s (cal-manip), 0.67 s (LO-manip), 0.29 s (jamming).
- Bug-fix metadata — Observed symptom: out-of-horizon warnings counted as H-forecast successes. Verified root cause: success accounting lacked a `lead <= H` constraint. Regression test: `tests/test_metric_integrity.py::test_warning_inside_horizon_is_horizon_valid`, `::test_warning_just_beyond_horizon_is_extended_alert_not_forecast`, `::test_warning_far_beyond_horizon_is_still_extended_alert`, `::test_horizon_validity_shrinks_as_horizon_shrinks`.
- Files: src/quantumattack/forecast_horizons.py, scripts/evaluate_reliability.py, tests/test_metric_integrity.py

### D-041: Wilson score intervals for event rates; scenario as the statistical unit

- Date / workstream / commit: 2026-10-11 / Statistical correctness / uncommitted
- Context: `scripts/evaluate_phase5.py::rate_ci` estimated warning and false-warning rates with a percentile bootstrap over a degenerate binary vector. For an all-success group (7/7) it returned exactly `[1.0, 1.0]`; for an all-failure group (0/30) exactly `[0.0, 0.0]`. Phase 5 reported "100.0% [100.0%, 100.0%]" and "0.0% [0.0%, 0.0%]" as confidence intervals.
- Observed symptom: Zero-width confidence intervals asserting certainty from 7–15 correlated scenarios.
- Verified root cause: A percentile bootstrap on a binary vector whose every entry is identical has zero sampling variance by construction. The interval width was an artifact of the estimator, not evidence of certainty.
- Decision: Introduce `src/quantumattack/statistics.py` with `wilson_interval` (validated to 1e-10 against an independent implementation, and against `scipy.stats.norm.ppf` to 1e-9 for the quantile) and `scenario_cluster_bootstrap` (resamples whole scenarios, records seed, counts failed resamples, returns None for undefined groups). All new reporting uses Wilson for event rates and scenario-clustered bootstrap for AUROC/AUPRC/Brier/lead time.
- Why: Small samples do not justify certainty; an operator acting on "100% [100%, 100%]" would be misled.
- Alternatives considered: Clopper-Pearson exact intervals — valid and similarly non-degenerate, but more conservative and wider; Wilson chosen for standard practice and adequate coverage at these sample sizes. Installing statsmodels — rejected: adds a dependency for functionality correctly implemented with existing numpy/scipy.
- Consequences: 7/7 now reports [64.6%, 100%]; 0/30 reports [0%, 11.4%]. G1 `calibration_manipulation` horizon-valid 50% (n=10) reports [23.7%, 76.3%].
- Bug-fix metadata — Observed symptom: degenerate [1,1]/[0,0] intervals. Verified root cause: bootstrap over a constant binary vector. Regression test: `tests/test_metric_integrity.py::test_wilson_interval_is_nondegenerate_at_zero_and_one`, `tests/test_statistics.py::test_wilson_narrows_with_more_samples`.
- Files: src/quantumattack/statistics.py, tests/test_statistics.py, tests/test_metric_integrity.py

### D-042: Telemetry perturbation defined in explicit units (`noise_models`)

- Date / workstream / commit: 2026-10-11 / Reliability / uncommitted
- Context: Phase 5 Test A added a single absolute `sigma=0.02` to the raw feature matrix and reported "a sharp cliff at sigma >= 0.02 collapsing AUROC from 0.896 to 0.503", concluding the feature set was brittle and that denoising/Kalman filtering would be mandatory.
- Observed symptom: AUROC collapsed to chance and stayed at 0.503 for sigma in {0.05, 0.1, 0.2}.
- Verified root cause: Group-D features span ~17 orders of magnitude in training spread. Measured on the frozen Phase 4 train split (189 features): `qber_proxy` std ~4.7e-17, `recon_efficiency` std ~3.5e-12, `cusum_neg_lo_power` std ~1.5e5. A fixed absolute sigma=0.02 equals **>= 1x the feature's own train std for 93 of 189 features**, **>= 5x for 63 features**, and ~5.7e9x for `recon_efficiency`. The experiment destroyed small-scale features completely while leaving large-scale ones untouched; the "cliff" was a units artifact, and the saturation at identical AUROC for all larger sigma confirmed saturation rather than graded degradation.
- Decision: Introduce `src/quantumattack/noise_models.py` requiring an explicit `units` string on every perturbation: `train_sigma` (multiples of each feature's TRAIN std), `feature_range` (fraction of TRAIN IQR), or `raw_absolute` (the legacy definition, retained **only** to reproduce the historical experiment and labelled not physically meaningful). Add structured corruptions (temporally correlated noise, impulsive spikes, quantization, missing-sample dropout, dead channels). Feature scale is fit on TRAIN data only.
- Why: A robustness claim is meaningless unless the perturbation magnitude is expressible in a comparable scale. The historical conclusion "the model is brittle" was an artifact.
- Alternatives considered: Adding a denoiser (Kalman/EWMA) as the first response — rejected: that would treat a symptom whose cause was never established, and would have been evaluated on a saturated metric that cannot discriminate.
- Consequences (G1, H=100, re-measured): train-sigma 0.0 -> AUROC 0.896; 0.05 -> 0.861; 0.1 -> 0.815; 0.2 -> 0.740; 0.5 -> 0.644; 1.0 -> 0.592; 2.0 -> 0.549. Legacy raw-absolute 0.02 -> 0.499. Degradation is **gradual and interpretable**, not a cliff. The correct engineering conclusion is that tolerance is roughly 0.2 train-sigma units before AUROC falls below 0.75.
- Bug-fix metadata — Observed symptom: unit-ambiguous noise experiment producing a false robustness cliff. Verified root cause: absolute sigma applied to heterogeneous features. Regression test: `tests/test_noise_models.py::test_train_sigma_noise_scales_with_each_feature`, `::test_raw_absolute_overwhelms_small_features`.
- Files: src/quantumattack/noise_models.py, tests/test_noise_models.py, scripts/evaluate_reliability.py

### D-043: NORMAL false alarms are sustained benign drift, not a warmup artifact

- Date / workstream / commit: 2026-10-11 / Reliability investigation / uncommitted
- Context: Phase 5 reported a 35.0% NORMAL false-warning rate alongside 0.0% BENIGN_DRIFT, without root-cause analysis.
- Observed symptom: 7 of 20 G1 NORMAL benign scenarios raised at least one warning, while 0 of 20 G3 stress scenarios (which reach max p = 0.9999) raised any.
- Verified root cause: Under the frozen `sustained_until_onset=True` policy, a benign warning is retained only if the probability stays above threshold from the first block of the K-run until **scenario end**. Measured: every one of the 3 G1 NORMAL scenarios whose above-threshold run reaches the end of the scenario produced a false alarm; **0 of the 53 benign scenarios whose run does not reach the end did**. G3 intense-disturbance scenarios spike to p ~ 0.999 transiently but fall back below threshold, so they are correctly filtered. The 7 failing G1 scenarios first warn at blocks 967–1995 (median 1934) — i.e. late scenario, ruling out a warmup artifact.
- Decision: Classify this as **true observational ambiguity under a sustained alarm policy**, not a code defect. The operating alarm burden is reported with three distinct quantities rather than one rate: scenario-level false-alarm rate, mean warnings per scenario (2.35), and warning-load fraction (5.1% of operating time). Hour-normalized rates are explicitly NOT reported because a scenario is only 20 s of simulated operation, making an hourly rate an extrapolation ~180x beyond the simulated window.
- Why: Distinguishing "the model cannot tell benign drift from precursor" from "the alarm policy is deliberately sticky" changes the correct remedy (operating-point selection vs. new features).
- Alternatives considered: Removing the NORMAL failures from the dataset — rejected (would hide the result). Relaxing `sustained_until_onset` — rejected without evidence, since it was introduced in D-028 precisely to remove warmup-noise false warnings; the trade-off must be measured on validation, not decided here.
- Consequences: G1 NORMAL false-alarm rate 35.0% [18.1%, 56.7%] is a real operational burden under the frozen policy, not a measurement error. G3 0/20 reports [0%, 16.1%], not [0%, 0%].
- Files: scripts/evaluate_reliability.py, docs/reliability-research-report.md

### D-044: Frozen logistic probabilities are miscalibrated; Platt scaling on validation fixes it

- Date / workstream / commit: 2026-10-11 / Calibration / uncommitted
- Context: The warning policy thresholds raw logistic output at P >= 0.5, yet Phase 5 never verified that those numbers mean anything.
- Observed symptom: On G1 at H=100, the uncalibrated forecaster has ECE = 0.191 and Brier = 0.119 — severely overconfident relative to the empirical event rate.
- Verified root cause: `class_weight='balanced'` is applied to a target with a ~2.8% positive rate, so the fitted intercept is optimized for a heavily re-balanced objective and the resulting sigmoid does not correspond to the true conditional frequency.
- Decision: Evaluate calibration variants fit on the **Phase 4 validation partition only** (41 scenarios, 77,900 rows, 1,800 positives at H=100): uncalibrated vs Platt vs isotonic. Results: Platt Brier 0.119 -> **0.0216**, ECE 0.191 -> **0.0105**; isotonic Brier 0.0211, ECE 0.0118 (supported: 1,800 positives >= 200 threshold).
- Why: A probability that is off by ~0.19 in expected calibration error cannot support a P >= 0.5 operating point. Calibration was never the cause of the reported AUROC (AUROC is rank-based and unchanged), but it directly determines whether the threshold is meaningful.
- Alternatives considered: Changing `class_weight` — rejected: it would alter the frozen baseline that all prior results depend on. Fitting calibration on G1 — rejected: G1 is an exposed evaluation partition (see the protocol's disclosure section).
- Consequences: The frozen baseline is preserved and reproducible; calibration is offered as a validated, validation-fit correction with its clean-condition effect reported. Probabilities remain calibrated to the **synthetic** attack distribution only and are not real-world attack probabilities.
- Files: scripts/evaluate_reliability.py, docs/reliability-evaluation-protocol.md

### D-045: Explicit operational warning state machine

- Date / workstream / commit: 2026-10-11 / Operational reliability / uncommitted
- Context: The repository had a warning *policy* but no notion of the monitoring system's operating state. Master prompt §16 requires distinguishing normal telemetry, elevated risk, valid pre-attack warning, confirmed active attack, degraded telemetry, abstention and recovery.
- Decision: Add `src/quantumattack/operational_states.py` with seven explicit states (`NORMAL`, `ELEVATED`, `PRE_ATTACK_WARNING`, `ACTIVE_ATTACK_CONFIRMED`, `DEGRADED_TELEMETRY`, `ABSTAINING`, `RECOVERY`) driven by `operational_state_series(...)`. Alarm states are sticky and cleared only by the documented recovery rule; cooldown suppresses re-arming; `ACTIVE_ATTACK_CONFIRMED` is reached from sustained evidence (independent of any forecast); degraded/abstain blocks are never counted as successful negatives.
- Why: "Missing information does not prove normal operation." A degraded reading reported as a confident low-risk NORMAL would be an operational safety defect.
- Bugs fixed (both caught by the new tests, not present in earlier code): (a) a short-circuit in the usability check (`usable and finite and …`) let a NaN probability pass as valid when telemetry was otherwise usable; (b) the recovery branch could never be reached because `below_run` reset conflicted with the alarm branches, so alarms dropped out after one block instead of persisting.
- Consequences: On G1 (60 scenarios) the machine enters PRE_ATTACK_WARNING in 49 and reaches ACTIVE_ATTACK_CONFIRMED in 27; under 2% induced missing telemetry (15 scenarios) it produces 13,200 DEGRADED and 11,460 ABSTAINING blocks and never silently reports NORMAL.
- Files: src/quantumattack/operational_states.py, tests/test_operational_states.py, scripts/evaluate_reliability.py

### D-046: Slow-ramp failure is a gradient-rate limit, not an amplitude limit

- Date / workstream / commit: 2026-10-11 / Reliability investigation / uncommitted
- Context: Phase 5 reported slow-ramp warning rates far below fast-ramp (42.9% vs 100%) without establishing the mechanism.
- Observed symptom: `lo-manipulation-slow-ramp` 42.9% and `calibration-manipulation-slow` 71.4% versus 100% for the fast/steep variants.
- Verified root cause: Measured over the final 100 pre-onset blocks, slow and fast ramps produce essentially the SAME precursor amplitude (excess_noise 0.0107 vs 0.0103; lo_power 0.32 vs 0.27), so the degradation is NOT weak amplitude. Benign drift, however, spans a comparable excess_noise range (median 0.0193) within the same window. The differentiator is gradient rate: the mean final pre-onset probability is 1.000 for steep/fast ramps but 0.598 (LO slow) and 0.717 (cal slow). Trajectory features (differences, slopes, CUSUM) key on rate of change, so a slow ramp's signal is buried in same-window benign variation.
- Decision: Classify the slow-ramp limitation as an operating boundary attributable to **rate-of-change sensitivity**, and preserve it as a quantified limit rather than tuning it away. The simulator is NOT modified to make slow ramps predictable.
- Why: Distinguishing an amplitude limit from a gradient-rate limit determines the correct remedy (multi-scale features / longer history) versus an unfixable observability wall. The evidence supports the former but shows the benefit is not free.
- Alternatives considered: Lengthening the history window to catch slow ramps — deferred; it changes the frozen feature set and must be validated against the clean-condition regression criterion before acceptance. Modifying the ramp simulator — rejected outright (would manufacture predictability).
- Consequences: Slow ramps remain a documented operating boundary; the boundary is quantified (final pre-onset p ~0.6-0.7 vs ~1.0 for fast ramps).
- Files: docs/reliability-research-report.md, scripts/evaluate_reliability.py

### D-047: The conventional threshold detector has no usable operating point on G1 benign

- Date / workstream / commit: 2026-10-11 / Benchmark integrity / uncommitted
- Context: All prior "forecast vs conventional" comparisons used a conventional threshold detector calibrated on Phase-4 **benign train** via `calibrate_thresholds`, then reported it as a baseline.
- Observed symptom: On G1 benign scenarios the conventional detector fires on **29/30** scenarios with the train calibration and **30/30** with a validation calibration — a 97–100% false-alarm rate. It also "detects" every `intercept_resend` attack with leads of 1200+ blocks despite that attack having no precursor.
- Verified root cause: **A persistence/threshold mismatch, not an inverted logic.** Per-block indicator violation rates on G1 benign are low (excess_noise 0.05%, lo_power 0.45%, skr_estimate 0.40%, background 0.05%). But `detect_warnings` only requires **K=3 consecutive** violating blocks, and the thresholds are calibrated as per-block quantiles on a *different* benign distribution (Phase-4 val, 19 scenarios). Over a 2000-block scenario, even a 0.4% per-block rate makes a 3-run of consecutive violations near-certain — so the detector fires on 30/30 G1 benign scenarios while never violating persistently within any one scenario. Two additional contributors: (i) `lo_power` and `skr_estimate` are direction=-1 indicators whose benign spread is extremely narrow (`lo_power` std ≈ 5e-4), so a small mean shift between benign distributions moves them across a fixed absolute threshold; (ii) `saturation_frac` falls back to a fixed threshold with zero benign variance.
- Decision: Record this as a **negative result about the baseline, not about the forecaster**. The prior matched-budget comparison is declared INVALID (the conventional detector had no usable operating point to match against). No operating point, ROC or gain number from those comparisons may be cited as evidence.
- Why: Master prompt §20 forbids presenting an artificially weak conventional detector. A 100%-false-alarm detector is not a weak detector — it is an absent one. Any future matched-budget comparison must first establish that the conventional baseline has a non-degenerate operating point (e.g. per-scenario relative thresholds or CUSUM on normalized statistics) on held-out benign data.
- Alternatives considered: Loosening the threshold until FWR is acceptable — rejected: it would be tuned on evaluation data. CUSUM/CPD on normalized deviations — deferred as the correct replacement baseline, to be built and validated before any comparative claim.
- Consequences: The forecasting system's advantage over conventional detection is currently **UNESTABLISHED**, not established. This supersedes the Phase 2/4/5 framing of a "forecast-vs-conventional gain" and is carried into the final gate (LIMITED OPERATING ENVELOPE).
- Files: docs/reliability-research-report.md, docs/reliability-evaluation-protocol.md

### D-048: Pin the logistic solver for cross-process reproducibility

- Date / workstream / commit: 2026-10-11 / Reproducibility / uncommitted
- Context: Phase 5 Test I claimed "Deterministic execution verified". Re-running `scripts/evaluate_reliability.py` produced materially different numbers.
- Observed symptom: Two consecutive runs of the identical pipeline gave clean-condition AUROC 0.895907 vs 0.895328, and noise-condition AUROC differing by up to **1.7e-2**; `lo_manipulation` horizon-valid rate flipped between 5/10 and 6/10. The stored `reliability_report.json` from the two runs differed in every section.
- Verified root cause: `fit_horizon_model` used scikit-learn's default `lbfgs` solver. On this problem (`class_weight='balanced'`, ~2.8% positive rate, 189 features, ~230k rows) it converges slowly through multi-threaded BLAS reductions whose summation order varies between processes, so the fitted coefficients were not reproducible. In-process repeated fits were bit-identical (confirming it was thread/reduction non-determinism, not an unseeded RNG), but `coef.sum()` varied 11.01 / 12.30 / 11.24 across three separate processes.
- Decision: Pin `solver="liblinear"` in `fit_horizon_model`. This preserves `C`, `class_weight`, `max_iter`, `random_state` and the train-only scaler exactly; only the optimizer changes.
- Why: A research system that cannot reproduce its own headline metric is not reproducible regardless of what a report claims. The residual `liblinear` convergence tolerance (~5e-6 AUROC spread over 5 cross-process runs) is inherent and immaterial.
- Alternatives considered: (a) Pinning BLAS thread counts via environment variables — rejected as insufficient: thread count is ambient configuration that a future run may not set, and even at a fixed thread count lbfgs reduction order is not guaranteed. (b) Recording the observed spread as an accepted tolerance — rejected: 1.7e-2 on AUROC is large enough to change reported rates. (c) Switching model family — rejected as out of scope.
- Consequences: Cross-process AUROC spread fell from ~1.7e-2 to **5.5e-6** (≈3000x tighter); coefficient-sum spread fell from ~1.3 to 3.9e-4. Clean G1 H=100 AUROC is now stably **0.8968** (previously reported as 0.896 / 0.901 depending on run). All 189 tests pass unchanged.
- Bug-fix metadata — Observed symptom: non-reproducible metrics across runs of the same command. Verified root cause: thread-order-dependent `lbfgs` reductions. Regression test: `tests/test_statistics.py::test_logistic_fit_is_stable_across_thread_counts`, `::test_logistic_fit_is_reproducible_within_process`.
- Files: src/quantumattack/baselines/logistic.py, tests/test_statistics.py, docs/reliability-research-report.md

### D-049: Causal warning emission -- alert time is persistence satisfaction, not run start

- Date / workstream / commit: 2026-10-12 / Causal warning repair / uncommitted
- Context: An independent source audit of `src/quantumattack/baselines/warnings.py` found `warning_blocks_for_scenario` returned `t_idx[i - persistence_k + 1]` (the first block of the qualifying run) as the warning firing time, even though the persistence condition is only satisfied at index `i`.
- Observed symptom: For K=3 with p=[0.1,0.1,0.1,0.9,0.9,0.9,...], the reported warning time was block 3 although the third qualifying observation only arrived at block 5. Every lead time in the evaluation pipeline was inflated by K-1 blocks.
- Verified root cause: The function conflated "excursion start" with "alert emission". At block `i-K+1` the system has not yet observed the remaining K-1 samples, so it cannot have emitted the warning. No call site distinguished the two timestamps.
- Decision: Introduce the canonical `WarningEvent` model (scenario, horizon, event id, excursion-start, persistence-satisfied, emission, config hash) and the ONLINE generator `warning_events_for_scenario` which emits at `t_idx[i] + processing_delay_blocks`. `warning_blocks_for_scenario` now returns EMISSION blocks. The excursion start is recorded as separate metadata and is never used as the warning time. Retrospective retention moved to `retrospective_sustained_retention`.
- WHY: The operational activation time must be the point when all required evidence became available; a warning that had not yet been substantiated cannot have been emitted.
- HOW: `warning_events_for_scenario` scans the probability series causally; on the K-th consecutive above-threshold sample it records excursion_start=t_idx[i-K+1], persistence_satisfied=t_idx[i], emission=t_idx[i]+delay, then applies cooldown from the emission block.
- WHEN: Evaluation and operational-state feeding, after per-block forecast inference, before retrospective attribution.
- Alternatives considered: (a) Keeping the old timestamp and documenting it as "run start" -- rejected: the field is consumed as the warning time by lead-time and horizon attribution. (b) Adding a separate parallel function and leaving the old one unchanged -- rejected: call sites would silently keep the backdated timestamp; the repair must be in the shared path.
- Consequences: All G1/G2/G4 lead times shorten by exactly K-1 = 2 blocks (0.02 s). The operational state machine (`operational_states.py`) already emitted at the persistence-satisfied block, so both online paths now agree (acceptance test A). Tests that encoded the backdating were corrected: `tests/test_baselines.py::test_warning_persistence_required`, `::test_warning_cooldown_suppresses_rearm`, `tests/test_metric_integrity.py::test_warning_emission_time_is_when_persistence_is_satisfied`.
- Regression tests: `tests/test_causal_warning_semantics.py::test_acceptance_a_activation_is_persistence_satisfied_not_run_start` and the K=1..4 / interrupted / missing-telemetry / delay / backdating-mutation variants.
- Files: src/quantumattack/baselines/warnings.py, tests/test_causal_warning_semantics.py, tests/test_baselines.py, tests/test_metric_integrity.py

### D-050: Attack confirmation requires independent evidence, not forecast probability

- Date / workstream / commit: 2026-10-12 / Confirmation semantics / uncommitted
- Context: `operational_states.py` entered `ACTIVE_ATTACK_CONFIRMED` after `confirm_persistence` consecutive blocks with forecast probability >= `confirm_probability`. No independent evidence of an active attack was required.
- Observed symptom: Sustained high P(attack within H) -- a statement about possible FUTURE onset -- produced the state "active attack confirmed", even on benign scenarios whose probabilities drift high.
- Verified root cause: The confirmation transition consumed only the forecast score. A forecast probability is not proof that an attack is currently occurring.
- Decision: Add a `confirmation_evidence` boolean mask parameter (per block) and `confirmation_evidence_persistence` policy field. With the default `require_confirmation_evidence=True`, `ACTIVE_ATTACK_CONFIRMED` requires `confirmation_evidence_persistence` consecutive evidence blocks. Absent evidence, a sustained high probability yields `PRE_ATTACK_WARNING` with an explicit "unconfirmed" reason. The legacy behaviour is retained only behind `require_confirmation_evidence=False` for reproduction.
- WHY: Prediction and confirmation are different security claims; conflating them produces false "active attack" states.
- HOW: The state machine tracks `evidence_run` (consecutive True mask blocks); `can_confirm = evidence_run >= persistence` (default). Evidence-driven confirmation also fires without any prior forecast warning, so sudden attacks remain confirmable after onset (requirement 10.3).
- WHEN: Online state transition evaluation, per block, after forecast scoring and after the (future) conventional detector produces evidence.
- Alternatives considered: (a) Dropping `ACTIVE_ATTACK_CONFIRMED` entirely -- rejected: active-attack confirmation is a required operational capability; it just needs valid evidence. (b) Reusing `warn_run` with a higher threshold -- rejected: that is still forecast-only.
- Consequences: The reliability evaluation supplies no evidence (no validated detector exists -- D-047) and therefore reports zero confirmations, correctly. Evidence-driven confirmation is tested with controlled masks in `tests/test_causal_warning_semantics.py` (positive, negative, all-False, sudden-attack, legacy-opt-in).
- Regression tests: `tests/test_operational_states.py::test_sustained_high_probability_warns_but_does_not_confirm_alone`, `::test_independent_evidence_confirms_active_attack`, `tests/test_causal_warning_semantics.py` acceptance test C (5 cases).
- Files: src/quantumattack/operational_states.py, tests/test_operational_states.py, tests/test_causal_warning_semantics.py

### D-051: False-alert burden accounted from emitted episodes and state occupancy

- Date / workstream / commit: 2026-10-12 / Event accounting / uncommitted
- Context: `scripts/evaluate_reliability.py` computed `false_alarm_episodes_per_1000_simulated_seconds` from the number of affected SCENARIOS, and `warning_load_fraction` from the first-to-last firing span (`max(fires) - min(fires) + 1`). The independent audit found both quantities do not measure what their names state.
- Observed symptom: A scenario with two separate alerts counted as one episode; warning occupancy included the quiet interval between alerts.
- Verified root cause: No canonical episode representation existed; the evaluator counted scenario-level flags and marker spans instead of emitted alert episodes and per-block state occupancy.
- Decision: Add `AlertEpisode`, `alert_episodes_from_trace`, and `summarize_alert_burden` to `operational_states.py`. Episodes are entered when the state machine enters an alarm state and closed when it returns to a non-alert state (sticky alarms are not fragmented by repeated threshold crossings). The evaluator reports, per partition and benign class: `n_alert_episodes`, `episodes_per_1000_simulated_seconds` (from episodes), `occupancy_fraction` (from per-block states), `median_episode_seconds`, plus a machine-readable `alert_event_ledger.json` and `scenario_ledger.json`. Output renamed to `reliability_report_v2.json` so the v1 artifact is preserved unchanged.
- WHY: Scenario counts, threshold crossings, and alert episodes are three different quantities; conflating them misstates the operational false-alarm burden.
- HOW: `alert_episodes_from_trace` scans the state timeline; `summarize_alert_burden` aggregates open/closed episodes, occupancy, and rates from those intervals.
- WHEN: Retrospective evaluation over recorded operational states (offline), after the online timeline is fixed.
- Alternatives considered: Counting `warning_events_for_scenario` emissions as episodes -- rejected: the bare policy re-arms after cooldown during sustained probability, while the documented sticky state machine does not; acceptance test D designates the state machine as authoritative.
- Consequences: v2 metrics differ from v1 by construction; v1 is retained with a superseded label. Acceptance test D verifies 2 scenarios / 3 episodes / rate from 3 / occupancy from intervals.
- Regression tests: `tests/test_causal_warning_semantics.py` acceptance test D (4 cases), `tests/test_operational_states.py` episode extraction.
- Files: src/quantumattack/operational_states.py, scripts/evaluate_reliability.py, tests/test_causal_warning_semantics.py

### D-052: Causal sequential (CUSUM) conventional detector with a calibrated operating point

- Date / workstream / commit: 2026-10-12 / Conventional detector implementation / uncommitted
- Context: D-047 established that the fixed-threshold conventional detector has no usable operating point (100% benign false alarms). The repair specification requires an actually implemented, causally correct conventional baseline with a validated false-alert budget.
- WHAT: `src/quantumattack/baselines/conventional.py` gains a causal sequential detector: per-indicator one-sided CUSUM over per-scenario warmup-normalized residuals, Huber-capped deviates, persistence, cooldown, documented missing-data handling, and joint (k, h) calibration on held-out validation benign data to a declared scenario-level false-alert budget.
- WHY: A threshold detector with per-block quantiles and 3-block persistence has near-certain false alarms over 2000-block scenarios (per-block violation ~0.4%, D-047). A sequential test accumulates evidence and has a calibratable operating point. A GLOBAL reference normalization was measured to fail (benign per-scenario baseline offsets accumulate: h=30 still gave 100% FPR); per-scenario CAUSAL warmup normalization fixes this because each scenario is compared against its own established baseline.
- HOW: `CusumConfig` (k_drift, h_threshold, persistence_k, cooldown_blocks, warmup_blocks, max_missing_run, deviate_cap, normalization); `cusum_statistic` computes S_t = max over indicators of max(0, S_{t-1} + clip(z_t)-k); `detect_warnings_cusum` emits at the block where persistence completes (same causal rule as D-049); `calibrate_cusum_threshold` scans k ascending and h ascending and returns the first pair whose validation-benign scenario FPR meets the budget, recording the achieved FPR.
- WHEN: online monitoring per telemetry block; calibration offline on Phase-4 validation benign only. The first `warmup_blocks` blocks produce no detector output (startup contract).
- Measured calibration: k=2.0, h=200.0 selected on 19 validation benign scenarios -> achieved scenario FPR 5.3% (budget <= 10%). Benign sustained |mean z| envelope measured at <= 5 sigma (100-block windows); attack shifts measured at 16 sigma (calibration det_gain), 33 sigma (intercept transmittance), 832 sigma (LO), 964 sigma (jamming) - the operating point sits above the benign drift envelope and below the attack shifts.
- Measured behaviour (frozen partitions, emission timestamps, k=3 persistence): G1 benign FPR 0/30, attack detection 30/30, median lead +15 blocks (0.15 s), 16/30 pre-onset; G2 40/40 detected; G3 extreme-stress benign FPR 3/30 (10%) - the honest false-alarm cost of extreme environmental stress; G4 30/30 detected, median lead 47.5 blocks.
- Failure modes documented: benign slow environmental drift above the calibrated envelope can accumulate (G3 10% FPR); an attack active during the warmup window contaminates the per-scenario baseline (silent-failure mode, tested); prolonged missing telemetry resets the accumulator (cold start).
- Alternatives considered: (a) global-reference CUSUM - rejected by measurement (see above). (b) two-sided CUSUM - not applicable: attack indicators shift one-directionally by contract (INDICATOR_DIRECTION). (c) adaptive EWMA baseline - deferred: would absorb slow attack ramps at the same rate as benign drift, trading away exactly the signal under test.
- Consequences: a genuine non-degenerate conventional baseline now exists; the forecast-vs-conventional comparison is repaired (D-053). The detector is NOT claimed to be better than the forecaster; the comparison is reported honestly with matched budgets where reachable.
- Regression tests: `tests/test_conventional_detector.py` (17 tests: constant/noisy benign, sustained shift detection, transient non-accumulation with cap control, warmup unusable, missing telemetry, invalid values, determinism, prefix invariance, scenario-state isolation, cooldown suppression + spacing, calibration budget compliance, two real end-to-end simulator scenarios).
- Files: src/quantumattack/baselines/conventional.py, tests/test_conventional_detector.py, scripts/evaluate_conventional_detector.py

### D-053: Fair forecast-vs-conventional comparison; the operational forecasting claim is not supported

- Date / workstream / commit: 2026-10-12 / Benchmark repair / uncommitted
- Context: D-047 invalidated the old conventional baseline; D-049..D-051 corrected the warning semantics. The comparison had to be rebuilt on operational (emission-based, look-ahead-free) semantics for both systems.
- WHAT: `scripts/evaluate_conventional_detector.py` evaluates the calibrated CUSUM detector and the frozen forecaster on the SAME populations, onsets and time base, with emission timestamps for both and mutually exclusive per-event outcomes. It also sweeps the forecaster threshold to find a matched false-alert budget. Outputs `artifacts/reliability/evaluation/conventional_comparison.json`.
- Measured results (160 scenarios: 100 attacks, 60 benign; G1-G4):
  * CUSUM detector at its validation-calibrated point (k=2.0, h=200; val FPR 5.3%): benign FPR **5.0% [1.7%, 13.7%]**, sensitivity 100%, pre-onset detection 51%, median lead **7.5 blocks (0.075 s)**; outcome split 51 pre-onset / 2 at-onset / 47 post-onset. G1 alone: 0% benign FPR [0%, 11.4%], 16/30 pre-onset, median lead 15 blocks. G3 extreme-stress benign: 10% FPR.
  * Frozen forecaster (P>=0.5, K=3): benign FPR **51.7% [39.3%, 63.8%]**, horizon-valid (H=100) first alarms **1.0% (1/100)**; median first-emission lead 916 blocks (9.16 s) -- i.e. the first alarm is almost always far outside the declared horizon. G1: 63.3% benign FPR, 0/30 horizon-valid, median lead 908 blocks.
  * Matched-budget sweep (G1): the forecaster cannot reach the detector's budget anywhere in the tested range. FPR falls 63% -> 50% -> 40% -> 37% -> 20% across P>=0.5/0.7/0.8/0.9/0.95 while sensitivity falls 100% -> 97% -> 93% -> 77% -> 67% and horizon-valid rises 0% -> 6.7% -> 16.7% -> 33% -> 30%. No threshold combination approaches the detector's 0% G1 FPR with useful horizon-validity.
- Decision: Report the comparison as measured and record that (a) a defensible non-degenerate conventional baseline now exists (Gate E satisfied), (b) the frozen forecasting operating point is not operationally viable once look-ahead selection is removed, and (c) NO matched-budget superiority of forecasting over conventional detection is established on this evaluation population. Every prior "forecast gain vs conventional" number (Phase 2/4/5 reports) is invalidated: they combined the degenerate baseline with retention-selected warning times.
- WHY: The project's central claim was advance warning relative to conventional detection. With both artifacts removed, the measurement shows the opposite ordering on this population: the detector achieves comparable sensitivity with an order of magnitude lower false-alert burden, while the forecaster's within-horizon rate is ~1% at the frozen threshold. Honest reporting requires stating this.
- Alternatives considered: (a) reporting only the high-threshold (P>=0.9) forecaster line (33% horizon-valid, 37% FPR) -- rejected as cherry-picking an unviable operating point; the sweep is reported in full. (b) declaring the comparison inconclusive and withholding numbers -- rejected: both systems were measured under identical, documented conditions; the result is informative even though it is negative for the forecaster.
- Consequences: Scientific gate downgraded to **WEAK SIGNAL** for the operational-forecasting claim: the learned representation retains real discrimination (AUROC 0.897; time-only 0.518), but it does not convert into horizon-valid operational warnings at any tested, defensible false-alert budget. The conventional-detector gate (E) passes; the comparative gate (F) resolves as "forecaster not superior, detector viable".
- Regression tests: `tests/test_causal_warning_semantics.py` (always-alert/never-alert sanity cases), `tests/test_conventional_detector.py` (operating-point behaviour), benchmark script itself reports all denominators and Wilson intervals.
- Files: scripts/evaluate_conventional_detector.py, artifacts/reliability/evaluation/conventional_comparison.json, docs/reliability-research-report.md

### D-054: Independent validation and untouched confirmatory evaluation

- Date / workstream / commit: 2026-10-12 / Scientific validation / uncommitted
- Context: The validation mandate required (a) auditing the repaired pipeline and detector for shortcuts, (b) a production source for confirmation evidence, and (c) a pre-registered evaluation on genuinely untouched scenarios. G1-G4 were declared exposed and could not support a confirmatory claim.
- WHAT:
  1. **Confirmation-evidence production path** (`conventional.confirmation_evidence_from_cusum`): the operational state machine's `ACTIVE_ATTACK_CONFIRMED` evidence now comes from the calibrated sequential detector's threshold excursions computed on causal telemetry (previously the mask existed only as a test parameter - disclosed integration gap). Verified: warmup-gated, onset-blind, suppressed by missing/invalid telemetry; ten regression tests (`tests/test_confirmation_evidence.py`), including a real-simulator check that evidence never precedes `precursor_start`.
  2. **Frozen confirmatory protocol** (`docs/confirmatory-evaluation-protocol.md`): committed BEFORE any confirmatory scenario was generated. Frozen: model config, forecast policy, detector operating point (k=2.0, h=200.0), seed block, populations, metrics, Wilson intervals, negative controls, no-retuning rule.
  3. **Confirmatory execution** (`scripts/evaluate_confirmatory.py`, `scripts/analyze_confirmatory.py`): 148 scenarios on seeds 41000-42999 (stride 7), verified disjoint from all 439 historical seeds; immutable hash-recorded outputs under `artifacts/confirmatory/<stamp>/`.
  4. **Adversarial leakage controls** (measured, not asserted): metadata-blind and label-permutation invariance of detector statistics (bit-identical); cross-scenario state isolation; warmup-contamination probe; benign-vs-attack statistic envelope.
- MEASURED CONFIRMATORY RESULTS (untouched seeds; Wilson 95%):
  - Forecaster: horizon-valid H=100 **0/88 (0.000)** on every attack group; benign FWR 60.0% [42.3%, 75.4%] (C1_NORMAL), 43.3% [27.4%, 60.8%] (C3); ALL first-emission median lead 887 blocks (8.87 s) - far outside the declared horizon. `intercept_resend`: 0% pre-onset (correct physics preserved).
  - Detector: benign FWR 6.7% [2.6%, 15.9%] ALL (C1_NORMAL 3.3% [0.6%, 16.7%]; C3 extreme stress 10.0% [3.5%, 25.6%]); sensitivity 100% (88/88); pre-onset detection 55.7% (49/88), median pre-onset lead 96 blocks (0.96 s).
  - **Lifecycle finding: 0 detector alerts preceded `precursor_start`** across all 88 attacks (earliest pre-onset emission 763 blocks before onset, still after the first modeled adversarial mechanism). The detector performs early malicious-activity detection DURING attacker preparation - NOT prediction before any hostile action.
  - **Confirmation split: 88/88 attacks confirmed; 4/60 benign confirmed (6.7%)** - the confirmation state inherits the detector's false-alert rate by construction (C1_NORMAL 1, C3 3).
  - Negative control on untouched data: time-only AUROC **0.525** vs model AUROC **0.880** (30 C1 attacks) - onsets are not trivially scheduled; discrimination is telemetry-driven.
- LEAKAGE-CONTROL FINDINGS (Phase-5 exposed data):
  - Detector statistics are bit-identical under label stripping and label permutation; no cross-scenario state contamination.
  - **Benign-envelope overlap (C4 control):** the frozen h=200 sits at the benign max-statistic p95 (189.7); benign scenarios reach max-S up to 487 (emissions avoided only by the 3-consecutive-block persistence); **45/100 attacks show no pre-onset statistic above the benign p95**. Pre-onset detection covers only the ramp subset; separation is real but modest.
  - **Warmup contamination (synthetic probe on real telemetry):** weak attacks (8-10 sigma calibration shifts) are **completely masked** under contamination (0 warnings vs 18-22 clean); the strongest family (LO, ~832 sigma) remains detectable (baseline re-anchors). G1-G4 contain no onset < 200 so this mode was invisible in historical evaluations.
- WHY these matter: the confirmatory experiment independently reproduces the v2 operational finding (0% horizon-valid; high benign burden) on untouched seeds, removing the possibility that the earlier correction was itself an artifact of the exposed partitions. The lifecycle finding prevents relabeling precursor detection as pre-attack prediction.
- Alternatives considered: treating G1-G4 re-evaluation as confirmation - rejected (exposed); upgrading the gate based on detector sensitivity 100% - rejected (sensitivity at 100% is dominated by post-onset detections and inherits a 6.7% benign confirmation rate).
- Consequences: **Scientific gate remains `WEAK SIGNAL`** for forecasting; the conventional detector is validated as an early-malicious-activity / active-attack detector with a measured false-alert budget; the forecasting-vs-detector comparison on untouched data is directionally identical to the exposed-data result (detector dominates at reachable budgets; no forecaster superiority).
- Known new limitation: the confirmatory groups reuse the same scenario DEFINITIONS as G1-G4 (only seeds are new); parameter-combination novelty is therefore partial, disclosed in the protocol.
- Regression tests: `tests/test_confirmation_evidence.py` (10), full suite 255 passed.
- Files: src/quantumattack/baselines/conventional.py, scripts/evaluate_confirmatory.py, scripts/analyze_confirmatory.py, docs/confirmatory-evaluation-protocol.md, tests/test_confirmation_evidence.py, artifacts/confirmatory/<stamp>/

### D-055: Publication safety audit and reproducible release packaging

- Date / workstream / commit: 2026-10-12 / Release preparation / 889c460, ba335fb, 0d7f56c
- Context: The repository had never been published and had no remote. It also had NO README, no dependency manifest, no packaging metadata and no CI, while carrying specific scientific claims (D-049..D-054) that a reader must be able to check. Publication therefore required proving that no credentials leak from files or history, that a third party can run the documented workflow from a fresh clone, and that the reported numbers are stated with their uncertainties and limitations.
- WHAT:
  1. **Credential audit** (tracked content AND full reachable history): 120 tracked files and 187 unique blobs across 21 commits scanned for GitHub tokens (`ghp_`, `github_pat_`), AWS access-key IDs, PEM private-key headers, bearer tokens, `password=`/`secret=`/`api_key=` assignments and Slack webhook URLs. Result: 0 hits in the working tree, 0 hits anywhere in reachable history - no compromised-credential condition, push not blocked. Seven tracked files contain the authoring-machine path `C:\Projects\Quantumattack` (provenance lines in the Phase-0 audit and later reports, plus one docstring in `tests/test_statistics.py`); reviewed and retained - a filesystem path is not a credential, and rewriting historical evidence documents would be cosmetic churn.
  2. **Artifact classification and exclusions**: `data/` (Phase 3: 160 scenarios, Phase 4: 234, Phase 5: 160; Parquet telemetry, 64 columns per scenario) and `artifacts/` (feature matrices, evaluation JSON, evidence bundles, confirmatory runs) remain git-ignored. No tracked file exceeds 94 KB, so nothing large is published. Regeneration commands, inputs, seeds and output locations are documented in the README rather than shipping the data.
  3. **Reproducible dependency and packaging configuration**: `requirements.txt` (numpy, pandas, scikit-learn, pyarrow, PyYAML - derived from an AST scan of `src/quantumattack`, not assumed), `requirements-dev.txt` (adds pytest and scipy; PyTorch deliberately excluded because it is lazily imported by the optional GRU/TCN comparators), and `pyproject.toml` (setuptools, `src` layout, `requires-python >=3.11`). Verified on the local checkout: full suite **255 passed in 117.09 s**.
  4. **Project README** (`README.md`): architecture diagram, subsystem map, the threshold/persistence/emission/episode/attribution taxonomy, verified technology stack, supported scenarios, PowerShell + bash quick start, simulation and evaluation commands, reproducibility notes, the scientific-status table (gate `WEAK SIGNAL`) with Wilson intervals, an explicit limitations section and the research-integrity statement. Every number is taken from D-049..D-054 or from an executed command; no badge, license, citation, award or test count is claimed that was not measured.
  5. **CI** (`.github/workflows/ci.yml`): installs the package plus dev requirements, runs the dataset-independent test subset (194 tests) on Python 3.11 and 3.13, and ends with an end-to-end CLI smoke test that generates a two-scenario dataset and asserts the manifest invariants (`block_ms == 10.0`). The exclusion list (5 modules, 4 individual tests) was derived empirically: the full suite was run in a fresh clone without datasets and every failing/erroring test was recorded, rather than guessed from module names.
  6. **Fresh-clone verification**: cloned the repository into an empty directory outside the working tree, created a virtual environment, installed `-e .` and `requirements-dev.txt`, ran the full suite to enumerate dataset-dependent failures, then ran the documented quick-start commands verbatim. Final result on the clean clone: dataset-independent subset **194 passed / 4 deselected**; `simulator.generate` on `configs/simulation/phase1.yaml` exported **65 scenarios** (2,000 blocks each) in 16 s; `features_cli` exported **65 feature files of 218 columns**. Three defects were found and fixed this way: a 6th dataset-dependent test (`test_conventional_detector_integrity.py::test_normalized_sigma_threshold_differs_from_absolute_quantile`) that the first exclusion list missed; `pyproject.toml` declaring version 1.0.0 while the package reports 0.1.0 (now single-sourced from `quantumattack.__version__`); and README dependency versions and dataset counts that did not match a real run.
- WHY: A public research repository is judged on whether its claims can be independently re-derived. Every historical claim in this project had to be withdrawn or downgraded at least once (D-040, D-047, D-049, D-053); publishing without a credential audit, a runnable environment and an honest limitations section would repeat that failure at the distribution level.
- Alternatives considered: (a) publishing `data/` so results are byte-verifiable - rejected: it is large, regenerable and deterministic, and a multi-GB diff makes review harder rather than easier. (b) `git init` plus one clean commit to drop the invalidated history - rejected: the withdrawal trail D-040..D-054 IS the scientific evidence and must stay public. (c) Full-suite CI that regenerates every dataset (~30-60 min per phase) - rejected as too slow for a per-push gate; the subset plus the CLI smoke covers packaging and logic regressions. (d) adding an OSI license to make the repo formally reusable - see D-056.
- Consequences: The public repository is self-describing and runnable within minutes on a clean machine, with research datasets regenerable rather than shipped. The dataset-dependent tests are only runnable on a machine that has regenerated `data/`; this is stated in the README rather than hidden.
- Publication record: pushed non-force to `https://github.com/PrathamKapoor/Quantum-Attack-Detector` (branch `main`) with the full 22-commit history preserved. Post-push verification: `origin/main` SHA equals local HEAD, ahead/behind 0/0, README and all referenced documents served, credential scan still clean. The GitHub Actions CI triggered by the push completed **green on both Python 3.11 and 3.13** (dataset-independent suite + CLI smoke test) — the first execution of this code outside the authoring machine.
- Files: .gitignore, README.md, SECURITY.md, pyproject.toml, requirements.txt, requirements-dev.txt, .github/workflows/ci.yml

### D-056: License status is deliberately left unresolved

- Date / workstream / commit: 2026-10-12 / Release preparation / ba335fb
- Context: The repository contained no license file. Publication makes the question unavoidable: without a license, default copyright applies and no third party may legally reuse the code.
- Decision: Publish WITHOUT inventing a license. `pyproject.toml` declares `license = { text = "Proprietary" }` (accurate: all rights reserved) and the README states the status explicitly, recording that selecting an OSI license remains a pending author decision.
- WHY: Choosing MIT/Apache/GPL on the author's behalf would grant permissions the author never expressed - an irreversible act performed in the author's name. The accurate status is "publicly viewable, not licensed", and it is carried into `handoff.md` as open publication work.
- Alternatives considered: (a) add MIT by default - rejected (grants rights that were not granted). (b) stay silent and let the README imply permissiveness - rejected (silence is misleading to downstream users). (c) publish privately until a license is chosen - rejected: the purpose of publication is research review, which requires visibility, not redistribution rights.
- Consequences: Reviewers can read, clone and run the code; reuse, modification or redistribution requires the author's permission. Resolving this is the first open item for the next release cycle.

### D-057: Project licensed under Apache License 2.0

- Date / workstream / commit: 2026-10-12 / Licensing / parent commit 99b9c55 ("docs: record publication and CI verification facts")
- Context: D-055 published the repository with an explicitly unresolved license status and D-056 recorded that no license had been granted, so the code shipped all-rights-reserved. That state was provisional: it was chosen to avoid granting reuse rights the copyright holder had not authorized, not because reuse was refused. The copyright holder has now authorized distribution of the original work under the Apache License, Version 2.0 (SPDX `Apache-2.0`), including its express patent grant and notice requirements.
- WHAT: The original project code and documentation are licensed under Apache-2.0, with the license expressed in machine-readable packaging metadata.
- WHY: Apache-2.0 is a recognised permissive licence that permits reuse, modification and redistribution while imposing explicit conditions (copy of the licence, change notices, retention of attribution, and an express patent grant with a patent-termination clause). That matches a research project intended to be read, reviewed and built upon without imposing copyleft obligations on downstream work.
- HOW:
  1. `LICENSE` at the repository root: the complete, unmodified official Apache-2.0 text downloaded from `https://www.apache.org/licenses/LICENSE-2.0.txt`, byte-identical (11,358 bytes, SHA-256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`), including all nine clauses, `END OF TERMS AND CONDITIONS` and the appendix.
  2. `NOTICE` at the repository root: records the project copyright and states the factual attribution position of this distribution. Created because Apache-2.0 clause 4(d) makes a NOTICE file the vehicle for attribution that downstream redistributors must carry; its content is limited to established facts.
  3. `pyproject.toml`: migrated to PEP 639 metadata - `license = "Apache-2.0"`, `license-files = ["LICENSE", "NOTICE"]`, and `requires = ["setuptools>=77.0.0"]` (the first setuptools release supporting PEP 639 expressions). The deprecated `license = { text = ... }` table form was removed. No proprietary-licence classifier existed, so none was removed or added; the SPDX expression is the authoritative declaration.
  4. `README.md`: the License section rewritten to the Apache-2.0 grant, an Apache-2.0 badge added at the header, and an explicit statement retained that licensing does not change the scientific status (synthetic-only, not hardware-validated, not certified for live QKD deployment).
  5. `handoff.md`: current license status updated.
- WHEN: The licence takes effect from the published revision that carries these files. Commits before it were published under the all-rights-reserved status recorded in D-056 and are deliberately left unchanged, so the repository history continues to show the earlier state accurately. No existing commit was rewritten.
- ATTRIBUTION CONSIDERATIONS: The tracked tree was inspected before relicensing. It contains only first-party Python source, YAML configurations and Markdown documentation; there are no vendored libraries, no external datasets, no images or figures, no third-party copyright headers and no existing licence files. Duplicated-module and blockquote scans returned nothing third-party. The only external URLs in the repository point at this repository itself. `docs/research-landscape.md` cites literature bibliographically (authors, titles, arXiv identifiers, journal references) without reproducing third-party text. Third-party Python dependencies are installed from their own distributions and retain their own licences; selecting Apache-2.0 for this project does not relicense them. Copyright is recorded as `PrathamKapoor`, the identity already established by the repository authorship and commit history - no legal personal name was invented.
- Alternatives considered: (a) Leaving the project unlicensed and asking users to open an issue for permission - rejected: it blocks legitimate reuse and is what the authorisation was given to end. (b) Choosing MIT or BSD instead of Apache-2.0 - rejected: the express patent grant and patent-termination clause are the reason the owner selected Apache-2.0. (c) GPL-style copyleft - rejected: it would impose obligations on derived research code that the owner did not authorise. (d) Adding licence headers to all 60+ source files - rejected as unnecessary mass-editing; Apache-2.0 does not require per-file headers, and the task forbids gratuitous source churn. (e) Omitting `NOTICE` entirely - rejected: the project has a single verified copyright holder and no third-party material, which is exactly the fact a NOTICE is designed to convey; it also keeps clause 4(d) attribution meaningful for redistributors.
- Consequences: The project is reusable, modifiable and redistributable under Apache-2.0, including commercially, subject to the licence conditions. Warranty and liability remain disclaimed as in the licence text. The scientific conclusions are unchanged by this decision - the gate remains `WEAK SIGNAL`, the simulator remains `SYNTHETIC ONLY`, and the graph gate remains `HOLD`. Anyone who relied on the earlier all-rights-reserved state should note the change is prospective from this revision.
- Verification commands actually executed (all exit 0):
  * `python -m pytest --collect-only -q` - 255 tests collected.
  * `python -m pytest tests/ -q -ra` - 255 passed, no skips.
  * `python -m pytest tests/ -q -ra --ignore=tests/test_phase4_dataset.py --ignore=tests/test_phase5_dataset.py --ignore=tests/test_data_integrity.py --ignore=tests/test_features.py --ignore=tests/test_temporal.py --deselect ...` - 194 passed (the CI subset, unchanged).
  * `python -m build` - sdist `quantumattack-0.1.0.tar.gz` and wheel `quantumattack-0.1.0-py3-none-any.whl` built; wheel metadata `Metadata-Version: 2.4`, `License-Expression: Apache-2.0`, `License-File: LICENSE`, `License-File: NOTICE`; both licence files embedded under `quantumattack-0.1.0.dist-info/licenses/` with the LICENSE hash unchanged; sdist contains LICENSE and NOTICE plus `PKG-INFO` with `License-Expression: Apache-2.0`.
  * Clean-venv wheel install and import - `quantumattack.__version__ == 0.1.0`, installed metadata reports `License-Expression: Apache-2.0`.
  * `git diff --check` - clean; build outputs (`dist/`, `src/quantumattack.egg-info/`) confirmed git-ignored and never staged.
- Files: LICENSE (new), NOTICE (new), pyproject.toml, README.md, handoff.md, decisions.md
