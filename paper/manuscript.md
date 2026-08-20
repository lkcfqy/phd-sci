---
title: >-
  When Healthy-Only Transfer Fails in PMSM Stator-Fault Detection:
  A Leakage-Resistant Cross-Dataset Evaluation
bibliography: ../references/key_papers.bib
link-citations: true
---

> Development draft, 2026-08-21. The Korea Advanced Institute of Science and
> Technology (KAIST) study is exploratory because its target-
> fault records were inspected during method development. The independent-laboratory
> fault files were opened only after the protocol, code, environment, healthy
> calibration scores, and primary threshold had been frozen in hash-addressed commits.
> A separately preregistered transient-set audit is non-confirmatory: its frozen
> parser failed before scoring, and the repaired 200 W analysis is explicitly
> post-reveal.

## Abstract

High within-dataset accuracy does not establish that a healthy-only stator-fault
detector will transfer to a different permanent-magnet synchronous motor (PMSM). We
evaluate eleven covariance and one-class detectors across two datasets
with motor/file separation, chronological target-health splits, 3 s alarm blocks, and
no target-fault labels for fitting or thresholding. An exploratory study used three
same-manufacturer 1.0, 1.5, and 3.0 kW PMSMs at fixed speed and load. The motor-balanced
Log-Euclidean detector produced 0/42
healthy alarms and 95.71% fault-block detection. A motor-balanced Isolation
Forest produced 0/42 and 96.07%, without a resolved difference. We froze the
pipeline and health threshold before revealing 48 fault records from an
independent dual-three-phase PMSM accelerated at eight loads. The frozen detector
failed its empirical health gate (1/32 alarms; descriptive 95% Wilson upper confidence
bound 15.74% versus a 12% limit), detected 25.00% of fault blocks (95% turn-stratified
record-bootstrap interval 21.09--29.43%), and attained an area under the
receiver-operating-characteristic curve (AUROC) of 0.635. Target-only Minimum
Covariance Determinant produced
0/32 healthy alarms, 70.05% detection (65.36--75.26%), and AUROC 0.927. The frozen
detector alarmed on none of 48 records in the first three blocks but on all 48 in
the final block; detection also fell from 56.25% at 0 N m to 12.50% at 35 N m.
Conditional on this external motor, the results reveal a ranking reversal,
acceleration-aligned alarm drift, and source-augmented variants that underperformed
target-only counterparts. This audit-first protocol demonstrates why same-dataset
scores and record-any alarms can overstate deployability under compound shift.

**Keywords:** permanent-magnet synchronous motor; stator-fault diagnosis;
cross-dataset evaluation; healthy-only learning; negative transfer; leakage-resistant
validation

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

Cross-machine generalization is already an established and increasingly large-scale
problem: prior work includes six machines, 43 bearings, and 20 conditions, while a
unified benchmark spans eight public and two self-collected datasets
[@li2023causalconsistency; @zhao2024dgbenchmark]. Transfer can also reduce target
performance relative to a non-transfer reference [@wang2019negativetransfer;
@kumar2024negativetransfer]. A credible evaluation must therefore include a target-only
control rather than assuming that more source data are beneficial.

Conformal prediction supplies model-agnostic finite-sample calibration under
exchangeability [@angelopoulos2023conformal], and conformal methods have recently been
used for open-set industrial fault diagnosis [@heddoub2026opensetconformal]. Ordinary
exchangeability is not credible for densely sampled windows from a single motor
record. Work on dependent conformal inference shows that time dependence requires
additional assumptions or modified interpretation
[@chernozhukov2018dependentconformal; @barber2026timeseriesconformal]. Treating
thousands of adjacent windows as independent calibration samples would consequently
overstate the evidence.

This is not a hypothetical concern. Across two bearing datasets, changing from easier
signal splits to run-, day-, and physical-part holdouts caused accuracy differences
exceeding 40 percentage points in some pipelines [@wheat2024dataleakage]. More broadly,
structured cross-validation is required when observations are temporally or
hierarchically dependent [@roberts2017structuredcv], and splitting one acquisition into
many windows does not create independent experimental replication
[@hurlbert1984pseudoreplication].

This paper evaluates healthy-only detectors around that deployment constraint. Its
contributions are:

1. an audit-first evaluation that separates physical motors and files, preserves
   chronological health regions, and never treats adjacent windows as independent
   experimental repeats;
2. a frozen, one-time external fault reveal in which features, eleven detectors,
   calibration scores, thresholds, and failure criteria were committed before any
   external fault value was opened;
3. direct evidence of a cross-dataset ranking reversal: near-ceiling same-family
   performance did not transfer under simultaneous topology, sampling-rate, speed,
   and load shift;
4. a diagnosis of negative transfer and operating-point confounding using target-only
   versus source-augmented comparators, ordered-block alarm drift, and record-level
   paired uncertainty;
