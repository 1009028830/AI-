---
name: engineering-toolbox
description: 使用统一工程工具箱执行代码静态分析和符号查询、PlantUML 绘图、Bruno 接口测试、CAN/UDS/串口/Modbus 分析、报文解析与聚焦测试。适用于 Windows 或 Linux 上相关工具执行任务，不用于普通架构问答或无关代码编辑。
---

# 统一工程工具箱

## 定位当前环境

读取当前主机的 `AGENT_TOOLBOX_HOME`，再读取该目录的 `ENVIRONMENT.json`，确认平台、安装结果、命令位置和验证状态。命令入口通常位于该目录的 `bin/`：Windows 包装脚本为 `.cmd`，Linux 为无扩展名命令；以报告中的实际记录和文件存在性为准。

环境变量缺失时，先查当前 PATH 上的 `agent-python` 或恢复结果记录来定位安装目录；不要推断成历史 Windows 路径，也不要因 PATH 尚未刷新直接重装。Windows、WSL、远程 Linux 和容器分别检查各自环境；清单列出、安装完成和本机验证通过是三种不同状态。

优先调用清单中的绝对入口，或已确认来源的 PATH 命令。PowerShell 调用带空格路径需使用 `&`，Bash 使用正确引用；不把 Bash 激活命令交给 PowerShell 执行。

## 按任务选择工具

| 能力 | 命令或服务 | 使用条件 |
| --- | --- | --- |
| C/C++ 静态分析与符号查询 | `cppcheck`、`clangd`、Serena MCP | 编译目标、宏、头文件路径与编译数据库匹配 |
| Python 类型与质量检查 | `pyright`、`agent-python -m ruff`、`agent-python -m pytest` | 遵循项目已有配置及测试入口 |
| 覆盖率与属性测试 | `gcovr`、`agent-python` 中的 Hypothesis | 覆盖率依赖兼容编译器插桩及测试数据；属性测试按任务需要 |
| 架构图、状态图、时序图 | `plantuml` | 使用恢复器生成的 Java 包装入口；中文加 `-charset UTF-8` |
| HTTP 接口测试 | `bru` | 在 Bruno 集合目录运行，保留默认安全脚本沙箱 |
| DBC/CAN/UDS/串口/Modbus | `cantools`、`agent-python` | Python 库及对应设备后端分别核实 |
| PCAP/PCAPNG 离线解析 | `tshark` | 使用该平台安装报告中的入口 |
| 文档格式转换与网页正文提取 | `pandoc`、`defuddle` | 使用现有文档或网页任务的实际输入和要求 |
| 本地调试、系统调用追踪、编译数据库捕获 | `gdb`、`strace`、`bear` | GDB 提供 Windows/Linux 入口；strace、Bear 按 Linux 条件安装，先检查目标架构和权限 |

不要为了任务用不到的能力运行整套工具或全量门禁。`agent-python` 是统一 Python 工具环境入口；项目有自己的虚拟环境或锁文件时，不把工具环境的包版本当作项目运行依赖。

## MCP 使用边界

- **Serena**：先看当前可调用工具和 `ENVIRONMENT.json` 的注册结果。配置存在但本轮未加载时重新打开客户端；不要仅因工具列表暂缺而重复安装。C/C++ 跨文件查询先检查 `compile_commands.json` 与目标编译配置，索引成功不等于构建或目标运行成功。
- **Context7**：用于当前依赖的文档查询；服务连接、联网和必要认证以本机实际状态为准。不要将远程工具可调用性写成离线恢复已完成的证明。
- **DBHub**：统一恢复默认连接本地演示只读库，只用于验证服务和查询流程。不得将演示数据用于业务结论，或未经任务授权改接生产数据库、扩大权限。

## 平台差异与验证

协议库支持跨平台，不代表硬件驱动可跨平台：Linux SocketCAN、Windows 厂商后端、USB 适配器及串口权限需分别核实。离线 DBC 编解码、虚拟 CAN 和串口回环可验证软件路径；真实 CAN 发送、寄存器写入、ECU 诊断服务及设备连接按任务授权执行。

Bruno 的具体版本、依赖覆盖和审计结果以本次恢复的清单与锁文件为准。只报告在当前平台实际执行过的请求、脚本、迭代与报表验证，不沿用另一台机器的结果。

Windows 上曾出现 Wireshark Falco 插件无法加载中文路径的问题。出现同类报错时先核对恢复器提供的英文安装入口和实际错误，不默认 Linux 同样受影响，也不下载来源不明的零散 DLL 或擅自删除插件。已有文件可用 `tshark -r 文件.pcapng` 分析；真实抓包需限定任务所需接口与范围。

安装验证、静态检查、仿真或回环不能冒充目标板、现场总线、真实执行器或生产验证。Linux 能力只有在目标 Linux 环境实际运行后才能记录为该平台验证通过。
