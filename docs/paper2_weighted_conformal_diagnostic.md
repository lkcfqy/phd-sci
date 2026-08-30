# Paper 2 estimated weighted-conformal diagnostic

Date: 2026-08-21  
Status: post-primary-result comparator; target-torque-blind density-ratio fitting

## Answer first

Likelihood-ratio weighting is numerically usable when the target is another uniform sample
from the released design law, but it becomes completely vacuous for the concentrated
20-parameter Gaussian shift. The failure is not hidden by clipping an infinite quantile.
It supplies an important boundary for Paper 2: geometry-scaled bands can be useful in this
benchmark precisely where formally shift-weighted bands lack source calibration support.

## Frozen comparison

The first 1,200 source designs fit the Fourier-11 quadratic-ridge torque surrogate, and 600
disjoint source designs provide curvewise calibration errors. Within each large target
table, a deterministic half-split assigns one half to label-free density-ratio fitting and
the other half to band evaluation. A balanced quadratic logistic domain classifier estimates
the target/source density ratio. Its regularization uses only cross-validated domain-label
log loss. Target torque never enters density-ratio estimation.

For each evaluation geometry, the weighted-conformal distribution places its test weight at
positive infinity. A band is infinite when the finite calibration mass cannot reach the
requested quantile. Reported `coverage including vacuous bands` is not interpreted as useful
coverage when the finite-band rate is zero.

## Results

At nominal 90% coverage:

| Target distribution | Held-out domain AUC | Calibration-weight ESS | Largest calibration mass | Finite weighted bands | Weighted coverage | Mean finite half-width |
|---|---:|---:|---:|---:|---:|---:|
| Uniform | 0.5059 | 516.50 / 600 | 0.53% | 5,625 / 5,625 | 0.9198 | 0.02502 |
| Gaussian | 1.0000 | 4.31 / 600 | 39.70% | 0 / 5,000 | vacuous | not defined |

The Gaussian result is unchanged at nominal 95%: 0/5,000 bands are finite. On the same
Gaussian evaluation half, ordinary global and geometry-scaled bands remain finite for all
5,000 designs; their 90% coverages are 0.9668 and 0.9088, respectively, with mean
half-widths 0.02390 and 0.01987.

## Interpretation boundary

The estimated weighted method does not inherit an exact guarantee that assumes a known
likelihood ratio. The perfect held-out domain separation, ESS collapse, and vacuous quantile
are nevertheless direct diagnostics of overlap failure. This comparison does not prove that
geometry scaling is distribution-free under Gaussian shift; it shows only that the latter
remains empirically informative in a setting where estimated importance weighting cannot
produce a finite band from the available uniform calibration sample.

Reproduce with:

```powershell
.\.venv\Scripts\python.exe scripts\run_torque_weighted_conformal.py
```

Authoritative outputs are in `results/paper2_weighted_conformal/`.
