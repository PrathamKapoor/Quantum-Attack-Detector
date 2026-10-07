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
