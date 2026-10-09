# Simulator Validity Audit (Phase 5)

## 1. Executive Summary & Epistemic Boundary

This audit establishes the explicit boundary between the mathematical/physical models implemented in the `Quantumattack` digital twin and real physical QKD hardware.

**Core Scientific Declaration**:
The `Quantumattack` digital twin is a **purely synthetic simulation environment**. All evaluations conducted to date represent synthetic in-silico validation of causal feature representations and forecasting policies. **No hardware validation is claimed, implied, or established.**

The validity of the early-warning signal established in Phases 1–5 is strictly valid with respect to the modeled physical phenomena and approximations detailed below.

---

## 2. Component-by-Component Epistemic Classification

Every physical and architectural element of the simulator is categorized into one of five rigorous scientific classifications:
1. **Established physical mechanism**: Direct implementation of first-principles physical laws (Maxwell's equations, quantum state evolution, Poissonian photon statistics).
2. **Literature-supported model**: Standard model widely adopted in peer-reviewed quantum optics and experimental QKD literature.
3. **Engineering approximation**: Discretized, simplified, or lumped-parameter models used for computationally tractable telemetry generation.
4. **Project inference**: Algorithmic rules, thresholds, or derived metrics designed specifically for this early-warning research system.
5. **Unvalidated assumption**: Postulated behaviors that lack direct empirical calibration against commercial or operational QKD hardware.

| Simulator Component | Module / Parameter | Epistemic Classification | Literature Basis / Implementation Rationale | Operational Risk & Validity Bound |
|:---|:---|:---|:---|:---|
| **Fiber Attenuation & Beer-Lambert Law** | `simulator/physics.py`<br>`attenuation_db_per_km = 0.2` | **Established physical mechanism** | Standard SMF-28 single-mode optical fiber attenuation at 1550 nm ($\alpha \approx 0.2\text{ dB/km}$). Transmittance $T = 10^{-\alpha L / 10}$. | Exact for linear propagation. Does not model nonlinear Kerr effects, Brillouin, or Raman scattering at high launch powers. |
| **Poissonian Photon Statistics & Decoy States** | `simulator/physics.py`<br>Poissonian pulse generation | **Established physical mechanism** | Weak coherent pulses (WCP) obey Poisson distribution $P(n) = \frac{\mu^n e^{-\mu}}{n!}$. Standard 3-state decoy protocol (vacuum, weak decoy $\nu$, signal $\mu$). | Accurate for phase-randomized laser pulses. Assumes ideal Poisson statistics without laser diode intensity fluctuations or spatial mode mismatch. |
| **Polarization Drift & Birefringence** | `simulator/physics.py`<br>Stochastic unitary matrix walk | **Literature-supported model** | Environmental stress and thermal fluctuations induce random birefringence fluctuations modeled as a 2D/3D unitary drift walk on the Poincaré sphere. | Discretized block-level drift rather than continuous-time Langevin process. Does not simulate acoustic/seismic shock frequencies above 100 Hz. |
| **Single-Photon Detector (SPAD/SNSPD) Model** | `simulator/physics.py`<br>$\eta_{det}, DCR, P_{afterpulse}$ | **Literature-supported model** | Standard detector efficiency ($\eta \approx 10\text{--}20\%$), dark count rate ($10^{-6}\text{--}10^{-5}$/gate), and geometric afterpulsing probability decay. | Lumped efficiency model; does not simulate dead-time recovery dynamics at ultra-high count rates or latching in superconducting nanowires. |
| **Local Oscillator (LO) Power & Attenuator Manipulation** | `simulator/attacks/lo_manipulation.py`<br>Laser power ramp & heterodyne receiver response | **Literature-supported model** | Häseler et al. / Jouguet et al. continuous-variable and bright-pulse LO side-channel attacks where adversary alters LO intensity to blind or bias homodyne detection. | The simulator models the physical actuator drive currents and optical power ramping as an exponential/linear drift preceding receiver saturation. Precursor is physically justified by the thermal and power stabilization time of the optical source. |
| **Calibration / Phase-Modulator Bias Shift** | `simulator/attacks/calibration_manipulation.py`<br>$V_\pi$ drift and feedback hunting | **Engineering approximation** | Phase-modulator DC bias drifts away from the optimum $V_\pi$ point. Control loop hunts for the optimum bias, creating variance and drift precursors before sudden key disruption. | In physical hardware, dither algorithms and feedback loops operate at millisecond timescales. The digital twin lumps feedback hunting into block-level control telemetry ($V_{bias}$, dither error). |
| **Spatial / Polarization Jamming** | `simulator/attacks/channel_jamming.py`<br>High-loss injection & multi-wavelength probing | **Engineering approximation** | Physical jamming involves either optical fiber bending/tapping or bright light injection into the quantum channel to saturate detectors or force system fallback. | The synthetic twin models probe pulses as intermittent insertion loss spikes and scattering noise. High-power sudden jamming is modeled as a sudden step function. |
| **Sudden Intercept-Resend** | `simulator/attacks/intercept_resend.py`<br>Instantaneous measurement and state re-emission | **Established physical mechanism** | Standard Eve intercept-resend attack without side-channels. Instantly introduces 25% QBER in 4-state BB84. | Physically, this attack has NO physical precursor on the optical line prior to activation. Model correctly produces ZERO pre-onset signals. |
| **Thermal & Acoustic Environmental Coupling** | `simulator/environment.py`<br>Diurnal temperature, loss drift | **Engineering approximation** | Ambient temperature changes affect fiber length ($40\text{ ps/km/K}$) and polarization alignment. | Modeled as slow sinusoidal drift + colored noise. Does not capture localized physical stressors (e.g., railway vibration, aerial fiber wind flutter). |
| **Feature Extraction & Temporal Windowing** | `features/`<br>Group A–D causal features | **Project inference** | 154 derived causal rolling features (EWMA, CUSUM, Kolmogorov-Smirnov, autocorrelation) computed strictly backward in time. | Highly sensitive to unmodeled observation noise (verified in Stress Test A). |
| **Warning Policy & Decision Thresholding** | `baselines/warnings.py`<br>Sustained-until-onset policy | **Project inference** | Requires $P \ge 0.5$ for $K=3$ consecutive blocks, sustained until attack onset. | Prevents false alarms on transient drift spikes, but assumes attack onset will occur within finite forecast horizon. |
| **Detector Linearity & Saturation Curve** | `simulator/telemetry.py` | **Unvalidated assumption** | SPAD/SNSPD response transitions linearly into saturation before paralyzation. | Real detectors exhibit complex nonlinear recovery and blinding behavior (e.g., Makarov et al. detector blinding). |
| **Attenuator Motor & DAC Quantization Noise** | `simulator/telemetry.py` | **Unvalidated assumption** | Actuator telemetry noise is modeled as independent zero-mean Gaussian. | Real physical DACs and motor encoders exhibit discrete step quantization, backlash, and correlated 1/f flicker noise. |

---

## 3. Threat Model Realism & Boundary Constraints

1. **Precursors are NOT Arbitrary**:
   - Precursors are physically grounded in actuator slewing, control-loop hunting, and adversarial probe signals.
   - Sudden attacks (`intercept_resend`) strictly contain **zero pre-onset artifacts**, preserving real-world physical ground truth.
2. **Benign Drift is NOT Trivially Distinguishable**:
   - Environmental variations include severe diurnal thermal stress ($0.06\text{ dB/km}$ drift, rapid polarization drift, high disturbance probability $p=0.8$).
   - The sustained-until-onset policy demonstrated empirical robustness ($0.00\%$ FWR) across unseen benign drift regimes (Partition G3).

---

## 4. Hardware Validation Gap & Production Prerequisites

Before any operational or hardware deployment, the following physical validation steps are mandatory:
1. **Physical Testbed Benchmarking**:
   - Connect commercial QKD hardware (e.g., ID Quantique, Toshiba QKD, or academic testbed) to real single-mode fiber spools and optical attenuators.
   - Record raw FPGA hardware telemetry (avalanche count rates, bias voltages, APD temperatures, optical power meters).
2. **Adversarial Hardware Injections**:
   - Execute controlled physical attacks using tunable external laser sources, fiber squeezers, and fast electro-optic modulators.
3. **Noise Calibration**:
   - Stress Test A demonstrated that the logistic model collapses under $\sigma \ge 0.02$ additive feature noise. Physical hardware deployment will require noise-robust retraining, Kalman filtering, or denoising autoencoders prior to logistic classification.
