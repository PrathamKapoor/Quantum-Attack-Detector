# Feature Specification (candidate derived features)

Created 2026-10-08 (Phase 1). Phase 1 establishes CANDIDATE derived features — the
final feature set must later be justified by empirical analysis and ablation
(master prompt §24). Everything here is computed strictly causally from historical
telemetry by `src/quantumattack/features.py` — never inside the base simulator.

Causality rule (normative, master prompt §17): features at time t use samples
`t−lookback+1 … t` only. Every rolling statistic is TRAILING. Derivatives are
backward differences. Missing-history behavior is explicit per feature.

## Legend

- lookback: number of telemetry records (blocks; 1 block = 10 ms) used.
- NaN policy: features return NaN until `lookback` samples are available (warmup) —
  never zeros, never partial-window values (a partial window would leak scenario
  start position and bias means).
- LEAKAGE RISK column: explicit flag for anything that could introduce future leakage
  if misused.

## Candidate features

### Level-1: differences (backward, causal)

| Feature | Input telemetry | Lookback | Causal calculation | Units | Missing-history | Purpose | LEAKAGE RISK |
|---|---|---|---|---|---|---|---|
| `d1_<col>` | any float telemetry column | 2 | `x[t] − x[t−1]` | col units | NaN for t<1 | slope detection; intercept-resend step produces | safe (backward diff) |
| `d2_<col>` | any float telemetry column | 3 | `x[t] − 2x[t−1] + x[t−2]` | col units | NaN for t<2 | acceleration; step onset has large d2 | safe |
| `d1_w_<col>` | any float column | W+1 | `mean(x[t−W+1..t]) − mean(x[t−2W+1..t−W])` (two adjacent trailing windows) | col units | NaN for t<2W−1 | windowed slope; robust to per-block noise | safe (both windows end ≤ t) |

### Level-2: rolling statistics (trailing, causal)

| Feature | Input | Lookback | Causal calculation | Units | Missing-history | Purpose | LEAKAGE RISK |
|---|---|---|---|---|---|---|---|
| `rm_<col>` | float col | W (5) | trailing mean | col units | NaN t<W−1 | smooth baseline | DANGER if window centered; keep trailing |
| `rv_<col>` | float col | W | trailing variance | col² | NaN t<W−1 | variability shift (jamming probes) | DANGER if centered |
| `rm_L_<col>` | float col | L (100) | long trailing mean | col units | NaN t<L−1 | slow baseline (drift vs step) | DANGER if centered |
| `rs_<col>` | float col | L | slope of OLS fit over trailing window | col units/block | NaN t<L−1 | drift detection (LO/calibration ramps) | safe (OLS uses ≤ t only) |
| `rc_<col>` | float col | L | trailing autocorrelation (lag 1) | unitless | NaN t<L−1 | regime change (OU vs ramp have different AC) | safe |
| `qdev_<col>` | float col | 50 | trailing 0.05–0.95 quantile width | col units | NaN t<50 | heavy-tail shift (probe blips) | safe |

### Level-3: CUSUM / change statistics (causal)

| Feature | Input | Lookback | Causal calculation | Units | Missing-history | Purpose | LEAKAGE RISK |
|---|---|---|---|---|---|---|---|
| `cusum_pos_<col>` | float col | all history (streaming) | `S+ = max(0, S+ + (x[t] − μ0)/σ0 − k)`, μ0/σ0 from a REFERENCE window = first `warmup` blocks of the scenario (or train-scenario constants later), k=0.5 | σ units | runs from t=warmup | cumulative upward drift (gradual ramps) | DANGER: μ0/σ0 from full scenario = leakage; Phase 1 uses warmup-window constants only |
| `cusum_neg_<col>` | float col | streaming | symmetric downward | σ units | runs from t=warmup | downward drift (T̂ drop, LO drop) | same danger |
| `ksstat_<col>` | float col | 2L | two-sample KS statistic: trailing-L window vs reference-L window (immediately preceding L blocks) | unitless | NaN t<2L−1 | distribution change (attack vs normal) | safe (both windows ≤ t) |
| `ewma_<col>` | float col | streaming | `E[t] = λ·x[t] + (1−λ)·E[t−1]`, λ=0.1, E[0]=x[0] | col units | runs from t=0 | smooth tracking | safe |

