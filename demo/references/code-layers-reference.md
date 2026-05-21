# 代码分层参考

本项目分层架构约定的参考文档。

---

## 推荐项目结构

### 带 UI 项目

```
project_root/
├── docs/      → 文档、方案、问题记录
├── ui/        → 界面层（显示、交互、状态）
├── logic/     → 业务逻辑层
├── comm/      → 通信层
├── data/      → 数据层（模型、解析、存储）
├── config/    → 配置层
├── utils/     → 工具层
├── tests/     → 测试
└── main.cpp   → 程序入口
```

### 纯后端项目

```
project_root/
├── docs/
├── service/   → 服务启动、生命周期、主流程
├── logic/     → 业务逻辑
├── comm/      → 通信
├── data/      → 数据处理
├── config/    → 配置
├── utils/     → 工具
├── tests/
└── main.cpp
```

---

## 各层职责

### UI 层

**仅用于有图形界面的项目。**

- 页面显示
- 用户交互
- 状态展示
- 日志展示
- 调用 logic 层接口

**禁止：** 复杂业务逻辑、底层通信、协议解析、大量文件保存。

### Service 层

**用于后端服务、命令行程序、systemd 服务、ROS 节点。**

- 程序启动入口
- 参数解析
- 服务生命周期管理
- 各模块初始化
- 信号处理
- 运行状态输出

### Logic 层

- 业务流程控制
- 功能调度
- 状态判断
- 调用 comm/data/config
- 向 UI 或 Service 提供接口

### Comm 层

- CAN 通信
- 串口通信
- TCP/UDP 通信
- WebSocket 通信
- Modbus 通信
- 连接状态管理

### Data 层

- 数据模型
- 数据解析
- 数据转换
- 数据缓存
- 数据保存

### Config 层

- 默认参数
- 配置加载
- 配置保存
- 运行参数管理

### Utils 层

- 时间工具
- 文件工具
- 字符串工具
- 日志辅助
- 通用函数

**注意：** 具体业务逻辑不要放到 utils 中。

---

## 文件命名

**推荐：**
```
can_driver.h
can_parser.h
can_debug_controller.h
can_record_storage.h
serial_port_driver.h
modbus_slave_service.h
config_manager.h
log_helper.h
```

**不推荐：**
```
test.cpp
new.cpp
fun.cpp
tools.cpp
data.cpp
main2.cpp
```

---

## 文件拆分规则

1. 每个功能尽量独立成文件/模块
2. 一个文件不能同时处理：UI + 通信 + 解析 + 存储 + 配置 + 日志
3. 文件名必须能看出作用

---

## UI 相关准则

**有 UI 时：**
- `.ui` 文件负责界面布局
- `.h/.cpp` 文件负责控件绑定和信号槽
- 核心逻辑留在 logic 层
- 推荐页面区域：功能操作 | 参数配置 | 状态显示 | 数据展示 | 日志调试

**无 UI（后端程序）时：**
- 启动参数清晰
- 配置文件格式清晰
- 日志输出清晰
- 状态可查询
- 错误提示明确
- 模块职责单一
- 方便部署和排查

**后端程序可观测性要求：**
必须至少提供以下之一：
- 控制台日志
- 文件日志
- 状态打印
- 命令行参数
- 配置文件
- 运行状态接口
- systemd service 状态
- ROS topic/service/param
- WebSocket/TCP 状态反馈
