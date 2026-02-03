#!/usr/bin/env python3
"""
Discord API 工具模块

提供与 Discord API 交互的基础功能，包括：
- API 常量定义
- 频道 ID 解析
- HTTP 请求（带重试机制）
- 会话创建
"""

import asyncio
import aiohttp
import logging
from typing import Dict, Optional, Tuple, Any

logger = logging.getLogger('discord_api')

# Discord API 端点
API_BASE = 'https://discord.com/api/v10'

# 默认重试次数和重试间隔
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 2  # 秒

# User-Agent
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'


def get_headers(token: str) -> Dict:
    """
    获取 Discord API 请求头。

    参数:
        token: Discord 认证令牌

    返回:
        包含认证信息的请求头字典
    """
    return {
        'Authorization': token,
        'Content-Type': 'application/json',
        'User-Agent': USER_AGENT
    }


def parse_channel_id(channel_input: str) -> tuple:
    """
    从用户输入解析服务器 ID 和频道 ID。

    参数:
        channel_input: 格式为 'server_id/channel_id' 或仅 'channel_id' 的字符串

    返回:
        (server_id, channel_id) 或 (None, channel_id) 的元组
    """
    if '/' in channel_input:
        parts = channel_input.strip().split('/')
        if len(parts) == 2:
            return parts[0], parts[1]

    # 如果只提供了频道 ID
    return None, channel_input.strip()


