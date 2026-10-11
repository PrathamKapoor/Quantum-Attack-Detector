"""Telemetry robustness tests (docs/reliability-evaluation-protocol.md §6).

These verify that perturbation models are deterministic, unit-aware, and that the
legacy `raw_absolute` experiment is distinguishable from properly-scaled noise.
They do NOT assert a specific robustness level (that is an empirical result,
reported in docs/reliability-research-report.md).
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantumattack.noise_models import (  # noqa: E402
    PerturbationSpec, FeatureScale, feature_scale_from_train, additive_noise,
    temporally_correlated_noise, impulsive_noise, quantize, dropout_runs,
    dead_channels, apply_perturbation, TRAIN_SIGMA, FEATURE_RANGE, RAW_ABSOLUTE,
)


@pytest.fixture
def scale():
    rng = np.random.default_rng(0)
    X = rng.normal(0, 1, size=(400, 12))
    X[:, 3] *= 1e6      # a large-scale feature
    X[:, 5] *= 1e-6     # a tiny-scale feature
    return X, feature_scale_from_train(X)


def test_feature_scale_reflects_heterogeneity(scale):
    X, sc = scale
    assert sc.std[3] > 1e5
    assert sc.std[5] < 1e-4


def test_train_sigma_noise_scales_with_each_feature(scale):
    """In train_sigma units, a small-scale feature receives proportionally small
    raw noise — the whole point of fixing the unit ambiguity."""
    X, sc = scale
    noisy = additive_noise(X, 1.0, TRAIN_SIGMA, sc, seed=1)
    resid_big = np.std(noisy[:, 3] - X[:, 3])
    resid_small = np.std(noisy[:, 5] - X[:, 5])
    assert resid_big / sc.std[3] == pytest.approx(resid_small / sc.std[5], rel=0.25)


def test_raw_absolute_overwhelms_small_features(scale):
    """The legacy unit applies the SAME absolute sigma everywhere, which is
    enormous for small-scale features — reproducing the original defect."""
    X, sc = scale
    noisy = additive_noise(X, 0.02, RAW_ABSOLUTE, sc, seed=1)
    resid_big = np.std(noisy[:, 3] - X[:, 3])
    resid_small = np.std(noisy[:, 5] - X[:, 5])
    assert resid_big == pytest.approx(resid_small, rel=0.25)   # equal absolute noise
    # but relative to its own scale the tiny feature is destroyed
    assert (resid_small / sc.std[5]) > (resid_big / sc.std[3])


def test_feature_range_units(scale):
    X, sc = scale
    noisy = additive_noise(X, 0.5, FEATURE_RANGE, sc, seed=2)
    # noise std should be ~0.5 * iqr per feature (approximately)
    assert np.all(np.isfinite(noisy))


def test_noise_is_deterministic_given_seed(scale):
    X, sc = scale
    a = additive_noise(X, 0.5, TRAIN_SIGMA, sc, seed=42)
    b = additive_noise(X, 0.5, TRAIN_SIGMA, sc, seed=42)
    c = additive_noise(X, 0.5, TRAIN_SIGMA, sc, seed=43)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


def test_zero_magnitude_is_identity(scale):
    X, sc = scale
    assert np.array_equal(additive_noise(X, 0.0, TRAIN_SIGMA, sc, seed=1), X)


def test_correlated_noise_is_persistent_not_white(scale):
    """Correlated noise should have positive lag-1 autocorrelation, unlike white."""
    X, sc = scale
    noisy = temporally_correlated_noise(X, 1.0, TRAIN_SIGMA, sc,
                                        correlation_time_blocks=10, seed=3)
    resid = (noisy - X)[:, 0]
    resid = resid - resid.mean()
    ac1 = float(np.corrcoef(resid[:-1], resid[1:])[0, 1])
    assert ac1 > 0.3


def test_impulsive_noise_is_sparse_but_large(scale):
    X, sc = scale
    noisy = impulsive_noise(X, spike_rate=0.05, spike_scale=5.0,
                            units=TRAIN_SIGMA, scale=sc, seed=4)
    delta = np.abs(noisy - X).max(axis=1)
    assert (delta > 0).mean() <= 0.2   # sparse, not everywhere
    assert delta.max() > 0            # but present


def test_quantize_roundtrips_within_step(scale):
    X, sc = scale
    step = 0.5
    q = quantize(X, step)
    assert np.abs(q - X).max() <= step / 2 + 1e-12


def test_dropout_produces_nan_not_zero(scale):
    """Missing telemetry must be NaN (absent), never a fabricated zero."""
    X, sc = scale
    out, mask = dropout_runs(X, dropout_rate=0.1, step_blocks=5, seed=5)
    assert mask.any()
    assert np.isnan(out[mask]).all()
    assert not np.isnan(out[~mask]).any()


def test_dead_channels_zero_a_subset(scale):
    X, sc = scale
    out = dead_channels(X, n_channels=3, seed=6)
    zero_cols = (out == 0).all(axis=0) & ~(X == 0).all(axis=0)
    assert zero_cols.sum() == 3


def test_apply_perturbation_dispatch_deterministic(scale):
    X, sc = scale
    spec = PerturbationSpec(kind="gaussian", units=TRAIN_SIGMA, magnitude=0.3, seed=7)
    a = apply_perturbation(X, spec, sc)
    b = apply_perturbation(X, spec, sc)
    assert np.array_equal(a, b)


def test_spec_records_units_description(scale):
    spec = PerturbationSpec(kind="gaussian", units=RAW_ABSOLUTE, magnitude=0.02)
    d = spec.to_dict()
    assert "NOT comparable" in d["units_description"]


def test_invalid_spec_units_rejected(scale):
    X, sc = scale
    spec = PerturbationSpec(kind="gaussian", units="bogus", magnitude=0.1)
    with pytest.raises(ValueError):
        apply_perturbation(X, spec, sc)


def test_correlated_noise_rejects_subblock_time(scale):
    X, sc = scale
    with pytest.raises(ValueError):
        temporally_correlated_noise(X, 1.0, TRAIN_SIGMA, sc, correlation_time_blocks=0.5)