# When Healthy-Only Transfer Fails: PMSM Cross-Dataset Evaluation

本仓库服务于博士主线：**科学机器学习 × 工业数字孪生 × 电驱动健康管理**。

首篇论文已经收敛为一个由冻结外部实验直接证伪、但更具科学价值的问题：

> **When Healthy-Only Transfer Fails in PMSM Stator-Fault Detection:
> A Leakage-Resistant Cross-Dataset Evaluation**

核心问题不再是包装某个新算法优越，而是检验：同数据集内近乎满分的健康样本迁移，
在电机拓扑、采样率、转速轨迹和负载同时变化时是否仍成立。仓库保留冻结主方法的失败，
Log-Euclidean 方法、不在揭盲后偷换主方法，并把跨数据集排名反转、负迁移和报警漂移
作为 Paper 1 的主要发现。

## 当前可复现的先导结果

截至 2026-08-21，三折 LOMO 的全量电流先导实验已经跑通：

- 27,000 个无重叠 0.2 s 窗口，45 条去重后的记录，3 s 宏块；
- 每折只用目标电机前 12 s 健康数据适配协方差，另用 20 个健康宏块校准；
- Log-Euclidean 实体平衡方法在 42 个 later-time 健康测试块上误报 `0/42`，
  Wilson 95% 上界 `0.0838`；
- 三台目标电机的故障块检出率为 `1.000 / 0.900 / 0.971`，折均值 `0.957`；
- 同协议的 motor-balanced source+target Isolation Forest 同样为 `0/42` 误报，
  record-macro 检出率为 `0.9607`；Proposed 为 `0.9571`，两者配对记录差为
  `-0.0036`（95% CI `[-0.0393, 0.0345]`），在当前数据上统计打平；
- target-only Isolation Forest 的检出率更高（`0.9756`），但产生 `1/42` 健康误报，
  描述性 Wilson 上界为 `0.1232`，超过预设 H1 的 `0.12` 门槛；
- 相对 target Ledoit-Wolf 和 source covariance，记录级配对 bootstrap 的检出率差
  95% CI 为正；相对 target sample covariance 和算术实体均值，CI 仍跨 0；
- 故障异常分数不随标称严重度稳定单调，原严重度排序假设未成立。
- 在提交 `fddf2f7` 冻结后，独立双三相 PMSM 的健康阶段得到 `1/32` 误报；点 FAR
  为 `0.03125`，但描述性 Wilson 上界为 `0.1574`，超过预设外部 H1 的 `0.12`，
  因此该闸门按失败报告，方法和阈值不作事后调整。
- 48 条外部故障记录在协议与阈值冻结后一次性揭盲。原方法的 fault-block detection
  仅 `0.2500`（95% record-bootstrap CI `[0.2109, 0.2943]`），AUROC `0.6354`；
  预先实现的 target-only MinCovDet 达到 `0.7005`（`[0.6536, 0.7526]`）、
  AUROC `0.9268`，且健康误报为 `0/32`。
- 原方法在外部故障 block 0--2 上均为 `0/48` 报警，而 block 7 为 `48/48`；唯一健康
  误报也位于 block 7。检出率还从 0 N m 的 `0.5625` 降至 35 N m 的 `0.1250`，
  显示分数与升速/负载轨迹强烈共变。
- target-only MinCovDet 比 source+target MinCovDet 高 `39.84` 个百分点
  （95% CI `[35.42, 44.27]`），构成该外部电机与冻结协议下的条件性负迁移证据；它仍只是预设比较器，不能在
  揭盲后改称“原主方法”。
- 原方法前 4/7/8 blocks 的 detection 仅 `2.60% / 14.29% / 25.00%`，record-any
  alarm 却从 `10.42% / 52.08%` 跳到 `100%`；中位首次报警约在 block 6、
  1,643 rpm。逐 block 匹配位置后平均 AUROC 为 `0.8047`，高于 pooled `0.6354`，
  说明仍有故障排序信息，但固定阈值被工况漂移淹没。
- 五个预设 seed 下 target MinCovDet 的外部检测为 `0.6536--0.7708`、FAR 为
  `0--2/32`，只有 `3/5` seed 通过 H1；其比较器排名较稳，但单次 `0.7005/0 FAR`
  不能包装成稳定保证。
