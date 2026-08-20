# 研究协议 v0.3

更新日期：2026-08-20

> 状态说明：本文档保留揭盲前的原始研究问题与方法开发边界，不随外部结果重写。
> 冻结外部实验已完成并否定原方法优越叙事；当前 Paper 1 题目与定位见
> `paper/outline.md`，完整揭盲记录见 `docs/fault_reveal_log.md`。

## 1. 长期博士方向

**科学机器学习 × 工业数字孪生 × 电驱动健康管理**

长期问题是：几何感知、多物理仿真预训练的电机数字孪生，能否利用未知电机的少量
健康传感器数据完成在线校准，并在电机、工况和故障分布偏移时提供可靠置信度与
拒判机制。

完整问题需要参数化仿真和新实验。首篇先验证其中公开数据足以支持的一环：跨真实
电机的 healthy-only 健康分布迁移与风险校准。

## 2. Paper 1 的冻结问题

### 暂定题目

**Healthy-Only Cross-Capacity PMSM Stator-Fault Detection via Motor-Balanced
Covariance Transfer and Block-Conformal Calibration**

中文：**基于电机实体平衡协方差迁移与健康样本块共形校准的跨容量永磁同步电机
定子故障检测**。

### 核心问题

在不使用目标电机任何故障样本的情况下，只允许使用少量目标健康电流，能否：

1. 将报警误报率经验校准到预设水平；
2. 检出匝间和线圈间短路；
3. 量化少量目标健康数据相对纯源迁移的价值；
4. 明确连续单记录数据下共形风险保证的适用边界？

“cross-capacity/cross-machine”在本文中仅指数据中的三台不同功率 PMSM，不等同于
跨任意厂商、拓扑或工况。

## 3. 数据、许可与审计事实

KAIST/Mendeley Data：`10.17632/rgn5brrgrn.5`，CC BY 4.0。

- 电机：1.0、1.5、3.0 kW，同一厂商、四极；
- 工况：固定 3000 rpm 和单一负载设置；
- 故障：inter-turn 与 inter-coil，各含健康加 7 个标称严重度；
- 信号：三相电流 100 kHz、单轴振动 25.6 kHz；
- 原始文件：3 个 ZIP、96 个 TDMS、6,973,577,960 bytes；
- 标称时长为 120 s，但部分故障文件实际为 121--149 s；主实验统一截取前 120 s，
  防止长记录获得更高权重；
- 两个故障目录中的 healthy 文件是同内容别名，去重后电流主实验为每台 15 条、
  合计 45 条唯一记录，而不是 48 条独立记录；
- 所有电流记录的主导频率为 200 Hz；健康特征审计发现约 3 s 的强周期性。

主结果先只使用三相电流。电流与振动的时间同步关系未严格确认前，不加入多模态主张。

## 4. 数据划分与防泄漏

### 4.1 外层：整台电机留出

固定三折 leave-one-motor-out（LOMO）：

| Fold | 源电机 | 未知目标电机 |
|---|---|---|
| M1 | 1.5 + 3.0 kW | 1.0 kW |
| M2 | 1.0 + 3.0 kW | 1.5 kW |
| M3 | 1.0 + 1.5 kW | 3.0 kW |

源域可以使用健康与故障标签。目标域模型选择、特征选择、阈值校准只允许使用健康
信号；目标故障记录仅用于评估。

### 4.2 内层：连续时间块

每个 120 s 文件划为 600 个互不重叠 0.2 s 窗口，再组成 40 个互不重叠 3 s 宏块；
全表共 27,000 个窗口。目标健康块按时间顺序固定为：

- adaptation：块 0--3（12 s，60 窗）；
- guard：块 4；
- calibration：块 5--24（60 s，20 块）；
- guard：块 25；
- later-time healthy test：块 26--39（42 s，14 块）。

源健康的块 0--23 用于参考，块 24 为 guard，块 25--39 只供源阈值/嵌套验证。相邻
窗口不能随机跨集合；所有标准化参数只由对应折允许的健康块拟合。

`alpha=0.05` 时至少需要 19 个共形校准单位才能得到有限阈值。因此不能把 3--24 s
少量目标健康预算直接称为 5% 块共形校准；少量预算实验只改变协方差适配量，仍保留
独立的 20 个校准宏块。

## 5. 先导假设、结果与失败条件

