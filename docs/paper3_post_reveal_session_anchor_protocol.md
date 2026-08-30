# Paper 3 post-reveal session-anchor protocol

Frozen after the preregistered PMSG confirmation failed and before computing any
session-anchored score. This analysis is explicitly post-reveal and cannot retroactively turn
the failed confirmation into a successful one.

## Trigger and immutable negative result

The selected `spline_residual` method produced 71/216 pre-fault session alarms (32.87%) and
156/216 detected fault sessions (72.22%). The preregistered safety and point-detection gates
failed. Selected primary-result SHA-256:
`f119fde0c7bc6625abc43d68769602305bf24e0e949a3f7c5e301b36634a63cb`.
The PMSG feature table SHA-256 is
`78bbc520ada5bcfe6f3dc419968e64892aaba48743f5976443cdf4f136346040`.

All seven global methods had pre-fault session FAR between 12.50% and 51.39%. This method-wide
failure motivates a single mechanism-based repair: remove a session-specific healthy feature
offset before scoring. The repair is not chosen from a benchmark menu.

## Locked session-anchor method

Use the same 26 scale-free outcome features. Within every record, the anchor is the
coordinate-wise median of exactly two healthy 0.2 s windows. Subtract that anchor from later
feature vectors. Learn a global coordinate-wise median/MAD scale and Ledoit-Wolf covariance
from healthy within-session residuals only. Score squared Mahalanobis distance. No operating
context, fault label, fault current, relay, voltage, or absolute current feature enters the
model.

For the nine standalone PMSG healthy records, anchor windows are health-analysis window IDs 0
and 1 (`[0.2,0.6)` s), and residual windows are IDs 2--12. The four previously designated fit
files supply 44 healthy residuals. The three calibration files supply 33 residual scores and a
split-conformal alpha 0.05 threshold (rank 33, the maximum). The two standalone health-test
files remain secondary tests.

For each of 216 fault experiment records, anchor the first two pre-fault windows
(`[0.2,0.6)` s). The last pre-fault window `[0.6,0.8)` is the session-level FAR test. The two
locked fault windows `[1.0,1.4)` remain the detection test; recovery remains diagnostic.

## Endpoints and interpretation

Report pre-fault session FAR, fault-record any-alarm detection, first/second-window delay,
standalone health FAR, family/speed/torque/fault-span stratification, and Wilson intervals.
Reuse the original gates for context only, but label every result exploratory/post-reveal.
Do not compare p-values as if the global and anchored analyses were independent.

The exact session-anchor method will then be carried without tuning to the already available
transient cross-capacity dataset. That dataset has been used previously for other methods, so
it is an external stress test rather than pristine confirmation. Its record-local healthy
prefix and post-fault windows must be used without consulting the new method's outcomes to
move onsets or select records.
