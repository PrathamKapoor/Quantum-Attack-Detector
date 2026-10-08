"""Reproducibility + physics/data invariants (master prompt §48).

- same seed → identical telemetry (deterministic reproduction)
- probabilities in [0,1], counts/vars nonnegative, timestamps monotonic
- QBER proxy in valid bounds
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantumattack.simulator.config import ScenarioConfig, AttackConfig  # noqa: E402
from quantumattack.simulator.scenario import run_scenario  # noqa: E402

N = 300


def _run(seed: int, attack: AttackConfig | None = None):
    cfg = ScenarioConfig(
        scenario_id=f"repro-{seed}", seed=seed, n_blocks=N,
        attack=attack or AttackConfig(attack_type="none"),
    )
    return run_scenario(cfg)


def test_same_seed_same_output():
    a = _run(123)
    b = _run(123)
    assert a.n_blocks == b.n_blocks
    for ra, rb in zip(a.records, b.records):
        for k in ra:
            va, vb = ra[k], rb[k]
            if isinstance(va, float):
                assert va == vb, f"field {k} differs: {va} != {vb}"
            else:
                assert va == vb, f"field {k} differs: {va!r} != {vb!r}"
    assert a.metadata["config_hash"] == b.metadata["config_hash"]


def test_different_seed_different_output():
    a = _run(1)
    b = _run(2)
    lo_a = [r["lo_power"] for r in a.records]
    lo_b = [r["lo_power"] for r in b.records]
    assert lo_a != lo_b


def test_reproducible_with_attack():
    atk = AttackConfig(attack_type="lo_manipulation", onset_block=150)
    a = _run(9, atk)
    b = _run(9, atk)
    assert [r["lo_power"] for r in a.records] == [r["lo_power"] for r in b.records]
    assert a.labels == b.labels


def test_probability_ranges():
    res = _run(3)
    for r in res.records:
        assert 0.0 <= r["saturation_frac"] <= 1.0
        assert 0.0 <= r["qber_proxy"] <= 1.0
        assert -0.5 <= r["det_imbalance"] <= 0.5  # signed imbalance (±)
        assert 0.0 < r["det_efficiency"] <= 1.0


def test_nonnegative_quantities():
    res = _run(4)
    for r in res.records:
        for k in ("transmittance", "excess_noise", "background", "skr_estimate",
                  "x_var", "p_var", "lo_power", "lo_variance", "fiber_loss_db",
                  "temperature", "det_temperature", "calibration_state"):
            assert r[k] >= 0.0, f"{k} negative: {r[k]}"


def test_monotonic_timestamps():
    res = _run(5)
    ts = [r["timestamp_ms"] for r in res.records]
    assert ts == sorted(ts)
    blocks = [r["block_index"] for r in res.records]
    assert blocks == list(range(N))


def test_qber_proxy_bounds_under_all_attacks():
    for atype in ("intercept_resend", "lo_manipulation", "calibration_manipulation",
                  "channel_jamming"):
        atk = AttackConfig(attack_type=atype, onset_block=100)
        res = _run(6, atk)
        for r in res.records:
            assert 0.0 <= r["qber_proxy"] <= 1.0


def test_labels_arrays_lengths():
    res = _run(7)
    assert all(len(v) == N for v in res.labels.values())