- 冻结几何的 post-reveal 贡献审计发现：`fundamental_hz` 的 direction-free AUROC 仅
  `0.5038`，在选定对称分解下却占外部 fault/health-test 绝对分数贡献的 `18.07%/38.54%`；三次谐波
  max/mean 的 AUROC 为 `0.9266/0.9255`，合计贡献却不足 `0.6%`。这支持“速度方向被
  过度加权、故障敏感谐波被低权重”的具体失败机制，但不构成跨电机因果结论。
- 将全部 KAIST 电流先抗混叠降采样至 10 kHz，再机械复用冻结协议后，原方法外部
  detection `0.2500→0.2474`、AUROC `0.6354→0.6331`、FAR 仍为 `1/32`；因此
  `100 kHz→10 kHz` 差异不支持为外部负迁移的主因。
- 在另一套含 200 W/20 kW 两台 PMSM、21 条瞬态记录的数据上，预注册主解析器因
  MATLAB `timeseries` 仅以元数据保存隐式时间而得到 `0/21` 兼容记录；该失败在计分前
  原样冻结，不能算检测结果。
- 事后仅修复时间重建后，200 W 为 `12/12` 可用，20 kW 仅 `4/9`，未过预设 `80%`
  兼容性门槛。200 W 单电机敏感性中，12 种方法在前 1 s 的 `60` 个故障窗和完整 2 s
  的 `120` 个故障窗上均为零告警；该结果只用于暴露数据/协议边界，不作为第三个确认集。

这些结果把论文从“新方法精度论文”转成“防泄漏跨数据集评估与负迁移失败研究”。
它具备继续形成 SCI/SCIE 稿件的价值，但单台外部电机仍限制总体推断，也不构成录用
保证。精确结果与失败项见 [`docs/fault_reveal_log.md`](docs/fault_reveal_log.md)、
[`results/external_pmsm_analysis/`](results/external_pmsm_analysis/) 和
[`docs/secondary_transient_reveal_log.md`](docs/secondary_transient_reveal_log.md)。

## JEET 投稿包状态

面向 *Journal of Electrical Engineering & Technology* 的双盲投稿包已经生成在
[`submission/jeet/`](submission/jeet/)：匿名 Word 正文、17 页审稿 PDF、独立标题页
模板、投稿信模板、8 页补充材料、匿名复现代码包以及 Fig1--Fig11 独立源文件均已就位。
最终视觉与结构复核状态记录在 [`submission/jeet/QA_Report.md`](submission/jeet/QA_Report.md)；
补齐作者信息后仍须由全体作者在最终提交所用 Word 版本中逐页复核并批准全部声明。
截至 2026-08-21，Springer 与 KIEE 均指向同一 Editorial Manager 地址，但落地页仍显示
“Site under development”并明确禁止正式投稿；若提交时该警告仍在，须先联系
`jeet@kiee.or.kr` 确认有效入口。
作者信息可直接按
[`submission/jeet/Author_Input_Form_CN.md`](submission/jeet/Author_Input_Form_CN.md)
填写或回复。

提交前剩余的人工门槛和费用警告见
[`submission/jeet/Submission_Checklist.md`](submission/jeet/Submission_Checklist.md)，
完整 QA 边界见 [`submission/jeet/QA_Report.md`](submission/jeet/QA_Report.md)，期刊规则
映射见 [`docs/jeet_submission_requirements.md`](docs/jeet_submission_requirements.md)。

## 为什么仍把它作为 Paper 1

- 数据来自 1.0、1.5、3.0 kW 三台真实 PMSM，可做严格的整机留出验证；
- 研究对象同时覆盖跨电机分布偏移、少样本在线校准、可信报警与真实负迁移；
- 主要贡献不是更换网络模块，而是目标域无故障标签、文件/整机防泄漏、冻结揭盲和
  失败机制诊断；
- 结果展示了同数据集高 AUROC、record-any alarm 与随机窗口划分为何会夸大可部署性；
- 这个失败自然导向 Paper 2：只用健康数据的转速/负载条件化模型，并在新数据上再次
  冻结确认。

