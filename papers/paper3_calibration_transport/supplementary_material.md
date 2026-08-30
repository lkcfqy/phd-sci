---
title: "Supplementary Material: When Healthy-Only Alarm Calibration Does Not Transport Across Permanent-Magnet Synchronous Machines"
author: "Anonymous review version"
---


# S1. Evidence chronology and immutable boundary

The development method was chosen with development fault labels. The PMSG protocol, selected method, feature schema, healthy roles, windows, alpha, and failure gates were then frozen before a PMSG signal variable was deserialized. All later session-anchor analyses are post-reveal. A repository size query had already fetched some Git objects containing MAT blobs, but no signal array was checked out for analysis, loaded, plotted, or summarized; the precise claim is therefore a signal-unrevealed metadata freeze.

| Artifact | SHA-256 |
|---|---|
| development features | `c3e7e13919a8868580bd3af8c501d8f022600f5a2637460470479ad7faff4743` |
| development protocol json | `a37d38937aee35ae0ed44c5c139a4e0daf54cd85a03f1e105b8cc6ab5f071ec9` |
| development selection | `1cccd12c8d7b8d4c6ad40b0a96ebd46ec839739b84b30512a8d4b7ca77324bf5` |
| confirmation protocol | `4fc0d12e1e69c09776f8c0f691eddf38552bdf2f7512dc71c426103cc349bfd9` |
| confirmation inventory | `4890f864e40fc3345f5af37364a6acf7d854af4ab94b57ebc73e2def94a36914` |
| confirmation features | `78bbc520ada5bcfe6f3dc419968e64892aaba48743f5976443cdf4f136346040` |
| confirmation primary | `f119fde0c7bc6625abc43d68769602305bf24e0e949a3f7c5e301b36634a63cb` |

The PMSG source is tag `v1.1.0`, commit `e02fba475cf82b375412a7382143dc29da5241ef`, tree `65430929e4886935d463f1e1410b5476d255f4d4`. All 225 MAT files passed the common-schema and time-base audit without a compatibility patch.

# S2. Feature and information schema

The detector uses time and three phase currents. Development additionally loads commanded speed and filename load as exogenous context; confirmation uses filename speed and torque setting code. Fault current, relay state, measured angle/speed, voltage, dq quantities, and absolute current scale are excluded. The 26 ordered outcomes are:

| Index | Feature |
|---|---|
| 1 | `sequence_unbalance` |
| 2 | `fundamental_amplitude_cv` |
| 3 | `phase_rms_cv` |
| 4 | `clarke_radius_cv` |
| 5 | `zero_sequence_ratio` |
| 6 | `spectral_entropy` |
| 7 | `sideband_lower_ratio` |
| 8 | `sideband_upper_ratio` |
| 9 | `harmonic_2_ratio_mean` |
| 10 | `harmonic_2_ratio_max` |
| 11 | `harmonic_3_ratio_mean` |
| 12 | `harmonic_3_ratio_max` |
| 13 | `harmonic_4_ratio_mean` |
| 14 | `harmonic_4_ratio_max` |
| 15 | `harmonic_5_ratio_mean` |
| 16 | `harmonic_5_ratio_max` |
| 17 | `thd_2_to_5_mean` |
| 18 | `rms_ratio_a` |
| 19 | `crest_a` |
| 20 | `kurtosis_a` |
| 21 | `rms_ratio_b` |
| 22 | `crest_b` |
| 23 | `kurtosis_b` |
| 24 | `rms_ratio_c` |
| 25 | `crest_c` |
| 26 | `kurtosis_c` |

PMSG feature inventory: 117 standalone-health windows, 648 pre-fault windows, 432 active-fault windows, and 1,296 recovery windows, totaling 2,493 rows from 225 records. Only `t`, `Ia`, `Ib`, and `Ic` were deserialized.

# S3. Complete development benchmark

Values below use only the six interpolation loads (5--30 N m) for selection. Each method has 48 healthy test blocks and 288 fault blocks. Detection is the equal-record macro average of actionable block alarms. Development fault labels select the method; these rows are not external confirmation.

| Method | Healthy alarms | FAR | Detection | Abstention | Eligible |
|---|---|---|---|---|---|
| Unconditioned residual | 1/48 | 2.08% | 28.47% | 0.00% | yes |
| Linear residual | 1/48 | 2.08% | 76.39% | 0.00% | yes |
| Quadratic residual | 1/48 | 2.08% | 81.25% | 0.00% | yes |
| Spline residual | 1/48 | 2.08% | 82.29% | 0.00% | yes (selected) |
| Spline + local scale | 10/48 | 20.83% | 93.75% | 0.00% | no |
| Isolation Forest | 1/48 | 2.08% | 65.97% | 0.00% | yes |
| MinCovDet | 1/48 | 2.08% | 7.64% | 0.00% | yes |

