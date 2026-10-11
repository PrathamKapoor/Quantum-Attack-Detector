"""Conventional sequential (CUSUM) detector tests (decisions.md D-052).

Exercises the real detector implementation on controlled synthetic telemetry and
one complete simulator-generated scenario. Tests assert behaviour, not the
existence of configuration options.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantumattack.baselines.conventional import (  # noqa: E402
    CusumConfig, CusumCalibration, fit_cusum_reference, cusum_statistic,
    detect_warnings_cusum, calibrate_cusum_threshold, INDICATORS,
)

REPO = Path(__file__).resolve().parents[1]


def _ref():
    """Reference stats for synthetic frames with unit spread per indicator."""
    return {ind: {"mean": 0.0, "std": 1.0, "direction": 1, "n": 1000}
            for ind in ("excess_noise", "det_gain", "background")}


def _cal(h=200.0):
    return CusumCalibration(_ref(), h_threshold=h, target_scenario_fpr=0.1,
                            achieved_scenario_fpr=None,
                            calibration_population="test", config={})


def _frame(values, ind="excess_noise", extra_nan_idx=(), columns=None):
    n = len(values)
    cols = columns or ("excess_noise", "det_gain", "background")
    data = {}
    for c in cols:
        data[c] = np.full(n, 0.0) if c != ind else np.asarray(values, dtype=float)
    data["block_index"] = np.arange(n)
    df = pd.DataFrame(data)
    for i in extra_nan_idx:
        df.loc[i, ind] = np.nan
    return df


def test_constant_normal_signal_never_alerts():
    config = CusumConfig(k_drift=2.0, h_threshold=200.0, persistence_k=3,
                         warmup_blocks=20)
    df = _frame(np.zeros(400))
    # make all indicators constant so the per-scenario baseline has unit spread
    df["det_gain"] = 0.01
    df["background"] = 0.02
    det = detect_warnings_cusum(df, _cal(), config)
    assert det["warning_blocks"] == []


def test_persistent_attack_shift_alerts():
    """A sustained +5-sigma step after warmup must alert; warmup itself is unusable."""
    config = CusumConfig(k_drift=2.0, h_threshold=10.0, persistence_k=3,
                         warmup_blocks=50, normalization="per_scenario_warmup")
    rng = np.random.default_rng(0)
    noise = rng.normal(0, 1.0, 400)
    shift = np.concatenate([noise[:200], noise[200:] + 5.0])
    df = _frame(shift)
    df["det_gain"] = noise * 0.01
    df["background"] = noise * 0.01
    det = detect_warnings_cusum(df, _cal(10.0), config)
    assert det["warning_blocks"], "persistent 5-sigma shift must be detected"
    # emission cannot occur in warmup and must respect persistence_k
    assert det["warning_blocks"][0] >= 50 + 3 - 1


def test_short_transient_does_not_accumulate():
    """A brief single-sample spike is bounded by the Huber-type deviate cap and
    cannot cross a large h through persistence."""
    config = CusumConfig(k_drift=2.0, h_threshold=30.0, persistence_k=3,
                         warmup_blocks=50, deviate_cap=10.0)
    rng = np.random.default_rng(1)
    x = rng.normal(0, 1.0, 300)
    x[150] = 50.0     # one huge spike -> capped at +10 -> S contributes 8
    df = _frame(x)
    det = detect_warnings_cusum(df, _cal(30.0), config)
    assert det["warning_blocks"] == []
    # without the cap the same spike would add 48 and cross h=30
    uncapped = CusumConfig(k_drift=2.0, h_threshold=30.0, persistence_k=1,
                           warmup_blocks=50, deviate_cap=1e9)
    det_uncapped = detect_warnings_cusum(df, _cal(30.0), uncapped)
    assert det_uncapped["warning_blocks"], "control: uncapped spike does cross h"


def test_deviate_cap_bounds_single_block_influence():
    config = CusumConfig(k_drift=0.0, h_threshold=1e9, persistence_k=1,
                         warmup_blocks=10, deviate_cap=5.0)
    x = np.zeros(60)
    x[30] = 1000.0
    df = _frame(x)
    s, _ = cusum_statistic(df, _ref(), config)
    # single-block contribution cannot exceed deviate_cap - k_drift = 5
    assert s[30] - s[29] <= 5.0 + 1e-9


def test_warmup_blocks_are_unusable():
    config = CusumConfig(k_drift=2.0, h_threshold=5.0, persistence_k=1,
                         warmup_blocks=100)
    df = _frame(np.full(200, 0.0))
    _s, usable = cusum_statistic(df, _ref(), config)
    assert not usable[:100].any()
    assert usable[100:].all()


def test_missing_telemetry_marks_block_unusable_and_resets_after_long_gap():
    config = CusumConfig(k_drift=2.0, h_threshold=5.0, persistence_k=1,
                         warmup_blocks=10, max_missing_run=3)
    x = np.zeros(100)
    df = _frame(x)
    # inject 10 consecutive NaNs after a strong shift
    x2 = np.zeros(100); x2[20:] = 10.0
    df2 = _frame(x2)
    df2.loc[30:39, "excess_noise"] = np.nan
    s, usable = cusum_statistic(df2, _ref(), config)
    assert not usable[30:40].any()
    # after > max_missing_run the accumulator is reset
    assert s[45] < s[29]


def test_missing_telemetry_disables_alerts():
    config = CusumConfig(k_drift=2.0, h_threshold=5.0, persistence_k=1,
                         warmup_blocks=10, max_missing_run=100)
    x = np.zeros(100); x[20:] = 10.0
    df = _frame(x)
    df.loc[20:, "excess_noise"] = np.nan   # never becomes evaluable
    det = detect_warnings_cusum(df, _cal(5.0), config)
    assert det["warning_blocks"] == []


def test_invalid_values_are_rejected_not_trusted():
    config = CusumConfig(k_drift=2.0, h_threshold=5.0, persistence_k=1,
                         warmup_blocks=10)
    x = np.zeros(100)
    x[50] = np.inf
    df = _frame(x)
    _s, usable = cusum_statistic(df, _ref(), config)
    assert not usable[50]


def test_determinism_same_input_same_output():
    rng = np.random.default_rng(3)
    x = rng.normal(0, 1, 300)
    x[150:] += 4.0
    df = _frame(x)
    config = CusumConfig(k_drift=2.0, h_threshold=10.0, persistence_k=3, warmup_blocks=50)
    a = detect_warnings_cusum(df, _cal(10.0), config)
    b = detect_warnings_cusum(df, _cal(10.0), config)
    assert a["warning_blocks"] == b["warning_blocks"]
    assert np.array_equal(a["statistic"], b["statistic"])


def test_prefix_invariance_future_change_cannot_alter_past_alerts():
    """Adversarial test K: alter the future; alerts in the shared prefix stay."""
    rng = np.random.default_rng(4)
    base = rng.normal(0, 1, 600)
    base[150:] += 6.0
    df_a = _frame(base.copy())
    future = base.copy()
    future[400:] = rng.normal(0, 1, 200)     # different benign-looking future
    df_b = _frame(future)
    config = CusumConfig(k_drift=2.0, h_threshold=15.0, persistence_k=3, warmup_blocks=50)
    a = detect_warnings_cusum(df_a, _cal(15.0), config)
    b = detect_warnings_cusum(df_b, _cal(15.0), config)
    a_prefix = [w for w in a["warning_blocks"] if w < 400]
    b_prefix = [w for w in b["warning_blocks"] if w < 400]
    assert a_prefix == b_prefix


def test_distinct_scenarios_have_independent_state():
    """One scenario's detector state must not leak into another."""
    rng = np.random.default_rng(5)
    hot = np.concatenate([rng.normal(0, 1, 100), rng.normal(6, 1, 300)])
    cold = rng.normal(0, 1, 400)
    config = CusumConfig(k_drift=2.0, h_threshold=15.0, persistence_k=3, warmup_blocks=50)
    hot_first = detect_warnings_cusum(_frame(hot), _cal(15.0), config)["warning_blocks"]
    cold_after = detect_warnings_cusum(_frame(cold), _cal(15.0), config)["warning_blocks"]
    cold_alone = detect_warnings_cusum(_frame(cold.copy()), _cal(15.0), config)["warning_blocks"]
    assert cold_after == cold_alone
    assert hot_first, "hot scenario must alert"


