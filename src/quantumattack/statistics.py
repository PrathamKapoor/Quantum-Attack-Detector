"""Scenario-level event-rate statistics with correct uncertainty (D-041).

WHY this module exists
----------------------
The historical evaluator estimated warning/false-warning rates with a percentile
bootstrap over a degenerate binary vector (`scripts/evaluate_phase5.py::rate_ci`).
For an all-success or all-failure group this returns exactly ``[1.0, 1.0]`` or
``[0.0, 0.0]`` — a zero-width interval that asserts certainty from 7 or 15
correlated scenarios. That is statistically wrong and materially misleading in an
operational report.

WHAT
    Wilson score intervals for binomial event rates, with an explicit choice of
    the independent statistical unit, plus scenario-clustered bootstrap for
    continuous metrics (AUROC/AUPRC/Brier/lead time).

WHY
    A warning rate over N independent scenarios is a binomial proportion; Wilson
    intervals are well defined at 0 and 1 and remain inside [0,1]. Continuous
    metrics computed over thousands of correlated windows from a handful of
    scenarios must be resampled at SCENARIO level, not at window level.

HOW
    `wilson_interval(k, n)` for event counts; `scenario_cluster_bootstrap` that
    resamples whole scenarios with a recorded seed for reproducible intervals.
    Empty groups return None (undefined), never 0.0.

WHEN
    Evaluation and reporting of warning success rates, false-alarm rates, AUROC
    and lead-time uncertainty. Never during training.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import numpy as np

__all__ = [
    "EventRateCI",
    "wilson_interval",
    "scenario_cluster_bootstrap",
    "BootstrapCI",
]


@dataclass(frozen=True)
class EventRateCI:
    """Point estimate + Wilson interval for a binomial event rate."""

    successes: int
    n: int
    point: float | None
    ci_low: float | None
    ci_high: float | None
    method: str = "wilson"
    confidence: float = 0.95

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class BootstrapCI:
    """Percentile bootstrap interval for a continuous metric."""

    point: float | None
    ci_low: float | None
    ci_high: float | None
    n_clusters: int
    n_boot: int
    seed: int
    method: str = "scenario_cluster_percentile_bootstrap"

    def to_dict(self) -> dict:
        return asdict(self)


def wilson_interval(
    successes: int,
    n: int,
    confidence: float = 0.95,
) -> EventRateCI:
    """Wilson score interval for a binomial proportion.

    Correctly non-degenerate at successes == 0 and successes == n, unlike the
    percentile bootstrap previously used. Uses a normal quantile via the
    inverse-error-function approximation (no scipy dependency required at call
    sites; matches scipy.stats.norm.ppf to ~1e-9 over the relevant range).

    Returns all-None metrics when n == 0 (undefined, not zero).
    """
    if n < 0 or successes < 0:
        raise ValueError(f"invalid counts: successes={successes}, n={n}")
    if successes > n:
        raise ValueError(f"successes ({successes}) cannot exceed n ({n})")
    if n == 0:
        return EventRateCI(successes, 0, None, None, None, confidence=confidence)

    phat = successes / n
    z = _norm_ppf(0.5 + confidence / 2.0)
    denom = 1.0 + (z * z) / n
    center = (phat + (z * z) / (2.0 * n)) / denom
    half = (z / denom) * math.sqrt(phat * (1.0 - phat) / n + (z * z) / (4.0 * n * n))
    return EventRateCI(
        successes=int(successes),
        n=int(n),
        point=float(phat),
        ci_low=float(max(0.0, center - half)),
        ci_high=float(min(1.0, center + half)),
        confidence=confidence,
    )


def scenario_cluster_bootstrap(
    per_scenario_values: dict[str, float],
    metric_fn,
    n_boot: int = 2000,
    seed: int = 2026,
    confidence: float = 0.95,
) -> BootstrapCI:
    """Percentile bootstrap that resamples WHOLE SCENARIOS (clusters).

    Parameters
    ----------
    per_scenario_values:
        Mapping scenario_id -> a value aggregated within that scenario (e.g. the
        mean probability, or the count of qualifying rows). Each scenario is one
        independent unit of replication.
    metric_fn:
        Callable receiving the resampled list of per-scenario values and
        returning a scalar metric (AUROC, Brier, median lead time, ...).
        Must return None/NaN for undefined cases so they can be handled
        explicitly rather than silently dropped.

    Notes
    -----
    Resamples the *scenarios*, not the windows, so correlated telemetry windows
    from one simulation are never treated as independent observations. Undefined
    resamples (metric_fn returns None/NaN, or degenerate single-class data) are
    counted and reported via the returned point/None values rather than being
    silently discarded from a narrower interval.
    """
    keys = list(per_scenario_values)
    n = len(keys)
    if n == 0:
        return BootstrapCI(None, None, None, 0, n_boot, seed)
    values = [per_scenario_values[k] for k in keys]

    point = _safe_metric(metric_fn, values)
    if point is None:
        return BootstrapCI(None, None, None, n, n_boot, seed)

    rng = np.random.default_rng(seed)
    stats: list[float] = []
    failed = 0
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        sample = [values[i] for i in idx]
        s = _safe_metric(metric_fn, sample)
        if s is None:
            failed += 1
            continue
        stats.append(s)
    if not stats:
        return BootstrapCI(point, None, None, n, n_boot, seed)
    alpha = (1.0 - confidence) / 2.0
    lo = float(np.percentile(stats, 100 * alpha))
    hi = float(np.percentile(stats, 100 * (1 - alpha)))
    return BootstrapCI(point, lo, hi, n, n_boot, seed)


def _safe_metric(metric_fn, values: list):
    try:
        out = metric_fn(values)
    except (ValueError, ZeroDivisionError, FloatingPointError):
        return None
    if out is None:
        return None
    try:
        f = float(out)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _norm_ppf(q: float) -> float:
    """Inverse standard-normal CDF (Acklam's rational approximation).

    Accurate to ~1e-9 absolute error for q in (0,1) — far tighter than needed
    for a 95% interval — and avoids forcing scipy as a hard runtime dependency
    of this module.
    """
    if not 0.0 < q < 1.0:
        raise ValueError("q must be in (0,1)")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if q < plow:
        u = math.sqrt(-2 * math.log(q))
        return (((((c[0]*u+c[1])*u+c[2])*u+c[3])*u+c[4])*u+c[5]) / ((((d[0]*u+d[1])*u+d[2])*u+d[3])*u+1)
    if q > phigh:
        u = math.sqrt(-2 * math.log(1 - q))
        return -(((((c[0]*u+c[1])*u+c[2])*u+c[3])*u+c[4])*u+c[5]) / ((((d[0]*u+d[1])*u+d[2])*u+d[3])*u+1)
    u = q - 0.5
    r = u * u
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*u / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)