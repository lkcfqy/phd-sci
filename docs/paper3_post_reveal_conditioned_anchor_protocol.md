# Paper 3 post-reveal conditioned-session-anchor protocol

Frozen after observing the topology-cross-fitted unconditioned session-anchor result and before
computing any conditioned-anchor score. This is the final post-reveal model analysis; no
further detector family or hyperparameter search is permitted on the PMSG.

The unconditioned matched-session anchor produced 14/216 pre-fault false alarms (6.48%) and
153/216 fault detections (70.83%). Fold thresholds ranged from 35.15 to 88.08 even though fit,
calibration, and test were acquisition-matched. This prespecified symptom indicates remaining
operating-condition structure after session offset removal.

Reuse the exact topology buckets and rotating fit/calibration/test roles in
`paper3_post_reveal_matched_calibration_protocol.md`. In each fold, take the 72 fit-bucket
healthy session residuals as outcomes and filename speed plus torque setting code as exogenous
context. Apply the already development-selected conditional model unchanged: additive
uniform-knot quadratic splines with four knots, ridge alpha 1, no local-scale model, four
whole-topology cross-fit folds, median/MAD residual scaling, and Ledoit-Wolf covariance.

Use the 72 calibration-bucket healthy scores at alpha 0.05 (rank 70). Test only the third
bucket's one pre-fault and two fault-active residual windows per record. Support uses the same
1.1 nearest-distance multiplier and fit-axis bounds; because each bucket contains all nine
nominal contexts, any abstention is reported and cannot be removed.

Report the same FAR, detection, delay, Wilson intervals, per-fold thresholds, and original
gates for context. The result is post-reveal topology-disjoint internal validation on one PMSG,
not prospective external confirmation. The original global failure, the simple session anchor,
and the unconditioned matched-calibration result all remain in the paper regardless of this
outcome.
