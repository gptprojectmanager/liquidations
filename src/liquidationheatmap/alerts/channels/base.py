"""Base channel interface for alert notifications.

All notification channels must inherit from BaseChannel and
implement the send method.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ChannelResult:
    """Result of sending an alert through a channel.

    Attributes:
        success: Whether the send was successful
        channel_name: Name of the channel (discord, telegram, email)
        error_message: Error message if send failed
        response_data: Optional response data from the channel
    """

    success: bool
    channel_name: str
    error_message: str | None = None
    response_data: dict | None = None


class BaseChannel(ABC):
    """Base class for notification channels.

    All notification channels must inherit from this class and
    implement the send method.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the channel name."""
        ...

    @abstractmethod
    async def send(self, alert: "Alert") -> ChannelResult:  # noqa: F821
        """Send an alert through this channel.

        Args:
            alert: The alert to send

        Returns:
            ChannelResult indicating success or failure
        """
        ...

    @abstractmethod
    async def test_connection(self) -> ChannelResult:
        """Test the channel connection.

        Returns:
            ChannelResult indicating if connection is valid
        """
        ...
