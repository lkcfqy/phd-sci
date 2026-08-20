# Frozen External Failure Diagnostics

This is a post-reveal, analysis-only audit. No estimator was refit, no feature or
threshold was changed, and no diagnostic replaces the frozen primary endpoint.

## Exact findings

- Proposed block detection was 0.0260 over the
  first four blocks, 0.1429 over the first seven,
  and 0.2500 over all eight. Record-any alarm rose
  from 0.1042 to
  0.5208 and finally
  1.0000.
- Proposed's median first alarm was block 6.0,
  approximately 1642.8 rpm using the matching
  healthy load record. RPM is a proxy, not a measurement copied from a fault record.
- Proposed pooled AUROC was 0.6354; the equal-weight mean
  of eight block-position-specific AUROCs was
  0.8047. The latter shows fault information
  after matching acceleration position, but is exploratory.
- Proposed score drift was strong in both held-out health
  (Spearman block-score 0.8361) and
  faults (0.8212). Ordered blocks are
  dependent, so these correlations are descriptive.
- Target MinCovDet achieved 0.7005 detection and
  0.9268 AUROC. Its paired record advantage over Proposed
  was 0.4505, with unadjusted bootstrap 95%
  interval [0.4062,
  0.4948] and Holm-adjusted p
  0.001000.
- In the same-estimator MinCovDet contrast, target-only minus source+target detection
  was 0.3984, interval
  [0.3542,
  0.4427]. This is evidence of conditional negative
  transfer on this motor, not a cross-motor population effect.

## Interpretation boundary

All 48 fault records are operating-condition records from one physical external motor.
The paired bootstrap resamples complete records within fault-turn strata and quantifies
variation conditional on this motor; it cannot create independent motors or prove
record independence. Holm adjustment controls only the listed family of post-reveal
method comparisons. Per-block AUROC, first-alarm RPM, and speed correlations diagnose
the frozen failure and must not be presented as new confirmatory endpoints.
