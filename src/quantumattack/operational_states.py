"""Operational warning state machine (D-045).

WHY this module exists
----------------------
The project had a warning *policy* (`baselines/warnings.py`) that fires alarms,
but no explicit notion of the operating state of the monitoring system. An
operator needs to distinguish at least these situations, which are genuinely
different operational facts:

  * NORMAL — telemetry healthy, probability low.
  * ELEVATED — probability rising but persistence/threshold not yet met.
  * PRE_ATTACK_WARNING — a valid pre-onset forecast fired (see
    `forecast_horizons` for horizon-validity accounting).
  * ACTIVE_ATTACK_CONFIRMED — evidence of an ongoing attack, independent of any
    forecast. A sudden, unheralded attack is undetectable *in advance* but must
    still be detectable *once it starts*.
  * DEGRADED_TELEMETRY — measurements missing, non-finite, or stale.
  * ABSTAINING — the system declines to make a confident prediction.
  * RECOVERY — returning to normal after an alarm, under documented criteria.

WHAT
    A deterministic, fully auditable online state machine over per-block inputs.
It records every transition with its block index and reason.

WHY
    "Missing information does not prove normal operation." Conflating degraded
    telemetry with a confident low risk reading would be a genuine operational
    defect: the system would silently report safety while blind.

HOW
    `operational_state_series(...)` consumes per-block (probability, validity)
    and returns a state label per block plus a transition log. Every transition
    rule is documented, deterministic, and parameterised by an
    `OperationalPolicy` whose settings are validated on validation data only.

WHEN
    Online prediction, after the forecasting model has produced a probability
    for the current window and the telemetry-validity rules have been applied.
It is a pure function of data already available at that block.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field

import numpy as np

__all__ = [
    "NORMAL", "ELEVATED", "PRE_ATTACK_WARNING", "ACTIVE_ATTACK_CONFIRMED",
    "DEGRADED_TELEMETRY", "ABSTAINING", "RECOVERY",
    "OPERATIONAL_STATES", "ALERT_STATES",
    "OperationalPolicy", "StateTransition", "OperationalTrace",
    "AlertEpisode", "alert_episodes_from_trace", "summarize_alert_burden",
]

# --- operational states -----------------------------------------------------
NORMAL = "NORMAL"
ELEVATED = "ELEVATED"
PRE_ATTACK_WARNING = "PRE_ATTACK_WARNING"
ACTIVE_ATTACK_CONFIRMED = "ACTIVE_ATTACK_CONFIRMED"
DEGRADED_TELEMETRY = "DEGRADED_TELEMETRY"
ABSTAINING = "ABSTAINING"
RECOVERY = "RECOVERY"

OPERATIONAL_STATES = (
    NORMAL, ELEVATED, PRE_ATTACK_WARNING, ACTIVE_ATTACK_CONFIRMED,
    DEGRADED_TELEMETRY, ABSTAINING, RECOVERY,
)


@dataclass(frozen=True)
class OperationalPolicy:
    """Thresholds governing the operational state machine.

    Defaults mirror the frozen forecasting policy (P>=0.5, K=3) so behaviour is
    comparable to the historical evaluation. All values are candidate settings;
    selection belongs on validation data only.
    """

    warn_threshold: float = 0.5        # probability entering a warning
    elevated_threshold: float = 0.2    # probability entering ELEVATED
    persistence_k: int = 3            # consecutive blocks above warn_threshold
    cooldown_blocks: int = 50         # suppress re-arming after an alarm
    recovery_blocks: int = 25         # blocks below warn_threshold to recover
    reacquire_blocks: int = 10        # fresh blocks required after an outage
    max_stale_blocks: int = 1         # telemetry older than this => degraded
    confirm_probability: float = 0.9  # sustained high probability (risk evidence)
    confirm_persistence: int = 10     # consecutive blocks above confirm_probability
    # ACTIVE_ATTACK_CONFIRMED requires INDEPENDENT active-attack evidence
    # (D-050). A sustained forecast probability is a statement about possible
    # future onset and is NOT evidence that an attack is currently active.
    confirmation_evidence_persistence: int = 3  # consecutive evidence blocks required
    require_confirmation_evidence: bool = True  # False restores legacy behaviour

    def validate(self) -> None:
        if not (0.0 < self.elevated_threshold <= self.warn_threshold < 1.0):
            raise ValueError(
                f"require 0 < elevated <= warn < 1, got "
                f"{self.elevated_threshold}, {self.warn_threshold}")
        if self.persistence_k < 1:
            raise ValueError("persistence_k must be >= 1")
        if self.cooldown_blocks < 0 or self.recovery_blocks < 1:
            raise ValueError("cooldown_blocks>=0 and recovery_blocks>=1 required")
        if self.reacquire_blocks < 1:
            raise ValueError("reacquire_blocks must be >= 1")
        if not (0.0 < self.confirm_probability < 1.0):
            raise ValueError("confirm_probability must be in (0,1)")
        if not (self.confirm_probability >= self.warn_threshold):
            raise ValueError("confirm_probability must be >= warn_threshold")
        if self.confirmation_evidence_persistence < 1:
            raise ValueError("confirmation_evidence_persistence must be >= 1")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class StateTransition:
    """One audited state change."""

    block: int
    from_state: str
    to_state: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class OperationalTrace:
    """Per-block state series plus the audited transition log."""

    states: list[str]
    transitions: list[StateTransition] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out = {s: 0 for s in OPERATIONAL_STATES}
        for s in self.states:
            out[s] += 1
        return out

    def first_entry(self, state: str) -> int | None:
        for i, s in enumerate(self.states):
            if s == state:
                return i
        return None


#: States that constitute an active operational alert.
ALERT_STATES = (PRE_ATTACK_WARNING, ACTIVE_ATTACK_CONFIRMED)


@dataclass(frozen=True)
class AlertEpisode:
    """One continuous operational alert episode (state occupancy interval)."""

    scenario_id: str
    episode_id: int
    enter_block: int
    exit_block: int | None   # None = still active at the end of the observed span
    peak_state: str

    @property
    def is_open(self) -> bool:
        return self.exit_block is None

    def duration_blocks(self, n_blocks: int) -> int:
        end = self.exit_block if self.exit_block is not None else n_blocks
        return int(end - self.enter_block)

    def to_dict(self) -> dict:
        return {"scenario_id": self.scenario_id, "episode_id": self.episode_id,
                "enter_block": self.enter_block, "exit_block": self.exit_block,
                "peak_state": self.peak_state, "is_open": self.is_open}


def alert_episodes_from_trace(
    trace: OperationalTrace,
    scenario_id: str = "",
) -> list[AlertEpisode]:
    """Extract distinct alert EPISODES from an operational state timeline.

    An episode begins when the state machine ENTERS an alert state
    (``ALERT_STATES``) from a non-alert state and ends when it exits to a
    non-alert state. Repeated threshold crossings while the alarm remains active
    (sticky) do NOT create new episodes; a new episode requires an actual
    exit-and-re-enter (i.e. the documented recovery/rearm cycle).
    """
    episodes: list[AlertEpisode] = []
    in_alert = False
    enter = -1
    peak = PRE_ATTACK_WARNING
    eid = 0
    for i, s in enumerate(trace.states):
        is_alert = s in ALERT_STATES
        if is_alert and not in_alert:
            in_alert = True
            enter = i
            peak = s
        elif is_alert and in_alert:
            if s == ACTIVE_ATTACK_CONFIRMED:
                peak = ACTIVE_ATTACK_CONFIRMED
        elif not is_alert and in_alert:
            episodes.append(AlertEpisode(scenario_id, eid, enter, i, peak))
            eid += 1
            in_alert = False
    if in_alert:
        episodes.append(AlertEpisode(scenario_id, eid, enter, None, peak))
    return episodes


def summarize_alert_burden(
    traces: dict[str, OperationalTrace],
    block_seconds: float = 0.01,
    benign_classes: dict[str, str] | None = None,
) -> dict:
    """Operational alert burden from ACTUAL episodes and state occupancy.

    Replaces scenario-count-as-episode-rate accounting (D-051). All quantities
    are computed from emitted episode intervals and the per-block state timeline:

      n_scenarios               independent scenarios in the ledger
      n_scenarios_with_alerts   scenarios with >= 1 emitted episode
      n_episodes                total distinct emitted alert episodes
      episodes_per_1000_seconds n_episodes / simulated_seconds * 1000
      occupancy_fraction        alert-state blocks / observed blocks
      median_episode_seconds    median closed-episode duration (open episodes are
                                measured to the end of their observed span and
                                flagged via n_open_episodes)
    """
    n_scenarios = len(traces)
    scenarios_with_alerts = 0
    all_episodes: list[AlertEpisode] = []
    alert_blocks = 0
    total_blocks = 0
    per_scenario: dict[str, dict] = {}
    for sid, trace in traces.items():
        eps = alert_episodes_from_trace(trace, sid)
        n_blocks = len(trace.states)
        occ = sum(1 for s in trace.states if s in ALERT_STATES)
        total_blocks += n_blocks
        alert_blocks += occ
        if eps:
            scenarios_with_alerts += 1
        all_episodes.extend(eps)
        per_scenario[sid] = {
            "n_episodes": len(eps),
            "alert_blocks": occ,
            "observed_blocks": n_blocks,
            "episodes": [e.to_dict() for e in eps],
            "scenario_class": (benign_classes or {}).get(sid),
        }
    sim_seconds = total_blocks * block_seconds
    durations_blocks = [e.duration_blocks(len(traces[e.scenario_id].states))
                        for e in all_episodes]
    closed = [e for e in all_episodes if not e.is_open]
    closed_blocks = [e.duration_blocks(len(traces[e.scenario_id].states)) for e in closed]
    return {
        "n_scenarios": n_scenarios,
        "n_scenarios_with_alerts": scenarios_with_alerts,
        "n_episodes": len(all_episodes),
        "n_open_episodes": sum(1 for e in all_episodes if e.is_open),
        "episodes_per_1000_seconds": (len(all_episodes) / sim_seconds * 1000.0)
        if sim_seconds > 0 else None,
        "occupancy_fraction": (alert_blocks / total_blocks) if total_blocks else None,
        "alert_blocks": alert_blocks,
        "observed_blocks": total_blocks,
        "simulated_seconds": sim_seconds,
        "median_episode_seconds": (float(np.median(closed_blocks)) * block_seconds)
        if closed_blocks else None,
        "median_episode_seconds_including_open": (float(np.median(durations_blocks)) * block_seconds)
        if durations_blocks else None,
        "per_scenario": per_scenario,
    }


def operational_state_series(
    probability: np.ndarray,
    telemetry_valid: np.ndarray | None = None,
    telemetry_stale: np.ndarray | None = None,
    policy: OperationalPolicy | None = None,
    confirmation_evidence: np.ndarray | None = None,
) -> OperationalTrace:
    """Run the online state machine over one scenario's probability series.

    Parameters
    ----------
    probability:
        P(attack within H) per block, from the frozen forecasting pipeline.
        Values outside [0,1] or NaN are treated as invalid (degraded), never as
        evidence of safety.
    telemetry_valid:
        Optional boolean mask, True where the telemetry for that block is usable.
        False means missing/invalid measurements -> DEGRADED_TELEMETRY.
    telemetry_stale:
        Optional boolean mask, True where the telemetry has not refreshed within
        ``policy.max_stale_blocks``. Stale data also degrades the state.
    policy:
        Operational policy; defaults mirror the frozen forecasting policy.
    confirmation_evidence:
        Optional boolean mask, True at blocks where INDEPENDENT active-attack
        evidence exists (e.g. a validated conventional-detector detection signal
        computed from current telemetry). ACTIVE_ATTACK_CONFIRMED requires
        ``policy.confirmation_evidence_persistence`` consecutive evidence blocks
        when ``policy.require_confirmation_evidence`` is True. A sustained
        forecast probability alone can never confirm an active attack (D-050).

    Returns
    -------
    OperationalTrace
        ``states[i]`` is the operating state at block i; ``transitions`` records
        every change with a human-readable reason.

    Notes
    -----
    Causality: every decision uses only the current and past blocks. There is no
    reference to attack onset or any future information anywhere in this function.
    """
    pol = policy or OperationalPolicy()
    pol.validate()

    p = np.asarray(probability, dtype=float)
    n = len(p)
    if telemetry_valid is None:
        telemetry_valid = np.ones(n, dtype=bool)
    else:
        telemetry_valid = np.asarray(telemetry_valid, dtype=bool)
    if telemetry_stale is None:
        telemetry_stale = np.zeros(n, dtype=bool)
    else:
        telemetry_stale = np.asarray(telemetry_stale, dtype=bool)
    if confirmation_evidence is None:
        evidence = np.zeros(n, dtype=bool)
    else:
        evidence = np.asarray(confirmation_evidence, dtype=bool)
        if len(evidence) != n:
            raise ValueError(
                f"confirmation_evidence length {len(evidence)} != probability length {n}")

    states: list[str] = []
    transitions: list[StateTransition] = []
    cur = NORMAL

    warn_run = 0        # consecutive blocks >= warn_threshold
    elev_run = 0        # consecutive blocks >= elevated_threshold
    conf_run = 0        # consecutive blocks >= confirm_probability
    evidence_run = 0    # consecutive blocks with independent confirmation evidence
    below_run = 0       # consecutive blocks < warn_threshold (recovery)
    cooldown_until = -1
    valid_run = 0       # consecutive degraded blocks
    valid_streak = 0    # consecutive usable blocks since the last outage
    recovering = False  # True while working through a post-outage re-acquisition

    for i in range(n):
        pi = p[i]
        finite = bool(np.isfinite(pi))
        in_range = finite and (0.0 <= pi <= 1.0)
        usable = bool(telemetry_valid[i]) and not bool(telemetry_stale[i]) and in_range

        if not usable:
            new = DEGRADED_TELEMETRY
            reason = ("telemetry missing, stale, or probability non-finite/out-of-range "
                      "at this block; the system declines to assert a risk level")
            # Reset evidence counters: we have no usable current evidence.
            warn_run = elev_run = conf_run = evidence_run = 0
            below_run = 0
            valid_run += 1
            valid_streak = 0
            recovering = True
        else:
            valid_run = 0
            valid_streak += 1
            # After an outage the features that depend on trailing windows are not
            # yet trustworthy; abstain until a full window of fresh data exists.
            if recovering and valid_streak <= pol.reacquire_blocks:
                warn_run = elev_run = conf_run = evidence_run = 0
                below_run = 0
                states.append(ABSTAINING)
                if cur != ABSTAINING:
                    transitions.append(StateTransition(
                        block=i, from_state=cur, to_state=ABSTAINING,
                        reason=("telemetry restored; abstaining until "
                                f"{pol.reacquire_blocks} fresh blocks re-establish "
                                "trailing-window features")))
                cur = ABSTAINING
                continue
            if recovering and valid_streak > pol.reacquire_blocks:
                recovering = False
            valid_run = 0
            if pi >= pol.warn_threshold:
                warn_run += 1
                elev_run += 1
                below_run = 0
            else:
                warn_run = 0
                if pi >= pol.elevated_threshold:
                    elev_run += 1
                else:
                    elev_run = 0
                below_run += 1
            if pi >= pol.confirm_probability:
                conf_run += 1
            else:
                conf_run = 0
            if bool(evidence[i]):
                evidence_run += 1
            else:
                evidence_run = 0

            risk_evidence = conf_run >= pol.confirm_persistence
            active_evidence = evidence_run >= pol.confirmation_evidence_persistence
            if pol.require_confirmation_evidence:
                can_confirm = active_evidence
            else:
                can_confirm = risk_evidence or active_evidence
            if can_confirm:
                new = ACTIVE_ATTACK_CONFIRMED
                if active_evidence:
                    reason = (f"independent active-attack evidence sustained for "
                              f"{pol.confirmation_evidence_persistence} blocks: "
                              "attack confirmed")
                else:
                    reason = ("legacy mode: sustained risk probability treated as "
                              "confirmation (require_confirmation_evidence=False)")
            elif risk_evidence and not active_evidence:
                # Forecast says 'attack likely within H' but no independent
                # evidence that an attack is active. Stay in the warning state.
                if cur in (PRE_ATTACK_WARNING, ACTIVE_ATTACK_CONFIRMED):
                    new = cur if cur != ACTIVE_ATTACK_CONFIRMED else PRE_ATTACK_WARNING
                    reason = ("risk probability sustained without independent "
                              "active-attack evidence: unconfirmed")
                else:
                    new = PRE_ATTACK_WARNING
                    reason = (f"probability >= {pol.confirm_probability} for "
                              f"{pol.confirm_persistence} blocks without independent "
                              "active-attack evidence: warning, not confirmed")
            elif cur in (ACTIVE_ATTACK_CONFIRMED, PRE_ATTACK_WARNING):
                # Alarm states are STICKY: an operator alarm must not blink off
                # while the underlying condition persists. It is cleared only by
                # the documented recovery rule below.
                if below_run >= pol.recovery_blocks:
                    new = RECOVERY
                    reason = (f"probability below warning threshold for "
                              f"{pol.recovery_blocks} blocks")
                else:
                    new = cur
                    reason = "alarm condition persists"
            elif warn_run >= pol.persistence_k and i > cooldown_until:
                new = PRE_ATTACK_WARNING
                reason = (f"probability >= {pol.warn_threshold} for "
                          f"{pol.persistence_k} consecutive blocks")
                cooldown_until = i + pol.cooldown_blocks
            elif elev_run >= pol.persistence_k:
                new = ELEVATED
                reason = (f"probability >= {pol.elevated_threshold} sustained; "
                          "below warning threshold")
            elif cur == RECOVERY and below_run >= pol.recovery_blocks:
                new = NORMAL
                reason = "recovered; risk indicators have returned to baseline"
            else:
                new = NORMAL
                if cur not in (NORMAL, ELEVATED):
                    reason = "risk indicators returned to baseline"
                else:
                    reason = "risk below elevated threshold"

        if new != cur:
            transitions.append(StateTransition(block=i, from_state=cur, to_state=new,
                                               reason=reason))
            cur = new
        states.append(cur)

    return OperationalTrace(states=states, transitions=transitions)