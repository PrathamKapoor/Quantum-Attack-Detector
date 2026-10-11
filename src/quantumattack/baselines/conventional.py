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
    threshold_method: str = "normalized_sigma"  # | "empirical_quantile" | "normal_sigma" | "fixed"
    fixed_thresholds: dict[str, float] = field(default_factory=lambda: {
        "saturation_frac": 0.01,
    })

    def validate(self) -> None:
        if self.persistence_k < 1:
            raise ValueError(f"persistence_k must be >= 1: {self.persistence_k}")
        if self.cooldown_blocks < 0:
            raise ValueError("cooldown_blocks cannot be negative")
        if self.threshold_method not in ("normalized_sigma", "empirical_quantile", "normal_sigma", "fixed"):
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
        elif policy.threshold_method == "normalized_sigma":
            mu, sigma = float(x.mean()), float(x.std())
            # Normalized z-score threshold: for direction > 0 (abnormal high),
            # threshold is above mean by multiplier*std; for direction < 0,
            # below mean by multiplier*std. This transfers better across
            # distributions with different absolute means.
            thr = mu + direction * policy.sigma_multiplier * sigma
            method_used = "normalized_sigma"
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


# ===========================================================================
# Causal sequential (CUSUM) conventional detector  -- decisions.md D-052
# ===========================================================================
#
# WHY: the fixed-threshold detector above has no usable operating point: with
# ~0.4% per-block violations and K=3 persistence, a 3-run occurs in essentially
# every 2000-block benign scenario (D-047). A GLOBAL reference normalization
# (one mean/std for the whole population) also fails, because each benign
# scenario has its own baseline offset whose accumulated z-drift exceeds any
# fixed allowance -- measured during development: h=30 (the largest grid value)
# still produced 100% benign FPR on the validation population.
#
# WHAT: a per-indicator one-sided CUSUM over PER-SCENARIO causally normalized
# residuals:
#
#     mu_i, sigma_i        from the scenario's own first `warmup_blocks` blocks
#                          (causal; declared startup contract)
#     z_t = (x_t - mu_i) / sigma_i
#     direction > 0 : S_t = max(0, S_{t-1} + z_t - k)
#     direction < 0 : S_t = max(0, S_{t-1} - z_t - k)
#
# The detector statistic is the maximum over indicators. An alert is emitted
# when the statistic stays >= h for `persistence_k` consecutive usable blocks,
# subject to cooldown. The emission timestamp is the block at which the
# persistence condition became satisfied (same causal rule as the forecast
# warning path, D-049).
#
# STARTUP CONTRACT (documented limitation): monitoring does not begin until
# `warmup_blocks` usable blocks have been observed. If an attack is already
# active during the warmup window the baseline is contaminated and detection
# may fail silently; this failure mode is evaluated explicitly
# (tests/test_conventional_detector.py) rather than assumed away.
#
# WHEN: online monitoring, per telemetry block. Calibration of h is offline on
# the Phase-4 validation benign population only.


@dataclass
class CusumConfig:
    """Configuration of the causal sequential conventional detector."""

    indicators: tuple[str, ...] = INDICATORS
    k_drift: float = 0.5          # drift allowance in reference-sigma units
    h_threshold: float = 8.0      # decision threshold (calibrated; sigma units)
    persistence_k: int = 3        # consecutive blocks with S >= h -> alert
    cooldown_blocks: int = 50     # suppress re-arming after an alert
    warmup_blocks: int = 200      # causal per-scenario baseline window
    max_missing_run: int = 5      # consecutive missing blocks that reset S
    deviate_cap: float = 10.0     # clip |z| per block (Huber-type robustness)
    normalization: str = "per_scenario_warmup"  # | "global_reference"

    def validate(self) -> None:
        if self.k_drift < 0:
            raise ValueError(f"k_drift cannot be negative: {self.k_drift}")
        if self.h_threshold <= 0:
            raise ValueError(f"h_threshold must be positive: {self.h_threshold}")
        if self.persistence_k < 1:
            raise ValueError(f"persistence_k must be >= 1: {self.persistence_k}")
        if self.cooldown_blocks < 0:
            raise ValueError("cooldown_blocks cannot be negative")
        if self.warmup_blocks < 2:
            raise ValueError("warmup_blocks must be >= 2")
        if self.max_missing_run < 1:
            raise ValueError("max_missing_run must be >= 1")
        if self.deviate_cap <= 0:
            raise ValueError("deviate_cap must be positive")
        if self.normalization not in ("per_scenario_warmup", "global_reference"):
            raise ValueError(f"unknown normalization: {self.normalization!r}")


