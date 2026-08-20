# Paper 1 SCI/SCIE 投稿策略

更新日期：2026-08-20

## 结论

当前工作可以按 **cross-dataset evaluation / negative-transfer case study** 继续推进
SCI/SCIE 投稿，但不能保证录用。它不适合再包装成“Log-Euclidean 新方法 SOTA”；真正
可审稿的价值是冻结外部揭盲、排名反转、防泄漏协议、报警漂移和负迁移证据。

投稿前仍需完成：文献缺口审计、英文全文与引用核查，以及把已完成的采样率敏感性、
特征漂移解释、主要表格和补充材料整理到目标期刊模板。

## 期刊梯度（以官网 2026-08-20 信息为准）

### A. 当前两数据集版本的首选

1. **Journal of Electrical Engineering & Technology (JEET)**

   - 推荐度：最高（无强制新增算法时）。
   - 原因：官网范围直接包含 permanent-magnet machines、motor drives、sensors and
     systems、signal processing；与 PMSM 故障跨数据集评估高度一致。
   - 官网列出 Science Citation Index Expanded (SCIE)，2025 JIF 2.0，出版模式为
     hybrid。
   - 风险：仍需把“新意”明确写成冻结评测方法和跨实验室失败机制，不能只是公开数据
     上比较算法。
   - 官网：<https://link.springer.com/journal/42835/aims-and-scope>
   - 索引与指标：<https://link.springer.com/journal/42835>

2. **IEEE Access**

   - 推荐度：最高（导师/项目可承担 APC 时）。
   - 原因：官网明确接收 applied engineering experiments 和 negative results，并强调
     可复现、技术正确和清晰结论；与本稿的诚实负结果高度匹配。
   - 官网列出 SCIE；当前 APC 为 2,160 美元，官网报告平均接收率约 20%，不能把“快”
     理解为容易录用。
   - 官网：<https://ieeeaccess.ieee.org/about/>
   - SCIE 信息：<https://ieeeaccess.ieee.org/about/bibliometrics/>
   - APC：<https://ieeeaccess.ieee.org/about/article-processing-charges/>

3. **Sensors — Fault Diagnosis & Sensors / Industrial Sensors**

   - 推荐度：现实备选。
   - 原因：期刊范围包含 sensor signal processing、AI-enabled sensors、sensor datasets，
     并设有 Fault Diagnosis & Sensors 专门栏目；官网强调完整实验细节与可复现性。
   - 官网列出 SCIE；开放获取 APC 需在提交前重新核对（当前官网专刊页面显示
     2,600 CHF）。
   - 风险：正文必须围绕电流测量链、报警可靠性和传感数据评估，不能只写通用 ML。
   - 官网：<https://www.mdpi.com/journal/sensors/about>
   - 栏目：<https://www.mdpi.com/journal/sensors/sections/fault>

4. **Electrical Engineering (Archiv für Elektrotechnik)**

   - 推荐度：稳妥备选。
   - 原因：官网范围包含 electrical machines and drives，并接收理论、计算和实验研究；
     官网列出 SCIE，2025 JIF 2.7，hybrid。
   - 风险：期刊整体更偏电力与电机工程，摘要和讨论需强化对电驱监测工程的直接意义。
   - 官网：<https://link.springer.com/journal/202/aims-and-scope>
   - 索引与指标：<https://link.springer.com/journal/202>

### B. 补强后可冲的期刊

1. **IET Electric Power Applications**

   - 官网明确包含 permanent-magnet machines、variable-speed drives，以及 electrical
     machines and drives 的 fault modelling, diagnosis, condition monitoring；并列出
     SCIE。
   - 当前稿件主题匹配，但“一个外部电机的失败 case study”技术增量可能不足。完成
     采样率分解、特征漂移机制和最好再加第三数据源后再冲更合理。
   - 官网：<https://ietresearch.onlinelibrary.wiley.com/hub/journal/17518679/homepage/productinformation.html>

2. **Measurement Science and Technology**

   - 官网包含 fault diagnosis、condition-based maintenance、signal processing、AI 与
     digital twins，但要求对 measurement science/technique 有实质进步，并讨论测量
     uncertainty、precision 或 accuracy。
   - 只有把论文提升为“跨域报警校准与测量不确定性评估方法”，而非普通故障分类，才
     值得投稿。
   - 官网：<https://publishingsupport.iopscience.iop.org/journals/measurement-science-and-technology/about-measurement-science-technology/>

### C. 当前不建议优先投

**Measurement** 的官网明确说明：只有很少 measurement-science 内容的 fault diagnosis
不在范围，普通 AI/ML 应用也可能直接 desk reject。除非新增清晰的测量学方法、误差/
不确定性框架和可复核校准贡献，否则不要因为期刊名字相近就优先投稿。

官网：<https://www.sciencedirect.com/journal/measurement>

## 推荐投稿顺序

### 无 APC 或优先电机领域认可

1. JEET
2. IET Electric Power Applications（仅在补强机制分析或第三数据源后）
3. Electrical Engineering

### 有 APC 且希望负结果定位最自然

1. IEEE Access
2. Sensors — Fault Diagnosis & Sensors
3. JEET

## 投稿前硬门槛

- 题目、摘要、结论均以 ranking reversal / negative transfer 为主线；
- 明确区分 exploratory KAIST 与 frozen external reveal；
- 11 个方法、五 seed、Holm 调整、early-horizon 和 per-block AUROC 可追溯；
- 把 48 fault records 正确写成一台电机的条件记录；
- 不用 record-any alarm 或高患病率 AUPRC 隐藏晚期漂移；
- 报告已完成的 100 kHz→10 kHz 抗混叠采样率敏感性（未恢复外部性能）；
- 报告哪些特征随转速漂移，且把贡献分析标成 post-reveal exploratory；
- 代码、环境、下载哈希、揭盲日志、主要派生结果与图形可复现；
- 投稿当天再次在期刊官网/Clarivate Master Journal List 核对索引和费用。

## Paper 2 与博士主线

Paper 2 不应在已揭盲外部数据上调出一个“更好方法”后直接投稿。正确路线是：

1. 只用健康数据学习 speed/load-conditioned reference 或 residual score；
2. 将 target-only MinCovDet 设为预声明主要比较器；
3. 固定健康 FAR、前四块检测、首次报警速度和拒判规则；
4. 在另一台完全未见电机/独立实验室数据上再次冻结确认；
5. 再把方法提升到数字孪生的工况条件化、物理约束和不确定性量化。

这条路线与长期方向 **科学机器学习 × 工业数字孪生 × 电驱动健康管理** 一致，也比
追逐拥挤的通用 LLM/具身赛道更容易形成连续论文、设备合作和产业资金接口。
