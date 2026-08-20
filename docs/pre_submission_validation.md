# Pre-submission evidence validation

Date: 2026-08-21
Audience: authors and supervisor
Decision: whether the analysis is sufficiently supported for journal submission

## Overall assessment: Share with caveats

The paper's central claim is supported as a conditional, single-external-motor result:
a detector with strong exploratory same-family performance failed after a frozen
cross-dataset reveal, while preimplemented target-only controls performed better. The
audit found no high-severity numerical contradiction. Three presentation risks were
corrected before rebuilding the submission package: a fault-turn/phase confound, unequal
load support in pooled external AUROC, and a 0.01 percentage-point interval-rounding
discrepancy.

This rating does not mean that cross-motor population generalization has been
established. It means that the manuscript can be shared if its existing evidence
boundaries remain prominent.

## Question, sources, and experimental units

- Primary question: does healthy-only source augmentation retain alarm performance when
  moved across motor capacity, winding topology, load, speed trajectory, and measurement
  chain without using target-fault labels?
- Exploratory source-family dataset: three KAIST PMSMs; the outer unit is one physical
  motor, but each motor has only one unique healthy time series.
- Frozen external dataset: one dual-three-phase PMSM; 48 fault records are recorded
  operating conditions from that one motor, not 48 independent machines.
- Secondary transient stress test: one 200 W and one 20 kW PMSM; the primary parser
  accepted 0/21 records, and the repaired quantitative sensitivity is limited to the
  single 200 W motor.
- Block rows are ordered observations within records. They are not independent motor or
  session replications.

## Methodology review

The target-fault-blind fitting and thresholding contract is consistent with the saved
protocols and reveal logs. KAIST results are correctly labeled exploratory because
target faults were inspected during development. The external primary method, feature
parser, calibration scores, thresholds, method set, and reveal manifest are preserved in
pre-reveal commits. Post-reveal diagnostics do not refit or rethreshold the primary
detector.

Record-level paired comparisons use complete fault records and turn-count strata. Their
intervals are conditional on the recorded conditions of one motor. Wilson intervals and
conformal p-values are descriptive because the calibration and test blocks come from a
small number of continuous records.

## Issues found and disposition

1. **Medium — fault-turn count and phase were confounded but not stated prominently.**
   Lower-grain external predictions show the fixed mapping U for 1/3/5/6 turns and V for
   2/4 turns. The manuscript, supplement, heatmap note, project findings, and reveal log
   now state that turn and phase effects cannot be separated.
2. **Medium — pooled external AUROC has unequal load support.** The 384 fault blocks span
   eight loads, while the 32 held-out health blocks come from four loads. The manuscript
   and supplement now describe pooled AUROC as a descriptive, non-load-matched ranking
   statistic.
3. **Low — one paired interval was rounded inconsistently.** The target-MinCovDet-minus-
   Proposed interval is `[40.62, 49.48]` percentage points in the frozen output. The main
   text and internal findings now use 40.62 rather than 40.63.
4. **Low — abstract scope could be read as ignoring the auxiliary third dataset.** It now
   identifies the headline experiment as the `primary two-dataset analysis`; the
   separately and prospectively frozen transient compatibility audit remains explicitly
   non-confirmatory.

## Calculation spot-checks

The reusable audit `scripts/validate_manuscript_evidence.py` recomputed the following
from lower-grain prediction and compatibility tables rather than copying manuscript
values:

- KAIST Proposed: 1,608/1,680 fault blocks detected, 0/42 later-time healthy alarms,
  mean detection 95.71%, worst motor 90.00%, and mean fold AUROC 0.99932.
- KAIST balanced Isolation Forest: 0/42 healthy alarms and 96.07% record-macro
  detection; the paired Proposed-minus-baseline interval crosses zero
  (`[-3.93, 3.45]` percentage points).
- External Proposed: 96/384 fault blocks, 1/32 held-out health blocks, Wilson upper
  15.74%, AUROC 0.6354, 0 alarms in blocks 0--2, and 48 alarms in block 7.
- External target MinCovDet: 269/384 fault blocks, 0/32 health blocks, AUROC 0.9268;
  paired target-MinCovDet-minus-Proposed difference 45.05 percentage points.
- Proposed load endpoints: 56.25% at 0 N m and 12.50% at 35 N m.
- Target MinCovDet five-seed sensitivity: 65.36%--77.08% detection, 0--2/32 health
  alarms, and 3/5 seeds passing H1.
- Sampling-rate control: Proposed changed from 25.00%/0.6354 to 24.74%/0.6331 with
  health alarms unchanged at 1/32.
- Transient audit: frozen parser 0/21; repair 12/12 for 200 W and 4/9 for 20 kW; primary-
  seed Proposed and target MinCovDet both retained zero thresholded early detection on
  the 200 W sensitivity.

The machine-readable output is
`results/manuscript_evidence_validation/evidence.json`.

## Reference and presentation review

The reference metadata audit resolved all 34 cited identifiers: 32 DOI records through
Crossref or DataCite and two DOI-free PMLR records through their publisher pages. All 34
passed normalized title, first-author, and available year checks. The dated table is in
`docs/reference_metadata_audit.md`; resolution verifies metadata existence, not the
correctness of every narrative interpretation.

The final external heatmap labels every turn row with its fixed phase. Its formal
caption states the non-identifiability directly. To follow the journal artwork rule,
the separate illustration files contain no figure-wide titles, subtitles, or
caption-like footer paragraphs; explicit denominators, held-out-health scope,
time/block ordering, and post-reveal status are carried by the manuscript captions.
Final PDF layout review is recorded separately in `submission/jeet/QA_Report.md`.

## Required caveats for submission

- The external conclusion is conditional on one physical motor and one recorded
  acceleration design.
- Turn-count and phase effects are not separately identifiable in the external grid.
- Pooled external AUROC is not load matched.
- Target MinCovDet is a preimplemented comparator, not the pre-reveal primary; its
  exact primary-seed operating point is not stable across all five seeds.
- The compound shift does not identify a causal contribution from topology, speed,
  load, sampling rate, controller, or sensor chain individually.
- Neither Wilson bounds nor conformal p-values are population-level safety guarantees
  under the observed temporal/session dependence.
- The secondary transient analysis remains a failed frozen compatibility test plus a
  post-reveal single-motor sensitivity, not a third confirmation dataset.

## Incomplete handoff blockers

- Author names/order, official affiliations, corresponding author, ORCIDs, funding,
  acknowledgments, and verified CRediT roles are still author-owned inputs.
- Microsoft Word/LibreOffice is unavailable on this workstation. The regenerated DOCX
  files require one final native-Word field update and page inspection after author
  metadata are inserted.
- The active JEET upload route, indexing, and fees must be rechecked on the submission
  date.
