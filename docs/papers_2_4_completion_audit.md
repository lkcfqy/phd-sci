# Papers 2--4 completion audit

Updated: 2026-08-21

## Verdict

Papers 2, 3, and 4 each satisfy the repository's technical definition of an independent,
submission-ready SCI manuscript package. This means that the scientific analysis, manuscript,
figures, supplementary evidence, mechanical claim validation, reproducibility bundle, and rendered
review files are complete. It does not mean that a paper has been submitted, peer reviewed, or
accepted.

## Completion rule

A paper is counted as technically complete only if all of the following are evidenced in the
current worktree:

1. a distinct scientific question, dataset role, and primary endpoint;
2. a complete English manuscript with limitations and unfavorable results retained;
3. publication figures and a generated supplement;
4. a validator that checks quantitative claims against frozen result files;
5. anonymous DOCX and PDF review files with structural and visual QA;
6. a hash-audited reproducibility bundle that excludes restricted raw third-party data; and
7. repository-wide static analysis and tests passing after the final artifact build.

## Requirement-by-requirement evidence

| Requirement | Paper 2: torque uncertainty | Paper 3: alarm calibration transport | Paper 4: electrothermal transport |
|---|---|---|---|
| Independent question | Simultaneous full-curve uncertainty and support warning for a 120-angle PMSM torque surrogate | Whether a healthy-only alarm operating point survives a frozen second-machine/laboratory reveal | Whether source thermal dynamics, five-minute source-prior calibration, and uncertainty transport to a second PMSM |
| Primary evidence unit | 23,250 independent simulator design rows; full 120-angle curve is one prediction object | Complete physical signal files/sessions; windows are not treated as independent machines | Complete operating profiles; seconds are not treated as independent machines |
| Complete manuscript | 5,158 words, 5 tables, 5 figures, 10 cited references | 5,240 words, 5 tables, 5 figures, 28 cited references | 5,919 words, 4 tables, 5 figures, 21 cited references |
| Negative evidence retained | Sparse uniform-tail coverage 76.13%/78.31%; Gaussian weighted method has 0/5,000 finite bands | Independent confirmation has 71/216 pre-fault session alarms; all seven methods fail the 5% FAR gate | Raw transport degrades 13.12-fold; source-prior calibration is worse than target-only overall, clips 999 times, rejects 62.5%, and needs 106.07 degrees C mean half-width for 15/16 joint coverage |
| Anonymous review files | 15-page PDF and DOCX; native Word render also inspected over 15 pages | 16-page journal-neutral PDF; 15-page native Word render inspected | 16-page journal-neutral PDF; 16-page native Word render inspected |
| Supplement | 4-page landscape PDF, 11 tables | 4-page landscape PDF | 7-page landscape PDF, 10 tables |
| Evidence validator | `results/paper2_evidence_validation/evidence.json`: pass | `papers/paper3_calibration_transport/evidence_validation.json`: pass | `papers/paper4_thermal_transport/evidence_validation.json`: pass |
| Reproducibility bundle | 84 source artifacts; SHA-256 `01b6673c3c45e2a8602198ec5a68be13b9105d2d18a0b09685bf50930ca55ecb` | 120 source artifacts; SHA-256 `e5c754bf20856196e90e66682c69ba1abc32e4a05d4c950945cbd3a7222a2b3e` | 79 source artifacts; SHA-256 `f7d59c00303252cb07ef389a2e71c757379cfd976ecb6c9249d8b18cc9e904a0` |
| Bundle data boundary | Raw public simulator files excluded | Raw and processed third-party signal features excluded | Raw third-party datasets excluded |
| Final status | **Technical package complete** | **Technical package complete** | **Technical package complete** |

## Independence audit

- Paper 2 studies electromagnetic design-to-torque surrogate uncertainty. It uses no Paper 3 fault
  endpoint and no Paper 4 temperature profile.
- Paper 3 studies current-only healthy-alarm calibration and prospective failure on an independent
  PMSG archive. Its endpoint is session false-alarm and short-horizon fault detection, not torque or
  temperature regression.
- Paper 4 studies continuous winding/stator-core/rotor temperature state rollout across two PMSMs.
  Its endpoint is profile-macro recursive error, numerical safety, support, and trajectory-band
  utility, not fault classification.
- The three papers therefore do not reuse one held-out target or one primary endpoint as three
  nominally different results. Shared practices such as hashing, record-level splitting, and honest
  negative-result reporting are methodology standards rather than duplicated scientific claims.

## Final verification evidence

The final repository run on 2026-08-21 produced:

- `ruff check .`: passed;
- `pytest -q`: passed;
- `pytest --collect-only`: 271 tests collected;
- all three quantitative evidence validators: passed;
- all three reproducibility-bundle member/hash audits: passed; and
- page-by-page raster inspection of all manuscript and supplementary PDFs, plus native Microsoft
  Word rendering of the three anonymous DOCX manuscripts: passed without clipping, overlap,
  missing figures, broken tables, detached captions, or missing glyphs.

## Items intentionally left for the authors

The following are not scientific-analysis gaps and cannot be completed safely without the author
team and target-journal decision:

- author names/order, affiliations, e-mails, ORCIDs, corresponding author, and CRediT roles;
- funding, acknowledgments, competing-interest, and generative-AI declarations approved by all
  authors;
- a public code/data companion URL and archival DOI;
- target-journal template, current word/figure/reference rules, cover letter, highlights, and
  suggested reviewers; and
- a final native render after journal-specific pagination changes.

The papers should be described as three completed technical submission packages, not as three
submitted or accepted SCI publications.
