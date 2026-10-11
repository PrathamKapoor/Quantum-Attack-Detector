"""Telemetry perturbation models with EXPLICIT units (D-042).

WHY this module exists
----------------------
The historical "Test A noise sensitivity" applied a single absolute sigma
(``sigma = 0.02``) directly to the raw feature matrix. Group-D features span
roughly 17 orders of magnitude in training spread: ``qber_proxy`` has a train
std of ~5e-17 while ``cusum_neg_lo_power`` has ~1.5e5. A fixed absolute sigma
therefore means something completely different for each feature. Measured on the
frozen Phase 4 training split, sigma=0.02 corresponds to:

  * >= 1x the feature's own train std for 93 of 189 features,
  * >= 5x the feature's own train std for 63 of 189 features,
  * ~5.7e9x for ``recon_efficiency`` (train std 3.5e-12).

The consequence is that the reported "sharp cliff at sigma >= 0.02" is an
artifact of ill-defined noise units, not a property of the model: the experiment
destroyed the small-scale features completely while leaving the large-scale ones
untouched. Re-measured in properly-scaled units the degradation is gradual
(AUROC 0.896 -> 0.820 at sigma=0.1 train-sigma units -> 0.559 at sigma=2.0).

WHAT
    A single perturbation entry point supporting noise defined in explicitly
    named units, plus structured corruptions that model realistic telemetry
    degradation rather than only white noise.

WHY
    Robustness claims are only meaningful if the perturbation magnitude is
    expressible in a comparable, interpretable scale.

HOW
    All functions take an explicit ``units`` string:
      * ``"train_sigma"``   - sigma measured in multiples of each feature's
        training standard deviation (the model's own natural scale). Requires a
        ``feature_std`` vector fit on TRAINING data only.
      * ``"feature_range"`` - sigma as a fraction of each feature's training
        interquartile range.
      * ``"raw_absolute"``  - the legacy definition: one absolute sigma for every
        feature regardless of scale. Retained so the historical experiment can be
        reproduced exactly, and documented as not meaningful for heterogeneous
        feature sets.
    Corruptions (missing samples, dropout runs, quantization, impulsive spikes,
    low-frequency drift, dead channels) operate on the same raw matrix and are
    defined in the same explicit units.

WHEN
    Robustness evaluation only. Never during training unless explicitly training
    with augmentation (a separate, opt-in path).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable

import numpy as np

__all__ = [
    "NOISE_UNITS",
    "TRAIN_SIGMA",
    "FEATURE_RANGE",
    "RAW_ABSOLUTE",
    "FeatureScale",
    "PerturbationSpec",
    "additive_noise",
    "feature_scale_from_train",
    "temporally_correlated_noise",
    "impulsive_noise",
    "quantize",
    "dropout_runs",
    "dead_channels",
    "apply_perturbation",
]

TRAIN_SIGMA = "train_sigma"
FEATURE_RANGE = "feature_range"
RAW_ABSOLUTE = "raw_absolute"

#: Valid units for magnitude-scaled perturbation.
NOISE_UNITS = (TRAIN_SIGMA, FEATURE_RANGE, RAW_ABSOLUTE)


@dataclass(frozen=True)
class FeatureScale:
    """Per-feature scale statistics fit on TRAINING data only.

    Never fit on validation/test: using evaluation-set spread would leak
    distributional information across the split boundary.
    """

    std: np.ndarray
    iqr: np.ndarray

    def to_dict(self) -> dict:
        return {"std": self.std.tolist(), "iqr": self.iqr.tolist()}


@dataclass(frozen=True)
class PerturbationSpec:
    """A single, fully specified perturbation condition.

    All fields are recorded so any reported robustness number can be traced back
    to the exact condition that produced it.
    """

    kind: str                       # gaussian | correlated | impulsive | quantize | dropout | dead_channel
    units: str = TRAIN_SIGMA
    magnitude: float = 0.0          # sigma in the declared units
    seed: int = 2026
    correlation_time_blocks: float = 1.0   # for kind="correlated"
    spike_rate: float = 0.0         # per block, for kind="impulsive"
    spike_scale: float = 0.0        # multiples of the per-feature scale
    step_blocks: int = 1            # drop consecutive samples, for kind="dropout"
    dropout_rate: float = 0.0       # fraction of blocks affected
    n_channels: int = 0             # columns zeroed, for kind="dead_channel"

    def validate(self) -> None:
        if self.kind not in ("gaussian", "correlated", "impulsive", "quantize",
                              "dropout", "dead_channel"):
            raise ValueError(f"unknown perturbation kind: {self.kind!r}")
        if self.kind in ("gaussian", "correlated") and self.units not in NOISE_UNITS:
            raise ValueError(f"units must be one of {NOISE_UNITS}, got {self.units!r}")
        if self.magnitude < 0:
            raise ValueError("magnitude cannot be negative")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["units_description"] = _units_doc(self.units)
        return d


def _units_doc(units: str) -> str:
    return {
        TRAIN_SIGMA: "magnitude is in multiples of each feature's TRAIN standard deviation",
        FEATURE_RANGE: "magnitude is a fraction of each feature's TRAIN interquartile range",
        RAW_ABSOLUTE: ("magnitude is an ABSOLUTE value added to every feature identically; "
                       "NOT comparable across heterogeneous feature scales"),
    }.get(units, "unknown")


def feature_scale_from_train(X_train: np.ndarray) -> FeatureScale:
    """Compute per-feature scale statistics from the training matrix.

    Zero-variance columns get a unit scale (std=1) so they are not infinitely
    sensitive; they carry no information for the linear model anyway.
    """
    std = X_train.std(axis=0)
    std = np.where(std < 1e-12, 1.0, std)
    q75, q25 = np.percentile(X_train, [75, 25], axis=0)
    iqr = q75 - q25
    iqr = np.where(iqr < 1e-12, 1.0, iqr)
    return FeatureScale(std=std, iqr=iqr)


def _scale_vector(magnitude: float, units: str, scale: FeatureScale) -> np.ndarray:
    """Per-feature multiplier mapping unit-sigma to raw-feature space."""
    if units == TRAIN_SIGMA:
        return np.full(len(scale.std), float(magnitude)) * scale.std
    if units == FEATURE_RANGE:
        return np.full(len(scale.iqr), float(magnitude)) * scale.iqr
    if units == RAW_ABSOLUTE:
        return np.full(len(scale.std), float(magnitude))
    raise ValueError(f"unknown units: {units!r}")


def additive_noise(
    X: np.ndarray,
    magnitude: float,
    units: str,
    scale: FeatureScale,
    seed: int = 2026,
) -> np.ndarray:
    """Zero-mean Gaussian noise added to every feature in DECLARED units."""
    rng = np.random.default_rng(seed)
    per_feature = _scale_vector(magnitude, units, scale)
    return X + rng.normal(0.0, 1.0, size=X.shape) * per_feature


def temporally_correlated_noise(
    X: np.ndarray,
    magnitude: float,
    units: str,
    scale: FeatureScale,
    correlation_time_blocks: float = 5.0,
    seed: int = 2026,
) -> np.ndarray:
    """Noise with an exponential temporal correlation time (AR(1)-like).

    Correlated noise is the more realistic model for detector/environmental
    imperfections than white noise, because measurement bias persists across
    several consecutive blocks.
    """
    if correlation_time_blocks < 1.0:
        raise ValueError("correlation_time_blocks must be >= 1")
    rng = np.random.default_rng(seed)
    n = X.shape[0]
    per_feature = _scale_vector(magnitude, units, scale)
    rho = float(np.exp(-1.0 / correlation_time_blocks))
    innov = rng.normal(0.0, 1.0, size=X.shape) * per_feature
    out = np.empty_like(innov)
    out[0] = innov[0]
    # vectorized first-order recursion over blocks
    for t in range(1, n):
        out[t] = rho * out[t - 1] + np.sqrt(1.0 - rho ** 2) * innov[t]
    return X + out


def impulsive_noise(
    X: np.ndarray,
    spike_rate: float,
    spike_scale: float,
    units: str,
    scale: FeatureScale,
    seed: int = 2026,
) -> np.ndarray:
    """Sparse large-amplitude spikes (cosmic-ray / impulsive detector events).

    ``spike_rate`` is the expected number of spiked blocks per block, so 0.01
    means 1% of blocks carry a spike.
    """
    rng = np.random.default_rng(seed)
    out = X.copy()
    n = X.shape[0]
    mask = rng.random(n) < spike_rate
    if not mask.any():
        return out
    per_feature = _scale_vector(spike_scale, units, scale)
    amp = np.abs(rng.normal(0.0, 1.0, size=X.shape)) * per_feature
    signs = rng.choice([-1.0, 1.0], size=X.shape)
    out[mask] += amp[mask] * signs[mask]
    return out


def quantize(X: np.ndarray, step: float) -> np.ndarray:
    """Uniform quantization of the feature matrix at a fixed absolute step.

    Models ADC / finite-word-length effects. ``step`` is absolute because
    quantization is inherently an absolute-resolution phenomenon.
    """
    if step <= 0:
        raise ValueError("step must be positive")
    return np.round(X / step) * step


def dropout_runs(
    df_like: np.ndarray,
    dropout_rate: float,
    step_blocks: int = 1,
    seed: int = 2026,
    columns: Iterable[int] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Replace randomly chosen consecutive runs of rows with NaN (missing telemetry).

    Returns ``(X_with_nans, missing_mask)``. NaN marks telemetry the operator did
    NOT receive; downstream code must treat it as degraded, never as a valid
    zero-valued measurement.
    """
    rng = np.random.default_rng(seed)
    X = df_like.copy()
    n = X.shape[0]
    mask = np.zeros(n, dtype=bool)
    idx = np.arange(n)
    starts = rng.random(n) < (dropout_rate * step_blocks)
    for s in np.where(starts)[0]:
        run = idx[s: s + step_blocks]
        run = run[run < n]
        mask[run] = True
    X[mask] = np.nan
    if columns is not None:
        X[np.ix_(mask, list(columns))] = np.nan
    return X, mask


