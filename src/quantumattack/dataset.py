"""Dataset column classes (docs/dataset-spec.md §2; master prompt §34).

Machine-readable classification of every column. The invariant
FEATURE_COLUMNS ∩ RESTRICTED_COLUMNS = ∅ is enforced here and tested.
"""
from __future__ import annotations

from .simulator.telemetry.collector import FEATURE_COLUMNS, TRUE_COLUMNS

METADATA_COLUMNS: frozenset[str] = frozenset({
    "scenario_id", "pair_id", "arm", "seed", "protocol", "sim_version",
    "config_hash", "scenario_class", "attack_type", "attack_onset",
    "precursor_start", "precursor_class",
})

LABEL_COLUMNS: frozenset[str] = frozenset({
    "state_label", "current_attack", "future_attack_h10", "future_attack_h25",
    "future_attack_h50", "future_attack_h100", "drift_episode_id",
})

EVAL_ONLY_COLUMNS: frozenset[str] = frozenset(TRUE_COLUMNS) | frozenset({
    "block_index", "timestamp_ms",
})

RESTRICTED_COLUMNS: frozenset[str] = METADATA_COLUMNS | LABEL_COLUMNS | EVAL_ONLY_COLUMNS

FEATURE_COLUMNS: frozenset[str] = frozenset(FEATURE_COLUMNS) - RESTRICTED_COLUMNS

# Subset of restricted columns that must NEVER become model inputs (master prompt §34)
NEVER_MODEL_INPUTS: frozenset[str] = frozenset({
    "attack_type", "attack_onset", "precursor_start", "state_label",
    "current_attack", "scenario_class", "pair_id", "seed",
    "future_attack_h10", "future_attack_h25", "future_attack_h50",
    "future_attack_h100", "drift_episode_id",
})


def validate_column_classes() -> None:
    """Fail loudly if the feature set leaks restricted columns."""
    leak = FEATURE_COLUMNS & RESTRICTED_COLUMNS
    if leak:
        raise RuntimeError(f"column-class invariant violated: {sorted(leak)}")


validate_column_classes()
