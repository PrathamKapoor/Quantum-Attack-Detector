"""Conventional threshold detector (docs/evaluation-protocol.md §1; master prompt §13-§16).

Represents what a real reactive security monitoring system might do: current-state
thresholds on monitor-visible CV-QKD telemetry, with a persistence policy.
NOT a strawman: thresholds are calibrated on benign/training portions only
(master prompt §14), never on test scenarios.

qber_proxy is EXCLUDED (Phase 1 found it degenerate — docs/telemetry-spec.md).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..simulator.config import BLOCK_MS

# Monitor-visible indicators (CV-QKD only; qber_proxy excluded as degenerate)
INDICATORS: tuple[str, ...] = (
    "excess_noise",        # ε̂ above bound → abort
    "transmittance",       # T̂ below budget
    "lo_power",            # LO anomaly
    "det_gain",            # calibration deviation
    "skr_estimate",        # secret-key degradation
    "saturation_frac",     # detector saturation
    "background",          # background light
)

# Direction: +1 = anomaly when value ABOVE threshold; −1 = below
INDICATOR_DIRECTION: dict[str, int] = {
    "excess_noise": +1,
    "transmittance": -1,
    "lo_power": -1,        # LO attenuation attack lowers power; upward drift is benign-coupled
    "det_gain": +1,
    "skr_estimate": -1,
    "saturation_frac": +1,
    "background": +1,
}


@dataclass
class ThresholdPolicy:
    """Conventional warning policy (master prompt §15): configurable."""

    persistence_k: int = 3          # K consecutive violating blocks → warning
    cooldown_blocks: int = 50       # suppress re-arming after a warning
    sigma_multiplier: float = 5.0   # 5σ convention (QKD parameter-estimation analogue)
    min_quantile: float = 0.995     # empirical-percentile alternative
    threshold_method: str = "empirical_quantile"  # | "normal_sigma" | "fixed"
    fixed_thresholds: dict[str, float] = field(default_factory=lambda: {
        "saturation_frac": 0.01,
    })

    def validate(self) -> None:
        if self.persistence_k < 1:
            raise ValueError(f"persistence_k must be >= 1: {self.persistence_k}")
        if self.cooldown_blocks < 0:
            raise ValueError("cooldown_blocks cannot be negative")
        if self.threshold_method not in ("empirical_quantile", "normal_sigma", "fixed"):
            raise ValueError(f"unknown threshold_method: {self.threshold_method!r}")
        if not (0.5 < self.min_quantile < 1.0):
            raise ValueError(f"min_quantile must be in (0.5, 1): {self.min_quantile}")


@dataclass
class CalibrationResult:
    """Per-indicator thresholds calibrated on a benign/reference portion."""

    thresholds: dict[str, float]          # indicator → threshold value
    method: str
    reference_blocks: int
    per_indicator_stats: dict[str, dict]  # diagnostics (mean/std/quantile used)


def calibrate_thresholds(
    reference_df: pd.DataFrame,
    policy: ThresholdPolicy,
    indicators: tuple[str, ...] = INDICATORS,
) -> CalibrationResult:
    """Calibrate per-indicator thresholds on a REFERENCE portion (benign blocks).

    LEAKAGE RULE (master prompt §14/§25): reference_df must contain ONLY benign /
    training-portion blocks — never test scenarios, never post-onset attack data.
    Methods:
      - empirical_quantile: threshold = per-indicator empirical quantile (default q=0.995)
      - normal_sigma: threshold = mean ± sigma_multiplier·std (5σ convention)
      - fixed: fixed engineering thresholds (e.g., saturation_frac > 0.01)
    """
    policy.validate()
    thresholds: dict[str, float] = {}
    stats: dict[str, dict] = {}
    for ind in indicators:
        if ind not in reference_df.columns:
            continue
        x = reference_df[ind].to_numpy(dtype=float)
        x = x[~np.isnan(x)]
        if len(x) < 10:
            continue  # insufficient reference history; indicator unavailable
        direction = INDICATOR_DIRECTION[ind]
        if ind in policy.fixed_thresholds and policy.threshold_method in ("fixed", "empirical_quantile"):
            thr = policy.fixed_thresholds[ind]
            method_used = "fixed" if policy.threshold_method == "fixed" else "fixed(fallback)"
        elif policy.threshold_method == "empirical_quantile":
            q = x.max() if direction < 0 else x.min()  # placeholder, replaced below
            if direction > 0:
                thr = float(np.quantile(x, policy.min_quantile))
            else:
                thr = float(np.quantile(x, 1.0 - policy.min_quantile))
            method_used = "empirical_quantile"
        else:  # normal_sigma
            mu, sigma = float(x.mean()), float(x.std())
            thr = mu + direction * policy.sigma_multiplier * sigma
            method_used = "normal_sigma"
        thresholds[ind] = thr
        stats[ind] = {
            "mean": float(x.mean()), "std": float(x.std()),
            "q_high": float(np.quantile(x, policy.min_quantile)),
            "q_low": float(np.quantile(x, 1.0 - policy.min_quantile)),
            "method": method_used, "direction": direction,
            "n_reference": int(len(x)),
        }
    return CalibrationResult(thresholds, method_used if thresholds else policy.threshold_method,
                             len(reference_df), stats)


def violating_blocks(
    df: pd.DataFrame,
    calibration: CalibrationResult,
    indicators: tuple[str, ...] = INDICATORS,
) -> pd.DataFrame:
    """Per-block violation table: indicator → bool (value crosses its threshold)."""
    out = pd.DataFrame(index=df.index)
    for ind in indicators:
        if ind not in calibration.thresholds or ind not in df.columns:
            continue
        thr = calibration.thresholds[ind]
        direction = INDICATOR_DIRECTION[ind]
        x = df[ind].to_numpy(dtype=float)
        out[f"viol_{ind}"] = (x > thr) if direction > 0 else (x < thr)
    return out


def detect_warnings(
    df: pd.DataFrame,
    calibration: CalibrationResult,
    policy: ThresholdPolicy,
    indicators: tuple[str, ...] = INDICATORS,
) -> dict:
    """Run the conventional detector over one scenario.

    Policy (master prompt §15): indicator crosses threshold for K consecutive
    blocks → warning; cooldown suppresses re-arming.

    Returns:
      warning_blocks: list of block indices where a warning FIRES
      violating_matrix: per-block per-indicator violation table
      any_violation_blocks: blocks where ANY indicator violates (no persistence)
    """
    violations = violating_blocks(df, calibration, indicators)
    n = len(df)
    k = policy.persistence_k
    cooldown = policy.cooldown_blocks

    any_violation = violations.any(axis=1).to_numpy()
    warning_blocks: list[int] = []
    cooldown_until = -1
    run_length = 0
    for t in range(n):
        if any_violation[t]:
            run_length += 1
        else:
            run_length = 0
        if run_length >= k and t > cooldown_until:
            warning_blocks.append(t)
            cooldown_until = t + cooldown
            run_length = 0

    return {
        "warning_blocks": warning_blocks,
        "violating_matrix": violations,
        "any_violation_blocks": np.where(any_violation)[0].tolist(),
    }


def conventional_warning_time(
    warning_blocks: list[int],
) -> float | None:
    """First conventional warning block; None if the threshold never fired.

    Semantics (master prompt §16): a missing warning is NOT zero lead time —
    it is reported as null (no detection at all).
    """
    return float(warning_blocks[0]) if warning_blocks else None


def conventional_lead_time(
    attack_onset: int | None,
    warning_blocks: list[int],
) -> float | None:
    """conventional_lead_time = attack_onset − conventional_warning_time.

    Positive = warning before onset; 0 = simultaneous; negative = late;
    None = threshold never fired (or no attack in a benign scenario).
    """
    if attack_onset is None:
        return None
    wt = conventional_warning_time(warning_blocks)
    if wt is None:
        return None
    return float(attack_onset) - wt


def lead_time_ms(lead_blocks: float | None) -> float | None:
    """Convert lead time from blocks to ms (1 block = BLOCK_MS ms)."""
    return None if lead_blocks is None else lead_blocks * BLOCK_MS
