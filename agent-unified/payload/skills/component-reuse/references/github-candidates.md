# GitHub 可复用代码候选

查询日期：2026-10-16。面向 C/C++、STM32、ESP32、Linux 用户态与设备通信。

以下是选型候选，不是已安装组件。已核对作者 README、公开仓库状态、默认分支提交和可取得的许可证文件；未完成全部源码审计、漏洞审计、编译或目标硬件测试。平台适用性和移植成本为基于这些资料的工程判断。默认分支快照不等于推荐稳定版本。

## 优先考虑的小型组件

| 仓库 / 维护方 | 可复用内容与接入位置 | 平台与主要适配工作 | 许可证摘要 |
| --- | --- | --- | --- |
| [LwRB / MaJerle](https://github.com/MaJerle/lwrb) | 字节环形缓冲区，适合串口收发与流式数据缓存；从 `lwrb/` 和测试入手 | C11 核心可移植；核对原子操作、单生产者/单消费者条件，DMA 与缓存一致性另验。成本低至中 | MIT |
| [nanoMODBUS / debevv](https://github.com/debevv/nanoMODBUS) | 小型 Modbus RTU/TCP 协议库，核心 `nanomodbus.c/.h` | MCU 或主机提供读写回调；核对超时、RTU 帧间隔、RS485 方向及异常响应。成本中 | MIT |
| [Nanopb / nanopb](https://github.com/nanopb/nanopb) | 小型 Protocol Buffers 编解码，适合 MCU 与上位机共享消息结构 | C 运行库加生成工具；固定 `.proto`、生成器版本和容量策略。并非串口分帧或可靠传输协议。成本中 | Zlib |
| [cJSON / DaveGamble](https://github.com/DaveGamble/cJSON) | 配置、诊断和 JSON 报文，核心 `cJSON.c/.h` | ANSI C；核对动态内存、输入长度、嵌套深度和释放路径。硬实时 ISR 不直接调用。成本低至中 | MIT |
| [littlefs / littlefs-project](https://github.com/littlefs-project/littlefs) | 面向微控制器的文件系统，核心 `lfs.c/.h` 与 `lfs_util.c/.h` | 提供块读写、擦除和同步回调；核对 Flash 几何、分区、寿命与真实掉电行为。成本中至高 | BSD-3-Clause |
| [Unity / ThrowTheSwitch](https://github.com/ThrowTheSwitch/Unity) | C 单元测试框架，从 `src/` 和 examples 入手 | 可用于主机及目标端测试；自有编译、输出与 mock 接口仍需配置。不是同名游戏引擎。成本低 | MIT |

优先试用组合：纯逻辑测试采用 Unity；串口缓存评估 LwRB；Modbus、JSON、Protobuf 和文件系统按实际需求择一接入，不为凑齐清单同时引入。

## 按项目需要使用的组件与示例

| 仓库 / 维护方 | 复用价值 | 主要边界 | 许可证摘要 |
| --- | --- | --- | --- |
| [ESP-Modbus / Espressif](https://github.com/espressif/esp-modbus) | ESP32 的 RS485、Wi-Fi/Ethernet Modbus 集成 | 与 ESP-IDF、芯片及组件版本匹配；ESP32 优先比较已有官方组件，不与 nanoMODBUS 重复实现同一功能 | 项目 Apache-2.0；历史 FreeMODBUS 与 Master 来源另有 BSD-3-Clause 声明 |
| [STM32 UART DMA 示例 / MaJerle](https://github.com/MaJerle/stm32-usart-uart-dma-rx-tx) | 学习 USART、DMA 与空闲事件处理，参考 RX/TX 示例 | 平台示例，不是直接通用库；芯片系列、DMA、时钟、HAL/LL 和缓存配置都要核对；不要整个搬入业务工程 | 仓库 MIT，厂商 SDK 文件按各自声明 |
| [coreMQTT / FreeRTOS](https://github.com/FreeRTOS/coreMQTT) | 嵌入式 MQTT 客户端协议核心 | 需提供网络/TLS、时间和并发策略。当前 README 分别指向 MQTT 3.1.1 的 v2.3.1 与 MQTT 5.0 的 v5.0.2；不能无条件选默认分支替换旧接口 | MIT |
| [ETL / ETLCPP](https://github.com/ETLCPP/etl) | 面向嵌入式的 C++ 容器和算法，可评估定容数据结构 | 按目标 C++ 标准、容量、错误处理、ROM/RAM 和编译器验证；只选所需部分 | MIT |
| [uthash / Troy Hanson](https://github.com/troydhanson/uthash) | C 哈希表及相关容器工具，从 `src/uthash.h` 开始 | 宏接口与分配策略需要审查；不能把哈希表默认理解为无动态分配或线程安全 | `uthash.h` 为 BSD 风格条款；根 LICENSE 要求查看各文件，不能统一重新授权 |
| [spdlog / gabime](https://github.com/gabime/spdlog) | Linux/Windows C++ 服务与上位机日志 | 核对线程、异步队列、格式化依赖和阻塞；不作为裸机或内核日志方案直接移植 | 主库 MIT；LICENSE 另列 fmt 相关声明 |
| [libmodbus / Stéphane Raimbault 等](https://github.com/stephane/libmodbus) | Linux/Windows 用户态 Modbus RTU/TCP | 更适合主机服务和网关；串口权限、连接恢复及调用并发需验证。与 MCU 小型库分别选型 | LGPL-2.1 系列，按实际源文件及链接/分发方式核对条款 |
| [can-utils / linux-can](https://github.com/linux-can/can-utils) | Linux SocketCAN 抓包、回放、ISO-TP 工具及调用示例 | Linux 专用工具集；优先直接使用工具，不把程序源码当通用驱动库。主动发包须有设备动作授权 | 按文件核对；例如 `candump.c` 标记 GPL-2.0-only OR BSD-3-Clause |
| [isotp-c / lishen2](https://github.com/lishen2/isotp-c) | ISO-TP 分段/重组的 C 实现参考 | 快照最新提交时间为 2022-01-30，作为次选并重点核对未解决问题、寻址、时序和 CAN FD 支持；ISO-TP 不等于完整 UDS 栈 | MIT |

## 版本与维护依据

机器可读记录见 [github-snapshot.json](github-snapshot.json)：包含 15 个仓库的完整提交 SHA、提交日期、归档状态、许可证链接及哈希。查询时这 15 个仓库均未归档；这不代表维护质量或当前安全性均已验证。

`can-utils` 的根许可证 API 返回 404；`spdlog`、`uthash` 的自动识别为 NOASSERTION。这些结果已原样记录，以下文件级原文用于补充判断，不能据此推断所有文件许可相同：

- [can-utils candump.c](https://github.com/linux-can/can-utils/blob/834ceef1f1eabec67625389172eebf1050d2f42b/candump.c)
- [spdlog LICENSE](https://github.com/gabime/spdlog/blob/08155a51c532126597db917c42aabdac1b20f011/LICENSE)
- [uthash.h](https://github.com/troydhanson/uthash/blob/a49bed0b4abb7dff16c73906dcdc8a9718d582d2/src/uthash.h)

实际采用时选定与项目兼容的 tag/commit，保存原始声明，记录必要补丁；先构建最小示例和测试，再接入业务项目。更新快照时同步复核本文，脚本不会自动更新人工选型结论。

## Linux 内核层

本清单中的通用 C 库默认面向用户态或 MCU，不宣称可直接链接进内核。驱动开发优先检查目标内核已有的 FIFO、CRC、链表、工作队列和总线子系统，避免重复引入用户态依赖。准确 API 与可用配置应回到目标内核源码，并用现有 `linux-driver-kernel` 技能核对执行上下文、资源与锁。
