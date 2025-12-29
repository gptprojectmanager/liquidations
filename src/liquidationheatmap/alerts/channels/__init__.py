"""Notification channel implementations.

Supported channels:
- Discord: Webhook-based notifications with embeds
- Telegram: Bot API notifications with Markdown
- Email: SMTP-based notifications with HTML
"""

from .base import BaseChannel, ChannelResult

__all__ = [
    "BaseChannel",
    "ChannelResult",
]
