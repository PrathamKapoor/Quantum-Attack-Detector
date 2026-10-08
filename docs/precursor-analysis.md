# Phase 1 Precursor Analysis

Generated 2026-10-08 from `C:\Projects\Quantumattack\data\phase1` (all seeds; matched counterfactual pairs).
Effect sizes = mean shift in sigma units of the matched benign baseline
(pre-precursor period of the paired benign run). Categories (master prompt §37):
1 = moves before onset · 2 = only at attack · 3 = also moves in benign drift · 4 = no signal.

## calibration_manipulation (5 seeds)

| Feature | Class | pre-precursor | precursor | active | benign drift | Category |
|---|---|---|---|---|---|---|
| lo_power | A | 0.00 | -0.01 | -0.01 | -0.01 | 4 |
| lo_sig_ratio | A | 0.00 | -0.51 | -0.09 | -0.51 | 4 |
| x_var | A | 0.00 | 5.43 | 16.27 | 0.25 | 1 |
| p_var | A | 0.00 | 5.43 | 16.27 | 0.25 | 1 |
| quad_std_ratio | A | 0.00 | 0.00 | 0.00 | 0.00 | 4 |
| transmittance | A | 0.00 | 0.52 | 0.08 | 0.52 | 4 |
| excess_noise | A | 0.00 | -0.24 | 0.21 | -0.24 | 4 |
| background | A | 0.00 | -0.17 | 0.06 | -0.17 | 4 |
| snr | A | 0.00 | -3.23 | -6.51 | -0.12 | 1 |
| skr_estimate | A | 0.00 | -2.96 | -5.71 | -0.13 | 1 |
| det_gain | A | 0.00 | 5.41 | 15.06 | 0.08 | 1 |
| det_offset | A | 0.00 | -0.30 | -0.09 | -0.30 | 4 |
| det_imbalance | A | 0.00 | 0.77 | 1.52 | 0.38 | 2 |
| saturation_frac | A | 0.00 | -0.15 | -0.08 | -0.17 | 4 |
| qber_proxy | A | 0.00 | 0.00 | 0.00 | 0.00 | 4 |
| xp_corr | A | 0.00 | 0.97 | 1.41 | 0.97 | 2 |
| clock_offset_ns | A | 0.00 | 0.76 | 1.36 | 0.76 | 2 |
| temperature | A | 0.00 | -0.01 | -0.01 | -0.01 | 4 |
| skr_drift | A | 0.00 | -0.07 | -0.01 | 0.00 | 4 |

Category counts: **Cat1 (pre-onset signal): 5 · Cat2 (attack-only): 3 · Cat3 (confounded with drift): 0 · Cat4 (no signal): 11**

## channel_jamming (10 seeds)

| Feature | Class | pre-precursor | precursor | active | benign drift | Category |
|---|---|---|---|---|---|---|
| lo_power | B | 0.00 | 0.00 | -0.02 | 0.00 | 4 |
| lo_sig_ratio | B | 0.00 | 0.00 | -0.08 | 0.00 | 4 |
| x_var | B | 0.00 | 0.14 | 4.76 | 0.00 | 2 |
| p_var | B | 0.00 | 0.14 | 4.76 | 0.00 | 2 |
| quad_std_ratio | B | 0.00 | 0.00 | 0.00 | 0.00 | 4 |
| transmittance | B | 0.00 | 0.00 | 0.07 | 0.00 | 4 |
| excess_noise | B | 0.00 | 0.00 | 1.46 | 0.00 | 2 |
| background | B | 0.00 | 0.01 | 453.28 | 0.00 | 2 |
| snr | B | 0.00 | -0.10 | -3.07 | 0.00 | 2 |
| skr_estimate | B | 0.00 | -0.10 | -2.92 | 0.00 | 2 |
| det_gain | B | 0.00 | 0.00 | 0.02 | 0.00 | 4 |
| det_offset | B | 0.00 | 0.00 | -0.08 | 0.00 | 4 |
| det_imbalance | B | 0.00 | 0.07 | 0.21 | 0.07 | 4 |
| saturation_frac | B | 0.00 | -0.02 | -0.22 | -0.02 | 4 |
| qber_proxy | B | 0.00 | 0.00 | 0.00 | 0.00 | 4 |
| xp_corr | B | 0.00 | 0.00 | 1.38 | 0.00 | 2 |
| clock_offset_ns | B | 0.00 | 0.00 | 1.30 | 0.00 | 2 |
| temperature | B | 0.00 | 0.00 | -0.02 | 0.00 | 4 |
| skr_drift | B | 0.00 | -0.00 | -0.01 | 0.00 | 4 |

Category counts: **Cat1 (pre-onset signal): 0 · Cat2 (attack-only): 8 · Cat3 (confounded with drift): 0 · Cat4 (no signal): 11**

