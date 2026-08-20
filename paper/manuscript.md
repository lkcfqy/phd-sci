---
title: >-
  Healthy-Only Cross-Capacity PMSM Stator-Fault Detection via
  Motor-Balanced Covariance Transfer and Block-Conformal Calibration
bibliography: ../references/key_papers.bib
link-citations: true
---

> Development draft, 2026-08-20. The KAIST results in this version are an
> exploratory pilot because all target-fault records were inspected during method
> development. Confirmatory wording is conditional on a frozen-method external test.

## Abstract

Deploying a stator-fault detector to a permanent-magnet synchronous motor (PMSM) of a
new power rating creates a substantial score-distribution shift, while labeled target
faults are normally unavailable. This study investigates healthy-only cross-capacity
transfer on three same-manufacturer PMSMs (1.0, 1.5, and 3.0 kW) using three-fold
leave-one-motor-out evaluation. A content audit removes duplicate healthy aliases,
every recording is truncated to a common 120 s, and correlated 0.2 s current windows
are aggregated into non-overlapping 3 s blocks. Scale-free current features are
robustly centered per motor. One healthy covariance is estimated for each source motor
and the target motor, regularized using a source-only selected ridge, and combined by
an equal-weight Log-Euclidean mean. Target-centered Mahalanobis scores are converted
to block maxima and calibrated at an alarm level of 0.05 using 20 target healthy
blocks; no target-fault label is used for fitting, selection, adaptation, or
calibration. In the exploratory pilot, the method produced 0 false alarms among 42
later-time healthy blocks (95% Wilson upper bound: 8.38%), detected 95.71% of 1,680
fault blocks, and achieved 90.00% worst-motor detection. A motor-stratified paired
record bootstrap favored the method over source-only covariance (+6.61 percentage
points, 95% CI [1.79, 12.32]) and target Ledoit--Wolf (+5.42 points, [0.59, 11.19]),
but did not resolve superiority over target sample covariance or arithmetic entity
balancing. A motor-balanced Isolation Forest achieved 96.07% detection with the same
0/42 healthy false-alarm count; its paired difference from the proposed method was
-0.36 points (95% CI [-3.93, 3.45]). Because calibration and later-time health
originate from one continuous
healthy record per motor, the results establish empirical block-risk calibration
rather than unrestricted distribution-free temporal coverage. Severity-score
monotonicity failed and is not claimed as a capability.

**Keywords:** permanent-magnet synchronous motor; stator fault; cross-machine
transfer; healthy-only adaptation; covariance geometry; conformal calibration;
distribution shift

## 1. Introduction

Interturn short circuits disturb the electrical symmetry of a PMSM and can progress
to destructive winding and magnet damage. Current-based monitoring is attractive
because three-phase currents are already measured by the drive and contain physically
interpretable negative-sequence, harmonic, and current-vector signatures
[@zafarani2018itscreview; @jeong2017negativesequence; @li2024negativesequence]. Recent
learning systems also estimate fault severity from current sequences
[@lee2021attentionseverity]. These methods usually assume, however, that training and
deployment data originate from the same motor, operating condition, or calibrated
measurement chain.

That assumption is fragile when a detector is moved to a motor of a different power
rating. Rated current, controller response, sensor gain, and healthy signal covariance
can all change even if the fault mechanism is related. The first classifier pilot in
this study illustrates the operational consequence: a threshold fitted on two source
motors labeled every later-time healthy block of the 1.0 and 1.5 kW targets as faulty.
A high source-domain accuracy therefore does not establish a usable target alarm.

Domain adaptation and domain generalization have become major themes in rotating-
machinery diagnosis [@li2020domaingeneralization; @xiao2025dgsurvey]. Most studies
optimize target classification accuracy or domain-invariant representations. In a new
motor, however, target fault labels may be unavailable while a short healthy
commissioning trace is realistic. This deployment setting calls for a different
question: can target health alone adapt the reference distribution and calibrate the
alarm risk without exposing a target fault?

