"""Baseline evaluation harness (master prompt §26-§36, §44).

Runs the full Phase 2 evaluation: train forecaster → predict → warning policy →
lead-time/false-warning/conventional comparison → metrics + experiment manifest.

Outputs to artifacts/phase2/ (predictions, metrics, manifest) — generated
artifacts, git-ignored unless intentionally versioned.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ..features import FEATURE_SCHEMA_VERSION, derived_feature_names
from ..feature_config import FeatureConfig
from .. import __version__ as PACKAGE_VERSION
from ..baselines.logistic import (
    ModelConfig, train_forecaster, predict_frames, feature_group_columns,
    base_feature_columns,
)
from ..baselines.splits import SplitConfig, split_scenarios, pair_isolation_check
from ..baselines.warnings import (
    WarningPolicy, evaluate_scenario_warnings, false_early_warning_rate,
    summarize_lead_times, warning_category,
)
from ..baselines.conventional import (
    ThresholdPolicy, calibrate_thresholds, detect_warnings,
    conventional_lead_time, lead_time_ms, INDICATORS,
)


# ---------------------------------------------------------------------------
# Forecasting metrics (master prompt §28)
# ---------------------------------------------------------------------------
def classification_metrics(y_true: np.ndarray, p: np.ndarray, threshold: float = 0.5) -> dict:
    """AUROC, AUPRC, precision, recall, F1, Brier at a fixed threshold."""
    from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss

    y_pred = (p >= threshold).astype(int)
    out: dict = {
        "n": int(len(y_true)),
        "n_positive": int(y_true.sum()),
        "auroc": None, "auprc": None, "precision": None, "recall": None,
        "f1": None, "brier": None,
    }
    if len(np.unique(y_true)) < 2:
        return out  # undefined metrics on single-class data; reported as null
    out["auroc"] = float(roc_auc_score(y_true, p))
    out["auprc"] = float(average_precision_score(y_true, p))
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    out["precision"] = float(tp / (tp + fp)) if tp + fp > 0 else None
    out["recall"] = float(tp / (tp + fn)) if tp + fn > 0 else None
    if out["precision"] and out["recall"] and (out["precision"] + out["recall"]) > 0:
        out["f1"] = float(2 * out["precision"] * out["recall"] / (out["precision"] + out["recall"]))
    out["brier"] = float(brier_score_loss(y_true, p))
    return out


def calibration_error(y_true: np.ndarray, p: np.ndarray, n_bins: int = 10) -> dict:
    """Reliability-diagram data + expected calibration error (ECE).

    Calibration is separate from discrimination (master prompt §27).
    """
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(p, bins) - 1, 0, n_bins - 1)
    reliability = []
    ece = 0.0
    for b in range(n_bins):
        mask = idx == b
        if mask.sum() == 0:
            continue
        conf = float(p[mask].mean())
        acc = float(y_true[mask].mean())
        reliability.append({"bin": b, "mean_p": conf, "empirical_rate": acc, "count": int(mask.sum())})
        ece += (mask.sum() / len(p)) * abs(conf - acc)
    return {"ece": float(ece), "reliability": reliability}


# ---------------------------------------------------------------------------
# Full harness
# ---------------------------------------------------------------------------
@dataclass
class HarnessResult:
    predictions: pd.DataFrame
    horizon_metrics: dict[int, dict]
    lead_time_summary: dict
    conventional_summary: dict
    false_warning_rates: dict
    split: object
    manifest: dict


def run_evaluation(
    data_dir: Path,
    features_dir: Path,
    out_dir: Path,
    model_config: ModelConfig | None = None,
    split_config: SplitConfig | None = None,
    warning_policy: WarningPolicy | None = None,
    threshold_policy: ThresholdPolicy | None = None,
    experiment_id: str = "phase2-baseline",
) -> HarnessResult:
    """Complete Phase 2 evaluation over a Phase 1 dataset.

    Pipeline (master prompt §57): scenario telemetry → schema validation →
    causal features → restricted-column validation → scenario-level split →
    train-only scaling → forecast model → probability predictions → warning
    policy → warning timestamps → lead-time evaluation → attack-specific analysis
    → conventional comparison → experiment report.
    """
    mc = model_config or ModelConfig()
    sc = split_config or SplitConfig()
    wp = warning_policy or WarningPolicy()
    tp = threshold_policy or ThresholdPolicy()

    import pandas as pd

    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    entries = manifest["scenarios"]

    # load FEATURE frames if precomputed, else raw (compute features here)
    frames: dict[str, pd.DataFrame] = {}
    for s in entries:
        fpath = features_dir / f"{s['scenario_id']}.parquet"
        if fpath.exists():
            frames[s["scenario_id"]] = pd.read_parquet(fpath)
        else:
            frames[s["scenario_id"]] = pd.read_parquet(data_dir / f"{s['scenario_id']}.parquet")

    # split (scenario-level; pairs isolated)
    split = split_scenarios(entries, sc)
    pair_isolation_check(split, entries)

    # train forecaster (train-only scaling inside)
    models = train_forecaster(frames, split, mc)

    # predict on val + test (never overwrite raw predictions)
    eval_ids = split.val + split.test
    preds = predict_frames(frames, eval_ids, models, mc)
    preds["split"] = preds["scenario_id"].map(lambda s: split.contains(s))
    preds["model_version"] = PACKAGE_VERSION
    preds["feature_schema_version"] = FEATURE_SCHEMA_VERSION

    # per-horizon metrics on TEST only (master prompt §25: test = final evaluation)
    horizon_metrics: dict[int, dict] = {}
    test_preds = preds[preds["split"] == "test"]
    for h in mc.horizons:
        y = test_preds[f"y_true_h{h}"].to_numpy()
        p = test_preds[f"p_attack_future_h{h}"].to_numpy()
        m = classification_metrics(y, p)
        m.update(calibration_error(y, p))
        m["warning_rate_scenarios"] = _scenario_warning_rate(test_preds, h, wp)
        horizon_metrics[h] = m

    # per-scenario warning evaluation on TEST
    warning_results: list = []
    for sid in split.test:
        df_s = test_preds[test_preds["scenario_id"] == sid]
        if df_s.empty:
            continue
        for h in mc.horizons:
            warning_results.append(evaluate_scenario_warnings(df_s, h, wp))

    lt_summary = summarize_lead_times(warning_results, category_filter="anticipatory")
    # pair-gated attribution (Phase 2 gate, master prompt §53): warnings whose matched
    # benign twin fired identically are NOT attack anticipation (observed artifact on
    # intercept-resend). Attributed summary counts only benign-twin-confirmed warnings.
    from ..baselines.warnings import attribute_warnings, summarize_lead_times_attributed

    h_max = max(mc.horizons)
    attributed = attribute_warnings(warning_results, warning_results, h_max)
    lt_attributed = summarize_lead_times_attributed(warning_results, warning_results, h_max, attributed)
    fwr = false_early_warning_rate(warning_results)
    fwr_attributed = false_early_warning_rate(list(attributed.values()))

    # conventional detector: calibrate on benign TRAIN portions only (master prompt §14)
    benign_train = [sid for sid in split.train if not sid.startswith("attack-")]
    ref_frames = [frames[sid] for sid in benign_train if sid in frames]
    ref_df = pd.concat(ref_frames, ignore_index=True) if ref_frames else None
    conventional_summary: dict = {}
    if ref_df is not None:
        calibration = calibrate_thresholds(ref_df, tp)
        conv_rows = []
        for sid in split.test:
            df_s = frames[sid]
            det = detect_warnings(df_s, calibration, tp)
            onset = int(df_s["attack_onset"].iloc[0])
            lt = conventional_lead_time(onset if onset >= 0 else None, det["warning_blocks"])
            conv_rows.append({
                "scenario_id": sid,
                "attack_type": str(df_s["attack_type"].iloc[0]),
                "scenario_class": str(df_s["scenario_class"].iloc[0]),
                "warning_blocks": det["warning_blocks"],
                "warning_time": None if not det["warning_blocks"] else float(det["warning_blocks"][0]),
                "lead_time_blocks": lt,
                "lead_time_ms": lead_time_ms(lt),
                "n_warnings": len(det["warning_blocks"]),
                "category": warning_category(lt, wp.grace_blocks) if onset >= 0 else (
                    "none" if not det["warning_blocks"] else "false_early_warning"),
            })
        conventional_summary = {
            "threshold_method": calibration.method,
            "thresholds": calibration.thresholds,
            "per_indicator_stats": calibration.per_indicator_stats,
            "scenarios": conv_rows,
            "lead_time_summary": _conventional_lead_summary(conv_rows),
            "false_early_warning_rate": _conv_fwr(conv_rows),
        }

    # forecast-vs-conventional comparison (master prompt §36)
    comparison = _compare_forecast_conventional(warning_results, conventional_summary)

    # experiment manifest (master prompt §44)
    out_dir.mkdir(parents=True, exist_ok=True)
    experiment_manifest = {
        "experiment_id": experiment_id,
        "phase": 2,
        "dataset": str(data_dir),
        "dataset_manifest": {"schema_version": manifest["schema_version"],
                             "n_scenarios": len(entries)},
        "feature_schema": FEATURE_SCHEMA_VERSION,
        "feature_group": mc.feature_group,
        "n_derived_features": len(derived_feature_names()),
        "split": {"train": split.train, "val": split.val, "test": split.test,
                  "config": sc.to_dict()},
        "model": mc.to_dict(),
        "warning_policy": wp.to_dict(),
        "threshold_policy": {"method": tp.threshold_method,
                             "persistence_k": tp.persistence_k,
                             "cooldown_blocks": tp.cooldown_blocks,
                             "sigma_multiplier": tp.sigma_multiplier},
        "package_version": PACKAGE_VERSION,
        "created_at": str(pd.Timestamp.now()),
    }
    (out_dir / "experiment_manifest.json").write_text(
        json.dumps(experiment_manifest, indent=2, default=str), encoding="utf-8")
    preds.to_parquet(out_dir / "predictions.parquet", index=False)
    (out_dir / "metrics.json").write_text(
        json.dumps({
            "horizon_metrics": {str(k): v for k, v in horizon_metrics.items()},
            "lead_time_summary": lt_summary,
            "lead_time_summary_attributed": lt_attributed,
            "false_early_warning_rates": fwr,
            "false_early_warning_rates_attributed": fwr_attributed,
            "conventional_summary": {
                "threshold_method": conventional_summary.get("threshold_method"),
                "lead_time_summary": conventional_summary.get("lead_time_summary"),
                "false_early_warning_rate": conventional_summary.get("false_early_warning_rate"),
                "thresholds": conventional_summary.get("thresholds"),
            },
            "forecast_vs_conventional": comparison,
        }, indent=2, default=str), encoding="utf-8")

    return HarnessResult(preds, horizon_metrics, lt_summary, conventional_summary,
                         fwr, split, experiment_manifest)


def _scenario_warning_rate(test_preds: pd.DataFrame, horizon: int, wp: WarningPolicy) -> float | None:
    """Fraction of ATTACK test scenarios where the warning policy fires pre-onset."""
    rates = []
    for sid, df_s in test_preds.groupby("scenario_id"):
        if str(df_s["attack_type"].iloc[0]) == "none":
            continue
        from ..baselines.warnings import warning_blocks_for_scenario

        fires = warning_blocks_for_scenario(df_s, horizon, wp)
        onset = int(df_s["attack_onset"].iloc[0])
        # pre-onset warning = first fire strictly before onset
        rates.append(1 if any(f < onset for f in fires) else 0)
    return sum(rates) / len(rates) if rates else None


def _conventional_lead_summary(conv_rows: list[dict]) -> dict:
    by_type: dict[str, list[float]] = {}
    total: dict[str, int] = {}
    for r in conv_rows:
        if r["scenario_class"] != "ATTACK":
            continue
        total[r["attack_type"]] = total.get(r["attack_type"], 0) + 1
        if r["lead_time_blocks"] is not None and r["category"] == "anticipatory":
            by_type.setdefault(r["attack_type"], []).append(r["lead_time_blocks"])
    out: dict[str, dict] = {}
    for atype, n in total.items():
        leads = by_type.get(atype, [])
        out[atype] = {
            "n_scenarios": n, "n_successful_warnings": len(leads),
            "warning_success_rate": len(leads) / n,
            "median_lead_blocks": float(np.median(leads)) if leads else None,
            "mean_lead_blocks": float(np.mean(leads)) if leads else None,
        }
    return out


def _conv_fwr(conv_rows: list[dict]) -> dict[str, float]:
    out: dict[str, float] = {}
    for cls in ("NORMAL", "BENIGN_DRIFT"):
        rows = [r for r in conv_rows if r["scenario_class"] == cls]
        if rows:
            out[cls] = sum(1 for r in rows if r["n_warnings"] > 0) / len(rows)
    return out


def _compare_forecast_conventional(
    warning_results: list, conventional_summary: dict
) -> dict:
    """Per-attack-type: does forecasting add warning BEFORE conventional detection?
    (master prompt §36: not "does ML have higher accuracy")."""
    conv_by_key = {}
    for r in conventional_summary.get("scenarios", []):
        conv_by_key[(r["scenario_id"])] = r
    added = 0
    both = 0
    per_type: dict[str, dict] = {}
    for wr in warning_results:
        if wr.horizon != 100:  # compare at the longest horizon (most warning opportunity)
            continue
        cr = conv_by_key.get(wr.scenario_id)
        if cr is None:
            continue
        if wr.scenario_class != "ATTACK":
            continue
        atype = wr.attack_type
        entry = per_type.setdefault(atype, {"n": 0, "forecast_earlier": 0, "conventional_earlier": 0,
                                            "median_gain_blocks": None})
        entry["n"] += 1
        flt, clt = wr.lead_time_blocks, cr["lead_time_blocks"]
        if flt is None and clt is None:
            continue
        if flt is not None and clt is None:
            entry["forecast_earlier"] += 1
            continue
        if flt is None and clt is not None:
            entry["conventional_earlier"] += 1
            continue
        both += 1
        gain = clt - flt  # positive: forecast warned EARLIER than conventional
        entry["_gains"] = entry.get("_gains", []) + [gain]
        if gain > 0:
            entry["forecast_earlier"] += 1
        elif gain < 0:
            entry["conventional_earlier"] += 1
    for atype, entry in per_type.items():
        gains = entry.pop("_gains", [])
        entry["median_gain_blocks"] = float(np.median(gains)) if gains else None
        entry["median_gain_ms"] = entry["median_gain_blocks"] * 10.0 if gains else None
    return {"at_horizon": 100, "per_attack_type": per_type,
            "n_both_warned": both}
