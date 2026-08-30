# Paper 3 signal-reveal and analysis-status log

Updated: 2026-08-21

## Evidential chronology

This log separates method development, independent confirmation, and analyses conceived
after the confirmation result was known. The labels in the final manuscript must follow this
table even if a post-reveal method appears numerically better.

| Stage | Information available for decisions | Status | Immutable evidence |
|---|---|---|---|
| Dual-three-phase PMSM development | Healthy and fault records from the development bench | Developmental; fault labels select among seven frozen candidates | `results/paper3_development/protocol.json`, SHA-256 `a37d38937aee35ae0ed44c5c139a4e0daf54cd85a03f1e105b8cc6ab5f071ec9`; selected-method JSON SHA-256 `1cccd12c8d7b8d4c6ad40b0a96ebd46ec839739b84b30512a8d4b7ca77324bf5` |
| PMSG metadata freeze | Filenames, directory inventory, article/repository metadata; no signal array deserialized or plotted | Preregistration boundary | Confirmation protocol SHA-256 `4fc0d12e1e69c09776f8c0f691eddf38552bdf2f7512dc71c426103cc349bfd9`; metadata inventory SHA-256 `4890f864e40fc3345f5af37364a6acf7d854af4ab94b57ebc73e2def94a36914` |
| PMSG container audit and feature reveal | Signal container/schema audit, then whitelisted `t`, `Ia`, `Ib`, `Ic` only | Mechanical reveal under the frozen protocol | Feature table SHA-256 `78bbc520ada5bcfe6f3dc419968e64892aaba48743f5976443cdf4f136346040` |
| Frozen PMSG confirmation | All 216 fault-record outcomes and seven mechanically applied methods | Sole independent confirmatory analysis | Selected primary JSON SHA-256 `f119fde0c7bc6625abc43d68769602305bf24e0e949a3f7c5e301b36634a63cb` |
| Session-anchor analysis | Frozen confirmation results visible | Post-reveal exploratory repair | Protocol SHA-256 `3be582ec0059253b832dc73356223c9f3c5a2e0d06c0ccf43ca436830ac162ca` |
| Matched-session topology cross-fit | Frozen and simple-anchor results visible | Post-reveal internal validation | Protocol SHA-256 `36199e442315a954384367a45744907f2c30bc53277f96ecfc89fb335f9cadce` |
| Conditioned matched-session cross-fit | All preceding results visible; final allowed PMSG mechanism check | Post-reveal internal validation | Protocol SHA-256 `1e50a84d0fd86eac9daeacb8e01fd96dcd9135e9f65fe71ad49844807debe28a` |

## Metadata-only access caveat

Before the signal freeze, a Git metadata/size query caused Git to fetch some objects that
contained MAT blobs. No MAT signal variable was checked out for analysis, deserialized,
plotted, summarized, or used to choose a method before the confirmation protocol was frozen.
The manuscript must say **signal-unrevealed metadata freeze**, not claim that no blob bytes
ever reached local object storage.

The PMSG source was frozen at repository tag `v1.1.0`, commit
`e02fba475cf82b375412a7382143dc29da5241ef`, tree
`65430929e4886935d463f1e1410b5476d255f4d4`. The container audit found all 225 expected MAT
files, a common 33-variable schema, the four required 60,001-by-1 double arrays, no duplicate
file hashes, and no need for a compatibility patch. The feature builder never loaded fault
relay state, fault current, voltage, angle, dq quantities, or measured speed.

## Execution incident before scoring

The first confirmation command stopped at a Python import error before any detector was fit or
score was emitted. Shared model code was moved from a script into
`src/pmsm_sci/faults/paper3_modeling.py`; no feature, method, hyperparameter, threshold rule,
split, or endpoint changed. Re-running the development benchmark through the shared module
reproduced `per_block_results.csv` byte for byte and produced maximum score difference zero.
This was a packaging repair, not a statistical amendment.

## Frozen confirmatory outcome

The development-selected spline residual detector failed the PMSG confirmation:

- pre-fault session FAR: 71/216 = 32.87% (descriptive 95% Wilson interval
  26.95--39.39%);
- fault-record detection within the two 0.2 s active-fault windows: 156/216 = 72.22%
  (65.90--77.77%);
- first-window detections: 127; second-window-only detections: 29; right-censored beyond
  0.4 s: 60;
- fault-record abstention: 0/216;
- all five gates did not jointly pass: both FAR gates and the point-detection gate failed.

All seven frozen methods also exceeded the 5% pre-fault session-FAR gate. The comparator table
cannot replace the selected method after reveal.

## Post-reveal analyses retained regardless of outcome

1. A two-window session anchor lowered PMSG pre-fault FAR to 17/216 = 7.87% and raised
   detection to 167/216 = 77.31%, but its FAR point and Wilson-upper gates still failed.
2. Topology-disjoint matched-session cross-fitting produced FAR 14/216 = 6.48% and detection
   153/216 = 70.83%. Its three healthy thresholds were 35.15, 88.08, and 53.93, revealing
   substantial calibration variability.
3. Adding the already selected spline context model to the same session residuals produced
   FAR 18/216 = 8.33% and detection 154/216 = 71.30%. Its thresholds were 31.80, 93.13, and
   49.56. It also failed the original gates.

No further PMSG feature arm, detector, calibration source, topology assignment, window, or
gate may be searched after the conditioned-anchor analysis. Future work requires a genuinely
new machine or prospectively acquired healthy calibration sessions.

## Interpretation boundary

- The independent result confirms a **calibration-transport failure for this frozen method,
  development bench, and PMSG bench**. It does not establish that every healthy-only detector
  fails across all permanent-magnet machines.
- The 216 fault files are operating-condition repetitions from one physical PMSG, not 216
  machine replicates. Wilson intervals are descriptive for these sessions.
- The development PMSM and confirmation PMSG differ in machine role, winding/topology,
  acquisition, operating grid, and fault construction. The study identifies compound
  external shift; it cannot isolate one causal source of failure.
- The post-reveal analyses explain and bound repair mechanisms. They are not independent
  confirmations and cannot be described as preregistered.
