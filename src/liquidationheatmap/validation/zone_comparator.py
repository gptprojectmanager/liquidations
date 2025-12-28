"""Zone comparison between Coinglass OCR extraction and our heatmap API.

Calculates hit_rate metrics to validate model accuracy.
"""

import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from .ocr_extractor import ExtractedPriceLevels


@dataclass
class APIPriceLevels:
    """Price levels from our heatmap API."""

    symbol: str  # "BTCUSDT" or "ETHUSDT"
    timestamp: datetime
    current_price: float
    long_zones: list[dict] = field(default_factory=list)  # [{"price": float, "volume": float}]
    short_zones: list[dict] = field(default_factory=list)
    total_long_volume: float = 0.0
    total_short_volume: float = 0.0

    @classmethod
    def from_api_response(cls, response: dict, top_n: int = 20) -> "APIPriceLevels":
        """Parse API response into structured data.

        Args:
            response: Raw API response dict
            top_n: Number of top zones by volume to include

        Returns:
            APIPriceLevels with top zones by volume
        """
        meta = response.get("meta", {})
        data = response.get("data", [{}])

        if not data:
            return cls(
                symbol=meta.get("symbol", ""),
                timestamp=datetime.now(),
                current_price=0.0,
            )

        # Aggregate levels from all timestamps in the time-series response
        all_levels: dict[float, dict] = {}
        for snapshot in data:
            for level in snapshot.get("levels", []):
                price = level.get("price", 0)
                # API returns long_density/short_density, not volume
                long_density = level.get("long_density", 0) or 0
                short_density = level.get("short_density", 0) or 0
                volume = long_density + short_density

                if price in all_levels:
                    all_levels[price]["volume"] += volume
                    all_levels[price]["long_density"] += long_density
                    all_levels[price]["short_density"] += short_density
                else:
                    all_levels[price] = {
                        "price": price,
                        "volume": volume,
                        "long_density": long_density,
                        "short_density": short_density,
                    }

        levels = list(all_levels.values())

        # Get current price from meta or estimate from price_range midpoint
        price_range = meta.get("price_range", {})
        current_price = meta.get("current_price", 0)
        if not current_price and price_range:
            min_price = price_range.get("min", 0)
            max_price = price_range.get("max", 0)
            if min_price and max_price:
                current_price = (min_price + max_price) / 2

        # Sort by volume (descending) and take top N
        sorted_levels = sorted(levels, key=lambda x: x.get("volume", 0), reverse=True)
        top_zones = sorted_levels[:top_n]

        # Classify by density type (long_density > 0 means long zone, etc.)
        # BUG FIX: Also include zones where densities are equal (split to both)
        # or where only one type has density
        long_zones = [z for z in top_zones if z.get("long_density", 0) > 0]
        short_zones = [z for z in top_zones if z.get("short_density", 0) > 0]

        # Calculate totals
        total_long = sum(z.get("long_density", 0) for z in long_zones)
        total_short = sum(z.get("short_density", 0) for z in short_zones)

        timestamp_str = meta.get("timestamp", meta.get("start_time", ""))
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            timestamp = datetime.now()

        return cls(
            symbol=meta.get("symbol", ""),
            timestamp=timestamp,
            current_price=current_price,
            long_zones=long_zones,
            short_zones=short_zones,
            total_long_volume=total_long,
            total_short_volume=total_short,
        )

    @property
    def all_prices(self) -> list[float]:
        """All price levels from zones."""
        return [z["price"] for z in self.long_zones + self.short_zones]


@dataclass
class ValidationResult:
    """Comparison result for a single screenshot."""

    screenshot_path: str
    timestamp: datetime | None
    symbol: str
    status: str = "pending"  # "success", "ocr_failed", "api_failed", "no_match"

    # OCR results
    ocr_confidence: float = 0.0
    ocr_long_zones: list[float] = field(default_factory=list)
    ocr_short_zones: list[float] = field(default_factory=list)

    # API results
    api_long_zones: list[dict] = field(default_factory=list)
    api_short_zones: list[dict] = field(default_factory=list)

    # Comparison metrics
    hit_rate: float = 0.0
    long_hit_rate: float = 0.0
    short_hit_rate: float = 0.0
    matched_zones: list[dict] = field(default_factory=list)
    missed_zones: list[float] = field(default_factory=list)
    extra_zones: list[dict] = field(default_factory=list)

    # Metadata
    processing_time_ms: int = 0
    tolerance_pct: float = 1.0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "screenshot": self.screenshot_path,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "symbol": self.symbol,
            "status": self.status,
            "ocr_confidence": self.ocr_confidence,
            "coinglass_zones": {
                "long": self.ocr_long_zones,
                "short": self.ocr_short_zones,
            },
            "api_zones": {
                "long": self.api_long_zones,
                "short": self.api_short_zones,
            },
            "comparison": {
                "hit_rate": self.hit_rate,
                "long_hit_rate": self.long_hit_rate,
                "short_hit_rate": self.short_hit_rate,
                "matched": self.matched_zones,
                "missed": self.missed_zones,
                "extra": self.extra_zones,
            },
            "processing_time_ms": self.processing_time_ms,
            "tolerance_pct": self.tolerance_pct,
            "error": self.error if self.error else None,
        }


