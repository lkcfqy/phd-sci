# Paper 3 outline

## Working title

**When Healthy-Only Alarm Calibration Does Not Transport Across Permanent-Magnet
Synchronous Machines: A Protocol-Frozen External Validation**

## One-sentence result

A speed/load-conditioned current detector selected on a dual-three-phase PMSM moved from
2.08% healthy-block FAR and 82.29% detection on development interpolation loads to 32.87%
pre-fault session FAR and 72.22% detection on a signal-unrevealed PMSG bench; session-local
anchoring reduced but did not eliminate the calibration failure.

## Contribution boundary

The paper contributes an external-validation design and a retained negative result. It does
not claim a new feature family, one-class classifier, conformal theorem, or universal
cross-machine result. The useful methodological elements are:

1. fault-blind healthy fitting and threshold calibration;
2. whole-record development splits and a signal-unrevealed external freeze;
3. record/session endpoints and predeclared failure gates rather than test-set AUROC tuning;
4. an explicit temporal separation between confirmation and post-reveal repair analyses;
5. topology-disjoint internal validation showing that session anchoring did not stabilize
   calibration thresholds.

## Main figures

1. `paper3_method_transport`: seven-method development versus confirmation operating points.
2. `paper3_session_repair`: preregistered failure and three explicitly post-reveal repairs.
3. `paper3_topology_fold_stability`: fold thresholds and FAR/detection instability.
4. `paper3_condition_heatmap`: speed/torque confounding in frozen confirmation.
5. `paper3_first_alarm`: 0.2 s, 0.4 s, and right-censored fault sessions.

## Main tables

1. Dataset and split inventory: physical machines, records, sampling, windows, fit/cal/test
   roles, and independence boundary.
2. Seven methods: development FAR/detection and frozen PMSG FAR/detection.
3. Confirmatory gates: point estimates, descriptive Wilson intervals, pass/fail.
4. Post-reveal variants: calibration source, split unit, FAR, detection, first alarms, status.
5. Limitations and corresponding claim restrictions.

## Section plan

### 1. Introduction

- Healthy-only monitoring is attractive because fault labels are scarce.
- Operating changes and machine/lab shift alter both scores and thresholds.
- A within-dataset detector result is not evidence that an alarm operating point transports.
- State the protocol-frozen external experiment and negative headline result.

### 2. Related work and gap

- PMSM/PMSG inter-turn diagnosis and operating-condition dependence.
- Healthy-only/one-class monitoring.
- Cross-machine domain generalization and leakage-resistant splits.
- Conformal alarms and their exchangeability/shift boundary.
- Gap: external, fault-blind alarm calibration with failure criteria frozen before signal
  reveal and post-reveal repairs kept separate.

### 3. Study chronology and data

- Development dual-three-phase PMSM: one machine, 8 healthy + 48 faults, 8 loads,
  10 kHz, two three-phase subsystems, common rising-speed interval.
- PMSG: one independent 2.5 kVA machine/lab, 9 healthy + 216 faults, 20 kHz, 3 speeds,
  3 torque setting codes, 24 topologies.
- Hashes, whitelist, and disclosure of the metadata-size fetch caveat.
- Distinguish records/sessions/topologies from independent machines.

### 4. Detector and frozen evaluation

- 26 scale-free current features in 0.2 s windows.
- Exogenous filename/command context only.
- whole-record cross-fitted spline mean; robust residual standardization; Ledoit-Wolf
  Mahalanobis score.
- support rule and alpha=.05 rank calibration.
- development selection among seven candidates.
- confirmation 4/3/2 healthy split and fixed [0.2,0.8)/[1.0,1.4) endpoints.
- five confirmatory gates.

### 5. Results

- development selection and edge-load abstention.
- complete seven-method transport reversal.
- confirmatory selected-method failure.
- condition/fault-family heterogeneity and early-alarm distribution.
- all comparators fail FAR gate; none can replace selected method.

### 6. Post-reveal mechanism analyses

- simple two-window session anchor: partial repair.
- topology-disjoint matched-session cross-fit.
- conditioned anchor as final frozen mechanism test.
- 2.5--2.9x threshold variability; no original joint gate passes.
- no further PMSG model search.

### 7. Discussion

- calibration dataset is part of the deployed model.
- session offset is material but not sufficient.
- conditioning can improve ranking while leaving operational calibration unsafe.
- data requirements: independent healthy sessions, prospective target calibration, repeated
  topology/lab/machine confirmation, sequential monitoring.
- negative results are useful because they prevent unsafe threshold reuse.

### 8. Limitations

- two physical machines, one per stage; development is a motor and confirmation a generator.
- compound shift cannot be causally decomposed.
- controlled faults and short 0.4 s horizon.
- dependent windows/sessions; descriptive intervals only.
- post-reveal repairs are internal, not independent confirmation.

### 9. Conclusion

- Do not deploy from within-bench FAR alone.
- Require target-session calibration and prospective external validation.
- Session anchoring helped, but topology-separated thresholds remained unstable.

## Target length and venue posture

- Main text: 5,000--6,500 words.
- Main figures: 5; main tables: 4; full features, hashes, per-condition results, and
  post-reveal tables in supplement.
- Best posture: Measurement / instrumentation / reliability / applied ML venue willing to
  publish rigorous negative external validation; avoid architecture-first framing.
