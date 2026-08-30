# Paper 2 targeted literature-gap audit

Updated: 2026-08-21

## Defensible positioning

Paper 2 must not claim the first conformal surrogate, the first conformal functional band,
the first adaptive conformal interval, or the first weighted-conformal treatment of
covariate shift. All four ideas have direct prior art. The defensible contribution is a
specific electrical-machine design study that joins curve-level risk, geometry-density
conditioning, support diagnostics, and an explicit overlap-failure audit on released
high-fidelity PMSM simulations.

## Closest prior work and non-overlap

| Prior work | What it already establishes | What remains distinct in Paper 2 |
|---|---|---|
| Partovizadeh, Schöps, and Loukrezis (2025), DOI `10.1007/s00366-025-02123-1` | Fourier reduction plus PCE, FNN, and GP response surfaces for 120-angle PMSM torque and Monte Carlo statistics | Simultaneous full-curve error control, design-density strata, a geometry-only support warning, and coverage/width behavior under the released uniform-to-Gaussian shift |
| Lei et al. (2018), DOI `10.1080/01621459.2017.1307116` | Model-agnostic split conformal regression and locally varying interval length | A periodic functional response, full-curve max-error endpoint, and PMSM design-space diagnostics |
| Diquigiovanni, Fontana, and Vantini (2022), DOI `10.1016/j.jmva.2021.104879`; Diquigiovanni et al. (2025), DOI `10.5705/ss.202022.0087` | Finite-sample simultaneous conformal bands for functional responses and output-domain modulation | Input-geometry density scaling, released electric-machine design shift, support warning, and comparison with density-ratio weighting |
| Tibshirani et al. (2019), NeurIPS 32 | Weighted conformal validity under known or accurately estimated target/source likelihood ratios | A measured overlap-collapse case in 20 PMSM geometry parameters: ESS 4.31/600 and no finite Gaussian-shift bands |
| El Mekkaoui et al. (2023), PMLR 204 | Adaptive conformal uncertainty for a neural structural-response surrogate | Periodic curvewise bands, electric-machine geometry, and simultaneous rather than scalar/componentwise coverage |
| Jaber et al. (2025), DOI `10.1615/JMachLearnModelComput.2025054687` | GP posterior-standard-deviation scaling with cross-conformal calibration for computer experiments | Model-agnostic Fourier surrogate comparison, label-free k-neighbour geometry scaling, and large fixed PMSM shift tables |
| Gray et al. (2025), PMLR 286 | SVD/zonotope conformal prediction sets for functional surrogate models | Direct interpretable torque bands over a 30-degree period and electric-machine design-support diagnostics |
| Gopakumar et al. (2026), DOI `10.1088/2632-2153/ae2e7b` | Broad conformal UQ experiments for high-dimensional spatiotemporal scientific surrogates | A focused PMSM geometry benchmark with all 23,250 high-fidelity labels, distance-conditional failures, torque engineering functionals, and weighted-overlap audit |

## Claims that are supported

1. The released source study reports prediction accuracy and Monte Carlo torque statistics,
   but not calibrated simultaneous bands for each complete torque period.
2. Paper 2 evaluates whole-curve coverage on 11,250 uniform and 10,000 Gaussian labeled
   simulator designs, rather than treating 120 anglewise intervals as independent.
3. Under source-like uniform sampling, ordinary split-conformal validity follows from
   exchangeability because the geometry scale is fixed without calibration torque labels.
4. Under Gaussian design-density shift, geometry-scaled performance is empirical. The
   estimated weighted comparator does not rescue a formal practical band because source
   calibration overlap collapses.
5. Sparse-region undercoverage remains visible: the geometry-scaled band improves but does
   not eliminate conditional undercoverage in the farthest uniform quintile.

## Claims that are prohibited

- first use of conformal prediction for scientific or engineering surrogates;
- first conformal functional or simultaneous prediction band;
- distribution-free Gaussian-shift coverage from geometry scaling;
- exact weighted-conformal validity with an estimated density ratio;
- calibration of finite-element model-form error or manufactured-machine uncertainty;
- cross-machine, cross-topology, or hardware generalization;
- novelty of Fourier reduction, PCE, GP, kernel ridge, or tree response surfaces.

## Manuscript implication

The Introduction should lead with the unaddressed decision endpoint: whether a complete
torque period is covered for a requested geometry and whether the request lies in supported
design space. The Discussion must contrast three outcomes rather than advertise a uniformly
successful method: near-nominal marginal coverage, persistent sparse-region undercoverage,
and vacuous density-ratio weighting under severe overlap loss.
