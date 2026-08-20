# Paper 1 Literature Gap and Claim Audit (2026-08-20)

## Audit scope and evidence rule

This is a targeted primary-literature audit for Paper 1, not a PRISMA systematic
review and not evidence that no unlocated paper exists. Searches covered DOI/Crossref
metadata, publisher pages, and the original article/full text where accessible, using
combinations of `cross-machine`, `cross-dataset`, `domain generalization`, `negative
transfer`, `variable speed`, `operating-condition shift`, `data leakage`, `recording-level
split`, `one-class`, `healthy-only`, `conformal anomaly detection`, and `false alarm` with
rotating machinery, bearing, motor, and PMSM. Empirical claims below are attributed only
to original studies or original benchmark components. Review/tutorial papers are used
only as maps of a field.

The audit distinguishes three units that are often conflated:

- a **window** is a derived segment and is not an independent physical repetition;
- a **record** is one continuous acquisition and its windows/blocks remain dependent;
- an **entity** is a physical bearing, motor, machine, or fleet unit and is the relevant
  holdout unit for a cross-machine claim.

## Conclusion first

The literature already contains cross-machine supervised domain generalization,
negative-transfer mitigation, one-class machinery detection, conformal industrial-fleet
alarms, and recording-level evaluation. Therefore Paper 1 should not be sold as the first
use of any one of those ingredients or as a new one-class algorithm.

The defensible gap is their **evaluation combination**:

> A leakage-resistant, fault-blind cross-dataset stress test of healthy-only
> cross-machine transfer, with the same one-class algorithm evaluated as source-assisted
> and target-only controls, non-overlapping target-health roles separated by record where
> available, and a frozen external fault reveal reported at record/block level.

The present results make this most credible as a transfer-failure / benchmark paper:
the frozen external experiment documents a conditional ranking reversal and speed-related
score drift, while a target-only MinCovDet control outperforms the proposed transferred
model. That is useful evidence about when transfer should not be trusted; it is not a
state-of-the-art-method result.

## 1. Cross-dataset and cross-machine generalization