Conformal prediction supplies model-agnostic finite-sample calibration under
exchangeability [@angelopoulos2023conformal], and conformal methods have recently been
used for open-set industrial fault diagnosis [@heddoub2026opensetconformal]. Ordinary
exchangeability is not credible for densely sampled windows from a single motor
record. Work on dependent conformal inference shows that time dependence requires
additional assumptions or modified interpretation
[@chernozhukov2018dependentconformal; @barber2026timeseriesconformal]. Treating
thousands of adjacent windows as independent calibration samples would consequently
overstate the evidence.

This paper develops a transparent healthy-only detector around that deployment
constraint. The contributions are:

1. a three-fold motor-level holdout protocol in which target fault labels never enter
   fitting, model selection, adaptation, or calibration;
2. an equal-motor covariance transfer score that combines one healthy covariance per
   motor on the symmetric-positive-definite (SPD) manifold;
3. sequential target-health adaptation, guard, calibration, and later-time test
   regions based on 3 s macroblocks rather than random adjacent windows;
4. record-level paired statistics and an audit of duplicate healthy aliases, unequal
   recording durations, calibration feasibility, and failed severity monotonicity;
5. an explicit evidence boundary: the study reports empirical block-risk calibration
   and does not claim arbitrary-dependence coverage or unrestricted cross-topology
   generalization.

## 2. Related work

### 2.1 PMSM stator-fault signatures

Motor current signature analysis detects winding asymmetry through sequence components,
Park/Clarke current-vector geometry, and spectral changes. Negative-sequence current is
particularly relevant to early interturn faults [@jeong2017negativesequence], while
harmonic behavior can depend on winding configuration and the closed-loop drive
[@zafarani2018itscreview]. This dependence motivates the use of ratios, normalized
spectral features, and within-motor healthy references instead of raw amplitude alone.

The present work does not attempt fault-phase localization or severity regression.
Those are distinct supervised tasks and can require motor parameters, injected signals,
or target fault examples. The observed nonmonotonic relation between the public
dataset's nominal severity labels and the proposed anomaly score further prevents a
valid severity claim.

### 2.2 Cross-domain diagnosis

Cross-domain machinery diagnosis commonly aligns source and target representations or
learns domain-invariant features. Benchmark surveys include source aggregation, DANN,
MMD, CORAL, mixup, meta-learning, and ensemble approaches
[@xiao2025dgsurvey]. Their predominant unit of evaluation is the classified signal
window. By contrast, this study treats the physical motor as the outer holdout unit and
uses the target domain only through healthy commissioning data. A source-supervised
classifier is retained as a domain-shift diagnostic, while the principal task is
one-class target alarm calibration.

### 2.3 SPD covariance transfer and calibrated alarms

A covariance matrix captures interactions among current-shape, imbalance, harmonic,
and spectral features. Direct Euclidean averaging preserves symmetry and positive
definiteness but does not respect the intrinsic geometry of SPD matrices. The
Log-Euclidean construction maps matrices through the matrix logarithm, averages them
in a vector space, and maps the result back by the matrix exponential
[@arsigny2006logeuclidean]. Here each motor contributes one covariance and therefore
one equal vote, irrespective of window count.

The resulting Mahalanobis distance is only an anomaly score; it is not yet an alarm.
Target healthy block scores are used to compute upper-tail conformal p-values. This
calibration does not repair arbitrary temporal dependence. It instead provides an
auditable empirical threshold whose calibration unit is a non-overlapping macroblock,
with the dependence limitation reported explicitly.

## 3. Dataset and leakage-resistant protocol

### 3.1 Dataset audit

The KAIST/Mendeley dataset contains vibration and three-phase current measurements from
1.0, 1.5, and 3.0 kW PMSMs at a fixed 3000 rpm and load setting
[@jung2023pmsmfaultdata; @jung2022pmsmfaultdataset]. Each motor has interturn and
intercoil faults at seven nominal nonzero severity levels. Current was sampled at
100 kHz.

