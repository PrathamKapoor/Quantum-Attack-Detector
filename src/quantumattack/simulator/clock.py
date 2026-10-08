"""Seeded simulation clock (master prompt §14: define time before prediction).

1 block = BLOCK_MS milliseconds = 1e6 symbols @100 MBaud (source 8 anchor).
Timestamps are monotonic by construction.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import BLOCK_MS


@dataclass
class Clock:
    """Block-indexed simulation clock."""

    n_blocks: int
    block_index: int = 0

    @property
    def t_ms(self) -> float:
        """Physical start time of the current block, in ms."""
        return self.block_index * BLOCK_MS

    @property
    def done(self) -> bool:
        return self.block_index >= self.n_blocks

    def step(self) -> None:
        if self.done:
            raise RuntimeError("clock exhausted")
        self.block_index += 1
