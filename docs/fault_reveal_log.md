# External PMSM Fault-Reveal Log

This log records the one-time reveal of the 48 dual-three-phase PMSM fault files.
Times are UTC on 2026-08-20. It supplements the pre-reveal frozen protocol in
`docs/external_validation_protocol.md`.

## Immutable stages before fault values were opened

| Commit | Frozen content |
|---|---|
| `fddf2f7` | KAIST pilot, protocol, MAT parser, features, eleven comparators, system scoring, and tests |
| `ca7a1c9` | One-time external health result and 24 calibration scores/thresholds |
| `e01edcf` | Official 48-file reveal plan with filename, byte count, and Zenodo MD5 |
| `a6d44a9` | Code-audit correction: record bootstrap follows the already written turn-count strata |
| `a3ab29a` | Output-only audit addition: retain both subsystem block scores; clarify fixed comparator roles |
| `e0b5844` | Parallel checksummed transfer; no feature or scoring change |

The two audit corrections were committed after content download had begun but before any
fault MAT file was opened by the feature pipeline or any fault score was computed. They
did not change features, fitted references, calibration scores, thresholds, the system
maximum, or the primary method.

## Download and integrity

- Planned fault files: 48; planned total: 1,134,692,510 bytes.
- Downloaded fault files: 48; partial files remaining: 0.
- The downloaded filename/size/MD5 mapping exactly matched
  `data/raw/external_validation/fault_reveal_plan.json`.
- The complete local directory contained 8 healthy and 48 fault MAT files. No record was
  selected, excluded, renamed, or substituted.

## First fault-value access and score run

- `2026-08-20T14:26:28Z`: the frozen feature builder completed its first access to fault
  values. All 48 fault files passed the strict filename, variable, dtype, sample-count,
  10 kHz timebase, finite-value, and `[12,36)` s interval checks.
- Output: 56 physical records, 112 record--subsystem streams, 13,440 windows, and no
  missing model feature. Combined feature SHA-256:
  `cef907bd7c7fef66170a87672df937827bd9a0e8c3f2083599ab277a19de9f0e`.
- `2026-08-20T14:26:55Z`: `run_external_pmsm_validation.py --require-faults`
  completed the first and primary fault-score run. It found exactly 48 records and 384
  system blocks.

## Locked primary outcome

The Log-Euclidean motor-balanced primary detector retained its health-stage result of
`1/32` false alarms. The point healthy-block FAR was 3.125%, while its descriptive 95%
Wilson upper bound was 15.74%; the predeclared 12% H1 gate therefore failed.

Across the 48 complete fault records, the primary detector achieved:

- record-macro block detection: 25.00%;
- turn-stratified record-bootstrap 95% interval: 21.09%--29.43%;
- block AUROC against the 32 held-out health blocks: 0.6354;
- at least one alarm in 48/48 fault records, caused in part by every fault record
  alarming in the final acceleration block.

The last fact is not treated as successful early detection. Primary alarms rose from
0/48 in blocks 0--2 to 48/48 in block 7, while the only primary healthy false alarm was
also in block 7. This is evidence that the frozen score is strongly entangled with the
acceleration/load trajectory.

The strongest preimplemented comparator was target-only Minimum Covariance Determinant:
`0/32` healthy false alarms, 70.05% record-macro block detection, and AUROC 0.9268. It
remains a comparator; selecting it as the new primary after reveal would be post-hoc and
is prohibited.

The 6 turn-count by 8 load grid is not crossed by fault phase. File labels assign
1/3/5/6-turn faults to phase U and 2/4-turn faults to phase V. Turn-count and phase
effects are therefore not separately identifiable, and the turn-stratified bootstrap
conditions on this fixed assignment. Pooled AUROC also compares all eight fault loads
against the four held-out health loads, so it is descriptive rather than load matched.

No primary result will be overwritten. Any revised condition-aware detector developed
from this failure must be labeled exploratory on this dataset and confirmed on a new,
unseen dataset.

## Post-reveal diagnostics (no refit or threshold change)

The following analyses read the frozen prediction tables only and do not replace the
primary endpoint:

- first-four/first-seven/all-eight-block detection was 2.60%/14.29%/25.00%, while
  record-any alarm was 10.42%/52.08%/100%;
- the median first alarm was block 6, approximately 1,643 rpm using the matching healthy
  load record as a speed proxy;
- pooled AUROC was 0.6354, whereas the equal-weight mean of block-position-specific
  AUROCs was 0.8047;
- Spearman association between block position and score was 0.8361 in held-out health
  and 0.8212 in faults;
- target MinCovDet minus the frozen detector was +45.05 percentage points, with a
  paired interval of [40.62, 49.48] and Holm-adjusted p = 0.001 within the listed
  candidate-versus-primary comparison family;
- target-only minus source+target MinCovDet was +39.84 points [35.42, 44.27].

A five-seed post-reveal stability audit mechanically refit only the stochastic
preimplemented comparators on the same frozen healthy data. Target MinCovDet remained
the highest of the four audited stochastic variants for every seed, but detection ranged
65.36--77.08%, healthy alarms ranged 0--2/32, and only three of five seeds passed H1.
This sensitivity is reported as such; the primary seed is not selected after fault
inspection.

An additional analysis-only reconstruction reproduced all 448 frozen Log-Euclidean
block scores to (3.64\times10^{-12}) maximum absolute error and allocated each
Mahalanobis cross-term symmetrically. `fundamental_hz` had matched AUROC 0.5038 but
accounted for 18.07% of fault and 38.54% of held-out-health absolute contribution;
third-harmonic max/mean ratios had AUROC 0.9266/0.9255 but only 0.352%/0.240% fault
contribution. This is a post-reveal mechanism diagnostic, not a refitted detector or a
causal cross-motor feature claim.

A one-factor sampling-rate sensitivity antialias-filtered and resampled all KAIST source
records from 100 kHz to the external 10 kHz before applying the otherwise unchanged
pipeline. The frozen detector's external detection changed from 25.00% to 24.74%,
AUROC from 0.6354 to 0.6331, and healthy alarms remained 1/32; 47/48 record alarm rates
were unchanged and one worsened. Sampling-rate alignment therefore did not rescue the
transfer result and was not used to alter the primary run.

## Manuscript consequence

The working paper is now a leakage-resistant cross-dataset failure and negative-transfer
study, not a Log-Euclidean superiority paper. The prespecified failed detector remains
the primary object, target MinCovDet remains a comparator, and any operating-condition-
aware replacement is reserved for a new study with an untouched confirmation dataset.