5. an explicit evidence boundary: intervals are conditional on the recorded motors,
   block calibration is empirical under time dependence, and no post-reveal model is
   relabeled as the primary method.

## 2. Related work

### 2.1 PMSM stator-fault signatures and operating conditions

Motor current signature analysis detects winding asymmetry through sequence components,
Park/Clarke current-vector geometry, and spectral changes. Negative-sequence current is
particularly relevant to early interturn faults [@jeong2017negativesequence], while
harmonic behavior can depend on winding configuration and the closed-loop drive
[@zafarani2018itscreview]. This dependence motivates the use of ratios, normalized
spectral features, and within-motor healthy references instead of raw amplitude alone.
Order-tracked PMSM indicators have specifically been proposed for nonstationary speed
and multiple loads [@urresty2013nonstationary], while physical--data dual models address
rapidly varying speed in sparse-data PMSM diagnosis [@li2024physicaldatapmsm]. These
studies motivate explicit operating-condition treatment rather than interpreting every
frequency-dependent score change as a fault effect.

The present work does not attempt fault-phase localization or severity regression.
Those are distinct supervised tasks and can require motor parameters, injected signals,
or target fault examples. The observed nonmonotonic relation between the public
dataset's nominal severity labels and the proposed anomaly score further prevents a
valid severity claim.

### 2.2 Cross-machine diagnosis, negative transfer, and split design

Cross-domain machinery diagnosis commonly aligns source and target representations or
learns domain-invariant features. Benchmark surveys include source aggregation,
domain-adversarial neural networks (DANN), maximum mean discrepancy (MMD), correlation
alignment (CORAL), mixup, meta-learning, and ensemble approaches
[@xiao2025dgsurvey]. Collaborative multimachine and multi-dataset benchmarks establish
that neither cross-machine diagnosis nor domain generalization is itself novel
[@li2023causalconsistency; @zhao2024dgbenchmark]. Recent machinery methods also attempt
to mitigate negative transfer [@kumar2024negativetransfer;
@liu2025frequencyguided].

The evaluation unit remains a separate problem. Signal-window holdout can share a
physical part, acquisition day, or continuous trajectory between train and test and
thereby measure interpolation rather than deployment [@wheat2024dataleakage]. This
study instead treats each physical motor from the Korea Advanced Institute of Science
and Technology (KAIST) dataset as the outer holdout, keeps external health roles in
separate files/loads where possible, and reports paired fault effects at the record
level. A source-supervised classifier is retained as a domain-shift
diagnostic, while the principal task is a healthy-only target alarm.

### 2.3 Healthy-only detectors, covariance geometry, and calibrated alarms

A one-class support vector machine (SVM), Isolation Forest, support-vector data
description, and Minimum
Covariance Determinant are established one-class or robust-description methods
[@scholkopf2001support; @liu2008isolationforest; @tax2004svdd;
@rousseeuw1999mcd]. Machinery studies have also fitted deep and classical one-class
detectors from normal signals, although random normal-sample splits and
fault-outcome-based hyperparameter selection can weaken a deployment interpretation
[@yoon2024deeponeclass]. These methods are consequently comparators here, not claimed
innovations.

A covariance matrix captures interactions among current-shape, imbalance, harmonic,
and spectral features. Direct Euclidean averaging preserves symmetry and positive
definiteness but does not respect the intrinsic geometry of symmetric
positive-definite (SPD) matrices. The
Log-Euclidean construction maps matrices through the matrix logarithm, averages them
in a vector space, and maps the result back by the matrix exponential
[@arsigny2006logeuclidean]. Here each motor contributes one covariance and therefore
one equal vote, irrespective of window count.

The resulting Mahalanobis distance is only an anomaly score; it is not yet an alarm.
Target healthy block scores are used to compute upper-tail conformal p-values. This
calibration does not repair arbitrary temporal dependence. It instead provides an
auditable empirical threshold whose calibration unit is a non-overlapping macroblock,
with the dependence limitation reported explicitly.

Conformal anomaly alarms for heterogeneous industrial fleets also predate this study
[@farouq2021mondrianfleet; @farouq2022conformalfleet], and limited-sample process
monitoring can miss nominal false-alarm targets even with conformal thresholds
[@diallo2025falsealarms]. The narrower gap examined here is the combination of a
fault-blind frozen external reveal, record/entity-aware reporting, and same-algorithm
target-only versus source-assisted controls. A targeted literature audit did not locate
a rotating-machine study combining all three, but this absence statement is not a
priority claim.

## 3. Dataset and leakage-resistant protocol

### 3.1 Dataset audit

The KAIST/Mendeley dataset contains vibration and three-phase current measurements from
1.0, 1.5, and 3.0 kW PMSMs at a fixed 3000 rpm and load setting
[@jung2023pmsmfaultdata; @jung2022pmsmfaultdataset]. Each motor has interturn and
intercoil faults at seven nominal nonzero severity levels. Current was sampled at
100 kHz.

