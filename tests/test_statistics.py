"""Statistical-method tests: scenario clustering, reproducibility, degenerate groups.

These enforce the statistical-correctness requirements: independent unit is the
scenario, intervals are non-degenerate at boundaries, empty groups are undefined,
and resampling is reproducible from a recorded seed.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantumattack.statistics import (  # noqa: E402
    wilson_interval, scenario_cluster_bootstrap,
)


def test_cluster_bootstrap_is_reproducible_from_seed():
    data = {f"s{i}": float(i) for i in range(20)}
    fn = lambda vals: float(np.mean(vals))
    a = scenario_cluster_bootstrap(data, fn, n_boot=200, seed=11)
    b = scenario_cluster_bootstrap(data, fn, n_boot=200, seed=11)
    c = scenario_cluster_bootstrap(data, fn, n_boot=200, seed=12)
    assert a.ci_low == b.ci_low and a.ci_high == b.ci_high
    assert (a.ci_low != c.ci_low) or (a.ci_high != c.ci_high)


def test_cluster_bootstrap_resamples_scenarios_not_rows():
    """Each cluster contributes ONE value; the number of independent units is
    the number of scenarios, not the number of underlying windows."""
    # 3 scenarios each with many windows collapsed to one value each
    per_scenario = {"a": 1.0, "b": 2.0, "c": 3.0}
    res = scenario_cluster_bootstrap(per_scenario, lambda v: float(np.mean(v)),
                                      n_boot=100, seed=3)
    assert res.n_clusters == 3
    assert res.point == pytest.approx(2.0)


def test_cluster_bootstrap_handles_undefined_metric():
    def always_none(vals):
        return None
    res = scenario_cluster_bootstrap({"a": 1.0, "b": 2.0}, always_none, n_boot=50)
    assert res.point is None
    assert res.ci_low is None


def test_cluster_bootstrap_survives_metric_exception():
    def raises(vals):
        if len(vals) < 2:
            raise ValueError("need 2")
        return float(np.mean(vals))
    res = scenario_cluster_bootstrap({"a": 1.0, "b": 2.0, "c": 3.0}, raises, n_boot=100, seed=4)
    # Some single-cluster resamples raise; the rest still produce an interval
    assert res.point == pytest.approx(2.0)
    assert res.ci_low is not None and res.ci_high is not None


def test_cluster_bootstrap_empty_input_undefined():
    res = scenario_cluster_bootstrap({}, lambda v: 0.0, n_boot=10)
    assert res.point is None and res.n_clusters == 0


def test_cluster_bootstrap_point_equals_full_sample_statistic():
    rng = np.random.default_rng(0)
    data = {f"s{i}": float(rng.normal()) for i in range(50)}
    res = scenario_cluster_bootstrap(data, lambda v: float(np.median(v)), n_boot=100, seed=5)
    full = float(np.median(list(data.values())))
    assert res.point == pytest.approx(full)


def test_cluster_bootstrap_interval_brackets_point_in_most_cases():
    rng = np.random.default_rng(1)
    data = {f"s{i}": float(rng.normal(loc=i % 5)) for i in range(40)}
    res = scenario_cluster_bootstrap(data, lambda v: float(np.mean(v)), n_boot=500, seed=6)
    assert res.ci_low <= res.point <= res.ci_high


def test_wilson_narrows_with_more_samples():
    small = wilson_interval(5, 10)
    large = wilson_interval(500, 1000)
    assert (large.ci_high - large.ci_low) < (small.ci_high - small.ci_low)