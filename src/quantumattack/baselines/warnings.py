"""Warning-policy conversion + lead-time + false-warning evaluation
(docs/evaluation-protocol.md §2-§6; master prompt §29-§36).

Policy: P(attack within H) ≥ threshold for K consecutive prediction points →
PRE-ATTACK WARNING. Threshold/persistence are configurable and MUST be selected
on validation scenarios only (master prompt §29) — never on test.
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
    # Phase 3 (pre-declarable): warning must SUSTAIN above threshold until onset —
    # transient spikes (warmup noise, drift blips) are not warnings. Uniform for all
    # models; selected on validation only.
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


def warning_blocks_for_scenario(
    df_scenario: pd.DataFrame,
    horizon: int,
    policy: WarningPolicy,
    sustained_until_onset: bool = False,
) -> list[int]:
    """Apply the warning policy to one scenario's probability series.

    Returns block indices where the warning FIRES (first block of each
    K-consecutive run above threshold, after cooldown).

    sustained_until_onset (Phase 3 policy fix, pre-declarable): if True, a warning
    counts only when the probability STAYS above threshold from the end of the
    k-run until the attack onset (or scenario end for benign runs) — transient
    spikes (warmup noise, drift blips) are not warnings. Applies uniformly to ALL
    models and benign scenarios; not tuned on test.
    """
    policy.validate()
    col = f"p_attack_future_h{horizon}"
    if col not in df_scenario.columns:
        return []
    p = df_scenario[col].to_numpy(dtype=float)
    t_idx = df_scenario["block_index"].to_numpy()
    above = p >= policy.prob_threshold
    onset = int(df_scenario["attack_onset"].iloc[0]) if "attack_onset" in df_scenario.columns else -1
    fires: list[int] = []
    cooldown_until = -1e9
    run = 0
    for i in range(len(p)):
        if above[i]:
            run += 1
        else:
            run = 0
        if run >= policy.persistence_k and t_idx[i] > cooldown_until:
            first_of_run = t_idx[i - policy.persistence_k + 1]
            if sustained_until_onset:
                # sustained: p must stay above threshold from i until onset (attack
                # already begun → sustain to scenario end) or end for benign runs
                if onset >= 0:
                    onset_pos = int(np.searchsorted(t_idx, onset))
                    end_idx = min(len(p), onset_pos + 1)
                else:
                    end_idx = len(p)
                if bool(above[i:end_idx].all()):
                    fires.append(int(first_of_run))
                    cooldown_until = t_idx[i] + policy.cooldown_blocks
                    run = 0
                # else: transient — not a warning; run keeps accumulating
            else:
                fires.append(int(first_of_run))
                cooldown_until = t_idx[i] + policy.cooldown_blocks
                run = 0
    return fires


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
    """Per-scenario warning outcome for one horizon."""

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
    warning_duration_blocks: int  # span of first..last warning


def evaluate_scenario_warnings(
    df_scenario: pd.DataFrame,
    horizon: int,
    policy: WarningPolicy,
    sustained_until_onset: bool = False,
) -> ScenarioWarningResult:
    """Full per-scenario warning evaluation for one horizon."""
    fires = warning_blocks_for_scenario(
        df_scenario, horizon, policy, policy.sustained_until_onset)
    onset = int(df_scenario["attack_onset"].iloc[0])
    attack_type = str(df_scenario["attack_type"].iloc[0])
    scenario_class = str(df_scenario["scenario_class"].iloc[0])
    # for benign scenarios there is no onset: warnings are all FALSE early warnings
    onset_for_lead = onset if onset >= 0 else None
    lt = lead_time(onset_for_lead, fires)
    wt = warning_time(fires)
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
