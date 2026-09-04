# P2P文件传输工具


## 项目概述

本项目是一个基于frp xtcp功能实现的P2P文件传输工具，支持大文件传输、断点续传、传输速度显示、双向传输等功能，并提供美观易用的用户界面。通过frp的xtcp模式，实现了NAT穿透，使得不同网络环境下的用户可以直接传输文件，无需通过中间服务器中转数据。

## 功能特点

- **P2P直连传输**：利用frp的xtcp功能实现点对点传输，无需经过服务器中转，传输速度更快
- **大文件支持**：支持大文件分块传输，无文件大小限制
- **断点续传**：支持传输中断后从断点处继续传输，避免重新开始
- **传输速度显示**：实时显示文件传输速度和进度
- **双向传输**：支持双方互相发送文件
- **传输确认**：接收方需确认后才能开始传输，保障安全
- **美观界面**：采用马卡龙暖色系配色方案，界面美观易用
- **角色区分**：明确区分发送端和接收端角色，确保连接正确建立
- **状态监控**：实时监控连接状态和传输进度
- **传输历史**：记录文件传输历史，方便查看

## 技术原理

### frp xtcp工作原理

frp (Fast Reverse Proxy) 是一个高性能的反向代理应用，可以帮助实现内网穿透。本项目使用其中的xtcp模式，该模式采用P2P方式进行NAT穿透：

1. 两个客户端都连接到frp服务器
2. 服务器协助两个客户端建立P2P连接
3. 连接建立后，数据直接在两个客户端之间传输，不再经过服务器

这种方式的优势在于：
- 传输速度不受服务器带宽限制
- 减轻服务器负担
- 提高传输效率

### 断点续传实现

断点续传通过以下步骤实现：
1. 文件分块传输
2. 记录已传输的块信息
3. 传输中断时保存断点信息
4. 恢复传输时从断点处继续

## 环境要求
- FRP服务器 v0.52.3 及以上
- Python 3.8+ 环境
- **操作系统**：Windows 10/11 或 Linux
- 至少2GB可用内存

### FRP客户端要求
- **Windows**: 需要 `frpc.exe` 文件
- **Linux**: 需要 `frpc` 可执行文件
- 请将对应的FRP客户端文件放在 `src/` 目录下

## 使用说明

### 角色说明
本工具采用服务端-访客端模式，使用时需要注意：

- **发送端（服务端/Server）**：选择"发送端"角色的用户，在frp中作为服务端
- **接收端（访客端/Visitor）**：选择"接收端"角色的用户，在frp中作为访客端

**重要**：双方必须选择不同的角色才能建立连接！如果双方都选择相同角色，将无法建立P2P连接。

### 使用流程

1. **启动程序**：双击运行程序，选择角色（发送端或接收端）
2. **建立连接**：程序会自动连接到frp服务器并尝试建立P2P连接
3. **发送文件**：
   - 点击"选择文件"按钮选择要发送的文件
   - 点击"发送文件"按钮发起传输请求
4. **接收文件**：
   - 当收到文件传输请求时，会弹出确认对话框
   - 选择"接受"或"拒绝"
   - 接受后，文件会自动保存到下载目录

### 端口配置

程序默认使用7100端口进行P2P通信。如果此端口被占用，可以修改源代码中的`local_port`值。

### 传输状态说明

- **正在连接frp服务器**：程序正在尝试连接到frp服务器
- **已连接到frp服务器**：成功连接到frp服务器，等待P2P连接建立
- **P2P连接已建立**：成功建立P2P连接，可以开始传输文件
- **正在发送/接收**：文件正在传输中
- **传输完成**：文件传输已完成
- **传输错误**：传输过程中出现错误

## 程序打包说明

本项目可以使用PyInstaller打包成单个可执行文件，方便分发和使用。

### 打包步骤

1. 确保已安装PyInstaller：
   ```
   pip install pyinstaller
   ```

2. 在项目根目录执行打包命令：
   ```
   pyinstaller --onefile --windowed --icon=resources/icon.ico --add-data "src/frpc.exe;." src/main.py
   ```

3. 打包完成后，可执行文件将生成在`dist`目录下

### 打包注意事项

- 确保frpc.exe文件包含在打包中
- 如果使用了自定义图标，需要提前准备icon.ico文件
- 打包时可能需要排除一些不必要的模块，以减小文件体积

## 常见问题

1. **无法连接到frp服务器**
   - 检查网络连接是否正常
   - 确认frp服务器地址和端口是否正确
   - 检查防火墙设置是否阻止了连接