The archive structure nominally contains one healthy record under each fault family.
For every motor, those two healthy members have identical uncompressed size and CRC;
an extracted pair was additionally identical by SHA-256. They are aliases rather than
independent repeats. After deduplication, the current study contains three healthy and
42 fault records. Several fault TDMS files contain 121--149 s although the dataset
description specifies 120 s. Every record is restricted to its first 120 s, producing
equal record weight.

Each record is divided into 600 non-overlapping 0.2 s windows. Window features include
phase RMS ratios, crest factor, kurtosis, Clarke-vector dispersion, sequence-current
ratios, normalized harmonics, total harmonic distortion, sideband ratios, and spectral
entropy. Absolute RMS, zero-sequence RMS, fundamental amplitude, and mean Clarke radius
are excluded from the primary scale-free representation. The complete table contains
27,000 windows and no missing values.

### 3.2 Leave-one-motor-out separation

Three outer folds hold out each motor in turn. The other two motors are sources. Source
fault labels can be used by supervised comparators, but the proposed detector estimates
only healthy distributions. In every fold, the target motor contributes no fault label
before evaluation.

Healthy feature autocorrelation exhibited an approximately 3 s nuisance cycle.
Consequently, fifteen adjacent 0.2 s windows form one non-overlapping 3 s macroblock.
The target healthy record has 40 blocks in chronological order:

- blocks 0--3: 12 s adaptation;
- block 4: guard;
- blocks 5--24: 60 s alarm calibration;
- block 25: guard;
- blocks 26--39: 42 s later-time healthy evaluation.

At an alarm level of 0.05, a conservative finite conformal threshold requires at least
19 calibration units. Thus, the 12 s adaptation trace cannot also be described as a
5% conformal calibration set: it supplies only four macroblocks. The protocol uses 20
separate calibration blocks.

![Motor holdout, sequential target-health split, and method flow.](figures/protocol_overview.pdf)

## 4. Motor-balanced healthy covariance transfer

Let (x_{m,i}\in\mathbb{R}^d) be a scale-free feature vector from motor (m). For
each motor, allowed healthy reference samples define a coordinate-wise median
\(c_m\) and robust scale \(r_m\). The standardized vector is

\[
\widetilde{x}_{m,i}=(x_{m,i}-c_m)\oslash r_m.
\]

Only source healthy reference blocks and target adaptation blocks are allowed in these
statistics. Let (S_m) be the sample covariance of the standardized healthy samples.
Each covariance is regularized relative to its average marginal variance,

\[
S_m^{(\lambda)}=S_m+\lambda\,\frac{\operatorname{tr}(S_m)}{d}I.
\]

The motor-balanced Log-Euclidean covariance is

\[
\Sigma_{\mathrm{LE}}=
\exp\!\left[\frac{1}{M}\sum_{m=1}^{M}\log S_m^{(\lambda)}\right].
\]

Two source motors and the target motor each contribute once. The ridge grid
\(10^{-4},10^{-3},10^{-2},10^{-1}\) is evaluated only by treating each outer fold's
source motors as nested pseudo-targets; all folds selected \(\lambda=10^{-2}\).

After robust target centering, the window anomaly score is

\[
s(x)=\widetilde{x}^{\top}\Sigma_{\mathrm{LE}}^{\dagger}\widetilde{x}.
\]

For block (b), (A_b=\max_{i\in b}s(x_i)). Given (n=20) target healthy
calibration scores, the upper-tail p-value is

\[
p_b=\frac{1+\sum_{j=1}^{n}\mathbf{1}(A_j\ge A_b)}{n+1}.
\]

The block raises an alarm when (p_b\le0.05). Because calibration blocks are ordered
parts of one health record, the p-value is interpreted empirically under a
block-stationarity or weak-dependence approximation, not as distribution-free coverage
under arbitrary temporal dependence.

## 5. Experiments

### 5.1 Exploratory KAIST comparison