async def make_request(
    session: aiohttp.ClientSession,
    url: str,
    method: str = "GET",
    headers: Optional[Dict] = None,
    params: Optional[Dict] = None,
    json_data: Optional[Dict] = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    proxy: Optional[str] = None
) -> Tuple[aiohttp.ClientResponse, bytes]:
    """
    发送HTTP请求，带重试机制。

    参数:
        session: aiohttp会话
        url: 请求URL
        method: HTTP方法 (GET, POST等)
        headers: 请求头
        params: URL参数
        json_data: JSON数据 (用于POST请求)
        max_retries: 最大重试次数
        proxy: 代理URL

    返回:
        响应对象和响应内容
    """
    retries = 0
    last_error = None

    # 准备请求参数
    kwargs = {
        'headers': headers,
        'params': params,
    }
    if proxy:
        kwargs['proxy'] = proxy

    while retries <= max_retries:
        try:
            if method.upper() == "GET":
                async with session.get(url, **kwargs) as response:
                    if response.status == 429:  # 速率限制
                        retry_after = int(response.headers.get('Retry-After', DEFAULT_RETRY_DELAY))
                        logger.warning(f"速率限制，等待 {retry_after} 秒后重试...")
                        await asyncio.sleep(retry_after)
                        retries += 1
                        continue
                    elif response.status >= 500:  # 服务器错误
                        logger.warning(f"服务器错误 ({response.status})，重试中...")
                        await asyncio.sleep(DEFAULT_RETRY_DELAY * (retries + 1))  # 指数退避
                        retries += 1
                        continue
                    elif response.status == 401:  # 未授权
                        logger.error(f"未授权错误 (401)，请检查您的Discord令牌是否有效")
                        raise Exception("Discord令牌无效或已过期")
                    elif response.status == 403:  # 禁止访问
                        logger.error(f"禁止访问错误 (403)，您可能没有权限访问此资源")
                        raise Exception("没有权限访问此资源")

                    # 预先读取响应内容，避免连接关闭问题
                    try:
                        content = await response.read()
                        return response, content
                    except Exception as e:
                        logger.warning(f"读取响应内容时出错: {str(e)}，重试中...")
                        await asyncio.sleep(DEFAULT_RETRY_DELAY * (retries + 1))
                        retries += 1
                        last_error = e
                        continue

            elif method.upper() == "POST":
                post_kwargs = {**kwargs, 'json': json_data}
                async with session.post(url, **post_kwargs) as response:
                    if response.status == 429:  # 速率限制
                        retry_after = int(response.headers.get('Retry-After', DEFAULT_RETRY_DELAY))
                        logger.warning(f"速率限制，等待 {retry_after} 秒后重试...")
                        await asyncio.sleep(retry_after)
                        retries += 1
                        continue
                    elif response.status >= 500:  # 服务器错误
                        logger.warning(f"服务器错误 ({response.status})，重试中...")
                        await asyncio.sleep(DEFAULT_RETRY_DELAY * (retries + 1))  # 指数退避
                        retries += 1
                        continue
                    elif response.status == 401:  # 未授权
                        logger.error(f"未授权错误 (401)，请检查您的Discord令牌是否有效")
                        raise Exception("Discord令牌无效或已过期")
                    elif response.status == 403:  # 禁止访问
                        logger.error(f"禁止访问错误 (403)，您可能没有权限访问此资源")
                        raise Exception("没有权限访问此资源")

                    # 预先读取响应内容，避免连接关闭问题
                    try:
                        content = await response.read()
                        return response, content
                    except Exception as e:
                        logger.warning(f"读取响应内容时出错: {str(e)}，重试中...")
                        await asyncio.sleep(DEFAULT_RETRY_DELAY * (retries + 1))
                        retries += 1
                        last_error = e
                        continue

        except aiohttp.ClientConnectorError as e:
            logger.warning(f"连接错误: {str(e)}，重试中...")
            await asyncio.sleep(DEFAULT_RETRY_DELAY * (retries + 1))
            retries += 1
            last_error = e
            continue
        except aiohttp.ClientOSError as e:
            logger.warning(f"操作系统错误: {str(e)}，重试中...")
            await asyncio.sleep(DEFAULT_RETRY_DELAY * (retries + 1))
            retries += 1
            last_error = e
            continue
        except aiohttp.ServerDisconnectedError as e:
            logger.warning(f"服务器断开连接: {str(e)}，重试中...")
            await asyncio.sleep(DEFAULT_RETRY_DELAY * (retries + 1))
            retries += 1
            last_error = e
            continue
        except asyncio.TimeoutError as e:
            logger.warning(f"请求超时: {str(e)}，重试中...")
            await asyncio.sleep(DEFAULT_RETRY_DELAY * (retries + 1))
            retries += 1
            last_error = e
            continue
        except Exception as e:
            logger.warning(f"未知错误: {str(e)}，重试中...")
            await asyncio.sleep(DEFAULT_RETRY_DELAY * (retries + 1))
            retries += 1
            last_error = e
            if retries > max_retries:
                raise

    # 如果所有重试都失败
    if last_error:
        raise Exception(f"请求失败，已达到最大重试次数 ({max_retries}): {str(last_error)}")
    else:
        raise Exception(f"请求失败，已达到最大重试次数 ({max_retries})")


async def create_client_session(
    connection_pool_size: int = 10,
    timeout: int = 60
) -> aiohttp.ClientSession:
    """
    创建一个配置了连接池和超时的aiohttp会话。

    参数:
        connection_pool_size: 最大连接数（默认: 10）
        timeout: 总超时时间，秒（默认: 60）

    返回:
        配置好的aiohttp.ClientSession对象
    """
    # 配置连接池
    conn = aiohttp.TCPConnector(
        limit=connection_pool_size,
        ttl_dns_cache=300,  # DNS缓存时间（秒）
        ssl=False,  # 禁用SSL验证以提高性能
        force_close=False  # 允许连接重用
    )

    # 配置超时
    client_timeout = aiohttp.ClientTimeout(
        total=timeout,
        connect=10,  # 连接超时
        sock_connect=10,  # 套接字连接超时
        sock_read=30  # 套接字读取超时
    )

    # 创建会话
    return aiohttp.ClientSession(
        connector=conn,
        timeout=client_timeout,
        headers={
            'User-Agent': USER_AGENT
        }
    )