The archive structure nominally contains one healthy record under each fault family.
For every motor, those two healthy members have identical uncompressed size and cyclic
redundancy check (CRC); an extracted pair was additionally identical by a 256-bit Secure
Hash Algorithm (SHA-256) digest. They are aliases rather than independent repeats. After
deduplication, the current study contains three healthy and 42 fault records. Several
Technical Data Management Streaming (TDMS) fault files contain 121--149 s although the dataset
description specifies 120 s. Every record is restricted to its first 120 s, producing
equal record weight.

Each record is divided into 600 non-overlapping 0.2 s windows. Window features include
phase root-mean-square (RMS) ratios, crest factor, kurtosis, Clarke-vector dispersion,
sequence-current
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
separate calibration blocks. The motor holdout, chronological target-health split, and
scoring flow are summarized in Fig. 1.

![Motor holdout, sequential target-health split, and method flow.](figures/protocol_overview.pdf)

## 4. Evaluated healthy-only detectors and alarm calibration

The frozen external protocol compared eleven detectors. Five covariance-score variants
used target Ledoit--Wolf, target sample covariance, source-only covariance, arithmetic
entity balancing, or Log-Euclidean entity balancing. Six one-class variants paired
target-only or motor-balanced source-plus-target fitting with one-class SVM, Isolation
Forest, or Minimum Covariance Determinant (MinCovDet). The Log-Euclidean variant below
was designated and frozen as the primary detector before the external fault reveal;
that designation is retained even though another comparator performed
better after reveal.

Let $x_{m,i}\in\mathbb{R}^d$ be a scale-free feature vector from motor $m$. For
each motor, allowed healthy reference samples define a coordinate-wise median
\(c_m\) and robust scale \(r_m\). The standardized vector is

\[
\widetilde{x}_{m,i}=(x_{m,i}-c_m)\oslash r_m.
\]

Only source healthy reference blocks and target adaptation blocks are allowed in these
statistics. Let $S_m$ be the sample covariance of the standardized healthy samples.
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

For block $b$, $A_b=\max_{i\in b}s(x_i)$. Given $n=20$ target healthy
calibration scores, the upper-tail p-value is

\[
p_b=\frac{1+\sum_{j=1}^{n}\mathbf{1}(A_j\ge A_b)}{n+1}.
\]

The block raises an alarm when $p_b\le0.05$. Because calibration blocks are ordered
parts of one health record, the p-value is interpreted empirically under a
block-stationarity or weak-dependence approximation, not as distribution-free coverage
under arbitrary temporal dependence.

## 5. Experiments

### 5.1 Exploratory same-family KAIST comparison

The implemented covariance comparators are target Ledoit--Wolf, regularized target
sample covariance, source-only covariance, and arithmetic entity-balanced covariance.
All share the same feature representation, target-health split, block maximum, and
calibration rule. A supervised logistic classifier and gradient boosting model diagnose
the initial source-to-target threshold shift.

Strong one-class comparators use either target adaptation health alone or a
motor-balanced union of source and target health. They comprise a one-class SVM,
Isolation Forest, and Minimum Covariance Determinant. Their hyperparameters were fixed
without target-fault labels. Stochastic methods were additionally evaluated across five
fixed seeds; the primary seed was frozen before external fault reveal.

Primary outcomes are the raw healthy false-alarm count, pooled Wilson confidence
interval (CI), maximum per-motor empirical false-alarm rate (FAR), mean and worst-motor
fault-block detection, and block AUROC. Paired method differences are computed for each
of the 42 target fault
records. A 10,000-replicate bootstrap resamples records within target motor and then
averages the three motor means. Macroblocks and windows are not treated as independent
experimental repetitions.

Target adaptation is varied over 3, 6, 12, and 24 s in two sensitivity designs. The
fixed-horizon design holds calibration and test time constant; the sequential design
moves calibration directly after each adaptation prefix. The original 12 s setting is
retained irrespective of target-fault results.

### 5.2 Frozen independent-laboratory protocol and one-time reveal

The external target is a public dual-three-phase PMSM with winding taps, two
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
used for calibration. The 48 public fault records remained sealed until the protocol,
feature parser, all comparator implementations, environment, healthy calibration
scores, and thresholds were captured in hash-addressed commits. All 48 files were then
downloaded from the official record, verified against a frozen filename, byte-count,
and Message-Digest Algorithm 5 (MD5)
manifest, and processed once over the unchanged [12, 36) s interval. The run yielded a
complete 6 fault-turn counts by 8 loads grid (384 system blocks). The chronological
reveal log and hash-addressed commits are retained as audit evidence.

