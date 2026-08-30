---
title: "Supplementary Material: Curvewise Conformal Prediction Bands for Periodic PMSM Torque Surrogates"
author: "Anonymous review version"
---


# S1. Data inventory and integrity audit

The released archive (DOI `10.5281/zenodo.15688397`) contains 23,250 independent simulated geometries from one two-dimensional, quarter-symmetry PMSM model. Each geometry has 20 inputs and a 120-angle torque period. The archive is licensed GPL-3.0-or-later. These are simulator rows, not independent machines or hardware measurements.

| Published table | Study role | Designs | Torque range | Median retained Fourier energy |
|---|---|---|---|---|
| train_test | development/internal | 2,000 | 0.297922-0.695034 | 99.9999955% |
| uq_uniform | large uniform evaluation | 11,250 | 0.296617-0.702839 | 99.9999955% |
| uq_gauss | Gaussian-shift evaluation | 10,000 | 0.340070-0.681911 | 99.9999920% |

All values were finite. The audit found no duplicate parameter rows, no duplicate torque rows, and zero exact parameter-row overlap in each of the three pairwise table comparisons. All files shared the 0-29.75 degree grid at 0.25-degree increments. The audit establishes row integrity and absence of exact reuse; it does not establish fidelity beyond the source simulator.

| Dataset | Role | File | Bytes | SHA-256 |
|---|---|---|---|---|
| train_test | parameters | train_test_parameters.csv | 477,742 | `10c0b1b344d5addadacfad2b53ebe7d41e70f4e6ecc9fa8344fd840fbe8906a0` |
| train_test | torque | train_test_torque.csv | 2,856,040 | `f9606c7e6b386e5eaf6537d63a745973d31fee6cb907101b85cd2c2d864cf39f` |
| uq_uniform | parameters | uq_uniform_parameters_11k.csv | 2,686,443 | `020f4b85fff4475f9662b1246c85c3253398fbef8c2b72b4f59d69b8fa262e88` |
| uq_uniform | torque | uq_uniform_torque_11k.csv | 16,061,335 | `df1f8aa5bf6e139659a7f935fb31b3831c2403119086ebaa323af83d3242656c` |
| uq_gauss | parameters | uq_gauss_parameters_10k.csv | 2,387,927 | `368832b4f571385788320c864a8a7a425da818b1acb5e66b6726e0d529088a40` |
| uq_gauss | torque | uq_gauss_torque_10k.csv | 14,277,285 | `ff85a001286dda41455e08d7ed6b269d7f0c9f16184f701af141cf848e3098e7` |

# S2. Frozen roles, splits, and endpoints

Rows 1-1,800 of `train_test` form the development pool. Seed 20260821 selects 1,200 fit rows and 600 calibration rows; the final 200 rows remain an internal evaluation set. The 11,250 uniform and 10,000 Gaussian rows never select a model or hyperparameter. Four additional deterministic seeds (1201, 2402, 3603, and 4804) repeat only the fit/calibration split.

The primary endpoint is simultaneous full-curve coverage at nominal 90% (`alpha=0.10`); 95% is a frozen sensitivity analysis. A design is covered only when all 120 torque angles fall inside its band. The nonconformity score is the maximum absolute error across the period. Wilson intervals treat independently simulated design rows as binomial units; they do not represent physical-machine variation.

The geometry scale uses the fifth-nearest fit-design distance after range normalization, divided by the median fit leave-one-out fifth-neighbour distance and floored at 0.25. The support warning compares an evaluation distance with the 600 calibration distances and flags an upper-tail p-value below 0.05. Neither diagnostic uses evaluation torque labels.

# S3. Response surfaces and source-only selection

All methods predict the same 21 real coordinates corresponding to 11 retained DFT components and reconstruct all 120 angles. Candidate settings for ridge, kernel ridge, and Extra Trees were selected by three-fold waveform-MAE cross-validation using only the 1,200 fit designs. The ARD Gaussian process optimized a shared 20-dimensional RBF kernel by fit-only log marginal likelihood with length-scale bounds 0.03-10, numerical noise `1e-8`, and no restarts. It is source-style, not an exact reproduction of the source article's coordinate-wise GP/CMA-ES workflow.

| Model | Selected parameters | Selection basis |
|---|---|---|
| poly2_ridge | `{'alpha': 1e-07}` | three-fold fit-only waveform MAE |
| rbf_kernel_ridge | `{'alpha': 0.0001, 'gamma': 0.025}` | three-fold fit-only waveform MAE |
| ard_gaussian_process | `{'dimensions': 20.0, 'length_scale_upper': 10.0}` | fit-only log marginal likelihood |
| extra_trees | `{'n_estimators': 300.0, 'min_samples_leaf': 1.0, 'max_features': 1.0}` | three-fold fit-only waveform MAE |