详细假设、划分、指标、止损条件见
[`docs/research_protocol.md`](docs/research_protocol.md)，论文结构见
[`paper/outline.md`](paper/outline.md)，当前 SCI/SCIE 期刊梯度与投稿硬门槛见
[`docs/submission_strategy.md`](docs/submission_strategy.md)，博士三篇论文与昌原本地合作
路线见 [`docs/phd_roadmap.md`](docs/phd_roadmap.md)。原始文献缺口与禁止主张见
[`docs/literature_gap.md`](docs/literature_gap.md)，机械生成的 S1--S9 补充材料见
[`paper/supplementary_material.md`](paper/supplementary_material.md)。

## 数据轨道

### 探索主轨：同系列跨容量定子故障

- 数据 DOI：`10.17632/rgn5brrgrn.5`，CC BY 4.0；
- 三台电机、两类短路、每类健康状态加 7 个故障严重度；
- 三相电流 100 kHz，单轴振动 25.6 kHz，每段记录 120 s；
- 主实验为三轮 leave-one-motor-out，原始记录和连续时间块不可跨集合。

### 冻结外部验证：双三相 PMSM（已完成揭盲）

- Zenodo `10.5281/zenodo.13889418`，CC BY 4.0；8 条健康负载记录和 48 条 ITSC
  记录，10 kHz、双三相电流；
- 健康审计确认记录是连续升速而非稳态；共同分析段在看故障前固定为 `[12,36) s`；
- 0 Nm 仅作 12 s 目标适配，10/20/30 Nm 产生 24 个系统校准块，
  5/15/25/35 Nm 产生 32 个完全不同文件的健康 FAR 测试块；
- 两个三相子系统分别计分，再取系统 maximum 并用同一系统分数校准；
- 48 条故障文件在协议、代码、环境与健康阈值形成带哈希提交后一次性下载并校验；
  完整 6 turns × 8 loads 网格已按冻结 `[12,36) s` 协议运行，无文件事后排除。

完整揭盲规则见 [`docs/external_validation_protocol.md`](docs/external_validation_protocol.md)。

### 预注册副验证：200 W/20 kW 瞬态 ITSC（非确认性）

- Zenodo `10.5281/zenodo.15631383`，CC BY 4.0；200 W 电机 12 条、20 kW 电机 9 条，
  每条均含健康到故障的转变，没有独立健康文件；
- 归档、解析器、通道白名单、起点算法、整记录留出和 `80%` 电机兼容门槛均在读取
  信号值前冻结；
- 主解析器失败与事后隐式时间修复分目录保存；20 kW 不过门槛，200 W 结果仅作单电机
  post-reveal 敏感性，不提升为跨容量验证。

完整协议与揭盲时间线见
[`docs/secondary_transient_validation_protocol.md`](docs/secondary_transient_validation_protocol.md)
和 [`docs/secondary_transient_reveal_log.md`](docs/secondary_transient_reveal_log.md)。

### 副轨 A：几何到转矩波形代理

Zenodo `10.5281/zenodo.15688397` 含 20 个几何参数和 120 点周期转矩曲线。
该数据用于博士后续的几何数字孪生研究；必须以 DFT+GP 为强基线，不能仅凭使用
DeepONet/FNO 声称创新。

### 副轨 B：PMSM 温度数字孪生

保留已有 profile-wise 温度估计代码，作为后续热健康评估与在线状态建模支线，
不作为当前 Paper 1 的主要投稿证据。

## 快速开始（PowerShell）

```powershell
$python = "C:\Users\lkcfq\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
& $python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -U pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# 三个 ZIP 合计约 6.97 GB；脚本支持断点续传并逐文件校验 SHA-256。
& .\.venv\Scripts\python.exe scripts\download_kaist_faults.py
& .\.venv\Scripts\python.exe scripts\audit_kaist_archives.py
& .\.venv\Scripts\python.exe scripts\extract_kaist_current.py
& .\.venv\Scripts\python.exe scripts\build_current_features.py

# 超参数只由外层折的源电机嵌套选择，然后运行透明分类器与主协方差方法。
& .\.venv\Scripts\python.exe scripts\select_log_covariance_ridge.py
& .\.venv\Scripts\python.exe scripts\run_fault_baseline.py
& .\.venv\Scripts\python.exe scripts\run_healthy_covariance_baseline.py `
    --ridge-fraction 0.001 --log-ridge-fraction 0.01
& .\.venv\Scripts\python.exe scripts\compare_covariance_methods.py

# 严格同协议的一类强基线及其与主方法的记录级配对比较。
& .\.venv\Scripts\python.exe scripts\run_oneclass_baselines.py
& .\.venv\Scripts\python.exe scripts\compare_oneclass_to_proposed.py

