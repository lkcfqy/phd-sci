# 博士方向与课题路线图

更新日期：2026-08-20

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

## 三个递进课题

### Paper 1：评测科学与负迁移

**When Healthy-Only Transfer Fails: A Leakage-Resistant Cross-Dataset Evaluation of
PMSM Stator-Fault Detectors under Compound Speed, Load, and Topology Shift**

- 作用：建立数据审计、整机/文件隔离、冻结揭盲、报警校准和证据边界。
- 当前发现：同系列探索检出 95.71%，冻结外部仅 25.00%；target-only MinCovDet
  70.05%，显示排名反转与负迁移。
- 投稿定位：cross-dataset evaluation / negative-result case study。

### Paper 2：工况条件化的健康样本异常检测

建议题目：

> **Healthy-Only Speed- and Load-Conditioned Fault Detection with Calibrated
> Abstention for Unseen PMSM Drives**

核心科学问题：只用目标健康数据和转速/负载等工况量，能否把“故障残差”与“正常工况
漂移”分离，并在不确定工况主动拒判？

最低设计：

1. 学习 (p(x\mid \omega,\tau,\theta_m,\text{healthy})) 或条件残差，而不是一个全局
   健康分布；
2. 比较 target MinCovDet、条件高斯过程、条件 normalizing flow、Mixture-of-Experts、
   physics-guided residual 等；
3. 用健康数据做工况覆盖/拒判，故障标签不参与阈值和超参数；
4. 预声明前四块检测、首次报警速度、健康 session FAR 与 non-inferiority margin；
5. 在一套完全未见电机/实验室数据上冻结确认。

这是博士阶段最关键的方法论文，也最容易对接电驱、机器人、机床、泵压缩机和智能工厂
项目。

### Paper 3：物理约束的多物理场数字孪生

建议题目：

> **Multi-Fidelity Physics-Informed Operator Learning for Online Thermal and
> Electromagnetic Health Digital Twins of Electric Drives**

核心设计：

- FEA/热网络/控制器仿真提供低成本多工况源数据；
- 少量真实传感完成跨电机校准；
- 预测温度、转矩纹波或故障残差，同时输出 epistemic/aleatoric uncertainty；
- 以参数辨识、GP/状态空间模型、LPTN 等强物理基线对照；
- 最终与 Paper 2 的异常报警和拒判层连接。

这一步才真正形成“数字孪生”，不能仅把一个 LSTM 温度预测器改名为 twin。

### 可选 Paper 4：边缘/联邦部署

只有拿到多企业/多设备数据后再做：隐私保护联邦校准、持续学习、边缘推理、模型漂移
监控或主动试验设计。不要在没有真实分布式数据时先堆联邦算法。

## 博士前 12 个月的执行顺序

1. **0--3 个月：**完成 Paper 1 文献、采样率/特征机制、补充材料和首投。
2. **0--4 个月并行：**与导师/KERI/企业确定至少一台可重复采集的 PMSM/伺服测试台，
   争取多 speed × load × session 的健康矩阵。
3. **3--6 个月：**预注册 Paper 2 的数据划分、主要比较器、FAR/早检/拒判指标；保持一台
   电机或一个实验室完全封存。
4. **6--10 个月：**开发工况条件化健康模型，只在开发电机调试；做跨 session 和跨电机
   ablation。
5. **10--12 个月：**一次性揭盲确认、写 Paper 2；同时建立热/电磁多保真仿真轨道。

## 入学后优先争取的资源

- 可控转速/负载的 PMSM、伺服或泵驱测试台；
- 电流、电压、速度、转矩、绕组/机壳温度同步采集；
- 至少 3 个独立日期/装配后的健康 sessions，而不是一条长记录切碎；
- 安全可控的匝间故障仿真或硬件故障注入；
- 电机参数、控制器设定和传感器传递函数；
- KERI/企业联合导师或共同数据管理协议；
- 项目开始前明确论文发表、数据公开、专利与作者排序。

## 方向止损线

- 如果一年内拿不到任何新实验/企业数据：把 Paper 2 限定为三公开数据源的条件化评测，
  不声称工业部署；同时优先转向可公开仿真的热数字孪生。
- 如果只能拿单机单工况：不做“跨机器泛化”标题，改做 session drift 和 calibration。
- 如果深度模型只比 MinCovDet/GP 高少量百分点：保留强基线，贡献转为风险、拒判、效率
  或物理一致性。
- 任何方法在开发数据上改完后，都必须留一个新、不可回看的确认数据源。

## 最终能力画像

毕业时应形成的不是“会调某个热门模型”，而是：能审计工业时序数据、构建物理/统计
基线、设计防泄漏实验、开发条件化数字孪生、量化不确定性，并在真实设备上完成冻结
验证。这类能力同时对应高校论文、政府制造 AX 项目和电驱/装备企业研发岗位。
