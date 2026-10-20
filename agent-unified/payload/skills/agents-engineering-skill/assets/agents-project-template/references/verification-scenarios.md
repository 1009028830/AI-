# 按场景选择验证

这是一份按需采用的场景目录，不是每次必跑清单。工具能力参考下方官方资料，检查范围与触发条件是工程建议，查询日期 2026-10-16。工具是否安装、许可证、目标版本及硬件是否可用须在项目中核实；登记工具不等于已经接入。

## 选择与复用

1. 从本次目标、修改文件、直接调用方和目标环境选择适用场景。
2. 复用项目现有测试，以 `verification.json` 声明任务、输入、输出与依赖。
3. 本地可重复检查可以显式启用缓存；外部服务、真实设备和时效性检查不缓存通过结果。
4. 不清楚依赖时扩大到相关模块，不能凭文件名猜测不受影响；脚本不会自动分析任意语言的语义依赖。
5. 缺少工具/硬件、没有测试或未执行，不得报告通过。通过后停止，交付复用证据。

## 软件与系统

| 场景 ID | 最小检查 / 可选工具 | 触发重跑或扩大范围 | 缓存边界 |
| --- | --- | --- | --- |
| guidance | 文档链接、结构、规则触发与冲突；已有 AGENTS 验证器 | 内容、引用目标、工作流变化 | 本地结构可缓存；在线链接状态不可长期复用 |
| python | 单元测试、固定数据样例；unittest/pytest，按需 testmon | 源码、测试、输入数据、配置、依赖变化 | testmon 不自动追踪全部静态资源及外部服务 [1] |
| cpp | 相关目标构建、单元测试；CTest，按需编译缓存 | 公共头文件、宏、链接脚本、工具链及调用方变化 | 编译成功与功能成功分别记录 [2] |
| frontend | 组件行为、受影响页面和关键流程；已有框架/Playwright | 公共组件、路由、状态、登录及接口变化 | 静态产物可复用；远端站点状态不得按源码缓存 [3] |
| api | 输入输出、错误码、权限、接口契约；Pact/现有接口测试 | 提供者、消费者或契约变化 | 本地固定依赖可缓存；在线接口重新验证 [4] |
| database | 临时数据库迁移、约束、数据完整性；Testcontainers | SQL、迁移、引擎版本、schema 或数据集变化 | 真实数据库作为 external；临时容器任务默认不缓存 [5] |
| concurrency | 资源生命周期、退出、并发边界；按需 Sanitizer | 所有权、锁、线程、队列、分配释放变化 | 一次成功不证明无竞争；平台支持单独核实 [6] |
| performance | 固定负载、基线和阈值；按需 k6/项目基准 | 算法、硬件、查询、缓存、并发变化 | 默认不缓存性能结论，明确硬件、负载和基线 [7] |

## 嵌入式、车载与电池

| 场景 ID | 最小检查 / 可选工具 | 触发重跑或扩大范围 | 缓存边界 |
| --- | --- | --- | --- |
| stm32 | 主机纯逻辑与 HAL 替身；Unity/CMock/Ceedling | BSP、HAL、Cube、链接、中断、DMA、RTOS 配置变化 | 主机证据不等于目标芯片、外设和时序 [8] |
| esp32 | 对应 IDF 目标与组件测试；Unity/pytest-embedded | IDF、芯片、sdkconfig、分区、无线或电源配置变化 | 目标板与无线环境测试不缓存成功 [9] |
| zephyr | 按测试、平台和配置使用 Twister | Kconfig、设备树、板级配置、内核变化 | 区分 build-only、主机、仿真和实板；不强制迁移非 Zephyr 项目 [10] |
| linux-app | 启停、信号、I/O、超时、异常恢复 | ABI、libc、服务配置、权限、设备接口变化 | 交叉编译与目标运行分开；不能跨 CPU 复用运行结果 |
| linux-kernel | KUnit 内部逻辑、kselftest 用户可见接口 | 内核、Kconfig、设备树、锁、DMA、中断及 UAPI 变化 | 设备 probe/remove、休眠唤醒等另做实板验证 [11] |
| can-uds | 编解码、超时、会话和异常序列；按需 vcan/协议库 | DBC、协议、字节序、比例、通道、适配器或固件变化 | vcan 不证明物理仲裁、负载和总线错误能力 [12] |
| serial-modbus | 分帧、校验、寄存器映射、重连与模拟从站 | 地址、寄存器、比例、帧格式、超时变化 | 实机电气条件及现场设备兼容性单独验证 |
| bms | 固定数据集、SOC/SOH/SOP、迟滞、延时、保护状态机 | 算法、标定、AFE、采样周期、联锁及硬件变化 | 按项目需求选择 SIL/PIL/HIL；不自定阈值或替代认证 [13] |
| ota | 镜像解析、签名、版本和状态机失败路径 | Bootloader、分区、密钥配置、升级/恢复逻辑变化 | 升级中断、启动选择等目标验证为 device，须动作授权 |

