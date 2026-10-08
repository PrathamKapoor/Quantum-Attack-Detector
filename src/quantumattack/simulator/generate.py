"""CLI entry: generate a Phase 1 validation dataset (master prompt §35).

Usage:
    python -m quantumattack.simulator.generate --config configs/simulation/phase1.yaml --out data/phase1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
elif "src" not in sys.path[0]:
    # running with -m from repo root without installation: make src importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from quantumattack.simulator.config import ScenarioConfig  # noqa: E402
from quantumattack.simulator.scenario import run_scenario  # noqa: E402
from quantumattack.simulator.export.parquet import export_batch  # noqa: E402


def load_config(path: Path) -> dict:
    """Load scenario batch config from YAML (PyYAML) or JSON."""
    if path.suffix in (".yaml", ".yml"):
        import yaml

        return yaml.safe_load(path.read_text(encoding="utf-8"))
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def build_scenario_configs(batch: dict) -> list[ScenarioConfig]:
    """Expand a batch spec into validated ScenarioConfigs.

    Batch spec keys:
      seeds: list[int]
      n_blocks: int
      horizons: list[int]
      scenarios: list of {class: normal|benign_drift|attack, attack: {...}|null,
                          pair: bool}
    """
    seeds = batch["seeds"]
    n_blocks = batch.get("n_blocks", 2000)
    horizons = tuple(batch.get("horizons", [10, 25, 50, 100]))
    configs: list[ScenarioConfig] = []

    for spec in batch["scenarios"]:
        kind = spec.get("class", "normal")
        make_pair = spec.get("pair", False)
        attack_dict = spec.get("attack") or {"attack_type": "none"}

        for seed in seeds:
            pair_id = ""
            arm = ""
            env = _env_from_dict(spec.get("env"))
            env_kwargs = {"environment": env} if env is not None else {}
            if make_pair:
                pair_id = f"pair-{len(configs) // 2 + 1:03d}-{spec.get('name', kind)}"
                arm = "attack"
                # Run A: matched benign run (same seed, same benign trajectory)
                configs.append(ScenarioConfig(
                    scenario_id=f"normal-{spec.get('name', kind)}-s{seed}",
                    seed=seed, n_blocks=n_blocks, horizons=horizons,
                    pair_id=pair_id, arm="normal", **env_kwargs,
                ))
            configs.append(ScenarioConfig(
                scenario_id=f"{kind}-{spec.get('name', attack_dict.get('attack_type', 'x'))}-s{seed}",
                seed=seed, n_blocks=n_blocks, horizons=horizons,
                attack=_attack_from_dict(attack_dict, n_blocks),
                pair_id=pair_id, arm=arm, **env_kwargs,
            ))
    return configs


def _attack_from_dict(d: dict, n_blocks: int):
    from dataclasses import fields as _fields

    from .config import AttackConfig

    valid = {f.name for f in _fields(AttackConfig)}
    kwargs = {k: v for k, v in d.items() if k in valid}
    return AttackConfig(**kwargs)


def _env_from_dict(d: dict | None):
    if not d:
        return None
    from dataclasses import fields as _fields

    from .config import EnvironmentConfig

    valid = {f.name for f in _fields(EnvironmentConfig)}
    kwargs = {k: v for k, v in d.items() if k in valid}
    return EnvironmentConfig(**kwargs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Phase 1 validation dataset")
    parser.add_argument("--config", required=True, help="path to batch config YAML/JSON")
    parser.add_argument("--out", required=True, help="output directory")
    args = parser.parse_args(argv)

    batch = load_config(Path(args.config))
    configs = build_scenario_configs(batch)
    results = []
    for cfg in configs:
        results.append(run_scenario(cfg))
        print(f"ran {cfg.scenario_id}: {len(results[-1].records)} blocks, "
              f"class={results[-1].metadata['scenario_class']}")
    manifest = export_batch(results, Path(args.out), batch_config=batch)
    print(f"exported {len(results)} scenarios; manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
