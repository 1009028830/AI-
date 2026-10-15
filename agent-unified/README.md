# Agent 跨平台规则与恢复源码

本目录是去除个人配置、项目专属快照和第三方二进制后的公开源码版。
Windows/Linux 共用规则和技能，工具程序及驱动按平台准备。

## 立即安装规则和技能

需要 Python 3.11+，无需其他 Python 依赖。在仓库根目录执行：

```bash
# 预览：不修改目标目录
python agent-unified/install_skills.py

# 安装 7 项内置技能，保留已有全局 AGENTS
python agent-unified/install_skills.py --apply

# 同时安装统一全局规则；已有不同文件默认报冲突
python agent-unified/install_skills.py --apply --with-rules

# 指定目标目录；已有明确冲突时审阅后再增加 --replace-existing
python agent-unified/install_skills.py --codex-home /path/to/.codex --apply
```

默认目标取 `CODEX_HOME`，未设置时使用用户主目录下 `.codex`。
Windows 可使用 `py -3`，Linux 可使用 `python3`。
安装器预检查全部冲突、原子写入并生成事务备份；不写 MCP 配置、账号或 PATH。
需要回退时，使用安装时输出的备份目录：

```bash
python agent-unified/install_skills.py --rollback /path/to/backup
```

回退检测到安装后的用户修改会停止，不强行覆盖。安装完成后重新打开客户端确认发现。

## 内置技能

| 技能 | 场景 |
| --- | --- |
| agents-engineering-skill | 初始化、审计和升级项目 AGENTS、模板及工作流 |
| engineering-toolbox | 调用已有静态分析、绘图、接口和协议工具 |
| stm32-firmware | STM32 Cortex-M 裸机/RTOS、BSP、中断和 DMA |
| esp-idf-firmware | ESP32 家族 ESP-IDF 应用、组件与运行诊断 |
| linux-application-engineering | Linux 用户态应用、交叉编译、并发与 I/O |
| linux-driver-kernel | Linux 驱动、设备树、内核并发和接口兼容 |
| hardware-software-validation | 设备协议核对、受控联调和验收证据 |

例如：“使用 `$linux-driver-kernel` 评审当前 BSP 驱动的退出路径”。
规则按任务加载，不要求每次读取全部技能。资料入口见[规范索引](docs/嵌入式编程规范索引.md)。

## 完整工具环境恢复

`restore.py`、`restore.ps1`、`restore.sh`、`engine/` 以及 `scripts/prepare_*.py`
保留完整工具环境的恢复和资源准备实现。`config/`、`locks/` 保存固定版本、来源和校验信息。

**Git 克隆不含 `assets/`，不能直接等同于完整离线包。** 完整恢复入口需要先补齐
拥有使用权限的、与清单哈希一致的资源和 wheelhouse，再运行
`python agent-unified/scripts/build_release.py` 生成本地清单。
维护者准备脚本中部分 Windows 原生工具仍依赖已有的本地上游缓存，当前并非一条命令
从全新机器重新构建所有二进制的流水线；无资源时使用上面的规则/技能安装入口。

资源齐备后运行 `restore.ps1` 或 `bash restore.sh` 预览，显式增加 `-Apply` 或 `--apply`
才执行工具恢复。支持范围为 Windows x64、GNU/Linux x64/ARM64；GNU/Linux 资源的
glibc 和发行版要求以固定资源及恢复器为准。账号登录、MCP 密钥和设备权限单独配置。
公开版不带私有项目快照，不能使用 `--project-dir` 恢复这些资料。

不要把个人完整离线包直接上传到公共 Release。重新发布第三方二进制前应核对其许可证、
声明、源代码提供义务及包内信息；本仓库未发布这类资产。

## 验证

```bash
python -m pip install tomlkit==0.15.1 PyYAML==6.0.2
python -B -m unittest discover -s agent-unified/tests -v
python -B -m unittest discover -s agent-unified/payload/skills/agents-engineering-skill/tests -v
python agent-unified/payload/skills/agents-engineering-skill/scripts/validate_agents_project.py agent-unified/payload/skills/agents-engineering-skill/assets/agents-project-template --template
```

测试依赖仅用于完整恢复器测试；规则/技能安装入口使用标准库。
测试在临时目录和合成配置上执行，不操作真实设备或生产数据库。
