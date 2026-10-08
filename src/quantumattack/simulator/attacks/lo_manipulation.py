"""Local-oscillator manipulation attack (P0, class A — gradual, PROJECT INFERENCE).

Physical mechanism (docs/attack-taxonomy.md #2): adversary attenuates the LO power
via a slowly-tuned path element (stochastic OU ramp — never a linear ramp), then the
ε̂-bias mechanism becomes operational at the attack operating point: parameter
estimation UNDER-estimates excess noise → SKR over-estimated (false security).

Precursor: class A ramp in [precursor_start, onset). LABEL: PROJECT INFERENCE —
synthetic research assumption, physics-plausible (docs/precursor-taxonomy.md).
"""
from __future__ import annotations

from .base import AttackModule
from ..config import AttackConfig


def _ou_step(x: float, theta: float, sigma: float, rng) -> float:
    return x - theta * x + sigma * rng.normal(0.0, 1.0)


class LOManipulationAttack(AttackModule):
    attack_type = "lo_manipulation"
    precursor_class = "A"

    def __init__(self, config: AttackConfig, seed: int):
        super().__init__(config, seed)
        # stochastic ramp duration drawn from [ramp_min, ramp_max]
        dur = int(self.rng.integers(config.ramp_min_blocks, config.ramp_max_blocks + 1))
        self.precursor_start = max(0, config.onset_block - dur)
        self.ramp_theta = 1.0 / max(1.0, dur * 0.5)
        # OU ramp state s in [0, 1]; s=1 means full attenuation reached
        self._s = min(1.0, config.ramp_jump_start)
        self._attenuation_per_unit = config.lo_attack_attenuation

    def step(self, state, block_index: int) -> None:
        if block_index < self.precursor_start:
            return
        # advance OU ramp (absorbed at 1)
        if block_index < self.onset_block:
            self._s = min(1.0, max(0.0, _ou_step(self._s, self.ramp_theta, self.config.ramp_ou_sigma, self.rng)))
        else:
            self._s = 1.0
        # LO power multiplier drifts during precursor window (telemetry-visible)
        lo_factor = 1.0 - self._attenuation_per_unit * self._s
        state.detector.lo_power = lo_factor
        # epsilon-bias mechanism: operational from onset only (hidden excess noise)
        if block_index >= self.onset_block:
            state.lo_hidden_noise_factor = self.config.lo_hidden_noise_factor
