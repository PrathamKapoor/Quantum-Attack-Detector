"""Attack module interface (docs/attack-taxonomy.md).

Each attack modifies ONLY the subsystem state its physical mechanism justifies.
Onset semantics: `attack_onset` = first block where the malicious mechanism modifies
system state per the attack's definition — never "first abnormal telemetry".
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import AttackConfig

class AttackModule(ABC):
    """Base interface for attack injection modules.

    Lifecycle (master prompt §31):
      1. prepare(config, seed) — draw attack-only randomness from (seed, "attack")
      2. step(state_view, block_index) — called EVERY block; modifies state only
         from onset_block onward (or per precursor spec inside the precursor window)
    """

    attack_type: str = "none"
    precursor_class: str = "C"  # A | B | C | none

    def __init__(self, config: AttackConfig, seed: int):
        from ..rng import make_rng

        self.config = config
        self.rng = make_rng(seed, "attack")
        self.onset_block: int = config.onset_block
        self.precursor_start: int = config.onset_block  # class C default: empty window

    @abstractmethod
    def step(self, state, block_index: int) -> None:
        """Apply the attack mechanism to system state for this block.

        `state` is a namespace exposing: channel (ChannelState), detector
        (DetectorState), environment (EnvironmentState), protocol (ProtocolConfig).
        Must NOT touch benign stream state or labels.
        """

    @property
    def is_active(self) -> bool:
        return self.config.attack_type != "none"
