# Graph Hypothesis — Graph-Model Decision Gate (Phase 4, §31–§37)

Created 2026-10-09, BEFORE any graph-model implementation (Phase 4 prompt §31: the
gate document precedes the GNN; §18/STEP 18). This document answers the three
mandatory questions and records the gate decision.

## 1. What information would the graph represent?

The physical dependency structure of the protected CV-QKD system:

```text
Source (modulator V_A)
  ↓ signal flow
Quantum Channel (T̂, ξ̂, background)
  ↓ measurement
Receiver/Detector (efficiency, gain/offset, saturation)
  ↓ derived
Security Metrics (SKR, ε̂-bias, imbalance, SNR)
```

with additional nodes for: local oscillator (power, modulation), timing
(clock offset/drift/jitter), environment (temperature, fiber loss, background),
and edges for physical dependency (source→channel→receiver), signal flow
(measurement chain), measurement dependency (metrics derive from detector +
channel state), and subsystem relationship (environment couples into LO/excess
noise/detector; timing couples into arrival residuals).

## 2. Why is this information not already captured by the feature/sequence model?

**It is not clear that it is missing.** The honest analysis:

1. **Feature-level coupling is already explicit.** The 154-feature layer (schema v2)
   includes per-column derivatives, rolling statistics, CUSUM/KS change-point
   features — computed PER TELEMETRY COLUMN independently. Cross-component
   RELATIONSHIPS (e.g. ε̂ moving while P_LO is stable = calibration signature;
   ε̂ and P_LO moving together = LO signature) exist as coefficient combinations a
   linear model can form, and as input features a GRU/TCN can combine at the
   hidden layer.
2. **The confounder structure is already in the feature set.** Environment→telemetry
   coupling (temperature→LO power, det efficiency) is represented by the telemetry
   columns themselves; the model sees every component's trajectory. What a graph
   adds over this is message-passing STRUCTURE — a fixed weighted combination of
   neighboring node features. But the physical graph here is a CHAIN
   (source→channel→receiver→detector): message passing over a chain of depth ≤ 3
   with per-node feature trajectories is expressively equivalent to a linear model
   over the concatenated features (the adjacency is a fixed linear mixing matrix).
3. **The Phase 4 empirical evidence does not show a cross-component gap.** The
   ablation (A/B/C/D) tests whether temporal/cross-time features add value; the
   per-family results show the gradual-attack signal is carried by the mean-shift
   features (ε̂/cal-gain/LO-power ramps), and sudden attacks have NO pre-onset
   signal by construction (class C — correct physics). There is no observed
   failure mode of the form "the model cannot distinguish which COMPONENT moved"
   — the attribution problem in Phase 2/3 was benign-drift alarming (dataset
   design), not component-confusion, and it is now measured per attack family.

### Concrete testable value hypothesis (for the record)

> Attack precursors manifest as cross-component interactions whose temporal
> relationships cannot be adequately represented by independently engineered
> feature trajectories.

**Test outcome on the current simulator**: NOT SUPPORTED. The precursors in the
simulator are SINGLE-COMPONENT ramp drifts (LO power ramp; calibration gain ramp;
jamming variance step). Their telemetry signatures are column-wise mean shifts —
precisely what independently engineered per-column features (d1/d2, rolling mean,
OLS slopes) capture. No cross-component interaction exists in the data-generating
process that a graph could exploit: the attack acts on ONE subsystem, and the
environment couplings are already explicit in the telemetry.

## 3. Why the graph gate is HOLD (not PROCEED, not REJECT)

- **Not PROCEED**: no concrete missing capability is identified (§32 test above);
  the physical graph is a shallow chain whose message passing is a fixed linear
  mixing of features the logistic/sequence models already see; Phase 4 evidence
  (ablation + per-family CIs) shows no component-confusion failure mode.
- **Not REJECT**: the evidence is specific to THIS simulator and telemetry
  representation. A richer simulator (multi-component coordinated attacks, cascade
  failures, spatially distributed topology) could produce cross-component precursor
  structure that a graph model would capture. The gate question remains open for
  future data, and the graph design (architecture-v1.md Part B) is documented.
- **HOLD rationale (§42)**: logistic ≈ GRU ≈ TCN on the larger dataset (Phase 3
  finding, re-verified in Phase 4 multi-split evaluation). Sequence models appear
  sufficient for the current simulator and telemetry representation. Building a
  GNN to satisfy the original architecture idea would be leaderboard-driven, not
  evidence-driven (master prompt §42: "do not build a GNN simply to satisfy the
  original architecture idea").

## 4. What would change the gate to PROCEED

1. A simulator extension with COORDINATED multi-component attacks (e.g. LO
   manipulation + calibration manipulation launched together with a staged
   schedule) where the onset timing relationship between components carries the
   predictive signal.
2. Evidence from the feature layer that per-column features cannot separate
   attack families whose signatures differ only in cross-component timing (a
   demonstrated component-confusion failure mode).
3. A paired experiment showing graph message passing improves ATTRIBUTED lead
   time (the primary operational dimension) over the sequence baselines.

None of these exist in Phase 4; none is fabricated here.
