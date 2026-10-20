# 统一验证入口

项目入口为 `scripts/verify.py`，配置为根目录 `verification.json`。Python 3.11+，仅标准库；Windows 使用实际 Python 命令，Linux 通常为 `python3`。首次执行所选检查建立基线，以后根据声明输入判断是否重跑。

## 使用

```bash
# 从项目根预览，不执行命令、不写缓存
python scripts/verify.py
# 执行已审阅配置；只复用输入未变的本地成功结果
python scripts/verify.py --run
# 聚焦某个任务，自动包括前置依赖
python scripts/verify.py --run --only agent-guidance
# 发布门禁、环境变动未被声明或排查不稳定测试时强制执行
python scripts/verify.py --run --force
```

可从其他目录调用，使用 `--root /path/to/project`。`--config` 是相对项目根的配置路径。脚本不安装依赖、不自动改测试、不自动选择板卡，也不读取 Git 作为唯一变化依据。未提交改动、文件新增和删除均按实际内容检测。

## 编译、功能验证与审查的顺序

常规代码修改先完成编译/基础检查，再运行相关功能测试，最后按 [验证与审查技能](../skills/verification-and-review/SKILL.md) 集中审查。已有执行器的 `depends_on` 足以表达自动化阶段顺序，无需再建执行框架。

具体项目先声明实际的 `build` 任务，再给功能测试任务配置 `"depends_on": ["build"]`。运行功能任务会自动包含构建依赖；构建失败会阻断依赖它的测试。声明真实源码、构建配置、工具链及所需产物，避免测试旧二进制；只运行构建任务不代表完成逻辑验证。解释型代码可依赖基础检查任务，纯规则仓库保留现有结构检查，不增加无意义的编译步骤。

正式审查由 Agent 或评审者依据差异和有效证据完成，不添加恒成功的命令冒充审查；执行器通过也不代表审查已经通过。当前模板只配置规则检查，业务构建和测试依赖须在目标项目接入后才会执行。

依据（查询日期：2026-10-19）：

- [Google Engineering Practices：What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)：开发者应在进入审查前充分测试；审查仍需关注边界、并发和测试质量。
- [GitLab：CI/CD pipelines](https://docs.gitlab.com/ci/pipelines/)：阶段可顺序运行，构建成功后进入测试，失败可阻断后续阶段。该机制支持自动检查顺序，并不强制规定人工审查何时开始。

这里采用的是适合本工作流的默认顺序，并非声称存在全球统一的强制流程。

## 配置契约

下面是配置格式示例，不是现成的业务测试；新增任务时替换为项目真实命令与存在的输入。

```json
{
  "version": 1,
  "tasks": [
    {
      "id": "module-tests",
      "description": "验证指定模块的行为",
      "command": ["{python}", "-B", "-m", "unittest", "discover", "-s", "tests"],
      "inputs": ["src/**/*.py", "tests/**/*.py", "requirements.lock"],
      "outputs": [],
      "depends_on": [],
      "tools": [],
      "cwd": ".",
      "scope": "local",
      "cache": true,
      "enabled": true,
      "platforms": ["windows", "linux"],
      "timeout": 120
    }
  ]
}
```

- `id` 唯一；`command` 是参数数组，只有独立参数 `{python}` 会替换为当前解释器。无 Shell 展开，不写 `&&`、管道或包含凭据的参数。需要多步动作时使用项目已有适配脚本。Windows `.cmd/.bat` 包装器需换成真实可执行程序或 Python 适配器。
- `inputs` 为项目根相对文件/通配模式，目录应写 `目录/**/*`；每个模式须至少匹配一个文件，避免路径写错被当作成功。包括代码、头文件、测试、夹具、配置、锁文件及调用到的脚本。忽略 `.git`、`.verification`、`__pycache__`、`.pytest_cache`。
- `outputs` 可声明构建产物；成功后必须存在，删除或变更会重跑。构建与测试拆分时，测试用 `depends_on` 声明前置构建。不能把被任务改写的生成文件同时当作该任务输入。
- `tools` 声明命令内部调用的额外工具名或路径；对可执行文件内容做指纹。未声明的系统库、SDK、动态加载插件等不会自动完整追踪，需要额外输入、隔离环境或关闭缓存。
- `cache` 默认 false，只对受控且可重复的本地检查设置 true。`scope` 为 local/external/device；external/device 禁止缓存通过结果。
- `enabled` 默认 true；false 表示不进入默认集合，仍可用 `--only` 显式选择。`platforms` 不填则不限制，填写时仅接受 windows/linux/darwin；这不代表已验证所有平台。
- `timeout` 为正数秒，默认 300，最大 86400；超时终止进程组。自脱离的守护进程不在保证范围内，检查脚本不得启动这类进程。

## 结果与失效

本地缓存与最后报告位于 `.verification/cache.json`、`.verification/report.json`，应加入项目忽略规则，不提交、不装入迁移包。输出状态区分 passed、reused、failed、blocked、not_applicable；预览是 plan，不是通过。

退出码：0 表示所选适用检查通过/有效复用（预览成功也为 0，须看 mode）；1 为失败、阻断或没有适用的成功检查；2 为配置/基础环境错误；130 为中断。报告必须同时满足 complete=true 和 ok=true 才能表述为本次集合通过，历史报告不能代替当前命令退出码。

缓存指纹包括任务定义、验证器、输入文件路径和内容、Python 版本及已安装 Python 分发包版本、系统/CPU、环境变量摘要、声明工具可执行文件和前置依赖的指纹/产物。新增无关任务不使既有任务全部失效；修改自己的配置会失效。环境变量只存摘要，不保存值。

缺少工具/输入、命令失败、超时、运行期间输入变化都不缓存成功；强制重跑前移除旧记录，失败后不能靠代码恢复成旧版本“捡回”旧成功。前置依赖不可缓存时，下游也不得复用结果。输出缺失或变化会重跑。失败后保留原因，重新执行同一命令即可。

这是一套显式依赖声明的执行器，不是完整语义依赖分析器或安全沙箱。漏报依赖会漏测，缓存也不是防篡改证明。测试涉及时间、随机、实时数据库、外部服务、设备、性能基线或漏洞数据时，默认关闭缓存或按具体场景声明为 external/device。工具原生内部失败不能靠“重试直到绿”掩盖。

## 设备与外部动作

只有取得具体动作授权、确认设备/服务目标及安全条件后，才可执行以下形式；它是操作入口，不替代授权：

```bash
python scripts/verify.py --run --only board-check --allow-external
```

任务须已经配置；不会默认存在 `board-check`。外部依赖任务也必须逐项显式列入 `--only`。默认不缓存设备结果，缺少板卡或权限是 blocked，不是 passed。

同一项目通过锁阻止并发写结果。异常退出留下 `run.lock` 时，确认原进程及其子进程均已结束后，才可手工删除该锁；不盲目自动抢锁。

## 场景扩展

从 [24 类验证场景](verification-scenarios.md) 选择适用项。统一入口调用已有测试程序，新增功能优先新增测试与配置；增加新工具后才需要适配脚本。初始化模板仅接入 AGENTS 结构检查，业务、设备和在线检查由具体项目添加。
