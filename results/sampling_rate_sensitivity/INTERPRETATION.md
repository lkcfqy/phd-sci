# Sampling-rate sensitivity interpretation

**POST-REVEAL SENSITIVITY — exploratory, not confirmatory.** This analysis was
specified after external fault reveal. External fault outcomes were used only to
evaluate the frozen rerun; they did not select the polyphase filter, features,
window/block geometry, ridge, calibration split, threshold, method, or seed.

## Direct answer

Aligning the KAIST source rate from 100 kHz to 10 kHz does **not** support sampling
rate mismatch as the primary explanation for the proposed method's external
negative transfer. Proposed fault-block detection changed from 0.2500
to 0.2474 (-0.0026); block AUROC changed from
0.6354 to
0.6331. Its detection gap to the best
frozen external method (target_min_cov_det) changed from 0.4505 to 0.4531,
so rate alignment did not close the gap.

Across the 48 physical external fault records, proposed block alarm rate improved
for 0, worsened for 1, and was unchanged for 47. These
records, not their 384 temporally ordered blocks, are the relevant independent
sampling units for that paired descriptive count.

## Source-task check

The 10 kHz source arm did not make the internal KAIST task unusable. Proposed LOMO
source detection changed from
0.9571 to
0.9196, with AUROC changing from
0.9993 to
0.9947. Therefore the absent external
recovery is not explained by wholesale failure of feature extraction at 10 kHz.

## Interpretation boundary

This is a one-factor diagnostic, not a new confirmatory experiment. It rules
against a simple “100 kHz source versus 10 kHz target” explanation under the
frozen pipeline, but it does not identify the remaining cause. Plausible residual
differences include sensor transfer functions, drive/control regime, topology,
speed/load coverage, and the external fault mechanism. Block-level rates remain
descriptive because blocks within a physical record are temporally dependent.
