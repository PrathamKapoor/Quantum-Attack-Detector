"""Statistical-method tests: scenario clustering, reproducibility, degenerate groups.

These enforce the statistical-correctness requirements: independent unit is the
scenario, intervals are non-degenerate at boundaries, empty groups are undefined,
and resampling is reproducible from a recorded seed.
"""
import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

REPO = Path(__file__).resolve().parents[1]

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


# --------------------------------------------------------------------------
# Model-fit reproducibility (D-048)
# --------------------------------------------------------------------------
def test_logistic_fit_is_reproducible_within_process():
    """Repeated fits on identical data must produce identical coefficients.

    A non-deterministic solver makes every reported metric irreproducible, so
    this is asserted directly rather than assumed.
    """
    sys.path.insert(0, str(REPO / "src"))
    from quantumattack.baselines.logistic import ModelConfig, fit_horizon_model

    rng = np.random.default_rng(0)
    n = 4000
    X = rng.normal(0, 1, size=(n, 12))
    y = (X[:, 0] + 0.5 * X[:, 1] + rng.normal(0, 0.3, size=n) > 0).astype(int)
    mc = ModelConfig()
    cols = [f"f{i}" for i in range(12)]
    m1 = fit_horizon_model(X, y, 100, cols, mc)
    m2 = fit_horizon_model(X, y, 100, cols, mc)
    assert np.array_equal(m1.coef, m2.coef)
    assert m1.intercept == m2.intercept


def test_logistic_fit_is_stable_across_thread_counts():
    """Coefficients must not depend on ambient BLAS thread count.

    The previous default solver ('lbfgs') reduced across threads in
    non-deterministic order, so the same seed produced materially different
    coefficients in different processes (AUROC spread ~1e-2).
    """
    sys.path.insert(0, str(REPO / "src"))
    from quantumattack.baselines.logistic import ModelConfig, fit_horizon_model

    rng = np.random.default_rng(7)
    n = 3000
    X = rng.normal(0, 1, size=(n, 20))
    y = (X[:, 0] - 0.3 * X[:, 3] + rng.normal(0, 0.5, size=n) > 0.5).astype(int)
    mc = ModelConfig()
    cols = [f"f{i}" for i in range(20)]

    script = (
        "import sys, json, numpy as np;"
        "sys.path.insert(0, r'C:\\Projects\\Quantumattack\\src');"
        "from quantumattack.baselines.logistic import ModelConfig, fit_horizon_model;"
        f"rng=np.random.default_rng(7);X=rng.normal(0,1,size=({n},20));"
        f"y=(X[:,0]-0.3*X[:,3]+rng.normal(0,0.5,size={n})>0.5).astype(int);"
        "m=fit_horizon_model(X,y,100,[f'f{i}' for i in range(20)],ModelConfig());"
        "print(json.dumps({'c':float(m.coef.sum()),'i':m.intercept}))"
    )
    import json as _json
    import subprocess
    outs = []
    for threads in ("1", "4"):
        env = dict(os.environ, OMP_NUM_THREADS=threads, MKL_NUM_THREADS=threads,
                   OPENBLAS_NUM_THREADS=threads)
        r = subprocess.run([sys.executable, "-c", script], capture_output=True,
                           text=True, env=env, cwd=str(REPO))
        assert r.returncode == 0, r.stderr
        outs.append(_json.loads(r.stdout.strip().splitlines()[-1]))

    # single-process reference
    from quantumattack.baselines.logistic import ModelConfig as MC, fit_horizon_model as fh
    m = fh(X, y, 100, cols, MC())
    ref = {"c": float(m.coef.sum()), "i": m.intercept}

    for o in outs:
        assert abs(o["c"] - ref["c"]) < 1e-6, \
            f"coefficients depend on thread count: {o} vs {ref}"
        assert abs(o["i"] - ref["i"]) < 1e-6