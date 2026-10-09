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
