# Paper 1 Outline (Evidence-Locked Living Draft)

## Fixed working title

**Healthy-Only Cross-Capacity PMSM Stator-Fault Detection via Motor-Balanced
Covariance Transfer and Block-Conformal Calibration**

中文：**基于电机实体平衡协方差迁移与健康样本块共形校准的跨容量 PMSM 定子故障
检测**。

## Manuscript status and claim boundary

当前三折结果是 **exploratory pilot**，不是独立确认性试验。全部 target-fault records 已在
方法迭代期间用于结果检查；论文必须披露这一点，不能称其为 untouched test。现有证据
支持继续形成 SCI 稿件和开展外部验证，但不保证投稿或录用。

“Cross-capacity”仅指 KAIST 数据中同厂商、同拓扑、固定 3000 rpm 与单一负载下的 1.0、
1.5、3.0 kW 三台 PMSM，不代表跨厂商、跨拓扑或变工况泛化。

## One-sentence contribution

We introduce an equal-motor Log-Euclidean covariance transfer score and calibrate its
3-s block alarms with only 12 s of target healthy adaptation data and 20 target healthy
calibration blocks, enabling zero-target-fault-label evaluation under three-fold
leave-one-motor-out separation.

## Draft abstract (numbers must remain traceable)

Deploying a stator-fault detector to a permanent-magnet synchronous motor of a new
power rating creates a substantial score-distribution shift, while labeled target faults
are normally unavailable. We study healthy-only cross-capacity transfer on three
same-manufacturer PMSMs (1.0, 1.5, and 3.0 kW) using a three-fold leave-one-motor-out
protocol. Duplicate healthy aliases are removed by content audit, every recording is
truncated to a common 120 s, and correlated 0.2-s windows are aggregated into
non-overlapping 3-s blocks. Scale-free current features are robustly centered per motor.
One healthy covariance is estimated for each of the two source motors and the target
motor, regularized with a source-only selected ridge of 0.01, and combined by an
equal-weight Log-Euclidean mean. Target-centered Mahalanobis scores are converted to
block maxima and calibrated at alpha = 0.05 using 20 target healthy blocks; no target
fault label is used for fitting, selection, or calibration. In the exploratory pilot, the
method produced 0 false alarms among 42 later-time healthy blocks (95% Wilson upper
bound, 8.38%), detected 95.71% of 1,680 fault blocks, achieved 90.00% worst-motor
detection, and obtained a mean block AUROC of 0.9993. Motor-stratified paired record
bootstrap favored the method over source-only covariance (+6.61 percentage points,
95% CI [1.79, 12.32]) and target Ledoit--Wolf (+5.42 points, [0.59, 11.19]), but did
not resolve superiority over target sample covariance or arithmetic entity balancing.
Against a motor-balanced source+target Isolation Forest, detection was 95.71% versus
96.07%, with 0/42 healthy false alarms for both; the paired difference was -0.36 points
(95% CI [-3.93, 3.45]), providing no superiority evidence. A target-only Isolation
Forest reached 97.56% detection but produced 1/42 false alarms, whose descriptive Wilson
upper bound of 12.32% missed the predeclared 12% empirical gate.
Because calibration and later-time health originate from one continuous healthy record
per motor, the results establish empirical block-risk calibration rather than unrestricted
distribution-free temporal coverage. Severity-score monotonicity failed and is not a
claimed capability.

## Contribution list (for Introduction)

1. **Leakage-aware problem formulation.** Three-fold motor-level holdout with zero
   target-fault labels and sequential target-health adaptation/calibration/test regions,
   separated by guard blocks.
2. **Motor-balanced covariance transfer.** One covariance per motor is combined on the
   SPD manifold as
   \(\Sigma_{LE}=\exp[M^{-1}\sum_m\log(S_m+\lambda\bar v_m I)]\), preventing window
   count from determining motor weight.
3. **Target-health block calibration.** Fifteen 0.2-s window scores form a 3-s block
   maximum; 20 target healthy blocks generate conformal p-values at alpha = 0.05.
