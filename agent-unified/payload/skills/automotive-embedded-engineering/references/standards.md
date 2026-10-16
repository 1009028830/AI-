# 车载嵌入式规范与来源

查询日期：2026-10-16。共 20 项标准、法规、方法或器件资料入口。版次是查询快照，不是自动升级指令。机构为发布者或官方信息平台。

本库只分发原创检查项和题录链接；未附付费或受限标准正文。公开可浏览不等于许可再分发。ISO/IEC/SAE/MISRA 正文按授权获取，AUTOSAR 按其使用与知识产权条款采用。

下表“用途”是工程选用建议，“核实深度”明确本次读取范围；没有正文证据时不生成精确条款号、合规结论或试验定值。生产项目须核对合同、目标市场、车型范围、修改单和过渡期。

| 资料与官方来源 | 机构 | 查询到的版次/状态 | 工程用途 | 核实深度/获取限制 |
| --- | --- | --- | --- | --- |
| [MISRA C](https://misra.org.uk/app/uploads/2025/03/MISRA-C-2025-ADD6.pdf) | MISRA Consortium | C:2025 | C 规则集、静态分析与偏离管理 | 公开 Addendum 6 确认版次；主标准需授权获取，未读取全文 |
| [MISRA C++](https://misra.org.uk/product/misra-cpp2023/) | MISRA Consortium | C++:2023；本次主站访问失败 | C++17 规则集选型；实施前核对正版正文与勘误 | 官方论坛检索记录可见该版；产品页 520，未确认最新勘误，未读取正文 |
| [AUTOSAR Classic Platform](https://www.autosar.org/standards/classic-platform) | AUTOSAR | R25-11 | 应用/RTE/BSW；按需查 OS、COM、DCM、DEM、NvM、WdgM、E2E、SecOC | 本次已读取平台目录；后续重复访问失败。规范按网站使用条款获取，不等于可自由再分发或商用授权 |
| [ISO 26262-6 道路车辆功能安全：软件层开发](https://www.iso.org/standard/68388.html) | ISO | 2018；2024 复审确认；后续版在研 | 软件安全生命周期；配合系列其他适用部分和项目安全计划 | 官方题录/摘要；付费正文未读取 |
| [GB/T 34590.6 道路车辆功能安全：软件层面产品开发](https://std.samr.gov.cn/gb/search/gbDetailedCNF?id=F159DFC2A87647EFE05397BE0A0AF334) | SAMR/SAC | 2022；实施 2023-07-01 | 国内项目软件功能安全基线；与合同指定系列配套 | 官方题录索引；未逐条读取正文，不推断与 ISO 版次完全相同 |
| [ISO/SAE 21434 道路车辆网络安全工程](https://www.iso.org/standard/70918.html) | ISO/SAE | 2021 | TARA、生命周期网络安全和证据组织 | 官方题录/摘要；付费正文未读取 |
| [Automotive SPICE PAM](https://vda-qmc.de/automotive-spice/automotive-spice-veroeffentlichungen/) | VDA QMC | 4.1 / 2026-08；4.0 中文为旧版翻译 | 需求、开发、验证、配置与质量过程评估 | 官方发布目录；4.1 英文与 4.0 中文不可混称同版；PAM 与付费 Guidelines 区分 |
| [Automotive SPICE for Cybersecurity](https://vda-qmc.de/automotive-spice/automotive-spice-veroeffentlichungen/) | VDA QMC | 2.0 / 2025-03 | 网络安全过程扩展；按项目评估范围使用 | 官方发布目录；未实施过程评估 |
| [ISO 11898-1 CAN 数据链路与物理编码子层](https://www.iso.org/standard/86384.html) | ISO | 2024 | CAN/CAN FD 等基础；能力由控制器及网络实际配置决定 | 官方题录/摘要；付费正文未读取 |
| [ISO 15765-2 DoCAN 传输与网络层](https://www.iso.org/standard/84211.html) | ISO | 2024；已发布、在修订 | ISO-TP 分段、流控和超时的项目基线 | 官方题录/摘要；在研 CD 不当成已发布替代版 |
| [ISO 14229-1 UDS 应用层](https://www.iso.org/standard/87962.html) | ISO | 2026-06，第 4 版；2020 版已撤销 | 诊断服务；OEM 合同旧版需做差异与迁移评估 | 官方题录/摘要及版次关系；付费正文未读取 |
| [ISO 13400-2 DoIP 传输与网络层](https://www.iso.org/standard/13400-2) | ISO | 2025；已发布、在修订 | 以太网诊断、路由与连接管理 | 官方题录/摘要；不把可选安全功能说成所有项目自动具备 |
| [ISO 17987-1 LIN 总体信息](https://www.iso.org/standard/85125.html?browse=tc) | ISO | 2025 | LIN 系列选型入口；实现另核对协议/物理层分册 | 官方题录索引；付费正文未读取 |
| [SAE J1939-22 CAN FD 数据链路](https://saemobilus.sae.org/standards/j1939-22_202107-fd-data-link-layer) | SAE International | 202209；202107 为历史版 | 商用车/工程机械 J1939 FD；配合 OEM 的 PGN/SPN 数据 | 官方历史页修订面板确认 202209；新版直链本次超时，正文未读取 |
| [GB 44495 汽车整车信息安全技术要求](https://std.samr.gov.cn/gb/search/gbDetailed?id=208DEC46F6B347EEE06397BE0A0AA4A0) | SAMR/SAC | 2024；实施 2026-01-01 | 中国市场适用车型的信息安全要求 | 官方题录索引；定版前核对修改单及车型过渡条款，未做条款合规判定 |
| [GB 44496 汽车软件升级通用技术要求](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=8BC0D8B44DD4E71F9557BADE5175565A) | SAMR/SAC | 2024；实施 2026-01-01；题录列第 1 号修改单 | 升级管理、车辆升级与证据 | 官方题录；修改单正文及实施细则须另核对，未逐条读取 |
| [UN R155 网络安全与 CSMS](https://unece.org/media/transport/Vehicle-Regulations/press/352397) | UNECE | 法规系列；按市场核对适用修订系列/增补 | 出口车型网络安全管理与型式批准适用性 | 官方法规介绍；不是最新整合文本，不作统一实施日期结论 |
| [UN R156 软件更新与 SUMS](https://unece.org/transport/documents/2021/03/standards/un-regulation-no-156-software-update-and-software-update) | UNECE | 法规系列；按市场核对适用修订系列/增补 | 车辆升级管理与型式批准适用性 | 官方原始发布入口；采用前复核 UNECE 状态表及修订，不代表已核验全部增补 |
| [CISPR 25 车载接收机无线电骚扰保护](https://webstore.iec.ch/en/publication/64645) | IEC/CISPR | 2021，第 5 版 | EMC 发射与接收机保护试验选型；不覆盖全部抗扰度 | 官方题录/摘要；付费正文未读取 |
| [ISO 7637-2 供电线电瞬态传导](https://www.iso.org/standard/50925.html?browse=tc) | ISO | 2011；本次检得版次，采用前复核状态 | 电源瞬态试验与软件功能状态关联 | 官方题录索引；未读取全文，不给出试验脉冲定值 |

维护数据见 [sources.json](sources.json)。后续核对更新这里的题录与日期，再评估项目差异；保留项目已批准基线。

按需扩展：AUTOSAR Adaptive/Foundation、ISO 16750 环境、ISO 11452 抗扰度、ISO 10605 ESD、UN R10、IATF 16949、ISO 21448/SOTIF、ISO 21448 相关感知与预期功能安全、IEEE 车载以太网/TSN、ASAM XCP/A2L/ODX。以上未在本次核实具体版次；仅在实际 ECU 职责触发时补齐官方资料，不宣称已完整收录。
