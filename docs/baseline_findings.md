# Paper 1 基线发现与证据边界（Exploratory Pilot）

更新日期：2026-08-20

## 1. 冻结题目与当前状态

**Healthy-Only Cross-Capacity PMSM Stator-Fault Detection via Motor-Balanced
Covariance Transfer and Block-Conformal Calibration**

中文工作题目：**基于电机实体平衡协方差迁移与健康样本块共形校准的跨容量 PMSM
定子故障检测**。

本文的目标不是证明一个对任意电机都成立的安全保证，而是回答一个可检验的问题：在
目标电机故障标签为零（zero target-fault labels）的条件下，能否使用两台源电机和少量
目标健康电流，建立对目标电机的块级异常分数并经验校准报警阈值。

当前结果是 **exploratory pilot**，足以支持继续写作和补实验，但不能视为独立确认性
验证，也不能保证 SCI 录用。方法开发期间已经查看同一数据集中的全部目标故障记录；
因此，重新运行相同划分不能恢复“untouched confirmatory test”的地位。最终论文必须
明确披露这一点，并优先增加冻结方法后的外部数据验证。

## 2. 数据审计与不可省略的披露

数据来自 KAIST/Mendeley Data（`10.17632/rgn5brrgrn.5`，CC BY 4.0），包括同一厂商
1.0、1.5 和 3.0 kW 三台 PMSM，在固定 3000 rpm、单一负载设置下采集的三相电流。
每台电机有一个唯一健康记录和 14 个故障记录：inter-turn 与 inter-coil 各 7 个标称
严重度，共 45 个唯一电流记录。

审计发现必须写入 Dataset/Limitations：

- 两个故障目录中的 healthy 文件在三台电机上均具有相同文件大小和 CRC；1.0 kW
  文件另经 SHA-256 验证完全相同。因此，每台电机只有一个唯一健康时间序列，两个
  healthy alias 已去重，不能当作独立重复试验。
- 若干 TDMS 实际长度约为 121--149 s，而非统一 120 s。所有记录只保留最前 120 s，
  以保证每个记录等权且避免利用额外时长。
- 电流以 100 kHz 采样；主实验使用 0.2 s 无重叠窗口。每个 120 s 记录产生 600 个
  窗口。
- 健康特征存在约 3 s 的强周期性 nuisance pattern，因此使用 3 s 非重叠宏块，每块
  15 个窗口、每个记录 40 个块。随机逐窗拆分不作为有效主结果。
- “Cross-capacity”仅指这三台不同额定功率、同厂商、同拓扑、同转速与同负载的电机，
  不代表跨厂商、跨拓扑或变工况泛化。

## 3. 三折 LOMO 与目标健康时间划分

外层采用固定三折 leave-one-motor-out（LOMO）：每次留出 1.0、1.5 或 3.0 kW 中的一台
作为未知目标，其余两台作为源电机。任何外层目标故障样本都不参与特征归一化、协方差
估计、ridge 选择或报警阈值校准，只在最终 pilot evaluation 中计算指标。

目标电机唯一健康记录的 40 个连续宏块按时间固定划分：

| 区间 | block id | 数量 | 时长 | 用途 |
|---|---:|---:|---:|---|
| adaptation | 0--3 | 4 | 12 s | 目标健康中心/尺度与协方差参考 |
| guard 1 | 4 | 1 | 3 s | 隔离 adaptation 与 calibration |
| calibration | 5--24 | 20 | 60 s | 块共形阈值与 p-value |
| guard 2 | 25 | 1 | 3 s | 隔离 calibration 与 test |
| later-time healthy test | 26--39 | 14 | 42 s | 误报率评估 |

源电机的健康 blocks 0--23 用于参考统计量。源与目标的健康片段均按电机分别以 median
和 robust scale（MAD，不足时退化到标准差）中心化/缩放；目标异常分数的 location 固定
为该变换后的零向量。三折中共得到 42 个 later-time healthy test blocks，以及
42 个目标故障记录、1,680 个目标故障宏块。

## 4. Proposed method 的可复现定义

### 4.1 Scale-free current representation

