# Paper 3 post-reveal matched-session calibration protocol

Frozen after the single session-anchor analysis and before computing any topology-cross-fitted
matched-calibration result. This remains post-reveal evidence; it does not replace the failed
independent confirmation.

## Motivation and prior result

The fixed standalone-file session anchor reduced PMSG pre-fault session FAR from 32.87% to
7.87% and increased record detection from 72.22% to 77.31%, but its FAR Wilson upper bound was
12.24%, above the original 10% gate. Standalone healthy test windows also remained shifted.
The remaining prespecified mechanism is calibration-source mismatch: thresholds learned from
standalone healthy acquisitions do not represent healthy prefixes of switched fault
experiments.

## Frozen three-way topology split

Define a fault topology by `(fault_family, terminal_a, terminal_b)`. Sort the 12 turn cases and
12 winding cases lexicographically within family. Assign topology bucket `case_index mod 3`.
Each bucket therefore has four turn and four winding cases, observed at all nine operating
conditions (72 physical experiment records).

For outer fold `f`:

- test bucket: `f`;
- healthy-geometry fit bucket: `(f + 2) mod 3`;
- healthy calibration bucket: `(f + 1) mod 3`.

Thus fit, calibration, and test contain eight disjoint fault topologies and 72 records each.
Every topology is tested exactly once. The assignment is mechanical; although case-level
results from the failed global method have already been inspected, no topology is moved based
on those outcomes.

## Healthy-only information flow

For every record, use pre-fault windows 0 and 1 (`[0.2,0.6)` s) as the session anchor and
window 2 (`[0.6,0.8)` s) as one healthy residual. Fit the same median/MAD plus Ledoit-Wolf
residual geometry on the 72 fit-bucket healthy residuals. Score 72 calibration-bucket healthy
residuals and set the alpha 0.05 split-conformal threshold at rank
`ceil((72 + 1) * 0.95) = 70`. Neither geometry nor threshold sees any fault-active window.

Apply the fold model to the test bucket's last pre-fault window and the unchanged two
fault-active windows `[1.0,1.4)` s. No standalone healthy file, recovery window, fault current,
relay, or condition-specific adjustment enters model selection or calibration. The same 26
scale-free current features and exact session-anchor implementation are reused.

## Outcomes and boundary

Pool the three topology-disjoint test folds and report session FAR, fault-record any-alarm
detection, first/second-window delay, Wilson intervals, and family/speed/torque/topology
strata. Original gates are shown only as an interpretable target. This cross-fitted result is a
post-reveal internal validation on one physical PMSG. It can establish that matched healthy
session history repairs calibration within this bench; it cannot establish prospective
external generalization.