@dataclass
class CusumCalibration:
    """Reference statistics + calibrated decision threshold."""

    reference: dict[str, dict]        # indicator -> {mean, std, direction, n} (training pop)
    h_threshold: float
    target_scenario_fpr: float | None
    achieved_scenario_fpr: float | None
    calibration_population: str
    config: dict

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


def fit_cusum_reference(
    reference_df: pd.DataFrame,
    config: CusumConfig,
) -> dict[str, dict]:
    """Reference mean/std per indicator from a TRAINING population.

    Used as an optional global normalizer (`normalization="global_reference"`)
    and as a diagnostic record of the training population.
    """
    ref: dict[str, dict] = {}
    for ind in config.indicators:
        if ind not in reference_df.columns:
            continue
        x = reference_df[ind].to_numpy(dtype=float)
        x = x[np.isfinite(x)]
        if len(x) < 10:
            continue
        std = float(x.std())
        ref[ind] = {
            "mean": float(x.mean()),
            "std": std if std > 1e-12 else 1e-12,
            "direction": INDICATOR_DIRECTION[ind],
            "n": int(len(x)),
        }
    return ref


def _per_scenario_baseline(
    df: pd.DataFrame,
    indicators: tuple[str, ...],
    warmup_blocks: int,
) -> dict[str, dict]:
    """Causal per-scenario baseline: mean/std over the FIRST warmup_blocks rows."""
    base: dict[str, dict] = {}
    head = df.iloc[:warmup_blocks]
    for ind in indicators:
        if ind not in head.columns:
            continue
        x = head[ind].to_numpy(dtype=float)
        x = x[np.isfinite(x)]
        if len(x) < 2:
            continue
        std = float(x.std())
        base[ind] = {
            "mean": float(x.mean()),
            "std": std if std > 1e-12 else 1e-12,
            "direction": INDICATOR_DIRECTION[ind],
            "n": int(len(x)),
        }
    return base


def cusum_statistic(
    df: pd.DataFrame,
    reference: dict[str, dict],
    config: CusumConfig,
) -> tuple[np.ndarray, np.ndarray]:
    """Per-block detector statistic S_t = max over indicators of one-sided CUSUM.

    Returns ``(S_max, usable_mask)``. The first ``warmup_blocks`` rows are
    marked unusable (startup period; no monitoring output). Non-finite
    measurements do not update the accumulator and are marked unusable; a run of
    more than ``max_missing_run`` unusable blocks resets the accumulator to zero
    (documented cold-start rule).
    """
    config.validate()
    n = len(df)
    s_max = np.zeros(n, dtype=float)
    usable = np.ones(n, dtype=bool)

    if config.normalization == "per_scenario_warmup":
        ref = _per_scenario_baseline(df, config.indicators, config.warmup_blocks)
        usable[: min(config.warmup_blocks, n)] = False
    else:
        ref = reference

    if not ref:
        return s_max, np.zeros(n, dtype=bool)

    missing_run = 0
    state: dict[str, float] = {ind: 0.0 for ind in ref}
    for t in range(n):
        if not usable[t]:
            s_max[t] = max(state.values()) if state else 0.0
            continue
        row_usable = True
        for ind, r in ref.items():
            if ind not in df.columns:
                row_usable = False
                continue
            x = df[ind].iloc[t]
            if not np.isfinite(x):
                row_usable = False
                continue
            z = (float(x) - r["mean"]) / r["std"]
            direction = int(r["direction"])
            deviate = z if direction > 0 else -z
            # Huber-type clip: a single outlier contributes at most deviate_cap,
            # bounding transient influence while preserving sustained shifts.
            deviate = float(np.clip(deviate, -config.deviate_cap, config.deviate_cap))
            state[ind] = max(0.0, state[ind] + deviate - config.k_drift)
        if not row_usable:
            usable[t] = False
            missing_run += 1
            if missing_run > config.max_missing_run:
                # documented cold-start rule: prolonged outage resets evidence
                for ind in state:
                    state[ind] = 0.0
            s_max[t] = max(state.values()) if state else 0.0
            continue
        missing_run = 0
        s_max[t] = max(state.values()) if state else 0.0
    return s_max, usable


