# 组件契约检查项

只记录与组件有关的项目；不为小模块制造空模板。

| 项目 | 需要回答的问题 |
| --- | --- |
| 用途与边界 | 解决什么问题；哪些业务或硬件行为不属于组件？ |
| 来源 | 自有代码来自哪个版本？上游仓库、tag/commit、许可及本地补丁是什么？ |
| 公共接口 | 输入、输出、单位、长度、错误码、超时和部分完成如何表达？ |
| 资源 | 谁分配/释放？借用数据能存活多久？是否保存调用方指针？ |
| 并发 | 多实例是否独立？是否可重入？锁由谁持有？能否在 ISR 调用？ |
| 平台 | C/C++ 标准、编译器、ABI、端序、原子操作、HAL/RTOS/内核版本要求是什么？ |
| 配置 | 必选/可选参数如何传入？避免隐式依赖项目全局宏和绝对路径。 |
| 验证 | 最小示例、主路径、边界和失败路径；原项目回归；目标板仍缺什么？ |
| 演进 | 版本固定方式、兼容性承诺、升级检查和回退版本是什么？ |

协议解析优先覆盖分段输入、粘包、截断、长度越界、错误校验和恢复同步；只有协议定义了相应行为才测试。DMA 组件另验缓冲区复用、完成/错误事件和缓存条件。

参考依据（查询：2026-10-16）：

- [C++ Core Guidelines](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines)：I.1/I.2 接口与隐藏依赖，SF.9/SF.11 循环依赖与自包含头文件。C 项目仅采用适用原则。
- [Martin Fowler：Extract Function](https://refactoring.com/catalog/extractFunction.html)：小步提取行为。
- [Alistair Cockburn：Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture)：接口与外部适配的分离。
- [Semantic Versioning 2.0.0](https://semver.org/lang/zh-CN/)：围绕公开 API 表达兼容性；版本号不自动保证 ABI 或硬件兼容。

上述文档提供设计依据，本技能文字为针对本工作流的独立整理。
