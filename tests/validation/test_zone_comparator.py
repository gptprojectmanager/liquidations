"""Unit tests for zone_comparator module."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.liquidationheatmap.validation.ocr_extractor import ExtractedPriceLevels
from src.liquidationheatmap.validation.zone_comparator import (
    APIPriceLevels,
    ValidationResult,
    ZoneComparator,
    calculate_aggregate_metrics,
    calculate_hit_rate,
)


class TestCalculateHitRate:
    """Tests for calculate_hit_rate function."""

    def test_perfect_match(self):
        """100% hit rate when all zones match."""
        coinglass = [100000.0, 95000.0, 90000.0]
        api = [
            {"price": 100000.0, "volume": 1000},
            {"price": 95000.0, "volume": 900},
            {"price": 90000.0, "volume": 800},
        ]

        result = calculate_hit_rate(coinglass, api, tolerance_pct=1.0)

        assert result["hit_rate"] == 1.0
        assert len(result["matched"]) == 3
        assert len(result["missed"]) == 0

    def test_partial_match(self):
        """Partial hit rate when some zones match."""
        coinglass = [100000.0, 95000.0, 90000.0]
        api = [
            {"price": 100000.0, "volume": 1000},
            {"price": 85000.0, "volume": 800},  # Doesn't match 95k or 90k
        ]

        result = calculate_hit_rate(coinglass, api, tolerance_pct=1.0)

        assert result["hit_rate"] == pytest.approx(1 / 3, rel=0.01)
        assert len(result["matched"]) == 1
        assert len(result["missed"]) == 2

    def test_no_match(self):
        """0% hit rate when no zones match."""
        coinglass = [100000.0, 95000.0]
        api = [
            {"price": 50000.0, "volume": 1000},
            {"price": 45000.0, "volume": 800},
        ]

        result = calculate_hit_rate(coinglass, api, tolerance_pct=1.0)

        assert result["hit_rate"] == 0.0
        assert len(result["matched"]) == 0
        assert len(result["missed"]) == 2

    def test_tolerance_window(self):
        """Match within tolerance percentage."""
        coinglass = [100000.0]
        api = [{"price": 100500.0, "volume": 1000}]  # 0.5% difference

        # 0.5% tolerance - should not match
        result_narrow = calculate_hit_rate(coinglass, api, tolerance_pct=0.4)
        assert result_narrow["hit_rate"] == 0.0

        # 1% tolerance - should match
        result_wide = calculate_hit_rate(coinglass, api, tolerance_pct=1.0)
        assert result_wide["hit_rate"] == 1.0

    def test_empty_coinglass_zones(self):
        """Handle empty Coinglass zones."""
        result = calculate_hit_rate([], [{"price": 100000.0, "volume": 1000}])

        assert result["hit_rate"] == 0.0
        assert len(result["extra"]) == 1

    def test_matched_includes_error_pct(self):
        """Matched zones include error percentage."""
        coinglass = [100000.0]
        api = [{"price": 100500.0, "volume": 1000}]

        result = calculate_hit_rate(coinglass, api, tolerance_pct=1.0)

        assert len(result["matched"]) == 1
        assert result["matched"][0]["coinglass"] == 100000.0
        assert result["matched"][0]["api"] == 100500.0
        assert result["matched"][0]["error_pct"] == pytest.approx(0.5, rel=0.01)


class TestAPIPriceLevels:
    """Tests for APIPriceLevels dataclass."""

    def test_from_api_response_parses_correctly(self):
        """Parse API response into structured data."""
        response = {
            "meta": {
                "symbol": "BTCUSDT",
                "current_price": 95000,
                "timestamp": "2025-10-30T14:57:08Z",
            },
            "data": [
                {
                    "timestamp": "2025-10-30T14:57:08",
                    "levels": [
                        {"price": 100000, "long_density": 0, "short_density": 1000},
                        {"price": 90000, "long_density": 900, "short_density": 0},
                        {"price": 85000, "long_density": 800, "short_density": 0},
                    ],
                }
            ],
        }

        result = APIPriceLevels.from_api_response(response, top_n=20)

        assert result.symbol == "BTCUSDT"
        assert result.current_price == 95000
        assert len(result.short_zones) == 1  # short_density > long_density
        assert len(result.long_zones) == 2  # long_density > short_density

    def test_from_api_response_sorts_by_volume(self):
        """Top N zones are sorted by volume (long_density + short_density)."""
        response = {
            "meta": {"symbol": "BTCUSDT", "current_price": 95000},
            "data": [
                {
                    "timestamp": "2025-10-30T14:57:08",
                    "levels": [
                        {"price": 100000, "long_density": 0, "short_density": 100},
                        {"price": 99000, "long_density": 0, "short_density": 1000},  # Higher volume
                        {"price": 98000, "long_density": 0, "short_density": 500},
                    ],
                }
            ],
        }

        result = APIPriceLevels.from_api_response(response, top_n=2)

        # Only top 2 by volume should be included
        all_prices = result.all_prices
        assert len(all_prices) == 2
        assert 99000 in all_prices  # Highest volume
        assert 98000 in all_prices  # Second highest

    def test_from_api_response_handles_empty_data(self):
        """Handle empty API response gracefully."""
        response = {"meta": {"symbol": "BTCUSDT"}, "data": []}

        result = APIPriceLevels.from_api_response(response)

        assert result.symbol == "BTCUSDT"
        assert result.all_prices == []


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_to_dict_serialization(self):
        """to_dict returns JSON-serializable dict."""
        result = ValidationResult(
            screenshot_path="/path/to/screenshot.png",
            timestamp=datetime(2025, 10, 30, 14, 57, 8),
            symbol="BTC",
            status="success",
            ocr_confidence=0.85,
            hit_rate=0.75,
            processing_time_ms=1500,
        )

        data = result.to_dict()

        assert data["screenshot"] == "/path/to/screenshot.png"
        assert data["timestamp"] == "2025-10-30T14:57:08"
        assert data["symbol"] == "BTC"
        assert data["status"] == "success"
        assert data["ocr_confidence"] == 0.85
        assert data["comparison"]["hit_rate"] == 0.75
        assert data["processing_time_ms"] == 1500

    def test_to_dict_handles_none_timestamp(self):
        """to_dict handles None timestamp gracefully."""
        result = ValidationResult(
            screenshot_path="/path/to/screenshot.png",
            timestamp=None,
            symbol="BTC",
            status="error",
            error="Test error",
        )

        data = result.to_dict()

        assert data["screenshot"] == "/path/to/screenshot.png"
        assert data["timestamp"] is None
        assert data["status"] == "error"


class TestCalculateAggregateMetrics:
    """Tests for calculate_aggregate_metrics function."""

    def test_calculate_metrics_from_results(self):
        """Calculate aggregate statistics from results."""
        results = [
            ValidationResult(
                screenshot_path="/path/1.png",
                timestamp=datetime(2025, 10, 30, 14, 0, 0),
                symbol="BTC",
                status="success",
                hit_rate=0.80,
                processing_time_ms=1000,
            ),
            ValidationResult(
                screenshot_path="/path/2.png",
                timestamp=datetime(2025, 10, 30, 15, 0, 0),
                symbol="BTC",
                status="success",
                hit_rate=0.60,
                processing_time_ms=1200,
            ),
        ]

        metrics = calculate_aggregate_metrics(results, threshold=0.70)

        assert metrics.total_screenshots == 2
        assert metrics.processed == 2
        assert metrics.avg_hit_rate == pytest.approx(0.70, rel=0.01)
        assert metrics.pass_count == 1  # Only 0.80 >= 0.70
        assert metrics.fail_count == 1

    def test_calculate_metrics_with_failures(self):
        """Track OCR and API failures separately."""
        results = [
            ValidationResult(
                screenshot_path="/path/1.png",
                timestamp=datetime.now(),
                symbol="BTC",
                status="ocr_failed",
            ),
            ValidationResult(
                screenshot_path="/path/2.png",
                timestamp=datetime.now(),
                symbol="BTC",
                status="api_failed",
            ),
            ValidationResult(
                screenshot_path="/path/3.png",
                timestamp=datetime.now(),
                symbol="BTC",
                status="success",
                hit_rate=0.75,
            ),
        ]

        metrics = calculate_aggregate_metrics(results)

        assert metrics.ocr_failures == 1
        assert metrics.api_failures == 1
        assert metrics.processed == 1

    def test_calculate_metrics_empty_results(self):
        """Handle empty results list."""
        metrics = calculate_aggregate_metrics([])

        assert metrics.total_screenshots == 0
        assert metrics.avg_hit_rate == 0.0

    def test_hit_rate_distribution(self):
        """Track hit rate distribution buckets."""
        results = [
            ValidationResult(
                screenshot_path=f"/path/{i}.png",
                timestamp=datetime.now(),
                symbol="BTC",
                status="success",
                hit_rate=rate,
            )
            for i, rate in enumerate([0.10, 0.30, 0.55, 0.80])
        ]

        metrics = calculate_aggregate_metrics(results)

        assert metrics.hit_rate_distribution["0-25%"] == 1
        assert metrics.hit_rate_distribution["25-50%"] == 1
        assert metrics.hit_rate_distribution["50-75%"] == 1
        assert metrics.hit_rate_distribution["75-100%"] == 1


class TestZoneComparator:
    """Tests for ZoneComparator class."""

    @pytest.mark.asyncio
    async def test_compare_success(self):
        """Successful comparison returns ValidationResult."""
        ocr_result = ExtractedPriceLevels(
            screenshot_path="/path/to/screenshot.png",
            short_zones=[100000.0, 95000.0],
            confidence=0.85,
        )

        api_response = APIPriceLevels(
            symbol="BTCUSDT",
            timestamp=datetime.now(),
            current_price=90000,
            short_zones=[
                {"price": 100000.0, "volume": 1000},
                {"price": 95000.0, "volume": 900},
            ],
        )

        with patch(
            "src.liquidationheatmap.validation.zone_comparator.fetch_api_heatmap",
            new_callable=AsyncMock,
            return_value=api_response,
        ):
            comparator = ZoneComparator(api_url="http://localhost:8000")
            result = await comparator.compare(
                ocr_result=ocr_result,
                screenshot_timestamp=datetime(2025, 10, 30, 14, 57, 8),
                symbol="BTC",
            )

        assert result.status == "success"
        assert result.hit_rate == 1.0
        assert result.ocr_confidence == 0.85

    @pytest.mark.asyncio
    async def test_compare_ocr_failed(self):
        """Return ocr_failed status for invalid OCR result."""
        ocr_result = ExtractedPriceLevels(
            screenshot_path="/path/to/screenshot.png",
            confidence=0.3,  # Below threshold
        )

        comparator = ZoneComparator()
        result = await comparator.compare(
            ocr_result=ocr_result,
            screenshot_timestamp=datetime.now(),
            symbol="BTC",
        )

        assert result.status == "ocr_failed"

    @pytest.mark.asyncio
    async def test_compare_api_failed(self):
        """Return api_failed status when API request fails."""
        ocr_result = ExtractedPriceLevels(
            screenshot_path="/path/to/screenshot.png",
            short_zones=[100000.0, 95000.0],
            confidence=0.85,
        )

        with patch(
            "src.liquidationheatmap.validation.zone_comparator.fetch_api_heatmap",
            new_callable=AsyncMock,
            return_value=None,
        ):
            comparator = ZoneComparator()
            result = await comparator.compare(
                ocr_result=ocr_result,
                screenshot_timestamp=datetime.now(),
                symbol="BTC",
            )

        assert result.status == "api_failed"

    @pytest.mark.asyncio
    async def test_compare_no_data(self):
        """Return no_data status when API returns empty zones."""
        ocr_result = ExtractedPriceLevels(
            screenshot_path="/path/to/screenshot.png",
            short_zones=[100000.0, 95000.0],
            confidence=0.85,
        )

        # API response with no zones
        api_response = APIPriceLevels(
            symbol="ETHUSDT",
            timestamp=datetime.now(),
            current_price=3500,
            long_zones=[],
            short_zones=[],
        )

        with patch(
            "src.liquidationheatmap.validation.zone_comparator.fetch_api_heatmap",
            new_callable=AsyncMock,
            return_value=api_response,
        ):
            comparator = ZoneComparator()
            result = await comparator.compare(
                ocr_result=ocr_result,
                screenshot_timestamp=datetime.now(),
                symbol="ETH",
            )

        assert result.status == "no_data"
        assert "no zone data" in result.error