# S4. Complete frozen PMSG benchmark

All methods use the same 39-window healthy calibration role and 216 fault sessions. A pre-fault session alarms if any of its three frozen pre-fault windows alarms; a fault record is detected if either of two active windows alarms. Only the spline residual is confirmatory. No method passed the 5% FAR point gate.

| Method | Threshold | Pre-fault alarms | FAR (95% Wilson) | Detected | Detection (95% Wilson) | AUROC |
|---|---|---|---|---|---|---|
| Unconditioned residual | 32.1594 | 111/216 | 51.39% (44.76%--57.97%) | 173/216 | 80.09% (74.26%--84.87%) | 0.7602 |
| Linear residual | 85.0129 | 57/216 | 26.39% (20.96%--32.64%) | 148/216 | 68.52% (62.05%--74.34%) | 0.7661 |
| Quadratic residual | 36.5397 | 86/216 | 39.81% (33.52%--46.47%) | 164/216 | 75.93% (69.80%--81.14%) | 0.7787 |
| Spline residual **[selected]** | 55.3097 | 71/216 | 32.87% (26.95%--39.39%) | 156/216 | 72.22% (65.90%--77.77%) | 0.7799 |
| Spline + local scale | 120.6509 | 56/216 | 25.93% (20.54%--32.15%) | 139/216 | 64.35% (57.76%--70.44%) | 0.7486 |
| Isolation Forest | 0.5408 | 90/216 | 41.67% (35.29%--48.33%) | 149/216 | 68.98% (62.53%--74.77%) | 0.7294 |
| MinCovDet | 2514.0028 | 27/216 | 12.50% (8.73%--17.58%) | 122/216 | 56.48% (49.81%--62.92%) | 0.7744 |

# S5. Frozen selected-method condition results

Each speed-by-setting cell contains 24 sessions. These repetitions come from one physical PMSG and are not population replicates. Setting codes 52, 64, and 80 are not asserted to be N m.

| Facet | Level | Records | Detection | Pre-fault FAR |
|---|---|---|---|---|
| fault_family | turns | 108 | 53.70% | 30.56% |
| fault_family | windings | 108 | 90.74% | 35.19% |
| speed_rpm | 1200 | 72 | 59.72% | 29.17% |
| speed_rpm | 1500 | 72 | 84.72% | 50.00% |
| speed_rpm | 1800 | 72 | 72.22% | 19.44% |
| torque_setting_code | 52 | 72 | 83.33% | 48.61% |
| torque_setting_code | 64 | 72 | 70.83% | 30.56% |
| torque_setting_code | 80 | 72 | 62.50% | 19.44% |
| speed_by_torque | 1200 / 52 | 24 | 75.00% | 50.00% |
| speed_by_torque | 1200 / 64 | 24 | 62.50% | 20.83% |
| speed_by_torque | 1200 / 80 | 24 | 41.67% | 16.67% |
| speed_by_torque | 1500 / 52 | 24 | 91.67% | 66.67% |
| speed_by_torque | 1500 / 64 | 24 | 83.33% | 41.67% |
| speed_by_torque | 1500 / 80 | 24 | 79.17% | 41.67% |
| speed_by_torque | 1800 / 52 | 24 | 83.33% | 29.17% |
| speed_by_torque | 1800 / 64 | 24 | 66.67% | 29.17% |
| speed_by_torque | 1800 / 80 | 24 | 66.67% | 0.00% |

## S5.1 Fault-topology rows

| Family | Terminals | Span (%) | Detection | Pre-fault FAR | First-window detection |
|---|---|---|---|---|---|
| turns | D01--D04 | 12.04 | 88.89% | 33.33% | 77.78% |
| turns | D02--D03 | 7.69 | 44.44% | 44.44% | 22.22% |
| turns | D05--D08 | 12.10 | 88.89% | 33.33% | 44.44% |
| turns | D06--D07 | 7.40 | 44.44% | 33.33% | 22.22% |
| turns | D09--D10 | 2.80 | 33.33% | 22.22% | 11.11% |
| turns | D11--D12 | 2.70 | 22.22% | 44.44% | 22.22% |
| turns | D13--D16 | 11.60 | 88.89% | 11.11% | 66.67% |
| turns | D14--D15 | 7.40 | 22.22% | 22.22% | 11.11% |
| turns | D17--D20 | 11.60 | 88.89% | 0.00% | 22.22% |
| turns | D18--D19 | 7.40 | 44.44% | 33.33% | 22.22% |
| turns | D21--D22 | 3.80 | 33.33% | 44.44% | 22.22% |
| turns | D23--D24 | 2.80 | 44.44% | 44.44% | 33.33% |
| windings | D01--D06 | 14.34 | 100.00% | 33.33% | 88.89% |
| windings | D01--D07 | 21.74 | 100.00% | 11.11% | 100.00% |
| windings | D04--D06 | 2.30 | 77.78% | 77.78% | 77.78% |
| windings | D04--D07 | 9.70 | 100.00% | 44.44% | 77.78% |
| windings | D11--D21 | 36.40 | 100.00% | 33.33% | 100.00% |
| windings | D11--D22 | 40.20 | 100.00% | 44.44% | 100.00% |
| windings | D12--D21 | 33.70 | 100.00% | 11.11% | 100.00% |
| windings | D12--D22 | 37.50 | 100.00% | 0.00% | 100.00% |
| windings | D13--D18 | 14.80 | 100.00% | 33.33% | 88.89% |
| windings | D13--D19 | 22.20 | 100.00% | 22.22% | 100.00% |
| windings | D16--D18 | 3.20 | 33.33% | 55.56% | 22.22% |
| windings | D16--D19 | 10.60 | 77.78% | 55.56% | 77.78% |