The implemented covariance comparators are target Ledoit--Wolf, regularized target
sample covariance, source-only covariance, and arithmetic entity-balanced covariance.
All share the same feature representation, target-health split, block maximum, and
calibration rule. A supervised logistic classifier and gradient boosting model diagnose
the initial source-to-target threshold shift.

Strong one-class comparators use either target adaptation health alone or a
motor-balanced union of source and target health. They comprise a one-class SVM,
Isolation Forest, and Minimum Covariance Determinant. Their hyperparameters were fixed
without target-fault labels. Stochastic methods were additionally evaluated across
five predetermined seeds; the primary comparison uses the preregistered seed.

Primary outcomes are the raw healthy false-alarm count, pooled Wilson interval, maximum
per-motor empirical false-alarm rate, mean and worst-motor fault-block detection, and
block AUROC. Paired method differences are computed for each of the 42 target fault
records. A 10,000-replicate bootstrap resamples records within target motor and then
averages the three motor means. Macroblocks and windows are not treated as independent
experimental repetitions.

Target adaptation is varied over 3, 6, 12, and 24 s in two sensitivity designs. The
fixed-horizon design holds calibration and test time constant; the sequential design
moves calibration directly after each adaptation prefix. The original 12 s setting is
retained irrespective of target-fault results.

### 5.2 Frozen independent-laboratory protocol

The confirmatory target is a public dual-three-phase PMSM with winding taps, two
measured three-phase current subsystems, and externally emulated interturn short
circuits [@kozovsky2024dualthreephasepmsm; @kozovsky2022dualthreephasemodel]. Its eight
healthy records are acceleration sweeps at 0--35 Nm, not steady 5000 rpm records. A
health-only audit fixed the common analysis interval to [12, 36) s before any external
fault file was downloaded. The 0 Nm record supplies four 3 s target-adaptation blocks;
the independent 10, 20, and 30 Nm records supply 24 system-calibration blocks; and the
5, 15, 25, and 35 Nm records supply 32 held-out healthy blocks.

Each three-phase subsystem receives its own target robust alignment and target
covariance. The three KAIST source motors and that target subsystem contribute one
covariance each to a four-entity Log-Euclidean mean. Window maxima are first formed
within each subsystem and then combined by a system maximum; the same system score is
used for calibration. The 48 public fault records remain sealed until the protocol,
feature parser, all comparator implementations, and environment are captured in a
hash-addressed commit. They will then be processed once over the identical [12, 36) s
interval. Until that reveal is complete, the KAIST findings remain exploratory and the
paper is not submission-ready.

## 6. Results

### 6.1 Cross-capacity detection and empirical false-alarm risk

The proposed detector raised no alarm in 42 later-time target healthy blocks. Zero
observed events does not imply zero population risk: the pooled 95% Wilson upper bound
was 8.38%. Fault-block detection was 100.00%, 90.00%, and 97.14% when 1.0, 1.5, and
3.0 kW were targets, respectively. The fold mean was 95.71%, and the worst-motor result
was 90.00%.

| Method | Healthy FAR | Wilson upper | Mean detection | Worst motor | Mean AUROC |
|---|---:|---:|---:|---:|---:|
| Target Ledoit--Wolf | 1/42 | 12.32% | 90.30% | 82.14% | 0.9969 |
| Target sample covariance | 0/42 | 8.38% | 93.87% | 86.79% | 0.9983 |
| Source-only covariance | 0/42 | 8.38% | 89.11% | 70.18% | 0.9968 |
| Arithmetic entity balance | 0/42 | 8.38% | 95.48% | 87.86% | 0.9989 |
| **Log-Euclidean entity balance** | **0/42** | **8.38%** | **95.71%** | **90.00%** | **0.9993** |

![Per-motor detection and healthy false-alarm intervals.](figures/method_performance.pdf)

### 6.2 Paired fault-record comparison

