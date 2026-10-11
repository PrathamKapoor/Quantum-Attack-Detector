"""Operational state-machine tests (docs/reliability-evaluation-protocol.md).

Every transition must be deterministic and explainable. These tests cover
normal->warning, warning recovery, sudden-onset confirmation, missing telemetry,
invalid probabilities, abstention and repeated alarms.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantumattack.operational_states import (  # noqa: E402
    operational_state_series, OperationalPolicy, OperationalTrace,
    NORMAL, ELEVATED, PRE_ATTACK_WARNING, ACTIVE_ATTACK_CONFIRMED,
    DEGRADED_TELEMETRY, ABSTAINING, RECOVERY, OPERATIONAL_STATES,
)


def test_normal_trajectory_stays_normal():
    p = np.full(200, 0.01)
    tr = operational_state_series(p)
    assert set(tr.states) == {NORMAL}


def test_elevated_then_warning_transition():
    p = np.concatenate([np.full(50, 0.01), np.full(10, 0.3), np.full(30, 0.9),
                        np.full(100, 0.01)])
    tr = operational_state_series(p)
    # ELEVATED after persistence_k blocks above the elevated threshold (block 52)
    assert tr.first_entry(ELEVATED) == 52
    # warning once p >= 0.5 for K=3 consecutive blocks (block 62)
    assert tr.first_entry(PRE_ATTACK_WARNING) == 62
    # the alarm is sticky while the condition holds, then recovers and clears
    assert tr.first_entry(RECOVERY) is not None
    assert tr.states[-1] == NORMAL


def test_warning_requires_persistence_not_single_spike():
    """A single high block must NOT raise a warning."""
    p = np.full(100, 0.01)
    p[50] = 0.99
    tr = operational_state_series(p)
    assert PRE_ATTACK_WARNING not in tr.states
    assert ACTIVE_ATTACK_CONFIRMED not in tr.states


def test_sustained_high_probability_confirms_active_attack():
    """A sudden attack is unpredictable BEFORE onset but must be confirmable
    once evidence is sustained. Warning precedes confirmation."""
    p = np.concatenate([np.full(100, 0.01), np.full(30, 0.95)])
    tr = operational_state_series(p)
    # warn at the K-th block above threshold (100 + 3 - 1 = 102)
    assert tr.first_entry(PRE_ATTACK_WARNING) == 102
    # confirm after confirm_persistence consecutive blocks (100 + 10 - 1 = 109)
    assert tr.first_entry(ACTIVE_ATTACK_CONFIRMED) == 109
    assert tr.first_entry(PRE_ATTACK_WARNING) < tr.first_entry(ACTIVE_ATTACK_CONFIRMED)


def test_missing_telemetry_degrades_rather_than_reports_normal():
    """Missing information must NOT be reported as a confident NORMAL reading."""
    pol = OperationalPolicy(reacquire_blocks=50)   # stay in abstention for the test
    p = np.full(100, 0.01)
    valid = np.ones(100, dtype=bool)
    valid[50:60] = False
    tr = operational_state_series(p, telemetry_valid=valid, policy=pol)
    assert tr.states[49] == NORMAL  # before the outage
    assert all(s == DEGRADED_TELEMETRY for s in tr.states[50:60])
    # and it must NOT immediately claim NORMAL on recovery
    assert tr.states[60] == ABSTAINING


def test_degraded_telemetry_can_transition_to_abstaining():
    """After an outage the system abstains until fresh trailing-window features
    are re-established, then resumes confident reporting."""
    pol = OperationalPolicy(reacquire_blocks=5)
    p = np.full(200, 0.9)
    valid = np.ones(200, dtype=bool)
    valid[50:52] = False
    tr = operational_state_series(p, telemetry_valid=valid, policy=pol)
    assert tr.states[50] == DEGRADED_TELEMETRY
    assert tr.states[51] == DEGRADED_TELEMETRY
    # 5 fresh blocks of abstention before confident reporting resumes
    assert tr.states[52:57] == [ABSTAINING] * 5
    # after re-acquisition the evidence counters restart, so the warning needs
    # persistence_k fresh blocks before it re-arms (this is intentional)
    assert tr.states[57] == NORMAL
    assert tr.states[57 + 3] == PRE_ATTACK_WARNING   # K=3 fresh blocks
    assert tr.first_entry(ACTIVE_ATTACK_CONFIRMED) is not None


def test_stale_telemetry_degrades():
    p = np.full(100, 0.01)
    stale = np.zeros(100, dtype=bool)
    stale[70] = True
    tr = operational_state_series(p, telemetry_stale=stale)
    assert tr.states[70] == DEGRADED_TELEMETRY


def test_nan_probability_is_treated_as_invalid_not_low_risk():
    p = np.full(100, 0.01)
    p[50] = np.nan
    tr = operational_state_series(p)
    assert tr.states[50] == DEGRADED_TELEMETRY


def test_out_of_range_probability_is_invalid():
    p = np.full(100, 0.01)
    p[50] = 1.5  # impossible probability
    tr = operational_state_series(p)
    assert tr.states[50] == DEGRADED_TELEMETRY


def test_cooldown_suppresses_repeated_alarms():
    """After a warning fires, cooldown prevents immediate re-arming."""
    pol = OperationalPolicy(cooldown_blocks=100, persistence_k=3)
    # warning at 50, dips, then rises again at 80 (inside cooldown)
    p = np.full(300, 0.01)
    p[50:60] = 0.9
    p[70:75] = 0.01
    p[80:95] = 0.9
    tr = operational_state_series(p, policy=pol)
    warnings = [t for t in tr.transitions if t.to_state == PRE_ATTACK_WARNING]
    assert len(warnings) == 1, f"cooldown should suppress the second alarm; got {warnings}"


def test_alarm_after_cooldown_expires_is_allowed():
    pol = OperationalPolicy(cooldown_blocks=20, persistence_k=3)
    p = np.full(300, 0.01)
    p[50:60] = 0.9
    p[70:75] = 0.01
    p[120:140] = 0.9   # well after cooldown
    tr = operational_state_series(p, policy=pol)
    warnings = [t for t in tr.transitions if t.to_state == PRE_ATTACK_WARNING]
    assert len(warnings) >= 2


def test_every_transition_is_deterministic_and_has_reason():
    p = np.concatenate([np.full(50, 0.01), np.full(60, 0.9), np.full(60, 0.01)])
    a = operational_state_series(p)
    b = operational_state_series(p)
    assert a.states == b.states
    assert [t.to_dict() for t in a.transitions] == [t.to_dict() for t in b.transitions]
    for t in a.transitions:
        assert t.reason, "every transition must carry a reason"
        assert t.from_state in OPERATIONAL_STATES
        assert t.to_state in OPERATIONAL_STATES


def test_no_backdating_state_is_causal():
    """Changing the future must not alter states at or before t."""
    p = np.full(200, 0.01)
    p[100:150] = 0.9
    a = operational_state_series(p)
    p2 = p.copy()
    p2[150:] = 0.99   # perturb the future only
    b = operational_state_series(p2)
    assert a.states[:150] == b.states[:150]
    assert a.states != b.states  # non-vacuous


def test_policy_validation_rejects_inconsistent_thresholds():
    with pytest.raises(ValueError):
        OperationalPolicy(elevated_threshold=0.9, warn_threshold=0.5).validate()
    with pytest.raises(ValueError):
        OperationalPolicy(persistence_k=0).validate()
    with pytest.raises(ValueError):
        OperationalPolicy(confirm_probability=0.1, warn_threshold=0.5).validate()


def test_trace_counts_and_first_entry():
    p = np.concatenate([np.full(50, 0.01), np.full(20, 0.9), np.full(30, 0.01)])
    tr = operational_state_series(p)
    counts = tr.counts()
    assert sum(counts.values()) == len(tr.states)
    assert tr.first_entry(NORMAL) == 0
    assert tr.first_entry(PRE_ATTACK_WARNING) is not None


def test_empty_series_is_handled():
    tr = operational_state_series(np.array([]))
    assert tr.states == []
    assert tr.transitions == []