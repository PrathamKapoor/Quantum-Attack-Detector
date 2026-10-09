# Feature Freeze v1 — Phase 4 Robustness & Telemetry Role Classification

Document status: **FROZEN** (2026-10-09, Phase 4 protocol v1).

This document fulfills Phase 4 requirements (§27, §28, §29) by providing:
1. Feature redundancy analysis based on correlation (|r| > 0.95) and coefficient stability across 5 independent split seeds.
2. Formal taxonomy separating **FORECAST FEATURES** from **CONFIRMATION FEATURES**.
3. Feature classification into six mandated categories: `CORE`, `USEFUL`, `REDUNDANT`, `UNSTABLE`, `POST-ONSET ONLY`, and `FUTURE WORK`.

---

## 1. Forecast vs Confirmation Architectural Distinction (§29)

The operational early-warning system produces two distinct outputs:

```text
+--------------------------------------------------------------+
|                QUANTUM CYBERATTACK DETECTOR                  |
+------------------------------+-------------------------------+
                               |
            +------------------+------------------+
            |                                     |
            v                                     v
       [PREDICTED]                           [CONFIRMED]
  "Precursor signature detected:        "Attack onset confirmed:
   Gradual ramp active;                  QBER threshold exceeded /
   forecast lead time tau > 0"           SKR collapsed to 0"
            |                                     |
    FORECAST FEATURES                     CONFIRMATION FEATURES
   (Rolling means, EWMA,                 (QBER proxy, sudden noise step,
    CUSUM drift, OLS slopes)              SKR crash, post-onset detectors)
```

> [!IMPORTANT]
> A feature that only changes **after** attack onset may be useless for pre-onset forecasting, but remains **vital for post-onset attack confirmation**.
> Such features are NOT removed from the telemetry stream or simulator; they are designated `POST-ONSET ONLY (CONFIRMATION)`.

---

## 2. Feature Redundancy & Stability Analysis (§27)

Evaluated across 189 total telemetry and derived columns on the Phase 4 training population:
- **High-correlation pairs (|r| > 0.95)**: 246 pairs.
  - Primary source of redundancy: Trailing rolling means vs EWMA at identical smoothing windows (`rm5` vs `ewma5`: r = 0.992; `rm25` vs `ewma25`: r = 0.988).
  - Trailing derivatives across adjacent horizons (`d1` vs small lag differences).
- **Coefficient stability across 5 independent split seeds (42, 7, 101, 2024, 31337)**:
  - Top 10 predictive features maintain consistent signs and high weights across all 5 splits.
  - 33 features exhibit instability (mean |coef| < 0.01 with coefficient of variation CV > 1.5, or sign reversal across splits).

---

## 3. Feature Classification (§28)

### Category 1: CORE (Primary Forecast Drivers)
Features with high predictive weight, stable sign across all 5 seeds, and high physical interpretability:
- `transmittance`: Base estimated channel transmittance (direct indicator of physical channel tampering).
- `rm5_transmittance`, `rm25_transmittance`, `rm100_transmittance`: Trailing rolling means capturing gradual channel attenuation ramps.
- `det_gain`: Base homodyne detector gain (captures calibration manipulation).
- `rm5_det_gain`, `rm25_det_gain`, `rm100_det_gain`: Multi-scale rolling averages of detector gain.
- `lo_sig_ratio`: Local oscillator to signal power ratio (primary signature of LO manipulation).
- `rm5_lo_sig_ratio`, `rm25_lo_sig_ratio`, `rm100_lo_sig_ratio`: Trailing averages of LO ratio.
- `cusum_neg_transmittance`: One-sided cumulative sum for downward drift in channel transmittance (mean coef: +10.80).
- `cusum_neg_x_var`: One-sided cumulative sum for excess quadrature variance drift (mean coef: -9.52).
- `cusum_neg_skr_estimate`: Cumulative sum for secret key rate degradation before complete loss of key (mean coef: +5.13).

### Category 2: USEFUL (Secondary / Complementary Forecast Features)
Features providing auxiliary stability, noise rejection, or secondary physical indicators:
- `p_lo_power_mw`: Raw LO optical power (direct monitor).
- `det_offset_v`: DC offset drift in balanced receiver.
- `excess_noise_xi`: Channel excess noise estimator (SNU).
- `rv25_transmittance`, `rv100_transmittance`: Rolling variance capturing probe-pulse variance elevation.
- `slope25_transmittance`, `slope100_transmittance`: Linear trend slope over trailing windows.
- `slope25_det_gain`, `slope100_det_gain`: Calibration ramp rate estimators.
- `ks_transmittance`, `ks_excess_noise_xi`: Two-sample Kolmogorov-Smirnov distribution shift statistics.
- `ac1_transmittance`: Lag-1 autocorrelation (temporal persistence indicator).

### Category 3: REDUNDANT (Statistically Redundant for Linear Model, Preserved for Non-Linear)
Features with |r| > 0.95 against core features. Not deleted from schema v2, but documented:
- `ewma5_transmittance` (collinear with `rm5_transmittance`, r = 0.992).
- `ewma25_transmittance` (collinear with `rm25_transmittance`, r = 0.988).
- `ewma5_det_gain` (collinear with `rm5_det_gain`, r = 0.995).
- `ewma25_det_gain` (collinear with `rm25_det_gain`, r = 0.991).
- `ewma5_lo_sig_ratio` (collinear with `rm5_lo_sig_ratio`, r = 0.996).

### Category 4: UNSTABLE (Low Weight / High Split Variance)
Features contributing minimal signal and exhibiting sign reversals or extreme variance across splits:
- `d2_temperature_c`: Second difference of ambient temperature (high derivative noise).
- `d2_clock_drift_ppm`: Second difference of clock drift.
- `ac1_phase_error_rad`: Lag-1 autocorrelation of phase error.
- `slope100_clock_drift_ppm`: 100-block trend on environmental clock drift.
- 29 additional second-order derivatives and noise-floor cross-products.

### Category 5: POST-ONSET ONLY (Confirmation Features)
Telemetry indicators that remain unperturbed during pre-onset preparation but react sharply after attack onset:
- `qber_proxy`: Quantum bit error rate proxy. By definition, QBER remains at baseline (~0.015) until active key interception or strong disturbance occurs. Vital for **CONFIRMED** attack alarm, 0% predictive utility.
- `skr_estimate` collapse to 0.0: Instantaneous security shutdown trigger.
- Post-onset variance step in `x_var`, `p_var`: Confirms intercept-resend and blinding attacks.

### Category 6: FUTURE WORK
Representations reserved for multi-node or multi-component extensions:
- Heterogeneous graph node embeddings.
- Cross-channel coherence metrics.
- Multi-component joint arrival timing matrices.

---

## 4. Frozen Status

Feature Schema Version: **`FEATURE_SCHEMA_VERSION = 2`**
Total Columns: 154 derived causal features + 35 raw telemetry columns.
No features have been removed from the pipeline. The classification above governs model development and operational triage in subsequent phases.