The predeclared empirical health gate (H1) required both a descriptive pooled 95%
Wilson upper confidence bound no greater than 12% and a maximum load-specific empirical
FAR no greater than 15%. Because its 32 blocks came from four records of one motor, H1
was an engineering decision rule rather than a population-level probability guarantee.

### 5.3 Prospectively frozen secondary transient-set audit

A secondary stress test used a public 10 kHz dataset containing 12 records from one
200 W PMSM and nine from one 20 kW PMSM [@zezula2024transientpmsm]. Every record
transitions from prefault operation to an interturn short circuit under steady-state,
load-transient, or speed-transient operation; there are no independent healthy-only
records. Before loading any signal values, we froze the archive hash, full-record
inclusion rule, parser contract, channel whitelist, onset rule, method set, thresholds,
and outputs. Only measured alpha-beta current entered the 26-feature score; fault
current located onset and electrical speed was retained for quality control only.

The primary endpoint used non-overlapping 0.2 s windows, a 0.2 s prefault guard, and
the first 1 s after the frozen causal onset. Within each motor, one complete record was
held out while the remaining records were assigned by hash to healthy-reference fitting
or calibration. At least 19 calibration windows and at least 80% compatible records per
motor were required. Parser incompatibility and failure of this motor-level gate were
predeclared reportable outcomes: no record, time interval, or onset could be manually
substituted after reveal. Because prefault segments and fault segments occur within the
same records, this audit was designated a secondary transient stress test rather than a
third independent health-cohort validation.

## 6. Results

### 6.1 Cross-capacity detection and empirical false-alarm risk

The proposed detector raised no alarm in 42 later-time target healthy blocks. Zero
observed events does not imply zero population risk: the pooled 95% Wilson upper bound
was 8.38%. Fault-block detection was 100.00%, 90.00%, and 97.14% when 1.0, 1.5, and
3.0 kW were targets, respectively. The fold mean was 95.71%, and the worst-motor result
was 90.00%. Table 1 compares the five covariance-score variants under the common
protocol.

| Method | Healthy false-alarm rate | Descriptive Wilson upper | Mean detection | Worst motor | Mean AUROC |
|---|---:|---:|---:|---:|---:|
| Target Ledoit--Wolf | 1/42 | 12.32% | 90.30% | 82.14% | 0.9969 |
| Target sample covariance | 0/42 | 8.38% | 93.87% | 86.79% | 0.9983 |
| Source-only covariance | 0/42 | 8.38% | 89.11% | 70.18% | 0.9968 |
| Arithmetic entity balance | 0/42 | 8.38% | 95.48% | 87.86% | 0.9989 |
| **Log-Euclidean entity balance** | **0/42** | **8.38%** | **95.71%** | **90.00%** | **0.9993** |

Per-motor detection and descriptive healthy false-alarm intervals are shown in Fig. 2.

![Per-motor detection and healthy false-alarm intervals.](figures/method_performance.pdf)

### 6.2 Paired fault-record comparison

The proposed method exceeded source-only covariance by 6.61 percentage points (95%
bootstrap CI [1.79, 12.32]) and target Ledoit--Wolf by 5.42 points ([0.59, 11.19]).
The interval crossed zero against target sample covariance (+1.85 points,
[-2.14, 6.01]) and arithmetic entity balancing (+0.24 points, [-1.37, 2.32]). The
pilot therefore supports the value of target-health covariance transfer over pure
source transfer, but it does not establish that Log-Euclidean averaging is uniformly
better than simpler entity averaging. The record-level paired differences are shown in
Fig. 3.

![Record-level paired detection differences.](figures/paired_detection_differences.pdf)

### 6.3 Strong one-class baselines

The strongest baseline with zero observed healthy alarms was the motor-balanced
Isolation Forest, with
96.07% record-macro detection and 90.71% worst-motor detection. The proposed method
reached 95.71% and 90.00%, respectively. Their paired record difference was -0.36
percentage points (95% CI [-3.93, 3.45]), providing no evidence that either detector
was more accurate. Target-only Isolation Forest attained the highest detection rate,
97.56%, but raised 1/42 healthy alarms and therefore missed the prespecified empirical
false-alarm gate. The proposed method exceeded target one-class SVM (+6.01 points,
[1.07, 11.90]), target Minimum Covariance Determinant (+5.89 points,
[0.95, 11.67]), and motor-balanced Minimum Covariance Determinant (+3.39 points,
[0.30, 6.85]). Table 2 reports the one-class comparison under the same health gate.

| One-class method | Healthy false-alarm rate | Mean detection | Worst motor |
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
an alarm-risk claim. Paired record differences against these baselines appear in Fig. 4.

![Paired record differences against strong one-class baselines.](figures/oneclass_detection_differences.pdf)

### 6.4 Adaptation budget

