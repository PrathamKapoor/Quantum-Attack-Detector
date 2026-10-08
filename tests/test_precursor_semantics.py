"""Precursor semantics tests (master prompt §11/§32/§48).

- precursor absent when disabled / for class C
- precursor occurs only in configured interval
- sudden-onset attack has no injected precursor
- mixture check: not every attack shares one precursor shape
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantumattack.simulator.config import ScenarioConfig, AttackConfig  # noqa: E402
from quantumattack.simulator.scenario import run_scenario  # noqa: E402
from quantumattack.simulator.export.parquet import scenario_to_dataframe  # noqa: E402

N = 400
ONSET = 250


def _res(atype: str, seed: int = 31, **kw):
    cfg = ScenarioConfig(
        scenario_id=f"prec-{atype}-{seed}", seed=seed, n_blocks=N,
        attack=AttackConfig(attack_type=atype, onset_block=ONSET, **kw),
    )
    return run_scenario(cfg)


def test_class_c_has_empty_precursor_interval():
    res = _res("intercept_resend")
    assert res.metadata["precursor_start"] == res.metadata["attack_onset"]
    assert res.metadata["precursor_class"] == "C"
    df = scenario_to_dataframe(res)
    assert sum(df["state_label"] == "PRECURSOR") == 0


def test_sudden_jamming_no_injected_precursor():
    res = _res("channel_jamming", probe_enabled=False)
    assert res.metadata["precursor_start"] == res.metadata["attack_onset"]
    assert res.metadata["precursor_class"] == "C"


def test_class_a_precursor_only_in_configured_interval():
    res = _res("lo_manipulation", lo_attack_attenuation=0.6, ramp_min_blocks=80, ramp_max_blocks=120)
    onset = res.metadata["attack_onset"]
    ps = res.metadata["precursor_start"]
    assert 0 <= ps < onset
    df = scenario_to_dataframe(res)
    prec_labels = df[df["state_label"] == "PRECURSOR"]["block_index"]
    assert prec_labels.min() >= ps
    assert prec_labels.max() < onset
    # attack labels strictly from onset
    atk_labels = df[df["state_label"] == "ATTACK"]["block_index"]
    assert atk_labels.min() >= onset


def test_class_a_ramp_is_stochastic_not_linear():
    res = _res("lo_manipulation", lo_attack_attenuation=0.6, ramp_min_blocks=80, ramp_max_blocks=120)
    df = scenario_to_dataframe(res)
    ps, onset = res.metadata["precursor_start"], res.metadata["attack_onset"]
    ramp = df[(df.block_index >= ps) & (df.block_index < onset)]["lo_power"].values
    assert len(ramp) > 10
    diffs = np.diff(ramp)
    # not a deterministic linear ramp: differences vary magnitude (OU stochastic)
    assert not np.allclose(diffs, diffs[0])
    # ramp trends downward toward the attack operating point (mean below baseline 1.0)
    # OU noise makes it non-monotone per block by design (docs/precursor-taxonomy.md);
    # benign thermal coupling adds ±0.01 wander, so the mean stays clearly below 1
    assert ramp.mean() < 0.95


def test_class_b_probes_weak_and_inside_window():
    res = _res("channel_jamming", probe_enabled=True, probe_lambda=3.0, precursor_lead_blocks=100)
    onset, ps = res.metadata["attack_onset"], res.metadata["precursor_start"]
    assert ps < onset
    df = scenario_to_dataframe(res)
    ramp = df[(df.block_index >= ps) & (df.block_index < onset)]["background"].values
    post = df[df.block_index >= onset]["background"].values
    # probe blips are WEAK: well below full jamming level
    assert ramp.max() < post.mean()
    # but above the benign baseline (blips exist)
    assert ramp.max() > np.median(df[df.block_index < ps]["background"].values)


def test_mixture_check_not_all_attacks_gradual():
    """Across a batch, at least two distinct precursor classes must be present
    (master prompt §11: prevent every attack sharing one precursor structure)."""
    classes = set()
    for atype, kw in (
        ("intercept_resend", {}),
        ("lo_manipulation", dict(ramp_min_blocks=50, ramp_max_blocks=80)),
        ("calibration_manipulation", dict(cal_ramp_min_blocks=50, cal_ramp_max_blocks=90)),
        ("channel_jamming", dict(probe_enabled=False)),
    ):
        res = _res(atype, seed=41, **kw)
        classes.add(res.metadata["precursor_class"])
    assert len(classes) >= 2, f"all attacks share one precursor class: {classes}"
    assert "C" in classes  # sudden-onset members exist


def test_precursor_labels_absent_for_benign_scenarios():
    cfg = ScenarioConfig(scenario_id="benign", seed=31, n_blocks=200)
    res = run_scenario(cfg)
    labels = res.labels["state_label"]
    assert labels.count("PRECURSOR") == 0
    assert labels.count("ATTACK") == 0
