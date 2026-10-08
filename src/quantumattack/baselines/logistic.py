"""Logistic-regression forecasting baseline (master prompt §17-§27).

Deliberately simple: does causal historical telemetry contain enough information
for useful pre-onset prediction at all? Separate logistic models per horizon
(Phase 1 horizons; master prompt §20).

LEAKAGE RULES (master prompt §24/§25):
  - scaler fit on TRAIN scenarios only; val/test transformed;
  - no test-set feature selection, thresholds, or hyperparameters;
  - restricted columns (attack metadata, labels, eval-only) never enter X.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from ..features import compute_features, derived_feature_names
from ..feature_config import FeatureConfig
from ..dataset import RESTRICTED_COLUMNS
from .splits import Split


@dataclass(frozen=True)
class ModelConfig:
    """Logistic baseline configuration (recorded for versioning, master prompt §43)."""

    horizons: tuple[int, ...] = (10, 25, 50, 100)
    C: float = 1.0                    # inverse regularization strength
    class_weight: str | None = "balanced"
    max_iter: int = 1000
    random_state: int = 0
    feature_group: str = "D"          # A: base only | B: +diffs | C: +temporal | D: all
    min_history_blocks: int = 100     # skip blocks without full history (L)

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: (list(v) if isinstance(v, tuple) else v) for k, v in d.items()}


# Ablation feature groups (master prompt §38)
def feature_group_columns(group: str, base_columns: list[str]) -> list[str]:
    """A: base telemetry only · B: +first differences · C: +temporal stats (rolling/
    EWMA/CUSUM/KS/AC) · D: all candidate causal features (B+C combined + slopes)."""
    derived = derived_feature_names()
    diffs = [c for c in derived if c.startswith(("d1_", "d2_"))]
    slopes = [c for c in derived if c.startswith("rs")]
    temporal = [c for c in derived if c.startswith(("rm", "rv", "ewma", "cusum", "ks_", "ac1_"))]
    if group == "A":
        return list(base_columns)
    if group == "B":
        return list(base_columns) + diffs
    if group == "C":
        return list(base_columns) + temporal
    if group == "D":
        return list(base_columns) + diffs + temporal + slopes
    raise ValueError(f"unknown feature group: {group!r} (A|B|C|D)")


def base_feature_columns(df: pd.DataFrame) -> list[str]:
    """Base telemetry columns = feature-class columns present in the frame
    (restricted columns excluded; master prompt §34)."""
    from ..dataset import FEATURE_COLUMNS as FEATURE_CLASS

    return [c for c in df.columns if c in FEATURE_CLASS]


def build_xy(
    frames: dict[str, pd.DataFrame],
    scenario_ids: list[str],
    horizon: int,
    model_config: ModelConfig,
    feature_columns: list[str],
    feature_cache: dict[str, pd.DataFrame] | None = None,
) -> tuple[np.ndarray, np.ndarray, list[tuple[str, int]]]:
    """Build X (features at t) and y_H (future labels) from scenario frames.

    y_H(t) = 1 iff t < onset ≤ t + H; 0 otherwise (INCLUDING t ≥ onset — the
    attack is no longer future; master prompt §19). Rows with insufficient
    feature history (t < min_history_blocks) are skipped (missing-history policy).

    feature_cache: memoizes computed features per scenario (features depend only
    on telemetry, never on the horizon — identical across horizon builds).
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
            # compute only when required AND not already computed (precomputed
            # feature frames already carry all derived columns — master prompt §46)
            cache[sid] = compute_features(df0) if (needed and not has) else df0
        feat = cache[sid]
        onset = int(feat["attack_onset"].iloc[0])
        n = len(feat)
        cols = [c for c in feature_columns if c in feat.columns]
        X = feat[cols].to_numpy(dtype=float)
        t_idx = np.arange(n)
        y = ((t_idx < onset) & (t_idx + horizon >= onset)).astype(int)
        mask = (t_idx >= model_config.min_history_blocks) & ~np.isnan(X).any(axis=1)
        X_parts.append(X[mask])
        y_parts.append(y[mask])
        index_parts.extend((sid, int(t)) for t in t_idx[mask])
    return np.vstack(X_parts), np.concatenate(y_parts), index_parts


@dataclass
class HorizonModel:
    """One fitted logistic model for one horizon."""

    horizon: int
    feature_columns: list[str]
    scaler_mean: np.ndarray
    scaler_std: np.ndarray
    coef: np.ndarray
    intercept: float
    model_config: dict


