# Telemetry Specification

Created 2026-10-08 (Phase 1). Candidate taxonomy from the master prompt §22, narrowed
to what the Phase 1 CV-QKD simulator actually implements. Per decision D-008 the
simulator supports exactly one protocol family: GMCS CV-QKD with heterodyne detection,
per-block closed-form Gaussian statistics (no per-symbol simulation). DV-specific
features (decoy gains, dark counts) are NOT implemented.

For every implemented feature: name, type, units, protocol applicability, physical
meaning, calculation, sampling cadence, causal availability, expected range.
Ranges are anchored to source 8 (Hajomer et al. 2024, VERIFIED FROM SOURCE:
η=0.028 untrusted @100 km, ξ≈0.2 mSNU, V_mod≈8.4 SNU at 100 MBaud) scaled to the
Phase 1 operating point (see §Ranges).

## Phase 1 operating point (simulator defaults)

| Parameter | Default | Unit | Anchored to |
|---|---|---|---|
| fiber length | 50 | km | source 8 (100 km demo; half for faster SKR) |
| fiber attenuation | 0.15 | dB/km @1550nm | source 8 (0.146 dB/km) |
| channel transmittance η (untrusted) | 10^(−0.15·50/10) ≈ 0.177 | linear | computed |
| detector efficiency τ (trusted) | 0.6 | linear | source 8 (0.68) |
| modulation variance V_A | 4.0 | SNU | source 8 sweep (3.5–9.3 SNU plausible) |
| electronic noise (input-referred) | 0.05 | SNU | source 8 (62.7 mSNU at detector; input-referred smaller) |
| baseline excess noise ξ | 0.01 | SNU | source 8 (0.212 mSNU = 0.000212 SNU at channel output; simulator uses 0.01 SNU at Bob input — conservative, includes phase noise residuals) |
| LO power | 1.0 | normalized | normalized units |
| block duration | 10 | ms | source 8 (1e7 samples @1 Gsample/s per frame) |

## Implemented features

### Source features

| Name | Type | Units | Applicability | Physical meaning | Calculation | Cadence | Causal availability | Expected range |
|---|---|---|---|---|---|---|---|---|
| `mod_variance` | float | SNU | CV-QKD | modulation variance V_A chosen by Alice | public protocol parameter (constant per scenario unless attack/confounder modifies it) | per block | yes (it is a configured value at t) | 2–9 SNU |
| `rep_rate_mhz` | float | MHz | CV-QKD | symbol repetition rate | public protocol parameter (constant) | per block | yes | 100 (source 8) |

Note: Alice's source settings are PUBLIC parameters in QKD (announced for parameter
estimation) — using them as features is causal-safe. ATTACKS do not change Alice's
source settings in Phase 1 (no source-side attack implemented); they change channel/
LO/detector state.

### Local oscillator features

| Name | Type | Units | Applicability | Physical meaning | Calculation | Cadence | Causal availability | Expected range |
|---|---|---|---|---|---|---|---|---|
| `lo_power` | float | normalized | CV-QKD | LO power at detection | mean LO power over block from state: `P_LO(t) = P0 · g_temp(t) · g_LO(t)` (g_temp = benign thermal coupling, g_LO = attack/attenuation factor, both evolving in state) | per block | yes | 0.3–1.2 |
| `lo_variance` | float | normalized² | CV-QKD | LO intensity noise | `Var(LO block samples) = (RIN·P_LO)² + base_LO_noise` — RIN relative intensity noise from state | per block | yes | small vs mean |
| `lo_sig_ratio` | float | normalized | CV-QKD | LO/signal ratio | `P_LO / P_sig(t)` where P_sig from V_A and η | per block | yes | ~10⁶–10⁸ (reported normalized) |
| `lo_drift` | float | normalized/block | CV-QKD | LO power first difference | backward difference `P_LO(t) − P_LO(t−1)` (causal) | per block | yes | ~±0.01 |

### Quantum measurement features (heterodyne quadratures)

Per-block Gaussian sufficient statistics of the measured quadrature distribution
(heterodyne: X and P measured simultaneously, each shot adds 1 SNU vacuum):

