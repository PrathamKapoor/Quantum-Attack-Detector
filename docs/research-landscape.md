# Research Landscape

Created 2026-10-07. Coverage: **non-exhaustive, snippet-level**. Every row comes from web
searches executed on 2026-10-07 (queries listed at bottom). Where a snippet does not answer
a column, the cell says UNKNOWN. Per decisions.md D-006, full texts are to be read in
Phase 1 before the architecture is frozen, and this file is updated then.

## Sources found (searched, not yet read in full)

| # | Paper / Repository | Year | System | Attack types | Features | Dataset | Model | Prediction vs detection | Unknown attacks | Temporal modeling | Graph modeling | QML | Hardware validation | Limitations | What we reuse | What we improve |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Ding et al., "Machine-learning-based detection for quantum hacking", Phys. Rev. A 107, 062422 (link.aps.org/doi/10.1103/PhysRevA.107.062422) | 2023 | UNKNOWN (QKD system) | "most quantum hacking attacks" per snippet (specific list UNKNOWN) | UNKNOWN | simulation (per snippet) | MADS — ML-based detection system (details UNKNOWN) | detection (per snippet; also "revise overestimated secret key rates") | UNKNOWN | UNKNOWN | UNKNOWN | no (classical ML per snippet) | UNKNOWN | UNKNOWN | multi-attack ML detection framing; SKR-revision idea | prediction-before-onset; lead-time metrics |
| 2 | Review: "Machine Learning Techniques for Enhancing Quantum [Key Distribution]" (arxiv.org/html/2603.07384v1) | 2026 (per listing) | QKD (review) | n/a (review) | n/a | n/a | review of 5 ML application domains incl. parameter optimization (others UNKNOWN) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | partially (review scope UNKNOWN) | n/a | UNKNOWN | domain map for Phase 1 reading list | our predictive (pre-onset) focus |
| 3 | Mao et al., "Hidden-Markov-model-based calibration-attack recognition for [CV-QKD]", Phys. Rev. A 101, 062320 (link.aps.org/doi/10.1103/PhysRevA.101.062320) | 2020 | CV-QKD | calibration attack | quadrature values (per snippet) | UNKNOWN | Hidden Markov Model | recognition/detection (temporal HMM) | UNKNOWN | yes (HMM = temporal) | no | no | UNKNOWN | UNKNOWN | precedent for temporal modeling of CV-QKD quadratures; calibration-attack physics | learned trajectory model vs fixed HMM; multi-horizon prediction |
| 4 | "Attack detection scheme for continuous variable quantum [key distribution]" (inspirehep.net/literature/2807166) | UNKNOWN | CV-QKD | UNKNOWN | UNKNOWN | UNKNOWN | GNN-based; "models data as a graph structure using three [something]" (snippet truncated) | detection | UNKNOWN | UNKNOWN | yes | no | UNKNOWN | UNKNOWN | GNN-on-CV-QKD precedent; closest known neighbor to our graph stage | temporal GNN + prediction residuals + lead-time evaluation |
| 5 | "Optimizing Quantum Key Distribution Network Performance [with] GNN" (arxiv.org/abs/2511.16468) | 2025 (per listing) | QKD networks | n/a (optimization, not attacks — per snippet) | UNKNOWN | UNKNOWN | GNN | no (performance optimization) | n/a | UNKNOWN | yes | no | UNKNOWN | not attack detection | GNN-for-QKD-networks context | attack-focused graph modeling |
| 6 | Decker et al., "Quantum key distribution as a [use case for] quantum machine learning", npj Quantum Information s41534-025-01088-9 (nature.com) | 2025 | QKD (general) | UNKNOWN | UNKNOWN | UNKNOWN | QML algorithms (specifics UNKNOWN) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | yes | UNKNOWN | UNKNOWN | QML-for-QKD precedent; Phase 10 reading | scientific QML-vs-classical benchmark with cost accounting |
| 7 | Pirandola et al., "Composable security for continuous variable quantum key distribution", Phys. Rev. Research 3, 043014 | 2021 | CV-QKD | n/a (security analysis) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | security-model grounding for the twin's SKR computations | n/a (we do not claim new security proofs) |
| 8 | Hajomer et al., "Long-distance continuous-variable quantum key distribution over [distance]" (orbit.dtu.dk) | 2024 | CV-QKD (experiment) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | experimental (optical link) | n/a | realistic CV-QKD parameter ranges for the twin | simulated environment (explicitly labeled) |
| 9 | Baliuka et al., "Deep-learning-based radio-frequency side-channel attack on [QKD]", Phys. Rev. Applied 20, 054040 | 2023 | QKD hardware | RF side-channel attack (offense) | UNKNOWN | captured RF data | deep learning (attack tool) | attack (not defense) | n/a | UNKNOWN | no | no | hardware (per context) | offense-oriented | reminder that attacks can be ML-driven; threat-model depth | defensive early-warning focus |
| 10 | "Beyond universal attack detection for continuous-variable QKD via deep learning" (researchgate.net/publication/359804812) | UNKNOWN | CV-QKD | UNKNOWN (snippet mixes in wavelength-attack text; attribution unclear) | UNKNOWN | UNKNOWN | deep learning | detection | UNKNOWN | UNKNOWN | UNKNOWN | no | UNKNOWN | UNKNOWN | title-level relevance only | UNKNOWN — must read |
| 11 | Dahlberg et al., "A simulator of a quantum internet [SeQueNC]" (arxiv.org/abs/1712.08032) | 2017 | quantum network stack | n/a (simulator) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | software | general-purpose, not attack-focused | simulator architecture ideas; discrete-event concepts | CV-QKD physics-first twin with attack injection |
| 12 | NetSQUID — "NETwork Simulator for QUantum Information using Discrete events" (netsquid.org; via search snippets) | UNKNOWN | quantum networks | n/a (simulator) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | software | heavyweight for our scope; Windows support UNKNOWN | discrete-event simulation concepts | lightweight numpy/scipy CV-QKD twin sufficient for telemetry research |

## Explicit gaps (to fill in Phase 1 by reading full texts)

- UNKNOWN: precise attack lists, feature sets, datasets, and results of sources 1, 2, 4, 6, 10.
- UNKNOWN: any prior work doing *pre-onset prediction with lead-time metrics* on CV-QKD telemetry — none of the snippets above claims it; we have NOT verified absence.
- UNKNOWN: GNN-for-QKD-attack-detection details (source 4) — critical to differentiate our graph stage.
- Non-exhaustive: additional searches needed (decoy-state attacks, trojan-horse, detector-blinding ML detection, open-set/OOD on time series, QKD simulators beyond the two above).

## Search queries used (2026-10-07)

1. "machine learning attack detection quantum key distribution QKD intercept-resend detector blinding"
2. "CV-QKD continuous-variable quantum key distribution attack detection neural network machine learning"
3. "graph neural network quantum key distribution security attack detection"
4. "quantum network simulator QKD open source NetSQUID SeQueNC QuTiP discrete-event"
