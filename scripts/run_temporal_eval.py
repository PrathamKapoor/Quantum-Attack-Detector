"""Phase 3 temporal model evaluation runner (GRU | TCN).

Usage:
    python scripts/run_temporal_eval.py --model gru --out artifacts/phase3/eval-gru
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import pandas as pd

from quantumattack.models.gru import SequenceModelConfig
from quantumattack.models.temporal_eval import run_temporal_evaluation
from quantumattack.baselines.splits import split_scenarios, SplitConfig
from quantumattack.baselines.warnings import WarningPolicy
from quantumattack.baselines.logistic import base_feature_columns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=("gru", "tcn"))
    ap.add_argument("--data", default=str(REPO / "data" / "phase3"))
    ap.add_argument("--features", default=str(REPO / "artifacts" / "phase3" / "features"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--split-seed", type=int, default=42)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--hidden", type=int, default=16)
    ap.add_argument("--ood-family", default=None)
    args = ap.parse_args()

    manifest = json.loads(Path(args.data, "manifest.json").read_text())
    frames = {}
    for s in manifest["scenarios"]:
        sid = s["scenario_id"]
        fpath = Path(args.features) / f"{sid}.parquet"
        frames[sid] = pd.read_parquet(fpath if fpath.exists() else Path(args.data) / f"{sid}.parquet")

    split = split_scenarios(
        manifest["scenarios"],
        SplitConfig(seed=args.split_seed, counterfactual_to_train=True,
                    ood_holdout_family=args.ood_family))
    cols = base_feature_columns(next(iter(frames.values())))
    cfg = SequenceModelConfig(
        model_type=args.model, hidden_channels=args.hidden, num_layers=1 if args.model == "gru" else 2,
        max_epochs=args.epochs, seq_length=100, batch_size=128,
        early_stopping_patience=4, seed=0)
    res = run_temporal_evaluation(frames, split, cfg, cols, WarningPolicy(sustained_until_onset=True),
                                  out_dir=args.out)
    print(f"== {args.model} (TEST) ==")
    for h, m in res["horizon_metrics"].items():
        print(f"H={h}: AUROC={m['auroc']} AUPRC={m['auprc']} Brier={m['brier']} warn={m['warning_rate_scenarios']}")
    for h in ("50", "100"):
        for atype, s in res["lead_time_summary"].get(h, {}).items():
            print(f"H={h} {atype}: succ={s['warning_success_rate']:.2f} med={s['median_lead_blocks']}")
    print("FWR:", res["false_early_warning_rates"])
    print(f"wrote {args.out}/metrics_{args.model}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
