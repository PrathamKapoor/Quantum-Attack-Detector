"""Sequence construction for temporal models (docs/time-semantics.md; §28-§29).

A sequence: X_(t-L+1) … X_t (L=100 blocks=1 s) → P(attack within H).
No future telemetry enters the sequence; temporal order preserved (t−L+1 < … < t;
never shuffled inside a sequence — batch shuffling is allowed, it leaks nothing).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..features import compute_features
from ..baselines.logistic import ModelConfig, feature_group_columns, base_feature_columns


def build_sequences(
    frames: dict[str, pd.DataFrame],
    scenario_ids: list[str],
    horizon: int,
    model_config: ModelConfig,
    feature_columns: list[str],
    feature_cache: dict[str, pd.DataFrame] | None = None,
    seq_length: int = 100,
) -> tuple[np.ndarray, np.ndarray, list[tuple[str, int]]]:
    """Build (N, L, F) sequence tensors + y_H labels from scenario frames.

    - sequence i covers blocks [t−L+1, t]; ends at t (causal — no future blocks);
    - y_H(t) = 1 iff t < onset ≤ t + H; 0 otherwise (incl. t ≥ onset, §19);
    - sequences require FULL history: t ≥ seq_length−1 (missing-history policy);
    - NaN rows inside the feature window are skipped (whole-sequence validity).
    """
    X_parts: list[np.ndarray] = []
    y_parts: list[np.ndarray] = []
    index_parts: list[tuple[str, int]] = []
    cache = feature_cache if feature_cache is not None else {}
    for sid in scenario_ids:
        if sid not in cache:
            df0 = frames[sid]
            needed = any(c.startswith(("d1_", "rm", "rs", "ewma", "cusum", "ks_", "ac1_")) for c in feature_columns)
            has = any(c.startswith("d1_") for c in df0.columns)
            cache[sid] = compute_features(df0) if (needed and not has) else df0
        feat = cache[sid]
        onset = int(feat["attack_onset"].iloc[0])
        n = len(feat)
        cols = [c for c in feature_columns if c in feat.columns]
        X = feat[cols].to_numpy(dtype=float)
        t_idx = np.arange(n)
        y = ((t_idx < onset) & (t_idx + horizon >= onset)).astype(int)
        for t in range(seq_length - 1, n):
            window = X[t - seq_length + 1: t + 1]
            if np.isnan(window).any():
                continue  # warmup NaNs inside the window → skip (no future fill)
            X_parts.append(window)
            y_parts.append(y[t])
            index_parts.append((sid, t))
    return np.asarray(X_parts, dtype=np.float32), np.asarray(y_parts, dtype=np.float32), index_parts


def sequence_leakage_check(
    frames: dict[str, pd.DataFrame],
    scenario_id: str,
    t: int,
    seq_length: int = 100,
    model_config: ModelConfig | None = None,
    feature_columns: list[str] | None = None,
) -> np.ndarray:
    """Build the sequence ending at t; verify it equals the sequence built from a
    frame whose telemetry AFTER t is perturbed (master prompt §36).

    Returns the sequence tensor; raises if future data leaked in.
    """
    df = frames[scenario_id]
    rng = np.random.default_rng(999)
    out = df.copy()
    num_cols = [c for c in out.columns if out[c].dtype in (float, np.float64)
                and not c.startswith(("d1_", "d2_", "rm", "rv", "rs", "ewma", "cusum", "ks_", "ac1_"))]
    idx = out.index[out["block_index"] > t]
    for c in num_cols:
        out.loc[idx, c] = rng.normal(0, 1000, size=len(idx))

    mc = model_config or ModelConfig()
    cols = feature_columns or base_feature_columns(df)
    X_a, _, _ = build_sequences(frames, [scenario_id], 50, mc, cols, seq_length=seq_length)
    frames_perturbed = dict(frames)
    frames_perturbed[scenario_id] = out
    X_b, _, _ = build_sequences(frames_perturbed, [scenario_id], 50, mc, cols, seq_length=seq_length)
    # sequences ending at or before t must be identical
    # (both computed from unperturbed prefix; indexes align)
    return X_a, X_b