With common calibration and evaluation periods, 3, 6, 12, and 24 s adaptation produced
94.64%, 96.90%, 96.25%, and 94.94% mean detection. All budgets had 0/30 healthy test
false alarms. Sequential deployment gave the same nonmonotonic pattern. The apparent
6 s maximum cannot be selected after inspecting target faults; 12 s remains the frozen
primary choice. If these short durations were instead used for conformal calibration,
their minimum attainable p-values would be 0.50, 0.333, 0.20, and 0.111, all above
0.05. The adaptation-budget results and calibration feasibility boundary are shown in
Fig. 5.

![Adaptation-budget sensitivity and calibration feasibility.](figures/adaptation_budget.pdf)

### 6.5 Block-length and aggregation sensitivity

The 3 s maximum exactly reproduced the primary outputs. With the same 60 s calibration
horizon, 1 s and 2 s maxima reduced mean detection to 93.61% and 93.73%, respectively.
A 3 s 90th-percentile aggregation increased mean detection to 97.32% but introduced
1/42 healthy false alarms; its descriptive Wilson upper bound was 12.32%, above the
predeclared 12% gate. It therefore does not replace the primary setting selected from
health autocorrelation. Five- and six-second blocks supply only 12 and 10 calibration units and were
skipped because they cannot resolve an alarm level of 0.05. Block-length and aggregation
sensitivity are summarized in Fig. 6.

![Block-length and aggregation sensitivity.](figures/block_sensitivity.pdf)

### 6.6 Negative findings

Every covariance method detected 100% of blocks in the lowest two labeled severities,
so the original exploratory pilot hypothesis had an uninformative ceiling. Detection was also
not monotone in severity. Three of six motor--fault-family Spearman correlations between
mean anomaly score and nominal severity were negative, including both families for the
1.0 kW motor. Reliable threshold detection on this dataset consequently does not imply
valid severity estimation. The nonmonotonic severity patterns are displayed in Fig. 7.

![Nonmonotonic detection across nominal severity.](figures/severity_detection.pdf)

### 6.7 Frozen external validation and ranking reversal

After the complete pipeline and health thresholds were frozen, all 48 external fault
files passed the predeclared filename, variable, sample-count, timebase, finite-value,
and interval checks. No file or block was excluded. The frozen Log-Euclidean
detector retained the one healthy alarm observed at the locked health stage. Its point
FAR was 1/32 = 3.125% and its maximum load-specific FAR was 1/8 = 12.5%, but the
descriptive pooled 95% Wilson upper bound was 15.74%. It therefore failed the
predeclared H1 criterion of at most 12% upper-bound risk. This failure means that the
available evidence was insufficient to pass the gate; it does not prove that the
population FAR exceeds 5%.

The fault result reversed the exploratory KAIST ranking. The frozen detector identified
25.00% of the 384 ordered fault blocks (turn-stratified record-bootstrap 95% interval,
21.09--29.43%) and attained pooled block AUROC 0.6354. Target-only MinCovDet, which had
been implemented before reveal, produced 0/32 healthy alarms, 70.05% detection
(65.36--75.26%), and AUROC 0.9268. The paired improvement of target MinCovDet over the
frozen detector was 45.05 percentage points (40.63--49.48%). Target-only MinCovDet is
reported as the observed comparator leader, not retroactively redesignated as the
primary method.

In a post-reveal analysis applying Holm adjustment across the ten listed
candidate-versus-primary contrasts, the target-MinCovDet comparison retained an
adjusted $p=0.001$. The 95% interval above is an unadjusted percentile interval; Holm
correction applies only to the $p$-values. This adjustment covers only that listed
conditional comparison family and does not turn the one external motor into a
population sample.

This ranking was more stable than the exact MinCovDet operating point. In a post-reveal
robustness analysis using five previously fixed seeds, target-only MinCovDet remained
above the other stochastic methods
but ranged from 65.36% to 77.08% detection and from 0 to 2 healthy alarms; only three of
five seeds passed H1. Its primary-seed outcome must therefore not be presented as a
seed-invariant performance guarantee. Table 3 gives the complete frozen external method
comparison.

| External method | Healthy alarms | Fault-block detection | Block AUROC | H1 |
|---|---:|---:|---:|---|
| Target MinCovDet | **0/32** | **70.05%** | **0.9268** | **pass** |
| Target Isolation Forest | 3/32 | 59.90% | 0.8670 | fail |
| Target sample covariance | 1/32 | 55.99% | 0.8757 | fail |
| Motor-balanced Isolation Forest | 2/32 | 50.52% | 0.8245 | fail |
| Target Ledoit--Wolf | 1/32 | 36.72% | 0.7675 | fail |
| Motor-balanced MinCovDet | 1/32 | 30.21% | 0.7013 | fail |
| Arithmetic entity covariance | 1/32 | 27.34% | 0.6972 | fail |
| **Frozen Log-Euclidean detector** | **1/32** | **25.00%** | **0.6354** | **fail** |
| Target one-class SVM | 1/32 | 12.76% | 0.7209 | fail |
| Motor-balanced one-class SVM | 1/32 | 12.76% | 0.6876 | fail |
| Source-only covariance | 1/32 | 12.76% | 0.5747 | fail |

