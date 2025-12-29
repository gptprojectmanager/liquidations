"""Unit tests for notification channels.

Tests for:
- Discord webhook client
- Telegram bot client
- Email SMTP client
- Message formatter
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.liquidationheatmap.alerts.models import (
    Alert,
    AlertSeverity,
)


class TestDiscordClient:
    """Tests for Discord webhook client."""

    @pytest.mark.asyncio
    async def test_discord_sends_embed(self) -> None:
        """Discord client should send proper embed format."""
        from src.liquidationheatmap.alerts.channels.discord import DiscordChannel

        mock_response = MagicMock()
        mock_response.status_code = 204  # Discord returns 204 on success
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        alert = Alert(
            symbol="BTCUSDT",
            current_price=Decimal("94500"),
            zone_price=Decimal("94000"),
            zone_density=Decimal("15000000"),
            zone_side="short",
            distance_pct=Decimal("0.53"),
            severity=AlertSeverity.CRITICAL,
        )

        with patch(
            "src.liquidationheatmap.alerts.channels.discord.httpx.AsyncClient"
        ) as mock_class:
            mock_class.return_value.__aenter__.return_value = mock_client
            mock_class.return_value.__aexit__.return_value = None

            channel = DiscordChannel(webhook_url="https://discord.com/api/webhooks/123/abc")
            result = await channel.send(alert)

        assert result.success is True
        assert result.channel_name == "discord"

        # Verify embed structure was sent
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get(
            "json", call_args.args[1] if len(call_args.args) > 1 else None
        )
        assert "embeds" in payload

    @pytest.mark.asyncio
    async def test_discord_handles_failure(self) -> None:
        """Discord client should handle API failures gracefully."""
        from src.liquidationheatmap.alerts.channels.discord import DiscordChannel

        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection failed")

        alert = Alert(severity=AlertSeverity.CRITICAL)

        with patch(
            "src.liquidationheatmap.alerts.channels.discord.httpx.AsyncClient"
        ) as mock_class:
            mock_class.return_value.__aenter__.return_value = mock_client
            mock_class.return_value.__aexit__.return_value = None

            channel = DiscordChannel(webhook_url="https://discord.com/api/webhooks/123/abc")
            result = await channel.send(alert)

        assert result.success is False
        assert "Connection failed" in result.error_message

    @pytest.mark.asyncio
    async def test_discord_color_matches_severity(self) -> None:
        """Discord embed color should match alert severity."""
        from src.liquidationheatmap.alerts.channels.discord import DiscordChannel

        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        alert = Alert(severity=AlertSeverity.WARNING)

        with patch(
            "src.liquidationheatmap.alerts.channels.discord.httpx.AsyncClient"
        ) as mock_class:
            mock_class.return_value.__aenter__.return_value = mock_client
            mock_class.return_value.__aexit__.return_value = None

            channel = DiscordChannel(webhook_url="https://discord.com/api/webhooks/123/abc")
            await channel.send(alert)

        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json", {})
        embed = payload.get("embeds", [{}])[0]
        # WARNING should be orange (0xFFA500)
        assert embed.get("color") == 0xFFA500


class TestTelegramClient:
    """Tests for Telegram bot client."""

    @pytest.mark.asyncio
    async def test_telegram_sends_message(self) -> None:
        """Telegram client should send message via Bot API."""
        from src.liquidationheatmap.alerts.channels.telegram import TelegramChannel

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        alert = Alert(
            symbol="BTCUSDT",
            current_price=Decimal("94500"),
            zone_price=Decimal("94000"),
            severity=AlertSeverity.CRITICAL,
        )

        with patch(
            "src.liquidationheatmap.alerts.channels.telegram.httpx.AsyncClient"
        ) as mock_class:
            mock_class.return_value.__aenter__.return_value = mock_client
            mock_class.return_value.__aexit__.return_value = None

            channel = TelegramChannel(bot_token="123:ABC", chat_id="@mychannel")
            result = await channel.send(alert)

        assert result.success is True
        assert result.channel_name == "telegram"

    @pytest.mark.asyncio
    async def test_telegram_handles_failure(self) -> None:
        """Telegram client should handle API failures gracefully."""
        from src.liquidationheatmap.alerts.channels.telegram import TelegramChannel

        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection failed")

        alert = Alert(severity=AlertSeverity.CRITICAL)

        with patch(
            "src.liquidationheatmap.alerts.channels.telegram.httpx.AsyncClient"
        ) as mock_class:
            mock_class.return_value.__aenter__.return_value = mock_client
            mock_class.return_value.__aexit__.return_value = None

            channel = TelegramChannel(bot_token="123:ABC", chat_id="@mychannel")
            result = await channel.send(alert)

        assert result.success is False

    @pytest.mark.asyncio
    async def test_telegram_uses_markdown(self) -> None:
        """Telegram message should use Markdown formatting."""
        from src.liquidationheatmap.alerts.channels.telegram import TelegramChannel

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        alert = Alert(severity=AlertSeverity.CRITICAL)

        with patch(
            "src.liquidationheatmap.alerts.channels.telegram.httpx.AsyncClient"
        ) as mock_class:
            mock_class.return_value.__aenter__.return_value = mock_client
            mock_class.return_value.__aexit__.return_value = None

            channel = TelegramChannel(bot_token="123:ABC", chat_id="@mychannel")
            await channel.send(alert)

        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json", {})
        assert payload.get("parse_mode") == "Markdown"


class TestEmailClient:
    """Tests for Email SMTP client."""

    @pytest.mark.asyncio
    async def test_email_sends_message(self) -> None:
        """Email client should send via SMTP."""
        from src.liquidationheatmap.alerts.channels.email import EmailChannel

        alert = Alert(
            symbol="BTCUSDT",
            current_price=Decimal("94500"),
            zone_price=Decimal("94000"),
            severity=AlertSeverity.CRITICAL,
        )

        with patch("src.liquidationheatmap.alerts.channels.email.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            channel = EmailChannel(
                smtp_host="smtp.example.com",
                smtp_port=587,
                recipients=["test@example.com"],
            )
            result = await channel.send(alert)

        assert result.success is True
        assert result.channel_name == "email"
        mock_server.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_email_handles_smtp_failure(self) -> None:
        """Email client should handle SMTP failures gracefully."""
        from src.liquidationheatmap.alerts.channels.email import EmailChannel

        alert = Alert(severity=AlertSeverity.CRITICAL)

        with patch("src.liquidationheatmap.alerts.channels.email.smtplib.SMTP") as mock_smtp:
            mock_smtp.side_effect = Exception("SMTP connection failed")

            channel = EmailChannel(
                smtp_host="smtp.example.com",
                smtp_port=587,
                recipients=["test@example.com"],
            )
            result = await channel.send(alert)

        assert result.success is False
        assert "SMTP" in result.error_message or "connection" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_email_subject_includes_severity(self) -> None:
        """Email subject should include severity level."""
        from src.liquidationheatmap.alerts.channels.email import EmailChannel

        alert = Alert(
            symbol="BTCUSDT",
            zone_price=Decimal("94000"),
            distance_pct=Decimal("0.53"),
            severity=AlertSeverity.CRITICAL,
        )

        with patch("src.liquidationheatmap.alerts.channels.email.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            channel = EmailChannel(
                smtp_host="smtp.example.com",
                smtp_port=587,
                recipients=["test@example.com"],
            )
            await channel.send(alert)

        # Check the message that was sent
        call_args = mock_server.send_message.call_args
        msg = call_args.args[0]
        assert "CRITICAL" in msg["Subject"]


class TestMessageFormatter:
    """Tests for message formatter."""

    def test_format_discord_embed(self) -> None:
        """Discord formatter should create proper embed structure."""
        from src.liquidationheatmap.alerts.formatter import format_discord_embed

        alert = Alert(
            symbol="BTCUSDT",
            current_price=Decimal("94500"),
            zone_price=Decimal("94000"),
            zone_density=Decimal("15000000"),
            zone_side="short",
            distance_pct=Decimal("0.53"),
            severity=AlertSeverity.CRITICAL,
        )

        embed = format_discord_embed(alert)

        assert "title" in embed
        assert "CRITICAL" in embed["title"]
        assert "fields" in embed
        assert embed["color"] == 0xFF0000  # Red for critical

    def test_format_telegram_message(self) -> None:
        """Telegram formatter should create Markdown message."""
        from src.liquidationheatmap.alerts.formatter import format_telegram_message

        alert = Alert(
            symbol="BTCUSDT",
            current_price=Decimal("94500"),
            zone_price=Decimal("94000"),
            zone_density=Decimal("15000000"),
            zone_side="short",
            distance_pct=Decimal("0.53"),
            severity=AlertSeverity.CRITICAL,
        )

        message = format_telegram_message(alert)

        assert "*" in message  # Markdown bold
        assert "CRITICAL" in message
        assert "BTCUSDT" in message

    def test_format_email_html(self) -> None:
        """Email formatter should create HTML message."""
        from src.liquidationheatmap.alerts.formatter import format_email_html

        alert = Alert(
            symbol="BTCUSDT",
            current_price=Decimal("94500"),
            zone_price=Decimal("94000"),
            severity=AlertSeverity.CRITICAL,
        )

        subject, body = format_email_html(alert)

        assert "CRITICAL" in subject
        assert "<html>" in body or "<table>" in body or "CRITICAL" in body
