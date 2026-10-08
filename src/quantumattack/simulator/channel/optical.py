"""Fiber quantum channel state (docs/threat-model.md §2).

Holds the causal chain: fiber loss state + attack tap → transmittance; excess noise;
background light. All state evolves per block; attacks modify only the fields their
physical mechanism justifies.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..rng import make_rng
from ..config import ChannelConfig


def loss_to_transmittance(length_km: float, attenuation_db_per_km: float) -> float:
    """Linear transmittance from dB attenuation: T = 10^(-A*L/10)."""
    return 10.0 ** (-attenuation_db_per_km * length_km / 10.0)


@dataclass
class ChannelState:
    """Mutable per-scenario channel state."""

    config: ChannelConfig
    base_transmittance: float          # from fiber length/attenuation
    fiber_loss_db: float               # current loss state (base + OU wander)
    excess_noise_snu: float            # current excess noise at Bob input
    background_snu: float              # background light at detector input
    tap_fraction: float = 0.0          # intercept-resend tap (0 = no attack)
    attack_excess_noise: float = 0.0   # added excess noise from attack mechanisms
    jamming_power_snu: float = 0.0     # injected jamming power (0 = no attack)

    @classmethod
    def create(cls, config: ChannelConfig, seed: int, ou_theta: float) -> "ChannelState":
        rng = make_rng(seed, "environment")
        t0 = loss_to_transmittance(config.length_km, config.attenuation_db_per_km)
        # small initial offsets so runs start inside the OU stationary distribution
        return cls(
            config=config,
            base_transmittance=t0,
            fiber_loss_db=config.attenuation_db_per_km * config.length_km
            + rng.normal(0.0, config.attenuation_db_per_km * config.length_km * 0.005),
            excess_noise_snu=config.base_excess_noise_snu * (1.0 + rng.normal(0.0, 0.1)),
            background_snu=config.base_background_snu * (1.0 + rng.normal(0.0, 0.1)),
            tap_fraction=0.0,
            attack_excess_noise=0.0,
            jamming_power_snu=0.0,
        )

    @property
    def transmittance(self) -> float:
        """Effective channel transmittance: fiber loss + attack tap."""
        t_loss = 10.0 ** (-self.fiber_loss_db / 10.0)
        return t_loss * (1.0 - self.tap_fraction)

    def effective_background(self) -> float:
        """Background at detector input incl. jamming."""
        return max(0.0, self.background_snu + self.jamming_power_snu)

    def effective_excess_noise(self, lo_hidden_factor: float = 0.0) -> float:
        """Excess noise INCLUDING attack contributions.

        lo_hidden_factor: fraction of the ATTACK-added excess noise that the LO
        attack hides from parameter estimation (mechanism of the ε̂-bias attack).
        True state keeps the full value; the estimator sees the reduced one.
        """
        total = self.excess_noise_snu + self.attack_excess_noise
        hidden = self.attack_excess_noise * lo_hidden_factor
        return max(0.0, total - hidden)
