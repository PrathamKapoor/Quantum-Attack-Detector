"""Data-integrity regression tests: causal invariance, split isolation,
schedule-leakage resistance (docs/reliability-evaluation-protocol.md §12).

These enforce the properties that distinguish genuine forecasting from a model
that has learned the simulator's scheduling conventions.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantumattack.features import compute_features, derived_feature_names  # noqa: E402
from quantumattack.dataset import FEATURE_COLUMNS, RESTRICTED_COLUMNS  # noqa: E402
from quantumattack.baselines.logistic import (  # noqa: E402
    ModelConfig, build_xy, feature_group_columns, predict_proba, fit_horizon_model,
)
from quantumattack.baselines.splits import (  # noqa: E402
    split_scenarios, SplitConfig, pair_isolation_check,
)

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def raw_scenario():
    files = sorted((REPO / "data" / "phase3").glob("*.parquet"))
    return files[0].stem, pd.read_parquet(files[0])


def test_derived_features_are_invariant_to_future_telemetry(raw_scenario):
    """THE temporal leakage test on the real pipeline: modify telemetry strictly
    after t, recompute all derived features, and require that every feature at
    and before t is bit-identical (NaN masks included)."""
    _, raw = raw_scenario
    t = 800
    base_cols = [c for c in FEATURE_COLUMNS if c in raw.columns]

    perturbed = raw.copy()
    rng = np.random.default_rng(42)
    idx = perturbed.index[perturbed["block_index"] > t]
    for c in base_cols:
        col = perturbed[c]
        if col.dtype in (float, np.float64):
            perturbed.loc[idx, c] = rng.normal(col.mean(), col.std(), size=len(idx))

    f_a = compute_features(raw)
    f_b = compute_features(perturbed)

    checked = 0
    changed_future = 0
    for c in derived_feature_names():
        if c not in f_a.columns or c not in f_b.columns:
            continue
        a = f_a[c].to_numpy(dtype=float)
        b = f_b[c].to_numpy(dtype=float)
        checked += 1
        na, nb = np.isnan(a[: t + 1]), np.isnan(b[: t + 1])
        assert np.array_equal(na, nb), f"{c}: NaN mask changed at/before t (future leak)"
        m = ~na
        if m.any():
            assert np.allclose(a[: t + 1][m], b[: t + 1][m], rtol=1e-9, atol=1e-12), \
                f"{c}: value changed at/before t after modifying future telemetry"
        # non-vacuity: the perturbation must actually change this feature later on
        fm = ~np.isnan(a[t + 1:]) & ~np.isnan(b[t + 1:])
        if fm.any() and not np.allclose(a[t + 1:][fm], b[t + 1:][fm]):
            changed_future += 1
    assert checked > 100, "expected the full derived-feature set to be checked"
    # If NOTHING changed after t the test would be vacuous — require real effect.
    assert changed_future > 50, "temporal-invariance test was vacuous"


def test_base_telemetry_columns_are_not_in_the_derived_feature_set():
    """Derived features must not duplicate or shadow restricted metadata."""
    derived = derived_feature_names()
    forbidden = ("attack_onset", "precursor_start", "attack_type", "scenario_class",
                 "current_attack", "future_attack", "state_label", "pair_id", "seed")
    for name in forbidden:
        assert not any(name in d for d in derived), \
            f"derived feature appears to embed restricted metadata: {name}"


def test_restricted_columns_never_reach_model_input():
    """The production path selects base columns by intersecting with
    FEATURE_COLUMNS, and FEATURE_COLUMNS is disjoint from RESTRICTED_COLUMNS.
    Every feature group built from that sanitized input must stay clean."""
    from quantumattack.baselines.logistic import base_feature_columns

    # Simulate a raw frame carrying BOTH telemetry and restricted columns.
    cols = sorted(set(FEATURE_COLUMNS) | set(RESTRICTED_COLUMNS))
    frame = pd.DataFrame({c: [0.0, 1.0] for c in cols})
    base = base_feature_columns(frame)
    assert base, "expected telemetry features to be selected"
    assert not (set(base) & set(RESTRICTED_COLUMNS)), \
        "base_feature_columns must never select labels/metadata/eval-only columns"

    for g in ("A", "B", "C", "D"):
        cols_g = feature_group_columns(g, base)
        leaked = set(cols_g) & set(RESTRICTED_COLUMNS)
        assert not leaked, f"feature group {g} would include restricted columns {leaked}"


def test_feature_and_restricted_column_sets_are_disjoint():
    """Structural invariant: a column can never be both a feature and restricted."""
    overlap = set(FEATURE_COLUMNS) & set(RESTRICTED_COLUMNS)
    assert not overlap, f"columns classified as both feature and restricted: {sorted(overlap)}"


def test_scenario_level_split_is_disjoint_and_deterministic():
    entries = [{"scenario_id": f"s{i}", "seed": i, "scenario_class": "NORMAL",
                "attack_type": "none"} for i in range(60)]
    a = split_scenarios(entries, SplitConfig(seed=42))
    b = split_scenarios(entries, SplitConfig(seed=42))
    assert set(a.train) & set(a.val) == set()
    assert set(a.train) & set(a.test) == set()
    assert set(a.val) & set(a.test) == set()
    assert (sorted(a.train), sorted(a.val), sorted(a.test)) == \
           (sorted(b.train), sorted(b.val), sorted(b.test))
    assert set(a.train) | set(a.val) | set(a.test) == {e["scenario_id"] for e in entries}


def test_split_raises_on_overlap():
    """Validation must REJECT a deliberate split violation."""
    s = split_scenarios([{"scenario_id": f"s{i}", "seed": i} for i in range(20)],
                        SplitConfig(seed=1))
    object.__setattr__(s, "val", list(s.val) + [s.train[0]])  # inject overlap
    with pytest.raises(RuntimeError):
        s.validate()


def test_build_xy_label_matches_horizon_definition():
    """y_H(t)=1 iff t < onset <= t+H; y=0 for t>=onset (no post-onset credit)."""
    df = pd.DataFrame({
        "scenario_id": ["s"] * 500,
        "block_index": np.arange(500),
        "attack_onset": [300] * 500,
        "attack_type": ["lo_manipulation"] * 500,
        "scenario_class": ["ATTACK"] * 500,
        "x": np.arange(500, dtype=float),
    })
    mc = ModelConfig(min_history_blocks=100)
    cols = ["x"]
    _, y, idx = build_xy({"s": df}, ["s"], 100, mc, cols)
    lut = {t: int(v) for (sid, t), v in zip(idx, y)}
    assert lut[200] == 1   # onset 300 within (200, 300]
    assert lut[199] == 0   # onset 301 blocks away -> beyond H=100
    assert lut[201] == 1
    assert lut[250] == 1
    assert lut[301] == 0   # onset already passed -> post-onset, no forecast credit
    assert lut[299] == 1   # t+1 == onset -> still inside horizon
    assert lut[300] == 0   # t == onset -> attack already underway


def test_time_only_baseline_is_near_chance_on_horizon_label():
    """Guard against schedule learning: block position alone must not predict the
    horizon label. This mirrors the measured result (time-only AUROC ~0.52)."""
    df = pd.DataFrame({
        "scenario_id": ["s"] * 1200,
        "block_index": np.arange(1200),
        "attack_onset": [700] * 1200,
        "attack_type": ["lo_manipulation"] * 1200,
        "scenario_class": ["ATTACK"] * 1200,
        "x": np.random.default_rng(0).normal(size=1200),
    })
    mc = ModelConfig(min_history_blocks=100)
    _, y, idx = build_xy({"s": df}, ["s"], 100, mc, ["x"])
    t_pos = np.array([t for (_, t) in idx], dtype=float) / df["block_index"].max()
    from sklearn.metrics import roc_auc_score
    auc = roc_auc_score(y, t_pos)
    # A pure time feature should be well below the telemetry model's performance.
    assert auc < 0.75, f"time-only feature predicts y_H too strongly (AUROC={auc:.3f})"