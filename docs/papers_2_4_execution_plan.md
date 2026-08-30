# Papers 2--4 execution plan

Updated: 2026-08-21

Final requirement-level evidence is recorded in `docs/papers_2_4_completion_audit.md`.

## Decision

The remaining three papers are now separated by **scientific endpoint**, not by slicing
Paper 1 analyses. Paper 2 predicts periodic electromagnetic output with calibrated
curve-level uncertainty; Paper 3 detects faults after conditioning out normal operating
variation; Paper 4 updates an electrothermal state online across machines. A result may be
cited by a later paper, but no headline experiment, held-out target, or primary endpoint is
reused as if it were new evidence.

| Paper | Independent question | Primary endpoint | Data needed for a defensible submission | Current gate |
|---|---|---|---|---|
| 2 | Can a periodic torque surrogate attach calibrated simultaneous bands and a geometry-only support warning under design-density shift? | Full-curve coverage and band width over 120 angles | 23,250 released PMSM simulations, with fit/calibration/test roles separated | **Technical submission package complete; author/journal fields remain** |
| 3 | Does a preselected healthy-only alarm operating point survive a protocol-frozen external machine/laboratory reveal? | Pre-fault session FAR, fault-record detection within 0.4 s, alarm time, abstention | One dual-three-phase PMSM for development and one independently collected PMSG for confirmation | **Technical submission package complete; author/journal fields remain** |
| 4 | Do electrothermal source models, source priors, and uncertainty bands transport across PMSMs under a fixed commissioning budget? | Cross-profile/cross-machine recursive temperature error, numerical guard activation, support-conditioned risk, and trajectory-band coverage/width | 52-kW public PMSM temperature data and a second IPMSM dataset, with raw-data, profile, protocol, and selection hashes frozen | **Technical submission package complete; author/journal fields remain** |

## Paper 2: curvewise torque-surrogate risk control

Working title:

> **Curvewise Conformal Prediction Bands for Periodic PMSM Torque Surrogates under
> Design-Distribution Shift**

The released source study already established DFT reduction and GP/PCE/FNN response
surfaces. Paper 2 therefore does **not** claim a new Fourier surrogate. Its separate
contribution is simultaneous uncertainty for the entire 120-point curve, geometry-density
adaptation, and an explicit support warning. The primary large tests contain 11,250 new
uniform designs and 10,000 Gaussian designs; the latter changes density but remains inside
the observed design ranges.

Submission gate:

1. **passed:** source-style ARD Gaussian-process accuracy is comparable to the source study,
   with implementation differences explicitly disclosed;
2. **passed:** 90% and 95% full-curve coverage, width, and all distance quintiles are frozen;
3. **passed:** five deterministic fit/calibration split seeds are complete;
4. **passed:** every result and figure states the one-simulator 2-D scope;
5. **passed:** a complete 5,000-word manuscript retains sparse-tail undercoverage and vacuous
   weighted-conformal results;
6. **passed:** mechanical evidence validation, a four-page rendered supplement, an 84-file
   hash-audited reproducibility bundle, and full visual QA of both the 15-page manuscript PDF and
   the 15-page native Microsoft Word render;
7. **author-side only:** insert identities/declarations/repository DOI, apply the selected
   journal template, and visually inspect the final DOCX in Word or LibreOffice.

## Paper 3: protocol-frozen alarm-calibration transport

Working title:

> **When Healthy-Only Alarm Calibration Does Not Transport Across Permanent-Magnet
> Synchronous Machines: A Protocol-Frozen External Validation**

The development-selected spline residual produced 1/48 actionable healthy-block alarms and
82.29% record-macro block detection on the six interpolation loads of one dual-three-phase
PMSM. Its algorithm, feature schema, healthy roles, time windows, alpha, and failure gates
were then hash-frozen before any signal array from an independently collected 2.5 kVA PMSG
was deserialized. The confirmation failed: 71/216 pre-fault sessions alarmed and 156/216
fault sessions were detected within 0.4 s. All seven frozen methods exceeded the 5% PMSG
session-FAR gate. Session anchoring reduced, but did not eliminate, calibration failure in
explicitly post-reveal analyses.

Submission gate:

1. **passed:** immutable PMSG tag/commit/tree, 225-file inventory, signal whitelist, split,
   time windows, alpha, and pass/fail gates are recorded before signal reveal;
2. **passed:** pre-fault session FAR, fault-record detection, first/second-window alarm,
   right-censoring, and abstention are reported at the physical-file level;
3. **passed:** all comparators and the failed joint confirmation remain visible; no
   post-reveal repair is promoted to independent evidence;
4. **passed:** five figures, five manuscript tables, a four-page generated supplement, an
   evidence validator, and both DOCX and PDF submissions passed visual/structural QA;
5. **passed:** the 120-file anonymous reproducibility bundle audits every archived hash and
   excludes raw and processed signal-feature data;
6. **author-side only:** insert identities/declarations/repository DOI and apply the selected
   journal template.

The paper claims conditional failure across one motor and one generator, not a fleet-level
PMSM generalization estimate and not causal attribution to any one domain-shift component.

## Paper 4: protocol-frozen electrothermal transport benchmark

Working title:

> **Do Electrothermal Models Transport Across PMSMs? A Protocol-Frozen Benchmark of
> Source Priors, Five-Minute Calibration, and Support-Aware Uncertainty**

This paper uses continuous thermal states, not Paper 3 fault labels. The source dataset contains
69 profiles from one 52-kW PMSM; the locked external dataset contains 16 profiles from a second
IPMSM. Eight methods receive the same five-minute commissioning prefix and are evaluated by
20-minute recursive rollout. All-profile results remain primary; a frozen support rule is reported
only as a secondary reject-option analysis.

Submission gate:

1. **passed:** complete-profile-disjoint source evaluation and a locked second-motor stress test;
2. **passed:** eight frozen target-blind or five-minute methods plus the published target-specific
   LPTN as a contextual oracle;
3. **passed:** the primary negative result is retained: the source-prior model is worse overall
   than target-only fitting and boundary persistence and activates 999 numerical guards on one
   external profile;
4. **passed:** trajectory bands expose the coverage--utility trade-off (15/16 joint external
   coverage only with 106.07 degrees C mean half-width), and the 62.5% support abstention is not
   hidden;
5. **passed:** one-, five-, and fifteen-minute commissioning sensitivity, support-conditioned
   analysis, uncertainty diagnostics, and all-profile comparisons are frozen;
6. **passed:** a complete manuscript, five figures, generated seven-page supplement, evidence
   validator, anonymous DOCX/PDF, and 79-file hash-audited reproducibility bundle are complete;
7. **author-side only:** insert identities/declarations/repository DOI and apply the selected
   journal template.

## Integrity rules shared by all three papers

- A table row is not automatically an independent physical replicate.
- Hyperparameters and thresholds are selected without target test labels.
- Every public archive is hashed and audited before modeling.
- A result inspected during feasibility work is labeled exploratory; it is not described as
  preregistered or blinded later.
- Negative transfer, failed coverage, or a strong simple baseline remains in the paper.
- A paper is counted as “complete” only after manuscript, independent evidence validator,
  reproducibility bundle, and rendered submission files all pass.