主分析使用 `scale_free` 特征臂。它保留频率、相间不平衡、归一化谐波、THD、侧带比、
谱熵、crest factor、kurtosis、相 RMS 比、Clarke 半径变异系数和零序比等量纲无关特征，
并排除相 RMS、基波幅值、Clarke 半径均值和零序 RMS 等绝对尺度量。选择此特征臂的
目的，是降低额定功率和电流幅值本身造成的 domain shortcut。

### 4.2 Motor-balanced Log-Euclidean covariance transfer

令每台允许使用的健康参考数据经过上述稳健变换后为
\(\widetilde{X}_m\)，其样本协方差为 \(S_m\)。先对每台电机分别加入相对 ridge：

\[
S_m^{(\lambda)} = S_m + \lambda\,\bar{v}_m I, \qquad
\bar{v}_m = \operatorname{tr}(S_m)/d .
\]

随后在 symmetric positive-definite manifold 上给予每台电机相同权重：

\[
\Sigma_{\mathrm{LE}}
= \exp\!\left(\frac{1}{M}\sum_{m=1}^{M}\log S_m^{(\lambda)}\right).
\]

在当前三折中，\(M=3\)：两台源电机与目标电机各贡献一个协方差，不按窗口数加权。
ridge fraction \(\lambda=0.01\) 在每个外层 fold 内仅通过两台源电机互作 pseudo-target
的 nested validation 选择；选择目标为 source validation detection minus twice FAR。
三折均选择 0.01，外层目标故障标签从未进入该选择。

单窗口异常分数为 target-centered Mahalanobis score：

\[
s(x)=\widetilde{x}^{\top}\Sigma_{\mathrm{LE}}^{\dagger}\widetilde{x}.
\]

每个 3 s 宏块使用 15 个窗口分数的最大值 \(A_b=\max_{i\in b}s(x_i)\)。以 20 个目标
健康 calibration blocks 的分数 \(A_1,\ldots,A_{20}\) 计算

\[
p_b=\frac{1+\sum_{j=1}^{20}\mathbf{1}(A_j\ge A_b)}{21},
\]

并在 \(p_b\le 0.05\) 时报警。由于 calibration blocks 来自同一连续健康记录，本文只
称其为 **empirically calibrated block risk under a block-stationarity/mixing
interpretation**；不声称在任意时间依赖下具有普通 exchangeable split-conformal 的
有限样本 distribution-free coverage。

## 5. 主结果（scale-free, block max, alpha = 0.05）

| Method | Healthy FAR | 95% Wilson upper | Mean detection | Worst-motor detection | Mean block AUROC | H1 empirical gate |
|---|---:|---:|---:|---:|---:|---|
| Target Ledoit--Wolf | 1/42 = 2.38% | 12.32% | 90.30% | 82.14% | 0.9969 | fail |
| Target sample covariance | 0/42 = 0% | 8.38% | 93.87% | 86.79% | 0.9983 | pass |
| Source-only covariance | 0/42 = 0% | 8.38% | 89.11% | 70.18% | 0.9968 | pass |
| Arithmetic entity-balanced covariance | 0/42 = 0% | 8.38% | 95.48% | 87.86% | 0.9989 | pass |
| **Proposed Log-Euclidean entity covariance** | **0/42 = 0%** | **8.38%** | **95.71%** | **90.00%** | **0.9993** | **pass** |

H1 的 pilot gate 定义为 pooled 95% Wilson upper 不超过 12%，且任一电机经验 FAR 不超过
15%。Proposed method 在 later-time healthy blocks 上没有误报，Wilson 上界仍为 8.38%，
因此结果不能解释为“真实 FAR 等于零”。

Proposed method 的逐电机结果为：

| Target motor | False alarms / healthy blocks | Fault blocks detected | Detection | Block AUROC |
|---|---:|---:|---:|---:|
| 1.0 kW | 0/14 | 560/560 | 100.00% | 1.0000 |
| 1.5 kW | 0/14 | 504/560 | 90.00% | 0.9999 |
| 3.0 kW | 0/14 | 544/560 | 97.14% | 0.9981 |
| pooled/mean | 0/42 | 1,608/1,680 | 95.71% | 0.9993 (fold mean) |

