# Reproducing Paper 3

This companion reproduces the protocol-frozen development analysis, independent PMSG
confirmation, explicitly post-reveal mechanism analyses, figures, evidence validation, and
journal-neutral manuscript for:

> *When Healthy-Only Alarm Calibration Does Not Transport Across Permanent-Magnet
> Synchronous Machines: A Protocol-Frozen External Validation*

The numerical analysis is deterministic given the two public archives and the recorded
software environment. Raw third-party signal files are intentionally excluded from the
reproducibility bundle.

## 1. Environment

Python 3.11 or newer is required. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,publication]"
```

The frozen run used Python 3.12.13 on Windows 11. Exact NumPy, pandas, SciPy, and
scikit-learn versions and the input hashes are written into the processed-data metadata and
result JSON files.

## 2. Public data

### Development dual-three-phase PMSM

The development archive is Zenodo DOI
[`10.5281/zenodo.13889418`](https://doi.org/10.5281/zenodo.13889418), CC BY 4.0. Download
the eight `flt0z` healthy files and the 48 frozen `flt1..6z{u|v}` fault files with:

```powershell
python scripts/download_external_pmsm_validation.py `
  --datasets dual_three_phase_health dual_three_phase_fault_reveal `
  --workers 4
```

The verified files are placed in
`data/raw/external_validation/dual_three_phase_health/`. There must be 56 MAT files: eight
healthy records and 48 fault records spanning eight commanded loads.

### Independent PMSG confirmation

The confirmation source is the PMSG benchmark described by DOI
[`10.1016/j.dib.2025.112040`](https://doi.org/10.1016/j.dib.2025.112040) and archived as
Zenodo DOI [`10.5281/zenodo.15741561`](https://doi.org/10.5281/zenodo.15741561), CC BY
4.0. The frozen repository state is GitHub tag `v1.1.0`, commit
`e02fba475cf82b375412a7382143dc29da5241ef`, tree
`65430929e4886935d463f1e1410b5476d255f4d4`.

```powershell
git clone --branch v1.1.0 --depth 1 `
  https://github.com/InnovaPower/MitDev-Eletrica.git `
  tmp/pmsg3_metadata_repo
```

The expected inventory is 225 three-second MAT files: nine standalone healthy records and
216 fault records. Only `t`, `Ia`, `Ib`, and `Ic` are deserialized by the signal builder.

## 3. Rebuild the development analysis

```powershell
python scripts/build_external_pmsm_health_features.py
python scripts/build_paper3_development_table.py
python scripts/run_paper3_development_benchmark.py
```

The first command emits 13,440 subsystem-window rows from 56 physical records. The second
attaches only filename/commanded operating context. The benchmark uses whole-record load
folds, selects among seven candidates using the six interpolation loads, and must reproduce
`spline_residual` as the selected development method.

## 4. Rebuild the PMSG reveal and confirmation

The historical metadata freeze cannot be recreated as a new blind event after the public
signals have already been inspected. The commands below reproduce its immutable inventory,
the strict parser audit, and the locked numerical analysis; the original chronology is in
`docs/paper3_reveal_log.md`.

```powershell
python scripts/freeze_pmsg_confirmation_metadata.py
python scripts/audit_pmsg_confirmation_container.py
python scripts/build_pmsg_confirmation_features.py
python scripts/run_pmsg_confirmation_analysis.py
```

The feature table must contain 2,493 windows from all 225 records. The frozen selected
method must reproduce 71/216 pre-fault sessions with at least one alarm and 156/216 detected
fault sessions within 0.4 s. All seven frozen methods must exceed the 5% PMSG session-FAR
gate; this negative result must not be replaced by a post hoc threshold.

## 5. Rebuild the post-reveal mechanism analyses

These analyses were designed only after the failed independent confirmation was known. They
are diagnostics and cannot replace it.

```powershell
python scripts/run_pmsg_session_anchor_exploratory.py
python scripts/run_pmsg_topology_crossfit_session_anchor.py
python scripts/run_pmsg_topology_crossfit_conditioned_anchor.py
```

The respective pooled pre-fault false-alarm counts are 17/216, 14/216, and 18/216; none
passes the original joint gate.

## 6. Rebuild figures, evidence, supplement, and submission files

```powershell
python scripts/make_paper3_figures.py
python scripts/validate_paper3_evidence.py
python scripts/build_paper3_supplementary_material.py
python scripts/build_paper3_supplementary_material.py --check
python scripts/build_paper3_submission.py
python scripts/build_paper3_submission.py --check
python scripts/build_paper3_supplementary_pdf.py
python scripts/build_paper3_supplementary_pdf.py --check
python scripts/build_paper3_reproducibility_bundle.py
python scripts/build_paper3_reproducibility_bundle.py --check
```

The evidence validator checks seven immutable hashes, all headline numerators and
denominators, the failed confirmation gates, the post-reveal counts, all 28 citations, and
both PNG/PDF versions of five figures.

## 7. Verification

```powershell
ruff check .
pytest -q
```

For submission, also render the final DOCX in Microsoft Word or LibreOffice and inspect
every page, then rasterize and inspect both PDFs. The frozen journal-neutral build contains
five figures, five manuscript tables, and 28 cited references.

## 8. Evidential boundary

The study contains two physical machines: one development PMSM and one confirmation PMSG.
The 48 development fault records and 216 PMSG fault records are conditions, not independent
machines. The external shift jointly changes machine role, winding topology, sensors,
sampling rate, controller/laboratory procedure, and fault construction. The study therefore
establishes a conditional calibration-transport failure; it does not identify a single
causal source of that failure or estimate fleet-population performance.