# S4. Complete primary ARD Gaussian-process results

The table reports both frozen nominal levels. Widths are half-widths in the units stored by the source archive. Accepted-set coverage is descriptive because support screening changes the evaluated population.

| Evaluation | Band | Nominal | n | Full-curve coverage | 95% Wilson interval | Mean half-width | Support rejected | Accepted-set coverage |
|---|---|---|---|---|---|---|---|---|
| fixed internal uniform | global | 95% | 200 | 96.00% | 92.31%-97.96% | 0.009615 | 5.000% | 97.37% |
| fixed internal uniform | geometry-scaled | 95% | 200 | 96.00% | 92.31%-97.96% | 0.009028 | 5.000% | 97.37% |
| fixed internal uniform | global | 90% | 200 | 92.00% | 87.40%-95.02% | 0.007125 | 5.000% | 93.68% |
| fixed internal uniform | geometry-scaled | 90% | 200 | 92.00% | 87.40%-95.02% | 0.006834 | 5.000% | 93.68% |
| large uniform | global | 95% | 11,250 | 95.51% | 95.11%-95.88% | 0.009615 | 5.511% | 96.50% |
| large uniform | geometry-scaled | 95% | 11,250 | 95.25% | 94.84%-95.63% | 0.008991 | 5.511% | 96.06% |
| large uniform | global | 90% | 11,250 | 90.29% | 89.73%-90.83% | 0.007125 | 5.511% | 91.85% |
| large uniform | geometry-scaled | 90% | 11,250 | 89.96% | 89.40%-90.51% | 0.006806 | 5.511% | 91.23% |
| Gaussian density shift | global | 95% | 10,000 | 100.00% | 99.96%-100.00% | 0.009615 | 0.000% | 100.00% |
| Gaussian density shift | geometry-scaled | 95% | 10,000 | 100.00% | 99.96%-100.00% | 0.007400 | 0.000% | 100.00% |
| Gaussian density shift | global | 90% | 10,000 | 100.00% | 99.96%-100.00% | 0.007125 | 0.000% | 100.00% |
| Gaussian density shift | geometry-scaled | 90% | 10,000 | 100.00% | 99.96%-100.00% | 0.005601 | 0.000% | 100.00% |

# S5. Geometry-distance conditioning

Each uniform quintile contains 2,250 independent simulations and each Gaussian quintile 2,000. Geometry-distance quintiles are descriptive conditional audits, not additional calibration groups. The primary failure is visible in uniform quintile 5: global coverage is 76.13% and scaled coverage 78.31%, despite near-nominal aggregate coverage.

| Evaluation | Distance quintile | n | Mean max error | Global coverage | Scaled coverage | Mean scaled half-width |
|---|---|---|---|---|---|---|
| large uniform | 1 | 2,250 | 0.002693 | 97.96% | 96.84% | 0.006207 |
| large uniform | 2 | 2,250 | 0.003181 | 95.47% | 94.13% | 0.006557 |
| large uniform | 3 | 2,250 | 0.003620 | 92.58% | 91.42% | 0.006790 |
| large uniform | 4 | 2,250 | 0.004109 | 89.33% | 89.11% | 0.007035 |
| large uniform | 5 | 2,250 | 0.005522 | 76.13% | 78.31% | 0.007438 |
| Gaussian density shift | 1 | 2,000 | 0.002281 | 100.00% | 100.00% | 0.005414 |
| Gaussian density shift | 2 | 2,000 | 0.002344 | 100.00% | 100.00% | 0.005534 |
| Gaussian density shift | 3 | 2,000 | 0.002422 | 100.00% | 100.00% | 0.005604 |
| Gaussian density shift | 4 | 2,000 | 0.002477 | 100.00% | 100.00% | 0.005671 |
| Gaussian density shift | 5 | 2,000 | 0.002509 | 100.00% | 100.00% | 0.005781 |

# S6. Five-seed sensitivity

No seed was selected from target performance. The table retains all 30 primary ARD rows (five seeds by three evaluations by two bands). Uniform global coverage ranges from 87.99% to 91.08%; scaled coverage ranges from 88.93% to 91.31%. The sparse-tail limitation remains because every split samples the same simulator and released design mechanism.

