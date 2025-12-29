"""Unit tests for alert dispatcher.

Tests for:
- Parallel delivery to multiple channels
- Channel failure isolation
- Delivery status tracking
- Severity-based routing
"""

from unittest.mock import AsyncMock

import pytest

from src.liquidationheatmap.alerts.channels.base import ChannelResult
from src.liquidationheatmap.alerts.models import (
    Alert,
    AlertSeverity,
    DeliveryStatus,
)


class TestAlertDispatcher:
    """Tests for AlertDispatcher class."""

    @pytest.mark.asyncio
    async def test_dispatcher_sends_to_all_enabled_channels(self) -> None:
        """Dispatcher should send to all enabled channels in parallel."""
        from src.liquidationheatmap.alerts.dispatcher import AlertDispatcher

        # Create mock channels
        discord_channel = AsyncMock()
        discord_channel.name = "discord"
        discord_channel.send.return_value = ChannelResult(success=True, channel_name="discord")

        telegram_channel = AsyncMock()
        telegram_channel.name = "telegram"
        telegram_channel.send.return_value = ChannelResult(success=True, channel_name="telegram")

        alert = Alert(severity=AlertSeverity.CRITICAL)

        dispatcher = AlertDispatcher(channels=[discord_channel, telegram_channel])
        result = await dispatcher.dispatch(alert)

        # Both channels should have been called
        discord_channel.send.assert_called_once_with(alert)
        telegram_channel.send.assert_called_once_with(alert)

        assert result.delivery_status == DeliveryStatus.SUCCESS
        assert "discord" in result.channels_sent
        assert "telegram" in result.channels_sent

    @pytest.mark.asyncio
    async def test_dispatcher_isolates_channel_failures(self) -> None:
        """Dispatcher should isolate failures - one failure shouldn't stop others."""
        from src.liquidationheatmap.alerts.dispatcher import AlertDispatcher

        # Discord fails
        discord_channel = AsyncMock()
        discord_channel.name = "discord"
        discord_channel.send.return_value = ChannelResult(
            success=False,
            channel_name="discord",
            error_message="Webhook failed",
        )

        # Telegram succeeds
        telegram_channel = AsyncMock()
        telegram_channel.name = "telegram"
        telegram_channel.send.return_value = ChannelResult(success=True, channel_name="telegram")

        alert = Alert(severity=AlertSeverity.CRITICAL)

        dispatcher = AlertDispatcher(channels=[discord_channel, telegram_channel])
        result = await dispatcher.dispatch(alert)

        # Status should be PARTIAL (some succeeded, some failed)
        assert result.delivery_status == DeliveryStatus.PARTIAL
        assert "telegram" in result.channels_sent
        assert "discord" not in result.channels_sent

    @pytest.mark.asyncio
    async def test_dispatcher_returns_failed_when_all_fail(self) -> None:
        """Dispatcher should return FAILED when all channels fail."""
        from src.liquidationheatmap.alerts.dispatcher import AlertDispatcher

        discord_channel = AsyncMock()
        discord_channel.name = "discord"
        discord_channel.send.return_value = ChannelResult(
            success=False,
            channel_name="discord",
            error_message="Webhook failed",
        )

        telegram_channel = AsyncMock()
        telegram_channel.name = "telegram"
        telegram_channel.send.return_value = ChannelResult(
            success=False,
            channel_name="telegram",
            error_message="API error",
        )

        alert = Alert(severity=AlertSeverity.CRITICAL)

        dispatcher = AlertDispatcher(channels=[discord_channel, telegram_channel])
        result = await dispatcher.dispatch(alert)

        assert result.delivery_status == DeliveryStatus.FAILED
        assert len(result.channels_sent) == 0
        assert result.error_message is not None


