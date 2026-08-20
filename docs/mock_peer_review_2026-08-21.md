# Internal pre-submission peer-review audit

Date: 2026-08-21

Target manuscript: *When Healthy-Only Transfer Fails in PMSM Stator-Fault Detection:
A Leakage-Resistant Cross-Dataset Evaluation*

This is an internal red-team record, not a document for journal upload. It evaluates
whether the present claims are supported and identifies changes that can be made without
using external fault labels to redesign the frozen detector.

## Editorial view

**Recommendation before the changes below:** major revision, principally because the
paper must be read as an evaluation contribution rather than a new-detector paper.

**Recommendation after the changes below:** technically submission-ready, with a
material but clearly bounded risk of rejection for limited independent-motor replication.
The work is in scope for an electrical-machines journal, but acceptance cannot be
guaranteed and the single external motor remains the decisive scientific limitation.

## Reviewer 1: electrical machines and drives

| Concern | Evidence inspected | Resolution/status |
|---|---|---|
| External machine description was too thin for an electrical-machines audience. | The Zenodo record points to [Kozovský et al., IECON 2022](https://doi.org/10.1109/IECON49645.2022.9968364). Its Table I reports 30.16 kW nominal power, 200 V DC link, 107 A maximum continuous current, ten pole pairs, and 8000 rpm nominal speed. | Added the source-backed parameters to Section 5.2 and the 30.16 kW rating to the abstract and cover-letter pitch. The analyzed interval remains reported by measured speed, not inferred from the filename. |
| A 0.2 s window could be mistaken for proof of online feasibility. | No end-to-end latency, memory, or embedded-hardware benchmark exists. | Added an explicit offline-only boundary in the Discussion. No real-time or embedded claim is made. |
| Compound topology, controller, speed, load, and sampling shifts prevent causal attribution. | External protocol and feature-drift diagnostics. | Already explicit in the limitations; the 100 kHz-to-10 kHz controlled arm rules out only a sampling-rate-only explanation under this pipeline. |
| Fault-turn and fault-phase effects may be confounded. | Frozen 6-by-8 external file grid. | Already corrected throughout: turns 1/3/5/6 use phase U and 2/4 use phase V, so separate effects are not claimed. |

## Reviewer 2: machine learning and statistics

| Concern | Evidence inspected | Resolution/status |
|---|---|---|
| Near-ceiling KAIST results could reflect development reuse. | Reveal logs and Section 5.1. | KAIST is labeled exploratory in the abstract, methods, results, and limitations. The external fault reveal is the primary confirmatory-style stress test. |
| Conformal and Wilson quantities may be overinterpreted under time dependence. | Ordered calibration/test partitions and manuscript Sections 3.2, 4, 5.2, and 7. | Every coverage or risk statement is empirical/descriptive; no arbitrary-dependence, motor-population, or safety guarantee is claimed. |
| Forty-eight external records are not forty-eight motors. | Dataset manifest and record hierarchy. | The manuscript repeatedly states that all 48 records belong to one physical motor. Bootstrap intervals are conditional recorded-condition summaries. |
| Post-reveal comparisons could silently replace the failed primary method. | Frozen metadata, reveal log, supplement, and figures. | The Log-Euclidean detector remains designated as Proposed and its failure remains primary. Target MinCovDet is reported as a post-reveal comparator, including five-seed instability. |
| Source-assisted and target-only comparisons need a common-algorithm control. | Eleven-method external table and paired supplement. | Same-family target-only versus source-plus-target contrasts are reported for OC-SVM, Isolation Forest, and MinCovDet; covariance contrasts are explicitly described as not holding the estimator fixed. |

## Reviewer 3: reproducibility and presentation

| Concern | Evidence inspected | Resolution/status |
|---|---|---|
| The freeze was not an externally registered preregistration. | Git history and protocol wording. | Claims now say prospectively frozen or pre-reveal frozen and explicitly state that this was not an external preregistration. |
| Figure artwork contained narrative titles/captions. | All eleven vector PDFs and journal artwork guidance. | Overall titles and caption-like footers were removed; denominators and caveats are synchronized in manuscript captions. |
| Headline values might drift from lower-grain outputs. | Mechanical evidence validator and generated supplement. | All headline denominators and values are recomputed from frozen result tables; the repository and isolated code bundle pass their complete test suites. |
| A failed secondary parser could be mistaken for a third validation success. | Section 6.11 and Online Resource 1, Section S9. | The immutable 0/21 compatibility failure is retained, and the repaired 200 W analysis is labeled post-reveal, single-motor, and non-confirmatory. |

## Remaining non-technical submission gates

1. Obtain approved author order, affiliations, ORCIDs, corresponding-author details,
   CRediT roles, funding, and acknowledgments.
2. Obtain all-author approval of the manuscript, declarations, AI-assistance statement,
   supplement, and cover letter.
3. Open the completed DOCX files in the exact Microsoft Word version used for upload,
   update fields, and inspect every page.
4. Confirm the active JEET submission route while the linked Editorial Manager page
   displays its implementation-mode warning.
5. Recheck indexing and charges on the submission date.

## Acceptance-critical future evidence

If reviewers require stronger population generalization, the correct addition is not a
post-reveal retuning on the current external motor. It is a prospectively frozen test on
additional independent motors or laboratories, with independent healthy sessions,
operating-condition-aware target-only and source-assisted models, and predeclared early-
trajectory detection and false-alarm criteria.
