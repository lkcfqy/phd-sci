# Paper 2 additional figure contracts

## Protocol workflow

- **Question:** How are the 23,250 designs partitioned and how do geometry, torque labels,
  conformal calibration, support testing, and the post-primary weighted diagnostic flow?
- **Takeaway:** Predictor fitting, calibration, fixed internal testing, large distribution
  evaluation, and unlabeled density-ratio fitting have visibly separate roles.
- **Form:** Static labeled flow diagram; no quantitative scale.
- **Palette:** One blue root for predictor flow, one orange root for calibrated uncertainty,
  grey for data roles; node text and arrows also encode meaning without color.
- **Outputs:** `paper2_protocol_workflow.png` and `.pdf`; inspect the 300-dpi PNG and a
  rasterized PDF page.

## Representative simultaneous bands

- **Question:** What do covered, rescued, and still-missed complete torque curves look like?
- **Takeaway:** Geometry scaling can widen a sparse-design band enough to rescue some global
  misses, but it does not remove all sparse-region failures; the Gaussian band can be
  narrower near nominal geometry.
- **Data sufficiency:** Four deterministic examples from 11,250 uniform and 10,000 Gaussian
  labeled simulator designs. Selection is rule-based, not aesthetic: median-error covered
  dense uniform; median-error sparse uniform global miss/scaled hit; median-error sparse
  uniform miss by both; median-error covered Gaussian near the median geometry scale.
- **Form:** Four small-multiple line-and-band panels on shared angle and torque scales.
- **Encodings:** truth dark solid; point prediction blue solid; global boundaries blue
  dashed; geometry-scaled interval orange translucent fill and edge. Line style and labels
  preserve meaning in grayscale.
- **Outputs:** `paper2_representative_curves.png` and `.pdf`, plus a machine-readable
  `selection_manifest.csv`; inspect both raster and rasterized vector output.
