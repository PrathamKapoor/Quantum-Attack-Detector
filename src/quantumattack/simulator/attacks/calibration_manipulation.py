"""Detector calibration manipulation attack (P0, class A — gradual, PROJECT INFERENCE).

Physical mechanism (docs/attack-taxonomy.md #3): adversary with electronics access
slowly biases detector gain/offset (stochastic OU ramps, independent durations).
Measured quadrature statistics are distorted so estimated parameters look BETTER
than reality; key generated with over-estimated security.

Deliberately confusable with benign calibration drift — that is the scientific point.
Precursor: class A ramps in [precursor_start, onset). LABEL: PROJECT INFERENCE.
"""
from __future__ import annotations

from .base import AttackModule
from ..config import AttackConfig


def _ou_step(x: float, theta: float, sigma: float, rng) -> float:
    return x - theta * x + sigma * rng.normal(0.0, 1.0)


class CalibrationManipulationAttack(AttackModule):
    attack_type = "calibration_manipulation"
    precursor_class = "A"

    def __init__(self, config: AttackConfig, seed: int):
        super().__init__(config, seed)
        # independent ramp durations for gain and offset (staggered precursor)
        g_dur = int(self.rng.integers(config.cal_ramp_min_blocks, config.cal_ramp_max_blocks + 1))
        o_dur = int(self.rng.integers(config.cal_ramp_min_blocks, config.cal_ramp_max_blocks + 1))
        self.precursor_start = max(0, config.onset_block - max(g_dur, o_dur))
        self._g_theta = 1.0 / max(1.0, g_dur * 0.5)
        self._o_theta = 1.0 / max(1.0, o_dur * 0.5)
        self._g_s = 0.0
        self._o_s = 0.0
        self._o_dir = 1.0 if self.rng.random() < 0.5 else -1.0

    def step(self, state, block_index: int) -> None:
        if block_index < self.precursor_start:
            return
        if block_index < self.onset_block:
            self._g_s = min(1.0, max(0.0, _ou_step(self._g_s, self._g_theta, self.config.ramp_ou_sigma, self.rng)))
            self._o_s = min(1.0, max(0.0, _ou_step(self._o_s, self._o_theta, self.config.ramp_ou_sigma, self.rng)))
        else:
            self._g_s = 1.0
            self._o_s = 1.0
        # gain/offset telemetry drifts during precursor window
        state.detector.det_gain = 1.0 + self.config.cal_gain_bias * self._g_s
        state.detector.det_gain_plus = 1.0 + self.config.cal_gain_bias * self._g_s
        state.detector.det_gain_minus = 1.0 + self.config.cal_gain_bias * self._g_s * 0.9
        state.detector.det_offset_snu += (
            0.0 if block_index == 0 else 0.0
        )
        state.detector.det_offset_target = (
            self.config.cal_offset_bias_snu * self._o_s * self._o_dir
        )
        # epsilon-bias mechanism: operational from onset only
        if block_index >= self.onset_block:
            state.lo_hidden_noise_factor = 0.3  # mild false-security bias
