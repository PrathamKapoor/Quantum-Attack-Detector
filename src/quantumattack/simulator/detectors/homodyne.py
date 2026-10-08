"""Balanced heterodyne detector (docs/threat-model.md §2).

Holds gain/offset/imbalance/efficiency state and produces per-block quadrature
statistics. Attack modules and benign confounders modify state; measurement is a
pure function of (channel state, LO state, detector state, protocol config).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..rng import make_rng
from ..config import ProtocolConfig


@dataclass
class DetectorState:
    """Mutable per-scenario detector state."""

    det_efficiency: float              # trusted tau (benign OU wander)
    det_gain: float                    # multiplicative gain (both arms, benign/attack)
    det_gain_plus: float               # arm + gain (imbalance tracking)
    det_gain_minus: float              # arm - gain
    det_offset_snu: float              # additive offset (SNU)
    lo_power: float                    # LO power (normalized)
    lo_rin: float                      # relative intensity noise

    @classmethod
    def create(cls, protocol: ProtocolConfig, seed: int) -> "DetectorState":
        rng = make_rng(seed, "environment")
        return cls(
            det_efficiency=protocol.det_efficiency,
            det_gain=1.0,
            det_gain_plus=1.0 + rng.normal(0.0, 0.002),
            det_gain_minus=1.0 + rng.normal(0.0, 0.002),
            det_offset_snu=0.0,
            lo_power=1.0,
            lo_rin=0.01,
        )

    @property
    def det_imbalance(self) -> float:
        """Relative imbalance between the two balanced arms (signed; ±)."""
        s = self.det_gain_plus + self.det_gain_minus
        return (self.det_gain_plus - self.det_gain_minus) / s if s > 0 else 0.0


def measure_block(
    det: DetectorState,
    channel_T: float,
    excess_noise_snu: float,
    background_snu: float,
    v_mod: float,
    protocol: ProtocolConfig,
    clock_offset_ns: float,
    n_symbols: float,
    rng: "object" = None,
) -> dict:
    """Per-block heterodyne measurement: closed-form Gaussian statistics.

    Physical model (GMCS + heterodyne, per docs/telemetry-spec.md):
      V_meas,X = (tau*T*(V_A + 1 + xi + background) + t) * (g_LO * g_det)^2 + 1
      - the +1 is heterodyne's 3 dB vacuum penalty per quadrature
      - offsets shift the mean; saturation fraction is analytic
    Returns sufficient statistics (no per-symbol samples).
    """
    g_lo = det.lo_power
    g_det = det.det_gain
    scale = (g_lo * g_det) ** 2

    # channel+measurement variance per quadrature (SNU), before scaling
    v_base = det.det_efficiency * channel_T * (
        v_mod + 1.0 + excess_noise_snu + background_snu
    ) + protocol.electronic_noise_snu
    v_x = v_base * scale + 1.0
    v_p = v_base * scale + 1.0

    # means: zero unless offset (attack/bias); sampling noise ~ sigma/sqrt(N)
    mean_sampling_std_x = (v_x ** 0.5) / (n_symbols ** 0.5)
    mean_sampling_std_p = (v_p ** 0.5) / (n_symbols ** 0.5)
    x_mean = det.det_offset_snu * g_det * g_lo + rng.normal(0.0, mean_sampling_std_x)
    p_mean = det.det_offset_snu * g_det * g_lo + rng.normal(0.0, mean_sampling_std_p)

    # phase-noise proxy: clock offset couples a small X-P correlation
    corr = min(0.5, abs(clock_offset_ns) / 200.0)

    # LO intensity noise
    lo_var = (det.lo_rin * det.lo_power) ** 2 + 1e-6

    # saturation: analytic fraction of Gaussian samples beyond k_sat sigma
    # (jamming inflates variance/offsets -> sharp rise)
    k_sat = 5.0
    mean_shift = abs(det.det_offset_snu * g_det * g_lo)
    sat_frac = 2.0 * (1.0 - _phi((k_sat * v_x ** 0.5 - mean_shift) / max(v_x ** 0.5, 1e-12)))

    return {
        "x_mean": x_mean,
        "x_var": v_x,
        "p_mean": p_mean,
        "p_var": v_p,
        "xp_corr": corr,
        "quad_std_ratio": (v_x / v_p) ** 0.5,
        "lo_variance": lo_var,
        "saturation_frac": min(1.0, max(0.0, sat_frac)),
    }


def _phi(z: float) -> float:
    """Standard normal CDF."""
    import math

    return 0.5 * (1.0 + math.erf(z / 2.0 ** 0.5))
