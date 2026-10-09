"""Phase 5 dataset tests (docs/phase5-protocol.md; Phase 5 prompt §5/§6).

Validates:
- Seed-pool disjointness (all Phase 5 seeds >= 20000, strictly disjoint from Phase 4)
- Partition count matches pre-registered protocol: G1=60, G2=40, G3=30, G4=30
- Scenario configuration validity (ProtocolConfig, ChannelConfig, EnvironmentConfig, AttackConfig)
- Manifest integrity when data/phase5 exists
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]


def _load_batch():
    return yaml.safe_load((REPO / "configs" / "simulation" / "phase5.yaml").read_text(encoding="utf-8"))


def test_phase5_config_expansion():
    """Verify expansion to exactly 160 scenarios across partitions G1..G4."""
    from quantumattack.simulator.generate import build_scenario_configs

    batch = _load_batch()
    cfgs = build_scenario_configs(batch)
    assert len(cfgs) == 160
    seeds = [c.seed for c in cfgs]
    assert len(set(seeds)) == len(seeds), "seed reused across scenarios"
    # Seed disjointness from Phase 4
    assert min(seeds) >= 20000, "Phase 5 seed overlaps with Phase 4 (<20000)"


def test_phase5_partition_counts():
    """Verify G1=60, G2=40, G3=30, G4=30."""
    from quantumattack.simulator.generate import build_scenario_configs
    from collections import Counter

    cfgs = build_scenario_configs(_load_batch())
    counts = Counter(getattr(c, "partition", "") for c in cfgs)
    assert counts["g1"] == 60
    assert counts["g2"] == 40
    assert counts["g3"] == 30
    assert counts["g4"] == 30


def test_phase5_configs_valid():
    """Every generated ScenarioConfig passes strict validation."""
    from quantumattack.simulator.generate import build_scenario_configs

    cfgs = build_scenario_configs(_load_batch())
    for c in cfgs:
        c.validate()
        c.protocol.validate()
        c.channel.validate()
        c.environment.validate()
        c.attack.validate(c.n_blocks)


@pytest.mark.skipif(not (REPO / "data" / "phase5" / "manifest.json").exists(),
                    reason="data/phase5 not yet generated")
def test_phase5_manifest_integrity():
    """Verify generated data/phase5 matches scenario count and schema."""
    m = json.loads((REPO / "data" / "phase5" / "manifest.json").read_text(encoding="utf-8"))
    assert len(m["scenarios"]) == 160
    for s in m["scenarios"]:
        pfile = REPO / "data" / "phase5" / f"{s['scenario_id']}.parquet"
        assert pfile.exists(), f"missing parquet for {s['scenario_id']}"
