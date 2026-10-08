# Precursor Taxonomy

Created 2026-10-08 (Phase 1). THE central Phase 1 design artifact: for each prioritized
attack, whether the simulator supports a precursor, its form, and its evidence level.

## Evidence-level legend (applies to every entry)

- **LITERATURE** — supported by a source in `docs/research-landscape.md` read at
  full-text level. (None of our precursors currently reach this level.)
- **PROJECT INFERENCE** — synthetic research assumption, physics-plausible, NOT
  observed in literature or hardware. Clearly labeled per entry below.
- **PHYSICAL ARGUMENT** — follows from QKD physics; not a behavioral observation.

## Precursor classes

| Class | Meaning | Simulator support |
|---|---|---|
| **A. Gradual** | Attack preparation causes observable drift before formal attack onset | stochastic ramp mechanism, configurable |
| **B. Weak** | Small statistical changes exist but are hard to distinguish from normal variation | weak-probe/burst mechanism, configurable, off by default |
| **C. No precursor / sudden onset** | Attack begins abruptly; no warning signal inserted | step change at onset; simulator MUST NOT inject any pre-onset signal |
| **D. Unknown** | Evidence insufficient to justify a precursor model | not modeled |

Rule (master prompt §32): never invent precursor behavior because it makes prediction
easier. Sudden attacks get NO synthetic warning signal — a strong model must sometimes
correctly conclude "no reliable early warning was possible".

## Per-attack precursor specifications

### Attack 1: intercept-resend — class C (no precursor)

| Property | Specification |
|---|---|
| Affected telemetry | none before onset |
| Physical justification | beam-splitter tap is passive; Eve's resend acts from the first intercepted block. Any visible pre-attack probing would itself be an attack (detectable event), not a precursor |
| Mathematical form | none — T_true, ε_true switch stepwise at `attack_onset` |
| Duration distribution | n/a |
| Magnitude distribution | n/a |
| Stochastic variation | n/a |
| Relationship to onset | precursor_start = attack_onset (no precursor interval) |
| Confounding benign conditions | benign channel-attenuation drift also moves T̂ — but gradually, not stepwise |
| Confidence/evidence | HIGH confidence in no-precursor — PHYSICAL ARGUMENT |

### Attack 2: LO manipulation — class A (gradual, PROJECT INFERENCE)

**LABEL: PROJECT INFERENCE — synthetic research assumption.** Physics-plausible
(rebalancing an LO path is a physical process taking many blocks); no literature
evidence that real attackers produce this telemetry. It exists to give the forecasting
task a defensible gradual-onset member, NOT as a claim about real adversaries.

| Property | Specification |
|---|---|
| Affected telemetry | LO power (slow decrease), LO variance (slight increase), quadrature variance (scales with LO²), LO/signal ratio |
| Physical justification | an attenuator/filter element inserted or re-tuned in the LO path changes power over a finite mechanical/thermal timescale; a careful adversary ramps slowly to stay under LO monitors |
| Mathematical form | LO power multiplier: `g(t) = 1 − A · s(t)` where `s(t) ∈ [0,1]` is a stochastic ramp: Ornstein-Uhlenbeck process in ramp space, absorbed at 1: `s(t+1) = clip(s(t) + θ·(1−s(t))·dt + σ·√dt·N(0,1), 0, 1)` starting at `s(precursor_start) = s0 > 0` (configurable jump-start) |
| Duration distribution | ramp duration ~ configurable `[ramp_min, ramp_max]` blocks (Phase 1 default: 40–120 blocks of 20 ms = 0.8–2.4 s) |
| Magnitude distribution | final attenuation A ~ configurable range (Phase 1 default: 0.3–0.7 linear attenuation) |
| Stochastic variation | OU noise on the ramp (σ configurable); never a deterministic linear ramp |
| Relationship to onset | `precursor_start < attack_onset`; `attack_onset` = first block where `g(t) ≤ 1 − A_target` (attenuation reaches operating point). ε̂-bias mechanism active from `attack_onset` only |
| Confounding benign conditions | benign LO thermal drift (slow power wander, no direction); benign calibration drift. Model must NOT equate "LO power moving" with "attack" |
| Confidence/evidence | MEDIUM — PROJECT INFERENCE, physics-plausible |

### Attack 3: detector calibration manipulation — class A (gradual, PROJECT INFERENCE)

**LABEL: PROJECT INFERENCE — synthetic research assumption.** Same caveat as attack 2.

| Property | Specification |
|---|---|
| Affected telemetry | detector gain telemetry (drift), detector offset telemetry (drift), quadrature mean (offset²), quadrature variance (gain²), detector imbalance, ε̂ and SKR bias |
| Physical justification | electronics bias (thermal drift or adversarial injection at a test point) accumulates gradually; adversarial version ramps to stay under recalibration triggers |
| Mathematical form | gain multiplier `g(t) = 1 + G·u(t)`, offset `o(t) = O·v(t)` where `u, v` are independent OU ramps as in attack 2 with their own durations; gain and offset ramps need not be simultaneous |
| Duration distribution | per-ramp configurable `[ramp_min, ramp_max]` (Phase 1 default: 50–150 blocks) |
| Magnitude distribution | G ~ configurable (default 0.05–0.25 relative gain bias); O ~ configurable (default: 0.02–0.15 of quadrature std) |
| Stochastic variation | OU ramps; independent per-ramp starts possible (staggered precursor) |
| Relationship to onset | `attack_onset` = first block where the dominant ramp (max normalized progress) crosses its operating point |
| Confounding benign conditions | **benign calibration drift — the key confounder.** Benign drift uses the SAME stochastic form with smaller magnitude and no operating-point target. This attack is deliberately the hardest to separate from benign behavior |
| Confidence/evidence | MEDIUM — PROJECT INFERENCE, physics-plausible; landscape source 3 (Mao et al. 2020) establishes that CV-QKD calibration-attack telemetry (quadrature statistics) is learnable, not that the ramp exists |

