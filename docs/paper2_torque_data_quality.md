# Paper 2 torque-data quality audit

Audit date: 2026-08-21

## Assessment: suitable for a simulation benchmark, not hardware validation

The six CSV files from Zenodo DOI
[10.5281/zenodo.15688397](https://doi.org/10.5281/zenodo.15688397) contain **23,250 unique
geometry--torque pairs** and passed the structural checks needed for Paper 2. They can
support a reproducible study of response-surface prediction and curvewise uncertainty.
They cannot support claims about another motor topology, three-dimensional end effects,
manufacturing asymmetry, sensor noise, controller dynamics, or real hardware.

## Dataset and grain

Each row is one independent parameter draw evaluated by the same deterministic,
two-dimensional quarter-symmetry PMSM model. Twenty geometric parameters map to one torque
period sampled at 120 angles from 0 to 29.75 degrees in 0.25-degree increments.

| Released table | Designs | Intended Paper 2 role |
|---|---:|---|
| `train_test` | 2,000 | 1,200 fit, 600 split-conformal calibration, 200 internal test |
| `uq_uniform` | 11,250 | large independent uniform evaluation |
| `uq_gauss` | 10,000 | design-density-shift evaluation |

## Checks and findings

- All parameter and torque cells are finite; no missing values were found.
- Parameter and torque row counts match within every released pair.
- All three tables have the same 20 parameter columns and the same 120-point angle grid.
- No duplicate parameter rows or duplicate torque curves occur within a table.
- No exact parameter row appears in more than one of the three tables.
- The minimum torque is 0.2966 and the maximum is 0.7028 in the released numerical units.
- Eleven retained real-FFT components capture a median of more than 99.99999% of discrete
  signal energy; the first-percentile retained fraction also exceeds 99.99996%.
- Of the 11,250 new uniform draws, 242 cross at least one *empirical* min/max from the 2,000
  development rows. This is expected from finite random samples and is retained as a useful
  support-boundary stress, not deleted.
- All 10,000 Gaussian draws lie inside the empirical development min/max in every parameter;
  this is a density shift toward the nominal design, not extrapolation beyond the box.

## Analytical risks

1. **Single simulator (high):** thousands of random designs do not create thousands of
   independent physical machines. Uncertainty bands cover simulator outputs, not model-form
   error relative to hardware.
2. **Known source task (high):** the source article already compared DFT/PCA/direct response
   surfaces and reported UQ means and standard deviations. Repeating that task is not novel.
3. **Symmetry assumptions (high):** the two-dimensional quarter model excludes asymmetric
   manufacturing tolerances and end effects.
4. **Feasibility inspection (medium):** aggregate target results were inspected before
   protocol v1 was written. Paper 2 must describe this honestly and use multi-seed stability,
   not a false preregistration claim.

## Reproducible evidence

Run:

```powershell
.\.venv\Scripts\python.exe scripts\audit_torque_dataset.py
```

Machine-readable outputs are written to `results/paper2_torque_data_audit/`, including the
input SHA-256 manifest, parameter summaries, cross-table overlap counts, and `audit.json`.
