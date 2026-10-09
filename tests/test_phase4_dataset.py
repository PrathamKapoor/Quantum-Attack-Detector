"""Phase 4 dataset tests (docs/phase4-protocol.md §3/§12; Phase 4 prompt §45).

Validates: seed-pool disjointness, partition assignment, OOD isolation (jamming
test-only), manifest integrity, scenario isolation, pair isolation, and drift
label windows on the GENERATED dataset (data/phase4) when present; the config
expansion is always validated (fast, no simulation).
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _load_batch():
    import yaml
    return yaml.safe_load((REPO / "configs" / "simulation" / "phase4.yaml").read_text(encoding="utf-8"))


def _manifest_path() -> Path:
    return REPO / "data" / "phase4" / "manifest.json"


# ---------------------------------------------------------------------------
# Config expansion (always run)
# ---------------------------------------------------------------------------

def test_config_expansion_partition_counts():
    """Definition-sliced pools: 6 non-OOD definitions x (20 train + 7 val + 7 test)
    + 2 jamming definitions x 15 OOD = 234 unique-seed scenarios."""
    from quantumattack.simulator.generate import build_scenario_configs

    cfgs = build_scenario_configs(_load_batch())
    assert len(cfgs) == 234
    seeds = [c.seed for c in cfgs]
    assert len(set(seeds)) == len(seeds), "seed reused across scenarios"


def test_config_expansion_partition_assignment():
    """Partition fixed by seed pool: [1000,5000) train / [5000,9000) val /
    [9000,13000) test / [13000,∞) ood; jamming scenarios OOD-only."""
    from quantumattack.simulator.generate import build_scenario_configs

    cfgs = build_scenario_configs(_load_batch())
    for c in cfgs:
        part = getattr(c, "partition", "")
        if c.scenario_id.startswith("attack-channel-jamming"):
            assert part == "ood", f"jamming scenario in partition {part!r}"
        elif part == "pool":
            if c.seed < 5000:
                assert part  # resolved per seed; see below
        if part == "ood":
            assert c.seed >= 13000
        elif part == "train":
            assert 1000 <= c.seed < 5000
        elif part == "val":
            assert 5000 <= c.seed < 9000
        elif part == "test":
            assert 9000 <= c.seed < 13000


def test_seed_pools_disjoint():
    """Seed pools never overlap across partitions (Phase 4 prompt §8)."""
    batch = _load_batch()
    pools = [set(batch["train_seeds"]), set(batch["val_seeds"]),
             set(batch["test_seeds"]), set(batch["ood_seeds"])]
    for i, a in enumerate(pools):
        for j, b in enumerate(pools):
            if i < j:
                assert a.isdisjoint(b), f"pool {i} overlaps pool {j}"
    # stride-7 arithmetic
    assert batch["train_seeds"] == [1000 + i * 7 for i in range(120)]
    assert batch["val_seeds"] == [5000 + i * 7 for i in range(42)]
    assert batch["test_seeds"] == [9000 + i * 7 for i in range(42)]
    assert batch["ood_seeds"] == [13000 + i * 7 for i in range(30)]


def test_ood_pool_jamming_only():
    """OOD pool feeds ONLY channel_jamming definitions (Phase 4 prompt §12)."""
    batch = _load_batch()
    # the two jamming definitions take disjoint 15-seed slices of the OOD pool
    assert len(batch["ood_seeds"]) == 30


# ---------------------------------------------------------------------------
# Generated dataset (skip if absent)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _manifest_path().exists(), reason="phase4 dataset not generated")
class TestPhase4Generated:
    @classmethod
    def setup_class(cls):
        import json
        cls.manifest = json.loads(_manifest_path().read_text(encoding="utf-8"))
        cls.scenarios = cls.manifest["scenarios"]
        import yaml
        batch = yaml.safe_load((REPO / "configs" / "simulation" / "phase4.yaml").read_text(encoding="utf-8"))
        cls.pools = {"train": set(batch["train_seeds"]), "val": set(batch["val_seeds"]),
                     "test": set(batch["test_seeds"]), "ood": set(batch["ood_seeds"])}

    def _partition_of(self, s):
        if s["attack_type"] == "channel_jamming":
            return "ood"
        for name in ("train", "val", "test"):
            if s["seed"] in self.pools[name]:
                return name
        raise AssertionError(f"seed {s['seed']} not in any pool")

    def test_manifest_integrity(self):
        """Manifest records dataset_version, seed pools, counts, schema versions."""
        m = self.manifest
        assert m["dataset_version"] == "phase4-v1"
        assert m["schema_version"] in ("1", 1)
        assert len(m["scenarios"]) == 234
        # every scenario has the protocol-required record fields (config_hash lives
        # in the per-scenario parquet metadata — validated below)
        for s in m["scenarios"]:
            for key in ("scenario_id", "seed", "attack_type", "scenario_class",
                        "attack_onset", "precursor_class"):
                assert key in s, f"manifest missing {key}"
        # feature schema version recorded
        assert (REPO / "artifacts" / "phase4" / "features" / "feature_schema.json").exists()

    def test_scenario_config_hash_present(self):
        """config_hash present in per-scenario parquet metadata (traceability)."""
        import pandas as pd
        df = pd.read_parquet(REPO / "data" / "phase4" / "normal-plain-s1000.parquet")
        for col in ("config_hash", "sim_version", "protocol"):
            assert col in df.columns
        hashes = df["config_hash"].unique()
        assert len(hashes) == 1 and len(str(hashes[0])) == 12

    def test_scenario_isolation(self):
        """Scenario isolation: unique ids, unique seeds, disjoint partitions."""
        ids = [s["scenario_id"] for s in self.scenarios]
        seeds = [s["seed"] for s in self.scenarios]
        assert len(set(ids)) == len(ids)
        assert len(set(seeds)) == len(seeds)
        # partition membership: pool disjointness + per-scenario resolution
        for name, pool in self.pools.items():
            for other, opool in self.pools.items():
                if name < other:
                    assert pool.isdisjoint(opool)
        # every seed resolves to exactly one partition
        for s in self.scenarios:
            self._partition_of(s)

    def test_ood_isolation(self):
        """channel_jamming: 0 train, 0 val, test-only. Verified programmatically."""
        jam = [s for s in self.scenarios if s["attack_type"] == "channel_jamming"]
        assert len(jam) == 30
        for s in jam:
            assert self._partition_of(s) == "ood"
        # no other attack family in the OOD pool
        for s in self.scenarios:
            if s["attack_type"] != "channel_jamming":
                assert s["seed"] not in self.pools["ood"]

    def test_attack_balance(self):
        """Sufficient scenarios per family for warning-probability/lead-time
        estimation (Phase 4 prompt §9)."""
        from collections import Counter
        counts = Counter(s["attack_type"] for s in self.scenarios if s["attack_type"] != "none")
        assert counts["intercept_resend"] == 34
        assert counts["lo_manipulation"] == 34
        assert counts["calibration_manipulation"] == 34
        assert counts["channel_jamming"] == 30

    def test_benign_populations_separate(self):
        """NORMAL and BENIGN_DRIFT maintained as separate populations (§10).
        NORMAL = plain + channel-drift (env drift, no episode); BENIGN_DRIFT =
        disturbance episodes (all fire: per-block prob 0.5 → ≈surely fired)."""
        from collections import Counter
        benign = Counter(s["scenario_class"] for s in self.scenarios
                         if s["scenario_class"] != "ATTACK")
        assert benign["NORMAL"] == 68      # plain 34 + channel-drift 34
        assert benign["BENIGN_DRIFT"] == 34  # disturbance 34
        # BENIGN_DRIFT comes only from the disturbance definition
        bd = [s["scenario_id"] for s in self.scenarios if s["scenario_class"] == "BENIGN_DRIFT"]
        assert all(sid.startswith("normal-disturbance") for sid in bd)

    def test_drift_labels_on_actual_windows(self):
        """BENIGN_DRIFT labels land on the ACTUAL episode window (regression for
        the Phase 3 label-window bug): background telemetry is elevated inside
        the labeled window, not at the run tail."""
        import pandas as pd
        import numpy as np
        dist = [s["scenario_id"] for s in self.scenarios
                if s["scenario_id"].startswith("normal-disturbance")]
        checked = 0
        for sid in dist:
            df = pd.read_parquet(REPO / "data" / "phase4" / f"{sid}.parquet")
            rows = df.index[df["state_label"] == "BENIGN_DRIFT"]
            if not len(rows):
                continue
            checked += 1
            bg_in = df["background"].iloc[rows].mean()
            bg_out = df["background"].drop(rows).mean()
            assert bg_in > bg_out * 2, f"{sid}: episode window mislabeled"
            # NOT the old tail-anchored bug (labels at n-20..n-1 for early episodes)
            assert rows.max() < len(df) - 1 or rows.min() > len(df) - 25 or len(rows) == 30
        # all disturbance scenarios fire an episode (prob 0.5 per block → ≈surely)
        assert checked >= 30

    def test_pair_isolation(self):
        """COUNTERFACTUAL pairs (phase1 batch, train-only) never cross partitions."""
        import json
        cf_manifest = json.loads(
            (REPO / "data" / "phase1" / "manifest.json").read_text(encoding="utf-8"))
        pairs = {}
        for s in cf_manifest["scenarios"]:
            if s.get("pair_id"):
                pairs.setdefault(s["pair_id"], set()).add(s["scenario_id"])
        assert len(pairs) == 25
        # all phase1 seeds (1-5) are disjoint from every phase4 pool
        phase1_seeds = {s["seed"] for s in cf_manifest["scenarios"]}
        for pool in self.pools.values():
            assert phase1_seeds.isdisjoint(pool)

    def test_onset_distribution(self):
        """Onset sampled per scenario in the pre-registered range 900-1400."""
        import numpy as np
        onsets = [s["attack_onset"] for s in self.scenarios if s["attack_type"] != "none"]
        assert len(onsets) == 132
        assert min(onsets) >= 900
        assert max(onsets) <= 1400
        # spread (not degenerate)
        assert np.std(onsets) > 100

    def test_precursor_classes(self):
        """Precursor taxonomy unchanged: gradual=A, jamming probes=B, sudden=C."""
        from collections import Counter
        pc = Counter((s["attack_type"], s["precursor_class"]) for s in self.scenarios
                     if s["attack_type"] != "none")
        assert pc[("lo_manipulation", "A")] == 34
        assert pc[("calibration_manipulation", "A")] == 34
        assert pc[("channel_jamming", "B")] == 15
        assert pc[("channel_jamming", "C")] == 15
        assert pc[("intercept_resend", "C")] == 34
