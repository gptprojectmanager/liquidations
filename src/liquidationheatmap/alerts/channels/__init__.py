"""Notification channel implementations.

Supported channels:
- Discord: Webhook-based notifications with embeds
- Telegram: Bot API notifications with Markdown
- Email: SMTP-based notifications with HTML
"""

from .base import BaseChannel, ChannelResult
from .discord import DiscordChannel
from .email import EmailChannel
from .telegram import TelegramChannel

__all__ = [
    "BaseChannel",
    "ChannelResult",
    "DiscordChannel",
    "EmailChannel",
    "TelegramChannel",
]
