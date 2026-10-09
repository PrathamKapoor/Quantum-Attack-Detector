# Architecture v1 — Simulator Package & Proposed Graph Representation

Created 2026-10-08 (Phase 1). Two parts: (A) the implemented Phase 1 simulator
architecture (actual module names — verified against src/), and (B) the PROPOSED
graph representation for later phases (design only — no GNN is trained in Phase 1,
master prompt §26).

## Part A — Simulator architecture (implemented, Phase 1)

```text
src/quantumattack/
    __init__.py              package metadata, SCHEMA_VERSION
    dataset.py               column classes (METADATA/LABEL/EVAL_ONLY/FEATURE),
                             RESTRICTED_COLUMNS invariant
    features.py              causal derived features (candidate set, feature-spec.md)

    simulator/
        __init__.py
        config.py            dataclass configs + validation (fail loudly on invalid)
        clock.py             seeded block clock (block index ↔ ms; monotonic)
        scenario.py          scenario runner: normal evolution + drift + precursor
                             + attack intervention + telemetry collection
        protocols/
            __init__.py
            cvqkd.py         GMCS CV-QKD protocol: per-block Gaussian statistics,
                             parameter estimation, SKR estimate
        channel/
            __init__.py
            optical.py       fiber channel state: loss, tap, background, excess noise
        detectors/
            __init__.py
            homodyne.py      balanced heterodyne detector: gain/offset/imbalance/
                             efficiency, quadrature measurement, saturation
        environment/
            __init__.py
            drift.py         benign confounders: temperature, LO thermal coupling,
                             detector efficiency wander, background OU+spikes,
                             clock drift (all seeded, all benign)
        attacks/
            __init__.py
            base.py          AttackModule interface (step(state, clock) + onset logic)
            intercept_resend.py   class C sudden: T tap + ε add at onset
            lo_manipulation.py    class A gradual: LO attenuation ramp → ε̂ bias
            calibration_manipulation.py  class A gradual: gain/offset ramp
            channel_jamming.py    class B probes (optional) then C full jamming
        telemetry/
            __init__.py
            collector.py     per-block record assembly (feature columns from state)
        labels/
            __init__.py
            builder.py       state_label, current_attack, y_H per horizon,
                             drift episode ids — from onset metadata only
        export/
            __init__.py
            parquet.py       per-scenario Parquet + batch manifest writer
        generate.py          CLI entry: python -m quantumattack.simulator.generate
```

Design rationale (master prompt §19/§20):

- one module per physical subsystem — attacks modify ONLY the subsystem they
  physically affect (channel/LO/detector), never global state directly;
- config-first: every scenario is a dataclass config validated at construction
  (invalid physical configs raise, e.g. onset outside duration, negative loss);
- benign randomness and attack randomness use separate seeded streams
  (`(seed, "environment")` vs `(seed, "attack")`) — matched-counterfactual pairs
  preserve the benign trajectory bit-exactly (dataset-spec §3);
- no model code inside simulation code; features are a separate layer;
- labels are derived AFTER simulation from onset metadata, never carried in state.

## Part B — Proposed graph representation (DESIGN ONLY)

Heterogeneous graph per telemetry block (later phases; requires torch+graph stack —
NOT installed in Phase 1, per dependency policy D-005):

### Nodes

| Node | Meaning | Candidate node features (causal) |
|---|---|---|
| `source` | Alice's modulator | mod_variance, rep_rate (public params) |
| `channel` | quantum channel state | transmittance, fiber_loss_db, background, snr |
| `lo` | local oscillator | lo_power, lo_variance, lo_sig_ratio, lo_drift |
| `detector` | Bob's detector (single node Phase 1; per-arm later) | det_gain, det_offset, det_imbalance, det_efficiency, saturation_frac, x_var, p_var |
| `timing` | timing subsystem | arr_residual, jitter_ns, clock_offset_ns, clock_drift_ppb |
| `security` | QKD metric subsystem | skr_estimate, qber_proxy, secret_fraction, skr_drift |
| `environment` | environmental state | temperature, det_temperature |

### Edges

| Edge (u → v) | Type | Meaning |
|---|---|---|
| source → channel | physical flow | states travel through fiber |
| channel → detector | physical flow | received states measured |
| lo → detector | physical flow | LO provides phase reference |
| channel → security | measurement relationship | (T̂, ξ̂) feed SKR |
| detector → security | measurement relationship | quadrature stats feed SKR |
| environment → lo | dependency | temperature couples into LO power |
| environment → detector | dependency | temperature couples into detector gain |
| environment → timing | dependency | clock discipline |
| detector → timing | correlation | arrival residuals measured at detector |
| security → security (self, temporal) | temporal relationship | SKR autocorrelation |

Edge features (later): weight = current correlation or physical coupling strength;
temporal edges carry lag-1 structure.

### Temporal update semantics

- nodes hold per-block feature vectors (history windowed to L blocks by the model);
- static topology (Phase 1 graph is a fixed 7-node heterograph — topology itself
  carries no time information);
- temporal relationships enter as edge features (correlations) and via the sequence
  model over node histories (temporal GNN later).

### Explicit stance (master prompt §44) & Phase 4 Gate Outcome

Do NOT assume GNN > sequence model. The benchmark ladder (threshold detector →
logistic regression → random forest → xgboost → MLP → GRU/LSTM → TCN → lightweight
transformer → GNN → temporal GNN → temporal GNN + next-state prediction → + OOD →
optional QML augmentation) was systematically evaluated through Phase 4.

**Phase 4 Graph Decision Gate Outcome: HOLD** (D-032, `docs/graph-hypothesis.md`).
- Precursors in the CV-QKD digital twin are single-component ramp drifts (LO power ramp, calibration gain ramp, probe pulse train); their telemetry manifestations are column-wise mean shifts.
- The 154-feature causal layer already captures all available temporal drift signal (H=100 AUROC 0.847, 85-100% warning rate on gradual attacks).
- The physical graph is a shallow chain (source -> channel -> receiver -> detector) whose message passing represents a fixed linear combination of features already accessible to linear and recurrent models.
- Deep sequence models (GRU/TCN) showed no attributable lead-time advantage over logistic regression (GRU H=10 AUROC 0.625 on test vs logistic 0.792).
- GNN implementation is held until a multi-component simulator extension demonstrates genuine cross-component precursor interactions.

QML (qiskit 2.5.1 + aer 0.17.2 installed) remains out of scope for early warning. Telemetry features are frozen under `docs/feature-freeze-v1.md` with explicit PREDICTED vs CONFIRMED architectural outputs.
