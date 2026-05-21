# 文档索引

本文档是项目文档导航。复制模板后，请按项目实际文档更新本索引。

## 1. 当前必读

| 文档 | 用途 |
|---|---|
| `../AGENTS.md` | AI/开发助手执行入口（技能路由 + 生命周期） |
| `../README.md` | 项目快速入口 |
| `项目代码结构与使用说明.md` | 当前代码结构、主要入口、运行方式、注意事项 |
| `文档整理说明.md` | 文档分类规则、推荐阅读顺序、历史方案说明 |
| `development_memory.md` | 长期问题记录，开发和排查前必读 |
| `process/代码开发规范_方案审核流程版.md` | 开发流程规范（权威参考） |

## 1.1 技能工作流（Agent 执行入口）

Agent 执行任务时优先走技能工作流，而非直接阅读规范文档。

| 技能 | 路径 | 用途 |
|------|------|------|
| 元技能 | `../skills/using-dev-workflows/SKILL.md` | 技能发现与路由 |
| 方案编写审核 | `../skills/plan-before-code/SKILL.md` | 需求理解 → 方案 → 审核 |
| 编码执行 | `../skills/minimal-implementation/SKILL.md` | 严格按方案最小改动 |
| 问题记录 | `../skills/problem-tracking/SKILL.md` | 记录问题到 development_memory |
| 交付检查 | `../skills/delivery-checklist/SKILL.md` | 自测 → 交付说明 → 检查清单 |

## 1.2 参考模板

| 模板 | 路径 | 用途 |
|------|------|------|
| 方案模板 | `../references/plan-template.md` | 编写开发方案的标准模板 |
| 问题记录模板 | `../references/problem-record-template.md` | 记录问题的标准格式 |
| 交付格式 | `../references/delivery-format.md` | 交付说明的标准格式 |
| 代码分层参考 | `../references/code-layers-reference.md` | 代码分层和文件命名规范 |

## 2. 使用说明

使用说明集中在：

```text
usage/
```

新增当前可执行操作说明时，放入该目录并更新本索引。

## 3. 部署与环境

部署说明集中在：

```text
deploy/
```

新增自启动、安装、环境配置、运维说明时，放入该目录并更新本索引。

## 4. 历史方案与变更记录

方案文档集中在：

```text
history_plans/
```

这些文档用于保留需求分析、方案审核和变更背景，不直接替代当前使用说明。

## 5. 协议资料

协议原件和外部资料集中在：

```text
protocol/
```

字段、接口、通信协议应优先参考该目录中的正式资料。

## 6. 过程规范

```text
process/代码开发规范_方案审核流程版.md  （权威参考，Agent 优先走 skills/）
development_memory.md
```

## 7. 技能与参考

技能工作流（Agent 执行入口）：

```text
../skills/using-dev-workflows/SKILL.md
../skills/plan-before-code/SKILL.md
../skills/minimal-implementation/SKILL.md
../skills/problem-tracking/SKILL.md
../skills/delivery-checklist/SKILL.md
```

参考模板（技能工作流按需引用）：

```text
../references/plan-template.md
../references/problem-record-template.md
../references/delivery-format.md
../references/code-layers-reference.md
```

## 7. 后续维护规则

- 新增当前操作说明时，放入 `usage/` 并更新本索引。
- 新增部署说明时，放入 `deploy/` 并更新本索引。
- 新增方案文档时，放入 `history_plans/` 并更新本索引。
- 已确认的问题、原因和解决方法写入 `development_memory.md`。
- 默认地址、端口、设备 ID、入口路径要以当前代码为准。
- 历史方案与当前代码冲突时，不直接按旧方案操作，应重新确认需求。
