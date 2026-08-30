# Paper 2 evidence-locked outline

## Working title

**Curvewise Conformal Prediction Bands for Periodic PMSM Torque Surrogates under
Design-Distribution Shift**

## Evidence-locked claim

A max-error split-conformal wrapper provides near-nominal marginal coverage for complete
120-angle PMSM torque curves on the broad uniform benchmark, but aggregate calibration hides
severe sparse-geometry undercoverage; geometry support and target-density overlap must be
audited separately.

## Primary evidence

Using the Fourier-11 ARD Gaussian process and primary split:

- fixed internal test (200 designs): global and geometry-scaled 90% coverage are both 0.9200;
- large uniform evaluation (11,250 designs): global coverage 0.9029 at half-width 0.007125;
  scaled coverage 0.8996 at mean half-width 0.006806;
- Gaussian density shift (10,000 designs): both methods cover 1.0000; geometry scaling cuts
  mean half-width from 0.007125 to 0.005601 (21.4%);
- sparsest uniform geometry-distance quintile: global coverage 0.7613 and scaled coverage
  0.7831 despite 0.9029/0.8996 aggregate coverage;
- the geometry-only support warning rejects 5.511% of uniform designs and no Gaussian
  designs; accepted uniform global coverage is 0.9185;
- across five split seeds, uniform global coverage ranges 0.8799--0.9108 and scaled coverage
  0.8893--0.9131;
- source-style accuracy sanity check: fixed-200 waveform MAPE is 0.003466 as a fraction,
  close to the source study's DFT--GP 0.0037 at 1,200 training designs, but the implementations
  and partitions differ and this is not an exact reproduction.

## Post-primary weighted diagnostic

- disjoint 5,625-design uniform evaluation half: held-out domain AUC 0.5059, calibration ESS
  516.5/600, all bands finite, 90% coverage 0.9198, half-width 0.02503;
- disjoint 5,000-design Gaussian evaluation half: held-out domain AUC 1.000, calibration ESS
  4.31/600, maximum normalized source-calibration weight 0.3970, and 0/5,000 finite bands at
  both 90% and 95%; the vacuous result is retained without clipping.

These are independent simulated designs from one two-dimensional quarter-symmetry PMSM
model. They are not hardware, cross-machine, cross-topology, three-dimensional, or
simulator-discrepancy evidence.

## Manuscript structure completed

1. Introduction: complete-period reliability as a different endpoint from mean prediction
   error and population torque statistics.
2. Related work: electric-machine Fourier response surfaces, functional conformal bands,
   scientific surrogates, and covariate shift.
3. Data and audit: all 23,250 designs, immutable roles, source physics, and no exact overlap.
4. Methods: Fourier-11 response surfaces, full-curve max score, geometry scaling, support
   p-value, and post-primary estimated weighted conformal.
5. Results: four predictors, two alpha levels, three distributions, distance quintiles,
   five seeds, support warning, overlap collapse, and computational cost.
6. Discussion and limitations: marginal versus conditional coverage, geometric support
   versus density overlap, simulator scope, and required prospective validation.

## Main figures completed

1. data-role and conformal workflow;
2. coverage versus mean half-width across models/distributions;
3. coverage and error by geometry-distance quintile, including the 0.761 sparse-tail result;
4. five-seed coverage/width sensitivity;
5. representative covered, rescued, and missed complete curves.

## Submission-gate result

- mechanical manuscript-evidence validation passes against the per-design and weighted
  outputs;
- all 10 citation keys resolve and the bibliography has no duplicated DOI;
- generated supplementary material and the self-auditing reproducibility bundle pass drift
  and member-hash checks;
- the journal-neutral 15-page PDF has been visually inspected page by page; the DOCX passes
  structural audit, while its final visual render awaits Word or LibreOffice on the
  submitting author's machine;
- the claim boundary and negative results are explicit throughout.

No scientific experiment remains before submission. Author identities, funding/CRediT,
repository DOI, target-journal template, and final DOCX rendering are intentionally left to
the submitting authors.