& .\.venv\Scripts\python.exe scripts\run_calibration_budget_sensitivity.py
& .\.venv\Scripts\python.exe scripts\run_block_sensitivity.py
& .\.venv\Scripts\python.exe scripts\make_paper1_figures.py

# 外部验证的健康阶段：默认下载器不会下载48条故障记录。
& .\.venv\Scripts\python.exe scripts\download_external_pmsm_validation.py
& .\.venv\Scripts\python.exe scripts\audit_external_pmsm_health.py
& .\.venv\Scripts\python.exe scripts\build_external_pmsm_health_features.py

# 仅在形成冻结提交后运行一次；此命令会消耗32块外部健康测试集。
& .\.venv\Scripts\python.exe scripts\run_external_pmsm_validation.py

& .\.venv\Scripts\python.exe -m pytest
& .\.venv\Scripts\ruff.exe check .
```

仅检查一台电机的数据格式时可使用：

```powershell
& .\.venv\Scripts\python.exe scripts\download_kaist_faults.py --motors 1.0kW
```

外部故障揭盲不是普通 quickstart 步骤。只有满足冻结协议第 6 节的条件后，才运行：

```powershell
& .\.venv\Scripts\python.exe scripts\download_external_pmsm_validation.py `
    --datasets dual_three_phase_fault_reveal
& .\.venv\Scripts\python.exe scripts\build_external_pmsm_health_features.py
& .\.venv\Scripts\python.exe scripts\run_external_pmsm_validation.py --require-faults
& .\.venv\Scripts\python.exe scripts\analyze_external_pmsm_results.py
& .\.venv\Scripts\python.exe scripts\analyze_external_failure_diagnostics.py
& .\.venv\Scripts\python.exe scripts\analyze_external_feature_drift.py
& .\.venv\Scripts\python.exe scripts\make_external_validation_figures.py

# Post-reveal 采样率敏感性：不会覆盖原100 kHz特征或冻结外部结果。
& .\.venv\Scripts\python.exe scripts\build_kaist_10khz_features.py
& .\.venv\Scripts\python.exe scripts\run_healthy_covariance_baseline.py `
    --features data\processed\kaist_current_features_10khz.csv.gz `
    --results-dir results\sampling_rate_sensitivity\kaist_10khz_covariance `
    --feature-arms scale_free --ridge-fraction 0.001 --log-ridge-fraction 0.01
& .\.venv\Scripts\python.exe scripts\run_oneclass_baselines.py `
    --features data\processed\kaist_current_features_10khz.csv.gz `
    --results-dir results\sampling_rate_sensitivity\kaist_10khz_oneclass
& .\.venv\Scripts\python.exe scripts\run_external_pmsm_validation.py `
    --source-features data\processed\kaist_current_features_10khz.csv.gz `
    --results-dir results\sampling_rate_sensitivity\external_10khz_source `
    --require-faults
& .\.venv\Scripts\python.exe scripts\summarize_sampling_rate_sensitivity.py
```

## 复现红线

- 同一台目标电机的任何故障样本不得进入训练、阈值校准或超参数选择；
- 同一连续时间块的相邻窗口不得随机分到不同集合；
- 标准化、基频估计阈值、特征选择和校准阈值只能用允许的数据拟合；
- 最终测试集在模型、超参数和报警阈值冻结前不可查看；
- 同时报告误报率、各严重度检出率、尾部失败和置信区间；
- 不把固定转速/负载下的三台同厂电机结果夸大为任意跨型号泛化。
- 不把同一记录内的宏块当作独立试验重复；显著性比较以故障记录为重采样单位。

## 目录

- `src/pmsm_sci/`：数据、切分、特征、模型、校准与实验代码
- `scripts/`：可审计的数据下载与预处理入口
- `tests/`：防泄漏、信号处理和校准测试
- `docs/`：研究协议、数据清单和决策记录
- `paper/`：论文结构和逐步形成的正文
- `references/`：核心文献 BibTeX
- `data/`、`results/`：本地数据和实验产物；仅提交复现论文所需的小型审计摘要

本项目的目标是形成可投稿、可复现、经强基线验证的 SCI 论文；任何研究设计都不能
保证期刊录用，因此预先定义成功门槛和失败后的改题条件。