| Seed | Evaluation | Band | Coverage | Mean half-width |
|---|---|---|---|---|
| 20260821 | fixed internal uniform | global | 92.00% | 0.007125 |
| 20260821 | fixed internal uniform | geometry-scaled | 92.00% | 0.006834 |
| 20260821 | large uniform | global | 90.29% | 0.007125 |
| 20260821 | large uniform | geometry-scaled | 89.96% | 0.006806 |
| 20260821 | Gaussian density shift | global | 100.00% | 0.007125 |
| 20260821 | Gaussian density shift | geometry-scaled | 100.00% | 0.005601 |
| 1201 | fixed internal uniform | global | 89.50% | 0.006826 |
| 1201 | fixed internal uniform | geometry-scaled | 89.50% | 0.006757 |
| 1201 | large uniform | global | 88.83% | 0.006826 |
| 1201 | large uniform | geometry-scaled | 88.93% | 0.006708 |
| 1201 | Gaussian density shift | global | 100.00% | 0.006826 |
| 1201 | Gaussian density shift | geometry-scaled | 99.96% | 0.005420 |
| 2402 | fixed internal uniform | global | 88.00% | 0.007257 |
| 2402 | fixed internal uniform | geometry-scaled | 87.50% | 0.007051 |
| 2402 | large uniform | global | 91.08% | 0.007257 |
| 2402 | large uniform | geometry-scaled | 91.04% | 0.007025 |
| 2402 | Gaussian density shift | global | 100.00% | 0.007257 |
| 2402 | Gaussian density shift | geometry-scaled | 100.00% | 0.005743 |
| 3603 | fixed internal uniform | global | 88.00% | 0.007550 |
| 3603 | fixed internal uniform | geometry-scaled | 89.00% | 0.007680 |
| 3603 | large uniform | global | 90.41% | 0.007550 |
| 3603 | large uniform | geometry-scaled | 91.31% | 0.007624 |
| 3603 | Gaussian density shift | global | 100.00% | 0.007550 |
| 3603 | Gaussian density shift | geometry-scaled | 99.98% | 0.006214 |
| 4804 | fixed internal uniform | global | 87.50% | 0.006446 |
| 4804 | fixed internal uniform | geometry-scaled | 87.50% | 0.006650 |
| 4804 | large uniform | global | 87.99% | 0.006446 |
| 4804 | large uniform | geometry-scaled | 89.23% | 0.006600 |
| 4804 | Gaussian density shift | global | 99.99% | 0.006446 |
| 4804 | Gaussian density shift | geometry-scaled | 99.95% | 0.005379 |

# S7. Post-primary estimated weighted-conformal diagnostic

This analysis was added after inspecting the primary aggregate results and uses the degree-two ridge surrogate. Each target table is split in half: one half fits a quadratic logistic domain classifier from geometry alone, and the other evaluates bands. The test weight is retained as point mass at positive infinity; an infinite quantile is not clipped. Coverage 'including vacuous' is set-theoretic and has no engineering utility when the finite-band rate is zero.

| Target | Method | Nominal | n | Finite-band rate | Coverage incl. vacuous | Finite-band coverage | Mean finite half-width |
|---|---|---|---|---|---|---|---|
| large uniform | global | 90% | 5,625 | 100.00% | 90.40% | 90.40% | 0.023903 |
| large uniform | geometry-scaled | 90% | 5,625 | 100.00% | 91.09% | 91.09% | 0.024129 |
| large uniform | estimated weighted | 90% | 5,625 | 100.00% | 91.98% | 91.98% | 0.025025 |
| large uniform | global | 95% | 5,625 | 100.00% | 95.72% | 95.72% | 0.030677 |
| large uniform | geometry-scaled | 95% | 5,625 | 100.00% | 95.70% | 95.70% | 0.029914 |
| large uniform | estimated weighted | 95% | 5,625 | 100.00% | 95.77% | 95.77% | 0.030904 |
| Gaussian density shift | global | 90% | 5,000 | 100.00% | 96.68% | 96.68% | 0.023903 |
| Gaussian density shift | geometry-scaled | 90% | 5,000 | 100.00% | 90.88% | 90.88% | 0.019873 |
| Gaussian density shift | estimated weighted | 90% | 5,000 | 0.00% | 100.00% | not defined | not defined |
| Gaussian density shift | global | 95% | 5,000 | 100.00% | 99.60% | 99.60% | 0.030677 |
| Gaussian density shift | geometry-scaled | 95% | 5,000 | 100.00% | 97.10% | 97.10% | 0.024637 |
| Gaussian density shift | estimated weighted | 95% | 5,000 | 0.00% | 100.00% | not defined | not defined |

| Target | Weight role | Designs | ESS | Maximum normalized mass | Held-out domain AUC |
|---|---|---|---|---|---|
| large uniform | source_calibration | 600 | 516.50 | 0.529% | 0.5059 |
| large uniform | target_evaluation | 5,625 | 4828.08 | 0.092% | 0.5059 |
| Gaussian density shift | source_calibration | 600 | 4.31 | 39.704% | 1.0000 |
| Gaussian density shift | target_evaluation | 5,000 | 2741.88 | 0.171% | 1.0000 |

