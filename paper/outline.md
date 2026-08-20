# Paper 1 Outline (Evidence-Locked Living Draft)

## Fixed working title

**When Healthy-Only Transfer Fails in PMSM Stator-Fault Detection:
A Leakage-Resistant Cross-Dataset Evaluation**

中文工作题目：**健康样本迁移何时失效：复合转速、负载与拓扑偏移下 PMSM 定子故障
检测器的防泄漏跨数据集评估**。

## Manuscript status and claim boundary

论文定位已从“Log-Euclidean 新方法优越”转为“防泄漏跨数据集评估、排名反转与负迁移
失败研究”。这是由冻结外部验证决定的，不是为了迎合结果而修改指标。

- KAIST 三电机结果是 exploratory：方法开发期间查看过其全部目标故障记录。
- 双三相 PMSM 外部故障是 frozen reveal：协议、代码、环境、24 个校准分数、阈值、
  11 个比较器和失败门槛均在打开任何外部故障值之前形成哈希提交。
- 外部 48 条故障记录来自一台物理电机的 6 turns × 8 loads 条件网格，不是 48 台电机。
- Wilson 区间和 record bootstrap 只描述已记录条件，不能外推成机群安全保证。
- 预注册 Log-Euclidean detector 外部失败后仍保留为 primary；target MinCovDet 只能称
  observed comparator leader，不能事后更换主方法。
- 任何揭盲后开发的速度条件化模型都属于 Paper 2 探索结果，必须在新未见数据确认。

## One-sentence contribution

We provide a frozen-reveal, leakage-resistant cross-dataset evaluation showing that a
healthy-only PMSM detector with near-ceiling same-family performance can undergo a
large ranking reversal and negative transfer when topology, sampling rate, speed, and
load change together.

## Evidence headline

| Evidence | Frozen Log-Euclidean | Best preimplemented external comparator |
|---|---:|---:|
| KAIST healthy alarms | 0/42 | balanced IF: 0/42 |
| KAIST detection | 95.71% | balanced IF: 96.07% |
| External healthy alarms | 1/32; H1 fail | target MinCovDet: 0/32; H1 pass |
| External detection | 25.00% [21.09, 29.43]% | target MinCovDet: 70.05% [65.36, 75.26]% |
| External AUROC | 0.6354 | target MinCovDet: 0.9268 |

The proposed-minus-target-MinCovDet paired external difference is -45.05 percentage
points (95% turn-stratified record-bootstrap interval [-49.48, -40.63]).

## Contribution list

1. **Audit-first, leakage-resistant protocol.** Physical motor/file holdout,
   chronological health partitions, duplicate removal, fixed record duration, and no
   random adjacent-window split.
2. **Frozen independent-laboratory reveal.** Official filenames, byte counts, and MD5s
   were committed before download; all 48 planned fault files were processed once with
   no post-hoc exclusion.
3. **Cross-dataset ranking reversal.** Same-family high performance did not survive a
   compound topology, sampling-rate, speed, and load shift.
4. **Negative-transfer diagnosis.** Target-only MinCovDet exceeded source+target
   MinCovDet by 39.84 points [35.42, 44.27], while target adaptation still improved over
   pure source covariance.
5. **Alarm-drift audit.** The frozen detector alarmed on 0/48 fault records in blocks
   0--2 and 48/48 in block 7; its only healthy alarm was also in block 7.
6. **Claim discipline and reproducibility.** Record-level paired statistics, calibration
   feasibility, failure logs, selected derived results, automated tests, and figures are
   retained without post-reveal primary replacement.

## Dataset and protocol summary

### Exploratory KAIST dataset

| Item | Setting |
|---|---|
| Motors | same-manufacturer 1.0, 1.5, 3.0 kW PMSMs |
| Conditions | fixed 3000 rpm and one load |
| Unique current records | 3 healthy + 42 fault |
| Sampling / duration | 100 kHz / first 120 s |
| Outer split | three-fold leave-one-motor-out |
| Window / block | 0.2 s / 3 s maximum |
| Target health | 12 s adaptation, guard, 60 s calibration, guard, 42 s test |
| Alarm level | empirical block p-value at alpha = 0.05; 20 calibration blocks |

### Frozen external dataset

| Item | Setting |
|---|---|
| Motor | one dual-three-phase PMSM, independent laboratory |
| Healthy records | eight loads: 0--35 N m in 5 N m increments |
| Fault records | 6 turn counts × 8 loads = 48 |
| Sampling / trajectory | 10 kHz acceleration sweeps |
| Frozen interval | [12,36) s in every file |
| Adaptation | 0 N m, first four local blocks = 12 s |
| Calibration | 10/20/30 N m, 24 system blocks |
| Held-out health | 5/15/25/35 N m, 32 system blocks |
| System score | separate subsystem scores, then maximum |
| Reveal status | complete; all planned files passed integrity and parser checks |

## Section-by-section writing plan

### 1. Introduction

- Distinguish same-dataset discrimination from deployable target alarms.
- Explain why target faults are unavailable but target healthy commissioning is realistic.
- Show how motor, file, time, and operating-point leakage inflate reported performance.
- State the six evaluation contributions; do not lead with a new matrix mean.

### 2. Related work

- PMSM interturn/intercoil signatures and speed/load dependence.
- Cross-machine domain adaptation and negative transfer.
- Healthy-only one-class detection and robust covariance estimators.
- SPD covariance transfer and target-health calibration.
- Conformal inference under dependence; distinguish empirical block thresholds from
  unrestricted finite-sample guarantees.