4. **Audit-first empirical evaluation.** Healthy aliases are deduplicated, unequal raw
   durations are truncated to 120 s, and the evaluation unit respects the observed 3-s
   nuisance cycle.
5. **Negative findings.** The study reports the low-severity ceiling effect, failed
   severity monotonicity, temporal-dependence caveat, statistical ties against two
   covariance baselines, and the unresolved comparison with motor-balanced Isolation
   Forest.

## Evidence-locked protocol summary

| Item | Frozen pilot setting |
|---|---|
| Outer validation | 3-fold LOMO: target = 1.0, 1.5, or 3.0 kW |
| Target fault labels used before evaluation | 0 |
| Unique current records | 45: 3 healthy + 42 fault |
| Record duration | first 120 s of every TDMS |
| Window / macroblock | 0.2 s non-overlap / 3 s (15 windows) |
| Target adaptation | blocks 0--3: 4 blocks = 12 s |
| Guard blocks | block 4 and block 25 |
| Target calibration | blocks 5--24: 20 blocks = 60 s |
| Later-time healthy test | blocks 26--39: 14 blocks = 42 s per motor |
| Primary representation | scale-free three-phase current features |
| Log-covariance ridge | 0.01, selected only by nested source-motor validation |
| Block score / alpha | maximum / 0.05 |
| Primary uncertainty statement | empirical block risk; no arbitrary-dependence guarantee |

## Section-by-section writing plan

### 1. Introduction

- Explain why new motor rating changes current scale and anomaly-score distributions.
- Motivate zero-target-fault-label deployment and why source-domain thresholds are
  operationally unsafe; the logistic pilot produced 100% target healthy FAR on the
  1.0 and 1.5 kW folds under its source threshold.
- State the five contributions above without claiming universal coverage or severity
  estimation.

### 2. Related work

- PMSM inter-turn and inter-coil fault diagnosis with current signatures.
- Cross-machine/cross-domain diagnosis and the distinction between window holdout and
  entity holdout.
- Healthy-only anomaly detection and covariance-domain methods.
- Riemannian/Log-Euclidean aggregation of SPD covariance matrices.
- Conformal fault diagnosis and conformal inference for dependent time series; explicitly
  distinguish this work from generic open-set conformal diagnosis.

### 3. Problem formulation

- Define source motors \(\mathcal M_s\), unseen target motor \(m_t\), healthy-only target
  adaptation/calibration sets, and target-fault evaluation set.
- Define window score, block maximum, conformal p-value, block alarm, empirical FAR and
  detection rate.
- State the restricted deployment target: cross-capacity transfer within the observed
  fixed-condition family.

### 4. Dataset audit and leakage-resistant protocol

- Inventory 1 healthy + 14 fault records per motor and two fault families with seven
  severities each.
- Report that the two healthy aliases per motor are duplicates by size/CRC (plus SHA-256
  for the extracted 1.0 kW pair) and are used once.
- Report 121--149 s raw duration exceptions and uniform first-120-s truncation.
- Show the 0.2-s window, 3-s macroblock and contiguous target-health partition. Explain
  that the 3-s choice is tied to the observed healthy nuisance cycle, not target faults.

### 5. Proposed method

1. Extract transparent scale-free current features and remove absolute-amplitude columns.
2. Robustly center/scale each motor with only allowed healthy reference blocks.
3. Estimate one regularized healthy covariance per motor.
4. Compute the equal-motor Log-Euclidean covariance mean; use a zero-centered
   Mahalanobis score for the target.
5. Aggregate 15 windows by maximum and compute p-values from 20 target healthy
   calibration blocks.
6. Describe source-only pseudo-target ridge selection: grid
   \(10^{-4},10^{-3},10^{-2},10^{-1}\), objective detection minus twice FAR, selected
   \(10^{-2}\) in all outer folds.

### 6. Experimental protocol and comparators

