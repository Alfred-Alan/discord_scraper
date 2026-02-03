#!/usr/bin/env python3
"""
Discord Watcher - Discord 频道消息监控工具

基于 Cron 调度器的 Discord 频道消息实时监听工具。
支持指定用户监听、上下文消息输出、企业微信推送。

使用方法:
1. 复制 config.example.yaml 为 config.yaml
2. 填写你的 Discord 令牌和频道信息
3. 运行: python watcher.py

示例:
    # 使用配置文件中的 cron 设置运行
    python watcher.py

    # 指定配置文件
    python watcher.py -c config.yaml

    # 显示详细日志
    python watcher.py -v
"""

import os
import sys
import json
import asyncio

import argparse
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path
from utils.wecom_bot import send_text

# 时区处理 - 使用 dateutil (支持跨平台，无需 tzdata)
from dateutil import tz

import yaml
from common import (
    API_BASE, DEFAULT_MAX_RETRIES, DEFAULT_RETRY_DELAY,
    get_headers, make_request, create_client_session, parse_channel_id
)
from utils.wecom_bot import send_md_v2
from pkg.scheduler import CronJobScheduler

# 配置日志
logger = logging.getLogger('discord_watcher')


class DiscordWatcher:
    """Discord 频道消息监听器 - 基于 Cron 调度器"""

    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化监控器

        Args:
            config_path: 配置文件路径
        """
        self.config = self.load_config(config_path)
        self.setup_logging()

        # Cron 表达式（从配置文件读取，自动转换 interval）
        self.cron_expr = self._get_cron_expr()

        # 获取令牌（仅使用配置文件）
        self.token = self.config.get('discord_token')
        if not self.token:
            logger.error("未找到 Discord 令牌。请在 config.yaml 中设置 discord_token。")
            raise ValueError("Discord 令牌未设置")

        # 频道配置
        self.channels = self.config.get('channels', [])
        if not self.channels:
            logger.error("请在 config.yaml 中配置要监控的频道")
            raise ValueError("未配置监控频道")

        # 新增：通知配置
        self.wecom_webhook = self.config.get('wecom_webhook', '')

        # 监控设置
        self.limit = self.config.get('limit', 50)

        # 显示设置
        self.display_config = self.config.get('display', {})

        # 时区设置（空值或省略则使用 UTC）
        timezone_str = self.display_config.get('timezone')
        if timezone_str:
            try:
                self.timezone = tz.gettz(timezone_str)
                if self.timezone is None:
                    raise ValueError(f"无法识别的时区: {timezone_str}")
            except Exception:
                logger.warning(f"无效的时区设置: {timezone_str}，使用 UTC")
                self.timezone = tz.UTC
        else:
            self.timezone = tz.UTC

        # 高级设置
        self.advanced_config = self.config.get('advanced', {})
        self.max_retries = self.advanced_config.get('max_retries', DEFAULT_MAX_RETRIES)

        # 代理设置
        self.proxy_config = self.config.get('proxy', {})
        self.proxy_url = None
        if self.proxy_config.get('enabled', False):
            self.proxy_url = self.proxy_config.get('url')

        # 状态跟踪：记录每个频道最后一条消息的ID
        self.last_message_ids = {}

        # 状态文件路径
        self.state_file = self.config.get('state_file', '.discord_watcher_state.json')
        self.load_state()

        # 上下文消息数量配置
        self.context_count = self.config.get('context_count', 10)

        # 会话
        self.session = None

        # 调度器（用于定时任务模式）
        self.scheduler: Optional[CronJobScheduler] = None

        # 速率限制：企业微信限制 20条/分钟
        self.wecom_rate_limit = 20  # 每分钟最大条数
        self.wecom_send_times: list = []  # 记录发送时间戳

    def _get_cron_expr(self) -> str:
        """
        获取 cron 表达式

        从配置文件中读取，如果没有设置则使用默认值

        Returns:
            cron 表达式
        """
        # 从配置文件中读取
        config_cron = self.config.get('cron')
        if config_cron:
            logger.info(f"Using cron from config: {config_cron}")
            return config_cron

        # 默认每5分钟
        default_cron = "*/5 * * * *"
        logger.warning(f"No cron configured, using default: {default_cron}")
        return default_cron

    def load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        if not os.path.exists(config_path):
            # 尝试在当前目录查找
            config_path = Path(__file__).parent / config_path

        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def setup_logging(self):
        """设置日志"""
        log_config = self.config.get('logging', {})
        level = getattr(logging, log_config.get('level', 'INFO').upper(), logging.INFO)

        handlers = [logging.StreamHandler()]

        if log_config.get('save_to_file', False):
            log_file = log_config.get('log_file', 'discord_monitor.log')
            handlers.append(logging.FileHandler(log_file, encoding='utf-8'))

        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=handlers
        )

    async def initialize(self):
        """初始化会话（支持代理）"""
        self.session = await create_client_session(
            connection_pool_size=self.advanced_config.get('connection_pool_size', 10),
            timeout=self.advanced_config.get('timeout', 60)
        )

        # 如果有代理，记录日志
        if self.proxy_url:
            logger.info(f"使用代理: {self.proxy_url}")

    async def close(self):
        """关闭会话"""
        if self.session:
            await self.session.close()

    async def make_request_with_proxy(self, url: str, params: Dict = None) -> tuple:
        """发送请求，支持代理和重试"""
        headers = get_headers(self.token)

        return await make_request(
            self.session,
            url,
            method="GET",
            headers=headers,
            params=params,
            max_retries=self.max_retries,
            proxy=self.proxy_url
        )

    async def fetch_new_messages(self, channel_id: str, after_message_id: Optional[str] = None) -> List[Dict]:
        """
        获取频道的新消息

        参数:
            channel_id: Discord 频道 ID
            after_message_id: 从此消息ID之后获取消息

        返回:
            消息列表（按时间排序，最新的在最后）
        """
        params = {'limit': self.limit}
        if after_message_id:
            params['after'] = after_message_id

        try:
            response, content = await self.make_request_with_proxy(
                f"{API_BASE}/channels/{channel_id}/messages",
                params=params
            )

            if response.status != 200:
                error_text = content.decode('utf-8', errors='replace')
                logger.error(f"获取消息失败: {response.status} - {error_text}")
                return []

            messages = json.loads(content)
            # 按时间排序（最旧的在前，最新的在后）
            messages.sort(key=lambda m: m['timestamp'])
            return messages

        except Exception as e:
            logger.error(f"获取消息时发生错误: {str(e)}")
            return []

    def format_message(self, message: Dict, channel_name: str = "") -> str:
        """
        格式化消息为聊天窗口样式

        参数:
            message: Discord 消息对象
            channel_name: 频道名称（用于显示）

        返回:
            格式化后的字符串
        """
        author = message['author']
        # 优先使用 global_name，如果没有则使用 username
        author_name = author.get('global_name') or author.get('username', 'Unknown')

        # 时间戳（转换为配置的时区）
        timestamp_str = ""
        if self.display_config.get('show_timestamp', True):
            ts_format = self.display_config.get('timestamp_format', '%H:%M:%S')
            try:
                # Discord 返回的是 UTC 时间
                timestamp_utc = datetime.fromisoformat(message['timestamp'].replace('Z', '+00:00'))
                # 转换为配置的时区
                timestamp_local = timestamp_utc.astimezone(self.timezone)
                timestamp_str = f"[{timestamp_local.strftime(ts_format)}] "
            except:
                pass

        # 频道标识
        channel_prefix = f"[{channel_name}] " if channel_name else ""

        # 消息内容
        content = message.get('content', '') or ""

        # 处理附件
        if self.display_config.get('show_attachments', True):
            attachments = message.get('attachments', [])
            if attachments:
                attachment_names = [a.get('filename', '未知文件') for a in attachments]
                if content:
                    content += " "
                content += f"[附件: {', '.join(attachment_names)}]"

        # 处理表情反应
        if self.display_config.get('show_reactions', True):
            reactions = message.get('reactions', [])
            if reactions:
                reaction_strs = []
                for r in reactions:
                    emoji = r['emoji'].get('name', '')
                    count = r.get('count', 1)
                    reaction_strs.append(f"{emoji}x{count}")
                if content:
                    content += " "
                content += f"[反应: {', '.join(reaction_strs)}]"

        # 保留原始内容，不做截断

        # 组合最终输出
        # 格式: [时间] [频道] 发送人: 消息内容
        formatted = f"{timestamp_str}{channel_prefix}{author_name}: {content}"

        return formatted

    def format_message_wecom(self, message: Dict, channel_name: str = "", is_target: bool = False) -> str:
        """
        格式化消息为企业微信 Markdown 格式

        参数:
            message: Discord 消息对象
            channel_name: 频道名称
            is_target: 是否是目标用户消息

        返回:
            Markdown 格式的字符串
        """
        author = message['author']
        author_name = author.get('global_name') or author.get('username', 'Unknown')

        # 时间戳
        timestamp_str = ""
        try:
            timestamp_utc = datetime.fromisoformat(message['timestamp'].replace('Z', '+00:00'))
            timestamp_local = timestamp_utc.astimezone(self.timezone)
            timestamp_str = timestamp_local.strftime('%Y-%m-%d %H:%M:%S')
        except:
            pass

        # 消息内容
        content = message.get('content', '') or ""

        # 处理附件
        attachments = message.get('attachments', [])
        if attachments:
            attachment_names = [a.get('filename', '未知文件') for a in attachments]
            if content:
                content += "\n"
            content += f"[附件: {', '.join(attachment_names)}]"

        # 处理表情反应
        reactions = message.get('reactions', [])
        if reactions:
            reaction_strs = [f"{r['emoji'].get('name', '')}x{r.get('count', 1)}" for r in reactions]
            if content:
                content += "\n"
            content += f"[反应: {', '.join(reaction_strs)}]"

        # 纯文本格式：
        # [18:54:20] [美股交流]
        # *username: content
        time_short = timestamp_str[11:19] if len(timestamp_str) > 10 else timestamp_str
        header = f"[{time_short}]"
        if channel_name:
            header += f" [{channel_name}]"

        # 目标用户标记
        user_display = f"*{author_name}" if is_target else author_name

        lines = [
            header,
            f"{user_display}: {content}",
        ]

        return "\n".join(lines)

    async def send_wecom(self, message: str, message_obj: Dict = None, channel_name: str = "", is_target: bool = False):
        """发送企业微信通知（带速率限制 20条/分钟，超限则等待）"""
        if not self.wecom_webhook:
            return

        import time
        import asyncio
        from datetime import datetime, timedelta

        # 检查速率限制
        now = time.time()
        one_minute_ago = now - 60

        # 清理一分钟前的记录
        self.wecom_send_times = [t for t in self.wecom_send_times if t > one_minute_ago]

        # 如果超过限制，等待直到可以发送
        while len(self.wecom_send_times) >= self.wecom_rate_limit:
            # 计算需要等待的时间
            oldest_time = min(self.wecom_send_times)
            wait_time = 60 - (now - oldest_time) + 0.5  # 多等0.5秒确保保险
            if wait_time > 0:
                logger.warning(f"WeCom rate limit ({self.wecom_rate_limit}/min) reached, waiting {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)

            # 重新检查
            now = time.time()
            one_minute_ago = now - 60
            self.wecom_send_times = [t for t in self.wecom_send_times if t > one_minute_ago]

        try:
            # 格式化消息
            if message_obj:
                content = self.format_message_wecom(message_obj, channel_name, is_target)
            else:
                content = message

            send_text(self.wecom_webhook, content)
            self.wecom_send_times.append(time.time())
            logger.debug(f"WeCom sent, count in last 60s: {len(self.wecom_send_times)}")
        except Exception as e:
            logger.error(f"WeCom send failed: {e}")

    def print_banner(self):
        """打印启动横幅"""
        print("\n" + "=" * 60)
        print("       Discord 频道消息实时监控")
        print("=" * 60)
        print(f"监控频道数: {len(self.channels)}")
        print(f"企业微信推送: {'已开启' if self.wecom_webhook else '未配置'}")
        print(f"调度周期: {self.cron_expr}")
        print(f"单次请求: {self.limit} 条 (自动分页直到追平最新)")
        print(f"上下文消息数: {self.context_count} 条 (目标用户前后各{self.context_count}条)")
        print("-" * 60)
        print("开始监控... (按 Ctrl+C 停止)\n")

    async def monitor_channel(self, channel_config: Dict):
        """
        监控单个频道 - 持续获取直到追平最新

        参数:
            channel_config: 频道配置字典
        """
        channel_id = channel_config.get('channel_id')
        guild_id = channel_config.get('guild_id')
        name = channel_config.get('name', channel_id)

        if not channel_id:
            logger.warning(f"频道配置缺少 channel_id: {channel_config}")
            return

        # 如果没有提供 guild_id，尝试解析
        if not guild_id:
            parsed_guild, parsed_channel = parse_channel_id(channel_id)
            if parsed_guild:
                guild_id = parsed_guild
                channel_id = parsed_channel

        # 初始化该频道的最后消息ID
        if channel_id not in self.last_message_ids:
            self.last_message_ids[channel_id] = None

        # 持续获取消息直到没有新消息
        total_fetched = 0
        last_id = self.last_message_ids[channel_id]

        while True:
            messages = await self.fetch_new_messages(channel_id, last_id)

            if not messages:
                break  # 没有新消息了，退出循环

            # 获取该频道的监听用户配置
            watch_users = channel_config.get('watch_users', [])

            if watch_users:
                # 步骤1: 找到所有目标用户消息的索引
                target_indices = set()
                for idx, msg in enumerate(messages):
                    author = msg.get('author', {})
                    global_name = author.get('global_name') or author.get('username', '')
                    if global_name in watch_users:
                        target_indices.add(idx)

                if target_indices:
                    # 步骤2: 为每个目标消息计算上下文范围
                    ranges = []
                    for target_idx in target_indices:
                        start_idx = max(0, target_idx - self.context_count)
                        end_idx = min(len(messages) - 1, target_idx + self.context_count)
                        ranges.append((start_idx, end_idx, target_idx))

                    # 步骤3: 合并重叠的范围
                    # 按起始位置排序
                    ranges.sort(key=lambda x: x[0])
                    merged_ranges = []
                    current_start, current_end, current_targets = ranges[0][0], ranges[0][1], {ranges[0][2]}

                    for i in range(1, len(ranges)):
                        start, end, target = ranges[i]
                        if start <= current_end + 1:  # 范围重叠或相邻
                            current_end = max(current_end, end)
                            current_targets.add(target)
                        else:  # 不重叠，保存当前范围
                            merged_ranges.append((current_start, current_end, current_targets))
                            current_start, current_end, current_targets = start, end, {target}
                    merged_ranges.append((current_start, current_end, current_targets))

                    # 步骤4: 按合并后的范围输出，保持时间顺序
                    for start_idx, end_idx, targets_in_range in merged_ranges:
                        # 输出该范围内的所有消息，按时间顺序
                        for i in range(start_idx, end_idx + 1):
                            msg = messages[i]
                            is_target = i in target_indices
                            prefix = "* " if is_target else "  "
                            formatted = prefix + self.format_message(msg, name)
                            print(formatted)

                            # 企业微信通知所有消息
                            if self.wecom_webhook:
                                await self.send_wecom("", message_obj=msg, channel_name=name, is_target=is_target)
            else:
                # 没有配置监听用户，输出所有消息
                for msg in messages:
                    formatted = self.format_message(msg, name)
                    print(formatted)

                    if self.wecom_webhook:
                        await self.send_wecom("", message_obj=msg, channel_name=name, is_target=False)

            total_fetched += len(messages)
            # 更新最后消息ID为这批消息的最后一条
            last_id = messages[-1]['id']

            # 如果获取的消息数少于限制，说明已经追平最新
            if len(messages) < self.limit:
                break

            # 分页间隔：使用配置值或默认1.5秒
            page_delay = self.advanced_config.get('page_delay', 1.5)
            await asyncio.sleep(page_delay)

            # 安全上限：单次轮询最多获取 10 页（防止极端情况无限循环）
            if total_fetched >= self.limit * 10:
                logger.warning(f"频道 [{name}] 本轮获取消息过多，已截断，剩余消息将在下次轮询获取")
                break

        # 更新全局最后消息ID
        if total_fetched > 0:
            self.last_message_ids[channel_id] = last_id
            logger.debug(f"频道 [{name}] 本轮共获取 {total_fetched} 条消息")

    def load_state(self):
        """从文件加载状态"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    self.last_message_ids = state.get('last_message_ids', {})
                    logger.info(f"State loaded from {self.state_file}")
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")
            self.last_message_ids = {}

    def save_state(self):
        """保存状态到文件"""
        try:
            state = {
                'last_message_ids': self.last_message_ids,
                'saved_at': datetime.now().isoformat()
            }
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            logger.debug(f"State saved to {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    async def tick(self):
        """
        单次执行监控任务

        被调度器定时调用，执行一次消息检查
        """
        if not self.session:
            await self.initialize()

        try:
            tasks = [
                self.monitor_channel(ch_config)
                for ch_config in self.channels
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

            # 保存状态
            self.save_state()

        except Exception as e:
            logger.error(f"Tick error: {e}")

    async def start(self):
        """启动监控器（调度器模式）"""
        self.print_banner()
        logger.info(f"调度器模式，cron: {self.cron_expr}")

        # 创建调度器
        self.scheduler = CronJobScheduler()

        # 添加定时任务 - 调用自身的 tick 方法
        await self.scheduler.add_job(
            job_id="discord_tick",
            cron_expr=self.cron_expr,
            func=self.tick
        )

        # 启动调度器
        await self.scheduler.start()
        logger.info("调度器已启动，按 Ctrl+C 停止")

        try:
            # 保持运行
            await self.scheduler.wait()
        except KeyboardInterrupt:
            logger.info("正在停止...")
        finally:
            await self.stop()

    async def stop(self):
        """停止监控器"""
        if self.scheduler:
            await self.scheduler.stop()
            self.scheduler = None
        await self.close()
        logger.info("监控器已停止")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Discord 频道消息实时监控（调度器模式）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python watcher.py                  # 使用配置文件设置（cron或interval）
  python watcher.py -c config.yaml   # 指定配置文件

配置文件示例:
  cron: "*/5 * * * *"        # 直接指定cron表达式
  # 或者使用interval（自动转换）
  interval: 300              # 300秒 = 5分钟
        """
    )

    parser.add_argument(
        "-c", "--config",
        help="配置文件路径",
        default="config.yaml"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细日志"
    )

    args = parser.parse_args()

    # 设置日志级别
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        monitor = DiscordWatcher(args.config)
        asyncio.run(monitor.start())
    except KeyboardInterrupt:
        print("\n\n监控已停止")
    except Exception as e:
        logger.error(f"发生错误: {str(e)}")
        raise


if __name__ == "__main__":
    main()
