"""Alert dispatcher for multi-channel delivery.

Handles parallel delivery to multiple notification channels with
failure isolation and severity-based routing.
"""

import asyncio
import logging
from dataclasses import dataclass, field

from .channels.base import BaseChannel, ChannelResult
from .models import Alert, DeliveryStatus

logger = logging.getLogger(__name__)


@dataclass
class DispatchResult:
    """Result of dispatching an alert to multiple channels."""

    delivery_status: DeliveryStatus
    channels_sent: list[str] = field(default_factory=list)
    channels_failed: list[str] = field(default_factory=list)
    error_message: str | None = None


class AlertDispatcher:
    """Dispatches alerts to multiple notification channels.

    Supports:
    - Parallel delivery to all enabled channels
    - Failure isolation (one channel failing doesn't affect others)
    - Timeout handling for slow channels
    - Severity-based routing (optional)
    """

    def __init__(
        self,
        channels: list[BaseChannel],
        timeout: float = 30.0,
        severity_filters: dict[str, list[str]] | None = None,
    ):
        """Initialize the dispatcher.

        Args:
            channels: List of notification channels
            timeout: Per-channel timeout in seconds
            severity_filters: Optional dict mapping channel names to allowed severity levels
                            e.g., {"email": ["critical"], "discord": ["critical", "warning", "info"]}
        """
        self.channels = channels
        self.timeout = timeout
        self.severity_filters = severity_filters or {}

    async def dispatch(self, alert: Alert) -> DispatchResult:
        """Dispatch an alert to all enabled channels.

        Args:
            alert: The alert to dispatch

        Returns:
            DispatchResult with delivery status and channel details
        """
        # Filter channels by severity if configured
        channels_to_send = self._filter_channels_by_severity(alert)

        if not channels_to_send:
            logger.info("No channels matched severity filter")
            return DispatchResult(
                delivery_status=DeliveryStatus.SUCCESS,
                channels_sent=[],
                channels_failed=[],
            )

        # Send to all channels in parallel with timeout
        tasks = []
        for channel in channels_to_send:
            task = self._send_with_timeout(channel, alert)
            tasks.append((channel.name, task))

        # Gather results
        results: list[tuple[str, ChannelResult | None]] = []
        gathered = await asyncio.gather(
            *[t[1] for t in tasks],
            return_exceptions=True,
        )

        for (channel_name, _), result in zip(tasks, gathered):
            if isinstance(result, Exception):
                logger.error(f"Channel {channel_name} raised exception: {result}")
                results.append((channel_name, None))
            else:
                results.append((channel_name, result))

        # Categorize results
        channels_sent = []
        channels_failed = []

        for channel_name, result in results:
            if result is not None and result.success:
                channels_sent.append(channel_name)
            else:
                channels_failed.append(channel_name)
                if result is not None:
                    logger.warning(f"Channel {channel_name} failed: {result.error_message}")

        # Determine overall delivery status
        delivery_status = self._determine_status(channels_sent, channels_failed)

        error_message = None
        if delivery_status == DeliveryStatus.FAILED:
            error_message = f"All channels failed: {', '.join(channels_failed)}"

        return DispatchResult(
            delivery_status=delivery_status,
            channels_sent=channels_sent,
            channels_failed=channels_failed,
            error_message=error_message,
        )

    def _filter_channels_by_severity(self, alert: Alert) -> list[BaseChannel]:
        """Filter channels based on severity configuration.

        Args:
            alert: The alert to check severity for

        Returns:
            List of channels that should receive this alert
        """
        if not self.severity_filters:
            return self.channels

        filtered = []
        severity_str = alert.severity.value.lower()

        for channel in self.channels:
            allowed = self.severity_filters.get(channel.name)
            if allowed is None:
                # No filter configured, include channel
                filtered.append(channel)
            elif severity_str in allowed:
                filtered.append(channel)
            else:
                logger.debug(
                    f"Skipping channel {channel.name}: severity {severity_str} not in {allowed}"
                )

        return filtered

    async def _send_with_timeout(
        self,
        channel: BaseChannel,
        alert: Alert,
    ) -> ChannelResult:
        """Send to a channel with timeout handling.

        Args:
            channel: The channel to send to
            alert: The alert to send

        Returns:
            ChannelResult (may indicate timeout failure)
        """
        try:
            return await asyncio.wait_for(
                channel.send(alert),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            logger.error(f"Channel {channel.name} timed out after {self.timeout}s")
            return ChannelResult(
                success=False,
                channel_name=channel.name,
                error_message=f"Timeout after {self.timeout}s",
            )
        except Exception as e:
            logger.error(f"Channel {channel.name} error: {e}")
            return ChannelResult(
                success=False,
                channel_name=channel.name,
                error_message=str(e),
            )

    @staticmethod
    def _determine_status(
        channels_sent: list[str],
        channels_failed: list[str],
    ) -> DeliveryStatus:
        """Determine overall delivery status.

        Args:
            channels_sent: List of successful channel names
            channels_failed: List of failed channel names

        Returns:
            DeliveryStatus based on success/failure counts
        """
        total = len(channels_sent) + len(channels_failed)

        if total == 0:
            return DeliveryStatus.SUCCESS

        if len(channels_sent) == total:
            return DeliveryStatus.SUCCESS

        if len(channels_sent) == 0:
            return DeliveryStatus.FAILED

        return DeliveryStatus.PARTIAL