# S6. Post-reveal session analyses

These analyses were specified only after the independent PMSG result was known. They cannot replace confirmation.

| Analysis | False alarms | FAR | Detected | Detection | First/second/censored |
|---|---|---|---|---|---|
| Session anchor | 17/216 | 7.87% | 167/216 | 77.31% | 149/18/49 |
| Matched-session topology cross-fit | 14/216 | 6.48% | 153/216 | 70.83% | 133/20/63 |
| Conditioned-anchor topology cross-fit | 18/216 | 8.33% | 154/216 | 71.30% | 136/18/62 |

## S6.1 Topology-disjoint fold results

| Analysis | Fold | Threshold | False alarms | FAR | Detected | Detection |
|---|---|---|---|---|---|---|
| Matched anchor | 1 | 35.1490 | 7 | 9.72% | 62 | 86.11% |
| Matched anchor | 2 | 88.0753 | 1 | 1.39% | 39 | 54.17% |
| Matched anchor | 3 | 53.9253 | 6 | 8.33% | 52 | 72.22% |
| Conditioned anchor | 1 | 31.7989 | 11 | 15.28% | 65 | 90.28% |
| Conditioned anchor | 2 | 93.1328 | 1 | 1.39% | 38 | 52.78% |
| Conditioned anchor | 3 | 49.5592 | 6 | 8.33% | 51 | 70.83% |

# S7. Reproducibility and claim restrictions

Run the feature/container audit, development benchmark, confirmation analysis, three session analyses, figure builder, and evidence validator in the order listed in `README_REPRODUCE.md`. The evidence validator checks seven immutable hashes, all headline numerators/denominators, the complete 3x3 condition grid, threshold instability, manuscript citations, and all ten figure files.

The following restrictions apply to every table and figure:

- two physical machines do not establish a fleet-population result;
- the 216 PMSG files are sessions/conditions, not independent machines;
- Wilson intervals are descriptive under dependence;
- motor-to-generator, topology, acquisition, and laboratory changes are confounded;
- post-reveal session repairs are internal mechanism analyses;
- censoring beyond 0.4 s is not proof of no later alarm;
- external abstention was zero, so context support did not detect conditional feature shift.

| File | SHA-256 |
|---|---|
| papers\paper3_calibration_transport\manuscript.md | `6ef3f4991a0ec030b7b34faddfa0c4dec92bfcbd489aa32b9abc46cd8caa12c3` |
| docs\paper3_reveal_log.md | `daf4b650bfc003b09655a8f88715eccd3ae39e25679880debd2988f0c5dd501b` |
| docs\paper3_literature_gap.md | `0bdb6d3b341490c5ff9e8c799f1be7b1f60d7bf919b027d22a5af8203b89d52d` |
| results\paper3_development\aggregate_summary.csv | `39b861d62743575e057054cb54e4ef054e0bbee9cc6fab8ba31a2d6e2786f29b` |
| results\paper3_pmsg_confirmation\aggregate_summary.csv | `20e3cdbf90b9a3fa4927cb0ab5cdcdc018e52f834f223a519b023ef6ce2ba27a` |
| results\paper3_pmsg_session_anchor\summary.json | `c9ec7187f8a25c7bbdadc42ce98c2cabe528a309f4f63aa591ee7100c07ffd53` |
| results\paper3_pmsg_topology_crossfit\summary.json | `d78a2ce955085e5ef373e87330e5d69213729d2823921c6117cffb409b7a78e8` |
| results\paper3_pmsg_conditioned_anchor\summary.json | `289f202a8ca4349cdff8f51a30a6aedf604caece480e49affd8e4402c8ca8992` |