@dataclass
class AggregateMetrics:
    """Aggregate statistics across all screenshots."""

    total_screenshots: int = 0
    processed: int = 0
    ocr_failures: int = 0
    api_failures: int = 0
    no_data_failures: int = 0  # API returned empty zones

    # Hit rate statistics
    avg_hit_rate: float = 0.0
    median_hit_rate: float = 0.0
    std_hit_rate: float = 0.0
    min_hit_rate: float = 0.0
    max_hit_rate: float = 0.0

    # Pass/fail counts
    pass_count: int = 0
    fail_count: int = 0
    pass_rate: float = 0.0

    # Distribution
    hit_rate_distribution: dict = field(default_factory=dict)

    # By symbol breakdown
    by_symbol: dict = field(default_factory=dict)

    # Time range
    earliest_timestamp: datetime | None = None
    latest_timestamp: datetime | None = None

    # Performance
    total_processing_time_ms: int = 0
    avg_processing_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "total_screenshots": self.total_screenshots,
            "processed": self.processed,
            "ocr_failures": self.ocr_failures,
            "ocr_failure_rate": self.ocr_failures / self.total_screenshots
            if self.total_screenshots
            else 0,
            "api_failures": self.api_failures,
            "no_data_failures": self.no_data_failures,
            "metrics": {
                "avg_hit_rate": self.avg_hit_rate,
                "median_hit_rate": self.median_hit_rate,
                "std_hit_rate": self.std_hit_rate,
                "min_hit_rate": self.min_hit_rate,
                "max_hit_rate": self.max_hit_rate,
                "pass_rate": self.pass_rate,
                "hit_rate_distribution": self.hit_rate_distribution,
            },
            "by_symbol": self.by_symbol,
            "timestamp_range": {
                "earliest": self.earliest_timestamp.isoformat()
                if self.earliest_timestamp
                else None,
                "latest": self.latest_timestamp.isoformat() if self.latest_timestamp else None,
            },
            "performance": {
                "total_time_ms": self.total_processing_time_ms,
                "avg_time_ms": self.avg_processing_time_ms,
            },
        }


def calculate_hit_rate(
    coinglass_zones: list[float],
    api_zones: list[dict],
    tolerance_pct: float = 1.0,
) -> dict[str, Any]:
    """Compare price zones and calculate hit rate.

    Args:
        coinglass_zones: Price levels from OCR extraction
        api_zones: Zone dicts with 'price' and 'volume' keys
        tolerance_pct: Price match tolerance (default 1%)

    Returns:
        Dict with hit_rate, matched, missed, extra zones
    """
    if not coinglass_zones:
        return {
            "hit_rate": 0.0,
            "matched": [],
            "missed": [],
            "extra": api_zones,
        }

    api_prices = [z["price"] for z in api_zones]
    matched = []
    missed = []

    for cg_price in coinglass_zones:
        if not api_prices:
            missed.append(cg_price)
            continue

        # Find closest API price
        closest = min(api_prices, key=lambda p: abs(p - cg_price))
        pct_diff = abs(closest - cg_price) / cg_price * 100

        if pct_diff <= tolerance_pct:
            matched.append(
                {
                    "coinglass": cg_price,
                    "api": closest,
                    "error_pct": round(pct_diff, 2),
                }
            )
        else:
            missed.append(cg_price)

    # Find zones in API but not matched to Coinglass
    matched_api_prices = {m["api"] for m in matched}
    extra = [z for z in api_zones if z["price"] not in matched_api_prices]

    hit_rate = len(matched) / len(coinglass_zones) if coinglass_zones else 0.0

    return {
        "hit_rate": round(hit_rate, 4),
        "matched": matched,
        "missed": missed,
        "extra": extra,
    }


