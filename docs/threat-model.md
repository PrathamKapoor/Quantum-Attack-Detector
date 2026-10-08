# Threat Model & System Boundary

Created 2026-10-08 (Phase 1). Defines WHAT system is protected, its components, the
adversaries, and the exact scope of the Phase 1 simulator. Evidence levels per §56:
claims about the physical system are standard QKD physics; claims about attacker
behavior marked PROJECT INFERENCE are synthetic research assumptions, not observed facts.

## 1. Protected system

A point-to-point **continuous-variable QKD (CV-QKD) link**: one transmitter (Alice), one
receiver (Bob), connected by an optical fiber quantum channel and a separate classical
authenticated channel. The asset to protect is the ** secrecy of the distributed key and
the integrity/availability of the key-distribution service**. The early-warning system
monitors telemetry produced by the link and estimates P(attack within horizon H).

Explicitly NOT in scope (this project does not claim to protect these):

- QKD network topologies (trusted-node routing, multi-link scheduling) — later phase at most.
- Key-management-system attacks downstream of the QKD layer (storage, PKI, application use).
- Side channels of the classical post-processing hosts (RF/EM emanations of computers).
- Physical safety of hardware.

## 2. System components (monitoring boundary)

| Component | Role | Phase 1 telemetry exposed | Simulator module |
|---|---|---|---|
| Source / modulator (Alice) | Prepares Gaussian-modulated coherent states | modulation variance (public config), repetition rate (public config) | `simulator/protocols/cvqkd.py` |
| Quantum channel (fiber) | Transmits states; subject to loss and excess noise | transmittance estimate, excess-noise estimate, background estimate, environment temperature | `simulator/channel/optical.py`, `simulator/environment/drift.py` |
| Local oscillator (Bob) | Phase reference for homodyne/heterodyne detection | LO power, LO variance, LO/signal ratio | `simulator/detectors/homodyne.py` |
| Detector (Bob, balanced heterodyne) | Measures quadratures | quadrature means/variances/correlation, detector gain/offset, efficiency, saturation fraction | `simulator/detectors/homodyne.py` |
| Timing subsystem | Clock synchronization, arrival timestamps | arrival residuals, jitter, clock offset/drift | `simulator/environment/drift.py` |
| Decoy-state subsystem | n/a for CV-QKD (decoy states are a DV technique) | — | — |
| Post-processing / security metrics | Parameter estimation, reconciliation, key rate | T̂, ε̂, SNR, secret-key-rate estimate, reconciliation efficiency | `simulator/protocols/cvqkd.py` |
| Classical authenticated channel | Carries reconciliation data | out of telemetry scope in Phase 1 (assumed authenticated, uncompromised) | — |
| Environmental conditions | Temperature, background light, clock discipline | temperature, background-light proxy, clock drift | `simulator/environment/drift.py` |

## 3. Protocol scope of the Phase 1 simulator

**Supported protocol family (exactly one, by decision D-008):**
Gaussian-modulated coherent-state (GMCS) CV-QKD with heterodyne detection
(GG02-family; the modern experimental default). Per-block closed-form Gaussian
channel model; no per-symbol simulation. See `docs/telemetry-spec.md` for the
model formulas and `docs/attack-taxonomy.md` for which attacks physically apply.

**NOT supported in Phase 1 (do not claim coverage):**

- Discrete-variable protocols (BB84, decoy-state BB84, MDI-QKD, Twin-Field) — DV
  attacks (time-shift, PNS, decoy-state attacks) are out of simulator scope; the
  attack taxonomy documents them as P2/RESEARCH ONLY.
- Measurement-device-independent or CV-MDI variants.
- Unidimensional vs four-state CV variants beyond GMCS Gaussian modulation.

Rationale for the single-protocol choice (decision D-003 confirmed, D-008):

- Sources 3, 4, 10 in `docs/research-landscape.md` (the closest prior work: HMM
  calibration-attack recognition, GNN attack detection, deep-learning multi-attack
  detection) are all CV-QKD — the literature neighborhood we must differentiate
  from is CV-based.
- CV telemetry is continuous and naturally temporal (quadratures, T̂, ε̂, SKR) —
  the richest substrate for trajectory/precursor modeling.
- The Gaussian channel model is expressible in numpy/scipy with closed-form
  per-block statistics — no new dependencies, fully reproducible.
- A second protocol (decoy-state BB84) would double the attack surface and halve
  the depth per attack; master prompt §13 warns explicitly against shallow
  fake support for two protocols.

## 4. Adversary model

| Property | Assumption |
|---|---|
| Location | All-powerful at the quantum channel and at Bob's optical input (standard QKD Eve); may also be a **malicious insider** able to perturb detector electronics or LO calibration (calibration/LO attack class). |
| Quantum capabilities | Intercept/resend, tap insertion, bright-light injection (jamming/blinding), LO attenuation. Limited by physics (no-cloning; measurement noise). |
| Classical capabilities | NONE in Phase 1: the authenticated classical channel is not attackable, and post-processing hosts are uncompromised. |
| Stealth goal | Eve wants the key WITHOUT tripping conventional monitors (QBER/ε̂ thresholds). Attacks that merely DoS the link are lower-value but included (availability asset). |
| Attack onset | Precise per attack: `attack_onset` = first simulation block in which the malicious mechanism modifies system state (see `docs/attack-taxonomy.md` per-attack onset definitions). NOT "first abnormal telemetry". |

Out-of-model threats (documented, not simulated in Phase 1): Trojan-horse probing
(requires multi-wavelength source model — P2), detector-blinding with faked states
(requires a measurement-control model — P2), wavelength-dependent detector
exploits (P2), RF side-channel attacks on hardware (RESEARCH ONLY).

## 5. Trust boundaries

```text
[Alice host]  --quantum channel (UNTRUSTED: Eve's domain)-->  [Bob optical front-end]
     |                                                              |
  authenticated classical channel (TRUSTED in Phase 1)           [Bob electronics]
     |                                                              |
[post-processing hosts (TRUSTED in Phase 1)] ---telemetry---> [early-warning monitor (ours)]
```

- The early-warning monitor trusts telemetry timestamps and sensor readings as
  produced by the (simulated) hardware. A compromised sensor feed is an
  out-of-model threat in Phase 1.
- Ground-truth channel state (T_true, ε_true) is visible to the SIMULATOR for
  label generation but is exported as evaluation-only columns — never model
  features (the real monitor would not see it).

## 6. Assets and what "attack" means per asset

| Asset | Attack classes (Phase 1) | Security meaning |
|---|---|---|
| Key secrecy | intercept-resend; LO manipulation (hidden excess noise) | Eve gains information; conventional indicators under-report |
| Measurement integrity | detector calibration manipulation | noise under-estimated → secret-key rate over-estimated (false security) |
| Availability | channel jamming / saturation | key distribution denied; obvious telemetry signature |
| Detection integrity (system-level) | any stealthy attack | the early-warning system's reason to exist: warn BEFORE thresholds cross |

## 7. Security metrics the monitor sees (conventional baselines)

Full rationale and threshold values: `docs/evaluation-protocol.md`. Summary:

- excess-noise estimate ε̂ vs confidence-bound threshold (parameter-estimation bound),
- secret-key-rate estimate K̂ vs minimum acceptable rate,
- SNR, LO power deviation, detector saturation flags, timing-residual alarms.

The Phase 1 question (master prompt §58): does telemetry move BEFORE these
thresholds cross, in a way distinguishable from benign drift? The simulator is
built to answer this honestly, including "no" for sudden-onset attacks.
