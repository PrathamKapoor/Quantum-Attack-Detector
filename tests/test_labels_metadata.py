"""Label + metadata-isolation tests (master prompt §34/§48).

- future label matches horizon definition
- current attack label differs from future attack label
- no label uses future features (SKR causality)
- attack metadata excluded from feature columns
- counterfactual: matched pair shares intended baseline conditions
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantumattack.simulator.config import ScenarioConfig, AttackConfig  # noqa: E402
from quantumattack.simulator.scenario import run_scenario  # noqa: E402
from quantumattack.simulator.export.parquet import scenario_to_dataframe  # noqa: E402
from quantumattack.dataset import (  # noqa: E402
    METADATA_COLUMNS, LABEL_COLUMNS, EVAL_ONLY_COLUMNS, RESTRICTED_COLUMNS,
    FEATURE_COLUMNS, NEVER_MODEL_INPUTS, validate_column_classes,
)

N = 300
ONSET = 150


def test_metadata_isolation_invariant():
    """FEATURE_COLUMNS ∩ RESTRICTED_COLUMNS = ∅ (machine-checked, master prompt §34)."""
    validate_column_classes()  # raises on violation
    assert FEATURE_COLUMNS.isdisjoint(METADATA_COLUMNS)
    assert FEATURE_COLUMNS.isdisjoint(LABEL_COLUMNS)
    assert FEATURE_COLUMNS.isdisjoint(EVAL_ONLY_COLUMNS)


def test_restricted_columns_never_model_inputs():
    """Every explicitly-forbidden column is in RESTRICTED_COLUMNS."""
    for col in NEVER_MODEL_INPUTS:
        assert col in RESTRICTED_COLUMNS, f"{col} not restricted"
    for col in ("attack_type", "attack_onset", "precursor_start", "state_label",
                "scenario_class", "pair_id"):
        assert col not in FEATURE_COLUMNS
    # ground-truth state columns excluded too
    for col in ("true_T", "true_xi", "true_lo_power", "true_background"):
        assert col not in FEATURE_COLUMNS


def test_future_label_matches_horizon_definition():
    cfg = ScenarioConfig(
        scenario_id="lbl", seed=51, n_blocks=N,
        attack=AttackConfig(attack_type="intercept_resend", onset_block=ONSET),
    )
    res = run_scenario(cfg)
    for h in (10, 25, 50, 100):
        y = res.labels[f"future_attack_h{h}"]
        expected = [1 if t < ONSET <= t + h else 0 for t in range(N)]
        assert y == expected, f"y_H definition violated for H={h}"


def test_current_vs_future_labels_differ():
    cfg = ScenarioConfig(
        scenario_id="lbl2", seed=51, n_blocks=N,
        attack=AttackConfig(attack_type="intercept_resend", onset_block=ONSET),
    )
    res = run_scenario(cfg)
    cur = res.labels["current_attack"]
    y50 = res.labels["future_attack_h50"]
    # in the pre-onset warning band [onset-50, onset), current=0 but y50=1
    band = range(ONSET - 50, ONSET)
    assert all(cur[t] == 0 for t in band)
    assert all(y50[t] == 1 for t in band)
    # after onset: current=1 but y50=0 (attack already began)
    assert all(cur[t] == 1 for t in range(ONSET, N))
    assert all(y50[t] == 0 for t in range(ONSET, N))


def test_skr_uses_only_current_state():
    """SKR causality (leakage risk #1): SKR(t) is a function of state at t only.

    Proof: rerunning the scenario with a DIFFERENT attack onset that is later
    must produce identical SKR values up to the first onset (state identical,
    future differs)."""
    atk_early = AttackConfig(attack_type="intercept_resend", onset_block=ONSET)
    atk_late = AttackConfig(attack_type="intercept_resend", onset_block=N - 1)
    res_a = run_scenario(ScenarioConfig(
        scenario_id="skr-a", seed=61, n_blocks=N, attack=atk_early))
    res_b = run_scenario(ScenarioConfig(
        scenario_id="skr-b", seed=61, n_blocks=N, attack=atk_late))
    skr_a = [r["skr_estimate"] for r in res_a.records[:ONSET]]
    skr_b = [r["skr_estimate"] for r in res_b.records[:ONSET]]
    assert skr_a == skr_b, "SKR before onset depends on future attack state (leakage!)"


def test_no_label_uses_future_features():
    """Labels derived from onset metadata, not telemetry (leakage risk #4/§5).

    For a class-C attack, PRECURSOR labels must be absent even though telemetry
    (sampling noise) fluctuates before onset."""
    cfg = ScenarioConfig(
        scenario_id="lbl3", seed=51, n_blocks=N,
        attack=AttackConfig(attack_type="intercept_resend", onset_block=ONSET),
    )
    res = run_scenario(cfg)
    labels = res.labels["state_label"]
    assert "PRECURSOR" not in set(labels)


def test_drift_episode_labels_are_ground_truth():
    """BENIGN_DRIFT labels come from the named simulation event, not telemetry
    inference (leakage risk #9)."""
    from quantumattack.simulator.config import EnvironmentConfig

    cfg = ScenarioConfig(
        scenario_id="lbl4", seed=52, n_blocks=200,
        environment=EnvironmentConfig(disturbance_episode_prob=1.0,
                                      disturbance_duration_blocks=30),
    )
    res = run_scenario(cfg)
    labels = res.labels["state_label"]
    assert sum(1 for l in labels if l == "BENIGN_DRIFT") == 30
    # episodes never labeled as attack/precursor
    assert "ATTACK" not in set(labels)
    assert "PRECURSOR" not in set(labels)


def test_drift_episode_window_matches_actual_event():
    """Regression (Phase 4 label-window bug): BENIGN_DRIFT labels must land on the
    ACTUAL episode block window (where the episode elevated the telemetry), not a
    tail-anchored approximation. With prob=1.0 the episode fires at block 1; the
    labeled window must be the episode's recorded start/end blocks."""
    from quantumattack.simulator.config import EnvironmentConfig

    cfg = ScenarioConfig(
        scenario_id="lbl4b", seed=52, n_blocks=200,
        environment=EnvironmentConfig(disturbance_episode_prob=1.0,
                                      disturbance_duration_blocks=30),
    )
    res = run_scenario(cfg)
    labels = res.labels["state_label"]
    drift_rows = [i for i, l in enumerate(labels) if l == "BENIGN_DRIFT"]
    # with prob=1.0 the episode fires on the first block (draw < 1.0 always true)
    assert drift_rows[0] == 1, f"episode window start wrong: {drift_rows[0]}"
    assert len(drift_rows) == 30
    # end of window == start + duration - 1 (contiguous event)
    assert drift_rows[-1] == drift_rows[0] + 29
    # the label window must NOT be the run tail (the old bug put it at 170..199)
    assert drift_rows[-1] != 199


def test_counterfactual_pair_shares_baseline():
    """Matched pair (master prompt §18): same seed/initial conditions/benign
    trajectory; ONLY the attack differs. Benign randomness streams are
    bit-identical between arms."""
    pair_id = "pair-test-001"
    cfg_normal = ScenarioConfig(
        scenario_id="cf-normal", seed=71, n_blocks=N,
        pair_id=pair_id, arm="normal",
    )
    cfg_attack = ScenarioConfig(
        scenario_id="cf-attack", seed=71, n_blocks=N,
        attack=AttackConfig(attack_type="lo_manipulation", onset_block=200),
        pair_id=pair_id, arm="attack",
    )
    res_a = run_scenario(cfg_normal)
    res_b = run_scenario(cfg_attack)
    # environmental trajectory identical: temperature, clock offset (env stream)
    temp_a = [r["temperature"] for r in res_a.records]
    temp_b = [r["temperature"] for r in res_b.records]
    assert temp_a == temp_b, "matched pair differs in benign environment trajectory"
    clk_a = [r["clock_offset_ns"] for r in res_a.records[:100]]
    clk_b = [r["clock_offset_ns"] for r in res_b.records[:100]]
    assert clk_a == clk_b
    # metadata: same seed, same pair_id, different arm
    assert res_a.metadata["seed"] == res_b.metadata["seed"] == 71
    assert res_a.metadata["pair_id"] == res_b.metadata["pair_id"] == pair_id
    assert res_a.metadata["arm"] == "normal"
    assert res_b.metadata["arm"] == "attack"
    # only the attack differs: attack scenario has onset metadata, normal has none
    assert res_a.metadata["attack_onset"] == -1
    assert res_b.metadata["attack_onset"] == 200


def test_exported_columns_classified():
    """Exported DataFrame carries metadata/labels/eval-only/features columns
    classified per docs/dataset-spec.md §2."""
    cfg = ScenarioConfig(
        scenario_id="exp", seed=81, n_blocks=200,
        attack=AttackConfig(attack_type="intercept_resend", onset_block=25),
    )
    res = run_scenario(cfg)
    df = scenario_to_dataframe(res)
    for col in RESTRICTED_COLUMNS:
        assert col in df.columns, f"restricted column {col} missing from export"
    for col in FEATURE_COLUMNS:
        assert col in df.columns, f"feature column {col} missing from export"
