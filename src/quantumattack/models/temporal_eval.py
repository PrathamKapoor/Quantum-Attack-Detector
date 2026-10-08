"""Temporal model training + evaluation (master prompt §26-§36, §35).

Same input/target/splits/horizons/policy as the logistic baseline (§27) — only the
model class changes. Validation-only early stopping (§34); class-weighted BCE (§33);
full experiment manifest (§35).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .gru import GRUModel, SequenceModelConfig, _gru_forward, _make_torch
from .tcn import TCNModel
from .sequences import build_sequences
from ..baselines.logistic import feature_group_columns, base_feature_columns
from ..baselines.warnings import (
    WarningPolicy, warning_blocks_for_scenario, evaluate_scenario_warnings,
    false_early_warning_rate, summarize_lead_times, attribute_warnings,
)
from ..evaluation.harness import (
    classification_metrics, calibration_error, _scenario_warning_rate,
)


def make_model(n_features: int, cfg: SequenceModelConfig):
    """Instantiate the configured temporal model (gru | tcn)."""
    if cfg.model_type == "gru":
        return GRUModel(n_features, cfg)
    if cfg.model_type == "tcn":
        return TCNModel(n_features, cfg)
    raise ValueError(f"unknown model_type: {cfg.model_type!r}")


def train_temporal_model(
    frames: dict[str, pd.DataFrame],
    split,
    cfg: SequenceModelConfig,
    feature_columns: list[str],
    horizon: int,
):
    """Train one temporal model for one horizon (validation-only early stopping)."""
    torch = _make_torch(cfg.seed)
    import torch.nn as nn

    X_train, y_train, _ = build_sequences(
        frames, split.train, horizon, _mc_from(cfg), feature_columns,
        seq_length=cfg.seq_length)
    X_val, y_val, _ = build_sequences(
        frames, split.val, horizon, _mc_from(cfg), feature_columns,
        seq_length=cfg.seq_length)

    model = make_model(X_train.shape[2], cfg)
    # class-weighted BCE (§33): pos_weight = n_neg/n_pos from TRAIN (never test)
    n_pos = float(y_train.sum())
    n_neg = float(len(y_train) - n_pos)
    pos_weight = cfg.pos_weight if cfg.pos_weight is not None else (n_neg / max(n_pos, 1.0))
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(pos_weight, dtype=torch.float32))

    def _params():
        if hasattr(model, "net"):  # GRU
            return list(model.net.parameters()) + list(model.head.parameters())
        params = []  # TCN: blocks have conv/proj
        for b in model.blocks:
            params += list(b.conv.parameters())
            if b.proj is not None:
                params += list(b.proj.parameters())
        params += list(model.head.parameters())
        return params

    optimizer = torch.optim.Adam(_params(), lr=cfg.lr)

    xt = torch.tensor(X_train)
    yt = torch.tensor(y_train)
    xv = torch.tensor(X_val)
    yv = torch.tensor(y_val)

    best_val = float("inf")
    best_state = None
    patience_left = cfg.early_stopping_patience
    rng = np.random.default_rng(cfg.seed)
    for epoch in range(cfg.max_epochs):
        if hasattr(model, "net"):
            model.net.train()
        else:
            for b in model.blocks:
                b.drop.train()
        # batch shuffle (batch ordering only — leaks nothing, §29)
        perm = rng.permutation(len(xt))
        for i in range(0, len(xt), cfg.batch_size):
            idx = perm[i:i + cfg.batch_size]
            optimizer.zero_grad()
            logits = _forward(model, xt[idx])
            loss = criterion(logits, yt[idx])
            loss.backward()
            optimizer.step()
        # validation-only early stopping (§34)
        if hasattr(model, "net"):
            model.net.eval()
        else:
            for b in model.blocks:
                b.drop.eval()
        with torch.no_grad():
            val_loss = float(criterion(_forward(model, xv), yv))
        if val_loss < best_val:
            best_val = val_loss
            best_state = {k: v.clone() for k, v in _state_dict(model).items()}
            patience_left = cfg.early_stopping_patience
        else:
            patience_left -= 1
            if patience_left <= 0:
                break
    if best_state is not None:
        _load_state(model, best_state)

    return model, {
        "model_type": cfg.model_type, "param_count": model.param_count,
        "seed": cfg.seed, "feature_schema": "2", "seq_length": cfg.seq_length,
        "horizon": horizon, "optimizer": "Adam", "lr": cfg.lr,
        "batch_size": cfg.batch_size, "epochs_run": epoch + 1,
        "max_epochs": cfg.max_epochs,
        "early_stopping_patience": cfg.early_stopping_patience,
        "best_val_loss": best_val, "pos_weight": float(pos_weight),
        "train_n": int(len(y_train)), "train_pos": int(y_train.sum()),
        "val_n": int(len(y_val)), "val_pos": int(y_val.sum()),
    }


def _mc_from(cfg: SequenceModelConfig):
    """Build the logistic-style ModelConfig view (min_history for build_sequences)."""
    from ..baselines.logistic import ModelConfig

    return ModelConfig(horizons=cfg.horizons, feature_group="D",
                       min_history_blocks=cfg.seq_length)


def _forward(model, x):
    if hasattr(model, "net"):  # GRU
        return _gru_forward(model, x)
    return model(x)  # TCN


def _state_dict(model):
    if hasattr(model, "net"):
        return {**{f"net.{k}": v for k, v in model.net.state_dict().items()},
                **{f"head.{k}": v for k, v in model.head.state_dict().items()}}
    sd = {}
    for i, b in enumerate(model.blocks):
        for k, v in b.conv.state_dict().items():
            sd[f"b{i}.conv.{k}"] = v
        for k, v in b.drop.state_dict().items():
            sd[f"b{i}.drop.{k}"] = v
        if b.proj is not None:
            for k, v in b.proj.state_dict().items():
                sd[f"b{i}.proj.{k}"] = v
    for k, v in model.head.state_dict().items():
        sd[f"head.{k}"] = v
    return sd


def _load_state(model, state):
    if hasattr(model, "net"):
        model.net.load_state_dict({k[4:]: v for k, v in state.items() if k.startswith("net.")})
        model.head.load_state_dict({k[5:]: v for k, v in state.items() if k.startswith("head.")})
    else:
        for i, b in enumerate(model.blocks):
            b.conv.load_state_dict({k.split(".conv.")[1]: v for k, v in state.items()
                                    if k.startswith(f"b{i}.conv.")})
            if b.proj is not None:
                b.proj.load_state_dict({k.split(".proj.")[1]: v for k, v in state.items()
                                        if k.startswith(f"b{i}.proj.")})
        model.head.load_state_dict({k[5:]: v for k, v in state.items() if k.startswith("head.")})


def predict_temporal(
    model,
    frames: dict[str, pd.DataFrame],
    scenario_ids: list[str],
    cfg: SequenceModelConfig,
    feature_columns: list[str],
    horizon: int,
) -> pd.DataFrame:
    """P(attack within H) per block from the trained temporal model (causal)."""
    torch = _make_torch(cfg.seed)
    X, _, index = build_sequences(
        frames, scenario_ids, horizon, _mc_from(cfg), feature_columns,
        seq_length=cfg.seq_length)
    probs = []
    if hasattr(model, "net"):
        model.net.eval()
    else:
        for b in model.blocks:
            b.drop.eval()
    with torch.no_grad():
        for i in range(0, len(X), 512):
            logits = _forward(model, torch.tensor(X[i:i + 512]))
            probs.append(torch.sigmoid(logits).numpy())
    p = np.concatenate(probs) if probs else np.array([])
    onset_by_sid = {sid: int(frames[sid]["attack_onset"].iloc[0]) for sid in scenario_ids}
    atype_by_sid = {sid: str(frames[sid]["attack_type"].iloc[0]) for sid in scenario_ids}
    sclass_by_sid = {sid: str(frames[sid]["scenario_class"].iloc[0]) for sid in scenario_ids}
    ts_by_sid = {sid: frames[sid]["timestamp_ms"].to_numpy() for sid in scenario_ids}
    rows = []
    for (sid, t), pi in zip(index, p):
        rows.append({
            "scenario_id": sid, "block_index": t,
            "timestamp_ms": float(ts_by_sid[sid][t]),
            f"p_attack_future_h{horizon}": float(pi),
            "attack_onset": onset_by_sid[sid],
            "attack_type": atype_by_sid[sid],
            "scenario_class": sclass_by_sid[sid],
        })
    return pd.DataFrame(rows)


def run_temporal_evaluation(
    frames: dict[str, pd.DataFrame],
    split,
    cfg: SequenceModelConfig,
    feature_columns: list[str],
    warning_policy: WarningPolicy,
    out_dir=None,
) -> dict:
    """Full temporal-model evaluation: same harness metrics (§27 — only the model
    class changes)."""
    import json
    from pathlib import Path

    preds_all: list[pd.DataFrame] = []
    training_info: dict[int, dict] = {}
    for h in cfg.horizons:
        model, info = train_temporal_model(frames, split, cfg, feature_columns, h)
        training_info[h] = info
        eval_ids = split.val + split.test
        preds_all.append(predict_temporal(model, frames, eval_ids, cfg, feature_columns, h))
        if out_dir is not None:
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            preds_all[-1].to_parquet(Path(out_dir) / f"preds_{cfg.model_type}_h{h}.parquet", index=False)

    # merge per-horizon predictions (join on scenario_id+block_index)
    merged = preds_all[0]
    for extra in preds_all[1:]:
        pcols = [c for c in extra.columns if c.startswith("p_attack_future")]
        merged = merged.merge(extra[["scenario_id", "block_index"] + pcols],
                              on=["scenario_id", "block_index"], how="inner")

    # metrics on TEST only (§25: test = final evaluation)
    test_preds = merged[merged["scenario_id"].isin(split.test)]
    horizon_metrics: dict[int, dict] = {}
    for h in cfg.horizons:
        y = test_preds[f"y_true_h{h}"].to_numpy() if f"y_true_h{h}" in test_preds.columns else None
        p = test_preds[f"p_attack_future_h{h}"].to_numpy()
        if y is None:
            # reconstruct y from onset metadata (causal label definition)
            onset = test_preds["attack_onset"].to_numpy()
            t = test_preds["block_index"].to_numpy()
            y = ((t < onset) & (t + h >= onset)).astype(int)
        m = classification_metrics(y, p)
        m.update(calibration_error(y, p))
        m["warning_rate_scenarios"] = _scenario_warning_rate(test_preds, h, warning_policy)
        horizon_metrics[h] = m

    # per-scenario warning evaluation (Metric A: independent early warning)
    warning_results = []
    for sid in split.test:
        df_s = test_preds[test_preds["scenario_id"] == sid]
        if df_s.empty:
            continue
        for h in cfg.horizons:
            warning_results.append(evaluate_scenario_warnings(df_s, h, warning_policy))

    lt_summary = summarize_lead_times(warning_results, category_filter="anticipatory")
    attributed = attribute_warnings(warning_results, warning_results, max(cfg.horizons))
    from ..baselines.warnings import summarize_lead_times_attributed

    lt_attributed = summarize_lead_times_attributed(
        warning_results, warning_results, max(cfg.horizons), attributed)
    fwr = false_early_warning_rate(warning_results)

    result = {
        "model_type": cfg.model_type,
        "training": {str(k): v for k, v in training_info.items()},
        "horizon_metrics": {str(k): v for k, v in horizon_metrics.items()},
        "lead_time_summary": lt_summary,
        "lead_time_summary_attributed": lt_attributed,
        "false_early_warning_rates": fwr,
        "model_config": cfg.to_dict(),
    }
    if out_dir is not None:
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        (Path(out_dir) / f"metrics_{cfg.model_type}.json").write_text(
            json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result