| Primary work | What the original study supports | What it does not establish for Paper 1 |
|---|---|---|
| [Li et al., 2020](https://doi.org/10.1016/j.neucom.2020.05.014) | Early original formulation of domain generalization for rotating-machinery fault diagnosis. Domain augmentation, adversarial training, and metric learning are evaluated on two rotating-machinery datasets for new working scenarios without using target test data during training. | Domain-generalized fault classification is not equivalent to healthy-only alarm-risk control on an unseen motor. |
| [Li et al., 2023, CCN](https://doi.org/10.1109/TII.2022.3174711) | Collaborative multimachine bearing diagnosis across six machines, 43 individual bearings, and 20 operating conditions. This is strong primary evidence that cross-machine DG predates Paper 1. | It transfers supervised fault-class knowledge and evaluates diagnosis accuracy; it does not provide a fault-blind target-health calibration or a same-algorithm target-only alarm comparator. |
| [Zhao et al., 2024](https://doi.org/10.1016/j.ress.2024.109964) | An original benchmark component evaluates DG methods on eight public and two self-collected datasets under a unified framework. It directly demonstrates that cross-dataset benchmarking is an established research design. | Its review component is secondary evidence, and the benchmark's supervised classification endpoints do not validate Paper 1's one-class threshold or false-alarm claim. |
| [Liu et al., 2025](https://doi.org/10.1016/j.measurement.2025.116989) | A frequency-guided latent-diffusion DG method is evaluated in cross-machine fault diagnosis; the paper explicitly motivates the method by the risk that source-focused regularization can cause negative transfer. | A gain in target fault-class accuracy is not a calibrated deployment alarm, and the study does not freeze an external fault reveal against a target-only one-class reference. |

**Paper 1 difference.** The source models use fault-free source data, target faults remain
hidden during fitting/selection/calibration, and transfer is judged against the same
detector trained from target-only health. This isolates the empirical cost or benefit of
adding source machines more directly than comparisons among different DG classifiers.
However, the KAIST evidence is limited to three same-manufacturer motors and the external
stress test contains one physical dual-three-phase PMSM. It is conditional cross-entity
evidence, not universal cross-machine generalization.

## 2. Negative transfer and the required comparator

| Primary work | What the original study supports | What it does not establish for Paper 1 |
|---|---|---|
| [Wang et al., 2019](https://doi.org/10.1109/CVPR.2019.01155) | Formally treats negative transfer as target performance harmed by transfer and makes the non-transfer reference an explicit part of the comparison. It evaluates six transfer methods on four benchmarks. | It is a general computer-vision study, not rotating machinery and not an alarm-calibration protocol. |
| [Kumar MP et al., 2024](https://doi.org/10.1109/TIM.2024.3476610) | Shows that negative-transfer mitigation already exists in rotating-machinery diagnosis: source-free UDA uses target pseudo-label refinement and weight-aware regularization and reports class-accuracy gains in matched and different operating environments. | Source-free UDA consumes an unlabeled target stream and optimizes class prediction. It is not the same question as whether adding healthy source machines worsens a frozen target alarm relative to target-only health. |
| [Liu et al., 2025](https://doi.org/10.1016/j.measurement.2025.116989) | Provides current, machinery-specific primary evidence that cross-machine DG authors recognize negative transfer caused by source-domain emphasis. | It proposes mitigation; it does not quantify a paired source-assisted versus target-only one-class alarm reversal under an external one-time reveal. |

**Paper 1 difference.** For OCSVM, Isolation Forest, MinCovDet, and covariance-distance
variants that can be paired, the scientifically meaningful comparison holds the algorithm,
target-health calibration load, windows, and scoring rule fixed and changes only whether
source-machine health enters training. The external ranking reversal is therefore evidence
of **conditional negative transfer on this motor and protocol**. One external motor cannot
support a population-level claim that transfer is generally harmful.

## 3. Operating-condition and speed confounding

| Primary work | What the original study supports | What it does not establish for Paper 1 |
|---|---|---|
| [Zhou et al., 2023](https://doi.org/10.1016/j.ress.2023.109528) | In bearing monitoring under time-varying operating conditions, operating information is entangled with health information; the proposed hybrid response model is designed to remove operating-condition interference and is tested on accelerated fatigue data under variable speed. | It does not identify which feature causes Paper 1's alarms or validate PMSM transfer. |
| [Urresty et al., 2013](https://doi.org/10.1109/TPEL.2012.2198077) | PMSM-specific primary evidence that interturn-fault indicators must be tracked under nonstationary speed and different loads; the study uses order tracking to follow current and zero-sequence-voltage harmonics over a wide speed range. | It is a physics/signal-processing diagnosis study, not a learned cross-machine one-class detector. |
| [Li et al., 2024](https://doi.org/10.1016/j.engappai.2024.107938) | A PMSM interturn-short-circuit study explicitly addresses sparse real data and rapidly varying speed/high-temperature oil-drilling conditions through a physical-data dual model and transfer learning. | Its fault-classification result does not establish false-alarm control or distinguish speed response from anomaly response in Paper 1. |

**Paper 1 difference.** The frozen external health and fault records are speed sweeps, and
post-reveal diagnostics show score/alarm probability rising with later speed blocks. This
makes operating condition a concrete competing explanation for detection. The correct
claim is an **association between block/speed and score**, not that speed has been proven
to cause every alarm. A causal claim requires matched-speed healthy/fault repetitions or
an intervention that varies speed independently of fault state.

## 4. Random-window leakage and pseudoreplication

| Primary work | What the original study supports | What it does not establish for Paper 1 |
|---|---|---|
| [Wheat et al., 2024](https://doi.org/10.1109/ACCESS.2024.3497716) | Six bearing-diagnosis pipelines on two datasets were compared under run-to-run, day-to-day, and part-to-part splits. The paper reports an accuracy drop exceeding 40% depending on the split. Among 55 audited Paderborn studies, ten were judged likely affected and only six properly addressed the issue. The authors recommend holding out physical parts and reporting splits explicitly. | It demonstrates a general machinery-evaluation risk, not the exact inflation magnitude for the KAIST PMSM data or Paper 1's feature set. |
| [Hurlbert, 1984](https://doi.org/10.2307/1942661) | Provides the classic experimental-design definition of pseudoreplication: inferential units are treated as replicated or independent when treatments/entities were not independently replicated. | It is not a machinery study and supplies no motor-specific effect size. |
| [Roberts et al., 2017](https://doi.org/10.1111/ecog.02881) | Demonstrates why random cross-validation can seriously underestimate error when observations have temporal, spatial, or hierarchical dependence, and motivates blocking to match the intended prediction task. | Blocking reduces leakage but does not magically turn blocks from one record into independent physical repetitions. |
| [González-García et al., 2026](https://doi.org/10.3390/electronics15143035) | Uses recording-level cross-validation on CWRU and MFPT. Split-conformal coverage succeeds on CWRU but fails on MFPT under recording-level class-proportion mismatch; Mondrian calibration improves but does not fully restore nominal coverage. | It is supervised bearing classification under controlled fixed-speed data. It does not validate healthy-only PMSM alarms, and its one normal CWRU recording is temporally divided rather than independently replicated. |

**Paper 1 difference.** Motor/entity holdout and record-separated target-health roles are
stronger than a random window split. Three-second blocks are the inferential reporting
unit for temporal risk and prevent a large window count from being presented as a large
physical sample count. They remain dependent observations from a continuous acquisition.
The paper must report record- or entity-level sample counts alongside window/block counts
and must not call the latter independent repetitions.

## 5. Healthy-only / one-class detection and calibrated alarms

### Algorithm provenance

The one-class baselines are established methods, not methodological novelties:

| Method | Original source | What it establishes |
|---|---|---|
| One-class SVM | [Schölkopf et al., 2001](https://doi.org/10.1162/089976601750264965) | Learning the support of a distribution from one class. |
| Support vector data description | [Tax and Duin, 2004](https://doi.org/10.1023/B:MACH.0000008084.60811.49) | A minimum-enclosing description for target-class data. |
| Isolation Forest | [Liu et al., 2008](https://doi.org/10.1109/ICDM.2008.17) | Isolation-based unsupervised anomaly scoring. |
| Minimum covariance determinant | [Rousseeuw and Van Driessen, 1999](https://doi.org/10.1080/00401706.1999.10485670) | Robust location/covariance estimation used by the MinCovDet baseline. |

### Machinery and industrial alarm studies

| Primary work | What the original study supports | What it does not establish for Paper 1 |
|---|---|---|
| [Yoon and Yu, 2024](https://doi.org/10.3390/app14010221) | Deep SVDD and classical one-class methods are fitted from normal machinery signals; 80% of normal samples are randomly assigned to training and the remaining normal samples plus faults to testing, with AUROC reported over repeated splits. | The experimental settings select several hyperparameters by highest AUROC, so fault outcomes affect selection even though model fitting is one-class. ROC threshold sweeping is not a frozen, fault-blind alpha-level operating alarm, and sample-wise normal splits need not separate records/entities. |
| [Farouq et al., 2021](https://doi.org/10.1016/j.neucom.2021.08.016) | With no labels, a Mondrian conformal subfleet uses similar fleet units as proxies for a target unit's normal behavior and extracts anomalous sequences in real district-heating data. | It is a heterogeneous-fleet precedent, but not rotating machinery/PMSM and not a paired target-only versus source-assisted detector comparison. |
| [Farouq et al., 2022](https://doi.org/10.1016/j.eswa.2022.116864) | Unit-, subfleet-, and combined conformal anomaly ensembles explicitly address false alarms; the combined model reduces false alarms at the cost of detection delay on real district-heating substations. | Its conformal validity statement assumes IID/exchangeable observations. It does not justify exchangeability of Paper 1's time blocks. |
| [Diallo et al., 2025](https://doi.org/10.1016/j.jprocont.2025.103495) | On the Tennessee Eastman Process, conformal and classical PCA/autoencoder thresholds are compared directly. With limited training data, marginal conformal and classical methods can exceed target false-alarm risk; conditional methods become more conservative when sufficient data are available. | It is process monitoring, not a cross-motor study, and does not transfer healthy reference data between entities. |
| [Heddoub et al., 2026](https://doi.org/10.1016/j.jprocont.2026.103701) | Class-conditional conformal prediction with discriminant-analysis backbones is evaluated for reliable open-set process-fault diagnosis on DAMADICS and Tennessee Eastman benchmarks. | It requires supervised known-fault classes and is not healthy-only PMSM detection. |
| [Chernozhukov et al., 2018](https://proceedings.mlr.press/v75/chernozhukov18a.html) | Develops exact/robust conformal inference for dependent data through structured permutations, providing a primary theoretical reason to model dependence explicitly. | It does not certify that arbitrary three-second motor blocks satisfy its assumptions. |
| [Barber and Pananjady, 2026](https://proceedings.mlr.press/v313/barber26a.html) | Analyzes split conformal for stationary beta-mixing time series and explains conditions under which temporal dependence can still permit coverage. | Paper 1's finite speed sweep is not shown to be stationary or beta-mixing, so this theory cannot be cited as an automatic guarantee. |

**Paper 1 difference.** The relevant contribution is not fitting a one-class model. It is
keeping all target fault labels out of representation/model selection and threshold
calibration; assigning target adaptation, calibration, and healthy testing to separate
records/loads where possible; comparing transferred and target-only versions at the same
alarm level; and revealing the external faults once after freezing the protocol. This is
an auditable deployment simulation. Because calibration blocks are temporally dependent
and the number of unique healthy records is small, the threshold should be described as
an empirical rank/block calibration at nominal alpha = .05, not as a distribution-free
guarantee of 5% physical-motor false alarms.

## Paper 1 gap stated conservatively

The targeted audit did **not locate** an original rotating-machine/PMSM study that combines
all of the following in one experiment:

1. physical motor/entity holdout and record-aware inference;
2. healthy-only fitting with no target fault label used for selection or calibration;
3. non-overlapping target-health roles for adaptation, calibration, and false-alarm
   testing, using separate records/loads where available;
4. same-algorithm source-assisted versus target-only comparisons;
5. a pre-specified external fault reveal with thresholds and windows frozen beforehand;
6. explicit reporting of negative transfer and operating-condition confounding when the
   transferred method fails.

This is a targeted-search absence statement, not proof of global priority. Manuscript-safe
wording is “we did not identify a prior study combining ...” rather than “this is the first.”

## Claims that current literature and data do not support

| Unsupported or under-supported claim | Why it is not supportable now | Defensible replacement |
|---|---|---|
| “First cross-machine fault diagnosis / first negative-transfer study” | Li 2023, Kumar MP 2024, Zhao 2024, and Liu 2025 are direct counterexamples. | “A fault-blind, target-only-controlled stress test of healthy-only cross-machine transfer.” |
| “First conformal industrial fault detector” | Farouq 2021/2022, Diallo 2025, Heddoub 2026, and González-García 2026 predate the paper. | Emphasize record-separated healthy calibration and frozen external reveal, not conformal novelty. |
| “Universal cross-machine generalization” | Three same-manufacturer KAIST motors plus one external motor do not represent manufacturers, topologies, or populations. | “Conditional evidence in the evaluated cross-capacity and external dual-three-phase settings.” |
| “Guaranteed alpha = .05 motor-level FAR” | Calibration units come from dependent blocks and few unique healthy records; exchangeability/stationarity is unverified. | “Nominal alpha = .05 rank calibration with empirical block- and record-level FAR reported.” |
| “Negative transfer is a population phenomenon” | The strongest reversal is conditional on one external physical motor. | “Observed conditional negative transfer/ranking reversal on the frozen external stress test.” |
| “Speed causes the alarms” | Score and block/speed co-vary in a sweep, but fault, time, temperature, and speed are not independently manipulated. | “Alarm scores are speed/block associated; speed is a plausible confounder.” |
| “Three-second blocks are independent samples” | Blocks share a continuous record, machine, sensors, ramp trajectory, and acquisition session. | Treat records/entities as physical units and blocks as dependent temporal analysis units. |
| “Random-window leakage inflated this KAIST result by a known amount” | Wheat 2024 establishes the general risk, but Paper 1's own random-window contrast is not a replicated causal experiment. | “The protocol avoids the documented leakage mechanism; no dataset-specific inflation magnitude is claimed.” |
| “Low-severity or severity-monotonic detection is established” | The frozen external early/low-severity detection is weak and the original exploratory severity hypothesis failed. | Report family/severity-resolved failures without a monotonicity claim. |
| “The proposed detector is the best calibrated one-class method” | Target-only MinCovDet is stronger on the current frozen external result. | Position MinCovDet as a critical target-only control and the ranking reversal as the finding. |
| “Natural degradation or field deployment has been validated” | The datasets use seeded/emulated faults and controlled test benches. | “Laboratory stress-test evidence; natural degradation and field validation remain future work.” |

## Secondary-source boundary and remaining search uncertainty

- [Xiao et al., 2025](https://doi.org/10.1016/j.aei.2024.103063) is retained in the
  bibliography as a field map, but no empirical claim above relies on its survey summary.
- [Angelopoulos and Bates, 2023](https://doi.org/10.1561/2200000101) is a conformal
  tutorial, not evidence that Paper 1's time blocks meet a coverage theorem.
- Zhao et al. 2024 contains both a review and an original ten-dataset benchmark; only the
  benchmark component is treated as primary empirical evidence here.
- This targeted audit is not exhaustive across every language, preprint server, thesis,
  or proprietary dataset. A formal “first” claim would require a registered systematic
  search with databases, dates, inclusion rules, dual screening, and a complete exclusion
  log. No such priority claim should be made from this document.
