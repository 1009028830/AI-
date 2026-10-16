# AGENTS.md

本文件是 `{{PROJECT_NAME}}` 的 Agent 入口地图，不是完整工程手册。保持短小、稳定、可执行：详细流程在 `skills/`，项目事实在 `docs/`，模板与完成标准在 `references/`。

## 作用域与优先级

- 本文件适用于所在目录及全部子目录。
- 编辑任何文件前，先查找从仓库根到目标文件路径上的 `AGENTS.md` / `AGENTS.override.md`；更近的同类规则优先。
- 用户本轮明确指令高于仓库规则；安全、权限、真实性与不回退用户改动的约束始终有效。
- 子目录只有在命令、技术栈、风险或交付规则确实不同的情况下才新增 AGENTS，不复制根文件。

## 项目定位

{{PROJECT_OVERVIEW}}

稳定事实与文档入口维护在 [`docs/agent/knowledge-map.md`](docs/agent/knowledge-map.md)。如果代码、配置和文档互相冲突，以实际运行行为和已验证测试为准，并记录冲突。

## 每次开始前

1. 确认仓库根目录并执行 `git status --short`，区分用户已有改动。
2. 定位目标文件适用的最近 AGENTS 规则。
3. 按任务分级，只加载 [`docs/agent/knowledge-map.md`](docs/agent/knowledge-map.md) 中与任务相关的资料。
4. 选择对应 skill；不确定时读 `skills/using-dev-workflows/SKILL.md`。
5. 修改前写明目标、范围、关键假设和验证方法。不要把推断写成事实。

## 任务分级与工作流

| 级别 | 典型任务 | 必需流程 |
|---|---|---|
| L0 只读 | 阅读、搜索、解释、审查、状态检查 | 直接分析；不创建方案或修改文件 |
| L1 小型可逆 | 1–2 个文件的局部修正，不改接口/数据/依赖/安全边界 | 简短 micro-plan -> 修改 -> 聚焦验证 |
| L2 标准改动 | 新功能、Bug 修复、重构、配置/脚本/大范围文档修改 | `project-analysis` -> `plan-before-code` -> 用户确认 -> `minimal-implementation` |
| L3 高风险 | 协议/API、数据迁移、安全、权限、设备控制、生产部署、破坏性操作 | L2 + 兼容/安全分析 + 回退方案 + 目标环境验证 |

用户已明确要求实现 L1 任务时，该请求本身就是实施授权，不重复索要同一层确认。L2/L3 在持久化方案获明确确认后实施；如果范围或风险发生实质变化，更新方案并重新确认。

## Skill 路由

| 任务意图 | 使用 |
|---|---|
| 结构、依赖、入口、影响范围分析 | `project-analysis` |
| 控制上下文、定位权威资料 | `context-loading` |
| 非稳定框架/API/标准需要官方依据 | `source-verification` |
| L2/L3 方案与用户审批 | `plan-before-code` |
| 按确认方案小步实现 | `minimal-implementation` |
| 编译、运行、通信、环境或数据异常 | `problem-tracking` |
| 重复使用的自动化 | `reuse-scripts` |
| 代码/配置/规则行为变化的风险匹配验证，或明确要求的评审 | `verification-and-review` |
| 多模块、高风险或正式交付 | `delivery-checklist` |

Skill 是按需工作流，不一次性全部加载。只读取被触发的 `skills/<name>/SKILL.md` 及其直接引用资料。

## 项目硬约束

- 不伪造命令、测试、硬件、远端服务或生产环境结果。
- 不回退、不整理、不覆盖与当前任务无关的用户改动。
- 不做方案外功能和无关重构；优先复用现有模式，不引入未确认依赖。
- 外部输入默认不可信；涉及协议、配置、文件、网络和设备数据时验证长度、类型、范围与失败路径。
- 不经用户明确要求，不提交、打标签、推送、部署或执行不可恢复操作。
- 真实问题按 `problem-tracking` 记录到 `docs/development_memory.md`；不要把普通工作日志写成长期记忆。

## 验证

项目级完成标准见 [`references/definition-of-done.md`](references/definition-of-done.md)。

- 普通问答不主动运行测试或构建；小修改采用聚焦检查，不强制验证矩阵或五轴审查。
- 按实际变化选最小相关检查，只有影响范围、门禁、发布或用户要求需要时扩大回归。
- 同一任务内相关输入和环境未变时复用可追溯结果；后续只重跑受影响项，总入口包含的检查不单独重跑。
- 必要检查通过且无新风险证据后停止；交付或仅 Git 提交不重新启动验证，仍满足明确门禁。
- 交付时记录命令/操作、预期、实际、环境与未覆盖风险。
- 本地/沙箱可验证：静态检查、单元测试、纯算法、配置解析、无外设冒烟。
- 不可冒充目标环境：真实 CAN/串口/控制器、生产性能、远端服务状态、现场数据正确性。
- 修改 AGENTS、skills、references 或知识地图后，运行项目的 AGENTS 验证命令。

## 常用命令

在仓库根目录执行；如项目实际命令变化，同步更新本节和知识地图。

```bash
# 工作区与搜索
git status --short
rg --files
rg "keyword"

# 构建
{{BUILD_COMMAND}}

# 测试
{{TEST_COMMAND}}

# 运行 / 冒烟
{{RUN_COMMAND}}

# AGENTS 系统校验（Linux/macOS；若环境只提供 python 命令则等价替换）
python3 scripts/validate_agents_project.py .
```

## 维护规则

- 根 AGENTS 目标约 100 行，只保留每次都需要的稳定规则与入口。
- 新事实写入知识地图指向的权威文档，不在多处复制。
- 可机械检查的规则优先写成 lint、测试或脚本。
- 同类失败反复出现时，先修验证器/工具/文档，再考虑增加一条简短规则。
- 每次修改 AGENTS 系统后检查链接、命令、skill 触发描述和过期内容。
