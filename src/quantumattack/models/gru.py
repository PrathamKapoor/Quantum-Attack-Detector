"""GRU sequence model (master prompt §30): deliberately small recurrent baseline.

1–2 recurrent layers + dense head → P(attack within H). CPU-only training
(torch 2.13.0+cpu) — architecture sized for that.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

from .sequences import build_sequences


@dataclass(frozen=True)
class SequenceModelConfig:
    """Temporal model configuration (recorded for versioning, master prompt §35)."""

    model_type: str = "gru"           # "gru" | "tcn"
    horizons: tuple[int, ...] = (10, 25, 50, 100)
    hidden_channels: int = 32
    num_layers: int = 1               # recurrent layers (GRU) / residual blocks (TCN)
    dropout: float = 0.1
    seq_length: int = 100             # L = 100 blocks = 1 s (docs/time-semantics.md)
    batch_size: int = 64
    lr: float = 1e-3
    max_epochs: int = 30
    early_stopping_patience: int = 5  # validation-only early stopping (§34)
    pos_weight: float | None = None   # class-weighted BCE (§33); None = auto from train
    seed: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: (list(v) if isinstance(v, tuple) else v) for k, v in d.items()}


def _make_torch(seed: int):
    import torch

    torch.manual_seed(seed)
    np.random.seed(seed % (2**32))
    return torch


class GRUModel:
    """Small GRU: input → GRU(hidden) → dense head → P(attack within H)."""

    def __init__(self, n_features: int, cfg: SequenceModelConfig):
        torch = _make_torch(cfg.seed)
        import torch.nn as nn

        self.cfg = cfg
        self.net = nn.Sequential(
            nn.GRU(n_features, cfg.hidden_channels, num_layers=cfg.num_layers,
                   batch_first=True, dropout=cfg.dropout if cfg.num_layers > 1 else 0.0),
        )
        self.head = nn.Linear(cfg.hidden_channels, 1)
        self.param_count = sum(p.numel() for p in self.net.parameters()) + sum(
            p.numel() for p in self.head.parameters())


def _gru_forward(model: GRUModel, x):
    import torch

    out, _ = model.net(x)
    # last timestep's hidden state (causal: uses only x[:t+1])
    return model.head(out[:, -1, :]).squeeze(-1)
