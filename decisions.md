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