2. **无法建立P2P连接**
   - 确保双方选择了不同的角色（一方为发送端，一方为接收端）
   - 检查NAT类型，某些严格的NAT可能无法穿透
   - 尝试重启程序

3. **传输中断**
   - 程序支持断点续传，重新发送同一文件会从断点处继续
   - 检查网络连接是否稳定

4. **文件传输速度慢**
   - P2P连接受网络环境影响，特别是上传带宽
   - 尝试使用有线网络连接以提高稳定性

## FRP服务器配置
1. 下载对应系统的frp程序（需包含frps）
2. 配置frps.ini（示例）：
```ini
[common]
bind_port = 7000
auth.token = your_secure_token
```
3. 启动frps：`frps -c frps.ini`

## 使用方法

### 客户端配置

1. **准备配置文件**：
   - 在项目根目录下的 `config/` 目录中创建配置文件：
    - **发送端配置文件** `config/frpc_server.toml`：
      ```toml
      serverAddr = "your-frp-server-domain.com"
      serverPort = 7000
      auth.token = "your-secure-token"

      # xtcp P2P模式（首选）
      [[proxies]]
      name = "p2pfile_xtcp"
      type = "xtcp"
      secretKey = "p2pfiletransfer"
      localIP = "127.0.0.1"
      localPort = 7100

      # stcp 安全隧道模式（fallback）
      [[proxies]]
      name = "p2pfile_stcp"
      type = "stcp"
      secretKey = "p2pfiletransfer"
      localIP = "127.0.0.1"
      localPort = 7100
      ```

    - **接收端配置文件** `config/frpc_visitor.toml`：
      ```toml
      serverAddr = "your-frp-server-domain.com"
      serverPort = 7000
      auth.token = "your-secure-token"

      # xtcp P2P模式（首选）
      [[visitors]]
      name = "p2pfile_xtcp_visitor"
      type = "xtcp"
      serverName = "p2pfile_xtcp"
      secretKey = "p2pfiletransfer"
      bindAddr = "127.0.0.1"
      bindPort = 7102

      # stcp 安全隧道模式（fallback）
      [[visitors]]
      name = "p2pfile_stcp_visitor"
      type = "stcp"
      serverName = "p2pfile_stcp"
      secretKey = "p2pfiletransfer"
      bindAddr = "127.0.0.1"
      bindPort = 7103
      ```

2. **修改配置文件**：
   - 修改以下参数：
     - `serverAddr`: 你的FRP服务器地址
     - `serverPort`: FRP服务器端口（默认7000）
     - `auth.token`: FRP服务器认证令牌
     - `secretKey`: P2P连接密钥（双方必须相同）

### 使用流程

1. **配置准备**：
   - 在项目根目录创建 `config/` 目录
   - 发送端：创建 `config/frpc_server.toml` 并填入发送端配置
   - 接收端：创建 `config/frpc_visitor.toml` 并填入接收端配置

2. **启动程序**：
   - 双方都启动应用程序
   - 程序会自动读取对应的配置文件

3. **建立连接**：
   - 程序会自动连接到frp服务器并尝试建立P2P连接

4. **传输文件**：
   - 发送方选择要传输的文件
   - 接收方确认接收
   - 开始传输，界面显示传输进度和速度
   - 传输完成后自动校验文件完整性

## 连接模式说明

### xtcp P2P模式（首选）
- **工作原理**：通过UDP打洞建立点对点直连
- **优势**：数据传输不经过服务器，速度快
- **限制**：成功率取决于NAT类型，Full-Cone NAT成功率最高

### stcp 安全隧道模式（fallback）
- **工作原理**：通过服务器中转数据
- **优势**：连接成功率100%，不受NAT类型限制
- **限制**：数据传输经过服务器，速度受服务器带宽限制

### 自动fallback机制
- 程序会优先尝试xtcp P2P连接
- 如果30秒内无法建立P2P连接，自动切换到stcp模式
- 无需用户干预，自动完成切换

## 注意事项

- xtcp模式的成功率取决于NAT类型，Full-Cone NAT类型成功率最高
- stcp模式作为fallback，确保连接成功率100%
- 大文件传输时请确保磁盘有足够空间
- 传输过程中请勿关闭程序，否则需要从断点处重新传输

## 参考资料

- [frp官方文档](https://gofrp.org/docs/)
- [frp xtcp模式说明](https://gofrp.org/zh-cn/docs/features/xtcp/)
- [NAT类型介绍](https://blog.csdn.net/deng_xj/article/details/89187944)

## 许可证

MIT License