### 3. Dataset audit and leakage-resistant protocol

- KAIST duplicate healthy aliases, unequal raw durations, first-120-s truncation.
- Three-fold motor holdout and chronological adaptation/calibration/test split.
- External healthy-only audit, common interval, subsystem combination, record-disjoint
  health loads, official fault manifest, and reveal timestamps.
- State experimental unit correctly: record for fault bootstrap, not window or block.

### 4. Evaluated detectors and calibration

- Five covariance variants and six one-class variants.
- Target-only versus motor-balanced source+target construction.
- Frozen Log-Euclidean detector definition and source-only ridge choice.
- 3 s block maximum and empirical upper-tail calibration.
- Keep detector name “frozen/prespecified Log-Euclidean,” not “SOTA method.”

### 5. Experiments and uncertainty

- Primary metrics: raw healthy alarm count, descriptive Wilson upper bound, maximum
  load-specific FAR, block detection, early-trajectory detection, AUROC, and record-any
  with an explicit late-alarm warning.
- Paired bootstrap resamples complete fault records within turn-count strata externally
  and within motor internally.
- Holm-adjust the family of candidate-versus-primary external comparisons.
- Five predefined seeds for stochastic IF/MinCovDet sensitivity.
- Adaptation-budget and block-length sensitivity remain secondary KAIST analyses.

### 6. Results

#### 6.1 Exploratory same-family result

- Frozen Log-Euclidean: 0/42 health alarms, 95.71% detection, worst motor 90.00%,
  AUROC 0.9993.
- Balanced IF: 0/42, 96.07%; paired difference unresolved.
- No Log-Euclidean superiority over target sample covariance or arithmetic entity mean.

#### 6.2 Frozen external health gate

- Log-Euclidean 1/32, point FAR 3.125%, Wilson upper 15.74%, max-load 12.5%.
- H1 fails because evidence does not meet the 12% upper-bound criterion; do not say the
  true FAR is proven above 5%.
- Target MinCovDet alone passes, but remains a comparator.

#### 6.3 Frozen external faults and ranking reversal

- Log-Euclidean detection 25.00%, AUROC 0.6354.
- Target MinCovDet detection 70.05%, AUROC 0.9268.
- Report all eleven methods, paired intervals, multiple-comparison adjustment, and seed
  sensitivity without selecting a favorable seed.

#### 6.4 Operating-point confounding

- Alarm rate by ordered block, approximate speed, load, and fixed turn--phase condition;
  the dataset does not separately identify turn-count and phase effects.
- First-four/first-seven/full-horizon detection and first-alarm speed.
- Per-block AUROC to distinguish residual fault information from threshold drift.
- State that pooled AUROC compares eight fault loads with four held-out health loads and
  is descriptive rather than load matched.
- Avoid headline AUPRC because prevalence is 384/416 = 92.3%.

#### 6.5 Negative transfer

- Target-only minus source+target comparison within the same algorithm.
- Target adaptation helps over pure source covariance, but source geometry harms the
  target-specific robust estimator under compound shift.

#### 6.6 Secondary sensitivity and failed hypotheses

- Calibration-budget feasibility, block length, seed sensitivity.
- Antialiasing KAIST to 10 kHz did not recover external transfer
  (25.00% to 24.74% detection; 1/32 FAR unchanged).
- Frozen-geometry contribution audit: speed proxy high contribution/near-chance matched
  AUROC versus third harmonic high matched AUROC/very low contribution.
- KAIST low-severity ceiling and failed severity monotonicity.

### 7. Discussion

- Explain why record-any alarm and same-dataset AUROC can be operationally misleading.
- Attribute failure to compound shift without claiming a causal decomposition.
- Separate score ranking from fixed-threshold transport.
- Outline Paper 2: healthy-only speed/load-conditioned residuals, harmonized sampling,
  target MinCovDet primary comparator, early-detection endpoint, and new frozen dataset.

### 8. Conclusion

Lead with the ranking reversal and protocol lesson. Do not end by claiming that the
failed detector merely “needs more validation.”

## Required figures

1. Leakage-resistant motor/file/time protocol.
2. KAIST exploratory performance and paired comparisons.
3. External eleven-method detection plus health H1 decisions.
4. Frozen-detector score and alarm drift across ordered acceleration blocks.
5. Fixed turn--phase condition × load detection heatmap.
6. Early-horizon/per-block diagnostic figure if it remains readable.

## Required tables

1. Dataset audit and physical experimental units.
2. Detector fit data, calibration data, and forbidden labels.
3. Exploratory KAIST results.
4. Frozen external results for all eleven methods.
5. Paired differences with Holm-adjusted inference.
6. Seed and operating-horizon sensitivity.

## Prohibited claims

- “Guaranteed 5% FAR,” “distribution-free under arbitrary dependence,” or safety
  certification.
- Universal cross-machine, cross-topology, or cross-condition generalization.
- Log-Euclidean, deep learning, or source augmentation is uniformly superior.
- Target MinCovDet was the preregistered primary method.
- 48 external records represent 48 independent motors.
- External turn-count and fault-phase effects are separately identified.
- Pooled external AUROC is a load-matched population estimand.
- 100% record-any alarm means reliable early detection.
- High AUPRC is strong evidence under 92.3% fault-block prevalence.
- Severity estimation, prognosis, RUL, or acceptance by an SCI journal.
