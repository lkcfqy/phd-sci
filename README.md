# Healthy-Only Cross-Capacity PMSM Stator-Fault Detection

本仓库服务于博士主线：**科学机器学习 × 工业数字孪生 × 电驱动健康管理**。

首篇论文已经收敛为一个能用公开真实试验数据立即验证、且结论可证伪的问题：

> **Healthy-Only Cross-Capacity PMSM Stator-Fault Detection via Motor-Balanced
> Covariance Transfer and Block-Conformal Calibration**

核心目标是在完全不使用目标电机故障样本的条件下，仅用少量目标电机健康信号，
将源电机与目标健康数据形成的异常评分校准到预设误报风险，并检测不同严重度的
匝间/线圈间短路。主方法在对称正定协方差流形上对每台电机等权，避免长记录或某一
功率等级主导健康分布。

## 当前可复现的先导结果

截至 2026-08-20，三折 LOMO 的全量电流先导实验已经跑通：

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

这些结果说明课题具备继续投稿开发的价值，但仍属于已查看同一数据集后的探索性
证据，不是独立确认，也不构成录用保证。精确结果与失败项见
[`docs/baseline_findings.md`](docs/baseline_findings.md)。

## 为什么选择它作为 Paper 1

- 数据来自 1.0、1.5、3.0 kW 三台真实 PMSM，可做严格的整机留出验证；
- 研究对象同时覆盖跨电机分布偏移、少样本在线校准和可信报警；
- 主要贡献不是更换网络模块，而是目标域无故障标签、时间块防泄漏和风险校准；
- 即使深度模型不胜出，强信号基线与严谨评估仍能形成有价值的负结果或基准结论。

详细假设、划分、指标、止损条件见
[`docs/research_protocol.md`](docs/research_protocol.md)，论文结构见
[`paper/outline.md`](paper/outline.md)。

## 数据轨道

### 主轨：跨电机定子故障可信评估

- 数据 DOI：`10.17632/rgn5brrgrn.5`，CC BY 4.0；
- 三台电机、两类短路、每类健康状态加 7 个故障严重度；
- 三相电流 100 kHz，单轴振动 25.6 kHz，每段记录 120 s；
- 主实验为三轮 leave-one-motor-out，原始记录和连续时间块不可跨集合。

### 冻结外部验证：双三相 PMSM

- Zenodo `10.5281/zenodo.13889418`，CC BY 4.0；8 条健康负载记录和 48 条 ITSC
  记录，10 kHz、双三相电流；
- 健康审计确认记录是连续升速而非稳态；共同分析段在看故障前固定为 `[12,36) s`；
- 0 Nm 仅作 12 s 目标适配，10/20/30 Nm 产生 24 个系统校准块，
  5/15/25/35 Nm 产生 32 个完全不同文件的健康 FAR 测试块；
- 两个三相子系统分别计分，再取系统 maximum 并用同一系统分数校准；
- 48 条故障文件只有在协议、代码、环境与健康阈值形成带哈希提交后才允许一次性下载。

完整揭盲规则见 [`docs/external_validation_protocol.md`](docs/external_validation_protocol.md)。

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

外部故障揭盲不是普通 quickstart 步骤。只有满足预注册第 6 节的冻结条件后，才运行：

```powershell
& .\.venv\Scripts\python.exe scripts\download_external_pmsm_validation.py `
    --datasets dual_three_phase_fault_reveal
& .\.venv\Scripts\python.exe scripts\build_external_pmsm_health_features.py
& .\.venv\Scripts\python.exe scripts\run_external_pmsm_validation.py --require-faults
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
- `data/`、`results/`：本地数据和实验产物，不提交 Git

本项目的目标是形成可投稿、可复现、经强基线验证的 SCI 论文；任何研究设计都不能
保证期刊录用，因此预先定义成功门槛和失败后的改题条件。
