"""Intercept-resend attack (P0, class C — sudden onset).

Physical mechanism (docs/attack-taxonomy.md #1): Eve splits off a fraction of each
pulse (passive tap) and forwards a replacement state carrying her measurement noise.
Channel transmittance drops by the tap fraction; excess noise increases. No
precursor: a passive tap leaves no signature before activation.
"""
from __future__ import annotations

from .base import AttackModule
from ..config import AttackConfig


class InterceptResendAttack(AttackModule):
    attack_type = "intercept_resend"
    precursor_class = "C"

    def __init__(self, config: AttackConfig, seed: int):
        super().__init__(config, seed)
        # deterministic onset; small per-run jitter in resend noise (attack stream)
        self._noise_jitter = 1.0 + self.rng.normal(0.0, 0.02)

    def step(self, state, block_index: int) -> None:
        if block_index < self.onset_block:
            return
        # sudden step change: tap inserted, resend begins
        state.channel.tap_fraction = self.config.tap_fraction
        state.channel.attack_excess_noise = (
            state.channel.excess_noise_snu
            * (self.config.resend_noise_mult - 1.0)
            * self._noise_jitter
        )
