"""Email SMTP notification channel.

Sends alerts via SMTP with HTML formatting.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..formatter import format_email_html
from ..models import Alert
from .base import BaseChannel, ChannelResult

logger = logging.getLogger(__name__)


class EmailChannel(BaseChannel):
    """Email SMTP notification channel."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        recipients: list[str],
        sender: str | None = None,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
    ):
        """Initialize the Email channel.

        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            recipients: List of email addresses to send to
            sender: Sender email address (defaults to first recipient)
            username: SMTP authentication username
            password: SMTP authentication password
            use_tls: Whether to use STARTTLS
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.recipients = recipients
        self.sender = sender or (recipients[0] if recipients else "alerts@example.com")
        self.username = username
        self.password = password
        self.use_tls = use_tls

    @property
    def name(self) -> str:
        """Return channel name."""
        return "email"

    async def send(self, alert: Alert) -> ChannelResult:
        """Send an alert via email.

        Args:
            alert: The alert to send

        Returns:
            ChannelResult with success status
        """
        try:
            subject, html_body = format_email_html(alert)

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.sender
            msg["To"] = ", ".join(self.recipients)

            # Add HTML content
            html_part = MIMEText(html_body, "html")
            msg.attach(html_part)

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()

                if self.username and self.password:
                    server.login(self.username, self.password)

                server.send_message(msg)

            logger.info(f"Email alert sent successfully to {len(self.recipients)} recipients")
            return ChannelResult(success=True, channel_name=self.name)

        except smtplib.SMTPException as e:
            error_msg = f"SMTP error: {e}"
            logger.error(error_msg)
            return ChannelResult(success=False, channel_name=self.name, error_message=error_msg)

        except Exception as e:
            error_msg = f"Email error: {e}"
            logger.error(error_msg)
            return ChannelResult(success=False, channel_name=self.name, error_message=str(e))

    async def test_connection(self) -> bool:
        """Test SMTP connectivity.

        Returns:
            True if SMTP server is reachable
        """
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.noop()
                return True
        except Exception as e:
            logger.warning(f"Email connection test failed: {e}")
            return False
