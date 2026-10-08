"""GMCS CV-QKD protocol block (docs/telemetry-spec.md).

Computes per-block parameter-estimation statistics and the secret-key-rate estimate
from the CURRENT state only (causal; no future samples — leakage risk #1).
"""
from __future__ import annotations

import math

from ..config import ProtocolConfig
from ..channel.optical import ChannelState


def parameter_estimate(
    protocol: ProtocolConfig,
    channel: ChannelState,
    det: DetectorState,
    measured: dict,
    lo_hidden_noise_factor: float = 0.0,
) -> dict:
    """Parameter estimation from measured statistics (what a monitor could compute).

    - T̂: transmittance estimated from measured variance vs modulation
    - ε̂: excess-noise estimate — the LO attack's hidden factor reduces the
      ATTACK-added noise the estimator sees (true state keeps the full value)
    - SKR: per-block asymptotic GMCS reverse-reconciliation estimate
    """
    v_a = protocol.mod_variance_snu
    scale = (det.lo_power * det.det_gain) ** 2
    # invert the measurement model for T̂ (assuming known V_A, tau, t)
    v_meas_minus_vac = max(1e-9, measured["x_var"] - 1.0)
    tau_t_est = v_meas_minus_vac / scale  # = tau*T*(V_A+1+xi+bg) + t  (upper bound form)
    tau_t = det.det_efficiency * channel.transmittance
    # excess-noise estimate: subtract known V_A contribution
    xi_est = max(0.0, tau_t_est / max(det.det_efficiency * channel.transmittance, 1e-9) - v_a - 1.0)
    # apply LO-attack hidden factor: estimator sees reduced attack noise
    attack_noise_part = max(0.0, xi_est - channel.excess_noise_snu - channel.background_snu)
    xi_est_visible = max(
        0.0, channel.excess_noise_snu + channel.background_snu + attack_noise_part * (1.0 - lo_hidden_noise_factor)
    )
    t_hat = min(1.0, tau_t_est / max(v_a + 1.0, 1e-9))

    snr_lin = max(
        1e-9,
        (det.det_efficiency * channel.transmittance * v_a)
        / max(v_meas_minus_vac - det.det_efficiency * channel.transmittance * (v_a + 1.0), 1e-9),
    )
    i_ab = math.log2(1.0 + snr_lin)
    # Holevo bound chi(W&P) — reverse reconciliation, asymptotic Gaussian approx
    t_eff = max(1e-9, t_hat)
    xi_eff = max(1e-9, xi_est_visible)
    chi = _holevo_reverse(t_eff, xi_eff, v_a)
    skr = max(0.0, protocol.recon_efficiency * i_ab - chi)

    return {
        "t_hat": t_hat,
        "xi_hat": xi_est_visible,
        "snr": 10.0 * math.log10(snr_lin),
        "i_ab": i_ab,
        "skr_estimate": skr,
    }


def _holevo_reverse(t: float, xi: float, v_a: float) -> float:
    """Asymptotic Holevo chi_BE for reverse reconciliation (Gaussian, approximate).

    Standard GG02 form: chi_BE = G((sqrt((1-t+t*xi)^2 + 4*t*xi) ... )) — the exact
    expression involves G(x) = (x+1)log2(x+1) - x log2 x over symplectic eigenvalues
    of the conditional state. Phase 1 uses the compact approximation documented here;
    finite-key corrections are later-phase work (docs/telemetry-spec.md §Security).
    """
    def g(x: float) -> float:
        if x <= 1e-12:
            return 0.0
        return (x + 1.0) * math.log2(x + 1.0) - x * math.log2(x)

    a = 1.0 - t + t * xi  # variance A
    b = t * (v_a + 1.0)   # variance B
    # symplectic eigenvalues (approximate conditional state)
    lam1 = a - t * v_a / max(b, 1e-9)
    lam2 = a
    lam1 = max(lam1, 1e-6)
    lam2 = max(lam2, 1e-6)
    return max(0.0, g((lam1 - 1.0) / 2.0) + g((lam2 - 1.0) / 2.0))
