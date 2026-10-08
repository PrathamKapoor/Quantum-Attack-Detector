# Research Landscape

Updated 2026-10-08 (Phase 1). Coverage: 20 sources, all re-verified 2026-10-08 by
reading full texts or publisher/INSPIRE/Crossref records (evidence level per row).
Supersedes the 2026-10-07 snippet-level version (D-006 obligation fulfilled).
Every row states: evidence level — VERIFIED FROM SOURCE (full text or authoritative
record read this phase), SECONDARY (snippet only), PROJECT INFERENCE, or UNKNOWN.
No bibliographic metadata is fabricated; UNKNOWN is stated explicitly.

## THE GAP (why this project exists)

**No prior work performing pre-onset prediction, forecasting, or lead-time-quantified
early warning for QKD attacks was found** across ~16 targeted queries (pre-onset,
early warning, lead time, forecasting, time-to-detection, "predict attack before").
Absence reported as a key finding; we have NOT proven nonexistence, but the closest
20 sources are all reactive/contemporaneous detectors, optimizers, or attacks.
The closest neighbors: Mao et al. 2020 (temporal HMM, no lead time), Isha et al. 2026
+ Gupta 2026 (temporal FEATURES but post-onset window scoring), Mohamed & Al-Kuwari
2026 (temporal LSTM/TCN detectors gating key distillation, explicitly reactive),
Al-Mohammed survey 2026 (confirms parameter prediction exists, attack-onset
prediction does not).

## Source table