| Name | Type | Units | Applicability | Physical meaning | Calculation | Cadence | Causal availability | Expected range |
|---|---|---|---|---|---|---|---|---|
| `x_mean` | float | SNU | CV-QKD | mean of measured X quadrature | block mean of N(μ_X, Σ) samples; μ_X = 0 unless offset attack/bias | per block (N_eff = 1e6 symbols) | yes | ≈0 ± offset/√N_eff |
| `x_var` | float | SNU | CV-QKD | variance of measured X | `V_meas,X = τ·η·(V_A + 1 + ξ_x) + t + 1` (heterodyne) scaled by (g_LO·g_det)²; ξ_x = excess noise seen in X | per block | yes | ~1–10 SNU |
| `p_mean` | float | SNU | CV-QKD | mean of measured P | same as x_mean for P phase | per block | yes | ≈0 |
| `p_var` | float | SNU | CV-QKD | variance of measured P | same form as x_var with ξ_p | per block | yes | ~1–10 SNU |
| `xp_corr` | float | unitless | CV-QKD | X–P correlation (phase noise proxy) | sample correlation of X,P in block; baseline ≈0 (isotropic modulation), rises with phase noise (ξ_RPN couples X,P) | per block | yes | 0–0.5 |
| `quad_std_ratio` | float | unitless | CV-QKD | anisotropy X vs P | `sqrt(x_var/p_var)`; baseline ≈1 | per block | yes | ~1 |

### Detector features

| Name | Type | Units | Applicability | Physical meaning | Calculation | Cadence | Causal availability | Expected range |
|---|---|---|---|---|---|---|---|---|
| `det_gain` | float | normalized | CV-QKD | detector gain state (both arms) | state variable; benign OU wander or attack ramp | per block | yes | 1.0 ± 0.05 (benign), 1.0±0.25 (attack) |
| `det_offset` | float | SNU | CV-QKD | detector offset state | state variable; benign OU wander or attack ramp | per block | yes | ≈0 ± 0.05·σ_quad |
| `det_imbalance` | float | unitless | CV-QKD | gain imbalance between the two balanced detector arms | `(g_+ − g_−)/(g_+ + g_−)` from state | per block | yes | 0–0.1 benign; larger under attack |
| `det_efficiency` | float | linear | CV-QKD | trusted detector efficiency τ | state variable (benign OU wander) | per block | yes | 0.55–0.65 |
| `saturation_frac` | float | unitless | CV-QKD | fraction of samples near detector saturation | analytic: fraction of N(μ,σ) samples beyond `k_sat·σ` from full scale under current (μ,σ); rises sharply when jamming inflates quadrature variance or offsets | per block | yes | ≈0; >0 under jamming |

Note (honesty): `det_gain`/`det_offset`/`det_imbalance` are STATE telemetry — in a
real system they would be inferred from periodic calibration runs. The simulator
exposes them because they are the causal chain from attack/benign-confounder state
to quadrature statistics; ground-truth state is exported as evaluation-only columns
(`true_*`), and the telemetry-level values are what a monitor could plausibly see.

### Timing features

| Name | Type | Units | Applicability | Physical meaning | Calculation | Cadence | Causal availability | Expected range |
|---|---|---|---|---|---|---|---|---|
| `arr_residual` | float | ns | CV-QKD | mean arrival-time residual per block | clock model: residual = accumulated clock offset + jitter sample; offset random-walks (benign) | per block | yes | 0–50 ns |
| `jitter_ns` | float | ns | CV-QKD | block jitter level | state variable (OU) | per block | yes | 1–10 ns |
| `clock_offset_ns` | float | ns | CV-QKD | accumulated synchronization offset | random walk from state | per block | yes | ±100 ns |
| `clock_drift_ppb` | float | ppb | CV-QKD | oscillator frequency offset | random walk from state | per block | yes | ±50 ppb |

Note: timing attacks (time-shift) are NOT simulated in Phase 1 (BB84-family, P2);
timing telemetry exists as benign-confounder surface so the model cannot ignore it.

### Channel features

| Name | Type | Units | Applicability | Physical meaning | Calculation | Cadence | Causal availability | Expected range |
|---|---|---|---|---|---|---|---|---|
| `transmittance` | float | linear | CV-QKD | block-level channel transmittance estimate | state-derived: η_true(t) from fiber loss state + attack tap; NO estimator noise beyond block sampling (estimator handled in security metrics) | per block | yes (state at t) | 0.05–0.3 |
| `fiber_loss_db` | float | dB | CV-QKD | fiber loss state | state: base + OU wander + benign degradation | per block | yes | 7.5±0.5 dB (50 km) |
| `excess_noise` | float | SNU | CV-QKD | block-level excess noise at Bob input | state-derived: ξ_true(t) = ξ_base + ξ_temp-coupling + ξ_attack (intercept-resend/jamming add) + LO-attack hidden reduction | per block | yes (state at t) | 0.005–0.1 benign; >0.1 attacked |
| `background` | float | SNU | CV-QKD | background light at detector input | state: base + OU + spikes (benign) + probes/jamming (attack) | per block | yes | ~0.001–0.05 SNU |
| `snr` | float | dB | CV-QKD | signal-to-noise ratio of quadrature measurement | `10·log10(τ·η·V_A / (V_meas − τ·η·(V_A+1)))` | per block | yes | 5–20 dB |