- Primary methods: target Ledoit--Wolf, ridge target sample covariance, source-only
  covariance, arithmetic entity-balanced covariance, and Proposed Log-Euclidean
  entity-balanced covariance.
- Strict healthy-only baselines under the identical representation, split and block
  calibration: target-only and motor-balanced source+target OCSVM, Isolation Forest and
  MinCovDet. OCSVM uses fixed RBF/`gamma=scale`/`nu=0.05`; Isolation Forest uses 500
  trees; MinCovDet removes only health-fit rank redundancies. No target fault selects a
  hyperparameter.
- Use seed 20260820 for primary stochastic results and report five predeclared seeds;
  classifiers remain domain-shift motivation rather than the only strong baselines.
- Primary metrics: pooled and per-motor healthy FAR, 95% Wilson interval, block
  detection, worst-motor detection and block AUROC.
- Paired comparison: 42 fault records, motor-stratified record bootstrap, 10,000
  replicates, seed 42; do not treat 1,680 correlated fault blocks as independent draws.
- Completed: 3/6/12/24-s target-health adaptation sensitivity and feasible 1/2/3-s
  block-length sensitivity with a disjoint 60-s calibration segment, plus strict
  one-class baselines. Pending: matching time-series/domain-adaptation baselines and
  frozen-method external validation.

### 7. Results

#### 7.1 Primary empirical result

- Proposed: 0/42 later-time healthy false alarms; Wilson upper 8.38%; 1,608/1,680 fault
  blocks detected (95.71%); worst motor 90.00%; fold-mean AUROC 0.9993.
- Per motor: 1.0 kW = 100.00%, 1.5 kW = 90.00%, 3.0 kW = 97.14% detection, all with
  0/14 later-time healthy false alarms.

#### 7.2 Comparator interpretation

- Proposed minus source-only covariance: +6.61 pp, 95% bootstrap CI [1.79, 12.32].
- Proposed minus target Ledoit--Wolf: +5.42 pp, [0.59, 11.19].
- Proposed minus target sample covariance: +1.85 pp, [-2.14, 6.01].
- Proposed minus arithmetic entity balance: +0.24 pp, [-1.37, 2.32].
- State plainly that the latter two intervals cross zero; do not claim universal or
  statistically resolved superiority.
- Motor-balanced source+target Isolation Forest: 0/42 FAR and 96.07% record-macro
  detection versus Proposed 0/42 and 95.71%; Proposed-minus-baseline = -0.36 pp,
  paired-record CI [-3.93, 3.45]. Treat this as a statistical tie.
- Target-only Isolation Forest: 97.56% detection, but 1/42 healthy false alarms and a
  12.32% descriptive Wilson upper bound, so it fails the 12% H1 gate despite the higher
  detection point estimate.
- Proposed is favored over target OCSVM (+6.01 pp, [1.07, 11.90]), target MinCovDet
  (+5.89 pp, [0.95, 11.67]) and motor-balanced MinCovDet (+3.39 pp, [0.30, 6.85]), but
  not resolved against motor-balanced OCSVM (+4.46 pp, [-0.42, 10.18]).
- Five-seed ranges: balanced Isolation Forest detection 96.01--96.85% with FAR 0--2/42;
  target Isolation Forest detection 96.49--97.56% with FAR 0--1/42. Do not hide seed
  variability behind the primary run.

#### 7.3 Falsified or uninformative hypotheses

- Lowest-two-severity detection is 100% for every covariance method, so the planned
  +10 pp improvement hypothesis is untestable because of a ceiling effect.
- Severity-score Spearman is negative in three of six motor-family combinations
  (1.0 kW inter-coil -0.500/inter-turn -0.607; 1.5 kW inter-coil -0.429). Remove
  severity estimation from the contribution and retain the plot as a failure analysis.

#### 7.4 Target-health adaptation budget

- With fixed calibration/test periods, 3/6/12/24 s adaptation yielded 94.64%, 96.90%,
  96.25% and 94.94% mean detection, respectively, with 0/30 healthy false alarms for
  every budget.
