"""Scenario configuration: dataclasses + validation (master prompt §20).

Every scenario is a validated config. Invalid physical or logical configurations
fail loudly at construction (ValueError), never mid-simulation.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
import hashlib
import json


# ---------------------------------------------------------------------------
# Time defaults (docs/time-semantics.md)
# ---------------------------------------------------------------------------
BLOCK_MS = 10.0  # 1 block = 10 ms = 1e6 symbols @100 MBaud (source 8 anchor)
DEFAULT_HORIZONS = (10, 25, 50, 100)  # blocks


@dataclass(frozen=True)
class ProtocolConfig:
    """GMCS CV-QKD with heterodyne detection (decision D-008)."""

    mod_variance_snu: float = 4.0       # V_A in shot-noise units
    symbol_rate_mbaud: float = 100.0    # source 8
    det_efficiency: float = 0.6         # trusted tau
    electronic_noise_snu: float = 0.05  # input-referred t
    recon_efficiency: float = 0.95      # beta

    def validate(self) -> None:
        if not (0.1 <= self.mod_variance_snu <= 20.0):
            raise ValueError(f"mod_variance_snu out of plausible range: {self.mod_variance_snu}")
        if not (0.0 < self.det_efficiency <= 1.0):
            raise ValueError(f"det_efficiency must be in (0, 1]: {self.det_efficiency}")
        if self.electronic_noise_snu < 0:
            raise ValueError(f"electronic_noise_snu cannot be negative: {self.electronic_noise_snu}")
        if not (0.0 < self.recon_efficiency <= 1.0):
            raise ValueError(f"recon_efficiency must be in (0, 1]: {self.recon_efficiency}")


@dataclass(frozen=True)
class ChannelConfig:
    """Fiber quantum channel baseline state."""

    length_km: float = 50.0
    attenuation_db_per_km: float = 0.15
    base_excess_noise_snu: float = 0.01  # at Bob input (conservative; includes phase-noise residuals)
    base_background_snu: float = 0.002   # background light at detector input

    def validate(self) -> None:
        if self.length_km <= 0:
            raise ValueError(f"length_km must be positive: {self.length_km}")
        if self.attenuation_db_per_km < 0:
            raise ValueError(f"attenuation_db_per_km cannot be negative: {self.attenuation_db_per_km}")
        if self.base_excess_noise_snu < 0 or self.base_background_snu < 0:
            raise ValueError("base_excess_noise_snu and base_background_snu cannot be negative")


@dataclass(frozen=True)
class EnvironmentConfig:
    """Benign confounders (docs/precursor-taxonomy.md §Environmental confounders).

    All processes are benign: magnitudes small, no attack operating points.
    """

    temperature_mean_c: float = 22.0
    temperature_amplitude_c: float = 0.8    # slow sinusoid amplitude
    temperature_ou_sigma: float = 0.05      # OU noise on temperature per block
    lo_thermal_coupling: float = 0.01       # max fractional LO power change per °C
    det_efficiency_ou_sigma: float = 0.002  # OU wander on detector efficiency
    det_gain_ou_sigma: float = 0.003        # benign calibration gain wander
    det_offset_ou_sigma: float = 0.002      # benign calibration offset wander (SNU)
    background_ou_sigma: float = 0.0005     # OU background fluctuation
    background_spike_prob: float = 0.002    # per-block prob of benign background spike
    background_spike_sigma_mult: float = 8.0  # spike magnitude in units of base background
    clock_drift_ou_sigma_ppb: float = 1.0   # oscillator frequency offset random walk
    jitter_ns: float = 2.0                  # baseline timing jitter
    fiber_loss_ou_sigma_db: float = 0.01    # OU wander on fiber loss per block
    fiber_degradation_db_per_block: float = 0.0  # aging (0 = off in Phase 1)
    ou_theta: float = 0.05                  # OU mean-reversion rate per block
    # benign sudden disturbance episodes (hard negatives; master prompt §11)
    disturbance_episode_prob: float = 0.0   # per-scenario prob of one benign transient
    disturbance_duration_blocks: int = 20
    disturbance_background_sigma_mult: float = 12.0
    disturbance_clock_step_ns: float = 30.0

    def validate(self) -> None:
        neg = [k for k, v in asdict(self).items() if isinstance(v, (int, float)) and v < 0]
        if neg:
            raise ValueError(f"environment parameters cannot be negative: {neg}")
        if self.ou_theta <= 0 or self.ou_theta >= 1:
            raise ValueError(f"ou_theta must be in (0, 1): {self.ou_theta}")


@dataclass(frozen=True)
class AttackConfig:
    """Attack configuration (docs/attack-taxonomy.md §Detailed entries).

    attack_type: none | intercept_resend | lo_manipulation | calibration_manipulation
                 | channel_jamming
    onset semantics: attack_onset = first block where the malicious mechanism modifies
    system state per the attack's definition — NOT first abnormal telemetry.
    """

    attack_type: str = "none"
    onset_block: int = -1               # required (>=0) for all non-none attacks
    # intercept_resend
    tap_fraction: float = 0.3           # fraction of channel power tapped
    resend_noise_mult: float = 2.0      # excess-noise multiplier from resend
    # lo_manipulation (class A gradual)
    lo_attack_attenuation: float = 0.5  # final LO power multiplier = 1 - A
    lo_hidden_noise_factor: float = 0.5 # fraction of excess noise hidden by ε̂ bias
    ramp_min_blocks: int = 40
    ramp_max_blocks: int = 120
    ramp_jump_start: float = 0.05       # s0 in OU ramp space
    ramp_ou_sigma: float = 0.08
    # calibration_manipulation (class A gradual)
    cal_gain_bias: float = 0.15         # relative gain bias target
    cal_offset_bias_snu: float = 0.05   # offset target (SNU)
    cal_ramp_min_blocks: int = 50
    cal_ramp_max_blocks: int = 150
    # channel_jamming (class B probes optional, then C sudden)
    jamming_power_snu: float = 0.5      # injected background power at detector input
    probe_enabled: bool = False
    probe_lambda: float = 0.5           # Poisson burst count over precursor window
    probe_duration_blocks: int = 2
    probe_mu_frac: float = 0.25         # probe elevation as fraction of jamming power
    precursor_lead_blocks: int = 80     # precursor_start = onset - lead (A/B attacks)

    def validate(self, n_blocks: int) -> None:
        valid_types = {
            "none", "intercept_resend", "lo_manipulation",
            "calibration_manipulation", "channel_jamming",
        }
        if self.attack_type not in valid_types:
            raise ValueError(f"unknown attack_type: {self.attack_type!r} (valid: {sorted(valid_types)})")
        if self.attack_type != "none":
            if not (0 <= self.onset_block < n_blocks):
                raise ValueError(
                    f"onset_block {self.onset_block} outside scenario duration [0, {n_blocks})"
                )
        if self.attack_type == "intercept_resend":
            if not (0.0 < self.tap_fraction < 1.0):
                raise ValueError(f"tap_fraction must be in (0, 1): {self.tap_fraction}")
            if self.resend_noise_mult < 1.0:
                raise ValueError(f"resend_noise_mult must be >= 1: {self.resend_noise_mult}")
        if self.attack_type == "lo_manipulation":
            if not (0.0 < self.lo_attack_attenuation < 1.0):
                raise ValueError(f"lo_attack_attenuation must be in (0, 1): {self.lo_attack_attenuation}")
            if not (0.0 <= self.lo_hidden_noise_factor <= 1.0):
                raise ValueError(f"lo_hidden_noise_factor must be in [0, 1]: {self.lo_hidden_noise_factor}")
            if not (0 < self.ramp_min_blocks <= self.ramp_max_blocks):
                raise ValueError("ramp_min_blocks must be in (0, ramp_max_blocks]")
            if not (0.0 < self.ramp_jump_start <= 1.0):
                raise ValueError(f"ramp_jump_start must be in (0, 1]: {self.ramp_jump_start}")
        if self.attack_type == "calibration_manipulation":
            if not (0.0 < self.cal_gain_bias < 0.5):
                raise ValueError(f"cal_gain_bias must be in (0, 0.5): {self.cal_gain_bias}")
            if self.cal_offset_bias_snu < 0:
                raise ValueError("cal_offset_bias_snu cannot be negative")
            if not (0 < self.cal_ramp_min_blocks <= self.cal_ramp_max_blocks):
                raise ValueError("cal_ramp_min_blocks must be in (0, cal_ramp_max_blocks]")
        if self.attack_type == "channel_jamming":
            if self.jamming_power_snu <= 0:
                raise ValueError(f"jamming_power_snu must be positive: {self.jamming_power_snu}")
            if self.probe_enabled:
                if self.probe_lambda < 0:
                    raise ValueError("probe_lambda cannot be negative")
                if self.probe_duration_blocks < 1:
                    raise ValueError("probe_duration_blocks must be >= 1")
                if self.precursor_lead_blocks < 1:
                    raise ValueError("precursor_lead_blocks must be >= 1 when probes enabled")
                if self.onset_block - self.precursor_lead_blocks < 0:
                    raise ValueError("precursor window would start before block 0")


@dataclass(frozen=True)
class ScenarioConfig:
    """Complete scenario configuration (master prompt §20)."""

    scenario_id: str
    seed: int
    n_blocks: int = 2000                # default 20 s
    protocol: ProtocolConfig = field(default_factory=ProtocolConfig)
    channel: ChannelConfig = field(default_factory=ChannelConfig)
    environment: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    attack: AttackConfig = field(default_factory=AttackConfig)
    horizons: tuple[int, ...] = DEFAULT_HORIZONS
    pair_id: str = ""                   # matched-counterfactual pair (empty = unmatched)
    arm: str = ""                       # "normal" | "attack" (empty = unmatched)

    def validate(self) -> None:
        if not self.scenario_id:
            raise ValueError("scenario_id is required")
        if self.seed < 0:
            raise ValueError(f"seed cannot be negative: {self.seed}")
        if self.n_blocks < 10:
            raise ValueError(f"n_blocks must be >= 10: {self.n_blocks}")
        if not self.horizons or any(h < 1 or h >= self.n_blocks for h in self.horizons):
            raise ValueError(f"horizons must be in [1, n_blocks): {self.horizons}")
        self.protocol.validate()
        self.channel.validate()
        self.environment.validate()
        self.attack.validate(self.n_blocks)
        if self.arm and self.arm not in ("normal", "attack"):
            raise ValueError(f"arm must be 'normal' or 'attack': {self.arm!r}")
        if bool(self.pair_id) != bool(self.arm):
            raise ValueError("pair_id and arm must be set together")

    def config_hash(self) -> str:
        """Stable hash of the configuration (reproducibility, master prompt §21)."""
        payload = json.dumps(asdict(self), sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]

    def to_dict(self) -> dict:
        return asdict(self)
