"""Causal derived features (docs/feature-spec.md; master prompt §4-§11).

EVERY statistic is trailing (window ends at t, inclusive); derivatives are backward
differences. Features return NaN until minimum history exists (warmup) — never
zeros, never partial-window values, never future samples (leakage-safe by design).

Missing-history policy (master prompt §8): explicit NaN + minimum-history
requirement. Each feature's warmup length is in FEATURE_SCHEMA metadata.
"""
from __future__ import annotations

import math

import numpy as np

from .feature_config import FeatureConfig

FEATURE_SCHEMA_VERSION = "2"


# ---------------------------------------------------------------------------
# Level-1: backward differences
# ---------------------------------------------------------------------------
def d1(x: np.ndarray) -> np.ndarray:
    """d1_t = x_t − x_(t−1); NaN for t<1. Causal (backward difference)."""
    out = np.full_like(x, np.nan, dtype=float)
    out[1:] = x[1:] - x[:-1]
    return out


def d2(x: np.ndarray) -> np.ndarray:
    """d2_t = x_t − 2x_(t−1) + x_(t−2); NaN for t<2. Causal."""
    out = np.full_like(x, np.nan, dtype=float)
    if len(x) > 2:
        out[2:] = x[2:] - 2.0 * x[1:-1] + x[:-2]
    return out


# ---------------------------------------------------------------------------
# Level-2: trailing rolling statistics
# ---------------------------------------------------------------------------
def _trailing_apply(x: np.ndarray, window: int, fn) -> np.ndarray:
    """Apply fn to the trailing window [t−window+1, t]; NaN until window samples."""
    out = np.full(len(x), np.nan, dtype=float)
    if len(x) < window:
        return out
    # rolling via cumulative windows (O(n·w) — sufficient for Phase 1 sizes)
    for t in range(window - 1, len(x)):
        out[t] = fn(x[t - window + 1: t + 1])
    return out


def rolling_mean(x: np.ndarray, window: int) -> np.ndarray:
    return _trailing_apply(x, window, np.mean)


def rolling_std(x: np.ndarray, window: int) -> np.ndarray:
    return _trailing_apply(x, window, np.std)


def rolling_min(x: np.ndarray, window: int) -> np.ndarray:
    return _trailing_apply(x, window, np.min)


def rolling_max(x: np.ndarray, window: int) -> np.ndarray:
    return _trailing_apply(x, window, np.max)


def rolling_slope(x: np.ndarray, window: int) -> np.ndarray:
    """OLS slope over the trailing window (units/block); NaN until warmup.

    Causal: the fit uses samples ≤ t only.
    """
    def _slope(w: np.ndarray) -> float:
        t = np.arange(len(w), dtype=float)
        t_mean, w_mean = t.mean(), w.mean()
        denom = ((t - t_mean) ** 2).sum()
        if denom < 1e-12:
            return 0.0
        return float(((t - t_mean) * (w - w_mean)).sum() / denom)

    return _trailing_apply(x, window, _slope)


# ---------------------------------------------------------------------------
# EWMA (streaming, causal)
# ---------------------------------------------------------------------------
def ewma(x: np.ndarray, span: int) -> np.ndarray:
    """E[t] = λ·x[t] + (1−λ)·E[t−1], λ = 2/(span+1), E[0] = x[0]. Causal."""
    lam = 2.0 / (span + 1.0)
    out = np.full(len(x), np.nan, dtype=float)
    if len(x) == 0:
        return out
    out[0] = x[0]
    for t in range(1, len(x)):
        out[t] = lam * x[t] + (1.0 - lam) * out[t - 1]
    return out


