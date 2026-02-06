# Discord 频道消息实时监控工具

定时获取指定 Discord 频道的最新消息，并以聊天窗口形式显示在控制台。

## 功能特点

- **实时监控**: 定时轮询获取新消息
- **多频道支持**: 可同时监控多个频道
- **Discord Bot 推送**: 支持将消息转发到另一个 Discord 频道
- **防速率限制**: 内置重试机制和请求间隔控制
- **聊天窗口样式**: `发送人: 消息内容` 格式显示
- **增量获取**: 只获取上次之后的新消息
- **灵活配置**: 通过 YAML 配置文件自定义各项参数

## 安装依赖

确保已安装项目根目录所需的依赖：

```bash
cd ..
pip install -r requirements.txt  # 如果有的话
# 或手动安装所需包
pip install aiohttp pyyaml backports.zoneinfo
```

## 使用方法

### 1. 配置

复制配置文件并填写必要信息：

```bash
cp config.yaml config.yaml  # 直接编辑 config.yaml
```

编辑 `config.yaml`：

```yaml
# 填写你的 Discord 令牌
discord_token: "你的令牌"

# 配置监控的频道
channels:
  - channel_id: "频道ID"
    name: "频道显示名称"
    # guild_id: "服务器ID"  # 可选，用于获取角色信息

# Discord Bot 推送（可选）
discord_bot:
  enabled: true
  token: "你的 Discord Bot Token"
  channel_id: "目标频道ID"

# 监控间隔（秒）
interval: 10
```

### 2. 运行

```bash
python discord_monitor.py
```

或指定配置文件：

```bash
python discord_monitor.py -c my_config.yaml
```

### 3. 命令行参数

```bash
python discord_monitor.py -h

# 选项:
#   -c, --config     配置文件路径 (默认: config.yaml)
#   -i, --interval   监控间隔秒数 (覆盖配置文件)
#   -v, --verbose    显示详细日志
```

## 配置文件说明

### 频道配置

支持两种格式：

**格式1 - 仅频道ID**（自动从频道信息获取服务器ID）：
```yaml
channels:
  - channel_id: "1234567890123456789"
    name: "general"
```

**格式2 - 服务器ID/频道ID**（推荐，可获取角色信息）：
```yaml
channels:
  - guild_id: "9876543210987654321"
    channel_id: "1234567890123456789"
    name: "announcements"
```

### 显示设置

```yaml
display:
  show_timestamp: true          # 是否显示时间戳
  timezone: "Asia/Shanghai"     # 时区设置，留空则为 UTC
  timestamp_format: "%H:%M:%S"  # 时间格式
  show_user_id: false           # 是否显示用户ID
  show_attachments: true        # 是否显示附件信息
  show_reactions: true          # 是否显示表情反应
```

### 代理设置（支持 Clash 等）

```yaml
proxy:
  enabled: true
  url: "http://127.0.0.1:7890"  # Clash 默认地址
  # 格式: http://host:port 或 socks5://host:port
```

### Discord Bot 推送配置

```yaml
discord_bot:
  enabled: true                          # 是否启用
  token: "YOUR_BOT_TOKEN"               # Bot Token
  channel_id: "1234567890123456789"     # 目标频道 ID
  rate_limit: 5                         # 速率限制：每个时间窗口最多发送消息数
  rate_window: 5                        # 时间窗口（秒）
```

**获取 Bot Token：**
1. 访问 [Discord Developer Portal](https://discord.com/developers/applications)
2. 点击 "New Application" 创建应用
3. 进入 "Bot" 页面，点击 "Add Bot"
4. 复制 Token（注意：Token 只能查看一次，请妥善保存）
5. 在 "Privileged Gateway Intents" 中启用必要权限

**邀请 Bot 到频道：**
1. 进入 "OAuth2" -> "URL Generator"
2. 在 "Scopes" 中选择 `bot`
3. 在 "Bot Permissions" 中选择：`Send Messages`, `Read Message History`
4. 复制生成的 URL 并在浏览器中打开
5. 选择目标服务器并授权

**获取频道 ID：**
1. 在 Discord 中开启开发者模式（设置 -> 高级 -> 开发者模式）
2. 右键点击目标频道，选择 "复制频道 ID"

## 输出示例

```
============================================================
       Discord 频道消息实时监控
============================================================
监控频道数: 2
监控间隔: 300 秒
单次请求: 100 条 (自动分页直到追平最新)
------------------------------------------------------------
开始监控... (按 Ctrl+C 停止)

[22:30:15] [美股交流] 张三: 大家好！有人在线吗？
[22:30:18] [美股交流] 李四: 在的，有什么事吗？
[22:30:25] [美股交流] 张三: 请教一个问题 [附件: screenshot.png]
[22:35:10] [美股交流] 管理员: 系统维护通知 [反应: 👍x5]
```

## 注意事项

1. **Discord 令牌**: 请妥善保管你的令牌，不要提交到代码仓库
2. **速率限制**: 建议将 `interval` 设置为 300 秒（5分钟）以上，避免触发 Discord 速率限制
3. **权限**: 确保你的令牌有权限访问配置的频道
4. **网络**: 需要稳定的网络连接
5. **代理**: 如需使用 Clash 等代理工具，请在配置中启用并设置正确的代理地址
6. **时区**: 默认使用 UTC，如需显示本地时间请配置正确的时区（如 Asia/Shanghai）

## 与主工具的区别

| 功能 | discord_scraper (主工具) | discord_monitor (本工具) |
|------|-------------------------|-------------------------|
| 用途 | 一次性导出历史消息 | 实时监控新消息 |
| 输出 | Markdown/JSON/HTML 文件 | 控制台实时显示 |
| 使用场景 | 备份、归档 | 实时监控、聊天窗口 |
| 消息范围 | 可获取全部历史 | 只获取运行时的新消息 |
