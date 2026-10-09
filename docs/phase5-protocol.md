# Phase 5 Protocol — Independent Generalization, Simulator Validity & Forecasting Robustness

Version: `phase5-protocol v1`  
Date: 2026-10-09  
Status: **PRE-REGISTERED** (Frozen prior to Phase 5 test evaluation)  
Target Commit: `bfcfcaf` (Base)

---

## 1. Primary Research Question & Formal Hypotheses

> **Question**: Does the attack-specific early-warning signal established in Phase 4 generalize across unseen scenario trajectories, attack intensities, environmental noise profiles, and attack mechanisms?

We investigate five distinct, non-conflated forms of generalization:

- **H1 (G1 — Scenario Generalization)**: The model maintains pre-onset early warning on independent scenario seeds and trajectories drawn from the nominal operating envelope ($H=100$ warning rate $\ge 0.70$ on gradual attacks, $FWR(\text{BENIGN\_DRIFT}) \le 0.05$).
- **H2 (G2 — Parameter Generalization)**: The model maintains predictive capability under parameter extrapolation: unseen ramp durations (short $20\text{--}40$ blk, extended $150\text{--}250$ blk), altered onset schedules ($600\text{--}1600$), and varying actuator drift magnitudes.
- **H3 (G3 — Environmental Generalization)**: Benign environmental shifts outside the training distribution (elevated fiber loss wander $\sigma_{\text{loss}}=0.06$ dB, high thermal coupling, frequent disturbance episodes $p=0.8$) do not induce catastrophic false warnings ($FWR \le 0.30$).
- **H4 (G4 — Attack Generalization)**: The model detects hybrid attack variants (e.g. combined multi-probe trains, multi-stage jamming) while maintaining the physically grounded zero pre-onset warning on sudden intercept-resend attacks.
- **H5 (G5 — Simulator Validity & Boundaries)**: The digital twin's physical assumptions, approximations, and limits are rigorously classified into established mechanisms, literature models, engineering approximations, and project inferences.

---

## 2. Experimental Partitions & Seed Design

To prevent data contamination, all scenario generation seeds are drawn from disjoint arithmetic progressions (stride 7) strictly non-overlapping with prior phases (Phases 1–4 used seeds $< 15,000$):

```text
TRAIN POOL (Phase 4 Retained): 1000 + i*7  (120 seeds, Phase 4 train)
VAL POOL   (Phase 4 Retained): 5000 + i*7  (42 seeds, Phase 4 val)

PHASE 5 GENERALIZATION EVALUATION PARTITIONS:
G1 POOL (Scenario Generalization):     20,000 + i*7, i=0..59  → 20000..20413 (60 scenarios)
G2 POOL (Parameter Extrapolation):     25,000 + i*7, i=0..39  → 25000..25273 (40 scenarios)
G3 POOL (Environmental Stress / Drift): 30,000 + i*7, i=0..29  → 30000..30203 (30 scenarios)
G4 POOL (Attack Stress / Hybrid):      35,000 + i*7, i=0..29  → 35000..35203 (30 scenarios)
```

| Partition | Purpose | Scenarios | Families Covered | Seed Range |
|---|---|---:|---|---|
| **G1 (Scenario)** | Independent test set on nominal envelope | 60 | plain (10), drift (10), dist (10), IR (10), LO (10), Cal (10) | 20000..20413 |
| **G2 (Parameter)** | Short/long ramps, steep drifts, varied onsets | 40 | LO short/long ramps (14), Cal steep/slow biases (14), IR varied taps (12) | 25000..25273 |
| **G3 (Environment)** | Severe fiber wander, thermal spikes, disturbances | 30 | extreme drift (10), intense disturbance (10), thermal stress (10) | 30000..30203 |
| **G4 (Attack/OOD)** | Hybrid probe pulses, multi-stage jamming | 30 | hybrid probes (15), sudden jamming (15) | 35000..35203 |
| **TOTAL** | — | **160** | Unpaired, fully disjoint | — |

---

## 3. Parameter Ranges & Stress Distributions

### G1: Nominal Parameter Ranges (Interpolation Benchmark)
- Onset: $U[900, 1400]$ blocks.
- LO manipulation: attenuation $U[0.3, 0.7]$, ramp $U[40, 160]$ blocks.
- Calibration manipulation: gain bias $U[0.05, 0.25]$, ramp $U[50, 180]$ blocks.
- Intercept-resend: tap fraction $U[0.2, 0.5]$.
- Environmental drift: fiber loss OU $\sigma=0.03$ dB, disturbance prob $0.5$.

