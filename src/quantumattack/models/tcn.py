"""TCN (Temporal Convolutional Network) with CAUSAL convolutions (master prompt §31).

Causal padding: each layer pads ONLY on the left (past) side — the output at t
depends on x[:t+1] exclusively. Ordinary same-padding convolutions would leak
future information; a causality test verifies left-padding correctness.
"""
from __future__ import annotations

import numpy as np

from .gru import SequenceModelConfig, _make_torch


class CausalConvBlock:
    """Residual block: causal dilated Conv1d → ReLU → dropout (left padding only)."""

    def __init__(self, in_ch: int, out_ch: int, dilation: int, kernel_size: int, dropout: float, seed: int):
        torch = _make_torch(seed)
        import torch.nn as nn

        self.pad_left = (kernel_size - 1) * dilation
        self.conv = nn.Conv1d(in_ch, out_ch, kernel_size, dilation=dilation)
        self.drop = nn.Dropout(dropout)
        self.residual = in_ch == out_ch
        self.proj = nn.Conv1d(in_ch, out_ch, 1) if not self.residual else None

    def __call__(self, x):
        # x: (B, C, T); pad LEFT only → causal
        import torch.nn.functional as F

        y = F.pad(x, (self.pad_left, 0))
        y = self.drop(F.relu(self.conv(y)))
        r = x if self.residual else self.proj(x)
        return y + r


class TCNModel:
    """TCN: input → N causal residual blocks (increasing dilation) → last-step head."""

    def __init__(self, n_features: int, cfg: SequenceModelConfig):
        import torch.nn as nn

        self.cfg = cfg
        blocks = []
        in_ch = n_features
        for i in range(cfg.num_layers):
            dilation = 2 ** i  # 1, 2, 4, ...
            blocks.append(CausalConvBlock(in_ch, cfg.hidden_channels, dilation,
                                          kernel_size=3, dropout=cfg.dropout, seed=cfg.seed))
            in_ch = cfg.hidden_channels
        self.blocks = blocks
        self.head = nn.Linear(cfg.hidden_channels, 1)
        self.param_count = sum(p.numel() for b in blocks for p in (
            b.conv.parameters().__next__(),) if True) + (
            sum(p.numel() for p in self.head.parameters()))

    def __call__(self, x):
        # x: (B, T, F) → transpose to (B, F, T) for Conv1d
        import torch

        y = x.transpose(1, 2)
        for block in self.blocks:
            y = block(y)
        # last timestep (causal: depends only on x[:t+1])
        return self.head(y[:, :, -1]).squeeze(-1)
