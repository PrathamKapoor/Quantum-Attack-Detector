"""Feature layer tests (master prompt §10/§11/§47).

- HISTORICAL INVARIANCE: modifying telemetry after t does not change features ≤ t
  (catches accidental future leakage)
- determinism: same input → same features
- schema stability, dimensions, NaN warmup policy
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantumattack.features import (  # noqa: E402
    compute_features, derived_feature_names, feature_metadata, d1, d2,
    rolling_mean, rolling_std, rolling_slope, ewma, cusum, ks_stat,
    autocorr_lag1, FEATURE_SCHEMA_VERSION,
)
from quantumattack.feature_config import FeatureConfig  # noqa: E402


@pytest.fixture(scope="module")
def scenario_df():
    repo = Path(__file__).resolve().parents[1]
    return pd.read_parquet(repo / "data" / "phase1" / "attack-lo-manipulation-s1.parquet")


# ---------------------------------------------------------------------------
# Historical invariance (THE powerful causality test, master prompt §10)
# ---------------------------------------------------------------------------
def _perturb_after(df: pd.DataFrame, t: int, seed: int = 999) -> pd.DataFrame:
    """Replace all telemetry AFTER block t with extreme noise (future data)."""
    out = df.copy()
    n = len(out)
    rng = np.random.default_rng(seed)
    num_cols = [c for c in out.columns
                if out[c].dtype in (float, np.float64) and not c.startswith(("d1_", "d2_", "rm", "rv", "rs", "ewma", "cusum", "ks_", "ac1_"))]
    for c in num_cols:
        idx = out.index[out["block_index"] > t] if "block_index" in out.columns else out.index[t + 1:]
        out.loc[idx, c] = rng.normal(0, 1000, size=len(idx))
    return out


def test_historical_invariance_differences(scenario_df):
    t = 100
    a = compute_features(scenario_df)
    b = compute_features(_perturb_after(scenario_df, t))
    for col in ("d1_lo_power", "d2_lo_power", "d1_x_var", "d1_skr_estimate"):
        va = a.loc[a["block_index"] <= t, col].to_numpy()
        vb = b.loc[b["block_index"] <= t, col].to_numpy()
        assert np.array_equal(va, vb, equal_nan=True), f"future leak in {col}"


def test_historical_invariance_rolling(scenario_df):
    t = 100
    a = compute_features(scenario_df)
    b = compute_features(_perturb_after(scenario_df, t))
    for col in ("rm5_lo_power", "rm25_lo_power", "rm100_lo_power", "rv5_x_var", "rv100_skr_estimate", "rs25_lo_power"):
        va = a.loc[a["block_index"] <= t, col].to_numpy()
        vb = b.loc[b["block_index"] <= t, col].to_numpy()
        assert np.array_equal(va, vb, equal_nan=True), f"future leak in {col}"


def test_historical_invariance_ewma_cusum(scenario_df):
    t = 150
    a = compute_features(scenario_df)
    b = compute_features(_perturb_after(scenario_df, t))
    for col in ("ewma5_lo_power", "ewma25_skr_estimate", "cusum_pos_lo_power", "cusum_neg_skr_estimate"):
        va = a.loc[a["block_index"] <= t, col].to_numpy()
        vb = b.loc[b["block_index"] <= t, col].to_numpy()
        assert np.array_equal(va, vb, equal_nan=True), f"future leak in {col}"


def test_historical_invariance_ks_autocorr(scenario_df):
    t = 150
    a = compute_features(scenario_df)
    b = compute_features(_perturb_after(scenario_df, t))
    for col in ("ks_x_var", "ks_background", "ac1_lo_power"):
        va = a.loc[a["block_index"] <= t, col].to_numpy()
        vb = b.loc[b["block_index"] <= t, col].to_numpy()
        assert np.array_equal(va, vb, equal_nan=True), f"future leak in {col}"


def test_post_onset_features_actually_change(scenario_df):
    """Sanity check for the invariance test: the perturbation DOES change features
    after t (otherwise the invariance test is vacuous)."""
    t = 100
    a = compute_features(scenario_df)
    b = compute_features(_perturb_after(scenario_df, t))
    after = a["block_index"] > t
    assert not np.allclose(
        a.loc[after, "rm5_lo_power"].to_numpy(),
        b.loc[after, "rm5_lo_power"].to_numpy(), equal_nan=True)


# ---------------------------------------------------------------------------
# Unit tests: known inputs → expected outputs
# ---------------------------------------------------------------------------
def test_d1_known_input():
    x = np.array([1.0, 3.0, 6.0, 10.0])
    out = d1(x)
    assert np.isnan(out[0])
    assert np.array_equal(out[1:], [2.0, 3.0, 4.0])


def test_d2_known_input():
    x = np.array([1.0, 3.0, 6.0, 10.0])
    out = d2(x)
    assert np.isnan(out[:2]).all()
    assert np.array_equal(out[2:], [1.0, 1.0])  # constant acceleration


def test_rolling_mean_trailing():
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    out = rolling_mean(x, 3)
    assert np.isnan(out[:2]).all()
    assert np.array_equal(out[2:], [2.0, 3.0, 4.0])  # trailing windows end at t


def test_rolling_std_nonnegative():
    x = np.array([1.0, 5.0, 2.0, 8.0, 3.0])
    out = rolling_std(x, 3)
    assert np.isnan(out[:2]).all()
    assert (out[2:] >= 0).all()


def test_rolling_slope_known():
    x = np.array([0.0, 1.0, 2.0, 3.0, 4.0])  # slope exactly 1
    out = rolling_slope(x, 5)
    assert np.isnan(out[:4]).all()
    assert abs(out[4] - 1.0) < 1e-12


def test_ewma_known():
    x = np.array([0.0, 10.0, 0.0])
    out = ewma(x, 5)  # λ = 2/(5+1) = 1/3
    assert out[0] == 0.0
    assert abs(out[1] - 10.0 / 3.0) < 1e-12
    assert abs(out[2] - 20.0 / 9.0) < 1e-12  # E2 = λ·0 + (1−λ)·E1 = (2/3)(10/3)


def test_cusum_reference_is_warmup_only():
    """CUSUM μ0/σ0 from FIRST ref_window blocks — not full scenario (leakage)."""
    n = 60
    x = np.concatenate([np.zeros(20), np.full(40, 100.0)])
    out = cusum(x, ref_window=20, k=0.5)
    assert np.isnan(out["pos"][:20]).all()
    # after the step, CUSUM accumulates: with μ0=0, σ0=0 (constant ref → clamp 1e-9)
    # z becomes huge → pos grows monotonically
    post = out["pos"][20:]
    assert (np.diff(post[~np.isnan(post)]) > 0).all()


def test_cusum_short_history_all_nan():
    x = np.ones(10)
    out = cusum(x, ref_window=100)
    assert np.isnan(out["pos"]).all() and np.isnan(out["neg"]).all()


def test_ks_stat_bounds_and_behavior():
    rng = np.random.default_rng(0)
    x = np.concatenate([rng.normal(0, 1, 60), rng.normal(5, 1, 60)])
    out = ks_stat(x, recent_window=50, ref_window=50)
    assert np.isnan(out[:99]).all()
    valid = out[~np.isnan(out)]
    assert ((valid >= 0) & (valid <= 1)).all()
    # distribution change detected: KS reaches 0.8 after the shift (strong change)
    assert valid[-1] >= 0.8


def test_autocorr_bounds():
    rng = np.random.default_rng(1)
    x = rng.normal(0, 1, 150)
    out = autocorr_lag1(x, 100)
    assert np.isnan(out[:99]).all()
    valid = out[~np.isnan(out)]
    assert ((valid >= -1) & (valid <= 1)).all()


def test_constant_series_autocorr_zero():
    out = autocorr_lag1(np.ones(120), 100)
    valid = out[~np.isnan(out)]
    assert (valid == 0).all()  # degenerate std → defined as 0, not NaN


# ---------------------------------------------------------------------------
# Determinism, schema, NaN policy (master prompt §11)
# ---------------------------------------------------------------------------
def test_feature_determinism(scenario_df):
    a = compute_features(scenario_df)
    b = compute_features(scenario_df)
    pd.testing.assert_frame_equal(a, b)


def test_schema_stable_columns(scenario_df):
    a = compute_features(scenario_df)
    assert list(a.columns) == list(scenario_df.columns) + derived_feature_names()


def test_schema_version_stable():
    assert FEATURE_SCHEMA_VERSION == "2"


def test_metadata_covers_all_derived_features():
    cfg = FeatureConfig()
    meta = feature_metadata(cfg)
    names = [m["feature_name"] for m in meta]
    assert names == derived_feature_names(cfg)
    assert len(names) == len(set(names)), "duplicate feature names in metadata"
    for m in meta:
        assert m["causal"] is True
        assert m["source_columns"] and m["operation"] and m["lookback"] >= 2


def test_warmup_nan_policy(scenario_df):
    """Features are NaN during warmup — never zeros, never future-filled."""
    feat = compute_features(scenario_df)
    n = len(feat)
    checks = {
        "d1_lo_power": 1, "rm100_lo_power": 99, "rm25_lo_power": 24,
        "cusum_pos_lo_power": 100, "ks_x_var": 99, "ac1_lo_power": 99,
        "rs100_lo_power": 99, "ewma5_lo_power": 0,
    }
    for col, expected_nan in checks.items():
        assert feat[col].isna().sum() == expected_nan, f"{col} NaN policy violated"


def test_no_infinite_values(scenario_df):
    feat = compute_features(scenario_df)
    num = feat.select_dtypes(include=[np.floating]).to_numpy()
    assert np.isinf(num).sum() == 0


def test_config_validation():
    with pytest.raises(ValueError):
        FeatureConfig(rolling_windows=(1,)).validate()
    with pytest.raises(ValueError):
        FeatureConfig(cusum_k=0.0).validate()
    with pytest.raises(ValueError):
        FeatureConfig(cusum_reference_window=1).validate()
    FeatureConfig().validate()  # default ok
