# Discord Bot 消息发送模块

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import aiohttp

logger = logging.getLogger('discord_bot')

# Discord API 限制：5条/5秒
DISCORD_RATE_LIMIT = 5  # 5条
DISCORD_RATE_WINDOW = 5  # 5秒


class DiscordBotSender:
    """Discord Bot 消息发送器 - 支持速率限制"""

    def __init__(self, bot_token: str, channel_id: str):
        """
        初始化 Discord Bot 发送器

        Args:
            bot_token: Discord Bot Token
            channel_id: 目标频道 ID
        """
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.enabled = bool(bot_token and channel_id)

        # 速率限制跟踪
        self.send_times: list = []  # 记录发送时间戳
        self.rate_limit_count = DISCORD_RATE_LIMIT
        self.rate_limit_window = DISCORD_RATE_WINDOW

        # API 端点
        self.api_base = "https://discord.com/api/v10"

        if self.enabled:
            logger.info(f"Discord Bot 发送器已启用，目标频道: {channel_id}")
        else:
            logger.info("Discord Bot 发送器未启用（缺少 token 或 channel_id）")

    async def send_message(self, content: str, message_obj: Dict = None, channel_name: str = "", is_target: bool = False) -> bool:
        """
        发送消息到 Discord 频道

        Args:
            content: 消息内容（纯文本）
            message_obj: 原始 Discord 消息对象（可选，用于格式化）
            channel_name: 频道名称（用于格式化）
            is_target: 是否是目标用户消息

        Returns:
            是否发送成功
        """
        if not self.enabled:
            return False

        # 检查速率限制
        await self._check_rate_limit()

        # 格式化消息
        if message_obj:
            formatted_content = self._format_message(message_obj, channel_name, is_target)
        else:
            formatted_content = content

        # Discord 消息长度限制：2000 字符
        if len(formatted_content) > 2000:
            formatted_content = formatted_content[:1997] + "..."

        try:
            success = await self._send_to_discord(formatted_content)
            if success:
                self.send_times.append(asyncio.get_event_loop().time())
                logger.debug(f"Discord Bot 消息已发送，过去 {self.rate_limit_window}秒内共 {len(self.send_times)} 条")
            return success
        except Exception as e:
            logger.error(f"Discord Bot 发送失败: {e}")
            return False

    def _format_message(self, message: Dict, channel_name: str = "", is_target: bool = False) -> str:
        """
        格式化消息为 Discord 格式

        Args:
            message: Discord 消息对象
            channel_name: 频道名称
            is_target: 是否是目标用户消息

        Returns:
            格式化后的字符串
        """
        author = message.get('author', {})
        author_name = author.get('global_name') or author.get('username', 'Unknown')

        # 时间戳
        timestamp_str = ""
        try:
            try:
                from zoneinfo import ZoneInfo
            except ImportError:
                from backports.zoneinfo import ZoneInfo
            timestamp_utc = datetime.fromisoformat(message['timestamp'].replace('Z', '+00:00'))
            timestamp_local = timestamp_utc.astimezone(ZoneInfo('Asia/Shanghai'))
            timestamp_str = timestamp_local.strftime('%Y-%m-%d %H:%M:%S')
        except:
            pass

        # 消息内容
        content = message.get('content', '') or ""

        # 处理附件
        attachments = message.get('attachments', [])
        if attachments:
            attachment_urls = [a.get('url', '') for a in attachments if a.get('url')]
            if attachment_urls:
                if content:
                    content += "\n"
                content += "📎 附件: " + ", ".join(attachment_urls[:3])  # 最多显示3个附件

        # 处理表情反应
        reactions = message.get('reactions', [])
        if reactions:
            reaction_strs = [f"{r['emoji'].get('name', '')}x{r.get('count', 1)}" for r in reactions]
            if content:
                content += "\n"
            content += "👍 " + ", ".join(reaction_strs)

        # 目标用户标记
        target_marker = "🎯 " if is_target else ""

        # 格式化输出
        time_short = timestamp_str[11:19] if len(timestamp_str) > 10 else timestamp_str
        header = f"[{time_short}]"
        if channel_name:
            header += f" [{channel_name}]"

        # 组合最终消息
        result = f"{header}\n{target_marker}**{author_name}**: {content}"

        return result

    async def _check_rate_limit(self):
        """检查并等待速率限制"""
        now = asyncio.get_event_loop().time()
        window_start = now - self.rate_limit_window

        # 清理过期的记录
        self.send_times = [t for t in self.send_times if t > window_start]

        # 如果超过限制，等待
        while len(self.send_times) >= self.rate_limit_count:
            oldest_time = min(self.send_times)
            wait_time = self.rate_limit_window - (now - oldest_time) + 0.1  # 多等0.1秒确保保险
            if wait_time > 0:
                logger.warning(f"Discord Bot 速率限制 ({self.rate_limit_count}/{self.rate_limit_window}s) 已达到，等待 {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)

            # 重新检查
            now = asyncio.get_event_loop().time()
            window_start = now - self.rate_limit_window
            self.send_times = [t for t in self.send_times if t > window_start]

    async def _send_to_discord(self, content: str) -> bool:
        """
        实际发送消息到 Discord API

        Args:
            content: 格式化后的消息内容

        Returns:
            是否发送成功
        """
        url = f"{self.api_base}/channels/{self.channel_id}/messages"

        headers = {
            "Authorization": f"Bot {self.bot_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "content": content,
 "flags": 0
        }

        # 创建 TCPConnector 禁用 SSL 验证（解决 macOS 证书问题）
        connector = aiohttp.TCPConnector(ssl=False)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200 or response.status == 201:
                        logger.debug("Discord Bot 消息发送成功")
                        return True
                    elif response.status == 429:  # 速率限制
                        retry_after = float(response.headers.get('Retry-After', 1))
                        logger.warning(f"Discord API 速率限制，等待 {retry_after}s 后重试...")
                        await asyncio.sleep(retry_after)
                        return await self._send_to_discord(content)  # 递归重试
                    elif response.status == 401:
                        logger.error("Discord Bot Token 无效或已过期")
                        return False
                    elif response.status == 403:
                        logger.error("Discord Bot 没有权限发送消息到该频道")
                        return False
                    elif response.status == 404:
                        logger.error(f"Discord 频道不存在: {self.channel_id}")
                        return False
                    else:
                        error_text = await response.text()
                        logger.error(f"Discord API 错误: {response.status} - {error_text}")
                        return False
            except aiohttp.ClientConnectorError as e:
                logger.error(f"Discord API 连接错误: {e}")
                return False
            except asyncio.TimeoutError:
                logger.error("Discord API 请求超时")
                return False
            except Exception as e:
                logger.error(f"Discord API 请求异常: {e}")
                return False
