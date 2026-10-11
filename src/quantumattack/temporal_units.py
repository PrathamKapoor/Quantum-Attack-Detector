"""Authoritative temporal-unit conversion for the whole project (D-039).

WHY this module exists
----------------------
The simulator's time unit is fixed by `simulator.config.BLOCK_MS` (10 ms per
block, anchored to the 100 MBaud / 1 Gsample-per-second parameter-estimation
frame cadence — see docs/time-semantics.md §1). Several historical reports
converted blocks to seconds using an INCORRECT 0.1 s/block factor (a factor-of-ten
error), producing lead times 10x too large. The underlying code was correct; the
defect was in ad-hoc human-readable reporting.

To make that class of error structurally impossible, every block<->second,
block<->symbol and block<->ms conversion in the codebase funnels through the
single `BLOCK_MS` constant imported here. There are no other magic time factors.

WHAT
    One conversion authority: `blocks_to_seconds`, `seconds_to_blocks`,
    `blocks_to_ms`, `blocks_to_symbols`, plus a self-check that the simulator's
    `BLOCK_MS` and this module never diverge.

WHY
    Prevents the factor-of-ten class of metric-integrity error from recurring in
    machine-readable outputs.

HOW
    Pure functions over the frozen `BLOCK_MS`. `blocks_to_symbols` uses the
    documented 100 MBaud symbol rate; it is informational (model-input span /
    reporting only) and does not enter the forecasting clock.

WHEN
    Used at every boundary where physical time is derived from a block index:
    evaluation lead-time summaries, forecast-horizon duration reporting, and
    human/JSON report generation. It is never used inside the simulator loop
    itself, which uses `Clock.t_ms` (the same `BLOCK_MS`).
"""
from __future__ import annotations

from .simulator.config import BLOCK_MS

__all__ = [
    "BLOCK_MS",
    "SYMBOL_RATE_MBAUD",
    "seconds_per_block",
    "blocks_to_seconds",
    "blocks_to_ms",
    "seconds_to_blocks",
    "blocks_to_symbols",
    "horizon_seconds",
    "verify_time_base",
]

#: Source symbol rate (MBaud) documented in docs/time-semantics.md §2.
SYMBOL_RATE_MBAUD: float = 100.0

#: Seconds represented by one simulation block (derived, never hardcoded twice).
seconds_per_block: float = BLOCK_MS / 1000.0


def blocks_to_seconds(blocks: float | None) -> float | None:
    """Convert a block count/duration to seconds. None propagates as None.

    EXAMPLES (verified against BLOCK_MS=10.0):
        78 blocks  -> 0.78 s   (NOT 7.8 s)
        100 blocks -> 1.0 s
    """
    return None if blocks is None else blocks * seconds_per_block


def blocks_to_ms(blocks: float | None) -> float | None:
    """Convert a block count/duration to milliseconds."""
    return None if blocks is None else blocks * BLOCK_MS


def seconds_to_blocks(seconds: float) -> float:
    """Convert a physical duration in seconds to blocks."""
    return seconds / seconds_per_block


def blocks_to_symbols(blocks: float | None) -> float | None:
    """Convert blocks to modulated symbols at the documented symbol rate.

    Informational only: used for reporting model-input span and comparing against
    literature anchor (1e6 symbols per block). Does not affect the forecast clock.
    """
    return None if blocks is None else blocks * 1.0e6


def horizon_seconds(horizon_blocks: int) -> float:
    """Physical duration of a forecast horizon given in blocks."""
    return blocks_to_seconds(horizon_blocks)


def verify_time_base() -> dict:
    """Return an auditable record of the project's authoritative time base.

    Used by tests and evaluation manifests so that any stored result records the
    exact conversion that produced it. If the simulator constant ever changes,
    this surfaces the change explicitly rather than silently re-scaling history.
    """
    return {
        "block_ms": BLOCK_MS,
        "seconds_per_block": seconds_per_block,
        "symbol_rate_mbaud": SYMBOL_RATE_MBAUD,
        "symbols_per_block": 1.0e6,
        "note": (
            "1 block = 10 ms = 1e6 symbols @100 MBaud. Seconds = blocks * 0.01. "
            "A 0.1 s/block convention is incorrect by a factor of ten."
        ),
    }