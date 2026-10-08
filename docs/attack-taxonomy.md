# Attack Taxonomy

Created 2026-10-08 (Phase 1). Covers the master-prompt attack families against QKD.
Scope discipline: only the four P0 attacks are implemented in Phase 1, all CV-QKD.
DV-protocol attacks are documented but NOT implemented (simulator supports CV-QKD only,
per decision D-008 in decisions.md).

Columns per attack: protocol applicability, attacked subsystem, physical mechanism,
expected telemetry effects, conventional detection indicators, plausible precursor?,
precursor confidence, expected onset type, simulation difficulty, scientific value,
implementation priority (P0 = implement first; P1 = after simulator foundation;
P2 = later extension; RESEARCH ONLY = insufficient confidence for implementation).

Precursor classes referenced below are defined in `docs/precursor-taxonomy.md`:
A = gradual, B = weak, C = no precursor / sudden onset, D = unknown.

## Summary table

| # | Attack | Family | Protocol applicability | Priority | Precursor class | Onset type |
|---|---|---|---|---|---|---|
| 1 | Intercept-resend | eavesdropping | CV-QKD, BB84, decoy-BB84 | P0 | C (sudden) | sudden |
| 2 | LO (local-oscillator) manipulation | source/reference | CV-QKD only | P0 | A (gradual, configurable) | gradual-then-operational |
| 3 | Detector calibration manipulation | detector | CV-QKD, BB84 (wavelength/Trojan variants P2) | P0 | A (gradual, configurable) | gradual-then-operational |
| 4 | Channel jamming / saturation | denial-of-service | CV-QKD, BB84, decoy-BB84 | P0 | B (weak, recon probing) then C | weak-probe then sudden |
| 5 | Photon-number splitting | eavesdropping | decoy-BB84, weak-coherent BB84 only | P2 | D | UNKNOWN |
| 6 | Beam splitting | eavesdropping | CV-QKD (passive tap), weak-coherent BB84 | P2 | D | UNKNOWN |
| 7 | Time-shift | detector/timing | BB84-family (SPAD detectors) | P2 | D | UNKNOWN |
| 8 | Detector blinding (+ faked-state) | detector | BB84-family; CV variants studied | P2 | D | UNKNOWN |
| 9 | Trojan horse | source | any with modulator + fragile isolators | P2 | D | UNKNOWN |
| 10 | Wavelength-dependent attack | detector | BB84-family, CV variants | P2 | D | UNKNOWN |
| 11 | Calibration attack (HMM-studied, CV) | detector/electronics | CV-QKD | merged into #3 (P0) | see #3 | see #3 |
| 12 | Saturation attack (detector) | detector | CV-QKD, BB84 | merged into #4 (P0, jamming family) | see #4 | see #4 |
| 13 | Local-oscillator manipulation (Calabrese/comm-class) | source/reference | CV-QKD | merged into #2 (P0) | see #2 | see #2 |
| 14 | Mixed / composite attacks | any | any | P1 (composition framework only) | n/a | n/a |
| 15 | Unknown / unseen attacks | any | any | evaluation partition (P1) | n/a | n/a |

## Detailed entries (implemented P0 attacks)

### 1. Intercept-resend (P0)

