"""Unit tests for screenshot_parser module."""

from datetime import datetime

import pytest

from src.liquidationheatmap.validation.screenshot_parser import (
    Screenshot,
    parse_filename,
)


class TestParseFilename:
    """Tests for parse_filename function."""

    def test_parse_btc_filename(self):
        """Parse BTC screenshot filename correctly."""
        filename = "coinglass_btc_m1_1month_20251030_145708.png"
        result = parse_filename(filename)

        assert result["symbol"] == "BTC"
        assert result["leverage"] == "m1"
        assert result["timeframe"] == "1month"
        assert result["timestamp"] == datetime(2025, 10, 30, 14, 57, 8)

    def test_parse_eth_filename(self):
        """Parse ETH screenshot filename correctly."""
        filename = "coinglass_eth_m5_1week_20251115_083022.png"
        result = parse_filename(filename)

        assert result["symbol"] == "ETH"
        assert result["leverage"] == "m5"
        assert result["timeframe"] == "1week"
        assert result["timestamp"] == datetime(2025, 11, 15, 8, 30, 22)

    def test_parse_filename_case_insensitive(self):
        """Symbol is normalized to uppercase."""
        filename = "coinglass_BTC_m1_1month_20251030_145708.png"
        result = parse_filename(filename)

        assert result["symbol"] == "BTC"

    def test_parse_invalid_filename_format(self):
        """Raise ValueError on invalid filename format."""
        with pytest.raises(ValueError, match="Invalid filename format"):
            parse_filename("screenshot.png")

    def test_parse_invalid_filename_missing_parts(self):
        """Raise ValueError on filename with missing parts."""
        with pytest.raises(ValueError, match="Invalid filename format"):
            parse_filename("coinglass_btc_20251030.png")

    def test_parse_filename_with_path(self):
        """Parse filename from full path - extracts basename first."""
        # parse_filename only works on basename, so extract it first
        import os

        full_path = "/path/to/screenshots/coinglass_btc_m1_1month_20251030_145708.png"
        filename = os.path.basename(full_path)
        result = parse_filename(filename)

        assert result["symbol"] == "BTC"


class TestScreenshot:
    """Tests for Screenshot dataclass."""

    def test_from_path_creates_valid_screenshot(self, tmp_path):
        """Create Screenshot from valid path."""
        # Create a valid PNG file
        from PIL import Image

        screenshot_file = tmp_path / "coinglass_btc_m1_1month_20251030_145708.png"
        img = Image.new("RGB", (100, 100), color="white")
        img.save(str(screenshot_file), "PNG")

        screenshot = Screenshot.from_path(str(screenshot_file))

        assert screenshot.symbol == "BTC"
        assert screenshot.leverage == "m1"
        assert screenshot.timeframe == "1month"
        assert screenshot.timestamp == datetime(2025, 10, 30, 14, 57, 8)
        assert screenshot.path == str(screenshot_file)

    def test_from_path_raises_on_nonexistent_file(self):
        """Raise FileNotFoundError for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            Screenshot.from_path("/nonexistent/path/screenshot.png")

    def test_screenshot_filename_property(self, tmp_path):
        """filename property returns just the filename."""
        from PIL import Image

        screenshot_file = tmp_path / "coinglass_btc_m1_1month_20251030_145708.png"
        img = Image.new("RGB", (100, 100), color="white")
        img.save(str(screenshot_file), "PNG")

        screenshot = Screenshot.from_path(str(screenshot_file))

        assert screenshot.filename == "coinglass_btc_m1_1month_20251030_145708.png"


class TestFilenamePatterns:
    """Test various filename patterns."""

    @pytest.mark.parametrize(
        "filename,expected_symbol,expected_leverage",
        [
            ("coinglass_btc_m1_1month_20251030_145708.png", "BTC", "m1"),
            ("coinglass_btc_m5_1month_20251030_145708.png", "BTC", "m5"),
            ("coinglass_btc_m10_1month_20251030_145708.png", "BTC", "m10"),
            ("coinglass_eth_m1_1week_20251030_145708.png", "ETH", "m1"),
        ],
    )
    def test_various_filename_patterns(self, filename, expected_symbol, expected_leverage):
        """Parse various valid filename patterns."""
        result = parse_filename(filename)

        assert result["symbol"] == expected_symbol
        assert result["leverage"] == expected_leverage
