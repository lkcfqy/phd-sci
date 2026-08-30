# 博士方向与课题路线图

更新日期：2026-08-21

## 最终建议方向

**Scientific Machine Learning × Industrial Digital Twins × Trustworthy Electric-Drive
Health Management**

中文：**面向跨电机与变工况域偏移的、工况条件化与不确定性校准的电驱动健康数字孪生**。

建议博士论文总题目：

> **Operating-Condition-Aware and Uncertainty-Calibrated Digital Twins for Reliable
> Electric-Drive Health Monitoring under Machine and Environment Shift**

这个方向保留 AI 算法创新，但把壁垒建立在电机机理、真实工业传感、跨设备验证、报警
风险和实验合作上，避免与通用 LLM/具身模型在纯算力与数据规模上正面竞争。

## 为什么它适合在昌原做

昌原的产业环境不是普通“AI 城市”，而是机械、汽车、防务、电气与智能制造密集的国家
产业集群。这使博士课题可以同时连接论文、设备、企业数据与政府项目。

- 昌原市 2025 年官方材料把昌原国家产业园区的制造 AI/AX 转型列为核心方向，并启动
  2026--2028 AI 综合计划：
  <https://www.changwon.go.kr/cwportal/10310/10429/10432.web?amode=view&idx=867522>
- 昌原市官方称，以本地制造数据为实证基础，2026 年起五年、总规模 1 万亿韩元的
  Physical AI 实证事业预计以昌原为中心推进；同时延续 2024--2026 年 227 亿韩元的
  超大规模制造 AI 服务开发与实证：
  <https://www.changwon.go.kr/cwportal/10310/10429/10432.web?amode=view&idx=869197>
- 韩国 MOTIE 的工业 AX 计划提出到 2030 年把企业 AI 利用率提高到 70%、制造现场 AI
  部署率提高到 40%，并在 2027 年前推进 300 个以上 anchor projects：
  <https://english.motie.go.kr/eng/article/EATCLdfa319ada/2056/view>
- 2026 年 2 月，韩国产业通商资源部在昌原大学启动产业园区 AX 分委会：官方材料称该
  网络覆盖 500 多家产学研机构，由昌原大学校长担任主席，并将通过本地大学开展需求
  驱动的 R&D 与人才培养；这为制造设备健康、共享工业 AI 模型和数字孪生提供了直接
  的项目接口：
  <https://english.motir.go.kr/eng/article/EATCLdfa319ada/2518/view>
- KERI 位于昌原，其公开材料包含 intelligent electricity、machine convergence 和
  Changwon Innotown 技术商业化接口：
  <https://www.keri.re.kr/upload/downfile/22brochure_en.pdf>

这些是“有资金与产业接口”的信号，不是个人项目获批保证。真正的竞争力来自尽早把导师、
KERI/企业合作、数据使用权和测试台资源绑定到具体课题。

## 四篇互不重叠的论文

### Paper 1：评测科学与负迁移

**When Healthy-Only Transfer Fails in PMSM Stator-Fault Detection:
A Leakage-Resistant Cross-Dataset Evaluation**

- 作用：建立数据审计、整机/文件隔离、冻结揭盲、报警校准和证据边界。
- 当前发现：同系列探索检出 95.71%，冻结外部仅 25.00%；target-only MinCovDet
  70.05%，显示排名反转与负迁移。
- 投稿定位：cross-dataset evaluation / negative-result case study。
- 当前状态：JEET 定制匿名正文、11 张图、补充材料、复现代码包、题名页/投稿信模板和
  逐页 QA 均已完成；只剩作者、单位、基金、署名审批及投稿门户确认。

### Paper 2：周期转矩代理的整曲线不确定性

建议题目：

> **Curvewise Conformal Risk Control for Periodic PMSM Torque Surrogates under
> Design-Distribution Shift**

核心科学问题：20 个几何参数到 120 点周期转矩波形的代理，能否为**整条曲线**给出校准
预测带，并在设计分布改变或几何支持不足时诚实扩宽/拒判？

最低设计：

1. 使用公开的 23,250 组 PMSM 几何—转矩仿真，并严格分离拟合、共形校准和评测；
2. 复现 Fourier 降维的强响应面基线，不把 DFT 包装成新贡献；
3. 比较全局整曲线共形带、几何密度缩放带和支持域拒判；
4. 报告 90%/95% 整曲线覆盖、带宽、稀疏区域分层覆盖和转矩纹波误差；
5. 明确当前仅是一台二维四分之一对称 PMSM 仿真，不声称硬件/跨拓扑有效。

当前状态：完整英文稿、五张投稿图、补充材料、证据验证器、匿名 DOCX/PDF 和哈希复现
包均已完成；只剩作者信息、仓库 DOI 和目标期刊模板。

### Paper 3：健康报警校准的冻结跨机器验证

建议题目：