# ---------------------------------------------------------------------------
# CUSUM (streaming, causal; reference = warmup-window constants)
# ---------------------------------------------------------------------------
def cusum(x: np.ndarray, ref_window: int, k: float = 0.5) -> dict[str, np.ndarray]:
    """Two-sided CUSUM with μ0/σ0 from the FIRST ref_window blocks (warmup).

    S+ = max(0, S+ + (x[t] − μ0)/σ0 − k); S− symmetric (downward drift).
    Runs from t = ref_window; NaN before (insufficient history for the reference).
    LEAKAGE RULE: μ0/σ0 from the scenario's first warmup blocks only — never the
    full scenario (full-scenario statistics would leak future into past).
    """
    n = len(x)
    pos = np.full(n, np.nan, dtype=float)
    neg = np.full(n, np.nan, dtype=float)
    if n < ref_window:
        return {"pos": pos, "neg": neg}
    ref = x[:ref_window]
    mu0 = float(ref.mean())
    sigma0 = max(float(ref.std()), 1e-9)
    s_pos = 0.0
    s_neg = 0.0
    for t in range(ref_window, n):
        z = (x[t] - mu0) / sigma0
        s_pos = max(0.0, s_pos + z - k)
        s_neg = max(0.0, s_neg - z - k)
        pos[t] = s_pos
        neg[t] = s_neg
    return {"pos": pos, "neg": neg}


# ---------------------------------------------------------------------------
# KS change statistic (two trailing windows)
# ---------------------------------------------------------------------------
def ks_stat(x: np.ndarray, recent_window: int, ref_window: int) -> np.ndarray:
    """Two-sample KS statistic: trailing recent_window vs the immediately
    preceding ref_window. Both windows end ≤ t → causal. NaN until 2 windows.

    Statistic ∈ [0, 1]; larger = distribution change.
    """
    n = len(x)
    out = np.full(n, np.nan, dtype=float)
    need = recent_window + ref_window
    if n < need:
        return out

    def _ks(a: np.ndarray, b: np.ndarray) -> float:
        a_sorted, b_sorted = np.sort(a), np.sort(b)
        all_vals = np.concatenate([a_sorted, b_sorted])
        cdf_a = np.searchsorted(a_sorted, all_vals, side="right") / len(a_sorted)
        cdf_b = np.searchsorted(b_sorted, all_vals, side="right") / len(b_sorted)
        return float(np.max(np.abs(cdf_a - cdf_b)))

    for t in range(need - 1, n):
        recent = x[t - recent_window + 1: t + 1]
        ref = x[t - need + 1: t - recent_window + 1]
        out[t] = _ks(recent, ref)
    return out


# ---------------------------------------------------------------------------
# Trailing autocorrelation (lag 1)
# ---------------------------------------------------------------------------
def autocorr_lag1(x: np.ndarray, window: int) -> np.ndarray:
    """Lag-1 autocorrelation over the trailing window; NaN until warmup."""
    def _ac(w: np.ndarray) -> float:
        a, b = w[:-1], w[1:]
        sa, sb = a.std(), b.std()
        if sa < 1e-12 or sb < 1e-12:
            return 0.0
        return float(((a - a.mean()) * (b - b.mean())).mean() / (sa * sb))

    return _trailing_apply(x, window, _ac)


# ---------------------------------------------------------------------------
# Feature layer: compute the full candidate set for one scenario frame
# ---------------------------------------------------------------------------
def compute_features(df, config: FeatureConfig | None = None) -> "object":
    """Compute all causal features for a scenario DataFrame (per-block records).

    Returns a DataFrame: original columns + derived feature columns.
    All derived features are NaN during warmup (missing-history policy).
    """
    cfg = config or FeatureConfig()
    cfg.validate()
    derived: dict[str, np.ndarray] = {}

    # Level-1: differences (d1 + d2 per configured column)
    if cfg.differences_enabled:
        for col in cfg.diff_columns:
            if col not in df.columns:
                continue
            x = df[col].to_numpy(dtype=float)
            derived[f"d1_{col}"] = d1(x)
            derived[f"d2_{col}"] = d2(x)

    # Level-2: trailing rolling stats
    for col in cfg.rolling_columns:
        if col not in df.columns:
            continue
        x = df[col].to_numpy(dtype=float)
        for w in cfg.rolling_windows:
            derived[f"rm{w}_{col}"] = rolling_mean(x, w)
            derived[f"rv{w}_{col}"] = rolling_std(x, w)
    for col in cfg.slope_columns:
        if col not in df.columns:
            continue
        x = df[col].to_numpy(dtype=float)
        for w in cfg.rolling_slope_windows:
            derived[f"rs{w}_{col}"] = rolling_slope(x, w)

    # EWMA
    for col in cfg.ewma_columns:
        if col not in df.columns:
            continue
        x = df[col].to_numpy(dtype=float)
        for span in cfg.ewma_spans:
            derived[f"ewma{span}_{col}"] = ewma(x, span)

    # CUSUM (reference = warmup window)
    if cfg.cusum_enabled:
        for col in cfg.cusum_columns:
            if col not in df.columns:
                continue
            x = df[col].to_numpy(dtype=float)
            cs = cusum(x, cfg.cusum_reference_window, cfg.cusum_k)
            derived[f"cusum_pos_{col}"] = cs["pos"]
            derived[f"cusum_neg_{col}"] = cs["neg"]

    # KS change statistic
    if cfg.ks_enabled:
        for col in cfg.ks_columns:
            if col not in df.columns:
                continue
            x = df[col].to_numpy(dtype=float)
            derived[f"ks_{col}"] = ks_stat(x, cfg.ks_recent_window, cfg.ks_reference_window)

    # Trailing autocorrelation
    for col in cfg.autocorr_columns:
        if col not in df.columns:
            continue
        x = df[col].to_numpy(dtype=float)
        derived[f"ac1_{col}"] = autocorr_lag1(x, cfg.autocorr_window)

    import pandas as pd

    return pd.concat([df, pd.DataFrame(derived, index=df.index)], axis=1)