一个有用的 domain-shift 对照是监督式 logistic pilot：固定 source-only threshold 在
1.0 和 1.5 kW 目标健康块上产生 100% FAR；改用目标健康校准后 FAR 降为 0，但三个
feature arms 的平均 detection 仅约 49.58%--59.52%。这说明高 AUROC 或源域分类性能
不能替代目标电机的健康风险校准。

## 6. 严格同协议的一类异常强基线

One-Class SVM、Isolation Forest 与 MinCovDet 均使用相同的 `scale_free` 特征、目标
健康时间划分、3 s block maximum、20 块 calibration 和 `alpha=0.05`，且没有目标故障
参与拟合、超参数选择或阈值校准。target-only 版本只拟合 4 个目标 adaptation blocks；
motor-balanced source+target 版本从每台电机各取四个完整健康块（每台 60 个窗口），
避免源电机因允许的健康窗口更多而主导模型。

OCSVM 固定为 RBF、`gamma=scale`、`nu=0.05`；Isolation Forest 固定 500 trees，报警
阈值不使用模型自身的 contamination 设置；MinCovDet 在健康拟合行上用 rank-revealing
QR 删除不变或代数冗余列后拟合。以上设置未使用目标故障选择。随机方法的主结果固定
seed 20260820，并总计运行五个预设 seed（包含主 seed）。

| One-class method | Healthy FAR | Wilson upper | Record-macro detection | Record-bootstrap 95% CI | Worst motor | Mean AUROC | H1 gate |
|---|---:|---:|---:|---:|---:|---:|---|
| Target OCSVM | 0/42 | 8.38% | 89.70% | [81.78, 96.37]% | 82.68% | 0.9979 | pass |
| Balanced source+target OCSVM | 0/42 | 8.38% | 91.25% | [83.63, 97.56]% | 82.86% | 0.9966 | pass |
| Target Isolation Forest | 1/42 | 12.32% | **97.56%** | [93.63, 100.00]% | 95.36% | 0.9942 | fail |
| **Balanced source+target Isolation Forest** | **0/42** | **8.38%** | **96.07%** | **[90.77, 99.52]%** | **90.71%** | 0.9954 | **pass** |
| Target MinCovDet | 1/42 | 12.32% | 89.82% | [82.26, 96.19]% | 84.11% | 0.9966 | fail |
| Balanced source+target MinCovDet | 1/42 | 12.32% | 92.32% | [86.49, 97.20]% | 87.32% | 0.9896 | fail |

这里的故障区间以 42 条完整 fault records 为单位、按 motor 分层 bootstrap，条件于当前
三台已观察电机；没有把同一记录的 40 个相关 blocks 当作独立样本。健康 Wilson 区间为
沿用 H1 gate 的描述性统计，因为 42 个测试块实际仅来自三条健康时间序列，独立二项
假设不成立。

Proposed 与六个一类基线的配对记录比较为：

| Baseline | Proposed minus baseline detection | 95% paired-record CI | Baseline healthy FAR | Interpretation |
|---|---:|---:|---:|---|
| Target OCSVM | +6.01 pp | [1.07, 11.90] pp | 0/42 | Proposed favored |
| Balanced source+target OCSVM | +4.46 pp | [-0.42, 10.18] pp | 0/42 | unresolved |
| Target Isolation Forest | -1.85 pp | [-4.88, 0.65] pp | 1/42 | IF point estimate higher, but H1 fails |
| Balanced source+target Isolation Forest | **-0.36 pp** | **[-3.93, 3.45] pp** | **0/42** | **statistical tie** |
| Target MinCovDet | +5.89 pp | [0.95, 11.67] pp | 1/42 | Proposed favored |
| Balanced source+target MinCovDet | +3.39 pp | [0.30, 6.85] pp | 1/42 | Proposed favored |

最重要的结果边界是：balanced Isolation Forest 的 detection 为 0.9607，Proposed 为
0.9571，且两者均为 `0/42` 误报；差异区间跨 0，因此二者在当前 pilot 中统计打平。
target Isolation Forest 的 0.9756 检出率是更高的点估计，但它产生 `1/42` 健康误报，
Wilson 上界 0.1232 严格超过 H1 的 0.12 门槛。五 seed 敏感性中，balanced Isolation
Forest detection 为 0.9601--0.9685、FAR 为 0--2/42；target Isolation Forest detection
为 0.9649--0.9756、FAR 为 0--1/42。MinCovDet 的 seed 波动更大。