> **When Healthy-Only Alarm Calibration Does Not Transport Across Permanent-Magnet
> Synchronous Machines: A Protocol-Frozen External Validation**

核心科学问题：在一台双三相 PMSM 上选出的健康样本报警规则，其报警工作点能否在冻结
协议后迁移到另一实验室采集的 PMSG？

- 开发台架：健康 FAR 1/48，记录宏平均故障块检出 82.29%；
- 冻结确认：PMSG 预故障 session 误报 71/216，0.4 s 内检出 156/216，联合门槛失败；
- 七种冻结方法均超过 5% PMSG session FAR，保留完整负结果；
- session anchor 将误报降至 6.48%--8.33%，但属于 post-reveal 机制分析且仍未通过原门槛；
- 当前状态：完整英文稿、五图、补充材料、证据验证、匿名 DOCX/PDF 和 120 文件复现包
  已完成；仅余作者信息和目标期刊模板。

这篇的贡献是可审计的报警校准迁移失败与实验设计教训，不声称两台机器代表总体，也不
把 post-reveal 修复包装为独立确认。

### Paper 4：跨电机在线电热数字孪生

建议题目：

> **Do Electrothermal Models Transport Across PMSMs? A Protocol-Frozen Benchmark of
> Source Priors, Five-Minute Calibration, and Support-Aware Uncertainty**

以 69 个 profile 的 52-kW 公共 PMSM 温度数据和 16 个 profile 的第二套 IPMSM 数据为
基础，冻结比较八种 source-only、target-only 与五分钟校准方法。结果保留了不利证据：
源域最优热网络的跨机 RMSE 恶化 13.12 倍；source-prior 方法外部 RMSE 为 13.61 °C，
不如 target-only 的 6.02 °C 和边界保持的 6.17 °C；其 15/16 外部联合覆盖需要
106.07 °C 的平均半带宽。支持域规则接受 6/16 profiles，但 62.5% 拒判率使该结果不能
被包装成普适迁移成功。

当前状态：完整英文稿、五张投稿图、七页补充材料、证据验证器、匿名 DOCX/PDF 和
79 文件哈希复现包均已完成；只剩作者信息、仓库 DOI 和目标期刊模板。

## 当前四篇完成口径

四篇均已达到“技术投稿包完成”：有完整英文正文、冻结结果、投稿图表和可复现证据。
Paper 1 另有 JEET 定制匿名稿、补充材料与上传清单；Paper 2--4 为期刊中性投稿包。
“完成”表示可以进入导师审阅和期刊格式化，不表示已投稿、已送审或必然录用。

## 入学后 12 个月的执行顺序

1. **0--1 个月：**与导师确定作者、目标期刊和投稿顺序；完成 Paper 1 作者字段并首投。
2. **1--3 个月：**根据期刊范围依次格式化 Paper 2--4，公开代码与数据说明并取得 DOI；
   避免四篇同时占用同一作者团队的修改窗口。
3. **0--4 个月并行：**与导师/KERI/企业确定至少一台可重复采集的 PMSM/伺服测试台，
   争取多 speed × load × session 的健康矩阵。
4. **4--8 个月：**用独立日期、独立装配或独立电机采集确认数据，优先补强 Paper 3 和
   Paper 4 暴露出的跨设备校准失败机制。
5. **8--12 个月：**依据审稿意见完成针对性复验，并把新增硬件证据发展为博士阶段下一篇
   正向方法论文，而不是回头修改已冻结结果以追求好看的数字。

## 入学后优先争取的资源

- 可控转速/负载的 PMSM、伺服或泵驱测试台；
- 电流、电压、速度、转矩、绕组/机壳温度同步采集；
- 至少 3 个独立日期/装配后的健康 sessions，而不是一条长记录切碎；
- 安全可控的匝间故障仿真或硬件故障注入；
- 电机参数、控制器设定和传感器传递函数；
- KERI/企业联合导师或共同数据管理协议；
- 项目开始前明确论文发表、数据公开、专利与作者排序。

## 方向止损线

- 如果一年内拿不到任何新实验/企业数据：把 Paper 3 限定为三公开数据源的条件化评测，
  不声称工业部署；同时优先转向可公开仿真的热数字孪生。
- 如果只能拿单机单工况：不做“跨机器泛化”标题，改做 session drift 和 calibration。
- 如果深度模型只比 MinCovDet/GP 高少量百分点：保留强基线，贡献转为风险、拒判、效率
  或物理一致性。
- 任何方法在开发数据上改完后，都必须留一个新、不可回看的确认数据源。

## 最终能力画像

毕业时应形成的不是“会调某个热门模型”，而是：能审计工业时序数据、构建物理/统计
基线、设计防泄漏实验、开发条件化数字孪生、量化不确定性，并在真实设备上完成冻结
验证。这类能力同时对应高校论文、政府制造 AX 项目和电驱/装备企业研发岗位。