| Field | Content |
|---|---|
| Protocol applicability | CV-QKD (primary), BB84, decoy-BB84 |
| Attacked subsystem | quantum channel |
| Physical mechanism | Eve splits off a fraction of each pulse (or measures a copy); draws her sample from the received mode; forwards a replacement state to Bob. In the Gaussian model: channel transmittance drops by tap fraction, excess noise increases from the resend imperfection and Eve's measurement |
| Expected telemetry effects | T̂ (transmittance estimate) drops stepwise; ε̂ (excess noise) rises; SNR falls; SKR estimate falls; quadrature variance shifts (re-sent states carry Eve's measurement noise) |
| Conventional detection indicators | ε̂ above parameter-estimation confidence bound; SKR below abort threshold; T̂ deviation from channel budget |
| Plausible precursor? | **No (class C).** Eve has no preparation phase visible in-channel: a beam splitter is passive and leaves no signature before activation; the resend mechanism acts from the first intercepted block. Precursor would require Eve to test the tap with visible probing — that IS the attack, not a precursor |
| Precursor confidence | HIGH confidence in "no precursor" (physical argument: passive tap + no test phase). Project inference, physics-grounded |
| Expected onset type | sudden (step change in T_true, ε_true at onset block) |
| Simulation difficulty | LOW — closed-form Gaussian channel modification |
| Scientific value | HIGH — canonical sudden-onset control; anchors the "attacks can be sudden" requirement |
| Implementation priority | P0 |

**Onset definition:** `attack_onset` = first block b where the tap is inserted and
resend begins, i.e. where (T_true, ε_true) switch from benign to attacked values.
Tap fraction is constant from onset to end (no ramp unless explicitly configured as
a separate RESEARCH variant). Lead time measured against this block.

### 2. Local-oscillator (LO) manipulation (P0)

| Field | Content |
|---|---|
| Protocol applicability | CV-QKD only (LO is a CV concept) |
| Attacked subsystem | local oscillator / Bob's reference arm (insider or physical-access adversary) |
| Physical mechanism | Adversary attenuates the LO power (or biases its calibration) so Bob's measured quadrature variance is scaled down; parameter estimation then UNDER-estimates excess noise ε̂ → SKR over-estimated → false security. This is the attack class studied with HMMs in landscape source 3 (Mao et al. 2020) |
| Expected telemetry effects | LO power drops gradually; measured quadrature variance scales with LO²; ε̂ estimate biased low; SNR distorted; SKR inflated (false-security signature); LO/signal ratio drifts |
| Conventional detection indicators | LO power monitor deviation; ε̂-vs-T̂ consistency check; SKR-vs-SNR plausibility bounds |
| Plausible precursor? | **Yes, class A (gradual) — configurable.** Physical justification: rebalancing an LO path (moving a filter wheel, adjusting an attenuator, thermal re-tuning of an inline element) is a physical process that takes many blocks and leaves a slow drift signature before the attack's effective regime. This is PROJECT INFERENCE (synthetic research assumption, physics-plausible), labeled as such in precursor-taxonomy |
| Precursor confidence | MEDIUM — mechanism plausible, no direct literature evidence of real-world precursor telemetry |
| Expected onset type | gradual-then-operational: LO power ramps during precursor window; attack_onset = first block where attenuation reaches the attack operating point and ε̂ bias becomes effective |
| Simulation difficulty | MEDIUM — must couple LO scaling into quadrature statistics and parameter estimation consistently |
| Scientific value | HIGH — the canonical "stealthy, gradual, insider" attack; primary candidate for early-warning research; literature-adjacent (source 3) |
| Implementation priority | P0 |

**Onset definition:** `attack_onset` = first block where LO attenuation ≥ configured
attack level (attenuation follows a stochastic ramp from `precursor_start`). The
ε̂-bias mechanism is considered "operational" from that block even though LO power
was already drifting before it — this is exactly the NORMAL → PRECURSOR → ATTACK
progression, and it is NOT imposed on other attacks.

### 3. Detector calibration manipulation (P0; absorbs "calibration attack" family)

| Field | Content |
|---|---|
| Protocol applicability | CV-QKD (BB84 variants via wavelength/Trojan attacks are P2) |
| Attacked subsystem | Bob's detector electronics (gain/offset of the balanced homodyne detectors) |
| Physical mechanism | Adversary with electronics access (insider; or compromised calibration routine) slowly biases detector gain/offset. Consequence: measured quadrature statistics are distorted so that estimated channel parameters (T̂, ε̂) look BETTER than reality; key is generated with over-estimated security |
| Expected telemetry effects | detector gain/offset telemetry drifts; quadrature means shift (offset); quadrature variance shifts (gain); ε̂ biased; SKR biased; detector-imbalance drift |
| Conventional detection indicators | periodic recalibration deltas; detector imbalance monitor; ε̂-vs-T̂ consistency |
| Plausible precursor? | **Yes, class A (gradual) — configurable.** Justification: electronics bias drifts (thermal or adversarial) accumulate over many blocks; a malicious bias is deliberately introduced as a slow ramp to stay under recalibration triggers. PROJECT INFERENCE, physics-plausible. Note: benign calibration drift ALSO produces gain/offset drift (see confounders) — this attack is the hardest to separate from benign behavior, which is scientifically the point |
| Precursor confidence | MEDIUM — mechanism plausible (landscape source 3 studies CV-QKD calibration attacks with HMMs on quadratures); precursor ramp itself is a synthetic assumption |
| Expected onset type | gradual-then-operational: gain/offset ramps from precursor_start; attack_onset = first block where the biased calibration crosses the configured attack operating point |
| Simulation difficulty | MEDIUM |
| Scientific value | HIGH — deliberately confusable with benign calibration drift; the acid test for "drift ≠ attack" |
| Implementation priority | P0 |

**Onset definition:** `attack_onset` = first block where biased gain/offset crosses
the configured operating point (bias ramps from `precursor_start`).

### 4. Channel jamming / saturation (P0; absorbs "saturation attack")

| Field | Content |
|---|---|
| Protocol applicability | CV-QKD, BB84, decoy-BB84 (any link-based protocol) |
| Attacked subsystem | quantum channel + Bob's detector front-end (saturation) |
| Physical mechanism | Eve injects bright light into the channel (availability attack): background noise level rises sharply; in CV-QKD, quadrature measurement variance is inflated and the detectors can saturate at high power. Optionally preceded by LOW-power reconnaissance probing (Eve characterizing the link before jamming) |
| Expected telemetry effects | background estimate rises; quadrature variance inflates; saturation fraction rises; SNR collapses; SKR collapses; T̂ distorted by background subtraction |
| Conventional detection indicators | background-light monitor; saturation flags; SKR abort; SNR floor |
| Plausible precursor? | **Weak, class B (configurable) then C.** Optional precursor: intermittent low-power probe pulses (Eve ranging the link) produce small background blips — statistically weak, easily confused with ambient background fluctuation. The jamming itself is sudden (class C). The precursor is a PROJECT INFERENCE (synthetic research assumption); it must NOT be enabled by default for all jamming scenarios |
| Precursor confidence | LOW-MEDIUM — probing behavior is plausible for a careful adversary but entirely synthetic |
| Expected onset type | weak-probe (optional) then sudden full jamming at attack_onset |
| Simulation difficulty | LOW-MEDIUM — background + saturation model straightforward; probe-pulse model simple shot-level extension |
| Scientific value | MEDIUM-HIGH — availability-asset attack; distinct telemetry signature (variance/saturation vs mean shifts); provides a sudden-onset member with an optional weak precursor |
| Implementation priority | P0 |

**Onset definition:** `attack_onset` = first block of full-power jamming. Probe
bursts (if enabled) occur in `[precursor_start, attack_onset)` and are telemetry
events only — they do NOT move attack_onset and are NOT labeled ATTACK.

## Detailed entries (documented, NOT implemented — P2/RESEARCH ONLY)

### 5. Photon-number splitting (P2)

Applies to weak-coherent-pulse BB84/decoy-BB84 only — NOT to the CV-QKD simulator
(coherent states have no photon-number basis for PNS). Mechanism: Eve performs
quantum non-demolition photon-number measurement, blocks single-photon pulses,
splits multi-photon pulses. Telemetry (in a DV twin): single-photon yield drop,
decoy-state gain anomalies. Precursor: UNKNOWN (no defensible model). Priority P2 —
requires a decoy-state BB84 protocol module (later phase).

### 6. Beam splitting (P2)

Passive tap on weak-coherent BB84 (in CV-QKD it degenerates into the intercept-resend
tap modeled in P0 #1). Precursor: UNKNOWN. P2.

### 7. Time-shift (P2)

Exploits SPAD detector efficiency vs timing (BB84-family). CV-QKD homodyne has no
gated-SPAD timing vulnerability of this form — out of simulator scope. Precursor:
UNKNOWN. P2.

### 8. Detector blinding (+ faked-state) (P2)

Bright-light control of SPADs (BB84-family). CV analogues studied in literature but
require a detector control-loop model we do not build in Phase 1. Precursor: UNKNOWN
(proposed mechanisms exist but no defensible telemetry model). P2.

### 9. Trojan horse (P2)

Eve sends light INTO Alice's/Bob's apparatus through the channel; reflected modulation
leaks key material. Requires multi-wavelength source/isolator model — out of Phase 1
scope. Precursor: UNKNOWN. P2.

### 10. Wavelength-dependent attack (P2)

Detector efficiency vs wavelength exploit (BB84-family/CV variants). Requires
wavelength-resolved channel model. Precursor: UNKNOWN. P2.

### 11-13. Calibration attack / saturation attack / LO manipulation (merged)

Families 11 (HMM-studied CV calibration attack) and 13 (LO manipulation) merge into
P0 #3 and P0 #2 respectively: same subsystem, same telemetry surface, same modeling
path. Family 12 (detector saturation) merges into P0 #4. Merging is recorded in
decisions.md (D-011).

### 14. Mixed / composite attacks (P1 — framework only)

Phase 1 implements the attack-composition interface (`simulator/attacks/base.py`)
so multiple attack modules can be active in one scenario, but Phase 1 does not
ship composite scenarios. Composite scenarios are P1 dataset work.

### 15. Unknown / unseen attacks (evaluation partition, P1)

No simulator module. Dataset partitions must hold out entire attack families for
open-set evaluation later (concept documented in `docs/dataset-spec.md` §OOD).

## Onset-type mixture requirement (master prompt §11)

The four P0 attacks deliberately produce a mixed onset/precursor structure:

| Attack | Precursor class | Onset type |
|---|---|---|
| intercept-resend | C — none | sudden step |
| LO manipulation | A — gradual stochastic ramp | gradual-then-operational |
| detector calibration manipulation | A — gradual stochastic ramp | gradual-then-operational |
| channel jamming | B — weak optional probes, then C | probe-then-sudden |

plus benign drift (class-B-like trajectories, no attack) and benign sudden
disturbances (e.g., environmental shock transients, no attack) as hard negatives.
Sanity checks in `tests/` prevent every attack from sharing one precursor shape
(`tests/test_precursor_semantics.py`).
