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


def _sample_range(spec_value, rng) -> object:
    """Sample a parameter from [lo, hi] (uniform) or return the fixed value."""
    if isinstance(spec_value, (list, tuple)) and len(spec_value) == 2 \
            and all(isinstance(v, (int, float)) for v in spec_value):
        return float(rng.uniform(spec_value[0], spec_value[1]))
    if isinstance(spec_value, list) and len(spec_value) == 1:
        return spec_value[0]
    return spec_value


def build_scenario_configs(batch: dict) -> list[ScenarioConfig]:
    """Expand a batch spec into validated ScenarioConfigs.

    Batch spec keys:
      seeds: list[int]                      (simple expansion, Phase 1/2 style)
      attack_seeds / benign_seeds: list[int] (unpaired expansion, Phase 3 style)
      n_blocks: int
      horizons: list[int]
      scenarios: list of {class, name, attack: {...}, pair: bool,
                          sample: {param: [lo, hi] | [fixed]}}   (per-scenario
                          parameter sampling — deterministic per scenario seed)
    """
    if "seeds" in batch:
        seeds = batch["seeds"]
    else:
        seeds = None  # unpaired mode: attack/benign seed lists per class
    n_blocks = batch.get("n_blocks", 2000)
    horizons = tuple(batch.get("horizons", [10, 25, 50, 100]))
    configs: list[ScenarioConfig] = []

    import numpy as np

    for spec in batch["scenarios"]:
        kind = spec.get("class", "normal")
        make_pair = spec.get("pair", False)
        attack_dict = spec.get("attack") or {"attack_type": "none"}
        if "attack" not in spec and kind == "attack":
            # unpaired mode (Phase 3): attack_type derived from the scenario name
            # (name → attack taxonomy id); sample keys carry the parameters
            name_to_type = {
                "intercept-resend": "intercept_resend",
                "lo-manipulation": "lo_manipulation",
                "calibration-manipulation": "calibration_manipulation",
                "channel-jamming-probes": "channel_jamming",
                "channel-jamming-sudden": "channel_jamming",
            }
            attack_dict = {"attack_type": name_to_type[spec["name"]]}
            if spec["name"] == "channel-jamming-sudden":
                attack_dict["probe_enabled"] = False
            if spec["name"] == "channel-jamming-probes":
                attack_dict["probe_enabled"] = True
        sample_spec = spec.get("sample") or {}
        onset_range = spec.get("sample_onset")

        # seed pool for this spec: paired/simple mode uses `seeds`; unpaired mode
        # uses attack_seeds for attack scenarios, benign_seeds for benign
        if seeds is not None:
            pool = seeds
        else:
            pool = batch["attack_seeds"] if kind == "attack" and attack_dict.get("attack_type", "none") != "none" \
                else batch["benign_seeds"]

        for seed in pool:
            # deterministic per-scenario parameter sampling (derived from scenario seed)
            import hashlib

            digest = int.from_bytes(hashlib.sha256(f"{seed}:{spec.get('name')}".encode()).digest()[:8], "big")
            srng = np.random.default_rng(digest)
            sampled = {k: _sample_range(v, srng) for k, v in sample_spec.items()}
            if onset_range:
                sampled["onset_block"] = int(srng.integers(onset_range[0], onset_range[1]))
            attack_kwargs = {**{k: v for k, v in attack_dict.items() if k != "attack_type"},
                             **sampled}
            attack_cfg = _attack_from_dict({"attack_type": attack_dict.get("attack_type", "none"), **attack_kwargs}, n_blocks)

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
                attack=attack_cfg,
                pair_id=pair_id, arm=arm, **env_kwargs,
            ))
    return configs


def _attack_from_dict(d: dict, n_blocks: int):
    from dataclasses import fields as _fields

    from .config import AttackConfig

    valid = {f.name for f in _fields(AttackConfig)}
    kwargs = {k: v for k, v in d.items() if k in valid}
    # int fields: sampled parameters arrive as floats (U[lo,hi]) — cast where the
    # dataclass declares int (probe_lambda stays float: Poisson mean)
    int_fields = {f.name for f in _fields(AttackConfig) if f.type == "int" or f.type == "int | None"}
    for k in int_fields & set(kwargs):
        if kwargs[k] is not None:
            kwargs[k] = int(kwargs[k])
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
