"""Benign environmental confounders (docs/precursor-taxonomy.md §Environmental confounders).

All processes here are BENIGN: small magnitudes, no attack operating points.
Each step advances the OU processes with the seeded environment stream —
bit-identical between matched-counterfactual arms.
"""
from __future__ import annotations

import math

from dataclasses import dataclass

from ..rng import make_rng
from ..config import EnvironmentConfig


def _ou_step(x: float, theta: float, sigma: float, rng) -> float:
    """One Ornstein-Uhlenbeck step: x' = x - theta*x + sigma*N(0,1)."""
    return x - theta * x + sigma * rng.normal(0.0, 1.0)


@dataclass
class EnvironmentState:
    """Mutable per-scenario benign environment state."""

    config: EnvironmentConfig
    temperature_c: float
    det_temperature_c: float
    lo_thermal_factor: float           # benign thermal coupling into LO power
    clock_offset_ns: float
    clock_drift_ppb: float
    fiber_loss_delta_db: float         # OU wander (added to channel base loss)
    background_spike: float            # current benign spike contribution (SNU)
    # benign calibration wander (OU; smaller magnitude than attack ramps, no target)
    det_gain_delta: float = 0.0
    det_gain_plus_minus_delta: float = 0.0
    det_offset_delta: float = 0.0
    # benign thermal coupling into excess noise (OU; temperature confounder §12)
    xi_thermal_delta: float = 0.0
    base_xi_snu: float = 0.01          # channel base level (for OU sigma scaling)
    # benign sudden disturbance episode (hard negative)
    episode_active: bool = False
    episode_remaining: int = 0
    episode_background: float = 0.0
    episode_clock_step: float = 0.0
    episode_fired: bool = False        # one episode max per scenario
    _block: int = 0

    @classmethod
    def create(cls, config: EnvironmentConfig, seed: int, base_xi_snu: float = 0.01) -> "EnvironmentState":
        rng = make_rng(seed, "environment")
        return cls(
            config=config,
            temperature_c=config.temperature_mean_c,
            det_temperature_c=config.temperature_mean_c,
            lo_thermal_factor=1.0,
            clock_offset_ns=0.0,
            clock_drift_ppb=0.0,
            fiber_loss_delta_db=0.0,
            background_spike=0.0,
            base_xi_snu=base_xi_snu,
        )

    def step(self, rng) -> None:
        """Advance all benign processes one block (10 ms)."""
        cfg = self.config
        self._block += 1
        # slow lab temperature: sinusoid (24 h cycle, fixed phase) + OU
        phase_rad = 2.0 * math.pi * (self._block * 0.01) / (24.0 * 3600.0)
        self.temperature_c = (
            cfg.temperature_mean_c
            + cfg.temperature_amplitude_c * math.sin(phase_rad + 0.7)
            + _ou_step(0.0, cfg.ou_theta, cfg.temperature_ou_sigma, rng)
        )
        self.det_temperature_c = self.temperature_c + _ou_step(
            0.0, cfg.ou_theta, cfg.temperature_ou_sigma, rng
        )
        # benign thermal coupling into LO power (small, wanders near 1.0)
        self.lo_thermal_factor = 1.0 + cfg.lo_thermal_coupling * (
            self.temperature_c - cfg.temperature_mean_c
        )
        # benign clock drift: frequency offset random walk -> accumulated offset
        self.clock_drift_ppb = _ou_step(
            self.clock_drift_ppb, cfg.ou_theta, cfg.clock_drift_ou_sigma_ppb, rng
        )
        self.clock_offset_ns += self.clock_drift_ppb * 1e-3  # ppb * 10 ms -> ns
        # benign fiber loss wander
        self.fiber_loss_delta_db = _ou_step(
            self.fiber_loss_delta_db, cfg.ou_theta, cfg.fiber_loss_ou_sigma_db, rng
        )
        # benign calibration wander (gain/offset OU drift; docs/precursor-taxonomy.md)
        self.det_gain_delta = _ou_step(
            self.det_gain_delta, cfg.ou_theta, cfg.det_gain_ou_sigma, rng
        )
        self.det_gain_plus_minus_delta = _ou_step(
            self.det_gain_plus_minus_delta, cfg.ou_theta, cfg.det_gain_ou_sigma * 0.5, rng
        )
        self.det_offset_delta = _ou_step(
            self.det_offset_delta, cfg.ou_theta, cfg.det_offset_ou_sigma, rng
        )
        # benign thermal coupling into excess noise (OU wander; §12 confounder)
        self.xi_thermal_delta = _ou_step(
            self.xi_thermal_delta, cfg.ou_theta, self.base_xi_snu * 0.1, rng
        )
        # benign background: OU + occasional spikes
        self.background_spike = max(
            0.0, _ou_step(self.background_spike, cfg.ou_theta, cfg.background_ou_sigma, rng)
        )
        if rng.random() < cfg.background_spike_prob:
            self.background_spike += (
                cfg.background_spike_sigma_mult * cfg.background_ou_sigma * abs(rng.normal())
            )
        # benign sudden disturbance episode (one max per scenario, prob-gated)
        if (
            not self.episode_fired
            and not self.episode_active
            and cfg.disturbance_episode_prob > 0
            and rng.random() < cfg.disturbance_episode_prob
        ):
            self.episode_active = True
            self.episode_fired = True
            self.episode_remaining = cfg.disturbance_duration_blocks
            self.episode_background = cfg.disturbance_background_sigma_mult * cfg.background_ou_sigma
            self.episode_clock_step = cfg.disturbance_clock_step_ns * (
                1.0 if rng.random() < 0.5 else -1.0
            )
        if self.episode_active:
            self.background_spike += self.episode_background
            self.clock_offset_ns += self.episode_clock_step / self.config.disturbance_duration_blocks
            self.episode_remaining -= 1
            if self.episode_remaining <= 0:
                self.episode_active = False
