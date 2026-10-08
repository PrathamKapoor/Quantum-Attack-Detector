"""Feature ablation experiments (master prompt §38): A/B/C/D feature groups.

A: base telemetry only · B: +first differences · C: +temporal statistics ·
D: all candidate causal features. Objective: does temporal information actually
improve forecasting? Do not assume it does.

Run: PYTHONPATH=src python -m quantumattack.ablation
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quantumattack.evaluation.harness import run_evaluation  # noqa: E402
from quantumattack.baselines.logistic import ModelConfig  # noqa: E402
from quantumattack.baselines.splits import SplitConfig  # noqa: E402
from quantumattack.baselines.warnings import WarningPolicy  # noqa: E402
from quantumattack.baselines.conventional import ThresholdPolicy  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Feature ablation A/B/C/D")
    parser.add_argument("--data", default="data/phase1")
    parser.add_argument("--features", default="artifacts/phase2/features")
    parser.add_argument("--out", default="artifacts/phase2/ablation")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = {}
    for group in ("A", "B", "C", "D"):
        res = run_evaluation(
            data_dir=Path(args.data),
            features_dir=Path(args.features),
            out_dir=out_dir / group,
            model_config=ModelConfig(feature_group=group),
            split_config=SplitConfig(seed=args.seed),
            warning_policy=WarningPolicy(),
            threshold_policy=ThresholdPolicy(),
            experiment_id=f"phase2-ablation-{group}",
        )
        results[group] = {
            "horizon_metrics": {str(h): {k: m[k] for k in ("auroc", "auprc", "brier")}
                                for h, m in res.horizon_metrics.items()},
            "lead_time_summary": res.lead_time_summary,
            "false_warning_rates": res.false_warning_rates,
        }
        print(f"== group {group} ==")
        for h, m in res.horizon_metrics.items():
            print(f"  H={h}: AUROC={m['auroc'] if m['auroc'] is None else round(m['auroc'],4)} "
                  f"AUPRC={m['auprc'] if m['auprc'] is None else round(m['auprc'],4)} "
                  f"Brier={m['brier'] if m['brier'] is None else round(m['brier'],4)}")
        for atype, s in res.lead_time_summary.items():
            print(f"  {atype}: success={s['warning_success_rate']:.2f} median={s['median_lead_blocks']}")

    (out_dir / "ablation_summary.json").write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"wrote {out_dir / 'ablation_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
