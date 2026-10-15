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
- L2 模板、初始化器、验证器或工作流行为变化：更新计划，修改实现与测试，运行完整验证。
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

从本目录执行。Linux/macOS 优先使用 `python3`；环境仅提供 `python`
命令时等价替换：

```bash
python3 scripts/check_project.py
python3 scripts/validate_agents_project.py assets/agents-project-template --template
python3 -B -m unittest discover -s tests -v
```

交付前还要确认：

- `agents/openai.yaml` 的默认提示显式包含 `$agents-engineering-skill`。
- 安装到临时目录后没有未解析的 `{{TOKEN}}`。
- 默认安装不会覆盖已有 `AGENTS.md` 或脚本。
- 失败测试能被验证器识别，成功报告不含伪造结果。

## 常用命令

```bash
python3 scripts/check_project.py --skip-optional-tools
rg --files -uu -g '!**/.git/**'
rg "TODO|{{[A-Z0-9_]+}}" assets scripts tests SKILL.md
python3 scripts/init_agents_project.py --target <temp-project> --dry-run
```
