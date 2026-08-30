# Paper 3 literature boundary and defensible contribution

Updated: 2026-08-21

## Answer first

Paper 3 is not defensible as the first healthy-only rotating-machine detector, the first
operating-conditioned detector, the first conformal anomaly alarm, or the first cross-machine
fault-diagnosis study. Its publishable contribution is narrower and empirical:

> A development-selected healthy-only current detector is carried through a signal-unrevealed,
> hash-frozen external PMSG confirmation with predeclared session-level failure gates; the
> resulting alarm-calibration failure is retained, and post-reveal repairs are explicitly
> sequestered and tested with topology-disjoint internal splits.

The headline is **calibration transport under compound machine/laboratory shift**, not a new
classifier or a universal claim that healthy-only detection fails.

## Closest prior work

| Literature | What is already established | What remains distinct here |
|---|---|---|
| Zafarani et al. (2018), DOI `10.1109/JESTPE.2018.2811538`; Urresty et al. (2013), DOI `10.1109/TPEL.2012.2198077` | PMSM inter-turn faults, current signatures, and the need to handle nonstationary speed/load are established. | Current features and speed/load conditioning are not claimed as novel; the endpoint is session alarm calibration after external transport. |
| Yang et al. (2023), DOI `10.1016/j.compind.2023.103878`; Yoon and Yu (2024), DOI `10.3390/app14010221` | One-class and self-supervised rotating-machinery detection can train on healthy data only. | Paper 3 freezes a selected method before a new signal reveal, evaluates record/session FAR, and does not use external faults to retune the confirmatory method. |
| Wang et al. (2025), DOI `10.1016/j.aej.2024.11.030` | Healthy-only anomaly detection based on stator current has been applied to permanent-magnet health monitoring. | That work does not establish transport of a frozen alarm threshold across an independently acquired PM synchronous machine/laboratory. |
| Li et al. (2020), DOI `10.1016/j.neucom.2020.05.014`; Li et al. (2023), DOI `10.1109/TII.2022.3174711`; Zhao et al. (2024), DOI `10.1016/j.ress.2024.109964` | Cross-domain and cross-machine fault diagnosis and domain generalization are mature research topics. | Those supervised/classification objectives differ from fault-blind healthy calibration and a fixed operational FAR gate. Paper 3 does not claim cross-machine DG novelty. |
| Farouq et al. (2021), DOI `10.1016/j.neucom.2021.08.016`; Farouq et al. (2022), DOI `10.1016/j.eswa.2022.116864`; Diallo et al. (2025), DOI `10.1016/j.jprocont.2025.103495` | Conformal anomaly alarms and false-alarm comparisons already exist in heterogeneous fleets and process monitoring. | Paper 3 applies a rank threshold as an auditable operating rule and reports when it fails under external shift; ordinary exchangeable coverage is not claimed for dependent windows. |
| Wheat et al. (2024), DOI `10.1109/ACCESS.2024.3497716` | Physical-run and part separation can reduce machinery-diagnosis results by more than 40 percentage points; random window splits are unsafe evidence for deployment. | Paper 3 separates physical records/topologies and makes the one-time external signal reveal part of the study design. |
| Lee (2026), PMLR 337 | Conformal performance can degrade under distribution shift, and shift detection alone need not predict failure severity. | Paper 3 provides an electrical-machine case with predeclared alarm gates and identifies session-to-session threshold instability as the unresolved mechanism. |
| Tominaga et al. (2025), DOI `10.1016/j.dib.2025.112040` | A 225-record PMSG current dataset supports controlled inter-turn/inter-winding fault studies at nine operating settings. | The dataset is used here as an independent signal-reveal target, not presented as a new dataset or a population of 225 machines. |

## What the evidence supports

1. On the development PMSM's six interpolation loads, the selected spline residual method
   achieved 1/48 actionable healthy-block alarms and 82.29% record-macro block detection.
2. On the frozen PMSG confirmation, the same algorithmic specification produced 71/216
   pre-fault session alarms and 156/216 detected fault sessions. The predeclared joint gate
   failed.
3. A post-reveal two-window session anchor reduced false alarms to 17/216, showing that
   session offset is a material part of the shift, but it did not satisfy the FAR gate.
4. Topology-disjoint matched-session and conditioned-anchor analyses retained 6.48--8.33%
   FAR and 70.83--71.30% detection, with 2.5--2.9-fold threshold variation across folds.
   Thus, context conditioning alone did not stabilize healthy calibration.

## Claims that must not appear

- "first healthy-only fault detector";
- "first cross-machine PMSM diagnosis";
- "distribution-free 5% session FAR";
- "external validation proves universal failure";
- "216 independent machines" or a machine-population confidence interval;
- "the session anchor is independently confirmed";
- "PMSG torque codes 52/64/80 are N m";
- "PMSG topology, acquisition, or generator operation is the identified causal source";
- "abstention solved extrapolation on the external bench" (all PMSG records were inside the
  filename-context support box, so external abstention was zero).

## Recommended contribution language

- "signal-unrevealed, hash-frozen external confirmation";
- "predeclared session-level alarm gates";
- "conditional failure on one independent PMSG bench";
- "post-reveal mechanism analyses retained separately from confirmation";
- "topology-disjoint internal validation exposed calibration-threshold instability";
- "current-only evidence under compound machine, topology, acquisition, and laboratory
  shift".

## Journal-facing value proposition

The paper is strongest for an instrumentation, measurement, reliability, or applied machine
learning venue that accepts rigorous negative external validation. It is weaker for a venue
expecting a new deep architecture or headline state-of-the-art accuracy. The practical lesson
is concrete: a low development false-alarm rate and an alpha-level rank threshold do not
authorize deployment on another PM synchronous machine; prospective target-session
calibration and repeated healthy sessions are separate design requirements.
