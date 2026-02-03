# Discord Watcher - Discord 频道消息监控工具

基于 Cron 调度器的 Discord 频道消息实时监听工具，支持指定用户监听、上下文消息输出、企业微信推送。

## 功能特性

- **Cron 调度模式**：基于 APScheduler 的定时任务调度，避免长时间运行导致的卡顿问题
- **指定用户监听**：可配置监听特定用户，或监听频道所有用户
- **上下文消息**：当监听到目标用户发言时，同时输出前后各 N 条消息
- **智能合并**：多个目标用户发言上下文重叠时，自动合并并按时间顺序输出
- **企业微信推送**：支持将消息推送到企业微信群
- **速率限制**：内置企业微信 20条/分钟 的速率限制，超限自动等待不丢消息
- **状态持久化**：支持保存和恢复最后读取的消息位置

## 快速开始

### 1. 安装依赖

```bash
cd /Users/ljq/projects/discord_scraper
pip install -r requirements.txt
```

### 2. 配置

复制配置模板并编辑：

```bash
cd discord_watcher
cp config-template.yaml config.yaml
vim config.yaml
```

关键配置项：

```yaml
# Discord 用户令牌（必填）
discord_token: "你的Discord用户令牌"

# Cron 表达式（调度频率）
cron: "*/5 * * * *"

# 企业微信推送（可选）
wecom_webhook: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxx"

# 监听的频道
channels:
  - channel_id: "1234567890123456789"
    name: "频道名称"
    watch_users:
      - "目标用户名"

# 上下文消息数量
context_count: 10
```

### 3. 运行

```bash
python watcher.py

# 或指定配置文件
python watcher.py -c config.yaml

# 调试模式
python watcher.py -v
```

## 配置详解

### 调度配置

```yaml
# Cron 表达式
# 格式: 分 时 日 月 周
# 示例:
#   "*/5 * * * *"    每5分钟
#   "*/10 * * * *"   每10分钟
#   "0 * * * *"      每小时整点
#   "0 9 * * 1-5"    工作日9点
cron: "*/5 * * * *"
```

> 建议：根据频道活跃度设置，活跃频道建议 5-10 分钟，不活跃频道可缩短到 1-2 分钟

### 频道配置

```yaml
channels:
  - channel_id: "Discord频道ID"
    name: "显示名称"
    watch_users:          # 监听特定用户，为空则监听所有
      - "用户名1"
      - "用户名2"
```

### 上下文配置

```yaml
# 当监听到目标用户发言时，输出前后各 N 条消息
# 多个目标用户的上下文重叠时会自动合并
context_count: 10

# 单次请求获取的消息数（Discord API 限制最大100）
limit: 100
```

### 企业微信配置

```yaml
wecom_webhook: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxx"
```

消息格式示例：
```
[18:54:20] [美股交流]
*卡皮巴菲特: 跟你说了有集团举报我
```

### 代理配置

```yaml
proxy:
  enabled: true
  url: "http://127.0.0.1:7890"
```

## 工作原理

### 调度模式

- 使用 `CronJobScheduler` 定时触发 `tick()` 方法
- 每次 `tick()` 执行一轮消息获取和处理
- 处理完成后保存状态，释放资源
- 避免长时间运行导致的内存泄漏和卡顿

### 消息处理流程

1. 获取频道新消息（从上次记录的位置开始）
2. 识别目标用户消息
3. 计算上下文范围（前后各 N 条）
4. 合并重叠的范围
5. 按时间顺序输出消息
6. 推送到企业微信（带速率限制）
7. 保存状态

### 速率限制

企业微信限制 20条/分钟：
- 当发送频率超过限制时，自动等待
- 不会跳过或丢失任何消息
- 日志会显示等待时间

## 状态文件

```yaml
state_file: ".discord_watcher_state.json"
```

状态文件保存每个频道最后读取的消息 ID，重启后从该位置继续，避免重复获取。

## 日志

```yaml
logging:
  level: "INFO"          # DEBUG, INFO, WARNING, ERROR
  save_to_file: false
  log_file: "discord_watcher.log"
```

## 注意事项

1. **Discord Token**：使用用户令牌而非机器人令牌，获取方式见配置文件注释
2. **速率限制**：企业微信 20条/分钟，Discord API 有独立的速率限制（代码已处理重试）
3. **隐私**：用户令牌具有账号完整权限，请勿泄露
4. **合规**：使用用户令牌可能违反 Discord 服务条款，请谨慎使用

## 文件结构

```
discord_watcher/
├── watcher.py              # 主程序
├── config.yaml             # 配置文件
├── config-template.yaml    # 配置模板
├── README.md               # 本文件
└── .discord_watcher_state.json  # 状态文件（自动生成）
```

## 依赖

- Python >= 3.8
- aiohttp >= 3.8.0
- apscheduler >= 3.10.0
- pyyaml >= 6.0
- python-dateutil >= 2.8.0

## 常见问题

### Q: 为什么用 Cron 调度而不是循环？
A: 长时间运行的循环可能导致内存泄漏或卡顿。Cron 调度每次执行完就释放资源，更稳定可靠。

### Q: context_count 是什么？
A: 当监听到目标用户发言时，除了该消息本身，还会获取前后各 N 条消息作为上下文，帮助理解对话背景。

### Q: 消息会重复推送吗？
A: 不会。状态文件会记录最后读取的消息 ID，重启后从该位置继续。

### Q: 企业微信收不到消息？
A: 检查：
1. webhook 地址是否正确
2. 是否触发了速率限制（查看日志）
3. 代理配置是否正确（如使用代理）

## License

MIT