| # | Source | Year | System | Attacks | Telemetry/features | Dataset | Model | Predictive vs detection | Unknown attacks | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Chao** Ding, Wang, Wang, Wu, Sun, Mao — "Machine-learning-based detection for quantum hacking attacks on continuous-variable-QKD systems", Phys. Rev. A 107, 062422 (first author Chao Ding, Hunan Univ.; NOT Song-Yan Ding, per INSPIRE/OpenAlex verification) | 2023 | CV-QKD | abstract: "most quantum hacking attacks" (list not enumerated); per SECONDARY survey Table V: LO-intensity, calibration, saturation, wavelength, blinding, hybrids (CA+SA, CA+LO) | attack-related feature vectors (exact list UNKNOWN — full text paywalled, NO arXiv mirror exists) | simulation (per abstract) | MADS: DBSCAN noise/outlier removal + multiclass SVM; predicted labels immediately gate final key generation | detection/gating; revises overestimated SKR; 99.96% per SECONDARY survey | UNKNOWN | VERIFIED (abstract + metadata) |
| 2 | Al-Kuwari et al. — "Machine Learning Techniques for Enhancing Quantum Key Distribution", arXiv:2603.07384 | 2026 | survey: DV/CV/MDI/TF-QKD | CV attacks covered: calibration, LO-intensity, saturation, wavelength, blinding, channel amplification, DoS, hybrids, unknown; DV: MITM, eavesdropping, Trojan-horse | quadratures, LO power, noise/shot-noise variances, electronic noise, block T, QBER series | mostly simulation, some experimental | maps 5 ML domains: parameter optimization, attack detection, protocol selection, key-metrics prediction, network mgmt | attack detection = REACTIVE; "predictive" = SKR/QBER/FKL prediction only; NO pre-onset attack prediction anywhere | surveys claims: GAN+AD, one-class SVM, GIN ~85% partial-unknown | VERIFIED (full text) |
| 3 | Mao, Wang, Huang, Qin, Huang, Guo — "Hidden-Markov-model-based calibration-attack recognition for CV-QKD", Phys. Rev. A 101, 062320 | 2020 | CV-QKD (receiver quadratures, homodyne) | calibration attack (+ environmental disturbance, imperfect devices as hidden states); mechanism (via sibling He et al. 2026, VERIFIED): Eve tampers shot-noise calibration so Bob adopts N0_cal = α·N0, rescaling measured variance and corrupting ε̂ evaluation (original proposal: Jouguet et al., PRA 87, 062313, 2013) | processed quadrature values (observation sequence; discretization UNKNOWN) | UNKNOWN (simulation per context) | HMM (interferences as hidden states) | contemporaneous recognition; NO lead-time; precision 98.735% @50% attack ratio, 25 km; FPR 1.28%, FNR 0.08% | no (calibration only) | VERIFIED (abstract + metadata; mechanism via verified sibling text) |
| 4 | Jin, Jiang, Guo, Hu, Huang — "Attack detection scheme for CV-QKD based on a graph neural network", J. Opt. Soc. Am. B 41(6), 1355 | 2024 | CV-QKD (coherent states) | FIVE attacks verified from Table 2: calibration, LO fluctuation, wavelength, saturation, blind | measured features verified (Table 2): mean ȳ, variance V_y, shot-noise unit N0, LO intensity I_LO + per-attack effect matrix (calibration: V_y+N0; LO: V_y+N0+I_LO; wavelength: V_y+I_LO; saturation/blind: ȳ+V_y); data V_A∈{2,4,6}, 30/50/70 km | UNKNOWN (simulated or experimental; data not public — verified Data Availability) | GNN (GIN per SECONDARY: 3 graph constructions, 97.8/86.4/98.8%) + anomaly detection | detection only; transfer across scenarios without retraining (>95%) | 85% partially-unknown | VERIFIED (abstract + Optica tables) |
| 5 | Anchan, Acharya, Thungon — "Optimizing QKD Network Performance using GNN", arXiv:2511.16468 | 2025 | BB84 QKD networks | NONE (link-establishment prediction; graph robustness only) | node: position/degree/betweenness; edge: loss, QBER, entanglement prob | custom simulation (multivariate-normal topologies, Poisson BB84) | TransformerConv→GATv2Conv→MLP | optimization only | n/a | VERIFIED (full text) |
| 6 | Decker, Gallezot, Kerstan, Paesano, Ginter, Wormsbecher — "Quantum key distribution as a quantum machine learning task", npj QI 11, 140 | 2025 | BB84 | attack CONSTRUCTION: PCCM (F_AB=F_AE≈0.853), imbalanced cloner (basis-asymmetric noise), collective attack w/ Cascade parity leakage (P_E=89.4%) | n/a (circuit fidelities) | numerical (PennyLane mixed-state) | QCL, 2-qubit HEA | neither — offense | n/a | VERIFIED (full text) |
| 7 | Pirandola et al. — "Composable security for CV-QKD", Phys. Rev. Research 3, 043014 | 2021 | CV-QKD | n/a (security analysis) | n/a | n/a | n/a | n/a | n/a | VERIFIED (metadata; unchanged from Phase 0) |
| 8 | Hajomer, Derkach, Jain, Chin, Andersen, Gehring — "Long-distance CV-QKD over 100 km fiber with local LO", Science Advances 10(1), eadi9474 | 2024 | GMCS CV-QKD, heterodyne, LLO | n/a (experiment; Trojan mitigated by Faraday isolator) | excess-noise decomposition ξ_RIN+ξ_mod+ξ_quant+ξ_Ram+ξ_RPN, transmittance η/τ, UKF phase estimates, β, FER | experimental: 100 km, 0.146 dB/km, 100 MBaud, 1e7 samples/frame | UKF carrier recovery + MD reconciliation (MET-LDPC) | DSP-predictive only (phase) | none | VERIFIED (full text) — REALISTIC PARAMETERS: η=0.028, τ=0.68, ξ=0.212 mSNU, V_mod=8.41 SNU, SKR=25.4 kbit/s, δ_fail=1e-10 |
| 9 | Baliuka et al. — "Deep-learning-based RF side-channel attack on QKD", Phys. Rev. Applied 20, 054040 | 2023 | QKD hardware | RF side-channel (offense) | captured RF data | captured RF | deep learning (attack tool) | offense | n/a | VERIFIED (metadata; unchanged) |
| 10 | Luo, Zhang, Qin, Sun, Huang, Wang, Wu, Guo, Huang — "Beyond universal attack detection for CV-QKD via deep learning", Phys. Rev. A 105, 042411 | 2022 | CV-QKD | known + potential/unseen; families: calibration, LO intensity, saturation, wavelength | threshold-based features from universal statistical model | UNKNOWN + proof-of-principle experiment | semisupervised DL | detection (post-onset) | claimed via anomaly detection | VERIFIED (abstract + metadata) |
| 11 | Dahlberg et al. — SeQueNC quantum internet simulator, arXiv:1712.08032 | 2017 | quantum network stack | n/a | n/a | n/a | n/a | n/a | n/a | VERIFIED (metadata; unchanged) |
| 12 | NetSQUID (netsquid.org) | — | quantum networks | n/a | n/a | n/a | n/a | n/a | n/a | SECONDARY (unchanged) |
| 13 | Isha, Singh, Kumar, Pal, Hambarde, Shukla — "Beyond the QBER Threshold: Temporal QBER ML for Multi-Attack Detection in BB84", arXiv:2608.04047 | 2026 | BB84 | 7 eavesdropping attacks + normal | 63 physics-informed temporal QBER features (burst, instability, asymmetry, QBER-loss) | simulation | RF, XGBoost, SVM-RBF + SHAP | window-level detection; NO lead-time | no | VERIFIED (full text) |
| 14 | Gupta — "Physics-Aware Temporal Feature Engineering for Eavesdropping Detection in BBM92", IACR eprint 2026/1282 | 2026 | BBM92, FSO | sub-threshold eavesdropping bursts camouflaged by atmospheric variation | 24 features / 30-s sliding window: QBER, Bell S, coincidences + cross-correlations | simulated FSO, 24 h, 5 seeds | XGBoost + SHAP | post-onset sliding-window detection | no | VERIFIED (full text) |
| 15 | Al-Kuwari, Mohamed, Al-Kuwari, Farouk, Behera — "Resisting QKD Attacks Using QML", arXiv:2509.14282 / IET Quantum Comm | 2025 | decoy-BB84 (PennyLane) | intercept-resend, PNS, Trojan-horse, blinding, wavelength-TH, combined | QBER, measurement entropy, signal/decoy loss, time metrics | simulation | hybrid QLSTM vs LSTM/CNN/ANN/RNN/RF | temporal classification; no forecasting | no | VERIFIED (full text) |
| 16 | Mohamed, Al-Kuwari — "Adversarial Learning Game for Intrusion Detection in QKD", arXiv:2603.03502 | 2026 | decoy-QKD (high-fidelity simulation) | adaptive adversary over time-shift/blinding/PNS/TH under hardware-feasibility bands | block telemetry: decoy residuals, timing-histogram moments, detector imbalances | simulation | minimax defender: one-class + LSTM/TCN, hard-negative mining; loss tied to finite-key secret fraction | explicitly reactive alarm-gated key distillation | adaptive adversary eval | VERIFIED (full text) |
| 17 | Liu, Huang, Su, Peng, Huang — "Deep Anomaly Detection for Active Attacks on the Receiver in QKD", arXiv:2508.12749 | 2025 | prepare-and-measure (receiver side) | active receiver attacks (attack-agnostic) | operational-state data | UNKNOWN (from operational states) | one-class ML | detection; potentially unknown attacks | one-class = open-set | VERIFIED (abstract + metadata) |
| 18 | Pereira, Pezelj, Prawits, Hübbel — "Experimental demonstration of a coherent detector blinding attack on a real CV-QKD system", arXiv:2605.03572 | 2026 | CV-QKD (real system) | coherent detector blinding; hides >2.5 SNU excess noise from parameter estimation | excess noise (SNU), parameter-estimation residuals | experimental | n/a (offense + countermeasures) | offense | n/a | VERIFIED (full text) |
| 19 | Qi, Fung, Lo, Ma — "Time-shift attack in practical quantum cryptosystems", arXiv:quant-ph/0512080 | 2005 | BB84-class, time-multiplexed SPD | time-shift (detector efficiency mismatch) | detection timing/arrival distributions | n/a (theory) | n/a (offense) | offense; full key info without errors in principle | n/a | VERIFIED (full text) |
| 20 | Gungor, Rios, Ahuja, Rosing — "TS-OOD: Evaluating Time-Series OOD Detection", arXiv:2502.15901 | 2025 | n/a (ML methodology) | n/a | multivariate time series | benchmarks | OOD survey/benchmark | detection methodology | OOD focus | VERIFIED (full text) |

