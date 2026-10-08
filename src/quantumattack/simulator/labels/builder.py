"""Label generation (docs/time-semantics.md §5; master prompt §16).

Labels are derived AFTER simulation from onset metadata only — the simulator state
carries no labels (leakage risk #4). For block t:

- current_attack = 1 if attack_onset <= t
- y_H(t) = 1 if t < attack_onset <= t + H (attack BEGINS within next H blocks)
- state_label precedence: ATTACK > PRECURSOR > BENIGN_DRIFT > NORMAL
"""
from __future__ import annotations

from ..config import DEFAULT_HORIZONS


def build_labels(
    n_blocks: int,
    attack_onset: int,          # -1 if no attack
    precursor_start: int,       # -1 if no attack; == attack_onset for class C
    has_precursor: bool,        # attack has class A/B precursor
    drift_episode_blocks: set[int],  # ground-truth episode block indices (benign scenarios)
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> dict[str, list]:
    """Build all label arrays for one scenario run."""
    labels: dict[str, list] = {
        "state_label": [],
        "current_attack": [],
    }
    for h in horizons:
        labels[f"future_attack_h{h}"] = []

    for t in range(n_blocks):
        current = 1 if (attack_onset >= 0 and t >= attack_onset) else 0
        labels["current_attack"].append(current)

        for h in horizons:
            if attack_onset >= 0 and t < attack_onset <= t + h:
                labels[f"future_attack_h{h}"].append(1)
            else:
                labels[f"future_attack_h{h}"].append(0)

        # state_label precedence: ATTACK > PRECURSOR > BENIGN_DRIFT > NORMAL
        if current:
            lab = "ATTACK"
        elif (
            has_precursor
            and precursor_start >= 0
            and precursor_start <= t < attack_onset
        ):
            lab = "PRECURSOR"
        elif t in drift_episode_blocks:
            lab = "BENIGN_DRIFT"
        else:
            lab = "NORMAL"
        labels["state_label"].append(lab)

    return labels