def feature_metadata(config: FeatureConfig | None = None) -> list[dict]:
    """Per-feature metadata (master prompt §9): traceability for audits/explainability."""
    cfg = config or FeatureConfig()
    meta: list[dict] = []
    if cfg.differences_enabled:
        for col in cfg.diff_columns:
            meta.append({"feature_name": f"d1_{col}", "source_columns": [col],
                         "operation": "backward_difference_1", "lookback": 2, "causal": True,
                         "units": col, "category": "difference"})
            meta.append({"feature_name": f"d2_{col}", "source_columns": [col],
                         "operation": "backward_difference_2", "lookback": 3, "causal": True,
                         "units": col, "category": "difference"})
    for col in cfg.rolling_columns:
        for w in cfg.rolling_windows:
            meta.append({"feature_name": f"rm{w}_{col}", "source_columns": [col],
                         "operation": "trailing_mean", "lookback": w, "causal": True,
                         "units": col, "category": "rolling"})
            meta.append({"feature_name": f"rv{w}_{col}", "source_columns": [col],
                         "operation": "trailing_std", "lookback": w, "causal": True,
                         "units": f"{col}^2", "category": "rolling"})
    for col in cfg.slope_columns:
        for w in cfg.rolling_slope_windows:
            meta.append({"feature_name": f"rs{w}_{col}", "source_columns": [col],
                         "operation": "trailing_ols_slope", "lookback": w, "causal": True,
                         "units": f"{col}/block", "category": "rolling"})
    for col in cfg.ewma_columns:
        for span in cfg.ewma_spans:
            meta.append({"feature_name": f"ewma{span}_{col}", "source_columns": [col],
                         "operation": "ewma", "lookback": span, "causal": True,
                         "units": col, "category": "ewma"})
    if cfg.cusum_enabled:
        for col in cfg.cusum_columns:
            for side in ("pos", "neg"):
                meta.append({"feature_name": f"cusum_{side}_{col}", "source_columns": [col],
                             "operation": f"cusum_{side}", "lookback": cfg.cusum_reference_window,
                             "causal": True, "units": "sigma", "category": "cusum"})
    if cfg.ks_enabled:
        for col in cfg.ks_columns:
            meta.append({"feature_name": f"ks_{col}", "source_columns": [col],
                         "operation": "ks_two_sample", "lookback": cfg.ks_recent_window + cfg.ks_reference_window,
                         "causal": True, "units": "unitless", "category": "change"})
    for col in cfg.autocorr_columns:
        meta.append({"feature_name": f"ac1_{col}", "source_columns": [col],
                     "operation": "trailing_autocorr_lag1", "lookback": cfg.autocorr_window,
                     "causal": True, "units": "unitless", "category": "autocorrelation"})
    return meta


def derived_feature_names(config: FeatureConfig | None = None) -> list[str]:
    """All derived feature column names (stable order)."""
    return [m["feature_name"] for m in feature_metadata(config)]