以下假设在首轮方法探索前写入，但 KAIST 目标故障记录随后已用于方法比较。因此现有
结果是 exploratory pilot，不是独立 confirmatory test。失败假设保留，不在看到结果后
更换指标宣布成功。

### H1：目标误报风险

名义 `alpha=0.05` 下，三台目标电机 later-time healthy test 合并后的块级误报率，其
95% Wilson 上界不超过 0.12；同时任一电机的经验误报率不超过 0.15。

**先导结果：支持但未独立确认。** 主方法为 `0/42` 个健康测试宏块误报，Wilson 95%
上界 0.0838，三个目标电机经验误报均为 0。由于每台电机只有一条健康记录且宏块仍
有时间依赖，只可表述为“在该协议下经验校准”，不能宣称无条件有限样本风险保证。
同协议下，motor-balanced source+target Isolation Forest 也为 `0/42`；target-only
Isolation Forest 虽达到更高的 0.9756 故障检出率，却产生 `1/42` 误报，描述性 Wilson
上界 0.1232，因严格大于 0.12 而未通过 H1 gate。

### H2：轻微故障检出改善

原假设要求：在满足 H1 的阈值下，最低两个非零严重度的宏平均检出率相较固定源域
阈值至少提高 10 个百分点，且配对 bootstrap 95% CI 不跨 0。

**先导结果：不支持原差异主张。** 多个协方差方法对最低两个标称严重度均达到 100%
检出，产生天花板效应，无法证明主方法提高 10 个百分点。不得改选其他严重度挽救 H2。

### H3：严重度排序

原假设要求异常分数与标称故障严重度的 Spearman 相关在两类故障中均为正，三折合并
置信区间下界大于 0。

**先导结果：失败。** 多个电机/故障族的分数随严重度明显非单调；例如 1 kW 两类
故障的相关均为负。严重度估计从当前论文主张中移除，并作为故障标签与驱动控制相互
作用的限制报告。

### H4：块校准的必要性

原假设要求随机逐窗校准相较连续块校准会低估真实误报风险或不确定性。

**状态：尚未形成强证据。** 当前 later-time 测试仍来自同一健康记录，无法把重采样
差异解释为跨 session 泛化。需要独立健康记录或外部数据。

## 6. 方法与基线

### 6.1 主方法

1. 仅保留负序比、谐波比、THD、谱熵、形状统计等 scale-free 电流特征；
2. 每台源电机用其允许的健康块、目标电机用 adaptation 健康块分别做 robust
   median/MAD 对齐；
3. 为每台电机估计一份健康协方差 `Sigma_m`；ridge 只通过外层折内的 source-only
   伪目标验证选择，当前三折均选中 0.01；
4. 在 SPD 流形上给予每台电机相同权重：

   `Sigma_LE = exp[(1/M) * sum_m log(Sigma_m + lambda I)]`；

5. 以目标健康中心为零，用 Mahalanobis 距离形成逐窗异常分数；
6. 每个 3 s 宏块取最大逐窗分数，用 20 个目标健康宏块计算上尾共形 p-value；
7. `p <= 0.05` 时报警，并保存电机、故障记录和宏块三级原始输出。

### 6.2 已实现比较

- 目标健康 Ledoit-Wolf；
- 目标健康样本协方差；
- 纯源电机协方差迁移；
- 算术实体平衡协方差；
- Log-Euclidean 实体平衡协方差；
- source-supervised logistic / gradient boosting 透明基线；
- target-only One-Class SVM、Isolation Forest 和 MinCovDet；
- motor-balanced source+target One-Class SVM、Isolation Forest 和 MinCovDet；
- absolute-scale、scale-free 与 healthy-relative 特征消融。

所有一类方法使用相同 `scale_free` 表征、3 s block maximum 和 20 个与拟合区间不重叠的
目标健康 calibration blocks。target-only 版本只拟合 blocks 0--3；source+target 版本每台电机
等量使用四个完整健康块，目标取 0--3，源电机从允许的 0--23 中等间隔抽取。OCSVM
固定 RBF、`gamma=scale`、`nu=0.05`；Isolation Forest 固定 500 trees，模型自身的
contamination threshold 不用于报警；MinCovDet 仅依据健康拟合行用 rank-revealing QR
删除不变/代数冗余特征。超参数未用目标故障选择。随机方法以 seed 20260820 为主结果，
并用五个预设 seed（包含主 seed）报告敏感性。

待补强基线包括深度一类/强时序模型及至少一种显式跨域方法。FNO/WNO/Mamba 不是
必需装饰，只有在严格同协议下构成合理时序基线才加入。

