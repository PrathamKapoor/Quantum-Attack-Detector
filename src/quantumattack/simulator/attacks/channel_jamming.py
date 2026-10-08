"""Channel jamming / saturation attack (P0, class B probes optional then C sudden).

Physical mechanism (docs/attack-taxonomy.md #4): Eve injects bright light into the
channel (availability attack). Optionally preceded by LOW-power reconnaissance
probes (class B, PROJECT INFERENCE) — weak background blips in
[precursor_start, onset). Full jamming is sudden (class C) at onset.
"""
from __future__ import annotations

from .base import AttackModule
from ..config import AttackConfig


class ChannelJammingAttack(AttackModule):
    attack_type = "channel_jamming"
    precursor_class = "B" if True else "C"  # class depends on probe_enabled; set in __init__

    def __init__(self, config: AttackConfig, seed: int):
        super().__init__(config, seed)
        if config.probe_enabled:
            self.precursor_class = "B"
            self.precursor_start = max(0, config.onset_block - config.precursor_lead_blocks)
            # Poisson burst schedule over the precursor window
            n_bursts = self.rng.poisson(config.probe_lambda)
            window = max(1, config.onset_block - self.precursor_start)
            self._bursts: dict[int, float] = {}
            for _ in range(n_bursts):
                start = self.precursor_start + int(self.rng.integers(0, window))
                power = config.jamming_power_snu * config.probe_mu_frac * abs(
                    self.rng.normal(1.0, 0.3)
                )
                for b in range(start, min(start + config.probe_duration_blocks, config.onset_block)):
                    self._bursts[b] = max(self._bursts.get(b, 0.0), power)
        else:
            self.precursor_class = "C"
            self.precursor_start = config.onset_block
            self._bursts = {}
        self._jamming_started = False

    def step(self, state, block_index: int) -> None:
        if block_index < self.onset_block:
            # weak probe blips (telemetry events only; never labeled ATTACK)
            probe_power = self._bursts.get(block_index, 0.0)
            if probe_power > 0:
                state.channel.jamming_power_snu = probe_power
            return
        if not self._jamming_started:
            self._jamming_started = True
            # sudden step: full-power jamming from onset to end
            state.channel.jamming_power_snu = self.config.jamming_power_snu
            state.channel.attack_excess_noise = state.channel.excess_noise_snu * 0.5
