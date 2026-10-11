"""Warning-policy conversion + lead-time + false-warning evaluation
(docs/evaluation-protocol.md §2-§6; master prompt §29-§36).

Policy: P(attack within H) ≥ threshold for K consecutive prediction points →
PRE-ATTACK WARNING. Threshold/persistence are configurable and MUST be selected
on validation scenarios only (master prompt §29) — never on test.

CAUSAL EMISSION SEMANTICS (repair, see decisions.md D-049)
----------------------------------------------------------
A warning episode distinguishes four distinct timestamps:

  excursion_start_block       first block of the qualifying K-run crossing the
                              threshold (recorded as metadata, NEVER as the
                              operational emission time)
  persistence_satisfied_block block at which the K-th required observation was
                              actually received (the earliest block at which the
                              persistence condition was known to be satisfied)
  emission_block              the block at which the online system actually
                              activated the alert = persistence_satisfied_block
                              plus any modelled processing delay
  resolution_block            the block at which the alarm state ended (recorded
                              by the operational state machine / episode ledger)

The ONLINE generator (`warning_events_for_scenario`) uses only the probability
series and block indices. It has NO access to attack onset, scenario duration, or
any future value. Retrospective analyses (`retrospective_sustained_retention`,
`evaluate_scenario_warnings`) classify already-emitted events using ground truth
and MUST NOT remove an emitted event from the operational ledger.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field

import numpy as np
import pandas as pd

from ..simulator.config import BLOCK_MS


@dataclass
class WarningPolicy:
    """Forecast-warning policy configuration (master prompt §29)."""

    prob_threshold: float = 0.5     # calibrated-probability threshold
    persistence_k: int = 3          # K consecutive prediction points above threshold
    cooldown_blocks: int = 50       # suppress re-arming after a warning fires
    grace_blocks: int = 5           # warnings within <grace of onset are "immediate detection"
    # RETROSPECTIVE research view (not an online policy): when True, the
    # evaluation-level retention filter keeps only alerts whose probability
    # stays above threshold until onset (attack runs) or scenario end (benign
    # runs). It is applied by `retrospective_sustained_retention` and NEVER
    # deletes an emitted event from the operational event ledger.
    sustained_until_onset: bool = False

    def validate(self) -> None:
        if not (0.0 < self.prob_threshold < 1.0):
            raise ValueError(f"prob_threshold must be in (0,1): {self.prob_threshold}")
        if self.persistence_k < 1:
            raise ValueError(f"persistence_k must be >= 1: {self.persistence_k}")
        if self.cooldown_blocks < 0 or self.grace_blocks < 0:
            raise ValueError("cooldown/grace cannot be negative")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class WarningEvent:
    """One actually-emitted operational warning episode (canonical event model).

    Emitted by the ONLINE generator. Contains no ground-truth information and no
    future-dependent fields. Retrospective classification attaches to a copy of
    this record; it never mutates or removes it.
    """

    scenario_id: str
    horizon: int
    event_id: int
    excursion_start_block: int
    persistence_satisfied_block: int
    emission_block: int
    config_hash: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def warning_events_for_scenario(
    df_scenario: pd.DataFrame,
    horizon: int,
    policy: WarningPolicy,
    processing_delay_blocks: int = 0,
    scenario_id: str | None = None,
) -> list[WarningEvent]:
    """ONLINE alert generation for one scenario and horizon (causal).

    Consumes ONLY the scenario's probability column and block indices. The attack
    onset column, if present, is never read — changing it cannot change the
    returned events (prefix-invariance and onset-blindness are regression-tested).

    For K consecutive above-threshold observations ending at index ``i``:
      excursion_start       = t_idx[i - K + 1]
      persistence_satisfied = t_idx[i]
      emission              = t_idx[i] + processing_delay_blocks
    The emission timestamp is the earliest block at which the persistence
    condition was knowable; it is never backdated to the excursion start.
    """
    policy.validate()
    if processing_delay_blocks < 0:
        raise ValueError(f"processing_delay_blocks cannot be negative: {processing_delay_blocks}")
    col = f"p_attack_future_h{horizon}"
    if col not in df_scenario.columns:
        return []
    sid = scenario_id if scenario_id is not None else (
        str(df_scenario["scenario_id"].iloc[0]) if "scenario_id" in df_scenario.columns else "")
    p = df_scenario[col].to_numpy(dtype=float)
    t_idx = df_scenario["block_index"].to_numpy(dtype=int)
    n = len(p)
    if n and (n > 1) and not np.all(np.diff(t_idx) == 1):
        raise ValueError("block_index must be contiguous for causal event generation")

    events: list[WarningEvent] = []
    cooldown_until = -1e9
    run = 0
    event_id = 0
    for i in range(n):
        pi = p[i]
        above_i = bool(np.isfinite(pi) and pi >= policy.prob_threshold)
        if above_i:
            run += 1
        else:
            run = 0
        if run >= policy.persistence_k and t_idx[i] > cooldown_until:
            events.append(WarningEvent(
                scenario_id=sid,
                horizon=horizon,
                event_id=event_id,
                excursion_start_block=int(t_idx[i - policy.persistence_k + 1]),
                persistence_satisfied_block=int(t_idx[i]),
                emission_block=int(t_idx[i]) + int(processing_delay_blocks),
                config_hash=f"thr={policy.prob_threshold};k={policy.persistence_k};cd={policy.cooldown_blocks}",
            ))
            event_id += 1
            cooldown_until = t_idx[i] + policy.cooldown_blocks
            run = 0
    return events


def retrospective_sustained_retention(
    events: list[WarningEvent],
    df_scenario: pd.DataFrame,
    horizon: int,
    policy: WarningPolicy,
) -> dict[int, bool]:
    """OFFLINE retention view: did each emitted event 'sustain' per the old rule?

    Uses attack onset (or scenario end for benign runs) to decide whether the
    probability stayed above threshold from the persistence-satisfaction block
    until onset/scenario end. Returns a mapping ``event_id -> retained``.

    This is a scientific classification of events that ALREADY happened. It does
    not delete or rewrite any event; the operational ledger keeps every emission.
    """
    policy.validate()
    col = f"p_attack_future_h{horizon}"
    if col not in df_scenario.columns:
        return {e.event_id: False for e in events}
    p = df_scenario[col].to_numpy(dtype=float)
    t_idx = df_scenario["block_index"].to_numpy(dtype=int)
    above = np.array(
        [bool(np.isfinite(x) and x >= policy.prob_threshold) for x in p], dtype=bool)
    onset = int(df_scenario["attack_onset"].iloc[0]) if "attack_onset" in df_scenario.columns else -1
    if onset >= 0:
        onset_pos = int(np.searchsorted(t_idx, onset))
        end_idx = min(len(p), onset_pos + 1)
    else:
        end_idx = len(p)
    out: dict[int, bool] = {}
    for e in events:
        start_pos = int(np.searchsorted(t_idx, e.persistence_satisfied_block))
        out[e.event_id] = bool(above[start_pos:end_idx].all())
    return out


def warning_blocks_for_scenario(
    df_scenario: pd.DataFrame,
    horizon: int,
    policy: WarningPolicy,
    sustained_until_onset: bool | None = None,
) -> list[int]:
    """Emission blocks (causal) for one scenario's probability series.

    Returns the ALERT-EMISSION blocks of each K-consecutive run (the block at
    which the K-th observation was received), after cooldown suppression.

    sustained_until_onset: when True, restricts the returned list to events that
    pass the retrospective sustained-retention filter (attack runs: sustain until
    onset; benign runs: sustain until scenario end). This is a RETROSPECTIVE
    research view — the operational event ledger produced by
    `warning_events_for_scenario` always keeps every emitted event. When None,
    falls back to ``policy.sustained_until_onset`` for backwards compatibility.
    """
    policy.validate()
    events = warning_events_for_scenario(df_scenario, horizon, policy)
    use_sustained = policy.sustained_until_onset if sustained_until_onset is None else sustained_until_onset
    if use_sustained:
        retention = retrospective_sustained_retention(events, df_scenario, horizon, policy)
        events = [e for e in events if retention.get(e.event_id, False)]
    return [int(e.emission_block) for e in events]


def warning_time(warning_blocks: list[int]) -> float | None:
    """first_valid_warning_time (block index); None if never warned."""
    return float(warning_blocks[0]) if warning_blocks else None


def lead_time(attack_onset: int | None, warning_blocks: list[int]) -> float | None:
    """lead_time = attack_onset − first_valid_warning_time (blocks).

    Positive = useful early warning; 0 = no lead; negative = late/reactive;
    None = no warning (or no attack). Missing warnings are NOT zero lead time
    (master prompt §30).
    """
    if attack_onset is None:
        return None
    wt = warning_time(warning_blocks)
    if wt is None:
        return None
    return float(attack_onset) - wt


def warning_category(lead_blocks: float | None, grace_blocks: int) -> str:
    """Classify warning timing (master prompt §32) — a 1-block warning and a
    500-block warning are NOT the same category:
      "anticipatory"   lead > grace_blocks (genuinely predictive)
      "immediate"      0 ≤ lead ≤ grace_blocks (detection at onset, not prediction)
      "late"           lead < 0 (reactive)
      "none"           no warning
    """
    if lead_blocks is None:
        return "none"
    if lead_blocks > grace_blocks:
        return "anticipatory"
    if lead_blocks >= 0:
        return "immediate"
    return "late"


@dataclass
class ScenarioWarningResult:
    """Per-scenario warning outcome for one horizon.

    ``warning_blocks`` / ``warning_time`` are ALERT-EMISSION blocks (the block at
    which the K-th consecutive above-threshold observation was received), not the
    start of the qualifying run. ``excursion_start_block`` records the run start
    as separate metadata and is never used as the warning time.
    """

    scenario_id: str
    attack_type: str
    scenario_class: str
    horizon: int
    warning_blocks: list[int]
    warning_time: float | None
    lead_time_blocks: float | None
    lead_time_ms: float | None
    category: str                 # anticipatory / immediate / late / none
    n_warnings: int
    warning_duration_blocks: int  # SPAN of first..last emission (not occupancy)
    # --- repair additions (defaults preserve existing constructors) ---
    excursion_start_block: float | None = None   # first block of the first run
    persistence_satisfied_block: float | None = None
    n_episodes: int = 0           # distinct emitted alert episodes


def evaluate_scenario_warnings(
    df_scenario: pd.DataFrame,
    horizon: int,
    policy: WarningPolicy,
    sustained_until_onset: bool | None = None,
) -> ScenarioWarningResult:
    """Full per-scenario warning evaluation for one horizon.

    Uses alert-EMISSION timestamps (causal). When ``sustained_until_onset`` is
    True the returned list is filtered to retrospectively sustained events, but
    the emission timestamps are unchanged and the unfiltered ledger remains
    available via ``warning_events_for_scenario``.
    """
    use_sustained = policy.sustained_until_onset if sustained_until_onset is None else sustained_until_onset
    all_events = warning_events_for_scenario(df_scenario, horizon, policy)
    if use_sustained:
        retention = retrospective_sustained_retention(all_events, df_scenario, horizon, policy)
        events = [e for e in all_events if retention.get(e.event_id, False)]
    else:
        events = list(all_events)
    fires = [int(e.emission_block) for e in events]
    onset = int(df_scenario["attack_onset"].iloc[0])
    attack_type = str(df_scenario["attack_type"].iloc[0])
    scenario_class = str(df_scenario["scenario_class"].iloc[0])
    # for benign scenarios there is no onset: warnings are all FALSE early warnings
    onset_for_lead = onset if onset >= 0 else None
    lt = lead_time(onset_for_lead, fires)
    wt = warning_time(fires)
    # SPAN of emissions (kept for backwards compatibility; NOT occupancy)
    duration = (max(fires) - min(fires) + 1) if fires else 0
    category = warning_category(lt, policy.grace_blocks) if onset_for_lead is not None else (
        "none" if not fires else "false_early_warning"
    )
    return ScenarioWarningResult(
        scenario_id=str(df_scenario["scenario_id"].iloc[0]),
        attack_type=attack_type,
        scenario_class=scenario_class,
        horizon=horizon,
        warning_blocks=fires,
        warning_time=wt,
        lead_time_blocks=lt,
        lead_time_ms=None if lt is None else lt * BLOCK_MS,
        category=category,
        n_warnings=len(fires),
        warning_duration_blocks=int(duration),
        excursion_start_block=(all_events[0].excursion_start_block if events else None),
        persistence_satisfied_block=(events[0].persistence_satisfied_block if events else None),
        n_episodes=len(fires),
    )


def false_early_warning_rate(
    results: list[ScenarioWarningResult],
    scenario_classes: tuple[str, ...] = ("NORMAL", "BENIGN_DRIFT"),
) -> dict[str, float]:
    """Scenario-level false early warnings (master prompt §31): any valid warning
    on a benign scenario = false early warning. Rate per benign class."""
    out: dict[str, float] = {}
    for cls in scenario_classes:
        scenarios = [r for r in results if r.scenario_class == cls]
        if not scenarios:
            continue
        flagged = sum(1 for r in scenarios if r.n_warnings > 0)
        out[cls] = flagged / len(scenarios)
    return out


def attribute_warnings(
    attack_results: list[ScenarioWarningResult],
    benign_results: list[ScenarioWarningResult],
    horizon: int,
) -> dict[str, ScenarioWarningResult]:
    """Pair-gated warning attribution (Phase 2 gate fix, master prompt §53).

    A warning on an attack scenario is attack-ATTRIBUTABLE only if the matched
    benign run (same seed/pair) does NOT warn at overlapping blocks. Warnings
    identical in both arms are benign-drift responses (e.g., calibration wander),
    not attack anticipation — counting them as 'anticipatory' lead would inflate
    sudden-attack predictability (observed on intercept-resend: identical warning
    blocks 151, 202, 309, 663, 722 in both arms).

    Returns results with category downgraded to "unattributed" for warnings whose
    benign twin also fired; lead_time preserved but success-counting excludes them.
    """
    benign_by_key: dict[str, list[int]] = {}
    for r in benign_results:
        if r.horizon != horizon:
            continue
        benign_by_key[r.scenario_id] = r.warning_blocks

    out: dict[str, ScenarioWarningResult] = {}
    for r in attack_results:
        if r.horizon != horizon:
            continue
        # find the paired benign run: same pair_id seed signature via scenario_id
        # pairing convention: attack-<name>-s<seed> ↔ normal-<name>-s<seed>
        sid = r.scenario_id
        if sid.startswith("attack-"):
            twin = "normal-" + sid[len("attack-"):]
        else:
            twin = None
        benign_blocks = benign_by_key.get(twin, []) if twin else []
        overlaps = bool(set(r.warning_blocks) & set(benign_blocks))
        if overlaps and r.category == "anticipatory":
            out[sid] = ScenarioWarningResult(
                scenario_id=r.scenario_id, attack_type=r.attack_type,
                scenario_class=r.scenario_class, horizon=r.horizon,
                warning_blocks=r.warning_blocks, warning_time=r.warning_time,
                lead_time_blocks=r.lead_time_blocks, lead_time_ms=r.lead_time_ms,
                category="unattributed",  # benign twin warned identically
                n_warnings=r.n_warnings,
                warning_duration_blocks=r.warning_duration_blocks,
            )
        else:
            out[sid] = r
    return out


def summarize_lead_times_attributed(
    attack_results: list[ScenarioWarningResult],
    benign_results: list[ScenarioWarningResult],
    horizon: int,
    attributed: dict[str, ScenarioWarningResult] | None = None,
) -> dict:
    """Lead-time summary counting ONLY attributed anticipatory warnings as success
    (master prompt §53 gate: benign-twin-confirmed anticipation)."""
    attr = attributed if attributed is not None else attribute_warnings(
        attack_results, benign_results, horizon)
    filtered = []
    for r in attack_results:
        if r.horizon != horizon or r.scenario_class != "ATTACK":
            continue
        updated = attr.get(r.scenario_id, r)
        if updated.category == "anticipatory":
            filtered.append(ScenarioWarningResult(
                scenario_id=updated.scenario_id, attack_type=updated.attack_type,
                scenario_class=updated.scenario_class, horizon=updated.horizon,
                warning_blocks=updated.warning_blocks, warning_time=updated.warning_time,
                lead_time_blocks=updated.lead_time_blocks, lead_time_ms=updated.lead_time_ms,
                category="anticipatory", n_warnings=updated.n_warnings,
                warning_duration_blocks=updated.warning_duration_blocks,
            ))
        else:
            # keep an entry with zero success so n_scenarios stays correct
            filtered.append(ScenarioWarningResult(
                scenario_id=updated.scenario_id, attack_type=updated.attack_type,
                scenario_class=updated.scenario_class, horizon=updated.horizon,
                warning_blocks=[], warning_time=None,
                lead_time_blocks=None, lead_time_ms=None,
                category=updated.category, n_warnings=0,
                warning_duration_blocks=0,
            ))
    return summarize_lead_times(filtered, category_filter="anticipatory")


def summarize_lead_times(
    results: list[ScenarioWarningResult],
    category_filter: str | None = "anticipatory",
) -> dict:
    """Lead-time distribution per attack type (master prompt §33/§41).

    Reports raw counts, median, mean, range — no overclaiming from small samples.
    category_filter: count only warnings in this category as "successful"
    (None = count any warning with a lead time).
    """
    by_type: dict[str, list[float]] = {}
    success: dict[str, int] = {}
    total: dict[str, int] = {}
    for r in results:
        if r.scenario_class != "ATTACK":
            continue
        total[r.attack_type] = total.get(r.attack_type, 0) + 1
        lt = r.lead_time_blocks
        if lt is None:
            continue
        if category_filter is not None and r.category != category_filter:
            continue
        by_type.setdefault(r.attack_type, []).append(lt)
    summary: dict[str, dict] = {}
    for atype, leads in sorted(by_type.items()):
        arr = np.array(leads)
        entry = {
            "n_scenarios": total[atype],
            "n_successful_warnings": len(leads),
            "warning_success_rate": len(leads) / total[atype],
            "median_lead_blocks": float(np.median(arr)),
            "mean_lead_blocks": float(arr.mean()),
            "std_lead_blocks": float(arr.std()) if len(arr) > 1 else None,
            "min_lead_blocks": float(arr.min()),
            "max_lead_blocks": float(arr.max()),
            "p25_lead_blocks": float(np.quantile(arr, 0.25)),
            "p75_lead_blocks": float(np.quantile(arr, 0.75)),
            "p90_lead_blocks": float(np.quantile(arr, 0.90)),
            "median_lead_ms": float(np.median(arr)) * BLOCK_MS,
            "mean_lead_ms": float(arr.mean()) * BLOCK_MS,
        }
        summary[atype] = entry
    # attacks with zero successful warnings
    for atype, n in total.items():
        if atype not in summary:
            summary[atype] = {
                "n_scenarios": n, "n_successful_warnings": 0,
                "warning_success_rate": 0.0, "median_lead_blocks": None,
                "mean_lead_blocks": None, "std_lead_blocks": None,
                "min_lead_blocks": None, "max_lead_blocks": None,
                "p25_lead_blocks": None, "p75_lead_blocks": None,
                "p90_lead_blocks": None, "median_lead_ms": None, "mean_lead_ms": None,
            }
    return summary


def false_warning_analysis(
    results: list[ScenarioWarningResult],
) -> dict:
    """False-warning behavior per benign class (master prompt §22): NORMAL and
    BENIGN_DRIFT evaluated separately — scenario %, warnings/scenario, duration,
    earliest warning."""
    out: dict[str, dict] = {}
    for cls in ("NORMAL", "BENIGN_DRIFT"):
        scenarios = [r for r in results if r.scenario_class == cls]
        if not scenarios:
            continue
        n_warn = [r.n_warnings for r in scenarios]
        durations = [r.warning_duration_blocks for r in scenarios if r.n_warnings > 0]
        earliest = [r.warning_time for r in scenarios if r.warning_time is not None]
        flagged = sum(1 for w in n_warn if w > 0)
        out[cls] = {
            "n_scenarios": len(scenarios),
            "pct_scenarios_with_warning": flagged / len(scenarios),
            "mean_warnings_per_scenario": float(np.mean(n_warn)),
            "mean_warning_duration_blocks": float(np.mean(durations)) if durations else 0.0,
            "earliest_warning_block": float(np.min(earliest)) if earliest else None,
            "mean_earliest_warning_block": float(np.mean(earliest)) if earliest else None,
        }
    return out
