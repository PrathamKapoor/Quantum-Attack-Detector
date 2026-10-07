# Phase 0 — Repository Audit (2026-10-07)

Scope: full audit of `C:\Projects\Quantumattack` before any implementation. Method: direct
filesystem inspection (`Get-ChildItem -Force`), git inspection, and Python environment probes.
Every statement below is backed by an executed check on 2026-10-07 unless marked UNKNOWN.

## 1. Repository state — OBSERVED

| Check | Command/result |
|---|---|
| Directory exists | `Test-Path` → True |
| Entries (incl. hidden) | `Get-ChildItem -Force` count → **0** |
| Git repository | `git status` → `fatal: not a git repository` |
| decisions.md / flow.md / handoff.md | Did not exist before this commit (directory was empty) |
| Prior architecture / code / tests / data | None — the "friend's previous architecture" referenced by the master prompt is **not present** in this workspace. Nothing to preserve, nothing to contradict. |

Conclusion: **greenfield project**. All requirements in the master prompt map to
"missing" rather than "partially implemented".

## 2. Categorization (master prompt §52 STEP 6)

| Category | Findings |
|---|---|
| Already implemented | None (empty repository) |
| Partially implemented | None |
| Missing | Everything: simulator, telemetry, features, datasets, models, evaluation, API, dashboard, tests, docs, reproducibility scripts |
| Broken | Nothing to break |
| Unknown | See §4 |

## 3. Environment audit — OBSERVED (executed probes)

Runtime: Python 3.13.12 (pip 25.3), OS Windows x64 (10.0.26200).

| Package | Status | Version (if installed) |
|---|---|---|
| numpy | installed | 2.5.3 |
| scipy | installed | 1.18.1 |
| pandas | installed | 3.0.5 |
| matplotlib | installed | 3.11.2 |
| qiskit | installed | 2.5.2 |
| qiskit-aer | present (import spec found) | exact version not yet printed |
| scikit-learn | **missing** | — |
| torch | **missing** | — |
| networkx | **missing** | — |
| xgboost | **missing** | — |
| fastapi | **missing** | — |

Implications:
- Physics simulation (CV-QKD Gaussian-channel model, decoy-state statistics) is feasible now with numpy/scipy.
- Classical ML baselines (logistic regression, random forest, one-class SVM, isolation forest) require scikit-learn.
- Temporal/graph models require torch (+ a graph library) and networkx.
- Benchmark ladder requires xgboost. API requires fastapi (later phase).
- Python 3.13 wheel compatibility for torch/xgboost must be verified at install time (dependency rule §45), not assumed.
- QML (Phase 10) can be prototyped with qiskit + Aer (quantum kernels / VQC via shots simulation); dedicated QML frameworks are not installed. UNKNOWN — requires verification when Phase 10 approaches.

## 4. Explicit UNKNOWN list

1. UNKNOWN — which machine (user laptop vs CI vs lab machine) will run training; affects dependency install location.
2. UNKNOWN — qiskit-aer exact version (import spec confirmed, version not printed).
3. UNKNOWN — whether the hackathon requires a specific Python version; 3.13 is what the local toolchain provides.
4. UNKNOWN — target prediction horizons in seconds/windows (master prompt §7: derive from simulation design; deferred to Phase 1/5).
5. UNKNOWN — full text of research-landscape sources; current entries are search-snippet-level (see docs/research-landscape.md).
6. UNKNOWN — whether a Git remote exists/will be provided for this project.

## 5. Risks

| Risk | Mitigation |
|---|---|
| "Precursor" data design accidentally teaches "gradual buildup ⇒ attack" for every attack | Master prompt §9: mix sudden-onset attacks; documented per-attack precursor taxonomy in Phase 1 |
| Temporal leakage in predictive labels | Mandatory leakage test (§32) before any model result is reported |
| Scope explosion (17 attack types × 12 models × 4 horizons) | Prioritized attack plan + benchmark ladder; QML strictly after classical baselines |
| Dependency churn on Python 3.13 | Install per-phase, verify imports, record decision entries |

## 6. Audit verdict

The repository was empty; the project starts from zero. Phase 0's only deliverables are
documentation (this file, decisions.md, flow.md, handoff.md, docs/*). No code was changed,
consistent with the master prompt's Phase 0 rule ("No unnecessary code changes").