def calculate_aggregate_metrics(
    results: list[ValidationResult],
    threshold: float = 0.70,
) -> AggregateMetrics:
    """Calculate aggregate statistics from validation results.

    Args:
        results: List of ValidationResult objects
        threshold: Hit rate threshold for pass/fail classification

    Returns:
        AggregateMetrics with summary statistics
    """
    if not results:
        return AggregateMetrics()

    total = len(results)
    successful = [r for r in results if r.status == "success"]
    ocr_failures = sum(1 for r in results if r.status == "ocr_failed")
    api_failures = sum(1 for r in results if r.status == "api_failed")
    no_data_failures = sum(1 for r in results if r.status == "no_data")

    hit_rates = [r.hit_rate for r in successful]

    # Calculate statistics
    if hit_rates:
        avg_hit_rate = statistics.mean(hit_rates)
        median_hit_rate = statistics.median(hit_rates)
        std_hit_rate = statistics.stdev(hit_rates) if len(hit_rates) > 1 else 0.0
        min_hit_rate = min(hit_rates)
        max_hit_rate = max(hit_rates)
    else:
        avg_hit_rate = median_hit_rate = std_hit_rate = min_hit_rate = max_hit_rate = 0.0

    # Pass/fail counts
    pass_count = sum(1 for r in hit_rates if r >= threshold)
    fail_count = len(hit_rates) - pass_count
    pass_rate = pass_count / len(hit_rates) if hit_rates else 0.0

    # Distribution buckets
    distribution = {
        "0-25%": sum(1 for h in hit_rates if h < 0.25),
        "25-50%": sum(1 for h in hit_rates if 0.25 <= h < 0.50),
        "50-75%": sum(1 for h in hit_rates if 0.50 <= h < 0.75),
        "75-100%": sum(1 for h in hit_rates if h >= 0.75),
    }

    # By symbol breakdown
    by_symbol = {}
    for symbol in ["BTC", "ETH"]:
        symbol_results = [r for r in successful if r.symbol == symbol]
        symbol_rates = [r.hit_rate for r in symbol_results]
        if symbol_rates:
            by_symbol[symbol] = {
                "count": len(symbol_results),
                "avg_hit_rate": round(statistics.mean(symbol_rates), 4),
            }

    # Time range
    timestamps = [r.timestamp for r in results if r.timestamp]
    earliest = min(timestamps) if timestamps else None
    latest = max(timestamps) if timestamps else None

    # Performance
    total_time = sum(r.processing_time_ms for r in results)
    avg_time = total_time / len(results) if results else 0.0

    return AggregateMetrics(
        total_screenshots=total,
        processed=len(successful),
        ocr_failures=ocr_failures,
        api_failures=api_failures,
        no_data_failures=no_data_failures,
        avg_hit_rate=round(avg_hit_rate, 4),
        median_hit_rate=round(median_hit_rate, 4),
        std_hit_rate=round(std_hit_rate, 4),
        min_hit_rate=round(min_hit_rate, 4),
        max_hit_rate=round(max_hit_rate, 4),
        pass_count=pass_count,
        fail_count=fail_count,
        pass_rate=round(pass_rate, 4),
        hit_rate_distribution=distribution,
        by_symbol=by_symbol,
        earliest_timestamp=earliest,
        latest_timestamp=latest,
        total_processing_time_ms=total_time,
        avg_processing_time_ms=round(avg_time, 2),
    )