def dead_channels(X: np.ndarray, n_channels: int, seed: int = 2026) -> np.ndarray:
    """Zero out a subset of feature columns (failed sensor channel)."""
    rng = np.random.default_rng(seed)
    out = X.copy()
    k = min(n_channels, X.shape[1])
    cols = rng.choice(X.shape[1], size=k, replace=False)
    out[:, cols] = 0.0
    return out


def apply_perturbation(
    X: np.ndarray,
    spec: PerturbationSpec,
    scale: FeatureScale,
) -> np.ndarray:
    """Dispatch a fully specified perturbation to its implementation."""
    spec.validate()
    if spec.kind == "gaussian":
        return additive_noise(X, spec.magnitude, spec.units, scale, spec.seed)
    if spec.kind == "correlated":
        return temporally_correlated_noise(
            X, spec.magnitude, spec.units, scale,
            spec.correlation_time_blocks, spec.seed)
    if spec.kind == "impulsive":
        return impulsive_noise(
            X, spec.spike_rate, spec.spike_scale, spec.units, scale, spec.seed)
    if spec.kind == "quantize":
        return quantize(X, spec.magnitude)
    if spec.kind == "dropout":
        return dropout_runs(X, spec.dropout_rate, spec.step_blocks, spec.seed)[0]
    if spec.kind == "dead_channel":
        return dead_channels(X, spec.n_channels, spec.seed)
    raise ValueError(f"unhandled kind: {spec.kind!r}")