The proposed method exceeded source-only covariance by 6.61 percentage points (95%
bootstrap CI [1.79, 12.32]) and target Ledoit--Wolf by 5.42 points ([0.59, 11.19]).
The interval crossed zero against target sample covariance (+1.85 points,
[-2.14, 6.01]) and arithmetic entity balancing (+0.24 points, [-1.37, 2.32]). The
pilot therefore supports the value of target-health covariance transfer over pure
source transfer, but it does not establish that Log-Euclidean averaging is uniformly
better than simpler entity averaging.

![Record-level paired detection differences.](figures/paired_detection_differences.pdf)

### 6.3 Strong one-class baselines

The strongest zero-false-alarm baseline was the motor-balanced Isolation Forest, with
96.07% record-macro detection and 90.71% worst-motor detection. The proposed method
reached 95.71% and 90.00%, respectively. Their paired record difference was -0.36
percentage points (95% CI [-3.93, 3.45]), providing no evidence that either detector
was more accurate. Target-only Isolation Forest attained the highest detection rate,
97.56%, but raised 1/42 healthy alarms and therefore missed the prespecified empirical
false-alarm gate. The proposed method exceeded target one-class SVM (+6.01 points,
[1.07, 11.90]), target Minimum Covariance Determinant (+5.89 points,
[0.95, 11.67]), and motor-balanced Minimum Covariance Determinant (+3.39 points,
[0.30, 6.85]).

| One-class method | Healthy FAR | Mean detection | Worst motor |
|---|---:|---:|---:|
| Target one-class SVM | 0/42 | 89.70% | 82.68% |
| Motor-balanced one-class SVM | 0/42 | 91.25% | 82.86% |
| Target Isolation Forest | 1/42 | **97.56%** | **95.36%** |
| Motor-balanced Isolation Forest | **0/42** | **96.07%** | **90.71%** |
| Target Minimum Covariance Determinant | 1/42 | 89.82% | 84.11% |
| Motor-balanced Minimum Covariance Determinant | 1/42 | 92.32% | 87.32% |
| Proposed Log-Euclidean detector | **0/42** | 95.71% | 90.00% |

The result supports a competitive deterministic and interpretable covariance detector,
not a claim of universal state-of-the-art performance. Across five seeds, the
motor-balanced Isolation Forest varied from 96.01% to 96.85% detection and from zero
to two healthy alarms, illustrating that a single favorable seed is insufficient for
an alarm-risk claim.

![Paired record differences against strong one-class baselines.](figures/oneclass_detection_differences.pdf)

### 6.4 Adaptation budget

With common calibration and evaluation periods, 3, 6, 12, and 24 s adaptation produced
94.64%, 96.90%, 96.25%, and 94.94% mean detection. All budgets had 0/30 healthy test
false alarms. Sequential deployment gave the same nonmonotonic pattern. The apparent
6 s maximum cannot be selected after inspecting target faults; 12 s remains the frozen
primary choice. If these short durations were instead used for conformal calibration,
their minimum attainable p-values would be 0.50, 0.333, 0.20, and 0.111, all above
0.05.

![Adaptation-budget sensitivity and calibration feasibility.](figures/adaptation_budget.pdf)

### 6.5 Block-length and aggregation sensitivity

The 3 s maximum exactly reproduced the primary outputs. With the same 60 s calibration
horizon, 1 s and 2 s maxima reduced mean detection to 93.61% and 93.73%, respectively.
A 3 s 90th-percentile aggregation increased mean detection to 97.32% but introduced
1/42 healthy false alarms; its descriptive Wilson upper bound was 12.32%, above the
predeclared 12% gate. It therefore does not replace the health-ACF-selected primary
setting. Five- and six-second blocks supply only 12 and 10 calibration units and were
skipped because they cannot resolve an alarm level of 0.05.

![Block-length and aggregation sensitivity.](figures/block_sensitivity.pdf)

### 6.6 Negative findings

Every covariance method detected 100% of blocks in the lowest two labeled severities,
so the preregistered improvement claim had an uninformative ceiling. Detection was also
not monotone in severity. Three of six motor--fault-family Spearman correlations between
mean anomaly score and nominal severity were negative, including both families for the
1.0 kW motor. Reliable threshold detection on this dataset consequently does not imply
valid severity estimation.