### Attack 4: channel jamming — class B (weak probes, optional) then C (sudden)

**LABEL: the probe precursor is PROJECT INFERENCE — synthetic research assumption.**
The sudden jamming itself needs no precursor assumption.

| Property | Specification |
|---|---|
| Affected telemetry (probe phase) | background-light estimate (small blips), occasional elevated quadrature variance samples |
| Physical justification | a careful Eve ranges the link with intermittent low-power pulses before committing to full jamming; each probe raises background marginally for its duration |
| Mathematical form | probe schedule: burst count ~ Poisson(λ_probe) over `[precursor_start, attack_onset)`; each burst duration ~ Geometric(p_dur) blocks; per-burst background elevation ~ |N(μ_probe, σ_probe)|; superimposed on benign background noise |
| Duration distribution | precursor interval configurable (Phase 1 default: 30–100 blocks); bursts 1–4 blocks each |
| Magnitude distribution | per-burst elevation μ_probe ≈ 0.1–0.4 of benign background σ — deliberately WEAK (class B) |
| Stochastic variation | Poisson schedule + Gaussian magnitudes; some scenarios get ZERO probe bursts (λ_probe may be 0) |
| Relationship to onset | probes live strictly in `[precursor_start, attack_onset)`; `attack_onset` = first full-power jamming block; probes never move onset and are never labeled ATTACK |
| Confounding benign conditions | ambient background fluctuation (benign sudden disturbances produce similar blips) |
| Confidence/evidence | LOW-MEDIUM — PROJECT INFERENCE |

## Sudden-onset controls (no precursor, by design)

| Scenario | Mechanism | Purpose |
|---|---|---|
| intercept-resend (class C) | step change in T_true, ε_true at onset | canonical sudden attack |
| jamming without probes (λ_probe = 0) | step change in background power | sudden attack, availability asset |
| benign sudden disturbance (hard negative) | transient environmental shock: e.g., background spike decaying over 10–30 blocks, clock-offset step, temperature step with slow relaxation — NO attack | prevents "any sudden change ⇒ attack" shortcut |

## Precursor-class mixture check (master prompt §11)

Required dataset property: attacks must NOT all share one precursor structure. Enforced
by `tests/test_precursor_semantics.py`:

1. intercept-resend scenarios have `precursor_start == attack_onset` (no precursor interval);
2. LO/calibration scenarios (class A enabled) have `precursor_start < attack_onset` with
   stochastic (non-linear, non-monotone-per-block) ramp telemetry;
3. jamming scenarios with probes enabled have weak blips strictly inside
   `[precursor_start, attack_onset)`;
4. benign scenarios have no precursor interval and no attack;
5. across a generated batch, at least two distinct precursor classes must be present
   (mixture check).

## Environmental confounders (master prompt §12)

Benign phenomena that can resemble attack precursors. The requirement: **benign drift
must exist so the model cannot equate drift with malicious activity.**

Investigated candidates and Phase 1 disposition:

| Confounder | Resembles | Phase 1 disposition |
|---|---|---|
| Channel attenuation drift | intercept-resend T̂ drop | IMPLEMENTED — slow random-walk/OU in fiber loss (0.01–0.05 dB/km-scale wander) |
| Detector efficiency variation | calibration-manipulation gain drift | IMPLEMENTED — OU wander in detector gain (no operating-point target) |
| Background light / noise variation | jamming probes, jamming onset | IMPLEMENTED — OU background fluctuations + occasional benign spikes |
| Temperature drift | LO/calibration drift (thermal coupling) | IMPLEMENTED — slow sinusoid+OU lab temperature, coupled weakly into LO power and detector gain |
| Clock drift | timing-based attacks (not simulated) | IMPLEMENTED (telemetry only) — oscillator frequency offset random walk; arrival residual telemetry |
| Calibration drift (benign) | calibration-manipulation attack | IMPLEMENTED — small OU gain/offset wander, same form as attack ramp but smaller magnitude and no target |
| Shot-noise variation | quadrature variance shifts | PARTIALLY — shot noise is derived from LO power; its variation follows LO/confounder state |
| Fiber degradation (aging, months-scale) | long-term loss trend | NOT IMPLEMENTED in Phase 1 scenarios (timescale exceeds scenario duration); noted for later phases |
| Detector dark-count variation | background blips | NOT IMPLEMENTED (CV-QKD homodyne has no dark counts; DV concept) |

Key design rule: benign drift processes use the SAME functional forms as the attack
precursors (OU ramps, spikes) but differ in MAGNITUDE, TARGET (benign drift has no
attack operating point), and CORRELATION STRUCTURE (each benign process wanders
independently; attack ramps converge to an operating point). The simulator must not
add any marker that separates them — that separation is the learning task.
