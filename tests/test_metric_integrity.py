"""Metric-integrity regression tests (docs/reliability-evaluation-protocol.md).

Covers the three defects found by inspection:
  * block<->second conversion must use BLOCK_MS (factor-of-ten guard),
  * horizon-valid forecasting must not credit out-of-horizon warnings,
  * warning timestamps must be causal (never backdated).

These are behavioural invariants, not assertions of arbitrary constants.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantumattack.simulator.config import BLOCK_MS  # noqa: E402
from quantumattack.temporal_units import (  # noqa: E402
    blocks_to_seconds, seconds_to_blocks, blocks_to_ms, blocks_to_symbols,
    horizon_seconds, verify_time_base, seconds_per_block,
)
from quantumattack.forecast_horizons import (  # noqa: E402
    classify_warning_outcome, is_horizon_valid, horizon_coverage_fraction,
    HORIZON_VALID, EXTENDED_ALERT, ONSET_DETECTION, POST_ONSET_CONFIRMATION,
    NO_WARNING,
)
from quantumattack.statistics import wilson_interval, _norm_ppf  # noqa: E402


# --------------------------------------------------------------------------
# Temporal unit correctness (factor-of-ten guard)
# --------------------------------------------------------------------------
def test_block_is_ten_milliseconds_not_one_hundred():
    """The project's time base is 1 block = 10 ms. A 0.1 s/block convention
    is wrong by exactly a factor of ten and must never reappear."""
    assert BLOCK_MS == 10.0
    assert seconds_per_block == pytest.approx(0.01)


def test_blocks_to_seconds_regression_values():
    """These specific values appeared inflated 10x in Phase 5 reporting."""
    assert blocks_to_seconds(78) == pytest.approx(0.78)   # reported as 7.8 s
    assert blocks_to_seconds(99) == pytest.approx(0.99)   # reported as 9.9 s
    assert blocks_to_seconds(147) == pytest.approx(1.47)  # reported as 14.7 s
    assert blocks_to_seconds(228) == pytest.approx(2.28)  # reported as 22.8 s


def test_horizon_durations_match_documented_table():
    """docs/time-semantics.md §7 declares H=10/25/50/100 as 0.1/0.25/0.5/1.0 s."""
    assert horizon_seconds(10) == pytest.approx(0.1)
    assert horizon_seconds(25) == pytest.approx(0.25)
    assert horizon_seconds(50) == pytest.approx(0.5)
    assert horizon_seconds(100) == pytest.approx(1.0)


def test_conversions_round_trip():
    for blocks in (0.0, 1.0, 78.0, 100.0, 2000.0):
        assert seconds_to_blocks(blocks_to_seconds(blocks)) == pytest.approx(blocks)
    assert blocks_to_ms(100) == pytest.approx(1000.0)
    assert blocks_to_symbols(1) == pytest.approx(1e6)


def test_conversions_propagate_none():
    assert blocks_to_seconds(None) is None
    assert blocks_to_ms(None) is None
    assert blocks_to_symbols(None) is None


def test_verify_time_base_records_conversion():
    rec = verify_time_base()
    assert rec["block_ms"] == BLOCK_MS
    assert rec["seconds_per_block"] == pytest.approx(0.01)
    assert "factor of ten" in rec["note"]


# --------------------------------------------------------------------------
# Forecast horizon semantics
# --------------------------------------------------------------------------
def test_warning_inside_horizon_is_horizon_valid():
    """Onset at t+H exactly is INSIDE the closed horizon (t, t+H] -> valid."""
    out = classify_warning_outcome(warning_block=900, onset_block=1000, horizon=100)
    assert out.outcome == HORIZON_VALID
    assert out.horizon_valid is True
    assert out.lead_blocks == 100


def test_warning_just_inside_horizon_is_valid():
    out = classify_warning_outcome(warning_block=901, onset_block=1000, horizon=100)
    assert out.outcome == HORIZON_VALID
    assert out.lead_blocks == 99


def test_warning_just_beyond_horizon_is_extended_alert_not_forecast():
    """Lead = H+1: a real pre-onset alert, but the H-forecast claim was FALSE."""
    out = classify_warning_outcome(warning_block=899, onset_block=1000, horizon=100)
    assert out.outcome == EXTENDED_ALERT
    assert out.horizon_valid is False
    assert out.is_pre_onset is True   # still an anticipatory capability
    assert out.lead_blocks == 101


def test_far_beyond_horizon_is_still_extended_alert():
    out = classify_warning_outcome(warning_block=433, onset_block=1000, horizon=100)
    assert out.outcome == EXTENDED_ALERT
    assert out.horizon_valid is False


def test_warning_at_onset_is_detection_not_forecast():
    out = classify_warning_outcome(warning_block=1000, onset_block=1000, horizon=100,
                                   grace_blocks=5)
    assert out.outcome == ONSET_DETECTION
    assert out.horizon_valid is False


def test_post_onset_warning_is_confirmation():
    out = classify_warning_outcome(warning_block=1050, onset_block=1000, horizon=100)
    assert out.outcome == POST_ONSET_CONFIRMATION
    assert out.is_pre_onset is False


def test_no_warning_and_benign_scenario_are_no_warning():
    assert classify_warning_outcome(None, 1000, 100).outcome == NO_WARNING
    # benign: no onset exists
    assert classify_warning_outcome(500, -1, 100).outcome == NO_WARNING
    assert classify_warning_outcome(500, None, 100).outcome == NO_WARNING


def test_classification_is_exclusive_and_covers_the_vocabulary():
    """Every (warning, onset, horizon) triple maps to exactly one outcome."""
    seen = set()
    for onset in (1000,):
        for warn in (500, 899, 900, 901, 995, 999, 1000, 1001, 1200):
            o = classify_warning_outcome(warn, onset, 100, grace_blocks=5)
            assert o.outcome in {HORIZON_VALID, EXTENDED_ALERT, ONSET_DETECTION,
                                 POST_ONSET_CONFIRMATION, NO_WARNING}
            seen.add(o.outcome)
    assert HORIZON_VALID in seen and POST_ONSET_CONFIRMATION in seen


def test_is_horizon_valid_helper():
    assert is_horizon_valid(50, 100) is True
    assert is_horizon_valid(100, 100) is True
    assert is_horizon_valid(101, 100) is False
    assert is_horizon_valid(0, 100) is False
    assert is_horizon_valid(-5, 100) is False
    assert is_horizon_valid(None, 100) is False


def test_horizon_coverage_fraction_undefined_when_no_warnings():
    assert horizon_coverage_fraction([], 100) is None
    assert horizon_coverage_fraction([None, None], 100) is None


def test_horizon_coverage_fraction_counts_only_valid():
    leads = [50, 80, 101, 200, None]
    # 4 present warnings, 2 of them within H=100
    assert horizon_coverage_fraction(leads, 100) == pytest.approx(0.5)


def test_invalid_horizon_rejected():
    with pytest.raises(ValueError):
        classify_warning_outcome(10, 100, 0)


def test_horizon_validity_shrinks_as_horizon_shrinks():
    """A lead of 150 blocks is horizon-valid at H=200 but not at H=100."""
    assert classify_warning_outcome(850, 1000, 200).horizon_valid is True
    assert classify_warning_outcome(850, 1000, 100).horizon_valid is False


# --------------------------------------------------------------------------
# Warning causality (no retrospective backdating)
# --------------------------------------------------------------------------
def _policy_frame(prob_col, values, onset, blocks=None):
    n = len(values)
    blocks = list(range(n)) if blocks is None else blocks
    return pd.DataFrame({
        "scenario_id": ["s"] * n,
        "block_index": blocks,
        "attack_onset": [onset] * n,
        "attack_type": ["lo_manipulation"] * n,
        "scenario_class": ["ATTACK"] * n,
        prob_col: values,
    })


def test_warning_timestamp_is_first_block_of_run_not_backdated():
    """The live warning time must be the FIRST block of the K-run, i.e. the
    earliest block at which the operator could have known the threshold was met
    on K consecutive samples."""
    from quantumattack.baselines.warnings import warning_blocks_for_scenario, WarningPolicy
    pol = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50)
    # p crosses at block 500 and stays high; K=3 -> first fire must be 500
    vals = [0.0] * 500 + [0.9] * 10
    df = _policy_frame("p_attack_future_h100", vals, onset=1000)
    fires = warning_blocks_for_scenario(df, 100, pol)
    assert fires == [500], f"warning backdated; expected first causal block 500, got {fires}"


def test_sustained_policy_does_not_move_the_warning_timestamp():
    """sustained_until_onset filters WHICH warnings survive using future onset,
    but must never shift a retained warning earlier than its causal run start."""
    from quantumattack.baselines.warnings import warning_blocks_for_scenario, WarningPolicy
    pol = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50,
                        sustained_until_onset=True)
    vals = [0.0] * 500 + [0.9] * 500
    df = _policy_frame("p_attack_future_h100", vals, onset=1000)
    fires = warning_blocks_for_scenario(df, 100, pol, sustained_until_onset=True)
    assert fires[0] == 500


def test_transient_spike_is_not_a_warning_under_sustained_policy():
    """A 3-block spike followed by a drop must NOT produce a warning when the
    sustained policy is active (it would be a false alarm in operation)."""
    from quantumattack.baselines.warnings import warning_blocks_for_scenario, WarningPolicy
    pol = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50,
                        sustained_until_onset=True)
    vals = [0.0] * 500 + [0.9] * 3 + [0.0] * 497
    df = _policy_frame("p_attack_future_h100", vals, onset=1000)
    fires = warning_blocks_for_scenario(df, 100, pol, sustained_until_onset=True)
    assert fires == []


def test_on_time_warning_precedes_onset_and_lead_is_positive():
    from quantumattack.baselines.warnings import lead_time, WarningPolicy
    pol = WarningPolicy(prob_threshold=0.5, persistence_k=3)
    vals = [0.0] * 800 + [0.9] * 200
    df = _policy_frame("p_attack_future_h100", vals, onset=1000)
    from quantumattack.baselines.warnings import warning_blocks_for_scenario
    fires = warning_blocks_for_scenario(df, 100, pol)
    assert lead_time(1000, fires) == 200.0


# --------------------------------------------------------------------------
# Statistical correctness
# --------------------------------------------------------------------------
def test_wilson_interval_matches_independent_computation():
    """Verified against an independent Acklam-normal + Wilson formula."""
    o = wilson_interval(9, 10)
    assert o.point == pytest.approx(0.9)
    assert o.ci_low == pytest.approx(0.5958499729, abs=1e-9)
    assert o.ci_high == pytest.approx(0.9821237869, abs=1e-9)


def test_wilson_interval_is_nondegenerate_at_zero_and_one():
    """A 0/7 or 7/7 outcome must NOT be reported with a zero-width interval."""
    zero = wilson_interval(0, 7)
    assert zero.ci_low == pytest.approx(0.0)
    # exact Wilson upper bound for 0/7 at 95% is 0.3543 (NOT 0.0)
    assert zero.ci_high == pytest.approx(0.3543304354, abs=1e-9)
    one = wilson_interval(7, 7)
    assert one.ci_high == pytest.approx(1.0)
    # exact Wilson lower bound for 7/7 at 95% is 0.6457 (NOT 1.0)
    assert one.ci_low == pytest.approx(0.6456695646, abs=1e-9)
    thirty = wilson_interval(0, 30)
    assert thirty.ci_high == pytest.approx(0.1135, abs=1e-3)


def test_wilson_interval_is_within_unit_range():
    for k in range(0, 21):
        o = wilson_interval(k, 20)
        assert 0.0 <= o.ci_low <= o.ci_high <= 1.0


def test_wilson_empty_group_is_undefined_not_zero():
    o = wilson_interval(0, 0)
    assert o.point is None and o.ci_low is None and o.ci_high is None


def test_wilson_rejects_impossible_counts():
    with pytest.raises(ValueError):
        wilson_interval(5, 3)
    with pytest.raises(ValueError):
        wilson_interval(-1, 3)


def test_norm_ppf_matches_scipy():
    from scipy.stats import norm
    for q in (0.5, 0.975, 0.99, 0.995):
        assert _norm_ppf(q) == pytest.approx(float(norm.ppf(q)), abs=1e-8)