![Nonmonotonic detection across nominal severity.](figures/severity_detection.pdf)

### 6.7 Locked external health stage

After commit `fddf2f7` froze the complete external pipeline, the proposed detector was
run once on the 32 record-disjoint healthy blocks. It raised one alarm, in the final
analyzed block of the held-out 35 Nm record. The point false-alarm rate was 3.125%, the
maximum load-specific rate was 1/8 = 12.5%, and the descriptive pooled Wilson upper
bound was 15.74%. The preregistered external health gate therefore failed because its
upper-bound criterion was 12%, despite the low point estimate. Motor-balanced and
target-only Isolation Forest raised 2/32 and 3/32 alarms, respectively. Target-only
Minimum Covariance Determinant raised none, but switching to it after revealing the
health test would be post-hoc selection and is not permitted. The pipeline remains
unchanged for the sealed fault reveal.

## 7. Discussion

The most operationally relevant result is not the near-perfect AUROC. It is the contrast
between unusable source-only classifier thresholds and a transparent target-health
calibration protocol. A short healthy trace can estimate the target coordinate system
and covariance, but a separate and substantially longer sequence is required to resolve
a 5% block alarm level. Conflating adaptation and calibration budgets would create an
anti-conservative or infinite threshold.

Equal-motor weighting prevents a motor with more retained windows from dominating the
reference geometry. The Log-Euclidean mean is mathematically natural for SPD matrices,
yet the current dataset does not distinguish it statistically from arithmetic entity
averaging. The paper therefore attributes the supported gain to motor-balanced
target-health covariance transfer as a framework, not to an unqualified superiority
claim for one matrix mean. Likewise, the strongest motor-balanced Isolation Forest is
statistically tied with the proposed detector. The covariance formulation is therefore
motivated by determinism, traceable feature interactions, and a compact reference
model rather than by a blanket accuracy advantage over nonlinear anomaly detectors.

Four limitations dominate external validity. First, each motor provides only one unique
healthy record. Calibration and later-time evaluation are sequential portions of that
same record, not independent sessions. Second, all motors are from one manufacturer and
share a fixed speed and load; “cross-capacity” is deliberately narrower than arbitrary
cross-machine transfer. Third, the method-development process inspected all KAIST
target-fault records, making the present comparisons exploratory. Fourth, a record's
40 macroblocks remain dependent observations; record-level bootstrap protects the fault
comparison from window pseudo-replication but cannot create additional healthy sessions.

The independent dual-three-phase PMSM protocol freezes features, ridge, block rule, and
alarm logic before fault reveal. It is a severe out-of-domain test because topology,
sampling rate, load, and speed profile change together, but it still represents only one
additional motor. New healthy sessions on the original three motors would provide a
cleaner validation of false-alarm transfer.

## 8. Conclusion

This exploratory study defines a leakage-resistant healthy-only protocol for stator-
fault detection across three PMSM power ratings. Motor-balanced covariance transfer and
target-health block calibration achieved 0/42 later-time healthy false alarms and 95.71%
mean fault-block detection without using a target-fault label before evaluation. Paired
record evidence favored the method over source-only covariance and target Ledoit--Wolf,
but not over all covariance alternatives or the strongest Isolation Forest baseline.
The result motivates frozen-method external validation; it does not establish arbitrary
temporal coverage, unrestricted machine generalization, severity estimation, prognosis,
or a safety guarantee.

## Data and code availability

The source dataset is available from Mendeley Data under CC BY 4.0
[@jung2022pmsmfaultdataset]. The project contains resumable checksummed download,
archive audit, duplicate removal, TDMS feature extraction, LOMO evaluation, paired
bootstrap, sensitivity, automated tests, and figure-generation scripts. Generated raw
data and results are excluded from version control and should be regenerated from the
documented commands before public release.
