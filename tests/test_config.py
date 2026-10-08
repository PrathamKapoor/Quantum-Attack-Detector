"""Configuration tests (master prompt §48): valid accepted, invalid rejected."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantumattack.simulator.config import (  # noqa: E402
    ScenarioConfig, AttackConfig, ProtocolConfig, ChannelConfig, EnvironmentConfig,
)


def test_valid_config_accepted():
    cfg = ScenarioConfig(scenario_id="ok", seed=1)
    cfg.validate()  # must not raise
    cfg2 = ScenarioConfig(
        scenario_id="ok2", seed=0, n_blocks=500,
        attack=AttackConfig(attack_type="intercept_resend", onset_block=100),
    )
    cfg2.validate()


def test_invalid_attack_type_rejected():
    with pytest.raises(ValueError, match="unknown attack_type"):
        ScenarioConfig(
            scenario_id="bad", seed=1,
            attack=AttackConfig(attack_type="teleport_the_key", onset_block=10),
        ).validate()


def test_onset_outside_duration_rejected():
    with pytest.raises(ValueError, match="outside scenario duration"):
        ScenarioConfig(
            scenario_id="bad", seed=1, n_blocks=200,
            attack=AttackConfig(attack_type="intercept_resend", onset_block=200),
        ).validate()
    with pytest.raises(ValueError, match="outside scenario duration"):
        ScenarioConfig(
            scenario_id="bad", seed=1, n_blocks=200,
            attack=AttackConfig(attack_type="lo_manipulation", onset_block=-5),
        ).validate()


def test_negative_physical_parameters_rejected():
    with pytest.raises(ValueError, match="cannot be negative"):
        ChannelConfig(attenuation_db_per_km=-0.2).validate()
    with pytest.raises(ValueError, match="cannot be negative"):
        ProtocolConfig(electronic_noise_snu=-0.1).validate()
    with pytest.raises(ValueError, match="cannot be negative"):
        EnvironmentConfig(temperature_mean_c=-1.0).validate()


def test_probability_ranges_rejected():
    with pytest.raises(ValueError):
        AttackConfig(attack_type="intercept_resend", onset_block=10, tap_fraction=1.5).validate(100)
    with pytest.raises(ValueError):
        AttackConfig(attack_type="intercept_resend", onset_block=10, tap_fraction=0.0).validate(100)
    with pytest.raises(ValueError):
        ProtocolConfig(det_efficiency=0.0).validate()
    with pytest.raises(ValueError):
        ProtocolConfig(recon_efficiency=1.5).validate()


def test_horizon_validation():
    with pytest.raises(ValueError, match="horizons"):
        ScenarioConfig(scenario_id="bad", seed=1, n_blocks=100, horizons=(0,)).validate()
    with pytest.raises(ValueError, match="horizons"):
        ScenarioConfig(scenario_id="bad", seed=1, n_blocks=100, horizons=(100,)).validate()


def test_pair_arm_validation():
    with pytest.raises(ValueError, match="pair_id and arm"):
        ScenarioConfig(scenario_id="bad", seed=1, pair_id="p1").validate()
    with pytest.raises(ValueError, match="arm must be"):
        ScenarioConfig(scenario_id="bad", seed=1, pair_id="p1", arm="both").validate()


def test_probe_window_validation():
    with pytest.raises(ValueError, match="precursor window"):
        ScenarioConfig(
            scenario_id="bad", seed=1, n_blocks=200,
            attack=AttackConfig(
                attack_type="channel_jamming", onset_block=50,
                probe_enabled=True, precursor_lead_blocks=60,
            ),
        ).validate()


def test_config_hash_stable():
    a = ScenarioConfig(scenario_id="h", seed=1)
    b = ScenarioConfig(scenario_id="h", seed=1)
    assert a.config_hash() == b.config_hash()
    c = ScenarioConfig(scenario_id="h", seed=2)
    assert a.config_hash() != c.config_hash()
