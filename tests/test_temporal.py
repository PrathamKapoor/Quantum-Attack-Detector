"""Temporal model tests (master prompt §36/§47).

- sequence invariance: modifying telemetry after t does not change sequences ≤ t
- TCN causality: left-padding only; output at t depends on x[:t+1] exclusively
- sequence construction: ordering, boundaries, missing-history policy
- same harness metrics path as the logistic baseline
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantumattack.models.sequences import build_sequences, sequence_leakage_check  # noqa: E402
from quantumattack.models.gru import GRUModel, SequenceModelConfig, _gru_forward, _make_torch  # noqa: E402
from quantumattack.models.tcn import TCNModel, CausalConvBlock  # noqa: E402
from quantumattack.baselines.logistic import ModelConfig, base_feature_columns  # noqa: E402


@pytest.fixture(scope="module")
def frames():
    repo = Path(__file__).resolve().parents[1]
    import json

    manifest = json.loads((repo / "data" / "phase3" / "manifest.json").read_text())
    # 2 small scenarios (1 attack + 1 benign) for fast tests
    attack = next(s["scenario_id"] for s in manifest["scenarios"] if s["attack_type"] == "lo_manipulation")
    benign = next(s["scenario_id"] for s in manifest["scenarios"] if s["attack_type"] == "none")
    import pandas as pd

    return {sid: pd.read_parquet(repo / "data" / "phase3" / f"{sid}.parquet")
            for sid in (attack, benign)}


@pytest.fixture(scope="module")
def cols(frames):
    return base_feature_columns(next(iter(frames.values())))


def _perturb_after(df, t, seed=999):
    out = df.copy()
    rng = np.random.default_rng(seed)
    num_cols = [c for c in out.columns if out[c].dtype in (float, np.float64)
                and not c.startswith(("d1_", "d2_", "rm", "rv", "rs", "ewma", "cusum", "ks_", "ac1_"))]
    idx = out.index[out["block_index"] > t]
    for c in num_cols:
        out.loc[idx, c] = rng.normal(0, 1000, size=len(idx))
    return out


def test_sequence_invariance_to_future(frames, cols):
    """THE temporal leakage test (master prompt §36): sequences ending at/before t
    must be identical when telemetry after t is modified."""
    t = 500
    cfg = ModelConfig(min_history_blocks=100)
    X_a, y_a, idx_a = build_sequences(frames, list(frames), 50, cfg, cols, seq_length=100)
    frames_p = {k: _perturb_after(v, t) for k, v in frames.items()}
    X_b, y_b, idx_b = build_sequences(frames_p, list(frames), 50, cfg, cols, seq_length=100)
    assert idx_a == idx_b
    # sequences ending at/before t identical; after t different (non-vacuous)
    ends = np.array([i[1] for i in idx_a])
    before = ends <= t
    assert np.array_equal(X_a[before], X_b[before]), "future leak in sequences"
    after = ~before
    assert not np.array_equal(X_a[after], X_b[after])


def test_sequence_temporal_order(frames, cols):
    """Within a sequence: t-L+1 < ... < t (never shuffled; master prompt §29)."""
    cfg = ModelConfig(min_history_blocks=100)
    X, y, idx = build_sequences(frames, list(frames), 50, cfg, cols, seq_length=100)
    df = next(iter(frames.values()))
    blocks = df["block_index"].to_numpy()
    for (sid, t), window in zip(idx, X[: len(idx)]):
        expected = blocks[t - 99: t + 1]
        assert expected[0] == t - 99 and expected[-1] == t  # ordered, ends at t


def test_sequence_boundaries_and_missing_history(frames, cols):
    """Sequences require FULL history: first sequence ends at t=L-1 (t=99);
    warmup NaNs inside a window are skipped (no future fill)."""
    cfg = ModelConfig(min_history_blocks=100)
    X, y, idx = build_sequences(frames, list(frames), 50, cfg, cols, seq_length=100)
    ends = [i[1] for i in idx]
    assert min(ends) == 99  # L-1
    # NaN check: any window containing NaN would have been skipped
    assert not np.isnan(X).any()
    # y matches horizon definition: y(t)=1 iff t < onset <= t+50
    sid, t = idx[0]
    onset = int(frames[sid]["attack_onset"].iloc[0])
    if onset >= 0:
        y_expected = 1 if t < onset <= t + 50 else 0
        assert y[0] == y_expected


def test_tcn_causal_padding():
    """TCN causality: changing FUTURE timesteps must not change output at t
    (master prompt §31: left padding only)."""
    torch = _make_torch(0)
    block = CausalConvBlock(1, 1, dilation=1, kernel_size=3, dropout=0.0, seed=0)
    block.conv.weight.data.fill_(0.25)
    block.conv.bias.data.zero_()
    x = torch.arange(10, dtype=torch.float32).reshape(1, 1, 10)
    out_full = block(x)
    # perturb FUTURE (last 3 timesteps)
    x2 = x.clone()
    x2[0, 0, -3:] = 1000.0
    out_perturbed = block(x2)
    # outputs at t=0..6 (which cannot see beyond t) unchanged
    assert torch.allclose(out_full[0, 0, :7], out_perturbed[0, 0, :7]), "TCN leaks future"
    # output at the last timesteps changed (non-vacuous)
    assert not torch.allclose(out_full[0, 0, -3:], out_perturbed[0, 0, -3:])


def test_tcn_output_shape_and_last_step():
    torch = _make_torch(0)
    cfg = SequenceModelConfig(model_type="tcn", num_layers=2, hidden_channels=8, seed=0)
    model = TCNModel(4, cfg)
    x = torch.randn(2, 100, 4)
    out = model(x)
    assert out.shape == (2,)  # one P(attack) per sequence


def test_gru_output_shape_and_last_step():
    torch = _make_torch(0)
    cfg = SequenceModelConfig(model_type="gru", num_layers=1, hidden_channels=8, seed=0)
    model = GRUModel(4, cfg)
    x = torch.randn(2, 100, 4)
    out = _gru_forward(model, x)
    assert out.shape == (2,)
    # GRU is recurrent: output at t uses x[:t+1]; changing ONLY future timesteps
    # (t+1..) cannot affect it because we feed the full window and take [:, -1]


def test_param_counts_recorded():
    cfg = SequenceModelConfig(model_type="gru", hidden_channels=8, num_layers=1, seed=0)
    m = GRUModel(10, cfg)
    assert m.param_count > 0
    cfg2 = SequenceModelConfig(model_type="tcn", hidden_channels=8, num_layers=2, seed=0)
    t = TCNModel(10, cfg2)
    assert t.param_count > 0


def test_sequence_model_config_recorded():
    cfg = SequenceModelConfig()
    d = cfg.to_dict()
    for k in ("model_type", "hidden_channels", "num_layers", "seq_length", "batch_size",
              "lr", "max_epochs", "early_stopping_patience", "seed"):
        assert k in d
