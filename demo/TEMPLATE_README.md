# SDK 开发模板 — 使用说明

## 这是什么

一套可直接复用的项目脚手架模板，内置：
- **技能驱动开发工作流**（`skills/`）：Agent 按生命周期阶段自动匹配工作流
- **参考模板**（`references/`）：方案模板、问题记录模板、交付格式、代码分层参考
- **文档体系**（`docs/`）：开发规范、问题记录、方案归档、使用/部署/协议说明
- **代码分层约定**（`src/`、`include/`、`config/` 等）：带 UI / 纯后端项目推荐结构

## 快速开始

### 1. 复制模板到新项目

```bash
# Windows
xcopy /E /I d:\Work\SDK开发-template d:\Work\你的新项目

# Linux / macOS
cp -r /path/to/SDK开发-template /path/to/your-new-project
```

### 2. 替换占位内容

以下文件包含占位符，需要按新项目实际情况填写：

| 文件 | 需替换的内容 |
|------|-------------|
| `README.md` | 项目名称、用途、构建/运行方法、当前状态 |
| `README.en.md` | 同上（英文版） |
| `docs/项目代码结构与使用说明.md` | 项目名称、类型、目录结构、入口、构建/运行/配置 |
| `docs/development_memory.md` | 环境约束（开发环境、目标环境、验证边界） |
| `AGENTS.md` | 环境约束章节（开发环境、目标运行环境、验证边界） |

### 3. 清理不需要的目录

如果新项目不需要某些目录，删除即可。例如纯脚本项目可能不需要 `include/`。

### 4. 开始开发

Agent 进入项目后，会自动读取 `AGENTS.md`，按技能路由执行开发工作流：

```
用户需求 → plan-before-code（方案） → 用户确认 → minimal-implementation（编码） → problem-tracking（记录） → delivery-checklist（交付）
```

## 模板包含内容

```
your-new-project/
├── AGENTS.md                            # Agent 执行入口（技能路由 + 生命周期）
├── README.md                            # 项目快速入口（需替换占位）
├── README.en.md                         # 英文入口（需替换占位）
├── .gitignore                           # Git 忽略规则
├── skills/                              # 技能工作流（Agent 按需加载）
│   ├── using-dev-workflows/SKILL.md     #   元技能：路由 + 核心行为
│   ├── plan-before-code/SKILL.md        #   方案编写与审核
│   ├── minimal-implementation/SKILL.md  #   最小改动编码
│   ├── problem-tracking/SKILL.md        #   问题记录
│   └── delivery-checklist/SKILL.md      #   交付检查
├── references/                          # 参考模板（技能工作流按需引用）
│   ├── plan-template.md                 #   方案模板
│   ├── problem-record-template.md       #   问题记录模板
│   ├── delivery-format.md               #   交付格式
│   └── code-layers-reference.md         #   代码分层参考
├── docs/                                # 文档体系
│   ├── INDEX.md                         #   文档索引
│   ├── development_memory.md            #   长期问题记录
│   ├── 文档整理说明.md                   #   文档分类与维护规则
│   ├── 项目代码结构与使用说明.md          #   项目结构说明（需替换）
│   ├── process/
│   │   └── 代码开发规范_方案审核流程版.md  #   完整开发规范（权威参考）
│   ├── history_plans/
│   │   └── 方案模板.md                   #   方案文档模板
│   ├── usage/                           #   使用说明（按需补充）
│   ├── deploy/                          #   部署说明（按需补充）
│   └── protocol/                        #   协议资料（按需补充）
├── config/                              # 配置目录（按需使用）
├── include/                             # 头文件目录（按需使用）
├── scripts/                             # 脚本目录（按需使用）
├── src/                                 # 源码目录（按需使用）
└── tests/                               # 测试目录（按需使用）
```

## 设计理念

本模板对标 [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills)，采用技能驱动工作流模式：

- **技能是工作流，不是参考文档。** 每个 SKILL.md 定义了 Agent 必须遵循的步骤化流程
- **反规避机制。** 每个技能包含"常见借口与反驳"表格，防止 Agent 跳过关键步骤
- **验证不可商量。** 每个技能以验证清单结尾，要求证据而非"看起来没问题"
- **按需加载。** 技能文件仅在匹配时加载，减少上下文消耗
- **最小改动原则。** 所有编码技能强制最小代码量、不做无关重构、不擅加功能

## 许可证

MIT — 可在你的项目、团队和工具中自由使用。