## 工程交付与维护

| 场景 ID | 最小检查 / 可选工具 | 触发重跑或扩大范围 | 缓存边界 |
| --- | --- | --- | --- |
| platform | 操作系统/CPU/工具链矩阵；已有 CI | OS、CPU、运行时、编译器或系统依赖变化 | Windows、Linux、ARM、x86 结果不能互相冒充 [14] |
| restore | 临时目录首次安装、幂等、冲突、失败回退 | 安装逻辑、载荷、权限和目标状态变化 | 必须是隔离目录测试才能声明本地可缓存 |
| deployment | 配置解析、构建、启动与健康检查 | 镜像、网络、挂载、权限、环境或部署目标变化 | 部署后在线健康检查使用 external，不复用离线结果 |
| dependency | 相关调用方、兼容性、核心功能 | 锁文件、依赖版本、ABI、编译参数变化 | 显式列出依赖锁和工具链；版本相同不证明所有外部状态相同 |
| security | 定位到风险的输入/权限/依赖检查 | 安全相关代码、规则库或漏洞数据更新 | 在线漏洞与时效性检查不缓存通过，或另用受控时效策略 |
| release | 实际产物、版本、清单、SHA256、安装冒烟 | 产物或打包逻辑变化 | 验证交付的字节；源码通过不等于归档完整 |
| git-delivery | 差异、敏感内容、已有证据与目标提交 | 新改动、输入失效或明确门禁 | 不因提交、推送或写总结重跑业务测试 |

## 场景组的采用顺序

- 日常：相关结构、静态检查、模块测试和短冒烟。
- 集成：跨模块、临时数据库、接口契约及平台矩阵。
- 台架：设备、目标板、时序、升级中断和受控故障场景。
- 发布：交付产物、兼容性及明确发布门禁。

这些组只用于组织配置，不是固定的测试时长或一律执行顺序。发布可以显式强制重跑；硬件、高压、充放电、执行器及生产动作仍需具体授权和条件。

## 官方来源

1. [testmon 依赖与限制](https://www.testmon.org/)
2. [CMake CTest](https://cmake.org/cmake/help/latest/manual/ctest.1.html)
3. [Playwright CLI](https://playwright.dev/docs/test-cli)
4. [Pact 提供者验证](https://docs.pact.io/provider)
5. [Testcontainers](https://testcontainers.com/)
6. [LLVM ThreadSanitizer](https://clang.llvm.org/docs/ThreadSanitizer.html)
7. [Grafana k6 阈值](https://grafana.com/docs/k6/latest/using-k6/thresholds/)
8. [ThrowTheSwitch Ceedling 测试环境](https://docs.throwtheswitch.org/Ceedling/latest/overview/test-environments/)
9. [Espressif ESP-IDF 单元测试](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/unit-tests.html)
10. [Zephyr Twister](https://docs.zephyrproject.org/latest/develop/twister/index.html)
11. [Linux Kernel Testing Guide](https://www.kernel.org/doc/html/latest/dev-tools/testing-overview.html)
12. [Linux SocketCAN](https://www.kernel.org/doc/html/latest/networking/can.html)
13. [MathWorks BMS 验证与测试](https://www.mathworks.com/videos/series/verifying-validating-and-testing-battery-management-systems.html)
14. [GitHub Actions 矩阵](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations)
15. [Nx 受影响任务](https://nx.dev/docs/features/ci-features/affected)
16. [Nx 缓存与减少重复工作](https://nx.dev/docs/kb/reduce-waste)
