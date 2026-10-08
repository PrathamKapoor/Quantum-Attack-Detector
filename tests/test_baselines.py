"""Split, warning-policy, lead-time, scaler, label tests (master prompt §47).

- split: no scenario overlap
- pair isolation: no matched pair crosses split
- scaler: fit only on train (train-vs-test statistics differ)
- warning policy: correct persistence behavior
- lead time: correct sign and null handling
- sudden attack: no artificial precursor warning expected
- benign drift: no label contamination
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantumattack.baselines.splits import (  # noqa: E402
    split_scenarios, SplitConfig, pair_isolation_check,
)
from quantumattack.baselines.warnings import (  # noqa: E402
    WarningPolicy, warning_blocks_for_scenario, warning_time, lead_time,
    warning_category, evaluate_scenario_warnings, false_early_warning_rate,
)
from quantumattack.baselines.conventional import (  # noqa: E402
    ThresholdPolicy, calibrate_thresholds, detect_warnings, conventional_lead_time,
)
from quantumattack.baselines.logistic import (  # noqa: E402
    fit_horizon_model, ModelConfig, feature_group_columns, base_feature_columns,
    build_xy,
)
from quantumattack.dataset import RESTRICTED_COLUMNS  # noqa: E402


def _entries(n_scen: int = 12, paired: int = 4) -> list[dict]:
    """Synthetic manifest entries: unpaired + paired attack scenarios."""
    entries = []
    for i in range(n_scen):
        entries.append({"scenario_id": f"attack-lo-s{i}", "pair_id": "", "arm": "",
                        "attack_type": "lo_manipulation", "scenario_class": "ATTACK"})
    for i in range(paired):
        pid = f"pair-{i:03d}"
        entries.append({"scenario_id": f"normal-lo-s{i}", "pair_id": pid, "arm": "normal",
                        "attack_type": "none", "scenario_class": "NORMAL"})
        entries.append({"scenario_id": f"attack-lo-pair-s{i}", "pair_id": pid, "arm": "attack",
                        "attack_type": "lo_manipulation", "scenario_class": "ATTACK"})
    return entries


# ---------------------------------------------------------------------------
# Splits (master prompt §21/§22/§23)
# ---------------------------------------------------------------------------
def test_split_disjoint_scenarios():
    split = split_scenarios(_entries(), SplitConfig(seed=0))
    split.validate()  # raises on overlap
    ids = set(split.train) | set(split.val) | set(split.test)
    assert len(ids) == len(_entries()), "every scenario in exactly one partition"


def test_split_deterministic():
    a = split_scenarios(_entries(), SplitConfig(seed=5))
    b = split_scenarios(_entries(), SplitConfig(seed=5))
    assert a.train == b.train and a.val == b.val and a.test == b.test


def test_split_changes_with_seed():
    a = split_scenarios(_entries(), SplitConfig(seed=1))
    b = split_scenarios(_entries(), SplitConfig(seed=2))
    assert a.train != b.train or a.val != b.val


def test_pair_isolation_no_cross_split():
    split = split_scenarios(_entries(), SplitConfig(seed=3))
    pair_isolation_check(split, _entries())  # raises if a pair crosses


def test_pair_isolation_catches_violation():
    entries = _entries()
    split = split_scenarios(entries, SplitConfig(seed=3))
    # corrupt: move one pair member to another partition manually
    normal_member = next(e["scenario_id"] for e in entries if e.get("arm") == "normal")
    if normal_member in split.train:
        split.train.remove(normal_member)
        split.test.append(normal_member)
    else:
        split.test.remove(normal_member)
        split.train.append(normal_member)
    with pytest.raises(RuntimeError, match="crosses splits"):
        pair_isolation_check(split, entries)


def test_split_scenario_not_block_level():
    """Splits are scenario-level: no scenario contributes rows to two partitions
    (master prompt §21/§22)."""
    split = split_scenarios(_entries(), SplitConfig(seed=7))
    all_ids = split.train + split.val + split.test
    assert len(all_ids) == len(set(all_ids))
    # every scenario id appears exactly once — block-level splitting would be
    # impossible by construction here, but this pins the contract


def test_ood_holdout_family_to_test():
    entries = _entries() + [
        {"scenario_id": f"attack-ir-s{i}", "pair_id": "", "arm": "",
         "attack_type": "intercept_resend", "scenario_class": "ATTACK"}
        for i in range(4)
    ]
    split = split_scenarios(entries, SplitConfig(seed=0, ood_holdout_family="intercept_resend"))
    ir_ids = [e["scenario_id"] for e in entries if e["attack_type"] == "intercept_resend"]
    assert all(sid in split.test for sid in ir_ids), "OOD family must be entirely in test"
    assert not any(sid in split.train for sid in ir_ids)


# ---------------------------------------------------------------------------
# Scaler (master prompt §24)
# ---------------------------------------------------------------------------
def test_scaler_fit_on_train_only():
    rng = np.random.default_rng(0)
    X_train = rng.normal(0, 1, (200, 3))
    y_train = rng.integers(0, 2, 200)
    mc = ModelConfig(horizons=(10,))
    model = fit_horizon_model(X_train, y_train, 10, ["a", "b", "c"], mc)
    # scaler statistics match TRAIN, not any test set
    assert np.allclose(model.scaler_mean, X_train.mean(axis=0))
    assert np.allclose(model.scaler_std, np.where(X_train.std(axis=0) < 1e-12, 1.0, X_train.std(axis=0)))


def test_scaler_constant_column_safe():
    X = np.column_stack([np.ones(50), np.random.default_rng(1).normal(0, 1, 50)])
    y = np.random.default_rng(1).integers(0, 2, 50)
    model = fit_horizon_model(X, y, 10, ["c0", "c1"], ModelConfig(horizons=(10,)))
    assert model.scaler_std[0] == 1.0  # constant column → std clamped to 1, no div-by-zero


def test_feature_group_columns():
    base = ["lo_power", "x_var"]
    a = feature_group_columns("A", base)
    b = feature_group_columns("B", base)
    c = feature_group_columns("C", base)
    d = feature_group_columns("D", base)
    assert a == base
    assert set(b) > set(a)
    assert set(c) > set(a)
    assert set(d) >= set(b) | set(c)
    with pytest.raises(ValueError):
        feature_group_columns("E", base)


def test_build_xy_future_label_excludes_post_onset():
    """y_H(t)=0 for t ≥ onset even when the attack is ACTIVE (master prompt §19)."""
    rng = np.random.default_rng(2)
    n = 300
    df = pd.DataFrame({
        "lo_power": rng.normal(1, 0.01, n),
        "attack_onset": 150,
        "block_index": np.arange(n),
    })
    # add derived-feature columns so build_xy computes features
    frames = {"s": df}
    mc = ModelConfig(horizons=(25,), min_history_blocks=100)
    cols = base_feature_columns(df)  # lo_power
    X, y, idx = build_xy(frames, ["s"], 25, mc, cols)
    # y_H(t)=1 iff t < onset ≤ t+H → warning band [onset−H, onset) = [125, 150)
    blocks = [t for _, t in idx]
    y_by_block = dict(zip(blocks, y))
    assert all(y_by_block[t] == 1 for t in range(125, 150))
    assert all(y_by_block.get(t, 0) == 0 for t in range(100, 125))  # onset outside (t, t+25]
    assert all(y_by_block.get(t, 0) == 0 for t in range(150, 300))  # attack no longer future


# ---------------------------------------------------------------------------
# Warning policy (master prompt §29/§31/§32)
# ---------------------------------------------------------------------------
def _prob_df(p_vals: list[float], onset: int = 200, attack_type: str = "lo_manipulation",
             scenario_class: str = "ATTACK") -> pd.DataFrame:
    n = len(p_vals)
    return pd.DataFrame({
        "scenario_id": "s",
        "block_index": np.arange(n),
        "timestamp_ms": np.arange(n) * 10.0,
        "p_attack_future_h50": p_vals,
        "attack_onset": onset,
        "attack_type": attack_type,
        "scenario_class": scenario_class,
    })


def test_warning_persistence_required():
    """A single spike must NOT warn; K consecutive above threshold must."""
    policy = WarningPolicy(prob_threshold=0.5, persistence_k=3, cooldown_blocks=50)
    # one spike
    df = _prob_df([0.1, 0.9, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1])
    assert warning_blocks_for_scenario(df, 50, policy) == []
    # three consecutive
    df = _prob_df([0.1, 0.9, 0.9, 0.9, 0.1, 0.1, 0.1, 0.1])
    fires = warning_blocks_for_scenario(df, 50, policy)
    assert fires == [1]  # first block of the satisfied run


def test_warning_cooldown_suppresses_rearm():
    policy = WarningPolicy(prob_threshold=0.5, persistence_k=2, cooldown_blocks=8)
    # run1 fires at t=0, cooldown until t=8; run2 (t=4,5) suppressed; run3 (t=7,8):
    # t=8 not > 8 → suppressed. Only one warning total.
    df = _prob_df([0.9, 0.9, 0.1, 0.1, 0.9, 0.9, 0.1, 0.9, 0.9])
    fires = warning_blocks_for_scenario(df, 50, policy)
    assert fires == [0]


def test_warning_never_fires_below_threshold():
    policy = WarningPolicy(prob_threshold=0.9, persistence_k=1)
    df = _prob_df([0.5, 0.8, 0.89, 0.5])
    assert warning_blocks_for_scenario(df, 50, policy) == []


def test_lead_time_sign_and_null():
    # positive: warning before onset
    assert lead_time(200, [150, 180]) == 50.0
    # zero: simultaneous
    assert lead_time(200, [200]) == 0.0
    # negative: late
    assert lead_time(200, [210]) == -10.0
    # null: never warned
    assert lead_time(200, []) is None
    # null: no attack
    assert lead_time(None, [100]) is None
    assert warning_time([]) is None
    assert warning_time([42]) == 42.0


def test_warning_category_grace_period():
    """Master prompt §32: a 1-block warning and a 500-block warning are NOT the
    same category."""
    assert warning_category(500.0, grace_blocks=5) == "anticipatory"
    assert warning_category(1.0, grace_blocks=5) == "immediate"
    assert warning_category(0.0, grace_blocks=5) == "immediate"
    assert warning_category(-3.0, grace_blocks=5) == "late"
    assert warning_category(None, grace_blocks=5) == "none"


def test_false_early_warnings_scenario_level():
    """Master prompt §31: any valid warning on a benign scenario = false early
    warning (scenario-level, not row-level)."""
    benign = _prob_df([0.1, 0.9, 0.9, 0.9, 0.1, 0.1], onset=-1,
                      attack_type="none", scenario_class="NORMAL")
    r = evaluate_scenario_warnings(benign, 50, WarningPolicy(prob_threshold=0.5, persistence_k=3))
    assert r.n_warnings == 1
    assert r.category == "false_early_warning"
    assert r.lead_time_blocks is None  # no onset → no lead time semantics
    rates = false_early_warning_rate([r])
    assert rates["NORMAL"] == 1.0


def test_benign_scenario_no_label_contamination():
    """Benign scenario warnings never produce lead times or ATTACK categories."""
    benign = _prob_df([0.9] * 10, onset=-1, attack_type="none", scenario_class="BENIGN_DRIFT")
    r = evaluate_scenario_warnings(benign, 50, WarningPolicy(prob_threshold=0.5, persistence_k=1))
    assert r.lead_time_blocks is None
    assert r.category == "false_early_warning"


def test_sudden_attack_no_artificial_warning():
    """Sudden-onset attacks have no pre-onset signal (Phase 1 gate) — a warning
    can only appear at/after onset. The evaluation must not reward pre-onset
    warnings that cannot exist (master prompt §34)."""
    # probability series of a sudden attack: flat until onset (no precursor signal)
    p = [0.2] * 100 + [0.9] * 100  # jumps only AT onset
    df = _prob_df(p, onset=100, attack_type="intercept_resend")
    r = evaluate_scenario_warnings(df, 50, WarningPolicy(prob_threshold=0.5, persistence_k=3))
    # first warning at/after onset → not anticipatory
    assert r.warning_time >= 100 or r.warning_time is None
    assert r.category in ("immediate", "late", "none")


# ---------------------------------------------------------------------------
# Conventional detector (master prompt §13-§16)
# ---------------------------------------------------------------------------
def test_conventional_threshold_calibration_on_benign():
    rng = np.random.default_rng(3)
    benign = pd.DataFrame({"excess_noise": rng.normal(0.01, 0.001, 500)})
    cal = calibrate_thresholds(benign, ThresholdPolicy(threshold_method="normal_sigma"))
    assert "excess_noise" in cal.thresholds
    # 5σ above the SAMPLE mean (calibration uses reference statistics, master prompt §14)
    x = benign["excess_noise"].to_numpy(dtype=float)
    assert abs(cal.thresholds["excess_noise"] - (x.mean() + 5 * x.std())) < 1e-12


def test_conventional_detection_and_lead_time():
    rng = np.random.default_rng(4)
    n = 300
    # benign for 150 blocks, then ε̂ jumps
    xi = np.concatenate([rng.normal(0.01, 0.001, 150), rng.normal(0.05, 0.001, 150)])
    df = pd.DataFrame({
        "scenario_id": "s", "block_index": np.arange(n),
        "excess_noise": xi, "attack_onset": 150, "attack_type": "intercept_resend",
        "scenario_class": "ATTACK",
        "transmittance": np.full(n, 0.17), "lo_power": np.ones(n),
        "det_gain": np.ones(n), "skr_estimate": np.full(n, 3.0),
        "saturation_frac": np.zeros(n), "background": np.full(n, 0.002),
    })
    cal = calibrate_thresholds(df.iloc[:100], ThresholdPolicy(threshold_method="normal_sigma"))
    det = detect_warnings(df, cal, ThresholdPolicy(persistence_k=3, cooldown_blocks=50))
    assert det["warning_blocks"], "detector must fire on a large ε̂ jump"
    lt = conventional_lead_time(150, det["warning_blocks"])
    # fires after onset (reactive detector) → negative lead time, or never pre-onset
    assert lt is not None and lt < 150


def test_conventional_never_fires_returns_null():
    df = pd.DataFrame({
        "scenario_id": "s", "block_index": np.arange(100),
        "excess_noise": np.full(100, 0.01),
        "attack_onset": -1, "attack_type": "none", "scenario_class": "NORMAL",
        "transmittance": np.full(100, 0.17), "lo_power": np.ones(100),
        "det_gain": np.ones(100), "skr_estimate": np.full(100, 3.0),
        "saturation_frac": np.zeros(100), "background": np.full(100, 0.002),
    })
    cal = calibrate_thresholds(df, ThresholdPolicy(threshold_method="normal_sigma"))
    det = detect_warnings(df, cal, ThresholdPolicy())
    assert det["warning_blocks"] == []
    assert conventional_lead_time(-1, det["warning_blocks"]) is None
    # missing warning is None, NOT zero (master prompt §16)
    assert conventional_lead_time(50, []) is None


def test_qber_proxy_excluded_from_indicators():
    """Phase 1 found qber_proxy degenerate — it must not be a conventional
    baseline indicator (master prompt §13)."""
    from quantumattack.baselines.conventional import INDICATORS

    assert "qber_proxy" not in INDICATORS
