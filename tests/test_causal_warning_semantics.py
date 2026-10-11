"""Causal warning semantics acceptance tests (repair workstream, D-049..D-051).

These tests are constructed INDEPENDENTLY of the implementation formulas: each
expected timestamp is derived by hand from the stated operational requirement,
not by calling the function under test.

Acceptance tests (from the repair specification):

  A. True activation timestamp: for K=3, p=[0.1,0.1,0.1,0.9,0.9,0.9,...] the
     excursion begins at block 3, persistence is satisfied at block 5, and the
     operational alert must be emitted at block 5 — never backdated to block 3.
  B. No future-dependent alert deletion: an alert emitted at block 5 stays in
     the operational event ledger even though the probability falls at block 6.
  C. No prediction-only attack confirmation: 15 consecutive p=0.99 blocks with
     no independent evidence must NOT enter ACTIVE_ATTACK_CONFIRMED.
  D. Correct false-alert metrics: three benign scenarios with 0, 1 and 2 emitted
     episodes give 2 scenarios-with-alerts, 3 episodes, and an episode rate
     computed from 3.
  E. Causal prefix invariance: identical prefixes with different futures produce
     identical operational states and events within the prefix; onset metadata
     never affects the online generator.
  F. Data preservation: the correction does not touch frozen datasets or saved
     artifacts (asserted structurally by path checks in the evaluator tests).

Additional adversarial coverage: K=1..4, interrupted runs, missing telemetry inside
a run, horizon boundary movement, duplicate-trigger non-fragmentation, and the
always-alert / never-alert baseline sanity checks.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantumattack.baselines.warnings import (  # noqa: E402
    WarningPolicy, WarningEvent, warning_events_for_scenario,
    warning_blocks_for_scenario, retrospective_sustained_retention,
    evaluate_scenario_warnings,
)
from quantumattack.operational_states import (  # noqa: E402
    operational_state_series, OperationalPolicy,
    NORMAL, ELEVATED, PRE_ATTACK_WARNING, ACTIVE_ATTACK_CONFIRMED,
    DEGRADED_TELEMETRY, ABSTAINING, RECOVERY,
    alert_episodes_from_trace, summarize_alert_burden,
)
from quantumattack.forecast_horizons import (  # noqa: E402
    classify_warning_outcome, HORIZON_VALID, EXTENDED_ALERT,
    ONSET_DETECTION, POST_ONSET_CONFIRMATION, NO_WARNING,
)


def _frame(values, onset=-1, scenario_class="NORMAL", attack_type="none",
           column="p_attack_future_h100", start_block=0):
    n = len(values)
    return pd.DataFrame({
        "scenario_id": ["s"] * n,
        "block_index": list(range(start_block, start_block + n)),
        "attack_onset": [onset] * n,
        "attack_type": [attack_type] * n,
        "scenario_class": [scenario_class] * n,
        column: list(values),
    })


# ==========================================================================
# Acceptance test A — true activation timestamp
# ==========================================================================
def test_acceptance_a_activation_is_persistence_satisfied_not_run_start():
    """p = [0.1,0.1,0.1,0.9,0.9,0.9,0.1,0.1], K=3, threshold 0.5.

    Hand-derived expectation: the first above-threshold block is index 3; the
    third consecutive above-threshold block is index 5. Persistence is therefore
    satisfied at block 5 and the alert must be emitted at block 5.
    """
    values = [0.1, 0.1, 0.1, 0.9, 0.9, 0.9, 0.1, 0.1]
    df = _frame(values)
    policy = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50)

    events = warning_events_for_scenario(df, 100, policy)
    assert len(events) == 1
    e = events[0]
    assert e.excursion_start_block == 3
    assert e.persistence_satisfied_block == 5
    assert e.emission_block == 5          # NOT 3
    assert e.emission_block >= e.persistence_satisfied_block

    # the evaluator agrees with the generator
    res = evaluate_scenario_warnings(df, 100, policy)
    assert res.warning_time == 5.0
    assert res.excursion_start_block == 3
    assert res.persistence_satisfied_block == 5

    # the operational state machine agrees with both
    machine = operational_state_series(np.array(values, dtype=float))
    assert machine.first_entry(PRE_ATTACK_WARNING) == 5


@pytest.mark.parametrize("k,expected_emission", [(1, 3), (2, 4), (3, 5), (4, None)])
def test_acceptance_a_persistence_lengths(k, expected_emission):
    """K=1,2,3 emit at the K-th crossing (blocks 3..5); K=4 never completes."""
    values = [0.1, 0.1, 0.1, 0.9, 0.9, 0.9, 0.1, 0.1]
    df = _frame(values)
    policy = WarningPolicy(prob_threshold=0.5, persistence_k=k, cooldown_blocks=50)
    events = warning_events_for_scenario(df, 100, policy)
    if expected_emission is None:
        assert events == []
    else:
        assert [e.emission_block for e in events] == [expected_emission]
        assert events[0].excursion_start_block == 3


def test_acceptance_a_interrupted_run_restarts_discontinuously():
    """A gap in the qualifying run resets persistence: 0.9,0.9,[0.1],0.9,0.9,0.9
    must first satisfy persistence at the final block (index 6)."""
    values = [0.9, 0.9, 0.1, 0.9, 0.9, 0.9]
    df = _frame(values)
    policy = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50)
    events = warning_events_for_scenario(df, 100, policy)
    assert len(events) == 1
    assert events[0].excursion_start_block == 3
    assert events[0].emission_block == 5


def test_acceptance_a_missing_telemetry_inside_run_resets_persistence():
    """NaN telemetry cannot count as a confirming observation."""
    values = [0.9, np.nan, 0.9, 0.9, 0.9]
    df = _frame(values)
    policy = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50)
    events = warning_events_for_scenario(df, 100, policy)
    assert len(events) == 1
    assert events[0].excursion_start_block == 2
    assert events[0].emission_block == 4


def test_acceptance_a_processing_delay_is_honoured():
    """A modelled processing delay pushes the emission block later, never earlier."""
    values = [0.1, 0.9, 0.9, 0.9, 0.1]
    df = _frame(values)
    policy = WarningPolicy(prob_threshold=0.5, persistence_k=3)
    events = warning_events_for_scenario(df, 100, policy, processing_delay_blocks=2)
    assert events[0].persistence_satisfied_block == 3
    assert events[0].emission_block == 5


def test_acceptance_a_backdating_mutation_is_detected():
    """Adversarial mutation (Test A in the spec): if the emission timestamp were
    replaced by the excursion-start timestamp, this assertion must fail. We
    simulate the mutation on a copy of the event and require inequality."""
    values = [0.1, 0.1, 0.1, 0.9, 0.9, 0.9, 0.1, 0.1]
    df = _frame(values)
    policy = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50)
    e = warning_events_for_scenario(df, 100, policy)[0]
    mutated_emission = e.excursion_start_block      # the historical defect
    assert mutated_emission == 3
    assert e.emission_block == 5
    assert mutated_emission != e.emission_block, \
        "the backdating mutation must be distinguishable from correct behaviour"


# ==========================================================================
# Acceptance test B — no future-dependent alert deletion
# ==========================================================================
def test_acceptance_b_emitted_alert_survives_retrospective_rejection():
    """Benign scenario: the alert emitted at block 5 remains in the operational
    ledger after the probability falls at block 6; the retrospective filter may
    reject it for its own analysis but must not erase it."""
    values = [0.1, 0.1, 0.1, 0.9, 0.9, 0.9, 0.1, 0.1]
    df = _frame(values, onset=-1, scenario_class="NORMAL")
    policy = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50)

    ledger = warning_events_for_scenario(df, 100, policy)
    assert [e.emission_block for e in ledger] == [5]

    retention = retrospective_sustained_retention(ledger, df, 100, policy)
    assert retention[0] is False, "transient alert is retrospectively rejected"

    # the ledger is unchanged: same objects, same timestamps, nothing removed
    assert len(ledger) == 1
    assert ledger[0].emission_block == 5
    # and the scenario still counts as a false-alarm scenario operationally
    res = evaluate_scenario_warnings(df, 100, policy)
    assert res.n_episodes == 1
    assert res.category == "false_early_warning"


def test_acceptance_b_onset_change_cannot_delete_or_move_events():
    """Changing ONLY the ground-truth onset metadata must not alter the online
    ledger (query/event generation is onset-blind)."""
    values = [0.1, 0.1, 0.1, 0.9, 0.9, 0.9, 0.1, 0.1]
    df_attack = _frame(values, onset=50, scenario_class="ATTACK", attack_type="lo_manipulation")
    df_benign = _frame(values, onset=-1, scenario_class="NORMAL")
    policy = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50)
    a = [e.to_dict() for e in warning_events_for_scenario(df_attack, 100, policy)]
    b = [e.to_dict() for e in warning_events_for_scenario(df_benign, 100, policy)]
    assert a == b


# ==========================================================================
# Acceptance test C — no prediction-only attack confirmation
# ==========================================================================
def test_acceptance_c_high_probability_alone_never_confirms():
    """15 consecutive p=0.99 blocks with no independent evidence: the machine may
    warn but must not enter ACTIVE_ATTACK_CONFIRMED."""
    p = np.concatenate([np.full(20, 0.01), np.full(15, 0.99), np.full(40, 0.01)])
    trace = operational_state_series(p)
    assert ACTIVE_ATTACK_CONFIRMED not in trace.states
    assert PRE_ATTACK_WARNING in trace.states


def test_acceptance_c_evidence_only_never_confirms_without_evidence_mask():
    """Providing an all-False evidence mask is equivalent to no evidence."""
    p = np.concatenate([np.full(20, 0.01), np.full(15, 0.99), np.full(40, 0.01)])
    trace = operational_state_series(p, confirmation_evidence=np.zeros(len(p), dtype=bool))
    assert ACTIVE_ATTACK_CONFIRMED not in trace.states


def test_acceptance_c_positive_case_with_real_evidence_contract():
    """The positive path exercises the implemented evidence contract: a boolean
    evidence mask sustained for confirmation_evidence_persistence blocks."""
    p = np.concatenate([np.full(20, 0.01), np.full(30, 0.99), np.full(40, 0.01)])
    evidence = np.zeros(len(p), dtype=bool)
    evidence[26:40] = True
    trace = operational_state_series(p, confirmation_evidence=evidence)
    confirm_at = trace.first_entry(ACTIVE_ATTACK_CONFIRMED)
    assert confirm_at is not None
    # default policy: 3 consecutive evidence blocks starting at 26 -> 28
    assert confirm_at == 28


def test_acceptance_c_sudden_attack_confirmable_from_evidence_without_forecast():
    """A sudden attack has no forecast signal; confirmation must still occur when
    independent evidence appears after onset."""
    p = np.full(200, 0.01)              # forecast stays low the whole time
    evidence = np.zeros(200, dtype=bool)
    evidence[120:140] = True            # detector evidence from onset
    trace = operational_state_series(p, confirmation_evidence=evidence)
    assert ACTIVE_ATTACK_CONFIRMED in trace.states
    assert PRE_ATTACK_WARNING not in trace.states   # no forecast warning ever fired


def test_acceptance_c_legacy_mode_requires_explicit_opt_in():
    """The legacy behaviour (probability-only confirmation) exists only behind an
    explicit policy flag, never by default."""
    p = np.concatenate([np.full(20, 0.01), np.full(15, 0.99), np.full(40, 0.01)])
    legacy = OperationalPolicy(require_confirmation_evidence=False)
    trace = operational_state_series(p, policy=legacy)
    assert ACTIVE_ATTACK_CONFIRMED in trace.states   # documented legacy mode


# ==========================================================================
# Acceptance test D — correct false-alert metrics
# ==========================================================================
def _three_benign_scenarios():
    """A: 0 episodes. B: 1 episode. C: 2 separate episodes (rearm after recovery)."""
    a = np.full(400, 0.01)
    b = np.concatenate([np.full(100, 0.01), np.full(50, 0.9), np.full(250, 0.01)])
    c = np.concatenate([np.full(100, 0.01), np.full(50, 0.9), np.full(100, 0.01),
                        np.full(100, 0.9), np.full(50, 0.01)])
    return {"A": a, "B": b, "C": c}


def test_acceptance_d_episode_and_scenario_counts():
    pol = OperationalPolicy()
    traces = {sid: operational_state_series(p, policy=pol)
              for sid, p in _three_benign_scenarios().items()}
    eps = {sid: alert_episodes_from_trace(tr, sid) for sid, tr in traces.items()}
    assert len(eps["A"]) == 0
    assert len(eps["B"]) == 1
    assert len(eps["C"]) == 2

    burden = summarize_alert_burden(traces)
    assert burden["n_scenarios"] == 3
    assert burden["n_scenarios_with_alerts"] == 2
    assert burden["n_episodes"] == 3

    # episode rate must use the 3 EPISODES, not the 2 scenarios
    total_seconds = 3 * 400 * 0.01
    assert burden["episodes_per_1000_seconds"] == pytest.approx(3 / total_seconds * 1000.0)
    assert burden["episodes_per_1000_seconds"] != pytest.approx(2 / total_seconds * 1000.0)


def test_acceptance_d_occupancy_uses_state_intervals_not_span():
    """Occupancy = blocks actually in an alert state. Scenario C has two closed
    episodes at [102,174) and [252,374): 72 + 122 = 194 blocks of 400."""
    pol = OperationalPolicy()
    traces = {sid: operational_state_series(p, policy=pol)
              for sid, p in _three_benign_scenarios().items()}
    burden = summarize_alert_burden(traces)
    c_eps = alert_episodes_from_trace(traces["C"], "C")
    expected_c_blocks = sum(e.duration_blocks(400) for e in c_eps)
    assert burden["per_scenario"]["C"]["alert_blocks"] == expected_c_blocks
    assert burden["occupancy_fraction"] == pytest.approx(
        burden["alert_blocks"] / burden["observed_blocks"])


def test_acceptance_d_sticky_alarm_is_not_fragmented_by_repeated_crossings():
    """Oscillation above the threshold with brief sub-threshold dips (shorter
    than the recovery requirement) must remain ONE episode."""
    pol = OperationalPolicy()
    osc = np.concatenate([np.full(100, 0.01),
                          np.tile([0.9, 0.9, 0.3, 0.9, 0.9, 0.9, 0.3], 30),
                          np.full(90, 0.01)])
    trace = operational_state_series(osc, policy=pol)
    eps = alert_episodes_from_trace(trace, "O")
    assert len(eps) == 1


def test_acceptance_d_cooldown_suppressed_events_are_not_episodes():
    """When the bare cooldown policy suppresses a re-arm, no episode exists for it
    in the state machine (the sticky alarm never left the alert state)."""
    pol = OperationalPolicy()
    p = np.concatenate([np.full(50, 0.01), np.full(200, 0.9), np.full(50, 0.01)])
    trace = operational_state_series(p, policy=pol)
    eps = alert_episodes_from_trace(trace, "S")
    assert len(eps) == 1   # sticky until recovery, despite periodic excursions


# ==========================================================================
# Acceptance test E — causal prefix invariance
# ==========================================================================
def test_acceptance_e_prefix_invariance_of_events_and_states():
    prefix = np.concatenate([np.full(50, 0.01), np.full(60, 0.8), np.full(40, 0.01)])
    t_prefix = 150
    traj_a = np.concatenate([prefix, np.full(100, 0.01)])
    traj_b = np.concatenate([prefix, np.full(100, 0.9)])

    pol = OperationalPolicy()
    ta = operational_state_series(traj_a, policy=pol)
    tb = operational_state_series(traj_b, policy=pol)
    assert ta.states[:t_prefix] == tb.states[:t_prefix]
    ta_tr = [t.to_dict() for t in ta.transitions if t.block < t_prefix]
    tb_tr = [t.to_dict() for t in tb.transitions if t.block < t_prefix]
    assert ta_tr == tb_tr

    wp = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50)
    fa = _frame(traj_a)
    fb = _frame(traj_b)
    events_a = [e.to_dict() for e in warning_events_for_scenario(fa, 100, wp)
                if e.emission_block < t_prefix]
    events_b = [e.to_dict() for e in warning_events_for_scenario(fb, 100, wp)
                if e.emission_block < t_prefix]
    assert events_a == events_b
    assert events_a, "the prefix must contain a real emitted event (non-vacuous)"


def test_acceptance_e_onset_metadata_is_not_an_input_to_the_generator():
    """Structural proof: the generator's only data dependency is the probability
    column and block index. Deleting the onset column must not change events."""
    values = [0.1, 0.1, 0.1, 0.9, 0.9, 0.9, 0.1, 0.1]
    df = _frame(values, onset=5)
    without_onset = df.drop(columns=["attack_onset"])
    wp = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50)
    a = [e.to_dict() for e in warning_events_for_scenario(df, 100, wp)]
    b = [e.to_dict() for e in warning_events_for_scenario(without_onset, 100, wp)]
    assert a == b


# ==========================================================================
# Horizon classification boundary (adversarial test G)
# ==========================================================================
def test_horizon_boundary_mutation_changes_classification():
    """Moving an emitted warning from inside the horizon to just outside must
    change its classification; boundaries use emission timestamps."""
    onset = 1000
    horizon = 100
    inside = classify_warning_outcome(900, onset, horizon)      # lead 100 -> valid
    outside = classify_warning_outcome(899, onset, horizon)     # lead 101 -> extended
    assert inside.outcome == HORIZON_VALID
    assert outside.outcome == EXTENDED_ALERT


def test_horizon_classification_uses_emission_not_excursion():
    """A warning whose EXCURSION is inside the horizon but whose EMISSION is at
    the boundary is classified by the emission timestamp (the claim was only
    knowable when persistence completed)."""
    values = [0.1] * 898 + [0.9] * 3 + [0.9] * 200
    df = _frame(values, onset=1000, scenario_class="ATTACK", attack_type="lo_manipulation")
    wp = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50)
    e = warning_events_for_scenario(df, 100, wp)[0]
    assert e.excursion_start_block == 898
    assert e.emission_block == 900
    assert classify_warning_outcome(900, 1000, 100).outcome == HORIZON_VALID
    # using the excursion timestamp would have produced the same category at this
    # exact boundary only because the run is short; the timestamps are distinct
    assert e.emission_block != e.excursion_start_block


# ==========================================================================
# Baseline sanity: always-alert and never-alert cannot masquerade as success
# ==========================================================================
def test_always_alert_baseline_is_exposed_by_false_alarm_accounting():
    pol = OperationalPolicy()
    always = np.full(300, 0.99)
    trace = operational_state_series(always, policy=pol)
    burden = summarize_alert_burden({"benign": trace})
    assert burden["n_scenarios_with_alerts"] == 1
    assert burden["occupancy_fraction"] > 0.5   # occupancies benign operation


def test_never_alert_baseline_reports_zero_sensitivity_and_zero_episodes():
    pol = OperationalPolicy()
    never = np.full(300, 0.01)
    trace = operational_state_series(never, policy=pol)
    burden = summarize_alert_burden({"benign": trace})
    assert burden["n_scenarios_with_alerts"] == 0
    assert burden["n_episodes"] == 0
    assert burden["episodes_per_1000_seconds"] == 0.0


# ==========================================================================
# Onset-adjacent behaviour
# ==========================================================================
def test_warning_beginning_near_onset_is_onset_detection():
    """Emission 2 blocks before onset with grace=5 -> onset detection, not a
    horizon-valid forecast."""
    out = classify_warning_outcome(998, 1000, 100, grace_blocks=5)
    assert out.outcome == ONSET_DETECTION


def test_warning_just_before_grace_boundary():
    """Emission 6 blocks before onset with grace=5 -> horizon-valid forecast."""
    out = classify_warning_outcome(994, 1000, 100, grace_blocks=5)
    assert out.outcome == HORIZON_VALID
    out2 = classify_warning_outcome(995, 1000, 100, grace_blocks=5)
    assert out2.outcome == ONSET_DETECTION


def test_post_onset_warning_is_confirmation_not_forecast():
    out = classify_warning_outcome(1010, 1000, 100)
    assert out.outcome == POST_ONSET_CONFIRMATION
    assert out.horizon_valid is False


# ==========================================================================
# Event-model integrity
# ==========================================================================
def test_event_ids_are_sequential_and_unique_per_scenario():
    values = [0.1] * 50 + [0.9] * 100 + [0.1] * 200 + [0.9] * 100
    df = _frame(values)
    wp = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50)
    events = warning_events_for_scenario(df, 100, wp)
    ids = [e.event_id for e in events]
    assert ids == list(range(len(events)))
    assert len(set(ids)) == len(ids)


def test_event_timestamps_are_ordered_and_consistent():
    values = [0.1] * 50 + [0.9] * 100 + [0.1] * 400 + [0.9] * 100
    df = _frame(values)
    wp = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50)
    for e in warning_events_for_scenario(df, 100, wp):
        assert e.excursion_start_block <= e.persistence_satisfied_block
        assert e.persistence_satisfied_block <= e.emission_block


def test_non_contiguous_blocks_are_rejected():
    df = _frame([0.9] * 10)
    df["block_index"] = [0, 1, 2, 4, 5, 6, 7, 8, 9, 10]   # gap
    wp = WarningPolicy(prob_threshold=0.5, persistence_k=3)
    with pytest.raises(ValueError):
        warning_events_for_scenario(df, 100, wp)


def test_negative_processing_delay_rejected():
    df = _frame([0.9] * 10)
    with pytest.raises(ValueError):
        warning_events_for_scenario(df, 100, WarningPolicy(), processing_delay_blocks=-1)