因此不能将 Proposed 写成全面优于传统强一类检测器或“全面 SOTA”。可用表述是它相对
部分基线具有优势，并以确定性协方差几何、可审计的电机等权结构和经验块风险校准，在
balanced Isolation Forest 达到统计不可区分的性能。是否存在可泛化优势必须由冻结后的
外部验证决定。

## 7. 协方差方法的配对 record-level bootstrap

比较以 42 个目标故障记录为重采样单位，在每台电机内有放回抽样后再等权平均三台
电机；使用 10,000 次重复、seed 42。\(\Delta\) 为 Proposed 减 Comparator 的记录级
detection rate。以下区间为未做多重比较校正的 percentile 95% bootstrap CI：

| Comparator | Mean delta | 95% bootstrap CI | Pr(bootstrap delta > 0) | Interpretation |
|---|---:|---:|---:|---|
| Source-only covariance | +6.61 pp | [1.79, 12.32] pp | 0.9988 | interval excludes 0 in this pilot |
| Target Ledoit--Wolf | +5.42 pp | [0.59, 11.19] pp | 0.9858 | interval excludes 0 in this pilot |
| Target sample covariance | +1.85 pp | [-2.14, 6.01] pp | 0.8123 | no supported superiority |
| Arithmetic entity-balanced covariance | +0.24 pp | [-1.37, 2.32] pp | 0.5793 | methods are statistically indistinguishable here |

因此，论文可以主张该 pilot 中 Proposed 相比 source-only covariance 和 target Ledoit
具有更高 detection；不能主张其总体显著优于 target sample covariance 或 arithmetic
entity balancing。Log-Euclidean 设计的价值需要以几何合理性、跨 fold 最差性能和外部
验证支撑，不能只用 +0.24 pp 的平均差异包装成优势。

## 8. 预设假设的诚实判定

### H1：目标健康误报风险——pilot 支持

Proposed 的 pooled FAR 为 0/42，95% Wilson upper 为 8.38%，单电机最大经验 FAR 为 0，
满足事先写下的经验 gate。但只有一个唯一健康记录/电机，且 calibration/test 仍来自同一
连续序列，所以证据是经验性的，不是安全认证。

### H2：最低两个严重度改进——不可辨识/失败

所有五种协方差方法对每个故障家族最低两个标称严重度的平均 detection 都达到 100%，
出现 ceiling effect。因 comparator 已为 100%，不可能实现原计划的 +10 percentage
points；当前数据不能支持“Proposed 特别改善轻微故障”的主张。不得更换严重度子集或
阈值以事后制造该结论。

### H3：严重度单调性——明确失败

Proposed 的 severity--mean-score Spearman 相关为：1.0 kW inter-coil -0.500、
inter-turn -0.607；1.5 kW inter-coil -0.429、inter-turn +0.571；3.0 kW inter-coil
+0.679、inter-turn +0.357。六个 motor-family 组合中有三个为负，故“异常分数随标称
严重度单调增加”的假设失败，严重度估计应从 Paper 1 主贡献中删除。可能原因包括控制器
响应、不同短路拓扑和标签严重度与电流可分性的非线性关系，但这些目前只是待验证解释。

## 9. 可写与不可写的论文主张

当前证据允许的限定表述：

- “In a three-fold cross-capacity pilot, the method used no target-fault labels and
  achieved 0/42 later-time healthy false alarms with 95.7% mean block detection.”
- “Equal-motor covariance transfer avoids allowing the motor with more windows to
  dominate the reference geometry.”
- “Record-stratified bootstrap favored the proposed method over source-only and
  target Ledoit baselines, while not resolving differences versus target sample or
  arithmetic entity-balanced covariance.”
- “The proposed method and motor-balanced source+target Isolation Forest were
  statistically indistinguishable in record-level detection while both produced 0/42
  later-time healthy false alarms.”

禁止或尚未支持的表述：

- 不能写“guaranteed 5% FAR”“distribution-free under temporal dependence”或 safety
  guarantee；