- The response is nonmonotonic; the 6-s pilot maximum cannot be selected using target
  faults. Retain 12 s as the pre-existing primary setting.
- At alpha = 0.05, 3--24 s is insufficient if interpreted as conformal calibration;
  at least 19 three-second blocks (57 s) are required for a finite threshold.

#### 7.5 Block-length and aggregation sensitivity

- The frozen 3-s/max design exactly reproduces the primary result. The 1-s and 2-s
  alternatives reduce mean detection to 93.61% and 93.73%.
- A 3-s 90th-percentile score reaches 97.32% detection but introduces 1/42 healthy
  false alarms and a 12.32% descriptive Wilson upper bound, missing the preregistered
  12% gate; it cannot replace the primary design after target-fault inspection.
- Five- and six-second blocks provide fewer than 19 calibration units in 60 s and are
  skipped at alpha = 0.05.

### 8. Discussion and limitations

- One unique healthy record per motor; time blocks are not independent experimental
  repeats.
- Calibration and later-time test are ordered parts of the same record. Ordinary
  exchangeable split-conformal finite-sample coverage is not claimed.
- Same manufacturer/topology and fixed condition limit external validity.
- The target faults have been inspected during pilot development; external frozen-method
  validation is required for confirmatory wording.
- Nonmonotonic severity response means reliable detection does not imply diagnosis,
  severity estimation, prognosis or RUL prediction.
- Explain why equal-motor Log-Euclidean geometry remains scientifically motivated even
  though the arithmetic entity-balanced CI overlaps it; external data must decide whether
  the added geometry improves robustness.
- Treat motor-balanced Isolation Forest as a co-leading empirical result. The current
  data support interpretability/determinism and calibrated operating-point tradeoffs for
  Proposed, not blanket superiority or a comprehensive SOTA claim.

### 9. Conclusion

Conclude narrowly: the pilot supports healthy-only block-calibrated cross-capacity
stator-fault detection in this three-motor dataset and motivates external validation. Do
not conclude that alpha = 0.05 is universally guaranteed or that SCI acceptance is assured.

## Required figures

1. Data inventory plus three-fold LOMO and the 40-block target-health timeline.
2. Full method flow: scale-free features, robust healthy alignment, per-motor
   covariances, Log-Euclidean mean, Mahalanobis windows and block p-values.
3. Source-threshold domain-shift example across the three target motors.
4. FAR by method with Wilson intervals and the 12% empirical gate.
5. Per-motor detection by covariance and one-class method.
6. Record-level paired detection differences, including Isolation Forest, with bootstrap
   intervals.
7. Detection/score versus severity, explicitly labeled as nonmonotonic failure analysis.
8. Representative 1.5 kW false-negative blocks and score trajectories.

## Required tables

1. Motor/record/fault inventory and data-audit corrections.
2. Frozen split, adaptation budget, guard blocks and calibration count.
3. All covariance and one-class methods under the identical scale-free LOMO protocol.
4. Per-motor FAR, detection, AUROC, random-seed sensitivity and low-severity ceiling.
5. Record-level paired bootstrap comparisons, including the balanced Isolation Forest tie.
6. Ridge, feature, calibration-budget and block-length sensitivity.
7. Claim audit: supported, unsupported and external-validation-dependent statements.

## Claims prohibited unless new evidence changes them

- distribution-free coverage under arbitrary temporal dependence;
- independent-repeat validation from duplicate healthy aliases;
- untouched confirmatory target-fault evaluation on the current KAIST split;
- significant superiority over target sample or arithmetic entity-balanced covariance;
- significant superiority over motor-balanced Isolation Forest, all strong one-class
  baselines, or a comprehensive SOTA claim;
- low-severity improvement or monotonic severity estimation;
- arbitrary cross-topology, cross-manufacturer or variable-condition generalization;
- online/embedded real-time capability without latency measurement;
- fault prognosis, remaining useful life prediction or a safety guarantee;
- guaranteed SCI submission outcome or acceptance.
