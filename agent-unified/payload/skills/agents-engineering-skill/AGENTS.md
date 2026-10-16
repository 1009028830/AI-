# AGENTS.md

本文件只约束 `agents-engineering-master` Skill 仓库本身。生成到目标项目的规则以 `assets/agents-project-template/AGENTS.md` 为准，不要把本文件复制给使用者。

## 作用域与优先级

- 适用于本目录全部文件。
- 用户本轮明确指令优先；安全、权限、真实性和不回退已有改动的约束始终有效。
- 修改生成模板时，同时考虑初始化器、验证器、测试和 `SKILL.md` 的说明是否需要同步。

## 仓库地图

| 路径 | 职责 |
|---|---|
| `SKILL.md` | Skill 的触发条件与核心工作流 |
| `agents/openai.yaml` | UI 展示名称、简介和默认调用提示 |
| `assets/agents-project-template/` | 安装到目标项目的唯一模板源 |
| `scripts/init_agents_project.py` | 安全初始化；默认不覆盖已有文件 |
| `scripts/validate_agents_project.py` | 确定性结构、编码、链接与 frontmatter 校验 |
| `scripts/check_project.py` | Linux、macOS、Windows 共用的零依赖质量门禁 |
| `scripts/check-project.sh` / `.cmd` | 可选的 POSIX shell 与 Windows 轻量入口 |
| `references/` | 审计与既有仓库采用原则，按需加载 |
| `evals/evals.json` | 真实触发/行为测试场景 |
| `tests/` | 初始化器和验证器回归测试 |

## 每次开始前

1. 执行 `git status --short`（如果目录已作为独立仓库初始化）并识别用户改动。
2. 阅读 `SKILL.md` 和本次要改的脚本/模板/测试。
3. 若是既有仓库采用逻辑，读取 `references/adoption-guide.md`；若是规则设计，读取 `references/design-principles.md`。
4. 写明目标、修改范围、验证方法和不修改项。

## 任务分级与工作流

- L0 只读审计：不改文件，给证据和差距。
- L1 局部文案/测试修正：micro-plan 后直接实现并运行聚焦检查。
- L2 模板或工作流变化：按已授权方案修改，检查结构、链接与相关行为场景；初始化器、验证器及其契约变化再运行受影响回归。
- L3 发布、覆盖目标项目或外部仓库写入：必须获得精确授权并准备回退。

## 修改规则

- 模板内容只在 `assets/agents-project-template/` 维护；初始化器负责复制，不在两处手工保留正文。
- 根 `SKILL.md` 保持精简，详细采用策略放在直接引用的 `references/`。
- 新增模板 Skill 时，目录名必须与 frontmatter `name` 一致，description 同时说明能力与触发条件。
- 模板根 AGENTS 目标约 100 行，作为地图而不是领域百科。
- 验证规则能机械化时写入脚本与测试，不新增重复的提示文本。
- 初始化器默认不得覆盖已有文件；改变覆盖语义属于高风险兼容变化。
- 核心自动化只使用 Python 标准库，默认不得要求 PowerShell、Bash 或系统级安装。
- 平台包装脚本必须保持轻量且可替换；CI 直接调用 Python 核心，避免 shell 绑定。

## 验证

从本目录按改动选择检查；Linux/macOS 的 `python3` 与 Windows 的 `python` 按实际环境替换。

- 只读审计：检查必要资料；没有运行证据需求时不启动验证命令。
- 规则、技能或模板文案：运行下方对应结构/链接验证，审阅触发边界和相关场景。
- 初始化器、验证器或安装契约变化：运行受影响回归；需要全门禁时执行 `python3 scripts/check_project.py` 一次，它已包含两个验证器调用和单元测试。
- 复用同一任务内输入和环境未变的可追溯结果；后续只重跑受影响项。通过后停止，交付阶段不重新运行。

```bash
python3 scripts/validate_agents_project.py . --template
python3 scripts/validate_agents_project.py assets/agents-project-template --template
```

根据实际修改核对 UI 提示、模板占位符、默认不覆盖及失败报告等相关契约；未修改对应脚本时不机械重跑全部安装测试。

## 常用命令

```bash
python3 scripts/check_project.py --skip-optional-tools
rg --files -uu -g '!**/.git/**'
rg "TODO|{{[A-Z0-9_]+}}" assets scripts tests SKILL.md
python3 scripts/init_agents_project.py --target <temp-project> --dry-run
```
