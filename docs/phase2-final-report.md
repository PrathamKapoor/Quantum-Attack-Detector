# Phase 2 Final Report
Status: COMPLETE · Gate: WEAK SIGNAL

Evidence artifacts: artifacts/phase2/ (metrics.json, predictions.parquet,
experiment_manifest.json, ablation_summary.json, multiseed-summary.json)

Key verified: feature layer (23 tests + 1 historical invariance test);
baselines (23 tests); 40 Phase 1 regression tests; 86 combined;
reproducible metrics; pair-gated attribution logic documented and used;
no simulator optimization for model success.

Gate: WEAK SIGNAL — row-level discrimination exists (AUROC 0.70-0.84 by horizon);
attributed (independent, sustained-until-onset) anticipatory warnings exist
for gradual attacks; sudden-onset attacks produce 0% attribution (correct physics);
FWR NORMAL ≈0.79; feature-group ablation shows temporal statistics improve calibration
(Brier 0.190→0.170 at H=100) but do not solve the paired-dataset attribution problem;
next: larger unpaired/mixed dataset (Phase 3 pre-registered).
