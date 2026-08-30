# Reproducing Paper 2

This companion reproduces the audit, model benchmark, conformal bands, distribution-shift
diagnostics, figures, evidence checks, and journal-neutral manuscript for:

> *Curvewise Conformal Prediction Bands for Periodic PMSM Torque Surrogates under
> Design-Distribution Shift*

The analysis is deterministic given the public source archive and the recorded software
environment. Raw data are intentionally not redistributed in this bundle.

## 1. Environment

Python 3.11 or newer is required. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,publication]"
```

The frozen run used Python 3.12.13, NumPy 2.5.2, pandas 3.0.5, and scikit-learn 1.9.0 on
Windows 11. Exact versions and input hashes are recorded in each `run_metadata.json` file.

## 2. Public data

Download the archive associated with DOI
[`10.5281/zenodo.15688397`](https://doi.org/10.5281/zenodo.15688397) and place these six files
directly in `data/raw/PMSM_torque_data/`:

| File | Expected SHA-256 |
|---|---|
| `train_test_parameters.csv` | `10c0b1b344d5addadacfad2b53ebe7d41e70f4e6ecc9fa8344fd840fbe8906a0` |
| `train_test_torque.csv` | `f9606c7e6b386e5eaf6537d63a745973d31fee6cb907101b85cd2c2d864cf39f` |
| `uq_uniform_parameters_11k.csv` | `020f4b85fff4475f9662b1246c85c3253398fbef8c2b72b4f59d69b8fa262e88` |
| `uq_uniform_torque_11k.csv` | `df1f8aa5bf6e139659a7f935fb31b3831c2403119086ebaa323af83d3242656c` |
| `uq_gauss_parameters_10k.csv` | `368832b4f571385788320c864a8a7a425da818b1acb5e66b6726e0d529088a40` |
| `uq_gauss_torque_10k.csv` | `ff85a001286dda41455e08d7ed6b269d7f0c9f16184f701af141cf848e3098e7` |

The source data are GPL-3.0-or-later. The associated article is DOI
`10.1007/s00366-025-02123-1`.

## 3. Rebuild the frozen results

Run the following commands from the repository root. The ARD Gaussian-process step is the
slowest; its frozen workstation time was about 41 seconds for fit and source-only selection.

```powershell
python scripts/audit_torque_dataset.py

python scripts/run_torque_conformal_benchmark.py

python scripts/run_torque_conformal_benchmark.py `
  --results-dir results/paper2_torque_seed_sensitivity `
  --models ard_gaussian_process `
  --seeds 20260821 1201 2402 3603 4804

python scripts/run_torque_weighted_conformal.py

python scripts/make_paper2_torque_figures.py
python scripts/make_paper2_torque_additional_figures.py

python scripts/validate_paper2_evidence.py
python scripts/build_paper2_supplementary_material.py
python scripts/build_paper2_supplementary_material.py --check
```

The primary benchmark writes 42,900 per-design ARD rows across the fixed internal, uniform,
and Gaussian evaluations. The weighted diagnostic uses disjoint target-covariate halves and
retains infinite bands rather than clipping them.

## 4. Rebuild the anonymous manuscript

```powershell
python scripts/build_paper2_submission.py
python scripts/build_paper2_submission.py --check
python scripts/build_paper2_supplementary_pdf.py
python scripts/build_paper2_supplementary_pdf.py --check
```

This creates:

- `papers/paper2_torque_uq/submission/Paper2_Manuscript_Anonymous.docx`
- `papers/paper2_torque_uq/submission/Paper2_Manuscript_Anonymous.pdf`
- `papers/paper2_torque_uq/submission/Paper2_Supplementary_Material.pdf`
- `papers/paper2_torque_uq/submission/build_metadata.json`

The builder performs structural audits for 5 figures, 5 tables, 10 cited references, the PDF
page count, and recoverable title/reference text. The evidence validator separately
recomputes the quantitative manuscript claims from frozen per-design outputs.

## 5. Verification

```powershell
ruff check .
pytest -q
```

For a submission handoff, also inspect every rendered PDF page. The checked manuscript contains
15 pages and the landscape supplement contains 4 pages. Both were inspected without clipped
figures, tables, equations, captions, references, or missing glyphs. The anonymous DOCX was also
rendered with Microsoft Word and its 15 pages were inspected. Repeat the native render after a
target-journal template changes pagination.

## 6. Evidential boundary

All 23,250 designs originate from one released two-dimensional, quarter-symmetry PMSM
simulator. Reproduction of these computations does not add validation on another simulator,
machine, topology, manufacturing process, or hardware experiment. The Gaussian weighted
diagnostic is deliberately negative: source-target overlap collapses and 0/5,000 bands are
finite. That result must not be replaced by a clipped finite interval.
