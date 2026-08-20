# Research Decision Log

## 2026-08-20 — Paper 1 scope

### Decision

Use the KAIST three-motor stator-fault dataset as the primary Paper 1 evidence and
study healthy-only target calibration under leave-one-motor-out transfer.

### Evidence

- Three real PMSMs (1.0, 1.5, and 3.0 kW) permit entity-level holdout.
- The dataset contains two stator-fault families and seven non-zero severities.
- A target motor can be evaluated without exposing any of its fault labels during
  training or calibration.
- This directly connects cross-machine transfer, online health calibration, and
  uncertainty-aware alarms.

### Alternatives considered

- **Geometry-to-torque surrogate:** very easy to reproduce, but the public dataset's
  article already established DFT+GP as a strong method. Retained as Paper 2.
- **Single-motor thermal estimation:** suitable for method development but cannot
  support a cross-machine claim alone. Retained as a thermal side track.
- **Full multiphysics neural-operator twin:** needs parameterized simulation and/or a
  laboratory partner and is too broad for the first publication.

## 2026-08-20 — Raw-data audit findings

### Confirmed

- Mendeley v5 consists of three ZIP archives totaling 6,973,577,960 bytes.
- Each motor archive contains 16 current and 16 vibration TDMS aliases.
- Current files have three 100 kHz channels, 12,000,000 samples per phase, and 120 s
  duration for the healthy record.
- Several fault files actually contain roughly 121--149 s despite the article's 120 s
  description. Every record is truncated to its first 120 s so severity classes and
  motors contribute the same number of windows; file duration cannot become a hidden
  weighting artifact.
- A 0.2 s non-overlapping window yields 600 windows per record.
- Initial feature autocorrelation revealed an almost exact 3 s nuisance cycle. The frozen
  first-pass macro block is therefore 3 s (40 units per record), so a block contains one
  complete cycle instead of splitting that cycle across calibration units.
- The dominant current component in the audited 1.0 kW healthy record is 200 Hz.

### Critical correction

For all three motors, the `intercoil`/`coil` and `interturn` healthy files have identical
uncompressed size and CRC; the extracted 1.0 kW pair also has identical SHA-256. They
are aliases of one recording, not independent repetitions. The pipeline therefore
deduplicates them and the paper must not claim repeated healthy trials.

### Consequence

Target-health calibration and evaluation use separated contiguous portions of one unique
healthy record with guard blocks. Coverage is empirical under a block-stationarity or
mixing assumption; ordinary exchangeable split-conformal guarantees are not claimed.
Independent external validation remains a desirable strengthening experiment.

## 2026-08-20 — Pilot method and evidence boundary

### Decision

Use scale-free current features, per-motor robust healthy alignment, equal-motor
Log-Euclidean covariance transfer, 3 s block maxima and target-health p-value calibration
as the main Paper 1 pilot. Keep the broader contribution name “motor-balanced covariance
transfer” because the paired interval does not resolve Log-Euclidean versus arithmetic
entity averaging.

### Evidence

- Source-only nested pseudo-target validation selected log-covariance ridge 0.01 in all
  three outer folds.
- The main method produced 0/42 later-time healthy false alarms and 95.71% mean fault
  detection, with 90.00% worst-motor detection.
- Record-stratified paired bootstrap favored it over target Ledoit-Wolf and source-only
  covariance, but intervals crossed zero versus target sample covariance and arithmetic
  entity averaging.
- Lowest-severity detection reached a ceiling across covariance methods, while severity
  score monotonicity failed. Severity estimation is removed from the primary claim.
- All target fault records were inspected during method development. Current results are
  exploratory; rerunning the same split cannot create a confirmatory test.

### Adaptation-budget audit

Varying target covariance adaptation from 3 to 24 s did not cause collapse, but results
were nonmonotonic and cannot be used to select 6 s after seeing target faults. The primary
12 s setting remains unchanged. At alpha 0.05, conformal calibration itself needs at least
19 three-second units (57 s); adaptation duration and calibration duration must not be
conflated.

### Block and one-class sensitivity

- The 3 s maximum exactly reproduced the primary result. Shorter blocks reduced
  detection; a 3 s 90th-percentile score improved detection but introduced one healthy
  alarm and missed the predeclared descriptive Wilson gate. The primary rule remains
  unchanged.
- Motor-balanced Isolation Forest achieved 96.07% detection with 0/42 healthy alarms,
  versus 95.71% and 0/42 for the proposed detector. Their paired record interval crossed
  zero. Target-only Isolation Forest reached 97.56% but had 1/42 healthy alarms and
  missed the same gate.
- The defensible contribution is therefore a deterministic, interpretable,
  motor-balanced covariance detector competitive with a strong nonlinear one-class
  baseline. Universal state-of-the-art or across-the-board superiority is not claimed.

## 2026-08-20 — External validation freeze strategy

### Decision

Use Zenodo `10.5281/zenodo.13889418` as the primary independent-laboratory PMSM test.
Download and audit its eight healthy load records first, write the split and system-level
score rule before seeing any fault record, and expose all 48 fault records exactly once
after code freeze.

### Rationale and boundary

- It is a real dual-three-phase PMSM with independent healthy records at eight loads,
  10 kHz current, and 48 ITSC records spanning two fault phases and six turn counts.
- Two three-phase subsystems will be scored separately and combined by a frozen maximum;
  calibration must use that same system maximum.
- A health-only structural audit showed that every 41.5 s record is a common
  acceleration sweep from near standstill to roughly 4400 rpm, not a 5000 rpm steady
  trace. With the documented ten pole pairs, the frozen `[12, 36)` s interval keeps the
  electrical fundamental within the existing 20--500 Hz feature-search range and
  supplies eight complete 3 s blocks per record.
- The 0 Nm record contributes only blocks 0--3 of that interval (12 s) to target
  adaptation. The independent 10, 20, and 30 Nm records supply 24 calibration blocks.
  Loads 5, 15, 25, and 35 Nm supply 32 untouched healthy false-alarm blocks.
- All three KAIST motors may contribute one equally weighted source covariance each;
  the external PMSM contributes only its designated healthy adaptation data.
- A successful test is an independent-laboratory out-of-distribution result on one new
  PMSM, not a new multi-motor cohort and not proof of arbitrary cross-topology coverage.

The compact 200 W/20 kW transient set (`10.5281/zenodo.15631383`) is retained as a
secondary stress test because it lacks independent healthy files and uses MATLAB MCOS
time-series objects. The 2.2 kW PMSG set (`10.18710/ZN1LPD`) is tertiary because its
generator topology changes the deployment domain.

## Open decisions after the strengthened pilot

1. Verify exact current/vibration synchronization before any multimodal claim.
2. Add any domain-adaptation baseline only if it can obey the same no-target-fault-label
   deployment setting; do not force a mismatched supervised benchmark.
3. Complete the primary dual-three-phase health audit and freeze an executable external
   feature/scoring pipeline before downloading faults.
4. Measure runtime before making online or embedded-deployment claims.
5. Obtain new independent healthy sessions if a formal false-alarm coverage claim is
   desired; the current evidence supports empirical block-risk only.
