#!/usr/bin/env python3
"""
Discord 频道消息实时监控工具

定时获取指定频道的最新消息，并以聊天窗口形式显示在控制台。
支持多个频道同时监控，带速率限制保护。

使用方法:
1. 复制 config.example.yaml 为 config.yaml
2. 填写你的 Discord 令牌和频道信息
3. 运行: python discord_monitor.py
"""

import os
import sys
import json
import asyncio

import aiohttp
import argparse
import logging
import requests
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from pathlib import Path

# 时区库兼容性处理
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# 添加父目录到路径以复用代码
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from discord_scraper import (
    API_BASE, DEFAULT_MAX_RETRIES, DEFAULT_RETRY_DELAY,
    make_request, create_client_session, parse_channel_id
)

# 配置日志
logger = logging.getLogger('discord_listener')


class DiscordMonitor:
    """Discord 消息监控器"""

    def __init__(self, config_path: str = "config.yaml"):
        """初始化监控器"""
        self.config = self.load_config(config_path)
        self.setup_logging()

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
        self.interval = self.config.get('interval', 10)
        self.limit = self.config.get('limit', 50)

        # 显示设置
        self.display_config = self.config.get('display', {})

        # 时区设置（空值或省略则使用 UTC）
        timezone_str = self.display_config.get('timezone')
        if timezone_str:
            try:
                self.timezone = ZoneInfo(timezone_str)
            except Exception:
                logger.warning(f"无效的时区设置: {timezone_str}，使用 UTC")
                self.timezone = timezone.utc
        else:
            self.timezone = timezone.utc

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

        # 会话
        self.session = None

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
        # 配置连接池
        conn = aiohttp.TCPConnector(
            limit=self.advanced_config.get('connection_pool_size', 10),
            ttl_dns_cache=300,
            ssl=False,
            force_close=False
        )

        # 配置超时
        timeout = aiohttp.ClientTimeout(
            total=self.advanced_config.get('timeout', 60),
            connect=10,
            sock_connect=10,
            sock_read=30
        )

        # 创建会话
        self.session = aiohttp.ClientSession(
            connector=conn,
            timeout=timeout,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )

        # 如果有代理，设置代理
        if self.proxy_url:
            logger.info(f"使用代理: {self.proxy_url}")
            # aiohttp 需要在请求时传入 proxy 参数，这里我们先记录
            self.session._default_proxy = self.proxy_url

    async def close(self):
        """关闭会话"""
        if self.session:
            await self.session.close()

    async def make_request_with_proxy(self, url: str, params: Dict = None) -> tuple:
        """发送请求，支持代理和重试"""
        # 使用配置文件中的 token 构建请求头
        headers = {
            'Authorization': self.token,
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        kwargs = {
            'params': params,
            'headers': headers  # 添加认证头
        }
        if self.proxy_url:
            kwargs['proxy'] = self.proxy_url

        retries = 0
        last_error = None

        while retries <= self.max_retries:
            try:
                async with self.session.get(url, **kwargs) as response:
                    if response.status == 429:  # 速率限制
                        retry_after = int(response.headers.get('Retry-After', DEFAULT_RETRY_DELAY))
                        logger.warning(f"速率限制，等待 {retry_after} 秒后重试...")
                        await asyncio.sleep(retry_after)
                        retries += 1
                        continue
                    elif response.status >= 500:  # 服务器错误
                        logger.warning(f"服务器错误 ({response.status})，重试中...")
                        await asyncio.sleep(DEFAULT_RETRY_DELAY * (retries + 1))
                        retries += 1
                        continue

                    content = await response.read()
                    return response, content

            except Exception as e:
                logger.warning(f"请求失败: {str(e)}，重试中...")
                await asyncio.sleep(DEFAULT_RETRY_DELAY * (retries + 1))
                retries += 1
                last_error = e
                continue

        if last_error:
            raise Exception(f"请求失败，已达到最大重试次数 ({self.max_retries}): {str(last_error)}")
        else:
            raise Exception(f"请求失败，已达到最大重试次数 ({self.max_retries})")

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

    def send_wecom(self, message: str):
        """发送企业微信通知"""
        if not self.wecom_webhook:
            return
        try:
            payload = {"msgtype": "text", "text": {"content": message}}
            proxies = {'http': self.proxy_url, 'https': self.proxy_url} if self.proxy_url and self.proxy_url.startswith('http') else None
            requests.post(
                self.wecom_webhook,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=10,
                proxies=proxies
            )
        except Exception as e:
            logger.error(f"WeCom send failed: {e}")

    def print_banner(self):
        """打印启动横幅"""
        print("\n" + "=" * 60)
        print("       Discord 频道消息实时监控")
        print("=" * 60)
        print(f"监控频道数: {len(self.channels)}")
        print(f"企业微信推送: {'已开启' if self.wecom_webhook else '未配置'}")
        print(f"监控间隔: {self.interval} 秒")
        print(f"单次请求: {self.limit} 条 (自动分页直到追平最新)")
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

            # 处理消息：过滤指定用户并通知
            for msg in messages:
                author = msg.get('author', {})
                global_name = author.get('global_name') or author.get('username', '')

                # 如果配置了 watch_users，只处理匹配的用户
                if watch_users and global_name not in watch_users:
                    continue

                formatted = self.format_message(msg, name)
                print(formatted)

                # 发送企业微信通知
                if self.wecom_webhook:
                    self.send_wecom(formatted)

            total_fetched += len(messages)
            # 更新最后消息ID为这批消息的最后一条
            last_id = messages[-1]['id']

            # 如果获取的消息数少于限制，说明已经追平最新
            if len(messages) < self.limit:
                break

            # 分页间隔：使用配置值或默认1.5秒
            # 注意：make_request 内已有 429 被动保护，这是主动预防
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

    async def run(self):
        """运行监控循环"""
        await self.initialize()
        self.print_banner()

        try:
            while True:
                tasks = [
                    self.monitor_channel(ch_config)
                    for ch_config in self.channels
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

                await asyncio.sleep(self.interval)

        except asyncio.CancelledError:
            logger.info("监控任务被取消")
        finally:
            await self.close()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Discord 频道消息实时监控",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-c", "--config",
        help="配置文件路径",
        default="config.yaml"
    )

    parser.add_argument(
        "-i", "--interval",
        type=int,
        help="监控间隔（秒）",
        default=None
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细日志"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        monitor = DiscordMonitor(args.config)

        # 命令行参数覆盖配置文件
        if args.interval:
            monitor.interval = args.interval

        asyncio.run(monitor.run())

    except KeyboardInterrupt:
        print("\n\n监控已停止")
    except Exception as e:
        logger.error(f"发生错误: {str(e)}")
        raise


if __name__ == "__main__":
    main()
