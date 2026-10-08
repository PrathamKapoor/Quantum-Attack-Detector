"""Seeded RNG streams (master prompt §18/§21).

Benign randomness and attack randomness use separate, independently seeded streams
derived from (seed, stream_name). Matched-counterfactual pairs preserve the benign
trajectory bit-exactly: Run A (no attack) simply skips attack stepping, so the
environment stream output is identical between arms.
"""
from __future__ import annotations

import numpy as np


def make_rng(seed: int, stream: str) -> np.random.Generator:
    """Deterministic Generator per (seed, stream) — stable across runs/platforms."""
    key = f"{seed}:{stream}".encode("utf-8")
    digest = int.from_bytes(__import__("hashlib").sha256(key).digest()[:8], "big")
    return np.random.default_rng(digest)