### G2: Parameter Extrapolation Ranges (Stress Benchmark)
- **Fast Ramps (Short Precursor)**: ramp duration $U[20, 40]$ blocks (0.2–0.4 s lead window).
- **Slow Ramps (Extended Precursor)**: ramp duration $U[160, 260]$ blocks (1.6–2.6 s lead window).
- **Steep Bias**: calibration gain bias $U[0.25, 0.45]$ (near detector linearity limit).
- **Onset Jitter**: onset $U[500, 800]$ (early onset) and $U[1500, 1800]$ (late onset).

### G3: Environmental Stress Ranges (Hard Negative Benchmark)
- **Extreme Fiber Loss Drift**: OU $\sigma=0.06$ dB/block (2× Phase 4 rate).
- **High-Frequency Benign Disturbances**: episode prob $p=0.8$, duration 40 blocks, background spike multiplier $16\times$.
- **Thermal Coupling Stress**: temperature amplitude $2.5^\circ\text{C}$, LO thermal coupling $0.025/\text{K}$.

### G4: Attack Variant Stress Ranges
- **Dense Hybrid Probing**: probe $\lambda = 5.0$, precursor lead 160 blocks.
- **Sparse Probing**: probe $\lambda = 0.5$, precursor lead 60 blocks.
- **High-Power Jamming**: jamming power $1.2$ SNU (extreme saturation).

---

## 4. Models & Evaluators

Two primary model evaluations will be performed:
1. **Frozen Phase 4 Baseline Model**: Trained strictly on Phase 4 training data (fit scaler, $C=1.0$, balanced weights, feature group D), evaluated directly on Phase 5 partitions G1–G4 without any retraining. Tests true zero-shot out-of-distribution robustness.
2. **Phase 5 Retrained Model**: Logistic model retrained on expanded training partitions to establish the retrained performance ceiling under broader distributions.
3. **Conventional Threshold Baseline**: Evaluated using identical threshold calibration rules ($q=0.995$ on benign train).
4. **Complexity Gate Check**: GRU/TCN evaluated only if logistic regression exhibits catastrophic non-linear failure.

---

## 5. Frozen Feature Schema & Warning Policy

- **Feature Schema**: Schema v2 (154 causal derived features) per `docs/feature-freeze-v1.md`.
- **Forecast vs Confirmation Integrity**: Post-onset features (`qber_proxy`, `p_attack_present`, SKR collapse) are strictly barred from forecast model inputs.
- **Warning Policy (Frozen)**:
  ```python
  WarningPolicy(
      prob_threshold=0.5,
      persistence_k=3,
      cooldown_blocks=50,
      grace_blocks=5,
      sustained_until_onset=True,
  )
  ```

---

## 6. Primary and Secondary Endpoints

### Primary Endpoints:
1. **Attributed Lead Time**: $t_{\text{onset}} - t_{\text{warning}}$ for anticipatory warnings (blocks & seconds).
2. **Early-Warning Success Rate**: Proportion of attack scenarios receiving valid pre-onset warning.
3. **False Early-Warning Rate (FWR)**: Measured separately for NORMAL, BENIGN_DRIFT, and G3 Environmental Stress.
4. **Forecast Gain**: Difference in warning time between forecast model and conventional detector ($t_{\text{conv}} - t_{\text{forecast}}$).
5. **AUPRC & AUROC**: Probabilistic discrimination across horizons $H \in \{10, 25, 50, 100\}$.

### Secondary Endpoints:
- Brier score and Expected Calibration Error (ECE).
- Detection delay after onset for sudden attacks.
- Robustness degradation curves under noise and parameter shifts.

---

## 7. Statistical Methodology & Acceptance Criteria

- **Unit of Independence**: The **scenario trajectory**.
- **Bootstrap Method**: Scenario bootstrap ($B=2000$ resamples with replacement, seed 2026) yielding 95% percentile confidence intervals.
- **Acceptance Thresholds for Scientific Gate**:
  - `ROBUST GENERALIZATION`: Gradual attack warning rate $\ge 0.70$ (95% CI lower bound $\ge 0.50$) across G1, G2, and G3; $FWR(\text{BENIGN\_DRIFT}) \le 0.15$; positive forecast gain over conventional detector.
  - `ATTACK-SPECIFIC GENERALIZATION`: The above holds for specific gradual families, sudden attacks remain $0\%$ pre-onset (correct physics), and G3 environmental stress maintains $FWR \le 0.30$.
  - `LIMITED GENERALIZATION`: Signal holds on G1 (unseen seeds) but degrades substantially under G2 (parameter extrapolation) or G3 (environmental stress).
  - `WEAK SIGNAL`: Early-warning rate drops below $0.50$ or FWR exceeds $0.40$ on benign drift.
- **Graph Model Gate**:
  - `PROCEED`: Cross-component information gap observed and verified.
  - `HOLD`: Precursors remain single-component; linear/sequence models remain sufficient.
  - `REJECT`: Graph structure provides zero advantage across all stress regimes.