### Level-4: cross-feature statistics (causal)

| Feature | Input | Lookback | Causal calculation | Units | Missing-history | Purpose | LEAKAGE RISK |
|---|---|---|---|---|---|---|---|
| `corr_xp` | x_mean/x_var/p_mean/p_var (raw) | W | trailing correlation between X and P block means | unitless | NaN t<W−1 | phase-noise coupling rise | safe |
| `corr_lo_quad` | lo_power, x_var | W | trailing correlation between LO power and quadrature variance | unitless | NaN t<W−1 | LO-attack signature (variance tracks LO²) | safe |
| `skr_consistency` | skr_estimate, x_var, transmittance | W | residual of SKR vs its (T̂, V_A)-only prediction | bit/symbol | NaN t<W−1 | hidden-noise attacks make SKR inconsistent with T̂ (false security) | safe |

## Next-state prediction support (master prompt §25)

The schema keeps consecutive per-block raw telemetry, so a later model can predict
`X_(t+1)` from `X_(t−L:t)` and form `prediction_residual = observed_next − predicted`.
Requirements for later phases (documented, not implemented):

- histories are contiguous raw telemetry (no gaps) — satisfied by the export schema;
- padding at sequence START only (never end) so padding cannot reveal onset;
- residuals must be computed per feature and tracked over time (magnitude,
  persistence) — the features above (`d1_`, `rv_`, `cusum_`) are the statistical
  fallbacks a no-model baseline uses.

## Not yet decided / explicitly deferred

- Final feature subset: deferred to empirical analysis (Phase 4+).
- Per-scenario normalization: FORBIDDEN for forecasting features; if any model needs
  normalization, fit scalers on TRAIN scenarios only (leakage rule).
- Feature selection by mutual information with labels: later phase (and only on train).

---

## Implementation status (Phase 2, 2026-10-08)

Implemented in `src/quantumattack/features.py` (schema v2, 154 derived features):

| Level | Features | Windows (blocks) | Causality | Missing-history |
|---|---|---|---|---|
| differences | d1_/d2_ over 13 columns | 2 / 3 | backward differences | NaN for t<1 / t<2 |
| rolling | rm{w}_/rv{w}_ over 14 columns | 5, 25, 100 | trailing mean/std | NaN until warmup |
| slopes | rs{w}_ over 5 columns | 25, 100 | trailing OLS | NaN until warmup |
| EWMA | ewma{span}_ over 5 columns | spans 5, 25 | streaming E[0]=x[0] | runs from t=0 |
| CUSUM | cusum_pos_/neg_ over 8 columns | ref=100 | μ0/σ0 from FIRST 100 blocks ONLY | NaN until t=100 |
| KS | ks_ over 5 columns | 50 vs 50 | two trailing windows | NaN until t=99 |
| autocorr | ac1_ over 3 columns | 100 | trailing lag-1 | NaN until t=99 |

Configuration: `FeatureConfig` (all windows/spans/columns configurable; validated).
Metadata: `feature_metadata()` — feature_name, source_columns, operation, lookback,
causal, units, category (machine-readable; exported to
artifacts/phase2/features/feature_schema.json by `python -m quantumattack.features_cli`).

Verified causality: historical-invariance tests (modify telemetry after t → features
≤ t unchanged) for every feature class (tests/test_features.py); determinism,
schema stability, NaN policy, no-inf tests included.

Phase 2 findings that inform later feature selection: group D (all features) best
AUROC at H=10 (0.839 vs 0.813 base-only); differences help short horizons; temporal
stats improve calibration (Brier 0.010 vs 0.19 base) but NOT attack-specific lead-time
attribution (pair-gated = 0%). The final feature set remains deferred to ablation
across larger datasets.
