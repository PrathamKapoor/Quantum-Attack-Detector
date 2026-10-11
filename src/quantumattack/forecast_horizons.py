"""Forecast-horizon validity: horizon-valid forecast vs. general pre-onset alert
vs. post-onset confirmation (D-040).

WHY this module exists
----------------------
A model at horizon H predicts P(attack onset within (t, t+H]). Its forecasting
target is `y_H(t) = 1` only when onset falls STRICTLY AFTER t and no later than
t+H (docs/time-semantics.md §5). Therefore a warning whose lead time exceeds H
cannot be credited to the H-specific forecaster: at that warning time the true
label was `y_H = 0`, so a probability above threshold there is a FALSE POSITIVE
of the horizon-H event, not a successful H-forecast.

The historical evaluator (`baselines/warnings.py`) classified any warning with
lead > grace_blocks as "anticipatory" regardless of H, silently merging three
distinct claims into one success count. On the Phase 5 dataset that mislabels 29
of 79 anticipatory warnings (37%) as "H=100 forecasts" when their lead exceeded
100 blocks (up to 567 blocks).

WHAT
    A single `classify_warning_outcome` function returning one of three mutually
    exclusive, explicitly-named outcomes, plus horizon-validity and horizon
    coverage helpers.

WHY
    Scientific integrity: prediction, early detection and post-onset confirmation
    are different security capabilities and must be counted separately.

HOW
    Given the first warning block, the attack onset block, the declared horizon
    and the grace window, return:
      * "horizon_valid_forecast"  — 0 < lead <= H : the H-forecast was correct.
      * "extended_pre_onset_alert" — lead > H   : warned before onset but the
                                   claim "attack within H" was false at that
                                   time; a genuine alert, not an H-forecast.
      * "onset_detection"        — 0 <= lead <= grace: coincides with onset.
      * "post_onset_confirmation"— lead < 0     : fired after onset (detection).
      * "no_warning"             — no warning fired.
    Horizon-valid credit is granted ONLY to "horizon_valid_forecast".

WHEN
    Evaluation/attribution time (after online prediction has produced probabilities
    and the warning policy has fired). Uses the causal warning timestamp; never
    backdates a warning.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "WarningOutcome",
    "OUTCOMES",
    "HORIZON_VALID",
    "EXTENDED_ALERT",
    "ONSET_DETECTION",
    "POST_ONSET_CONFIRMATION",
    "NO_WARNING",
    "classify_warning_outcome",
    "is_horizon_valid",
    "horizon_coverage_fraction",
]


# --- outcome constants (explicit strings; never compare to bare booleans) -----
HORIZON_VALID = "horizon_valid_forecast"
EXTENDED_ALERT = "extended_pre_onset_alert"
ONSET_DETECTION = "onset_detection"
POST_ONSET_CONFIRMATION = "post_onset_confirmation"
NO_WARNING = "no_warning"

#: The full, mutually exclusive outcome vocabulary.
OUTCOMES = (
    HORIZON_VALID,
    EXTENDED_ALERT,
    ONSET_DETECTION,
    POST_ONSET_CONFIRMATION,
    NO_WARNING,
)

#: Outcomes that constitute a genuinely anticipatory capability (pre-onset).
PRE_ONSET_OUTCOMES = (HORIZON_VALID, EXTENDED_ALERT, ONSET_DETECTION)


@dataclass(frozen=True)
class WarningOutcome:
    """Per-scenario, per-horizon classification of the FIRST warning.

    Attributes
    ----------
    outcome:
        One of :data:`OUTCOMES`.
    lead_blocks:
        ``onset - warning_block`` (None when no warning fired).
    horizon:
        Declared forecast horizon in blocks.
    horizon_valid:
        True only for :data:`HORIZON_VALID` — i.e. the H-specific forecaster is
        credited for this warning.
    is_pre_onset:
        True when the warning preceded onset at all (any positive lead).
    """

    outcome: str
    lead_blocks: float | None
    horizon: int
    horizon_valid: bool
    is_pre_onset: bool


def classify_warning_outcome(
    warning_block: int | None,
    onset_block: int | None,
    horizon: int,
    grace_blocks: int = 0,
) -> WarningOutcome:
    """Classify the first warning of one scenario at a declared horizon.

    Parameters
    ----------
    warning_block:
        Block index at which the live warning policy actually fired (causal —
        the first block of the K-consecutive above-threshold run). ``None`` if
        the policy never fired.
    onset_block:
        Ground-truth attack onset block. ``None``/negative means a benign
        scenario (no onset exists).
    horizon:
        The declared forecast horizon H in blocks.
    grace_blocks:
        Lead window treated as "detection at onset" rather than prediction
        (immediate detection band).

    Notes
    -----
    * A benign scenario (no onset) that warned is NOT classified here as a
      horizon event; callers use it for false-alarm accounting instead.
    * Horizon validity is ``0 < lead <= horizon``. Lead exactly == horizon is
      VALID (onset at t+H is inside the closed horizon ``(t, t+H]``).
    """
    if horizon < 1:
        raise ValueError(f"horizon must be >= 1, got {horizon}")
    if warning_block is None or onset_block is None or onset_block < 0:
        return WarningOutcome(NO_WARNING, None, horizon, False, False)

    lead = float(onset_block) - float(warning_block)

    if lead < 0:
        return WarningOutcome(POST_ONSET_CONFIRMATION, lead, horizon, False, False)
    if lead <= grace_blocks:
        return WarningOutcome(ONSET_DETECTION, lead, horizon, False, lead > 0)
    if lead <= horizon:
        return WarningOutcome(HORIZON_VALID, lead, horizon, True, True)
    return WarningOutcome(EXTENDED_ALERT, lead, horizon, False, True)


def is_horizon_valid(lead_blocks: float | None, horizon: int) -> bool:
    """True iff a pre-onset warning of ``lead_blocks`` falls inside ``horizon``."""
    if lead_blocks is None:
        return False
    return 0.0 < lead_blocks <= horizon


def horizon_coverage_fraction(
    leads: list[float | None], horizon: int
) -> float | None:
    """Fraction of warnings that qualify as horizon-valid for ``horizon``.

    Returns None when there are no warnings to classify (undefined, not 0.0), so
    that "no observations" is never reported as "zero validity".
    """
    present = [x for x in leads if x is not None]
    if not present:
        return None
    return sum(1 for x in present if is_horizon_valid(x, horizon)) / len(present)