### Security features

| Name | Type | Units | Applicability | Physical meaning | Calculation | Cadence | Causal availability | Expected range |
|---|---|---|---|---|---|---|---|---|
| `qber_proxy` | float | unitless | CV-QKD | CV-QKD has no QBER; this is the analogous error indicator | derived: `1 − I_AB/(log2(1+SNR_lin))`-style normalized distortion proxy; documented as PROXY only | per block | yes | ~0.01–0.1 |
| `skr_estimate` | float | bit/symbol | CV-QKD | estimated secret-key rate | GMCS asymptotic formula: `K = β·I_AB − χ(W&P)` with I_AB = log2(1+SNR_lin), χ from (T̂, ξ̂, V_A) reverse reconciliation; attack-modified state feeds χ | per block | yes (uses only state ≤ t) | 0–0.1 bit/symbol |
| `secret_fraction` | float | unitless | CV-QKD | fraction of symbols surviving to key | 1 − leak fraction (constant reconciliation overhead in Phase 1) | per block | yes | ~0.9 |
| `recon_efficiency` | float | unitless | CV-QKD | reconciliation efficiency β | constant 0.95 per scenario config | per block | yes | 0.95 |
| `skr_drift` | float | bit/symbol/block | CV-QKD | SKR first difference | backward difference (causal) | per block | yes | small |

Note: Phase 1 SKR is a per-block ASYMPTOTIC estimate from (T̂, ξ̂, V_A) — finite-key
composable security (source 8's δ_fail=1e-10 bounds) is out of scope; the estimator
is written so finite-key corrections can slot in later.

### Decoy-state features

NOT IMPLEMENTED — decoy states are a DV-QKD technique; the simulator supports
CV-QKD only (decision D-008). Documented as out-of-scope in `docs/threat-model.md` §2.

### Environmental / context features

| Name | Type | Units | Applicability | Physical meaning | Calculation | Cadence | Causal availability | Expected range |
|---|---|---|---|---|---|---|---|---|
| `temperature` | float | °C | any | lab temperature near LO/detector | state: 22 + sinusoid(24h, phase) + OU; slow | per block | yes | 22±2 °C |
| `det_temperature` | float | °C | any | detector thermal state | state: follows lab temperature + OU | per block | yes | 22±3 °C |
| `background_proxy` | float | SNU | any | monitor-visible background-light proxy | same value as `background` (exported separately for graph-node mapping later) | per block | yes | same as background |
| `channel_condition` | int (enum) | — | any | categorical channel state | NORMAL/DEGRADED/JAMMED from state (evaluation-only in Phase 1; a real monitor would infer it) | per block | yes | 0–2 |
| `calibration_state` | float | — | any | calibration health indicator | state: residual after last benign recalibration; drifts between recalibrations | per block | yes | 0–1 |
| `clock_drift_ppb` | float | ppb | any | (also listed under Timing) | same value | per block | yes | ±50 ppb |

## Raw vs derived (master prompt §23)

All features above are RAW/base telemetry: produced directly by the simulator from
its state, one record per block. DERIVED temporal features (delta beyond the two
first-differences above, rolling means/variances, EWMA, CUSUM, change statistics,
autocorrelation, cross-correlation, spectral summaries) are computed by the FEATURE
layer (`src/quantumattack/features.py`), strictly causally — specified in
`docs/feature-spec.md`. The base simulator contains NO model-specific feature
engineering beyond the two documented first-differences (`lo_drift`, `skr_drift`)
which are themselves causal (backward differences).

## Column classification (normative; enforced by tests/test_metadata_isolation.py)

| Class | Columns |
|---|---|
| metadata (never model inputs) | `scenario_id`, `pair_id`, `seed`, `protocol`, `attack_type`, `attack_onset`, `precursor_start`, `scenario_class`, `sim_version`, `config_hash` |
| label (never model inputs) | `state_label`, `current_attack`, `future_attack_h10/h25/h50/h100`, `drift_episode_id` |
| evaluation-only (never model inputs in Phase 1) | `true_*` ground-truth state columns (`true_T`, `true_xi`, `true_lo_power`, `true_det_gain`, `true_det_offset`, `true_background`, `true_clock_offset`, `true_channel_condition`), `window_index` |
| model features (candidate) | everything else in the tables above |
