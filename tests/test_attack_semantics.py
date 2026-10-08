"""Attack semantics tests (master prompt §48).

- attack inactive before onset (state and telemetry unchanged)
- attack active according to scenario after onset
- onset = mechanism activation, not first abnormal telemetry
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantumattack.simulator.config import ScenarioConfig, AttackConfig  # noqa: E402
from quantumattack.simulator.scenario import run_scenario  # noqa: E402
from quantumattack.simulator.export.parquet import scenario_to_dataframe  # noqa: E402

N = 300
ONSET = 150


def _df(atype: str, **kw):
    cfg = ScenarioConfig(
        scenario_id=f"atk-{atype}", seed=21, n_blocks=N,
        attack=AttackConfig(attack_type=atype, onset_block=ONSET, **kw),
    )
    res = run_scenario(cfg)
    return res, scenario_to_dataframe(res)


def test_intercept_resend_step_at_onset():
    res, df = _df("intercept_resend", tap_fraction=0.3, resend_noise_mult=2.0)
    pre = df[df.block_index < ONSET]
    post = df[df.block_index >= ONSET]
    # attack inactive before onset: true_T at baseline
    assert pre["true_T"].min() > 0.15
    # active after: transmittance drops by ~tap fraction
    assert post["true_T"].max() < pre["true_T"].mean() * 0.75
    # excess noise increases after onset. Benign thermal wander moves the base itself,
    # so compare against the matched benign run at the SAME blocks (counterfactual, §18):
    # added step ≈ (resend_noise_mult − 1) × base × jitter ≈ 1.0 × base ≈ 0.01 SNU.
    import numpy as np

    benign = run_scenario(ScenarioConfig(
        scenario_id="ir-benign-match", seed=21, n_blocks=N))
    atk_xi = np.array([r["true_xi"] for r in res.records])
    ben_xi = np.array([r["true_xi"] for r in benign.records])
    added_vs_matched = float((atk_xi[ONSET:] - ben_xi[ONSET:]).mean())
    assert added_vs_matched > 0.005, f"IR added noise vs matched benign too small: {added_vs_matched}"
    # onset semantics: metadata block, not first abnormal telemetry
    assert res.metadata["attack_onset"] == ONSET
    assert res.metadata["precursor_start"] == ONSET  # class C: no precursor interval
    assert res.metadata["precursor_class"] == "C"


def test_lo_manipulation_gradual_ramp():
    res, df = _df("lo_manipulation", lo_attack_attenuation=0.5, ramp_min_blocks=60, ramp_max_blocks=100)
    onset = res.metadata["attack_onset"]
    ps = res.metadata["precursor_start"]
    assert ps < onset  # class A: precursor interval exists
    pre = df[df.block_index < ps]
    ramp = df[(df.block_index >= ps) & (df.block_index < onset)]
    post = df[df.block_index >= onset]
    # LO power drifts during precursor window (telemetry-visible before onset)
    assert ramp["lo_power"].mean() < pre["lo_power"].mean()
    # ramp is stochastic (not linear): per-block differences vary
    diffs = np.diff(ramp["lo_power"].values)
    assert diffs.std() > 0
    # epsilon-bias active from onset: SKR estimate inflated (false security)
    assert post["skr_estimate"].mean() > pre["skr_estimate"].mean()
    assert res.metadata["precursor_class"] == "A"


def test_calibration_manipulation_gradual_ramp():
    res, df = _df("calibration_manipulation", cal_gain_bias=0.2, cal_ramp_min_blocks=60, cal_ramp_max_blocks=120)
    onset = res.metadata["attack_onset"]
    ps = res.metadata["precursor_start"]
    assert ps < onset
    pre = df[df.block_index < ps]
    ramp = df[(df.block_index >= ps) & (df.block_index < onset)]
    # detector gain drifts during precursor
    assert ramp["det_gain"].mean() > pre["det_gain"].mean()
    assert res.metadata["precursor_class"] == "A"


def test_jamming_sudden_and_probe_variants():
    # sudden variant: no precursor
    cfg = ScenarioConfig(
        scenario_id="jam-sudden", seed=21, n_blocks=N,
        attack=AttackConfig(attack_type="channel_jamming", onset_block=ONSET, probe_enabled=False),
    )
    res = run_scenario(cfg)
    assert res.metadata["precursor_start"] == ONSET
    assert res.metadata["precursor_class"] == "C"
    df = scenario_to_dataframe(res)
    pre = df[df.block_index < ONSET]
    post = df[df.block_index >= ONSET]
    assert post["background"].mean() > pre["background"].mean() * 10

    # probe variant: weak blips strictly inside precursor window
    cfg = ScenarioConfig(
        scenario_id="jam-probe", seed=21, n_blocks=N,
        attack=AttackConfig(
            attack_type="channel_jamming", onset_block=ONSET,
            probe_enabled=True, probe_lambda=5.0, precursor_lead_blocks=100,
        ),
    )
    res = run_scenario(cfg)
    assert res.metadata["precursor_start"] < ONSET
    assert res.metadata["precursor_class"] == "B"
    df = scenario_to_dataframe(res)
    ps = res.metadata["precursor_start"]
    pre = df[df.block_index < ps]
    ramp = df[(df.block_index >= ps) & (df.block_index < ONSET)]
    # probes raise background above baseline during precursor window
    assert ramp["background"].max() > pre["background"].mean()


def test_attack_state_labels():
    res, df = _df("intercept_resend")
    labels = df["state_label"].tolist()
    # NORMAL before onset, ATTACK from onset
    assert all(l == "NORMAL" for l in labels[:ONSET])
    assert all(l == "ATTACK" for l in labels[ONSET:])
    assert sum(df["current_attack"]) == N - ONSET


def test_y50_matches_horizon_definition():
    res, df = _df("intercept_resend")
    y50 = res.labels["future_attack_h50"]
    # y_H(t)=1 iff t < onset <= t+H → blocks [onset-50, onset-1]
    expected = [1 if ONSET - 50 <= t < ONSET else 0 for t in range(N)]
    assert y50 == expected
    # current_attack and future labels differ (no attack yet vs pre-onset window)
    assert sum(res.labels["current_attack"][:ONSET - 50]) == 0


def test_no_attack_scenario():
    cfg = ScenarioConfig(scenario_id="none", seed=21, n_blocks=200)
    res = run_scenario(cfg)
    assert res.metadata["attack_onset"] == -1
    assert res.metadata["precursor_start"] == -1
    assert res.metadata["scenario_class"] == "NORMAL"
    assert sum(res.labels["current_attack"]) == 0
    assert all(sum(res.labels[f"future_attack_h{h}"]) == 0 for h in (10, 25, 50, 100))
