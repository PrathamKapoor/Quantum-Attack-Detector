"""Scenario-level data splitting (docs/dataset-spec.md §5/§6; master prompt §21-§23).

The unit of statistical independence is the SCENARIO/RUN, not the individual record
(master prompt §22). Splits are disjoint at scenario level; matched counterfactual
pairs NEVER cross partitions (both arms share the benign trajectory).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..simulator.config import DEFAULT_HORIZONS


@dataclass(frozen=True)
class SplitConfig:
    """Split strategy configuration.

    Partition method: by scenario with disjoint seed groups per class, matched
    pairs kept within one partition, OOD holdout by attack family.
    """

    train_fraction: float = 0.6
    val_fraction: float = 0.2    # test = remainder
    ood_holdout_family: str | None = None  # e.g. "intercept_resend" (later phases)
    seed: int = 0

    def validate(self) -> None:
        if not (0 < self.train_fraction < 1) or not (0 < self.val_fraction < 1):
            raise ValueError("fractions must be in (0, 1)")
        if self.train_fraction + self.val_fraction >= 1.0:
            raise ValueError("train+val fractions must leave a test remainder")

    def to_dict(self) -> dict:
        return {
            "train_fraction": self.train_fraction,
            "val_fraction": self.val_fraction,
            "ood_holdout_family": self.ood_holdout_family,
            "seed": self.seed,
        }


@dataclass
class Split:
    """Disjoint scenario-level partitions."""

    train: list[str]
    val: list[str]
    test: list[str]

    def validate(self) -> None:
        a, b, c = set(self.train), set(self.val), set(self.test)
        if a & b or a & c or b & c:
            overlap = (a & b) | (a & c) | (b & c)
            raise RuntimeError(f"split overlap: {sorted(overlap)}")

    def contains(self, scenario_id: str) -> str:
        for name, part in (("train", self.train), ("val", self.val), ("test", self.test)):
            if scenario_id in part:
                return name
        raise KeyError(f"scenario {scenario_id} not in any partition")


def split_scenarios(
    scenario_entries: list[dict],
    config: SplitConfig | None = None,
) -> Split:
    """Split scenario manifest entries into train/val/test.

    Rules (master prompt §21-§23):
      1. split by SCENARIO (whole runs), never by block;
      2. within a class, disjoint seed sets per partition (same config, different seeds);
      3. matched pairs stay within one partition (both arms same split);
      4. OOD holdout family (if configured) goes to test entirely.
    Deterministic given config.seed.
    """
    cfg = config or SplitConfig()
    cfg.validate()

    # group scenarios by "unit" = (pair_id if paired else scenario base, class)
    # units are atomic: all members of a unit go to the same partition
    import hashlib

    def unit_key(s: dict) -> str:
        if s.get("pair_id"):
            return f"pair:{s['pair_id']}"
        # unpaired: group by attack/drift definition + seed bucket later; here the
        # scenario_id base (before -s<seed>) identifies the definition
        base = s["scenario_id"].rsplit("-s", 1)[0]
        return f"unit:{base}"

    units: dict[str, list[dict]] = {}
    for s in scenario_entries:
        units.setdefault(unit_key(s), []).append(s)

    # OOD holdout: entire attack family to test
    ood_units: set[str] = set()
    if cfg.ood_holdout_family:
        for key, members in units.items():
            if any(m.get("attack_type") == cfg.ood_holdout_family for m in members):
                ood_units.add(key)

    # deterministic ordering: sort unit keys
    remaining = sorted(k for k in units if k not in ood_units)
    # hash-based assignment for reproducibility: sort by (hash(seed:key), key)
    def sort_key(k: str) -> tuple:
        h = int.from_bytes(hashlib.sha256(f"{cfg.seed}:{k}".encode()).digest()[:8], "big")
        return (h, k)

    remaining = sorted(remaining, key=sort_key)
    n = len(remaining)
    n_train = round(cfg.train_fraction * n)
    n_val = round(cfg.val_fraction * n)

    train_units = remaining[:n_train]
    val_units = remaining[n_train:n_train + n_val]
    test_units = remaining[n_train + n_val:] + sorted(ood_units)

    split = Split(
        train=sorted({s["scenario_id"] for k in train_units for s in units[k]}),
        val=sorted({s["scenario_id"] for k in val_units for s in units[k]}),
        test=sorted({s["scenario_id"] for k in test_units for s in units[k]}),
    )
    split.validate()
    return split


def pair_isolation_check(split: Split, scenario_entries: list[dict]) -> None:
    """Fail loudly if any matched pair crosses partitions (master prompt §21)."""
    pairs: dict[str, set[str]] = {}
    for s in scenario_entries:
        if s.get("pair_id"):
            pairs.setdefault(s["pair_id"], set()).add(split.contains(s["scenario_id"]))
    for pair_id, parts in pairs.items():
        if len(parts) > 1:
            raise RuntimeError(f"matched pair {pair_id} crosses splits: {sorted(parts)}")


def horizons_default() -> tuple[int, ...]:
    return DEFAULT_HORIZONS
