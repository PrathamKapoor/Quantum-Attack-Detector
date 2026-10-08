"""Per-block telemetry record assembly (docs/telemetry-spec.md §Implemented features).

Collects ONE record per block from (protocol, channel, detector, environment, attack,
parameter estimate) state. Raw telemetry only — no model-specific feature engineering
beyond the two documented causal first-differences.
"""
from __future__ import annotations

import math

from typing import Any

from ..config import BLOCK_MS
from ..protocols.cvqkd import parameter_estimate
from ..channel.optical import ChannelState
from ..detectors.homodyne import DetectorState, measure_block
from ..environment.drift import EnvironmentState

# Feature columns (order-stable; docs/telemetry-spec.md §Column classification)
FEATURE_COLUMNS: tuple[str, ...] = (
    # source
    "mod_variance", "rep_rate_mhz",
    # local oscillator
    "lo_power", "lo_variance", "lo_sig_ratio", "lo_drift",
    # quantum measurements
    "x_mean", "x_var", "p_mean", "p_var", "xp_corr", "quad_std_ratio",
    # detector
    "det_gain", "det_offset", "det_imbalance", "det_efficiency", "saturation_frac",
    # timing
    "arr_residual", "jitter_ns", "clock_offset_ns", "clock_drift_ppb",
    # channel
    "transmittance", "fiber_loss_db", "excess_noise", "background", "snr",
    # security
    "qber_proxy", "skr_estimate", "secret_fraction", "recon_efficiency", "skr_drift",
    # environment/context
    "temperature", "det_temperature", "background_proxy", "calibration_state",
)

# Evaluation-only ground-truth state columns (never model inputs)
TRUE_COLUMNS: tuple[str, ...] = (
    "true_T", "true_xi", "true_lo_power", "true_det_gain", "true_det_offset",
    "true_background", "true_clock_offset", "true_channel_condition",
)


class TelemetryCollector:
    """Assembles per-block telemetry records; tracks causal first-differences."""

    def __init__(self, protocol, n_symbols_per_block: float = 1e6):
        self.protocol = protocol
        self.n_symbols = n_symbols_per_block
        self._prev_lo_power: float | None = None
        self._prev_skr: float | None = None

    def collect(
        self,
        clock,
        channel: ChannelState,
        det: DetectorState,
        env: EnvironmentState,
        attack_state: Any,
        rng,
    ) -> dict:
        """One record for the current block (clock.block_index)."""
        block = clock.block_index
        v_a = self.protocol.mod_variance_snu
        lo_hidden = getattr(attack_state, "lo_hidden_noise_factor", 0.0)

        # measurement (uses TRUE channel state incl. attack contributions)
        measured = measure_block(
            det=det,
            channel_T=channel.transmittance,
            excess_noise_snu=channel.excess_noise_snu + channel.attack_excess_noise,
            background_snu=channel.effective_background(),
            v_mod=v_a,
            protocol=self.protocol,
            clock_offset_ns=env.clock_offset_ns,
            n_symbols=self.n_symbols,
            rng=rng,
        )
        # parameter estimation (monitor-visible; LO attack hides part of attack noise)
        pest = parameter_estimate(self.protocol, channel, det, measured, lo_hidden)

        lo_power = det.lo_power * env.lo_thermal_factor
        background = channel.effective_background() + env.background_spike
        jitter = env.config.jitter_ns * (1.0 + 0.1 * abs(env.clock_drift_ppb))

        lo_drift = 0.0 if self._prev_lo_power is None else lo_power - self._prev_lo_power
        skr_drift = 0.0 if self._prev_skr is None else pest["skr_estimate"] - self._prev_skr
        self._prev_lo_power = lo_power
        self._prev_skr = pest["skr_estimate"]

        # qber proxy: normalized distortion indicator (CV-QKD has no QBER)
        qber_proxy = min(1.0, max(0.0, 1.0 - pest["i_ab"] / max(math.log2(1.0 + 10 ** (pest["snr"] / 10.0)), 1e-9)))

        record: dict[str, Any] = {
            "block_index": block,
            "timestamp_ms": block * BLOCK_MS,
            # source
            "mod_variance": v_a,
            "rep_rate_mhz": self.protocol.symbol_rate_mbaud,
            # LO
            "lo_power": lo_power,
            "lo_variance": measured["lo_variance"],
            "lo_sig_ratio": lo_power / max(1e-12, v_a * channel.transmittance),
            "lo_drift": lo_drift,
            # measurements
            "x_mean": measured["x_mean"],
            "x_var": measured["x_var"],
            "p_mean": measured["p_mean"],
            "p_var": measured["p_var"],
            "xp_corr": measured["xp_corr"],
            "quad_std_ratio": measured["quad_std_ratio"],
            # detector
            "det_gain": det.det_gain,
            "det_offset": det.det_offset_snu,
            "det_imbalance": det.det_imbalance,
            "det_efficiency": det.det_efficiency,
            "saturation_frac": measured["saturation_frac"],
            # timing
            "arr_residual": env.clock_offset_ns + jitter * rng.normal(0.0, 1.0),
            "jitter_ns": jitter,
            "clock_offset_ns": env.clock_offset_ns,
            "clock_drift_ppb": env.clock_drift_ppb,
            # channel
            "transmittance": channel.transmittance,
            "fiber_loss_db": channel.fiber_loss_db,
            "excess_noise": channel.excess_noise_snu + channel.attack_excess_noise,
            "background": background,
            "snr": pest["snr"],
            # security
            "qber_proxy": qber_proxy,
            "skr_estimate": pest["skr_estimate"],
            "secret_fraction": 0.9,
            "recon_efficiency": self.protocol.recon_efficiency,
            "skr_drift": skr_drift,
            # environment/context
            "temperature": env.temperature_c,
            "det_temperature": env.det_temperature_c,
            "background_proxy": background,
            "calibration_state": max(0.0, 1.0 - abs(det.det_gain - 1.0) / 0.5),
            # ground-truth state (evaluation-only; never model inputs)
            "true_T": channel.transmittance,
            "true_xi": channel.excess_noise_snu + channel.attack_excess_noise,
            "true_lo_power": lo_power,
            "true_det_gain": det.det_gain,
            "true_det_offset": getattr(det, "det_offset_target", det.det_offset_snu),
            "true_background": background,
            "true_clock_offset": env.clock_offset_ns,
            "true_channel_condition": self._channel_condition(channel),
        }
        return record

    @staticmethod
    def _channel_condition(channel: ChannelState) -> int:
        if channel.jamming_power_snu > 0:
            return 2  # JAMMED
        base_t = channel.base_transmittance
        if channel.transmittance < 0.95 * base_t:
            return 1  # DEGRADED
        return 0  # NORMAL
