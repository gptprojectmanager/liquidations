"""
Tests for email_handler.py - Email notification handler.

Tests cover:
- Email configuration
- HTML email body generation
- Subject line formatting
- SMTP connection handling
- Error handling
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from src.validation.alerts.email_handler import EmailHandler


class TestEmailHandler:
    """Test EmailHandler functionality."""

    def test_initialization_with_defaults(self):
        """EmailHandler should initialize with default values."""
        # Act
        handler = EmailHandler()

        # Assert
        assert handler.smtp_host == "localhost"
        assert handler.smtp_port == 587
        assert handler.from_email == "validation@liquidationheatmap.local"
        assert handler.use_tls is True

    def test_initialization_with_custom_values(self):
        """EmailHandler should accept custom configuration."""
        # Act
        handler = EmailHandler(
            smtp_host="smtp.example.com",
            smtp_port=465,
            smtp_user="user@example.com",
            smtp_password="secret",
            from_email="alerts@example.com",
            to_emails=["admin@example.com"],
            use_tls=False,
        )

        # Assert
        assert handler.smtp_host == "smtp.example.com"
        assert handler.smtp_port == 465
        assert handler.smtp_user == "user@example.com"
        assert handler.smtp_password == "secret"
        assert handler.from_email == "alerts@example.com"
        assert handler.to_emails == ["admin@example.com"]
        assert handler.use_tls is False

    def test_build_subject_for_grade_f(self):
        """Subject should indicate CRITICAL for grade F."""
        # Arrange
        handler = EmailHandler()
        alert_context = {
            "grade": "F",
            "model_name": "test_model",
            "run_id": "test-run-1",
        }

        # Act
        subject = handler._build_subject(alert_context)

        # Assert
        assert "🚨" in subject  # F grade uses alarm emoji
        assert "test_model" in subject
        assert "F" in subject

    def test_build_subject_for_grade_c(self):
        """Subject should indicate WARNING for grade C."""
        # Arrange
        handler = EmailHandler()
        alert_context = {
            "grade": "C",
            "model_name": "test_model",
            "run_id": "test-run-2",
        }

        # Act
        subject = handler._build_subject(alert_context)

        # Assert
        assert "⚠️" in subject  # C grade uses warning emoji
        assert "test_model" in subject
        assert "C" in subject

    def test_build_body_contains_essential_information(self):
        """Email body should include all critical alert details."""
        # Arrange
        handler = EmailHandler()
        alert_context = {
            "run_id": "test-run-3",
            "model_name": "test_model",
            "grade": "F",
            "score": Decimal("45.0"),
            "status": "completed",
            "started_at": datetime(2025, 11, 27, 10, 0, 0),
            "completed_at": datetime(2025, 11, 27, 10, 5, 0),
            "duration_seconds": 300.0,
            "test_details": [
                {
                    "name": "funding_correlation",
                    "score": 40.0,
                    "passed": False,
                    "weight": 0.33,
                    "error": "Correlation below threshold",
                }
            ],
        }

        # Act
        body = handler._build_body(alert_context)

        # Assert
        assert "test-run-3" in body
        assert "test_model" in body
        assert "F" in body or "45" in body
        assert "funding_correlation" in body
        assert "<html>" in body or "<body>" in body  # HTML format

    def test_build_body_handles_missing_completed_at(self):
        """Email body should handle runs without completed_at."""
        # Arrange
        handler = EmailHandler()
        alert_context = {
            "run_id": "test-run-4",
            "model_name": "test_model",
            "grade": "C",
            "score": Decimal("75.0"),
            "status": "running",
            "started_at": datetime(2025, 11, 27, 10, 0, 0),
            "completed_at": None,
            "duration_seconds": None,
            "tests": [],
        }

        # Act
        body = handler._build_body(alert_context)

        # Assert
        assert "test-run-4" in body
        assert body is not None

    @patch("smtplib.SMTP")
    def test_send_email_succeeds_with_valid_smtp(self, mock_smtp):
        """Email should send successfully with valid SMTP."""
        # Arrange
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        handler = EmailHandler(
            smtp_host="smtp.test.com",
            smtp_port=587,
            to_emails=["test@example.com"],
        )

        # Act
        result = handler._send_email("Test Subject", "Test Body")

        # Assert
        assert result is True
        mock_server.send_message.assert_called_once()

    @patch("smtplib.SMTP")
    def test_send_email_with_tls_enabled(self, mock_smtp):
        """Email should use TLS when enabled."""
        # Arrange
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        handler = EmailHandler(
            smtp_host="smtp.test.com",
            use_tls=True,
            to_emails=["test@example.com"],
        )

        # Act
        handler._send_email("Test", "Body")

        # Assert
        mock_server.starttls.assert_called_once()

    @patch("smtplib.SMTP")
    def test_send_email_with_authentication(self, mock_smtp):
        """Email should authenticate when credentials provided."""
        # Arrange
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        handler = EmailHandler(
            smtp_user="user@test.com",
            smtp_password="password123",
            to_emails=["test@example.com"],
        )

        # Act
        handler._send_email("Test", "Body")

        # Assert
        mock_server.login.assert_called_once_with("user@test.com", "password123")

    @patch("smtplib.SMTP")
    def test_send_email_handles_smtp_exception(self, mock_smtp):
        """Email should handle SMTP exceptions gracefully."""
        # Arrange
        mock_smtp.side_effect = Exception("SMTP connection failed")

        handler = EmailHandler(to_emails=["test@example.com"])

        # Act
        result = handler._send_email("Test", "Body")

        # Assert
        assert result is False

    def test_send_alert_builds_and_sends_email(self):
        """send_alert should build email from context and send."""
        # Arrange
        with patch.object(EmailHandler, "_send_email", return_value=True) as mock_send:
            handler = EmailHandler(to_emails=["test@example.com"])

            alert_context = {
                "run_id": "test-run-5",
                "model_name": "test_model",
                "grade": "F",
                "score": Decimal("30.0"),
                "status": "completed",
                "started_at": datetime.utcnow(),
                "completed_at": datetime.utcnow(),
                "duration_seconds": 120.0,
                "tests": [],
            }

            # Act
            result = handler.send_alert(alert_context)

            # Assert
            assert result is True
            mock_send.assert_called_once()
            args = mock_send.call_args[0]
            assert len(args) == 2  # subject, body
            assert "test_model" in args[0]  # subject

    def test_send_alert_without_recipients_returns_false(self):
        """send_alert should return False when no recipients configured."""
        # Arrange
        handler = EmailHandler(to_emails=[])
        alert_context = {
            "run_id": "test-run-6",
            "model_name": "test_model",
            "grade": "F",
            "score": Decimal("40.0"),
            "status": "completed",
            "started_at": datetime.utcnow(),
            "tests": [],
        }

        # Act
        result = handler.send_alert(alert_context)

        # Assert
        assert result is False

    def test_html_body_includes_css_styling(self):
        """HTML email body should include CSS for styling."""
        # Arrange
        handler = EmailHandler()
        alert_context = {
            "run_id": "test-run-7",
            "model_name": "test_model",
            "grade": "F",
            "score": Decimal("50.0"),
            "status": "completed",
            "started_at": datetime.utcnow(),
            "tests": [],
        }

        # Act
        body = handler._build_body(alert_context)

        # Assert
        assert "<style>" in body or "style=" in body

    def test_email_includes_all_test_results(self):
        """Email body should list all test results."""
        # Arrange
        handler = EmailHandler()
        alert_context = {
            "run_id": "test-run-8",
            "model_name": "test_model",
            "grade": "C",
            "score": Decimal("72.0"),
            "status": "completed",
            "started_at": datetime.utcnow(),
            "test_details": [
                {"name": "funding_correlation", "score": 70.0, "passed": True, "weight": 0.33},
                {"name": "oi_conservation", "score": 65.0, "passed": False, "weight": 0.33},
                {"name": "directional_positioning", "score": 80.0, "passed": True, "weight": 0.34},
            ],
        }

        # Act
        body = handler._build_body(alert_context)

        # Assert
        assert "funding_correlation" in body
        assert "oi_conservation" in body
        assert "directional_positioning" in body
