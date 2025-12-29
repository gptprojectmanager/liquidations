"""Telegram bot notification channel.

Sends alerts to Telegram via Bot API with Markdown formatting.
"""

import logging

import httpx

from ..formatter import format_telegram_message
from ..models import Alert
from .base import BaseChannel, ChannelResult

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramChannel(BaseChannel):
    """Telegram bot notification channel."""

    def __init__(self, bot_token: str, chat_id: str, timeout: float = 10.0):
        """Initialize the Telegram channel.

        Args:
            bot_token: Telegram bot token from BotFather
            chat_id: Target chat/channel ID (can be @username for channels)
            timeout: Request timeout in seconds
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout = timeout

    @property
    def name(self) -> str:
        """Return channel name."""
        return "telegram"

    @property
    def api_url(self) -> str:
        """Return the Telegram API URL."""
        return f"{TELEGRAM_API_BASE}/bot{self.bot_token}"

    async def send(self, alert: Alert) -> ChannelResult:
        """Send an alert to Telegram via Bot API.

        Args:
            alert: The alert to send

        Returns:
            ChannelResult with success status
        """
        try:
            message = format_telegram_message(alert)
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown",
            }

            url = f"{self.api_url}/sendMessage"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.debug(f"Sending Telegram message to {self.chat_id}")
                response = await client.post(url, json=payload)
                response.raise_for_status()

                data = response.json()
                if not data.get("ok"):
                    error_msg = data.get("description", "Unknown Telegram error")
                    logger.error(f"Telegram API error: {error_msg}")
                    return ChannelResult(
                        success=False, channel_name=self.name, error_message=error_msg
                    )

            logger.info(f"Telegram alert sent successfully: {alert.severity.value}")
            return ChannelResult(success=True, channel_name=self.name)

        except httpx.HTTPError as e:
            error_msg = f"Telegram HTTP error: {e}"
            logger.error(error_msg)
            return ChannelResult(success=False, channel_name=self.name, error_message=error_msg)

        except Exception as e:
            error_msg = f"Telegram error: {e}"
            logger.error(error_msg)
            return ChannelResult(success=False, channel_name=self.name, error_message=str(e))

    async def test_connection(self) -> ChannelResult:
        """Test bot connectivity via getMe endpoint.

        Returns:
            ChannelResult indicating if connection is valid
        """
        try:
            url = f"{self.api_url}/getMe"
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                data = response.json()
                if data.get("ok", False):
                    return ChannelResult(success=True, channel_name=self.name)
                else:
                    return ChannelResult(
                        success=False,
                        channel_name=self.name,
                        error_message=data.get("description", "Unknown error"),
                    )
        except Exception as e:
            logger.warning(f"Telegram connection test failed: {e}")
            return ChannelResult(
                success=False,
                channel_name=self.name,
                error_message=str(e),
            )
