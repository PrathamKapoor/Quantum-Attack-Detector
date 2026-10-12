# Security Policy

## Scope of this project

Quantum Attack Detector is **research software that simulates attacks** on a modelled
continuous-variable quantum-key-distribution link. Simulated attack behaviour
(intercept–resend, local-oscillator manipulation, calibration manipulation, channel
jamming) is the subject of study, not a vulnerability.

**Do not open a security issue to report a simulated attack.** That is exactly what the
simulator is built to produce, and doing so will be closed as "working as intended".

## What is in scope

Real defects in the software itself, for example:

- online code paths that can consume future information (look-ahead leakage);
- incorrect statistical reporting — degenerate confidence intervals, wrong denominators,
  broken unit conversions (see `src/quantumattack/temporal_units.py`, the single block ↔
  second conversion authority);
- evaluation code that silently drops scenarios or double-counts alerts;
- unsanitised input handling in the CLI modules (`quantumattack.simulator.generate`,
  `quantumattack.features_cli`) or in `scripts/`.

The contracts in `tests/test_causal_warning_semantics.py` and
`tests/test_confirmation_evidence.py` encode the invariants that matter most; a change
that silently weakens them is a security-relevant regression in this project's terms.

## What is out of scope

- Anything about the underlying scientific conclusions — those are discussed as issues
  or pull requests, not vulnerabilities.
- The absence of a security guarantee for real QKD deployments. This code is
  **synthetic-only** and is not intended to protect a live link.

## How to report

There is no dedicated security-response team. Report suspected defects by opening a
**public GitHub issue** describing the reproducer (command, config, and the observed vs
expected output). Please include the simulator version (`quantumattack.__version__`),
the configuration file used, and the seed.

If a defect would only matter once the code is adapted to a live system, say so in the
issue — that adaptation is out of this repository's scope, but the analysis is still
welcome.

## Disclosure

Fixes land through ordinary pull requests and are recorded in `decisions.md` with a
sequential `D-NNN` entry when they change behaviour or measurement semantics.