- 不能把 duplicate healthy aliases 写成独立重复；
- 不能声称跨厂商、跨拓扑、变转速/负载或任意功率等级泛化；
- 不能声称 severity estimation、prognosis、RUL 或低严重度 superiority；
- 不能声称 Log-Euclidean 方法显著优于所有 covariance baselines；
- 不能声称 Proposed 全面优于强一类异常基线、Isolation Forest 或达到全面 SOTA；
- 不能声称当前 target-fault evaluation 是未查看的 confirmatory test；
- 不能保证投稿或录用结果。

## 10. 目标健康适配预算敏感性

冻结 scale-free 特征、Log-Euclidean ridge 0.01、3 s 宏块和独立 60 s 校准序列后，
评估 3/6/12/24 s 目标健康适配量。固定相同 calibration/test 时段的平均检出率分别为
94.64%、96.90%、96.25% 和 94.94%，四种预算均为 `0/30` 健康测试块误报；对应最差
电机检出率为 90.00%、91.61%、90.00% 和 86.96%。顺序部署划分也得到相同的非单调
趋势，平均检出率为 93.33%、96.96%、95.71% 和 94.94%。

这些结果说明 3--24 s 适配范围内没有性能崩溃，但不能依据已查看的目标故障事后选择
表面最优的 6 s。若将 3/6/12/24 s 解释为 conformal calibration 本身，则仅有 1/2/4/8
个宏块，`alpha=0.05` 下均不能形成有限的保守阈值；至少需要 19 块（57 s），主实验
使用 20 块（60 s）。该区分必须写清：12 s 是协方差适配预算，60 s 才是报警校准预算。

## 11. 宏块长度与聚合敏感性

固定 detector、12 s 适配、60 s 校准和时间顺序后，仅重新组合既有 0.2 s 窗口。
`alpha=0.05` 下 1/2/3 s 分别提供 60/30/20 个校准块，能够评估；5/6 s 仅有
12/10 个校准块，不能形成有限阈值，故明确跳过。3 s/max 精确复现主结果：FAR
`0/42`、平均检出 95.71%、最差电机 90.00%。1 s/max 与 2 s/max 的平均检出分别为
93.61% 和 93.73%；3 s/q90 提高到 97.32%，但产生 `1/42` 健康误报，其 Wilson 上界
12.32% 超过预设 12% gate，不能据此改换主设置。

不同宏块长度改变的是同一 120 s 记录被切出的行数，不会创造新的独立实验重复。
敏感性表中的 Wilson 区间仅作描述，3 s/max 仍因健康自相关审计而保持预设主设置。

## 12. 从 pilot 到可投稿稿件仍需完成

1. 冻结当前 method、ridge、特征和阈值流程，在独立外部数据上验证；若数据域不同，明确
   标为 out-of-domain stress test，而非与 KAIST 同分布复现。
2. 适配预算与 block length/aggregation sensitivity 已完成；任何默认设置的选择都
   不能依据目标故障结果。还需补充跨 session 的依赖稳健性证据。
3. 一类强基线已完成；仍需在完全相同 LOMO/time-block protocol 下补充强时序与
   domain-adaptation baselines。对深度/随机模型报告多 seed，而协方差方法本身是
   确定性的。
4. 报告每个 record/fault family 的失败案例，尤其是 1.5 kW 漏检与严重度非单调现象。
5. 对普通 conformal exchangeability 不成立的风险给出理论假设和依赖敏感性讨论。
6. 在 manuscript 中将当前表格标为 exploratory pilot；只有冻结后的新数据结果才能承担
   confirmatory claim。

当前可复核结果位于 `results/healthy_covariance_v0/aggregate_summary.csv`、
`results/healthy_covariance_v0/summary.csv`、
`results/healthy_covariance_v0/paired_record_bootstrap.csv`，ridge 选择位于
`results/log_ridge_selection/selected_ridge.json`，适配预算结果位于
`results/calibration_budget_sensitivity/aggregate_summary.csv`，宏块敏感性位于
`results/block_sensitivity/aggregate_summary.csv`；一类基线、seed 敏感性及与 Proposed
的配对比较位于 `results/oneclass_baselines/aggregate_summary.csv`、
`results/oneclass_baselines/randomness_ranges.csv` 和
`results/oneclass_baselines/comparison_to_proposed.csv`。
