# Discord 用户消息监听转发工具

监听指定 Discord 频道中特定用户的消息，并转发到企业微信。

## 功能特点

- **按频道配置监听用户**: 每个频道可单独配置要监听的用户（按 global_name 匹配）
- **企业微信推送**: 匹配的消息自动推送到企业微信
- **复用 monitor 逻辑**: 保持与 discord_monitor 相同的监控机制和性能优化

## 安装依赖

确保已安装项目根目录所需的依赖：

```bash
cd ..
pip install -r requirements.txt
# 或手动安装所需包
pip install aiohttp pyyaml backports.zoneinfo requests
```

## 配置方法

1. 复制配置示例（可选）：

```bash
cp config.yaml config.local.yaml
```

2. 编辑 `config.yaml`，填写以下必要信息：

```yaml
# Discord 用户令牌（必填）
discord_token: "YOUR_DISCORD_TOKEN"

# 企业微信 Webhook 地址（必填，用于接收通知）
wecom_webhook: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"

# 监控的频道配置
channels:
  - guild_id: "1234567890123456789"
    channel_id: "9876543210987654321"
    name: "频道名称"
    # 该频道的监听用户（按 global_name 匹配）
    watch_users:
      - "用户名1"
      - "用户名2"

  - guild_id: "1111111111111111111"
    channel_id: "2222222222222222222"
    name: "另一个频道"
    # 不配置 watch_users 或留空，则监听该频道所有用户
```

### 获取 Discord Token

1. 在浏览器中打开 Discord 并登录
2. 按 F12 打开开发者工具
3. 切换到 Network 标签
4. 刷新页面，找到任意请求，查看请求头中的 "Authorization"
5. 复制该值（不要包含引号）

### 获取企业微信 Webhook

1. 在企业微信群中，点击右上角「...」→「添加群机器人」
2. 选择「新建机器人」，填写名称
3. 复制生成的 Webhook 地址

## 使用方法

```bash
# 使用默认配置文件 (config.yaml)
python discord_listener.py

# 指定配置文件
python discord_listener.py -c config.local.yaml

# 调试模式（显示详细日志）
python discord_listener.py -v

# 自定义监控间隔（秒）
python discord_listener.py -i 60
```

## 配置说明

### 频道配置

| 参数 | 说明 | 必填 |
|------|------|------|
| `guild_id` | Discord 服务器 ID | 是 |
| `channel_id` | Discord 频道 ID | 是 |
| `name` | 频道显示名称 | 否 |
| `watch_users` | 监听用户列表（global_name） | 否，留空监听所有 |

### 代理设置

如果需要使用代理（如 Clash）：

```yaml
proxy:
  enabled: true
  url: "http://127.0.0.1:7890"  # Clash 默认地址
```

## 输出格式

控制台输出格式：

```
[22:30:15] [频道名] 用户名: 消息内容
```

企业微信推送格式：

```
[频道名] 用户名: 消息内容
```

## 与 discord_monitor 的区别

| 功能 | discord_monitor | discord_listener |
|------|-----------------|------------------|
| 显示消息 | 所有用户 | 仅各频道 watch_users 匹配的用户 |
| 企业微信推送 | 不支持 | 支持 |
| 用户配置 | 无 | 每个频道独立配置 |
| 使用场景 | 全局监控 | 特定用户提醒 |

## 注意事项

1. **Discord 令牌**: 请妥善保管，不要提交到代码仓库
2. **企业微信 Webhook**: 包含敏感信息，不要分享给他人
3. **速率限制**: 建议将 `interval` 设置为 300 秒（5分钟）以上
4. **权限**: 确保你的令牌有权限访问配置的频道
5. **用户名匹配**: 使用 Discord 的 global_name（显示名称）进行匹配