def test_cooldown_suppresses_rearm_until_window_expires():
    """A second excursion inside the cooldown window that decays before the
    window expires must NOT produce a second alert."""
    rng = np.random.default_rng(6)
    x = np.zeros(500)
    x[100:110] = 8.0      # first excursion -> alert ~102, cooldown until ~302
    x[205:225] = 8.0      # second excursion, decays below h well before 302
    x = x + rng.normal(0, 0.05, 500)
    config = CusumConfig(k_drift=2.0, h_threshold=15.0, persistence_k=3,
                         warmup_blocks=50, cooldown_blocks=200)
    det = detect_warnings_cusum(_frame(x), _cal(15.0), config)
    assert len(det["warning_blocks"]) == 1
    assert det["warning_blocks"][0] < 200


def test_consecutive_alerts_respect_cooldown_spacing():
    """Every pair of consecutive emissions must be separated by more than
    cooldown_blocks (the documented re-arm rule)."""
    rng = np.random.default_rng(6)
    x = np.zeros(800)
    x[100:110] = 8.0
    x[205:260] = 8.0
    x[500:620] = 8.0
    x = x + rng.normal(0, 0.05, 800)
    config = CusumConfig(k_drift=2.0, h_threshold=15.0, persistence_k=3,
                         warmup_blocks=50, cooldown_blocks=200)
    det = detect_warnings_cusum(_frame(x), _cal(15.0), config)
    fires = det["warning_blocks"]
    assert len(fires) >= 2
    for a, b in zip(fires, fires[1:]):
        assert b - a > config.cooldown_blocks