async def fetch_api_heatmap(
    symbol: str,
    timestamp: datetime,
    api_url: str = "http://localhost:8000",
    timestamp_window_minutes: int = 5,
) -> APIPriceLevels | None:
    """Fetch heatmap data from our API.

    Args:
        symbol: "BTC" or "ETH"
        timestamp: Target timestamp for data
        api_url: Base API URL
        timestamp_window_minutes: Tolerance window for timestamp matching

    Returns:
        APIPriceLevels or None if request fails
    """
    from datetime import timedelta

    # Map symbol to API format
    api_symbol = f"{symbol}USDT"

    # BUG FIX: Calculate start_time and end_time from timestamp + window
    # The API expects start_time and end_time, not timestamp and window_minutes
    start_time = timestamp - timedelta(minutes=timestamp_window_minutes)
    end_time = timestamp + timedelta(minutes=timestamp_window_minutes)

    # Build query with correct API parameters
    endpoint = f"{api_url}/liquidations/heatmap-timeseries"
    params = {
        "symbol": api_symbol,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            return APIPriceLevels.from_api_response(data)
    except Exception:
        return None


class ZoneComparator:
    """Compare Coinglass OCR extraction with our API heatmap data."""

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        tolerance_pct: float = 1.0,
        timestamp_window_minutes: int = 5,
    ):
        """Initialize comparator.

        Args:
            api_url: Base URL for heatmap API
            tolerance_pct: Price match tolerance percentage
            timestamp_window_minutes: Timestamp alignment window
        """
        self.api_url = api_url
        self.tolerance_pct = tolerance_pct
        self.timestamp_window_minutes = timestamp_window_minutes

    async def compare(
        self,
        ocr_result: ExtractedPriceLevels,
        screenshot_timestamp: datetime,
        symbol: str,
    ) -> ValidationResult:
        """Compare OCR extraction with API data.

        Args:
            ocr_result: Extracted price levels from screenshot
            screenshot_timestamp: Timestamp from screenshot filename
            symbol: "BTC" or "ETH"

        Returns:
            ValidationResult with comparison metrics
        """
        import time

        start_time = time.time()

        # Check OCR validity
        if not ocr_result.is_valid:
            return ValidationResult(
                screenshot_path=ocr_result.screenshot_path,
                timestamp=screenshot_timestamp,
                symbol=symbol,
                status="ocr_failed",
                ocr_confidence=ocr_result.confidence,
                processing_time_ms=int((time.time() - start_time) * 1000),
                tolerance_pct=self.tolerance_pct,
                error="OCR extraction failed or low confidence",
            )

        # Fetch API data
        api_data = await fetch_api_heatmap(
            symbol=symbol,
            timestamp=screenshot_timestamp,
            api_url=self.api_url,
            timestamp_window_minutes=self.timestamp_window_minutes,
        )

        if api_data is None:
            return ValidationResult(
                screenshot_path=ocr_result.screenshot_path,
                timestamp=screenshot_timestamp,
                symbol=symbol,
                status="api_failed",
                ocr_confidence=ocr_result.confidence,
                ocr_long_zones=ocr_result.long_zones,
                ocr_short_zones=ocr_result.short_zones,
                processing_time_ms=int((time.time() - start_time) * 1000),
                tolerance_pct=self.tolerance_pct,
                error="API request failed",
            )

        # Check if API returned any zones
        all_api = api_data.long_zones + api_data.short_zones
        if not all_api:
            return ValidationResult(
                screenshot_path=ocr_result.screenshot_path,
                timestamp=screenshot_timestamp,
                symbol=symbol,
                status="no_data",
                ocr_confidence=ocr_result.confidence,
                ocr_long_zones=ocr_result.long_zones,
                ocr_short_zones=ocr_result.short_zones,
                processing_time_ms=int((time.time() - start_time) * 1000),
                tolerance_pct=self.tolerance_pct,
                error="API returned no zone data for this timestamp",
            )

        # Reclassify OCR zones using API's current price
        all_ocr_zones = ocr_result.all_zones
        ocr_long = [p for p in all_ocr_zones if p < api_data.current_price]
        ocr_short = [p for p in all_ocr_zones if p > api_data.current_price]

        # Calculate hit rates
        long_comparison = calculate_hit_rate(ocr_long, api_data.long_zones, self.tolerance_pct)
        short_comparison = calculate_hit_rate(ocr_short, api_data.short_zones, self.tolerance_pct)

        # Overall hit rate
        all_ocr = ocr_long + ocr_short
        overall_comparison = calculate_hit_rate(all_ocr, all_api, self.tolerance_pct)

        processing_time_ms = int((time.time() - start_time) * 1000)

        return ValidationResult(
            screenshot_path=ocr_result.screenshot_path,
            timestamp=screenshot_timestamp,
            symbol=symbol,
            status="success",
            ocr_confidence=ocr_result.confidence,
            ocr_long_zones=ocr_long,
            ocr_short_zones=ocr_short,
            api_long_zones=api_data.long_zones,
            api_short_zones=api_data.short_zones,
            hit_rate=overall_comparison["hit_rate"],
            long_hit_rate=long_comparison["hit_rate"],
            short_hit_rate=short_comparison["hit_rate"],
            matched_zones=overall_comparison["matched"],
            missed_zones=overall_comparison["missed"],
            extra_zones=overall_comparison["extra"],
            processing_time_ms=processing_time_ms,
            tolerance_pct=self.tolerance_pct,
        )