def fit_horizon_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    horizon: int,
    feature_columns: list[str],
    model_config: ModelConfig,
) -> HorizonModel:
    """Fit scaler (TRAIN ONLY) + logistic regression for one horizon."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.exceptions import ConvergenceWarning
    import warnings

    # scaler fit on TRAIN ONLY (master prompt §24)
    scaler_mean = X_train.mean(axis=0)
    scaler_std = X_train.std(axis=0)
    scaler_std = np.where(scaler_std < 1e-12, 1.0, scaler_std)
    Xs = (X_train - scaler_mean) / scaler_std

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        clf = LogisticRegression(
            C=model_config.C, class_weight=model_config.class_weight,
            max_iter=model_config.max_iter, random_state=model_config.random_state,
        )
        clf.fit(Xs, y_train)

    return HorizonModel(
        horizon=horizon,
        feature_columns=list(feature_columns),
        scaler_mean=scaler_mean,
        scaler_std=scaler_std,
        coef=clf.coef_[0].copy(),
        intercept=float(clf.intercept_[0]),
        model_config=model_config.to_dict(),
    )


def predict_proba(model: HorizonModel, X: np.ndarray) -> np.ndarray:
    """P(attack within H) from the fitted model (sigmoid of scaled features)."""
    Xs = (X - model.scaler_mean) / model.scaler_std
    z = Xs @ model.coef + model.intercept
    return 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))


def train_forecaster(
    frames: dict[str, pd.DataFrame],
    split: Split,
    model_config: ModelConfig | None = None,
    config: FeatureConfig | None = None,
) -> dict[int, HorizonModel]:
    """Train one logistic model per horizon on TRAIN scenarios only."""
    mc = model_config or ModelConfig()
    base_cols = base_feature_columns(next(iter(frames.values())))
    feature_cols = feature_group_columns(mc.feature_group, base_cols)
    models: dict[int, HorizonModel] = {}
    feature_cache: dict[str, pd.DataFrame] = {}
    for h in mc.horizons:
        X_train, y_train, _ = build_xy(frames, split.train, h, mc, feature_cols, feature_cache)
        if len(np.unique(y_train)) < 2:
            raise RuntimeError(
                f"horizon {h}: training data has one class ({y_train.sum()} positives) — "
                "increase dataset or adjust min_history_blocks"
            )
        models[h] = fit_horizon_model(X_train, y_train, h, feature_cols, mc)
    return models


def predict_frames(
    frames: dict[str, pd.DataFrame],
    scenario_ids: list[str],
    models: dict[int, HorizonModel],
    model_config: ModelConfig | None = None,
) -> pd.DataFrame:
    """Predict P(attack within H) for all horizons over the given scenarios.

    Output (master prompt §26): scenario_id, block_index, timestamp, per-horizon
    p_attack_future_h{H}, y_true_h{H}, attack_onset (metadata for evaluation).
    """
    mc = model_config or ModelConfig()
    rows: list[dict] = []
    cache = getattr(predict_frames, "_cache", None)
    if cache is None:
        cache = {}
        predict_frames._cache = cache
    for sid in scenario_ids:
        if sid not in cache:
            df0 = frames[sid]
            has = any(c.startswith("d1_") for c in df0.columns)
            cache[sid] = df0 if has else compute_features(df0)
        feat = cache[sid]
        n = len(feat)
        onset = int(feat["attack_onset"].iloc[0])
        t_idx = np.arange(n)
        # use the union of feature columns across horizon models (same set here)
        feature_cols = models[mc.horizons[0]].feature_columns
        cols = [c for c in feature_cols if c in feat.columns]
        X = feat[cols].to_numpy(dtype=float)
        valid = (t_idx >= mc.min_history_blocks) & ~np.isnan(X).any(axis=1)
        y = {h: ((t_idx < onset) & (t_idx + h >= onset)).astype(int) for h in mc.horizons}
        for t in range(n):
            if not valid[t]:
                continue
            row: dict = {
                "scenario_id": sid,
                "block_index": t,
                "timestamp_ms": float(feat["timestamp_ms"].iloc[t]),
                "attack_onset": onset,
            }
            X_t = X[t:t + 1]
            for h, m in models.items():
                row[f"p_attack_future_h{h}"] = float(predict_proba(m, X_t)[0])
                row[f"y_true_h{h}"] = int(y[h][t])
            # current-state label for context (evaluation only, never a forecasting target)
            row["current_attack"] = int(t >= onset)
            # metadata for evaluation (never model inputs)
            row["attack_type"] = str(feat["attack_type"].iloc[0])
            row["scenario_class"] = str(feat["scenario_class"].iloc[0])
            rows.append(row)
    return pd.DataFrame(rows)
