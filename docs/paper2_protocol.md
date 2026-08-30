# Paper 2 protocol v1: curvewise PMSM torque uncertainty

Frozen: 2026-08-21, after an explicitly exploratory aggregate feasibility run

## Question and contribution boundary

Can a periodic PMSM torque response surface provide **simultaneous coverage for all 120
angles**, adapt band width to local geometry density, and warn when a requested geometry has
weak support?

The Fourier representation is inherited from Partovizadeh, Schöps, and Loukrezis (2025),
DOI [10.1007/s00366-025-02123-1](https://doi.org/10.1007/s00366-025-02123-1).
Paper 2 does not claim that DFT reduction, polynomial response surfaces, kernel response
surfaces, or Monte Carlo UQ are new. The new endpoint is calibrated full-curve risk rather
than point error or aggregate mean/standard-deviation accuracy.

## Data roles

- First 1,800 rows of `train_test`: deterministic seed split into 1,200 fit and 600
  calibration designs.
- Last 200 rows of `train_test`: preserve the source article's fixed internal test role.
- 11,250 `uq_uniform` rows: main large uniform evaluation.
- 10,000 `uq_gauss` rows: density-shift evaluation.
- Primary seed: 20260821. Sensitivity seeds: 1201, 2402, 3603, and 4804.

No torque from calibration or evaluation tables may choose a regressor hyperparameter.
Each regressor uses three-fold cross-validation inside the 1,200-row fit role only.

## Predictors

All predictors retain the first 11 real-FFT components and reconstruct the 120-angle curve.

1. quadratic polynomial features with ridge regularization;
2. RBF kernel ridge as a transparent approximation to a GP posterior mean;
3. a source-style anisotropic (ARD) Gaussian process with a shared kernel across the 21
   real Fourier coordinates and fit-only marginal-likelihood optimization;
4. Extra Trees as a nonlinear nonparametric comparator.

The source paper fitted each reduced coordinate independently and optimized its ellipsoidal
Gaussian covariance with CMA-ES. The shared-kernel ARD implementation is a closer
source-style comparator, not an exact reproduction; kernel ridge remains a simpler
transparent approximation. Polynomial, kernel-ridge, and tree settings use three-fold
fit-only cross-validation. The ARD kernel parameters use fit-only log marginal likelihood.

## Curvewise uncertainty

For design `i`, the nonconformity score is the maximum absolute error over all 120 angles.
The global band applies the finite-sample split-conformal order statistic to those 600
scores. Therefore, under exchangeability with the calibration designs, coverage refers to
the **entire curve**, not 120 separate pointwise intervals.

The geometry-scaled band divides each calibration score by a label-free scale:

1. normalize all 20 parameters using only the 1,800-row development range;
2. compute distance to the fifth-nearest fit design;
3. divide by the median leave-one-out fifth-neighbour distance among fit designs;
4. floor the scale at 0.25;
5. conformalize the scaled maximum error.

Because the scale is fixed from fit geometries before calibration labels are used, ordinary
split-conformal validity is retained for exchangeable uniform designs. No distribution-free
coverage guarantee is asserted for the Gaussian density shift.

## Support warning

Fifth-neighbour distances of the 600 calibration geometries form a label-free reference.
An evaluation geometry receives the upper-tail conformal p-value
`(1 + count(calibration distance >= test distance)) / 601` and is rejected at 0.05.
Accepted-set coverage is descriptive because selection changes the evaluated population.

## Post-primary weighted-conformal comparator

After the primary aggregate results had already been inspected, an estimated weighted
split-conformal comparator was added to test whether likelihood-ratio correction is usable
for the released Gaussian design shift. It is therefore a transparent post-primary
diagnostic, not a preregistered primary endpoint.

For each published target parameter table, a deterministic half-split separates unlabeled
target geometries used to estimate the density ratio from geometries used to evaluate the
bands. A quadratic logistic domain classifier is fitted to the 1,200 source-fit geometries
and the target ratio-fit half. Class balancing makes its log odds an estimate of the
target/source log density ratio; regularization is selected by three-fold domain-label log
loss. No target torque is used to fit the ratio estimator or choose its regularization.

The weighted quantile retains the test-point likelihood-ratio mass at positive infinity,
as required by weighted conformal prediction. Infinite bands are reported as vacuous and
are never clipped to the largest calibration error. Because the likelihood ratio is
estimated rather than known, no exact distribution-free target-shift guarantee is claimed.
The mandatory endpoints are held-out domain AUC, calibration-weight effective sample size,
maximum normalized calibration weight, finite-band rate, coverage including vacuous bands,
and coverage and width among finite bands.

## Endpoints

Primary miscoverage is 0.10; 0.05 is a sensitivity analysis.

- simultaneous full-curve coverage with Wilson intervals;
- mean and 90th-percentile band half-width;
- coverage and error by geometry-distance quintile;
- support-rejection rate and accepted-set coverage;
- waveform MAE/RMSE/MAPE;
- mean-torque and peak-to-peak torque-ripple MAE;
- fit/calibration split sensitivity across five seeds.

All 200 internal-test rows are reported even if their small-sample coverage differs from the
two large evaluation tables. No row, distance quintile, or model may be suppressed after the
result is seen.

## Completion gate

Paper 2 is not submission-ready until the full multi-seed benchmark, source-method
comparison, literature audit, figures, manuscript, evidence validator, and extracted
reproducibility bundle pass. Hardware or cross-topology claims additionally require a new
dataset; the current public archive alone cannot satisfy that gate.