Additional verified sources (2026-10-08 searches; same evidence discipline):

| # | Source | Year | System | Attacks | Key facts | Evidence |
|---|---|---|---|---|---|---|
| 21 | Du, Huang — "Multi-Attack Detection: General Defense Strategy Based on NNs for CV-QKD", Photonics 9(3), 177 | 2022 | CV-QKD | coexisting multi-attack (multi-label); unknown via OC-SVM | BR-NN/LP-NN + one-class SVM; 98.7–99.8% unknown (per QLSTM table, SECONDARY) | VERIFIED (Crossref abstract) |
| 22 | Dai, Huang, Zhang — "Low-Rate DoS Attack Detection: Spectral Estimation for CV-QKD", Photonics 9(6), 365 | 2022 | CV-QKD | low-rate DoS on transmittance T | Bartlett PSD of T time series; LDoS = high low-frequency PSD | VERIFIED (Crossref abstract) |
| 23 | Al-Mohammed, Al-Ali — "From Provable to Practical: survey of classical & ML defenses for DV/CV QKD", arXiv:2605.27497 | 2026 | DV+CV survey | 9 problem classes P1–P9 | parameter prediction exists; attack-ONSET prediction does not; proposes SKR-impact/latency/robustness benchmarking | VERIFIED (full text) |
| 24 | He, Xiao, Lyu — "Hybrid Quantum–Classical NN for quantum hacking detection in CV-QKD", Applied Sciences 16(6), 2793 | 2026 | CV-QKD | LOIA, calibration, saturation, hybrid, none (5-class) | CNN + VQC; 93% 5-class; raw pulse signals | VERIFIED (INSPIRE abstract) |
| 25 | Liu et al. — "Dynamically quantum attack detection based on deep representations", Sci. China Inf. Sci. 69, 192503 | 2026 | CV-QKD | 4 known + 2 unseen | self-updating feature DB, no retraining; 100%/99% | VERIFIED (INSPIRE abstract) |
| 26 | Sharath, Vrindavanam — "Unsupervised ML Anomaly Detection for BB84 (OC-SVM, iForest, Ex-iForest)", IEEE ICICDS 2026 | 2026 | BB84 | intercept-resend + 6 channel noises | QBER/polarization/counts/jitter features; Ex-iForest 95% | VERIFIED (INSPIRE abstract) |
| 27 | Lejeune, Damanet — "Deep-learning-based continuous attacks on QKD protocols", arXiv:2408.12571 | 2024 | BB84 | DL continuous attack (offense) | weak continuous measurement + recurrent nets; between I-R and optimal individual | VERIFIED (full text) |