### 6.3 当前方法差异的可用边界

记录级分层配对 bootstrap（42 条故障记录、10,000 次）显示，Log-Euclidean 版本相对
target Ledoit-Wolf 的平均检出率差为 0.0542（95% CI 0.0059--0.1119），相对纯 source
covariance 为 0.0661（0.0179--0.1232）；相对 target sample covariance 和算术实体均值
的区间跨 0。

因此，“Log-Euclidean 显著优于所有协方差方法”不是可用结论。主贡献应表述为实体
平衡健康协方差迁移与块风险校准框架，Log-Euclidean 是经源域选择的主要实例。

同协议一类强基线进一步收紧了结论边界：motor-balanced source+target Isolation
Forest 为 `0/42` 健康误报、0.9607 record-macro detection，Proposed 为 `0/42` 和
0.9571。记录级配对差（Proposed 减 Isolation Forest）为 -0.0036，95% bootstrap CI
`[-0.0393, 0.0345]`，没有方法优劣证据。target-only Isolation Forest 的检出率为
0.9756，但其 `1/42` 误报使描述性 Wilson 上界达到 0.1232，未通过 H1 gate。Proposed
相对 target OCSVM、target MinCovDet 与 motor-balanced MinCovDet 的配对区间为正；相对
motor-balanced OCSVM 的区间跨 0。论文不得声称 Proposed 全面优于强一类基线或达到
全面 SOTA。

时间依赖且每状态只有一条连续记录，本文不声称普通 split conformal 的严格交换性
保证。理论表述限定于块平稳/弱依赖近似，并重点报告原始误报计数和经验覆盖。

## 7. 指标与统计

### 主指标

- 名义 `alpha` 下的实际 false-alarm rate、原始计数和 Wilson/块 bootstrap CI；
- 每台目标电机及每条故障记录的 detection rate；
- 记录级配对检出率差及 95% CI；
- block AUROC/AUPRC，但不以高 AUROC 替代阈值风险分析。

### 辅助指标

- 各故障族/标称严重度检出率；
- calibration budget 与 block length 敏感性；
- 特征消融、推理时延、参数量和随机模型多 seed 稳定性；
- 严重度 Spearman 仅作为失败分析，不再作为正面主张。

故障比较以 42 条目标故障记录分层按电机配对 bootstrap，不能把 1,680 个故障宏块或
25,200 个窗口当作独立重复。健康风险同时报告合并 Wilson 区间和逐电机经验值。
多重比较采用 Holm 校正。

宏块敏感性已确认 1/2/3 s 可在 60 s 校准时满足有限阈值，5/6 s 不可行。3 s/max
精确复现主结果；3 s/q90 虽提高检出率，却出现一个健康误报并使描述性 Wilson 上界
超过 H1 gate。因此保留由健康自相关预先确定的 3 s/max，不用目标故障事后改设置。

## 8. 投稿闸门

首篇达到可投稿状态至少需要：

- 完整三折 LOMO，而不是单个目标电机；
- source-only、传统信号、已实现的一类异常和不确定性强基线；
- 无时间泄漏的数据清单和自动化测试；
- 主结果有记录级置信区间，失败案例与固定工况限制完整披露；
- 一条命令复现实验表格和图，原始输出可公开；
- 至少一个未参与方法开发的独立数据源/session 完全冻结验证。若无法取得，题目与
  结论必须降格为 benchmark/pilot，不应冲击高位综合期刊；
- 不以当前 KAIST 同一数据的探索性 bootstrap 代替独立确认。

优先期刊根据最终证据再定：以 AI 方法与外部验证为主可考虑 EAAI；以工业测量和
故障诊断实证为主可考虑 Measurement / ISA Transactions；证据较窄则选择更稳妥的
电机诊断或计算工程期刊。投稿前重新核实最新 scope、索引和费用政策。

## 9. 后续博士路线

- Paper 2：20 参数 PMSM 几何到周期转矩波形的 shift-aware surrogate 与曲线级 UQ；
- Paper 3：Pyleecan/FEMM + CREATOR Case 的仿真到真实健康校准；
- Paper 4：电磁—热—振动多物理状态更新与在线拒判。

目前没有公开数据同时覆盖“多电机完整几何 + 多物理场 + 故障实测 + 在线退化”。
长期课题采用参数化仿真预训练与真实健康数据校准的组合路线。