For the uniform half-split, domain AUC was 0.5059, calibration ESS 516.50/600, and all 5,625 primary 90% weighted bands were finite. For the Gaussian half-split, domain AUC was 1.0000, calibration ESS 4.31/600, one source row carried 39.70% of normalized mass, and 0/5,000 weighted bands were finite at either nominal level. This is retained as an overlap failure, not repaired.

# S8. Timing and deterministic representative curves

Timings are workstation-specific and exclude high-fidelity simulation. The ARD model's 41.0 s figure includes fitting and fit-only hyperparameter optimization; predicting 11,250 uniform designs required 0.317 s.

| Model | Evaluation | Fit/select seconds | Predict seconds | Designs |
|---|---|---|---|---|
| poly2_ridge | fixed internal uniform | 0.110 | 0.001 | 200 |
| poly2_ridge | large uniform | 0.110 | 0.028 | 11,250 |
| poly2_ridge | Gaussian density shift | 0.110 | 0.026 | 10,000 |
| rbf_kernel_ridge | fixed internal uniform | 0.990 | 0.005 | 200 |
| rbf_kernel_ridge | large uniform | 0.990 | 0.177 | 11,250 |
| rbf_kernel_ridge | Gaussian density shift | 0.990 | 0.147 | 10,000 |
| ard_gaussian_process | fixed internal uniform | 41.005 | 0.008 | 200 |
| ard_gaussian_process | large uniform | 41.005 | 0.317 | 11,250 |
| ard_gaussian_process | Gaussian density shift | 41.005 | 0.260 | 10,000 |
| extra_trees | fixed internal uniform | 3.178 | 0.069 | 200 |
| extra_trees | large uniform | 3.178 | 0.164 | 11,250 |
| extra_trees | Gaussian density shift | 3.178 | 0.140 | 10,000 |

Representative curves were selected mechanically by frozen role and median-error rules rather than by visual preference.

| Distribution | Role | Published row | Max error | Global width | Scaled width | Global covered | Scaled covered |
|---|---|---|---|---|---|---|---|
| uq_uniform | dense_both_covered | 607 | 0.002257 | 0.007125 | 0.006385 | 1 | 1 |
| uq_uniform | sparse_scaled_rescue | 7690 | 0.007269 | 0.007125 | 0.008054 | 0 | 1 |
| uq_uniform | sparse_both_missed | 665 | 0.010097 | 0.007125 | 0.007273 | 0 | 0 |
| uq_gauss | gaussian_middle_both_covered | 6106 | 0.002470 | 0.007125 | 0.005626 | 1 | 1 |

# S9. Reproducibility boundary and evidence hashes

The companion bundle includes the analysis modules, deterministic scripts, tests, frozen aggregate and per-design results, figures, manuscript sources, and SHA-256 manifest. Raw public data are omitted from the bundle to avoid redistribution and must be downloaded from the source DOI. The main evidence validator recomputes claims from 42,900 primary per-design rows and the disjoint weighted diagnostic.

The evidential scope is one public two-dimensional PMSM simulator. The study does not quantify simulator model-form discrepancy, three-dimensional effects, manufacturing variation, another topology, another machine, or hardware uncertainty. Several ARD length scales reached the optimization upper bound. The weighted ratio is estimated, not known, and the diagnostic is explicitly post-primary.

| Frozen evidence file | SHA-256 |
|---|---|
| papers/paper2_torque_uq/manuscript.md | `01699a7a7010f239bf900c51fa7efc02b3a4501e5e2ff47d31955c1ef8e8f6ab` |
| results/paper2_torque_conformal/aggregate_summary.csv | `0700590d03103d3cc7b68b55a2d89afa5f244e08f85cee41950ccf5f175cced7` |
| results/paper2_torque_conformal/primary_per_design_scores.csv.gz | `a5695affa0244d2d4586db095ec2277ec1aec8b7533fa3b25d03e7833fe5f905` |
| results/paper2_torque_seed_sensitivity/aggregate_summary.csv | `424b57d378301f325ae940ec2013dce60368f04cc5c95a4b367caa8afdee665c` |
| results/paper2_weighted_conformal/comparison_summary.csv | `a5f08fe15d3e6dfbe3cd49517f6b04033b6a91400ff7243beb0410cb4a4fb3c7` |
| results/paper2_weighted_conformal/weighted_per_design.csv.gz | `e3974ca6697b4e2b6fd283e39730546687bf63ba102a18869133272679d06da0` |
| results/paper2_evidence_validation/evidence.json | `deb721c39280d53fc4c302ecaebca72fba913e724da8720ba1ff7191975a8dbc` |