Figure 8 jointly shows fault detection, healthy alarms, and the predeclared H1 decision.

![External fault detection, healthy false alarms, and the predeclared H1 decision.](figures/external_method_performance.pdf)

### 6.8 Operating-point drift and negative transfer

The frozen detector did not alarm on any of the 48 fault records in analysis blocks
0--2, but alarmed on every record in block 7. Its only held-out healthy alarm also
occurred in block 7. Over the same ordered blocks, approximate median speed rose from
218 to 2,214 rpm. The fault and healthy score trajectories therefore moved in the same
direction as the operating point, making the apparent 48/48 record-any detection
misleading: each record could be counted as detected by a late, speed-entangled alarm.

At the first four blocks, block detection was 2.60% and only 10.42% of records had any
alarm. By the first seven blocks these values were 14.29% and 52.08%; only inclusion of
the eighth block raised them to 25.00% and 100%. The median first alarm was block 6,
corresponding to an approximate 1,643 rpm proxy taken from the matching healthy load
record. In contrast, target MinCovDet detected 54.69% of the first four blocks and had a
median first alarm at block 1 (approximately 318 rpm).

The pooled Spearman association between block position and frozen score was 0.836 for
held-out health and 0.821 for faults. Yet the equal-weight mean of eight
block-position-specific AUROCs was 0.805, compared with the pooled AUROC of 0.635.
This post-reveal diagnostic suggests that fault-ranking information remained after
matching acceleration position, while the transported unconditional score and fixed
threshold were overwhelmed by operating-point drift. The threshold-normalized score and
alarm trajectories are shown in Fig. 9.

![Threshold-normalized score and alarm drift over the acceleration trajectory.](figures/external_condition_drift.pdf)

The failure was also load dependent. Frozen-detector block detection fell from 56.25%
at 0 N m to 12.50% at 35 N m. Across fault-turn counts, detection ranged only from
15.63% to 32.81% and did not increase monotonically. The full 6 by 8 condition grid
shows that many high-load records triggered in only one of eight ordered blocks. The
complete fault-turn-by-load alarm grid is shown in Fig. 10.

![Frozen-detector block detection over fault turns and load.](figures/external_proposed_heatmap.pdf)

Source data were not uniformly harmful: the frozen target-adapted Log-Euclidean
configuration exceeded pure source covariance by 12.24 points (paired interval
8.33--16.41%), although those configurations also differ in covariance aggregation and
regularization. Within the same MinCovDet estimator family, the source-augmented variant
underperformed the target-only variant, 30.21% versus 70.05%; the paired target-only
minus motor-balanced difference was 39.84 points (35.42--44.27%). On this motor under
the frozen protocol, that same-estimator contrast is evidence of conditional negative
transfer from source augmentation.

### 6.9 Post-reveal feature and geometry diagnosis

An exploratory, analysis-only audit reconstructed the frozen Log-Euclidean precision
matrices from hash-locked inputs. It reproduced all 448 frozen block scores to a maximum
absolute error of $3.64\times10^{-12}$. For a symmetric precision matrix $P$, the
winning window's Mahalanobis score was allocated as
$c_j=x_j(Px)_j$, which splits each cross-term equally and satisfies
$\sum_j c_j=x^\top Px$. No detector was refit and no threshold was changed. Reported
contribution percentages are means of block-normalized absolute shares from the winning
window under this chosen decomposition; they are not unique model feature weights.

