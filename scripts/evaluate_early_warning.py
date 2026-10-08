"""Early-warning evaluation CLI (master prompt §45): thin wrapper over the harness.

Usage:
    python scripts/evaluate_early_warning.py [--data data/phase1]
        [--features artifacts/phase2/features] [--out artifacts/phase2/eval]
        [--feature-group D] [--split-seed 0]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from quantumattack.evaluation.harness import run_evaluation  # noqa: E402
from quantumattack.baselines.logistic import ModelConfig  # noqa: E402
from quantumattack.baselines.splits import SplitConfig  # noqa: E402
from quantumattack.baselines.warnings import WarningPolicy  # noqa: E402
from quantumattack.baselines.conventional import ThresholdPolicy  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 2 early-warning evaluation")
    parser.add_argument("--data", default=str(REPO / "data" / "phase1"))
    parser.add_argument("--features", default=str(REPO / "artifacts" / "phase2" / "features"))
    parser.add_argument("--out", default=str(REPO / "artifacts" / "phase2" / "eval"))
    parser.add_argument("--feature-group", default="D", choices=("A", "B", "C", "D"))
    parser.add_argument("--split-seed", type=int, default=0)
    args = parser.parse_args(argv)

    res = run_evaluation(
        data_dir=Path(args.data),
        features_dir=Path(args.features),
        out_dir=Path(args.out),
        model_config=ModelConfig(feature_group=args.feature_group),
        split_config=SplitConfig(seed=args.split_seed),
        warning_policy=WarningPolicy(),
        threshold_policy=ThresholdPolicy(),
        experiment_id=f"phase2-baseline-{args.feature_group}",
    )
    print(f"evaluation complete → {args.out}")
    for h, m in res.horizon_metrics.items():
        auroc = "n/a" if m["auroc"] is None else f"{m['auroc']:.4f}"
        auprc = "n/a" if m["auprc"] is None else f"{m['auprc']:.4f}"
        print(f"H={h}: AUROC={auroc} AUPRC={auprc} "
              f"warn_rate={m['warning_rate_scenarios']}")
    for atype, s in res.lead_time_summary.items():
        med = "n/a" if s["median_lead_blocks"] is None else f"{s['median_lead_blocks']:.0f} blocks"
        print(f"{atype}: success={s['warning_success_rate']:.2f} median_lead={med}")
    print(f"false early warnings: {res.false_warning_rates}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
