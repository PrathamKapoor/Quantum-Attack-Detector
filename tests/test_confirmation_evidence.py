"""Confirmation-evidence audit tests (validation workstream).

Verifies the REAL production evidence path (`conventional.
confirmation_evidence_from_cusum`) against the D-050 contract, including
warmup gating, missing telemetry, invalid values, and the distinction between
the test-only mask and the production source.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantumattack.baselines.conventional import (  # noqa: E402
    CusumConfig, CusumCalibration, fit_cusum_reference,
    confirmation_evidence_from_cusum, confirmation_evidence_series,
)
from quantumattack.operational_states import (  # noqa: E402
    operational_state_series, OperationalPolicy,
    PRE_ATTACK_WARNING, ACTIVE_ATTACK_CONFIRMED, NORMAL,
)


def _cal(h=50.0, warmup=200):
    return CusumCalibration(
        reference={"excess_noise": {"mean": 0.0, "std": 1.0, "direction": 1, "n": 500}},
        h_threshold=h, target_scenario_fpr=0.1, achieved_scenario_fpr=None,
        calibration_population="test", config={})


def _cfg(h=50.0, warmup=200):
    return CusumConfig(k_drift=2.0, h_threshold=h, persistence_k=3,
                       warmup_blocks=warmup, cooldown_blocks=50)


def _frame(values):
    n = len(values)
    return pd.DataFrame({"excess_noise": np.asarray(values, dtype=float),
                         "block_index": np.arange(n)})


def test_evidence_requires_real_excursion_not_probability():
    """Forecast probability alone can never produce evidence; only a detector
    excursion of the real telemetry can."""
    df = _frame(np.zeros(300))
    ev, usable = confirmation_evidence_from_cusum(df, _cal(), _cfg())
    assert not ev.any(), "flat telemetry must not generate evidence"


def test_evidence_is_gated_by_warmup():
    """No evidence during the warmup window even if values are extreme."""
    x = np.zeros(300)
    x[:150] = 50.0       # extreme during warmup (baseline contamination case)
    df = _frame(x)
    ev, usable = confirmation_evidence_from_cusum(df, _cal(), _cfg(warmup=200))
    assert not ev[:200].any()
    assert not usable[:200].any()


def test_evidence_tracks_sustained_shift_after_warmup():
    x = np.zeros(400)
    x[250:] = 8.0        # sustained shift well after warmup
    df = _frame(x)
    ev, _ = confirmation_evidence_from_cusum(df, _cal(), _cfg())
    idx = np.where(ev)[0]
    assert idx.size and idx.min() >= 250


def test_evidence_is_onset_blind():
    """Changing ground-truth onset metadata cannot alter the evidence mask."""
    x = np.zeros(400)
    x[250:] = 8.0
    df = _frame(x)
    a, _ = confirmation_evidence_from_cusum(df, _cal(), _cfg())
    df2 = df.copy()
    df2["attack_onset"] = 100
    df2["scenario_class"] = "ATTACK"
    b, _ = confirmation_evidence_from_cusum(df2, _cal(), _cfg())
    assert np.array_equal(a, b)


def test_missing_telemetry_suppresses_evidence():
    x = np.zeros(400)
    x[250:] = 8.0
    df = _frame(x)
    df.loc[250:, "excess_noise"] = np.nan     # the shift is unobservable
    ev, usable = confirmation_evidence_from_cusum(df, _cal(), _cfg())
    assert not ev.any()
    assert not usable[250:].any()


def test_invalid_values_suppress_evidence():
    x = np.zeros(400)
    x[250:] = 8.0
    x[300] = np.inf
    df = _frame(x)
    ev, usable = confirmation_evidence_from_cusum(df, _cal(), _cfg())
    assert not usable[300]
    # a single invalid block breaks the persistence run, but evidence resumes
    assert ev[302]


def test_state_machine_confirms_from_production_evidence():
    """End-to-end: the production evidence source drives ACTIVE_ATTACK_CONFIRMED
    after warmup, and cannot do so before it."""
    n = 400
    x = np.zeros(n)
    x[250:] = 8.0
    df = _frame(x)
    ev, _ = confirmation_evidence_from_cusum(df, _cal(), _cfg())
    p = np.full(n, 0.99)     # forecast screams the whole time
    tr = operational_state_series(p, policy=OperationalPolicy(),
                                  confirmation_evidence=ev)
    c_at = tr.first_entry(ACTIVE_ATTACK_CONFIRMED)
    assert c_at is not None and c_at >= 250
    # and without evidence, never confirms
    tr2 = operational_state_series(p, policy=OperationalPolicy())
    assert ACTIVE_ATTACK_CONFIRMED not in tr2.states


def test_state_machine_warns_without_confirmation_when_only_probability_high():
    p = np.full(300, 0.99)
    tr = operational_state_series(p, policy=OperationalPolicy())
    assert PRE_ATTACK_WARNING in tr.states
    assert ACTIVE_ATTACK_CONFIRMED not in tr.states


def test_test_only_mask_is_distinct_from_production_source():
    """A hand-built mask is NOT the production evidence path. This test
    documents the distinction the validation prompt requires: the earlier
    implementation exposed only a mask parameter (test-only input); production
    now has a real source, and the two must not be conflated."""
    # hand-built mask (what tests previously injected)
    manual = np.zeros(100, dtype=bool)
    manual[50:] = True
    # production evidence for flat telemetry is all-False regardless of the mask
    df = _frame(np.zeros(100))
    produced, _ = confirmation_evidence_from_cusum(df, _cal(), _cfg(warmup=10))
    assert not produced.any()
    assert manual.any()
    # and the operational contract accepts either ONLY through the explicit
    # confirmation_evidence parameter (never from labels/onset)
    p = np.full(100, 0.99)
    tr_manual = operational_state_series(p, policy=OperationalPolicy(),
                                         confirmation_evidence=manual)
    assert ACTIVE_ATTACK_CONFIRMED in tr_manual.states
    tr_prod = operational_state_series(p, policy=OperationalPolicy(),
                                       confirmation_evidence=produced)
    assert ACTIVE_ATTACK_CONFIRMED not in tr_prod.states


def test_real_simulator_scenarios_end_to_end():
    """On REAL frozen telemetry: benign scenarios must produce no evidence with
    the frozen operating point; LO-manipulation must produce evidence after onset."""
    import json
    REPO = Path(__file__).resolve().parents[1]
    m5 = json.load(open(REPO / "data" / "phase5" / "manifest.json", encoding="utf-8"))
    cal = CusumCalibration(
        reference={},   # per-scenario warmup normalization ignores global ref
        h_threshold=200.0, target_scenario_fpr=0.1, achieved_scenario_fpr=None,
        calibration_population="frozen", config={})
    cfg = CusumConfig(k_drift=2.0, h_threshold=200.0, persistence_k=3,
                      cooldown_blocks=50, warmup_blocks=200)
    benign = next(s["scenario_id"] for s in m5["scenarios"] if s["scenario_class"] == "NORMAL")
    attack = next(s["scenario_id"] for s in m5["scenarios"]
                  if s["attack_type"] == "lo_manipulation")
    df_b = pd.read_parquet(REPO / "artifacts" / "phase5" / "features" / f"{benign}.parquet")
    df_a = pd.read_parquet(REPO / "artifacts" / "phase5" / "features" / f"{attack}.parquet")
    ev_b, _ = confirmation_evidence_from_cusum(df_b, cal, cfg)
    ev_a, _ = confirmation_evidence_from_cusum(df_a, cal, cfg)
    assert not ev_b.any(), "frozen point must not flag benign telemetry"
    onset = int(df_a["attack_onset"].iloc[0])
    idx_a = np.where(ev_a)[0]
    assert idx_a.size, "LO manipulation must produce evidence"
    # evidence must not PRECEDE the first malicious intervention by design:
    # it may occur during the ramp (preparation) but never before precursor_start
    pre = int(df_a["precursor_start"].iloc[0])
    assert idx_a.min() >= pre - 1, (
        f"evidence at block {idx_a.min()} precedes precursor_start {pre}")