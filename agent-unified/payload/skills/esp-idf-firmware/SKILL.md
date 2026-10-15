---
name: esp-idf-firmware
description: 开发、诊断或评审 ESP32 家族的 ESP-IDF 应用与组件，核对芯片目标、IDF 版本、sdkconfig、任务与内存、中断、构建及目标板验证。Arduino-only 工程不直接套用 IDF 命令，应先确认集成关系。
metadata:
  version: "1.0.0"
---

# ESP-IDF 固件开发与评审

以工程实际芯片与 ESP-IDF tag 为准开展工作，不将 stable 文档当作所有已部署版本的接口契约。

## 识别工程

- 读取顶层和组件 `CMakeLists.txt`、`sdkconfig`、`sdkconfig.defaults`、分区表、组件清单及依赖锁文件，确认 IDF 版本、芯片目标与构建目录。
- 明确 Xtensa/RISC-V、单核/多核、Flash/PSRAM 配置、板卡与外设连接。不要将整个 ESP32 家族默认成双核 Xtensa。
- 从当前 Shell 核实 IDF 工具环境、Python 和交叉编译器；Windows、WSL、Linux 分开检查。优先使用项目记录的环境，不混用另一版本 IDF 的 Python 包。
- 不为探测工程而运行 `idf.py set-target`、`fullclean` 或重新生成配置；它们会改变工程状态。需要改变目标时先明确受影响配置并保留现有内容。

## 开发和审查重点

| 变更类别 | 关注内容 |
| --- | --- |
| 组件/API | 公开头文件、组件依赖、初始化顺序、错误返回与失败清理；SDK API 按项目版本核对 |
| FreeRTOS | 任务优先级、亲和性、队列/通知、同步、退出回收；单核与 SMP 分开分析，不能只关本核中断就假定共享数据安全 |
| 内存 | 栈参数单位、栈余量、堆峰值、分配能力、内部 RAM/PSRAM 和 DMA 可访问性；按当前 IDF 接口核实单位 |
| ISR/cache | 可调用 API、代码及数据所在区域、整个调用链的缓存关闭约束；仅添加 IRAM_ATTR 不代表整体满足要求 |
| 错误和恢复 | 区分可恢复错误与致命错误；按语义返回、释放、有限重试或终止，不机械对所有错误调用 ESP_ERROR_CHECK |
| 配置与发布 | sdkconfig、分区表、应用/引导程序及产物对应；更改 OTA、加密或签名配置时分析兼容性与恢复路径 |

按当前变更选择相关项，保留项目风格和第三方代码边界。增加依赖、升级 IDF 或调整全局配置不作为普通功能修复的默认步骤。

## 聚焦执行

1. 在已核实 IDF 环境中使用现有构建入口；采用标准 IDF 工程时可运行 `idf.py build`，但先确认目标和依赖获取需求，不自动切换芯片或升级组件。
2. 对纯逻辑运行项目单元测试，对目标组件使用项目已配置的 IDF 测试设施；记录构建配置和实际执行范围。
3. 授权包含烧录时核实端口、设备、固件、分区布局与备份，再执行项目指定命令；烧录、整片擦除、eFuse 写入是不同动作，尤其不可逆 eFuse 必须有明确动作授权。
4. 用相匹配的 ELF/符号解析崩溃或回溯；采集实际启动日志、返回码和任务/内存诊断。看门狗问题先检查阻塞、任务饥饿和临界区，不直接关闭看门狗。
5. 无目标板时继续源码检查和可执行构建，将实际 RF、功耗、掉电恢复、OTA 与外设用例列为待验证。异常设备状态下停止后续写入，保留日志和恢复条件。

交付记录芯片、IDF tag、配置、变更和实际验证证据；不把编译通过写成 Wi-Fi、蓝牙或真实外设验收通过。

## 官方资料入口

查询日期：2026-10-15。以下入口当前指向 stable，使用时切换至工程所用 IDF 版本和芯片。

- [Error Handling / Espressif](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/error-handling.html)：错误传播、清理和致命错误边界。
- [FreeRTOS (IDF) / Espressif](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/system/freertos_idf.html)：调度、SMP、任务及临界区。
- 其他 API、构建和烧录命令优先阅读同一版本工程中的文档和工具帮助，不从不同 IDF 大版本拼接示例。