def detect_warnings_cusum(
    df: pd.DataFrame,
    calibration: CusumCalibration,
    config: CusumConfig,
) -> dict:
    """Run the causal sequential detector over one scenario.

    Emission semantics match the forecast path (D-049): an alert fires at the
    block where ``persistence_k`` consecutive usable blocks satisfy S >= h.

    Returns:
      warning_blocks: emission block indices
      statistic: per-block max-CUSUM values
      usable_mask: per-block telemetry usability
    """
    config.validate()
    s_max, usable = cusum_statistic(df, calibration.reference, config)
    n = len(df)
    fires: list[int] = []
    cooldown_until = -1e9
    run = 0
    for t in range(n):
        cond = bool(usable[t]) and bool(s_max[t] >= calibration.h_threshold)
        if cond:
            run += 1
        else:
            run = 0
        if run >= config.persistence_k and t > cooldown_until:
            fires.append(t)          # emission at the block the evidence completed
            cooldown_until = t + config.cooldown_blocks
            run = 0
    return {"warning_blocks": fires, "statistic": s_max, "usable_mask": usable}


def calibrate_cusum_threshold(
    reference_df: pd.DataFrame,
    benign_df: pd.DataFrame,
    config: CusumConfig,
    target_fpr: float = 0.10,
    k_grid: tuple[float, ...] = (2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0),
    h_grid: tuple[float, ...] = (10.0, 20.0, 30.0, 50.0, 80.0, 120.0, 200.0, 400.0, 1000.0),
) -> CusumCalibration:
    """Fit reference stats on ``reference_df`` and choose (k, h) on ``benign_df``.

    Selection rule (documented, deterministic): scan ``k_grid`` ascending (smaller
    k = more sensitive); for each k find the smallest ``h`` in ``h_grid`` whose
    scenario-level false-positive rate on the held-out benign population is
    ``<= target_fpr``; return the first (k, h) pair that satisfies the budget.
    If no pair meets the budget, the most conservative pair is returned and the
    missed budget is recorded honestly in ``achieved_scenario_fpr``.
    """
    config.validate()
    ref = fit_cusum_reference(reference_df, config)
    if not ref:
        raise ValueError("no usable indicators in reference population")
    if "scenario_id" in benign_df.columns:
        frames = {sid: benign_df[benign_df["scenario_id"] == sid]
                  for sid in benign_df["scenario_id"].unique().tolist()}
    else:
        frames = {0: benign_df}

    def _fpr_for(k: float, h: float) -> float:
        cfg = CusumConfig(indicators=config.indicators, k_drift=float(k),
                          h_threshold=float(h), persistence_k=config.persistence_k,
                          cooldown_blocks=config.cooldown_blocks,
                          warmup_blocks=config.warmup_blocks,
                          max_missing_run=config.max_missing_run,
                          normalization=config.normalization)
        cal = CusumCalibration(ref, float(h), target_fpr, None,
                               "phase4-validation-benign", {})
        fired = 0
        for frame in frames.values():
            if detect_warnings_cusum(frame, cal, cfg)["warning_blocks"]:
                fired += 1
        return fired / len(frames)

    best = None            # (k, h, fpr) meeting the budget
    most_conservative = None  # (k, h, fpr) fallback
    for k in k_grid:
        for h in h_grid:
            fpr = _fpr_for(k, h)
            if best is None and fpr <= target_fpr:
                best = (float(k), float(h), fpr)
                break
            most_conservative = (float(k), float(h), fpr)
        if best is not None:
            break
    chosen_k, chosen_h, achieved = best if best is not None else most_conservative

    final_cfg = CusumConfig(indicators=config.indicators, k_drift=chosen_k,
                            h_threshold=chosen_h, persistence_k=config.persistence_k,
                            cooldown_blocks=config.cooldown_blocks,
                            warmup_blocks=config.warmup_blocks,
                            max_missing_run=config.max_missing_run,
                            normalization=config.normalization)
    return CusumCalibration(
        reference=ref,
        h_threshold=chosen_h,
        target_scenario_fpr=target_fpr,
        achieved_scenario_fpr=achieved,
        calibration_population="phase4-validation-benign",
        config={"k_drift": final_cfg.k_drift, "persistence_k": final_cfg.persistence_k,
                "cooldown_blocks": final_cfg.cooldown_blocks,
                "warmup_blocks": final_cfg.warmup_blocks,
                "max_missing_run": final_cfg.max_missing_run,
                "normalization": final_cfg.normalization,
                "meets_target": bool(best is not None)},
    )