## What we reuse / what we improve (per source, condensed)

- **S1 (Ding MADS)**: feature-extract→classify→gate-key-generation pipeline is the detection
  baseline we extend backwards in time; SKR-revision metric reused. Improve: pre-onset
  prediction, lead time. (Authorship verified: Chao Ding, Hunan Univ.; no arXiv mirror exists.)
- **S2 (ML survey)**: five-domain taxonomy backbone; gap evidence (no pre-onset attack
  prediction). Improve: the missing 6th domain — attack forecasting.
- **S3 (Mao HMM)**: precedent for temporal modeling of CV quadratures; fixed HMM is the
  baseline to beat; precision/FPR/FNR @50% attack ratio, 25 km = baseline operating points.
  Calibration-attack mechanism verified via sibling text (He et al. 2026): tampered
  N0_cal = α·N0 rescales measured variance — exactly the ε̂-bias mechanism of our P0
  attacks #2/#3 (original proposal: Jouguet et al., PRA 87, 062313, 2013). Improve:
  learned multi-horizon prediction with lead time.
- **S4 (Jin GNN)**: GNN-on-CV-QKD precedent; attack→feature effect matrix (ȳ, V_y, N0,
  I_LO per attack — Table 2, verified) directly grounds our attack-injection signatures;
  differentiate on lead-time/pre-onset, not accuracy; cross-scenario-without-retraining
  evaluation standard reused.
