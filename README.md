# AI 工程规范、技能与跨平台恢复

面向架构设计、软件工程和软硬件协同开发，维护 AGENTS 规则、可复用技能、
工程模板、嵌入式规范索引，以及 Windows/Linux 环境恢复源码。

## 开始使用

- [跨平台规则与技能安装](agent-unified/README.md)：仅需 Python 3.11+，默认预览，确认后执行。
- [技能与 MCP 目录](agent-unified/docs/技能目录.md)：区分公开内置、第三方来源和客户端管理能力。
- [嵌入式规范索引](agent-unified/docs/嵌入式编程规范索引.md)：STM32、ESP32、Linux 应用、驱动及内核。
- [公开版 Excel 维护清单](agent-unified/docs/技能与MCP维护清单-公开版.xlsx)：可筛选、维护版本和记录更新。
- [原项目模板](demo/)与既有根规范保留，按项目需要采用。

公开版内置 **7 项技能**：AGENTS 工程体系、工程工具箱，以及 STM32、ESP-IDF、
Linux 应用、Linux 驱动/内核、软硬件联调五项专项技能。
个人环境中的其他技能仅登记来源；并非全部可以用本仓库许可证重新分发。

```bash
git clone git@github.com:1009028830/AI-.git
cd AI-
python agent-unified/install_skills.py
python agent-unified/install_skills.py --apply
```

源码安装不会下载芯片 SDK、安装驱动、连接业务数据库或操作真实设备。
完整工具环境的资源准备与恢复边界见子目录说明。

## 开源与发布边界

自编写的源码与文档采用 [MIT](LICENSE) 许可证。第三方软件、标准和插件仍遵循
各自许可证及服务条款，详见 [第三方来源说明](agent-unified/THIRD_PARTY_NOTICES.md)。
Git 仓库不包含登录凭据、个人账号配置、业务项目快照、虚拟环境和大型离线工具包。

技能结构检查、模拟测试和构建成功不等于目标硬件验收。公开版本的测试范围见
[发布验证说明](agent-unified/docs/公开发布说明.md)。
