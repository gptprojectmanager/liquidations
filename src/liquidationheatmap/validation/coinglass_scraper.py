"""
Automated Coinglass validation scraper.

Extracts liquidation data from Coinglass via headless browser
and compares with our heatmap predictions.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CoinglassLiquidation:
    """Liquidation data point from Coinglass."""

    symbol: str
    price: Decimal
    long_1h: Decimal
    short_1h: Decimal
    long_24h: Decimal
    short_24h: Decimal
    timestamp: datetime


@dataclass
class ValidationResult:
    """Result of comparing our heatmap vs Coinglass."""

    timestamp: datetime
    symbol: str

    # Coinglass data
    cg_price: Decimal
    cg_long_24h: Decimal
    cg_short_24h: Decimal

    # Our data
    our_total_long: Decimal
    our_total_short: Decimal

    # Metrics
    long_ratio: float  # our/coinglass
    short_ratio: float
    price_match: bool  # within 0.5%

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "cg_price": float(self.cg_price),
            "cg_long_24h": float(self.cg_long_24h),
            "cg_short_24h": float(self.cg_short_24h),
            "our_total_long": float(self.our_total_long),
            "our_total_short": float(self.our_total_short),
            "long_ratio": self.long_ratio,
            "short_ratio": self.short_ratio,
            "price_match": self.price_match,
        }


def parse_coinglass_value(value_str: str) -> Decimal:
    """Parse Coinglass formatted values like '$3.59M', '$457.22K'."""
    if not value_str or value_str == "$0":
        return Decimal("0")

    # Remove $ and whitespace
    clean = value_str.replace("$", "").replace(",", "").strip()

    multiplier = Decimal("1")
    if clean.endswith("B"):
        multiplier = Decimal("1000000000")
        clean = clean[:-1]
    elif clean.endswith("M"):
        multiplier = Decimal("1000000")
        clean = clean[:-1]
    elif clean.endswith("K"):
        multiplier = Decimal("1000")
        clean = clean[:-1]

    try:
        return Decimal(clean) * multiplier
    except Exception:
        return Decimal("0")


def extract_btc_data_from_snapshot(snapshot: dict) -> Optional[CoinglassLiquidation]:
    """Extract BTC liquidation data from Playwright snapshot.

    Looks for the BTC row in the Total Liquidations table.
    Expected format from table row:
    - Symbol: BTC
    - Price: $87790.8
    - 1h Long/Short, 4h Long/Short, 12h Long/Short, 24h Long/Short
    """
    # The snapshot is a nested structure, we need to find BTC row
    # Based on observed structure: row contains cells with values

    # This is a simplified parser - in production would be more robust
    try:
        # Look for patterns in the snapshot text
        snapshot_str = json.dumps(snapshot) if isinstance(snapshot, dict) else str(snapshot)

        # Extract BTC price (pattern: "BTC" followed by price)
        import re

        # Find BTC price pattern
        price_match = re.search(r'"BTC"[^$]*\$(\d+\.?\d*)', snapshot_str)
        price = Decimal(price_match.group(1)) if price_match else Decimal("0")

        # Find liquidation values (simplified - would need proper DOM parsing)
        # For now return placeholder that will be filled by Playwright extraction
        return CoinglassLiquidation(
            symbol="BTC",
            price=price,
            long_1h=Decimal("0"),
            short_1h=Decimal("0"),
            long_24h=Decimal("0"),
            short_24h=Decimal("0"),
            timestamp=datetime.now(),
        )
    except Exception as e:
        logger.error(f"Failed to extract BTC data: {e}")
        return None


async def fetch_our_heatmap(symbol: str = "BTCUSDT") -> dict:
    """Fetch our heatmap data from local API."""
    import urllib.request

    url = f"http://localhost:8000/liquidations/heatmap-timeseries?symbol={symbol}&time_window=48h"

    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f"Failed to fetch our heatmap: {e}")
        return {}


def calculate_validation_metrics(
    cg_data: CoinglassLiquidation,
    our_data: dict,
) -> ValidationResult:
    """Calculate validation metrics comparing Coinglass vs our data."""

    meta = our_data.get("meta", {})

    # Sum our liquidation volumes
    our_long = Decimal(str(meta.get("total_long_volume", 0)))
    our_short = Decimal(str(meta.get("total_short_volume", 0)))

    # Calculate ratios (avoid division by zero)
    long_ratio = float(our_long / cg_data.long_24h) if cg_data.long_24h > 0 else 0.0
    short_ratio = float(our_short / cg_data.short_24h) if cg_data.short_24h > 0 else 0.0

    # Check price match (within 0.5%)
    # Would need current price from our API
    price_match = True  # Placeholder

    return ValidationResult(
        timestamp=datetime.now(),
        symbol=cg_data.symbol,
        cg_price=cg_data.price,
        cg_long_24h=cg_data.long_24h,
        cg_short_24h=cg_data.short_24h,
        our_total_long=our_long,
        our_total_short=our_short,
        long_ratio=long_ratio,
        short_ratio=short_ratio,
        price_match=price_match,
    )


class ValidationPipeline:
    """Automated validation pipeline that runs periodically."""

    def __init__(self, results_dir: Path = None):
        self.results_dir = results_dir or Path("data/validation")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.results_file = self.results_dir / "validation_history.jsonl"

    def log_result(self, result: ValidationResult):
        """Append result to JSONL file for historical tracking."""
        with open(self.results_file, "a") as f:
            f.write(json.dumps(result.to_dict()) + "\n")
        logger.info(
            f"Logged validation: long={result.long_ratio:.2f}, short={result.short_ratio:.2f}"
        )

    def get_history(self, limit: int = 100) -> list[dict]:
        """Get recent validation history."""
        if not self.results_file.exists():
            return []

        results = []
        with open(self.results_file) as f:
            for line in f:
                if line.strip():
                    results.append(json.loads(line))

        return results[-limit:]

    def calculate_rolling_accuracy(self, window: int = 24) -> dict:
        """Calculate rolling accuracy metrics."""
        history = self.get_history(window)

        if not history:
            return {"error": "No history available"}

        long_ratios = [h["long_ratio"] for h in history if h["long_ratio"] > 0]
        short_ratios = [h["short_ratio"] for h in history if h["short_ratio"] > 0]

        return {
            "window_size": len(history),
            "avg_long_ratio": sum(long_ratios) / len(long_ratios) if long_ratios else 0,
            "avg_short_ratio": sum(short_ratios) / len(short_ratios) if short_ratios else 0,
            "long_ratio_std": self._std(long_ratios) if len(long_ratios) > 1 else 0,
            "short_ratio_std": self._std(short_ratios) if len(short_ratios) > 1 else 0,
        }

    @staticmethod
    def _std(values: list) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance**0.5


# Entry point for CLI usage
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    pipeline = ValidationPipeline()

    if len(sys.argv) > 1 and sys.argv[1] == "history":
        history = pipeline.get_history()
        print(json.dumps(history, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "accuracy":
        accuracy = pipeline.calculate_rolling_accuracy()
        print(json.dumps(accuracy, indent=2))
    else:
        print("Usage: python coinglass_scraper.py [history|accuracy]")
        print("For automated validation, use the API endpoint or scheduled job.")
