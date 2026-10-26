# AI 工程规范与跨平台恢复仓库

## 规则与范围

- 适用于本仓库；用户当前明确要求优先，更近目录规则只约束对应子树。
- 通用工程、跨平台、安全、设备边界和正式文档要求以 [统一规则](agent-unified/config/AGENTS.md) 为准，按任务读取相关部分。
- 本文件替代旧的全任务方案审核流程。只读直接分析，小型可逆修改简短说明后实施；复杂变化明确范围、验收与验证，已有授权持续有效。
- 阅读任务必要的代码和上下文；不因新对话或交付阶段重复扫描仓库。

## 仓库地图

- [恢复与安装入口](agent-unified/README.md)：平台支持、安装参数和边界。
- `agent-unified/config/AGENTS.md`：Windows/Linux 共用全局规则源。
- `agent-unified/payload/skills/`：公开内置技能；工程模板在 `agents-engineering-skill/assets/agents-project-template/`。
- `agent-unified/install_skills.py`、`restore.py`：安装与恢复入口。
- `agent-unified/tests/`：安装、恢复等行为测试。
- `agent-unified/payload/agents/`：按需调用的工程角色；[协作与安装说明](agent-unified/docs/多智能体协作.md)。
- [技能目录](agent-unified/docs/技能目录.md) 与 [第三方声明](agent-unified/THIRD_PARTY_NOTICES.md)：来源与分发边界。
- [统一代码架构与编码规范](统一代码架构与编码规范.md)：三层架构、硬件隔离与注释约定的入口；正文随工程技能恢复，按需读取。
- [Git/Gitee 协作规则](agent-unified/payload/skills/agents-engineering-skill/assets/agents-project-template/references/git-collaboration.md)：提交、分支、版本与回退要求；个人工作默认提交/推送，协作或明确要求时创建 PR，远端保护设置需单独核实。
- 新项目只采用工程技能内的现行模板；旧 demo 和早期通用规范已停用，保留的历史正文不再作为执行流程，历史版本也可通过 Git 查询。

## 修改与验证

- 修改前检查 Git 状态和目标路径规则，保留用户已有改动；不改动无关历史样例。
- 纯文案核对差异、链接和格式；规则/技能变化检查结构、触发边界、冲突和相关场景，不默认执行全部安装/恢复测试。
- 常规代码先编译/基础检查，再验证相关功能，最后集中审查本次改动；审查修复后仅复核受影响差异，执行前安全审查仍保留。
- 安装器、恢复器或构建/测试行为变化运行相关回归；全量检查只由实际影响、明确门禁、发布条件或用户要求触发。
- 同一任务内相关文件、依赖、配置与环境未变时复用可追溯证据；检查通过后停止，交付只汇总，提交前核对差异与敏感内容。
- 重复验证优先使用 `python agent-unified/verify.py` 预览，按需增加 `--run --only <任务ID>`；用法与边界见 [增量验证说明](agent-unified/docs/增量验证说明.md)。
- 工程技能的结构验证从仓库根执行以下命令。总门禁已包含的子检查不再单独重跑。

```bash
python agent-unified/payload/skills/agents-engineering-skill/scripts/validate_agents_project.py agent-unified/payload/skills/agents-engineering-skill --template
python agent-unified/payload/skills/agents-engineering-skill/scripts/validate_agents_project.py agent-unified/payload/skills/agents-engineering-skill/assets/agents-project-template --template
```

## 工程与公开边界

- 保留分层、职责单一与可观测性要求；后端项目不强制增加 UI，UI 不堆积通信和业务逻辑。
- 普通 C/C++ 公共接口与关键模块遵循已有 Doxygen 风格，内核代码使用 kernel-doc；说明契约与维护要点，不为补齐注释重写无关代码。
- 不提交凭据、账号配置、业务数据、私人项目快照、虚拟环境或大型离线工具包。
- 第三方内容遵循原许可证，标准索引不能当作已获授权的完整标准正文。
- 本地结构检查不等于 Linux 实机、板卡、内核或真实外设验收；驱动、协议及 BMS 安全相关变化保留对应风险验证。
- 发布、推送及设备动作按明确授权执行；交付只报告实际结果及影响验收的限制。