class TestChannelIsolation:
    """Tests for channel failure isolation."""

    @pytest.mark.asyncio
    async def test_exception_in_one_channel_doesnt_affect_others(self) -> None:
        """Exception in one channel should not prevent others from running."""
        from src.liquidationheatmap.alerts.dispatcher import AlertDispatcher

        # Discord throws exception
        discord_channel = AsyncMock()
        discord_channel.name = "discord"
        discord_channel.send.side_effect = Exception("Unexpected error")

        # Telegram succeeds
        telegram_channel = AsyncMock()
        telegram_channel.name = "telegram"
        telegram_channel.send.return_value = ChannelResult(success=True, channel_name="telegram")

        alert = Alert(severity=AlertSeverity.CRITICAL)

        dispatcher = AlertDispatcher(channels=[discord_channel, telegram_channel])
        result = await dispatcher.dispatch(alert)

        # Telegram should still succeed
        assert "telegram" in result.channels_sent
        assert result.delivery_status == DeliveryStatus.PARTIAL

    @pytest.mark.asyncio
    async def test_timeout_in_one_channel_doesnt_block_others(self) -> None:
        """Slow channel should not block other channels."""
        import asyncio

        from src.liquidationheatmap.alerts.dispatcher import AlertDispatcher

        async def slow_send(alert):
            await asyncio.sleep(5)  # Simulate slow channel
            return ChannelResult(success=True, channel_name="discord")

        # Discord is slow
        discord_channel = AsyncMock()
        discord_channel.name = "discord"
        discord_channel.send = slow_send

        # Telegram is fast
        telegram_channel = AsyncMock()
        telegram_channel.name = "telegram"
        telegram_channel.send.return_value = ChannelResult(success=True, channel_name="telegram")

        alert = Alert(severity=AlertSeverity.CRITICAL)

        # With timeout, slow channel should timeout
        dispatcher = AlertDispatcher(
            channels=[discord_channel, telegram_channel],
            timeout=0.1,
        )
        result = await dispatcher.dispatch(alert)

        # Telegram should succeed, discord should timeout
        assert "telegram" in result.channels_sent


class TestSeverityFilter:
    """Tests for severity-based channel routing."""

    @pytest.mark.asyncio
    async def test_severity_filter_routes_critical_only(self) -> None:
        """Channel with critical filter should only receive critical alerts."""
        from src.liquidationheatmap.alerts.dispatcher import AlertDispatcher

        # Discord receives all severities
        discord_channel = AsyncMock()
        discord_channel.name = "discord"
        discord_channel.send.return_value = ChannelResult(success=True, channel_name="discord")

        # Email receives critical only
        email_channel = AsyncMock()
        email_channel.name = "email"
        email_channel.send.return_value = ChannelResult(success=True, channel_name="email")

        alert = Alert(severity=AlertSeverity.WARNING)

        dispatcher = AlertDispatcher(
            channels=[discord_channel, email_channel],
            severity_filters={
                "discord": ["critical", "warning", "info"],
                "email": ["critical"],
            },
        )
        result = await dispatcher.dispatch(alert)

        # Discord should be called (WARNING allowed)
        discord_channel.send.assert_called_once()
        # Email should NOT be called (WARNING not in filter)
        email_channel.send.assert_not_called()

        assert "discord" in result.channels_sent
        assert "email" not in result.channels_sent

    @pytest.mark.asyncio
    async def test_severity_filter_allows_matching_severity(self) -> None:
        """Channel should receive alert when severity matches filter."""
        from src.liquidationheatmap.alerts.dispatcher import AlertDispatcher

        email_channel = AsyncMock()
        email_channel.name = "email"
        email_channel.send.return_value = ChannelResult(success=True, channel_name="email")

        alert = Alert(severity=AlertSeverity.CRITICAL)

        dispatcher = AlertDispatcher(
            channels=[email_channel],
            severity_filters={"email": ["critical"]},
        )
        result = await dispatcher.dispatch(alert)

        email_channel.send.assert_called_once()
        assert "email" in result.channels_sent
