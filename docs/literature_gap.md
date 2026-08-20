# Literature Gap Matrix (2026-08-20 Snapshot)

This matrix is a working claim audit, not a substitute for the final systematic search.

| Work | What is already covered | Gap relevant to Paper 1 |
|---|---|---|
| [Jung et al., 2023](https://doi.org/10.1016/j.dib.2023.108952) | Public current/vibration records from three PMSMs and seeded stator-fault severities | Data article; no healthy-only cross-machine risk calibration protocol |
| [Son et al., 2025](https://doi.org/10.1016/j.ymssp.2025.112561) | Multiphysics-informed DeepONet digital twin for one PMSM | No entity-level transfer to a new motor and no target-health conformal calibration |
| [Partovizadeh et al., 2025](https://doi.org/10.1007/s00366-025-02123-1) | Geometry-to-torque waveform surrogate; DFT+GP is a strong baseline | Design surrogate rather than real-sensor fault transfer |
| [DeepONet IPMSM map prediction, 2024](https://doi.org/10.1109/TMAG.2024.3477448) | Operator learning for electric-machine characteristic maps | Using DeepONet alone is no longer a novelty claim |
| [Heddoub et al., 2026](https://doi.org/10.1016/j.jprocont.2026.103701) | Class-conditional conformal prediction and rejection for open-set process faults | Not a PMSM entity-holdout study; does not address one target healthy time series and severity |
| [Chernozhukov et al., 2018](https://proceedings.mlr.press/v75/chernozhukov18a.html) | Block-structured conformal inference for dependent data | Supplies the dependence-aware foundation; assumptions must be checked for the motor records |
| [Barber and Pananjady, 2026](https://proceedings.mlr.press/v313/barber26a.html) | Coverage analysis of split conformal under stationary beta-mixing time series | Shows why temporal dependence cannot be ignored or described as ordinary exchangeability |

## Defensible Paper 1 gap

The contribution is not “the first conformal fault diagnosis” and not “the first neural
operator for motors.” The defensible combination is:

1. the complete target PMSM is excluded from supervised training and model selection;
2. no target fault label is used for adaptation or alarm calibration;
3. calibration units are full nuisance-cycle time blocks, not randomly shuffled windows;
4. the primary endpoint is target-motor false-alarm risk at a frozen threshold;
5. detection is resolved by fault family and severity, including the lowest severities;
6. the method may abstain and its risk-coverage behavior is reported.

## Claim boundary

- The KAIST motors differ in rated power but share manufacturer and test condition.
- Each health/fault state has one unique continuous record, not independent repetitions.
- The result is conditional evidence for this cross-capacity setting, not a universal
  guarantee across topology, manufacturer, speed, load, or natural degradation.
- External variable-condition data or a new testbench repeat would materially strengthen
  the paper and should be added before aiming at the most selective journal tier.
