"""Discord webhook notification channel.

Sends alerts to Discord via webhook with rich embed formatting.
"""

import logging

import httpx

from ..formatter import format_discord_embed
from ..models import Alert
from .base import BaseChannel, ChannelResult

logger = logging.getLogger(__name__)


class DiscordChannel(BaseChannel):
    """Discord webhook notification channel."""

    def __init__(self, webhook_url: str, timeout: float = 10.0):
        """Initialize the Discord channel.

        Args:
            webhook_url: Discord webhook URL
            timeout: Request timeout in seconds
        """
        self.webhook_url = webhook_url
        self.timeout = timeout

    @property
    def name(self) -> str:
        """Return channel name."""
        return "discord"

    async def send(self, alert: Alert) -> ChannelResult:
        """Send an alert to Discord via webhook.

        Args:
            alert: The alert to send

        Returns:
            ChannelResult with success status
        """
        try:
            embed = format_discord_embed(alert)
            payload = {"embeds": [embed]}

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.debug(f"Sending Discord webhook to {self.webhook_url[:50]}...")
                response = await client.post(self.webhook_url, json=payload)
                response.raise_for_status()

            logger.info(f"Discord alert sent successfully: {alert.severity.value}")
            return ChannelResult(success=True, channel_name=self.name)

        except httpx.HTTPError as e:
            error_msg = f"Discord HTTP error: {e}"
            logger.error(error_msg)
            return ChannelResult(success=False, channel_name=self.name, error_message=error_msg)

        except Exception as e:
            error_msg = f"Discord error: {e}"
            logger.error(error_msg)
            return ChannelResult(success=False, channel_name=self.name, error_message=str(e))

    async def test_connection(self) -> bool:
        """Test webhook connectivity.

        Returns:
            True if webhook is reachable
        """
        try:
            # Discord webhooks return info on GET
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.webhook_url)
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Discord connection test failed: {e}")
            return False
