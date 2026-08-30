# Paper 3 development protocol and amendment log

## Scope and evidential boundary

Paper 3 develops and selects an operating-conditioned, healthy-only detector on one
dual-three-phase PMSM. The development table contains eight healthy physical records and
48 inter-turn-fault records across eight commanded loads. Model fitting, residual geometry,
support estimation, and conformal calibration use healthy records only. Development fault
labels may select among frozen candidate methods. They cannot support an independent-machine
claim.

The independent confirmation dataset is the PMSG dataset at DOI
`10.5281/zenodo.15741561`. Its repository filenames and metadata have been enumerated, but no
signal array has been deserialized, plotted, summarized, or used for a decision as of this
protocol revision. A metadata-size query inadvertently fetched some Git objects containing
MAT blobs; signal values remain unparsed and uninspected. The final PMSG method and protocol
must be frozen before the first signal reveal.

## Frozen development inputs

- Outcome signals: three phase currents only, represented by the 26 scale-free features in
  `PAPER3_OUTCOME_FEATURES`.
- Exogenous context: window-mean commanded speed (`Speed_requred_rpm`) and filename load.
- Excluded from context and outcomes: measured speed, fault current, relay state, voltage,
  dq variables, absolute current scale, and current-derived `fundamental_hz`.
- Window/block unit: non-overlapping 0.2 s windows, maximum within each 3 s block, maximum
  across the two subsystems.
- Threshold: 24 disjoint healthy calibration blocks and upper-tail split-conformal p-values
  at alpha 0.05. The blocks are temporally ordered units from only three physical healthy
  records per fold, so finite-sample exchangeability is not claimed.

## Eight-fold load protocol

The ordered grid is `[0, 5, 10, 15, 20, 25, 30, 35]` Nm and each load is held out once. Each
fold contains four fit and three calibration loads. For the six primary interior tests, fit
always contains 0 and 35 Nm plus a lower and upper bracketing load; for 5 and 30 Nm a central
anchor supplies the fourth distinct fit load. The three remaining non-test loads calibrate.
For the 0 and 35 Nm stress folds, the four fit loads lie strictly on the available side. This
construction ensures every calibration load lies within the fit load range and every primary
test load is an interpolation. Exact assignments are mechanically emitted in
`fold_assignments.csv`. Roles are assigned without fault measurements.

For every method and fold, the two subsystem models are fitted separately. A common support
model uses only fit and calibration context. A block is actionable only if all 15 windows of
both subsystems are inside the support radius. Abstention is reported separately and is never
counted as a correct healthy decision or a detected fault.

## Candidate selection rule

A candidate is eligible when, on the six interpolation loads 5--30 Nm, pooled actionable
healthy-block FAR is no greater than 0.05 and pooled fault-block abstention is no greater than
0.20. Among eligible methods, maximize fault-record-macro actionable detection, then prefer
lower FAR, lower abstention, and the earlier frozen method order. The two boundary loads are
reported as extrapolation stress tests but cannot select the method. This is a development
selection using fault labels, not a confirmatory test.

## Amendment A1 — load-role geometry

The first executable attempt used calibration offsets `{1, 3, 5}` and fit offsets
`{2, 4, 6, 7}`. On the 0 Nm outer fold, every test block was outside the support radius for
every method; consequently no candidate met the frozen 0.20 abstention guardrail and no method
was selected. Fault results from that aborted development run were visible, so the rerun is
explicitly developmental.

Before any independent PMSG signal reveal, the offsets were changed to `{2, 4, 6}` for
calibration and `{1, 3, 5, 7}` for fit. The reason is context geometry alone: the nearest
5 Nm neighbor of every held-out load is now in the fit set, including both grid boundaries.
The FAR and abstention guardrails, candidate models, features, scoring, alpha, and selection
objective were not relaxed. No further load-role amendment is allowed after the PMSG reveal.

## Amendment A2 — interpolation support and boundary stress tests

The A1 rerun showed that the nearest-neighbor radius alone treated the held-out 0 Nm load as
supported, and all 8 healthy blocks at that unseen lower boundary alarmed. This invalidated the
interpretation of the radius as an interpolation-support rule; no candidate passed selection.

Before independent PMSG signal reveal, support was therefore strengthened using only operating
context: a point must lie within the minimum and maximum of every healthy-fit context axis as
well as within 1.1 times the maximum healthy-calibration nearest-fit distance. Fold roles were
also made geometry-explicit: all primary test and calibration loads are inside the healthy-fit
load range, while 0 and 35 Nm are deliberately outside it when held out. The 1.1 margin was the
smallest checked value that covered all healthy windows at the six interior held-out loads;
both boundary tests remain rejected. The primary selection population is consequently the six
interpolation folds, while both boundary folds remain fully reported extrapolation stress
tests. Fault scores did not determine the 1.1 margin. No post-reveal support adjustment is
allowed.
