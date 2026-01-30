import requests
import json


def send_text(webhook, content, mentioned_list=None, mentioned_mobile_list=None):
    """Send text message to WeCom bot.

    Args:
        webhook: WeCom bot webhook URL
        content: Message content
        mentioned_list: Optional list of userids to @mention
        mentioned_mobile_list: Optional list of phone numbers to @mention
    """
    header = {
        "Content-Type": "application/json",
        "Charset": "UTF-8"
    }
    data = {
        "msgtype": "text",
        "text": {
            "content": content,
            "mentioned_list": mentioned_list or [],
            "mentioned_mobile_list": mentioned_mobile_list or []
        }
    }
    data = json.dumps(data)
    return requests.post(url=webhook, data=data, headers=header)


def send_md(webhook, content):
    """Send markdown message to WeCom bot.

    Args:
        webhook: WeCom bot webhook URL
        content: Markdown content
    """
    header = {
        "Content-Type": "application/json",
        "Charset": "UTF-8"
    }
    data = {
        "msgtype": "markdown",
        "markdown": {
            "content": content
        }
    }
    data = json.dumps(data)
    return requests.post(url=webhook, data=data, headers=header)