Electrical fundamental frequency was almost nondiscriminative after matching health and
fault at the same load and block position (direction-free single-feature AUROC 0.504;
matched Hedges' $g$ approximately zero), yet the chosen decomposition allocated it
18.07% of absolute fault-score contribution and 38.54% of held-out healthy contribution.
In block 7 those shares rose to 39.63% and
89.31%, respectively. Conversely, the maximum and mean third-harmonic ratios each had
single-feature AUROC above 0.925 and matched standardized effects near 1.0, but together
received less than 0.6% of the frozen fault-score contribution. Phase-A RMS ratio
combined high discrimination (AUROC 0.815) with 21.62% contribution, while sequence
unbalance produced AUROC 0.771 and 6.99% contribution. At the feature-family level,
absolute fault contribution was 49.79% current shape, 24.91% sequence imbalance,
18.07% speed proxy, 6.53% harmonics/sidebands, and 0.70% entropy.

This mismatch supports a specific failure interpretation: under the chosen symmetric
decomposition, observed scores allocated substantial contribution to an operating-point
direction with almost no matched fault contrast, while allocating little contribution to
some fault-sensitive harmonic directions.
It is not a causal feature-selection result. The same healthy load/block/subsystem is
reused across six fault-turn conditions and every record comes from one motor, so these
effect sizes are descriptive and post-reveal only. Figure 11 contrasts single-feature
discrimination with the frozen-score contribution allocation.

![Post-reveal single-feature discrimination versus frozen-score contribution.](figures/external_feature_geometry.pdf)

### 6.10 Sampling-rate sensitivity

To examine whether the 100 kHz KAIST versus 10 kHz external sampling mismatch could
explain the failure under this pipeline, every KAIST current record was
antialias-filtered and resampled to 10 kHz
with polyphase resampling before applying the unchanged 0.2 s windows, feature schema,
3 s blocks, ridge, calibration, and external protocol. This analysis was specified
after reveal and is diagnostic rather than confirmatory.

The 10 kHz KAIST arm remained usable internally: exploratory leave-one-motor-out
detection decreased from 95.71% to 91.96% and AUROC from 0.9993 to 0.9947. Replacing
only the source arm in
the frozen external run did not recover transfer. Log-Euclidean external detection
changed from 25.00% to 24.74%, AUROC from 0.6354 to 0.6331, and healthy alarms remained
1/32. Forty-seven of 48 fault records were unchanged and one worsened; none improved.
Target-only MinCovDet was, by construction, unchanged at 70.05%, so its lead over the
transfer detector increased from 45.05 to 45.31 points. The sampling-rate mismatch may
affect individual features, but this controlled sensitivity does not support it as the
primary explanation for the observed negative transfer.

### 6.11 Secondary transient-set compatibility and null sensitivity

The frozen primary parser attempted all 21 official records and accepted none. The
MATLAB `timeseries` objects contained empty explicit time arrays even though uniform
10 kHz timing was encoded in their metadata, whereas the frozen parser required an
explicit monotonic time vector. Consequently, the primary run produced no features,
scores, or detector comparison; this is a prospective compatibility failure, not a
fault-detection result.

An opt-in post-reveal structural repair reconstructed time only from the stored
start, increment, and length metadata without changing signals, features, or onset
rules. It made 12/12 records from the 200 W motor and 4/9 from the 20 kW motor
compatible. The other five 20 kW onsets overlapped the frozen 0.5 s baseline, so that
motor failed the 80% gate (44.44%) and was not selectively reanalyzed. A descriptive
leave-one-record-out sensitivity on the single 200 W motor then produced 0/60 alarms
in the primary first-second fault windows for every one of 12 detectors, and 0/120
across the full 2 s post-onset horizon. Held-out prefault alarms ranged from 7/176 to
13/176. Proposed produced 8/176 (4.55%) with mean record AUROC 0.541; Target MinCovDet
produced 9/176 (5.11%) with AUROC 0.564. With no standalone healthy sessions, zero
thresholded detection, and only one analyzed motor, this post-reveal result neither
confirms generalization nor identifies positive or negative transfer. Full compatibility,
method, and hash tables are reported in Online Resource 1, Section S9.

## 7. Discussion

The central result is the external ranking reversal, not the near-ceiling KAIST AUROC.
Within one manufacturer, topology, speed, and load, both the frozen Log-Euclidean
detector and a motor-balanced Isolation Forest appeared highly effective. Under a
simultaneous change in winding topology, measurement rate, load, and speed trajectory,
the same frozen score lost detection and failed the predeclared empirical health gate. This is the
deployment gap that random-window or same-family holdout cannot measure.

The ordered-block analysis changes the interpretation of the raw external outcomes.
All 48 fault records alarmed in block 7, while some had already alarmed in earlier
blocks; the final block's operating point also drove the healthy score upward. Record-any detection would
therefore report 100% while hiding poor early-trajectory coverage and a late healthy
false alarm. Pooled area under the precision-recall curve (AUPRC) similarly adds
limited operational information unless
interpreted against the 384/416 = 92.3% fault-block prevalence, which gives an
all-positive ranking a baseline near 0.923. The appropriate evidence is the joint display of chronological
block detection, held-out health alarms, per-condition coverage, and record-level
paired differences.

Conditional negative transfer on this motor is not equivalent to saying that source
knowledge has no value. The target-adapted Log-Euclidean configuration outperformed
pure-source covariance, while source-augmented MinCovDet underperformed its target-only
counterpart under the same estimator family. A plausible mechanism is a mismatch
between an unconditional healthy reference and the external acceleration trajectory:
speed-sensitive spectral and covariance directions move both healthy and faulty scores
together. The frozen-geometry audit supports this interpretation: fundamental frequency
received large score contribution despite chance-level matched discrimination, while a
third-harmonic contrast was highly discriminative but weakly weighted. Antialiasing the
KAIST source to the same 10 kHz rate did not rescue transfer, ruling against a simple
sampling-rate-only explanation under this pipeline. A block-conditioned analysis can
still retain fault-ranking information, which motivates operating-condition-aware
healthy residuals, but any such detector is post-reveal development on this dataset and
requires a new untouched confirmation.

The calibration design also sets a practical boundary. A short target trace can estimate
a coordinate system, but a nominal 5% conformal p-value needs at least 19 calibration
units. In this study those units are ordered blocks from a few continuous records, not
independent sessions; the resulting Wilson intervals and p-values are descriptive under
a stationarity/mixing interpretation. They are not machine-level safety guarantees.

The secondary transient audit adds a different failure mode: a validation can fail
before model comparison if file-time semantics or available prefault baselines do not
meet the frozen contract. Reconstructing documented implicit time made analysis
possible, but it did not restore confirmatory status. The 200 W null sensitivity is
consistent with cross-record healthy heterogeneity overwhelming the short post-onset
change under these thresholds; because this interpretation followed reveal, it is a
design diagnostic rather than evidence for a revised detector.

Six limitations dominate the claims. First, each KAIST motor has only one unique
healthy record, so its calibration and later-time evaluation are not independent
sessions. Second, all KAIST machines share manufacturer and fixed operating condition.
Third, the KAIST target faults were inspected during development and are exploratory.
Fourth, the external 48-record grid comes from one physical dual-three-phase motor;
record bootstrap quantifies variability across its recorded conditions, not across a
population of motors. Fifth, the external shift is compound, so this experiment cannot
causally separate topology, sampling rate, controller, speed, and load effects. Sixth,
the secondary transient dataset has no independent healthy records; its frozen parser
failed, only four of nine 20 kW records passed the repaired baseline gate, and the
reported 200 W sensitivity is post-reveal and conditional on one motor.

The next method study should use only healthy data to condition scores on electrical
frequency and load, include a target-only MinCovDet primary comparator, harmonize
sampling-rate sensitivity, and freeze early-trajectory detection and FAR criteria before
evaluation on another unseen motor or independent laboratory. Multiple genuinely
independent healthy sessions, documented time semantics, and adequate prefault duration
are required before session-level risk can be estimated.

## 8. Conclusion

This study demonstrates why healthy-only PMSM fault detection must be evaluated across
physical files, motors, operating trajectories, and laboratories rather than adjacent
windows. A detector with 95.71% exploratory same-family detection fell to 25.00% after a
frozen external reveal, failed its health-risk gate, and was exceeded by a target-only
robust covariance comparator at 70.05%. The failure was structured: alarms drifted
across ordered blocks in alignment with the acceleration trajectory, detection weakened
with load, and source-augmented variants underperformed target-only counterparts on this
motor. The contribution is
therefore not a claim of a universally superior detector, but a reproducible account of
ranking reversal and conditional negative transfer that preserves the frozen primary
failure. A prospectively logged secondary audit likewise did not supply confirmatory
evidence: its primary parser was incompatible with the stored time representation, and
all methods missed the first second in the repaired single-motor sensitivity. Reliable
deployment requires operating-condition-aware target-health modeling, independent
healthy sessions, and a new untouched confirmation; the present evidence does not
establish unrestricted machine generalization, severity estimation, prognosis, or a
safety guarantee.

## Data and code availability

The KAIST source dataset is available from Mendeley Data; the independent
dual-three-phase PMSM dataset and the secondary 200 W/20 kW transient dataset are
available from Zenodo. All three are under the Creative Commons Attribution (CC BY)
4.0 licence
[@jung2022pmsmfaultdataset; @kozovsky2024dualthreephasepmsm;
@zezula2024transientpmsm]. The project contains
resumable checksummed downloads, archive and MATLAB-file audits, duplicate removal, feature
extraction, motor/file-level evaluation, paired bootstrap, sensitivity analyses,
automated tests, and figure generation. Raw data remain excluded from version control;
the reveal manifests, protocols, selected derived results, and audit metadata are
retained for exact reconstruction. Detailed partitions, thresholds, comparator results,
post-reveal diagnostics, sampling-rate controls, transient-set compatibility outcomes,
and file hashes are provided in Online Resource 1. The anonymized code, automated tests,
protocols, and selected derived outputs needed to rerun the reported analyses are
provided in Online Resource 2.

## Statements and declarations

### Competing interests

The authors declare no financial or non-financial competing interests.

### Ethics approval and consent to participate

Not applicable. This study reanalyzes public experimental machine-current datasets and
does not involve human participants, animals, or personal data.

### Funding

Funding information is supplied on the separate title page and withheld from this file
for double-blind review.

### Author contributions

The author-contribution statement is supplied on the separate title page and withheld
from this file for double-blind review.

### Generative AI assistance

A large language model (LLM)-based coding assistant was used under human direction for
implementation support, automated consistency checks, and manuscript drafting and
editing. All reported computations were executed on the cited datasets and checked
against frozen outputs and automated tests. The human authors remain responsible for
reviewing and approving the submitted version.
