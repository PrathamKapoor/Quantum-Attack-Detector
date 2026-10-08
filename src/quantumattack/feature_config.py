"""Feature configuration (master prompt §7): configurable windows/spans/policies.

Values chosen against the Phase 1 temporal design (docs/time-semantics.md):
1 block = 10 ms; window W=5 blocks (50 ms) is the Phase 1 aggregation window;
history L=100 blocks (1 s) is the model input span. Rolling windows {5, 25, 100}
cover block-scale, mid-scale, and full-history baselines. EWMA spans mirror the
rolling windows. CUSUM reference window = 100 blocks (warmup). KS comparison =
50 vs 50 blocks (recent vs older trailing baseline).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass(frozen=True)
class FeatureConfig:
    """Causal feature-layer configuration (all statistics trailing)."""

    # first/second-order backward differences
    differences_enabled: bool = True
    diff_columns: tuple[str, ...] = (
        "lo_power", "x_var", "transmittance", "excess_noise", "background",
        "snr", "skr_estimate", "det_gain", "det_imbalance", "qber_proxy",
        "saturation_frac", "clock_offset_ns", "xp_corr",
    )
    # trailing rolling statistics
    rolling_windows: tuple[int, ...] = (5, 25, 100)
    rolling_columns: tuple[str, ...] = (
        "lo_power", "x_var", "transmittance", "excess_noise", "background",
        "snr", "skr_estimate", "det_gain", "det_imbalance", "qber_proxy",
        "saturation_frac", "clock_offset_ns", "temperature", "xp_corr",
    )
    rolling_slope_windows: tuple[int, ...] = (25, 100)
    slope_columns: tuple[str, ...] = (
        "lo_power", "skr_estimate", "transmittance", "det_gain", "x_var",
    )
    # EWMA
    ewma_spans: tuple[int, ...] = (5, 25)
    ewma_columns: tuple[str, ...] = (
        "lo_power", "x_var", "skr_estimate", "background", "snr",
    )
    # CUSUM: reference = warmup window of the scenario (train-scenario constants later)
    cusum_enabled: bool = True
    cusum_reference_window: int = 100
    cusum_k: float = 0.5
    cusum_columns: tuple[str, ...] = (
        "lo_power", "x_var", "skr_estimate", "transmittance", "excess_noise",
        "background", "det_gain", "snr",
    )
    # KS change statistic: recent window vs preceding reference window
    ks_enabled: bool = True
    ks_recent_window: int = 50
    ks_reference_window: int = 50
    ks_columns: tuple[str, ...] = (
        "x_var", "background", "skr_estimate", "lo_power", "snr",
    )
    # trailing autocorrelation (lag 1)
    autocorr_window: int = 100
    autocorr_columns: tuple[str, ...] = ("lo_power", "skr_estimate", "x_var")

    def validate(self) -> None:
        if not self.rolling_windows or any(w < 2 for w in self.rolling_windows):
            raise ValueError(f"rolling_windows must be >= 2: {self.rolling_windows}")
        if self.cusum_reference_window < 10:
            raise ValueError(f"cusum_reference_window must be >= 10: {self.cusum_reference_window}")
        if self.cusum_k <= 0:
            raise ValueError(f"cusum_k must be positive: {self.cusum_k}")
        if self.ks_recent_window < 5 or self.ks_reference_window < 5:
            raise ValueError("KS windows must be >= 5")
        if not self.diff_columns:
            raise ValueError("diff_columns cannot be empty")

    def to_dict(self) -> dict:
        d = asdict(self)
        # tuples → lists for JSON/YAML serialization
        return {k: (list(v) if isinstance(v, tuple) else v) for k, v in d.items()}