- **S5 (Anchan GNN)**: node/edge feature semantics; no attack modeling (supports gap).
- **S6 (Decker QML)**: explicit quantum attack circuits (PCCM, imbalanced cloner) as
  potential injection modules; QML-vs-classical benchmark discipline.
- **S8 (Hajomer)**: PRIMARY parameter anchor for the simulator (η=0.028, ξ≈0.2 mSNU,
  V_mod≈8.4 SNU, 100 MBaud, 10 ms frames, β≈0.92, SKR≈25 kbit/s @100 km, δ_fail=1e-10).
- **S10 (Luo)**: experimental CV attack families (calibration, LO, saturation, wavelength)
  calibrate attack-injection physics; threshold-features-uncorrelated claim motivates
  richer temporal features.
- **S13 (Isha)**: 63-feature physics-informed temporal taxonomy template; FNR-vs-threshold
  comparison frame (threshold FNR 0.85 vs learned 0.02) = the conventional baseline our
  early-warning metrics must beat.
- **S14 (Gupta)**: cross-observable decoupling (QBER vs Bell-S vs coincidences) transfers to
  cross-metric decoupling (QBER-proxy vs ε̂ vs SNR vs LO) in CV; validates
  simulated-telemetry methodology (5 seeds).
- **S16 (Mohamed adversarial game)**: closest combination of physics-constrained telemetry +
  temporal detectors + adaptive adversary; finite-key-based loss and hardware-feasibility
  attack bands parameterize injection; explicitly reactive → differentiates our lead-time focus.
- **S18 (Pereira blinding)**: real-CV-QKD blinding hides >2.5 SNU excess noise — the
  hidden-excess-noise signature our early-warning model must catch before SKR collapse.
- **S19 (Qi time-shift)**: canonical timing-attack physics (P2 for us; BB84-family).
- **S20 (TS-OOD)**: SOTA OOD underperforms on multivariate time series → justifies
  physics-informed temporal features; evaluation protocol for OOD experiments.
- **S22 (Dai LDoS)**: spectral (PSD) features of transmittance — reusable telemetry channel;
  LDoS as a candidate attack family (P2).
- **S23 (survey)**: P1–P9 taxonomy + benchmarking metrics scaffolding; confirms the gap.

## Explicit gaps this project addresses

1. **Pre-onset attack prediction with lead-time metrics on QKD telemetry — NO prior work
   found** (primary gap; S2, S13, S16, S23 all confirm).
2. Per-attack precursor taxonomy (which attacks have observable pre-onset structure) —
   not established anywhere in the sources above.
3. Matched-counterfactual simulation (attack vs same-seed benign run) for isolating
   attack-specific signal from environmental drift — not found in any source.
4. Mixture of sudden-onset and gradual-onset attacks to prevent the
   "instability ⇒ attack" shortcut — S13/S16 include normal/noisy conditions but no
   explicit onset-mixture design.

## Honest unknowns

- Full texts not retrieved this phase: S1 (Ding 2023 — abstract+metadata only; no arXiv
  mirror exists, verified via INSPIRE/OpenAlex/arXiv-API searches), S3 (Mao 2020 —
  abstract+metadata; no arXiv mirror, no standalone INSPIRE record), S4 (Jin 2024 —
  abstract + Optica tables; full text paywalled), S10 (Luo 2022 — abstract+metadata),
  S17 (Liu 2025 — abstract+metadata). Their feature details beyond abstracts remain
  UNKNOWN.
- We have NOT proven that no pre-onset-prediction paper exists anywhere (absence of
  evidence across our queries only).
- Precursor behaviors in `docs/precursor-taxonomy.md` are PROJECT INFERENCE (labeled
  there); no source describes measured pre-onset attacker telemetry.

## Search queries used (2026-10-07 Phase 0: 4 queries listed in git history; 2026-10-08: ~16 queries)

Pre-onset/early-warning/lead-time/forecasting variants for QKD attacks · PNS/Trojan/
blinding/time-shift/intercept-resend + ML detection · GNN CV-QKD (INSPIRE 2807166) ·
QKD simulator landscape · TS-OOD time-series anomaly detection · "beyond universal
attack detection" attribution · temporal QBER BB84 · adversarial QKD intrusion game.
