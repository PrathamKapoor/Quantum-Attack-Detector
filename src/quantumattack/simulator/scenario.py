"""Scenario runner (docs/architecture-v1.md Part A).

Pipeline per block:
  environment.step → attack.step (state modification) → protocol evolution
  → telemetry.collect → (labels built AFTER simulation, from onset metadata)
"""
from __future__ import annotations

import importlib.metadata as _md

from .config import ScenarioConfig
from .clock import Clock
from .rng import make_rng
from .channel.optical import ChannelState
from .detectors.homodyne import DetectorState
from .environment.drift import EnvironmentState
from .telemetry.collector import TelemetryCollector, FEATURE_COLUMNS, TRUE_COLUMNS
from .labels.builder import build_labels
from ..dataset import METADATA_COLUMNS, LABEL_COLUMNS, EVAL_ONLY_COLUMNS

try:
    _SIM_VERSION = _md.version("quantumattack")
except Exception:  # package may be run from src/ without install
    from .. import __version__ as _SIM_VERSION


def create_attack(config: ScenarioConfig):
    """Instantiate the attack module from config (none → None)."""
    if config.attack.attack_type == "none":
        return None
    mod = {
        "intercept_resend": "intercept_resend",
        "lo_manipulation": "lo_manipulation",
        "calibration_manipulation": "calibration_manipulation",
        "channel_jamming": "channel_jamming",
    }[config.attack.attack_type]
    cls = _load_attack_class(mod)
    return cls(config.attack, config.seed)


def _load_attack_class(module_name: str):
    import importlib

    m = importlib.import_module(f".attacks.{module_name}", package=__package__)
    classes = {
        "intercept_resend": "InterceptResendAttack",
        "lo_manipulation": "LOManipulationAttack",
        "calibration_manipulation": "CalibrationManipulationAttack",
        "channel_jamming": "ChannelJammingAttack",
    }
    return getattr(m, classes[module_name])


class ScenarioResult:
    """One simulation run: telemetry records + labels + metadata."""

    def __init__(self, records: list[dict], labels: dict[str, list], metadata: dict):
        self.records = records
        self.labels = labels
        self.metadata = metadata

    @property
    def n_blocks(self) -> int:
        return len(self.records)


def run_scenario(config: ScenarioConfig) -> ScenarioResult:
    """Run one scenario end-to-end (deterministic given config)."""
    config.validate()

    # seeded streams: environment and attack are independent (dataset-spec §3)
    env_rng = make_rng(config.seed, "environment")
    meas_rng = make_rng(config.seed, "measurement")

    clock = Clock(n_blocks=config.n_blocks)
    channel = ChannelState.create(config.channel, config.seed, config.environment.ou_theta)
    detector = DetectorState.create(config.protocol, config.seed)
    env = EnvironmentState.create(config.environment, config.seed, base_xi_snu=config.channel.base_excess_noise_snu)
    attack = create_attack(config)
    collector = TelemetryCollector(config.protocol)

    records: list[dict] = []
    while not clock.done:
        env.step(env_rng)
        # benign drift couples into channel state: fiber loss wander (docs/precursor-taxonomy.md)
        channel.fiber_loss_db = (
            config.channel.attenuation_db_per_km * config.channel.length_km
            + env.fiber_loss_delta_db
        )
        # benign thermal coupling into excess noise (temperature confounder, §12):
        # small OU+temperature-driven drift around the base level, no attack target
        channel.excess_noise_snu = (
            config.channel.base_excess_noise_snu
            * (1.0 + 0.02 * (env.temperature_c - config.environment.temperature_mean_c))
            + env.xi_thermal_delta
        )
        # benign detector efficiency wander + benign calibration drift (confounder surface)
        detector.det_efficiency = (
            config.protocol.det_efficiency + (env.det_temperature_c - config.environment.temperature_mean_c) * 0.001
        )
        # benign calibration wander: OU gain/offset drift, same form as the attack ramp
        # but smaller magnitude and no operating-point target (docs/precursor-taxonomy.md)
        detector.det_gain = 1.0 + env.det_gain_delta
        detector.det_gain_plus = detector.det_gain + env.det_gain_plus_minus_delta
        detector.det_gain_minus = detector.det_gain - env.det_gain_plus_minus_delta
        detector.det_offset_snu = env.det_offset_delta
        if attack is not None:
            attack.step(_StateView(channel, detector, env), clock.block_index)
        # measurement randomness stream (per-block; independent of attack stream)
        records.append(collector.collect(clock, channel, detector, env, attack, meas_rng))
        clock.step()

    # attack metadata (onset semantics per docs/attack-taxonomy.md)
    if attack is not None:
        attack_onset = attack.onset_block
        precursor_start = attack.precursor_start
        has_precursor = attack.precursor_class in ("A", "B")
        precursor_class = attack.precursor_class
    else:
        attack_onset = -1
        precursor_start = -1
        has_precursor = False
        precursor_class = "none"

    # drift episode ground truth (benign sudden disturbances)
    drift_blocks = _drift_episode_blocks(env)

    labels = build_labels(
        n_blocks=config.n_blocks,
        attack_onset=attack_onset,
        precursor_start=precursor_start,
        has_precursor=has_precursor,
        drift_episode_blocks=drift_blocks,
        horizons=config.horizons,
    )

    scenario_class = _scenario_class(config, drift_blocks)

    metadata = {
        "scenario_id": config.scenario_id,
        "pair_id": config.pair_id,
        "arm": config.arm,
        "seed": config.seed,
        "protocol": "cvqkd-heterodyne",
        "sim_version": _SIM_VERSION,
        "config_hash": config.config_hash(),
        "scenario_class": scenario_class,
        "attack_type": config.attack.attack_type,
        "attack_onset": attack_onset,
        "precursor_start": precursor_start,
        "precursor_class": precursor_class,
    }

    return ScenarioResult(records, labels, metadata)


class _StateView:
    """Namespace exposing subsystem states to attack modules."""

    def __init__(self, channel, detector, environment):
        self.channel = channel
        self.detector = detector
        self.environment = environment


def _drift_episode_blocks(env: EnvironmentState) -> set[int]:
    """Reconstruct which blocks the benign disturbance episode covered.

    The episode is a named simulation event: its blocks are ground truth (labels),
    never inferred from telemetry (leakage risk #9).
    """
    if not env.episode_fired:
        return set()
    end = env._block  # total blocks stepped
    start = max(0, end - env.config.disturbance_duration_blocks)
    # approximate episode coverage: last `duration` blocks before episode end
    # (exact per-block tracking kept simple: episode ran contiguous to its end)
    return set(range(start, end)) if env.episode_remaining <= 0 else set(range(start, end))


def _scenario_class(config: ScenarioConfig, drift_blocks: set[int]) -> str:
    if config.attack.attack_type != "none":
        return "ATTACK"
    if drift_blocks:
        return "BENIGN_DRIFT"
    return "NORMAL"
