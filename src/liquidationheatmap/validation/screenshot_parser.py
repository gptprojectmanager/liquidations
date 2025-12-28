"""Screenshot filename parser for Coinglass heatmap validation.

Parses Coinglass screenshot filenames to extract metadata:
- Symbol (BTC, ETH)
- Leverage (m1, m3, etc.)
- Timeframe (1month, 1week, etc.)
- Timestamp (datetime from filename)
"""

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from PIL import Image


def parse_filename(filename: str) -> dict[str, Any]:
    """Parse Coinglass screenshot filename into structured metadata.

    Args:
        filename: Screenshot filename, e.g., 'coinglass_btc_m1_1month_20251030_145708.png'

    Returns:
        dict with keys: symbol, leverage, timeframe, timestamp

    Raises:
        ValueError: If filename doesn't match expected pattern
    """
    pattern = r"coinglass_(\w+)_(\w+)_(\w+)_(\d{8})_(\d{6})\.png"
    match = re.match(pattern, filename)

    if not match:
        raise ValueError(
            f"Invalid filename format: {filename}. "
            f"Expected: coinglass_{{symbol}}_{{leverage}}_{{timeframe}}_YYYYMMDD_HHMMSS.png"
        )

    symbol, leverage, timeframe, date_str, time_str = match.groups()

    # Parse timestamp: YYYYMMDD_HHMMSS
    timestamp = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")

    return {
        "symbol": symbol.upper(),  # BTC or ETH
        "leverage": leverage,  # m1, m3, etc.
        "timeframe": timeframe,  # 1month, 1week, etc.
        "timestamp": timestamp,
    }


@dataclass
class Screenshot:
    """Coinglass heatmap screenshot metadata."""

    path: str  # Absolute file path
    filename: str  # e.g., "coinglass_btc_m1_1month_20251030_145708.png"
    symbol: str  # "BTC" or "ETH"
    leverage: str  # "m1", "m3", etc.
    timeframe: str  # "1month", "1week", "3month"
    timestamp: datetime  # Extracted from filename
    resolution: tuple[int, int]  # (width, height) in pixels

    @classmethod
    def from_path(cls, path: str) -> "Screenshot":
        """Create Screenshot from file path.

        Args:
            path: Absolute or relative path to screenshot file

        Returns:
            Screenshot instance with parsed metadata

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If filename format is invalid
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Screenshot not found: {path}")

        abs_path = os.path.abspath(path)
        filename = os.path.basename(path)
        parsed = parse_filename(filename)

        # Get resolution
        with Image.open(abs_path) as img:
            resolution = img.size

        return cls(
            path=abs_path,
            filename=filename,
            symbol=parsed["symbol"],
            leverage=parsed["leverage"],
            timeframe=parsed["timeframe"],
            timestamp=parsed["timestamp"],
            resolution=resolution,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "path": self.path,
            "filename": self.filename,
            "symbol": self.symbol,
            "leverage": self.leverage,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp.isoformat(),
            "resolution": list(self.resolution),
        }