def test_calibration_selects_operating_point_within_budget():
    """Calibration must choose (k, h) meeting the declared budget on held-out
    benign data, and must record the achieved FPR."""
    rng = np.random.default_rng(7)
    ref_frames = []
    for i in range(6):
        x = rng.normal(0, 1, 300)
        ref_frames.append(pd.DataFrame({"excess_noise": x,
                                        "det_gain": rng.normal(0, 1, 300),
                                        "background": rng.normal(0, 1, 300)}))
    ref_df = pd.concat(ref_frames, ignore_index=True)
    benign_frames = []
    for i in range(8):
        x = rng.normal(0, 1, 600)
        benign_frames.append(pd.DataFrame({
            "scenario_id": f"b{i}",
            "excess_noise": x,
            "det_gain": rng.normal(0, 1, 600),
            "background": rng.normal(0, 1, 600),
            "block_index": np.arange(600)}))
    benign_df = pd.concat(benign_frames, ignore_index=True)
    config = CusumConfig(persistence_k=3, warmup_blocks=100)
    cal = calibrate_cusum_threshold(ref_df, benign_df, config, target_fpr=0.10)
    assert cal.achieved_scenario_fpr is not None
    assert cal.achieved_scenario_fpr <= 0.10 or cal.config.get("meets_target") is False
    assert cal.calibration_population == "phase4-validation-benign"


def test_real_simulator_scenario_end_to_end():
    """Run the detector through a complete simulator-generated scenario with the
    REAL frozen telemetry and reference statistics."""
    import json
    m4 = json.load(open(REPO / "data" / "phase4" / "manifest.json", encoding="utf-8"))
    benign = [s for s in m4["scenarios"] if s["scenario_class"] == "NORMAL"][:5]
    df = pd.read_parquet(REPO / "artifacts" / "phase4" / "features"
                         / f"{benign[0]['scenario_id']}.parquet")
    ref = fit_cusum_reference(df, CusumConfig(warmup_blocks=200))
    assert ref, "reference stats must be computable from real telemetry"
    config = CusumConfig(k_drift=2.0, h_threshold=200.0, persistence_k=3,
                         warmup_blocks=200)
    det = detect_warnings_cusum(df, CusumCalibration(ref, 200.0, 0.1, None, "test", {}), config)
    # benign scenario: h=200 must not fire (calibrated operating point)
    assert det["warning_blocks"] == []
    assert det["usable_mask"][:200].sum() == 0
    assert det["usable_mask"][200:].any()


def test_attack_scenario_is_detected_end_to_end():
    import json
    m4 = json.load(open(REPO / "data" / "phase4" / "manifest.json", encoding="utf-8"))
    attacks = [s for s in m4["scenarios"] if s["attack_type"] == "lo_manipulation"][:3]
    df = pd.read_parquet(REPO / "artifacts" / "phase4" / "features"
                         / f"{attacks[0]['scenario_id']}.parquet")
    ref = fit_cusum_reference(df, CusumConfig(warmup_blocks=200))
    config = CusumConfig(k_drift=2.0, h_threshold=200.0, persistence_k=3,
                         warmup_blocks=200)
    det = detect_warnings_cusum(df, CusumCalibration(ref, 200.0, 0.1, None, "test", {}), config)
    assert det["warning_blocks"], "LO manipulation must be detected"
    onset = int(df["attack_onset"].iloc[0])
    # the emission must not precede the warmup period
    assert det["warning_blocks"][0] >= 200


def test_config_validation_rejects_invalid_values():
    with pytest.raises(ValueError):
        CusumConfig(k_drift=-1.0).validate()
    with pytest.raises(ValueError):
        CusumConfig(h_threshold=0.0).validate()
    with pytest.raises(ValueError):
        CusumConfig(persistence_k=0).validate()
    with pytest.raises(ValueError):
        CusumConfig(warmup_blocks=1).validate()
    with pytest.raises(ValueError):
        CusumConfig(normalization="bogus").validate()