## intercept_resend (5 seeds)

| Feature | Class | pre-precursor | precursor | active | benign drift | Category |
|---|---|---|---|---|---|---|
| lo_power | C | 0.00 | 0.00 | -0.02 | 0.00 | 4 |
| lo_sig_ratio | C | 0.00 | 0.00 | 60.92 | 0.00 | 2 |
| x_var | C | 0.00 | 0.00 | -13.35 | 0.00 | 2 |
| p_var | C | 0.00 | 0.00 | -13.35 | 0.00 | 2 |
| quad_std_ratio | C | 0.00 | 0.00 | 0.00 | 0.00 | 4 |
| transmittance | C | 0.00 | 0.00 | -42.67 | 0.00 | 2 |
| excess_noise | C | 0.00 | 0.00 | 3.08 | 0.00 | 2 |
| background | C | 0.00 | 0.00 | -0.01 | 0.00 | 4 |
| snr | C | 0.00 | 0.00 | -1.56 | 0.00 | 2 |
| skr_estimate | C | 0.00 | 0.00 | -1.52 | 0.00 | 2 |
| det_gain | C | 0.00 | 0.00 | 0.10 | 0.00 | 4 |
| det_offset | C | 0.00 | 0.00 | -0.06 | 0.00 | 4 |
| det_imbalance | C | 0.00 | 0.00 | 0.26 | 0.00 | 4 |
| saturation_frac | C | 0.00 | 0.00 | -0.06 | 0.00 | 4 |
| qber_proxy | C | 0.00 | 0.00 | 0.00 | 0.00 | 4 |
| xp_corr | C | 0.00 | 0.00 | 1.38 | 0.00 | 2 |
| clock_offset_ns | C | 0.00 | 0.00 | 1.35 | 0.00 | 2 |
| temperature | C | 0.00 | 0.00 | -0.02 | 0.00 | 4 |
| skr_drift | C | 0.00 | 0.00 | -0.00 | 0.00 | 4 |

Category counts: **Cat1 (pre-onset signal): 0 · Cat2 (attack-only): 9 · Cat3 (confounded with drift): 0 · Cat4 (no signal): 10**

## lo_manipulation (5 seeds)

| Feature | Class | pre-precursor | precursor | active | benign drift | Category |
|---|---|---|---|---|---|---|
| lo_power | A | 0.00 | -295.00 | -1019.05 | -0.06 | 1 |
| lo_sig_ratio | A | 0.00 | -18.58 | -70.55 | -0.72 | 1 |
| x_var | A | 0.00 | -12.10 | -36.87 | 0.34 | 1 |
| p_var | A | 0.00 | -12.10 | -36.87 | 0.34 | 1 |
| quad_std_ratio | A | 0.00 | 0.00 | 0.00 | 0.00 | 4 |
| transmittance | A | 0.00 | 0.73 | 0.07 | 0.73 | 4 |
| excess_noise | A | 0.00 | 0.03 | 0.21 | 0.03 | 4 |
| background | A | 0.00 | -0.21 | 0.07 | -0.21 | 4 |
| snr | A | 0.00 | 49.52 | 74.75 | -0.13 | 1 |
| skr_estimate | A | 0.00 | 54.33 | 82.59 | -0.14 | 1 |
| det_gain | A | 0.00 | 0.10 | 0.06 | 0.10 | 4 |
| det_offset | A | 0.00 | -0.34 | -0.09 | -0.34 | 4 |
| det_imbalance | A | 0.00 | 0.50 | 0.24 | 0.50 | 4 |
| saturation_frac | A | 0.00 | -0.36 | -0.69 | -0.28 | 4 |
| qber_proxy | A | 0.00 | 0.00 | 0.00 | 0.00 | 4 |
| xp_corr | A | 0.00 | 0.96 | 1.40 | 0.96 | 2 |
| clock_offset_ns | A | 0.00 | 0.73 | 1.35 | 0.73 | 2 |
| temperature | A | 0.00 | -0.06 | -0.01 | -0.06 | 4 |
| skr_drift | A | 0.00 | 2.03 | 0.00 | 0.01 | 1 |

Category counts: **Cat1 (pre-onset signal): 7 · Cat2 (attack-only): 2 · Cat3 (confounded with drift): 0 · Cat4 (no signal): 10**

## Summary across attacks

| Attack | Features with pre-onset signal (Cat1) | Confusable with drift (Cat3) |
|---|---|---|
| calibration_manipulation | x_var, p_var, snr, skr_estimate, det_gain | — |
| channel_jamming | — | — |
| intercept_resend | — | — |
| lo_manipulation | lo_power, lo_sig_ratio, x_var, p_var, snr, skr_estimate, skr_drift | — |
