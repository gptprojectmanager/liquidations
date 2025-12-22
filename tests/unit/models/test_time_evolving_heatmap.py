"""Unit tests for time-evolving heatmap algorithm.

TDD RED phase: Write failing tests for US1 Core Algorithm.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class MockCandle:
    """Mock candle for testing."""

    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal = Decimal("100")


class TestShouldLiquidate:
    """Tests for should_liquidate() function (T011)."""

    def test_long_liquidates_when_price_drops_below(self):
        """Long position should liquidate when candle low <= liq_price."""
        from src.liquidationheatmap.models.time_evolving_heatmap import should_liquidate

        from src.liquidationheatmap.models.position import LiquidationLevel

        level = LiquidationLevel(
            entry_price=Decimal("100000"),
            liq_price=Decimal("91000"),
            volume=Decimal("50000"),
            side="long",
            leverage=10,
            created_at=datetime(2025, 11, 15, 12, 0, 0),
        )

        candle = MockCandle(
            open_time=datetime(2025, 11, 16, 8, 0, 0),
            open=Decimal("92000"),
            high=Decimal("92500"),
            low=Decimal("90000"),  # Below liq_price
            close=Decimal("91500"),
        )

        assert should_liquidate(level, candle) is True

    def test_long_not_liquidated_when_price_above(self):
        """Long position should NOT liquidate when candle low > liq_price."""
        from src.liquidationheatmap.models.time_evolving_heatmap import should_liquidate

        from src.liquidationheatmap.models.position import LiquidationLevel

        level = LiquidationLevel(
            entry_price=Decimal("100000"),
            liq_price=Decimal("91000"),
            volume=Decimal("50000"),
            side="long",
            leverage=10,
            created_at=datetime(2025, 11, 15, 12, 0, 0),
        )

        candle = MockCandle(
            open_time=datetime(2025, 11, 16, 8, 0, 0),
            open=Decimal("95000"),
            high=Decimal("96000"),
            low=Decimal("94000"),  # Above liq_price
            close=Decimal("95500"),
        )

        assert should_liquidate(level, candle) is False

    def test_long_liquidates_on_exact_match(self):
        """Long position should liquidate when candle low == liq_price exactly."""
        from src.liquidationheatmap.models.time_evolving_heatmap import should_liquidate

        from src.liquidationheatmap.models.position import LiquidationLevel

        level = LiquidationLevel(
            entry_price=Decimal("100000"),
            liq_price=Decimal("91000"),
            volume=Decimal("50000"),
            side="long",
            leverage=10,
            created_at=datetime(2025, 11, 15, 12, 0, 0),
        )

        candle = MockCandle(
            open_time=datetime(2025, 11, 16, 8, 0, 0),
            open=Decimal("92000"),
            high=Decimal("92500"),
            low=Decimal("91000"),  # Exactly at liq_price
            close=Decimal("91500"),
        )

        assert should_liquidate(level, candle) is True

    def test_short_liquidates_when_price_rises_above(self):
        """Short position should liquidate when candle high >= liq_price."""
        from src.liquidationheatmap.models.time_evolving_heatmap import should_liquidate

        from src.liquidationheatmap.models.position import LiquidationLevel

        level = LiquidationLevel(
            entry_price=Decimal("100000"),
            liq_price=Decimal("109000"),
            volume=Decimal("50000"),
            side="short",
            leverage=10,
            created_at=datetime(2025, 11, 15, 12, 0, 0),
        )

        candle = MockCandle(
            open_time=datetime(2025, 11, 16, 8, 0, 0),
            open=Decimal("108000"),
            high=Decimal("110000"),  # Above liq_price
            low=Decimal("107500"),
            close=Decimal("109500"),
        )

        assert should_liquidate(level, candle) is True

    def test_short_not_liquidated_when_price_below(self):
        """Short position should NOT liquidate when candle high < liq_price."""
        from src.liquidationheatmap.models.time_evolving_heatmap import should_liquidate

        from src.liquidationheatmap.models.position import LiquidationLevel

        level = LiquidationLevel(
            entry_price=Decimal("100000"),
            liq_price=Decimal("109000"),
            volume=Decimal("50000"),
            side="short",
            leverage=10,
            created_at=datetime(2025, 11, 15, 12, 0, 0),
        )

        candle = MockCandle(
            open_time=datetime(2025, 11, 16, 8, 0, 0),
            open=Decimal("105000"),
            high=Decimal("106000"),  # Below liq_price
            low=Decimal("104500"),
            close=Decimal("105500"),
        )

        assert should_liquidate(level, candle) is False


class TestInferSide:
    """Tests for infer_side() function (T012)."""

    def test_infer_long_when_bullish(self):
        """Should infer 'long' when close > open (bullish candle)."""
        from src.liquidationheatmap.models.time_evolving_heatmap import infer_side

        candle = MockCandle(
            open_time=datetime(2025, 11, 15, 12, 0, 0),
            open=Decimal("95000"),
            high=Decimal("97000"),
            low=Decimal("94500"),
            close=Decimal("96500"),  # Close > open
        )

        assert infer_side(candle) == "long"

    def test_infer_short_when_bearish(self):
        """Should infer 'short' when close < open (bearish candle)."""
        from src.liquidationheatmap.models.time_evolving_heatmap import infer_side

        candle = MockCandle(
            open_time=datetime(2025, 11, 15, 12, 0, 0),
            open=Decimal("96500"),
            high=Decimal("97000"),
            low=Decimal("94500"),
            close=Decimal("95000"),  # Close < open
        )

        assert infer_side(candle) == "short"

    def test_infer_long_when_doji(self):
        """Should default to 'long' when close == open (doji)."""
        from src.liquidationheatmap.models.time_evolving_heatmap import infer_side

        candle = MockCandle(
            open_time=datetime(2025, 11, 15, 12, 0, 0),
            open=Decimal("95000"),
            high=Decimal("96000"),
            low=Decimal("94000"),
            close=Decimal("95000"),  # Close == open
        )

        # Default to long for neutral candles
        assert infer_side(candle) == "long"


class TestCreatePositions:
    """Tests for create_positions() function (T013)."""

    def test_creates_positions_for_all_leverage_tiers(self):
        """Should create positions distributed across leverage tiers."""
        from src.liquidationheatmap.models.time_evolving_heatmap import create_positions

        positions = create_positions(
            entry_price=Decimal("100000"),
            volume=Decimal("1000000"),  # 1M USDT
            side="long",
            timestamp=datetime(2025, 11, 15, 12, 0, 0),
        )

        # Should create one position per leverage tier (5 tiers)
        assert len(positions) == 5

        # Verify all leverage tiers are represented
        leverages = {p.leverage for p in positions}
        assert leverages == {5, 10, 25, 50, 100}

    def test_positions_sum_to_total_volume(self):
        """Sum of position volumes should equal input volume."""
        from src.liquidationheatmap.models.time_evolving_heatmap import create_positions

        positions = create_positions(
            entry_price=Decimal("100000"),
            volume=Decimal("1000000"),
            side="long",
            timestamp=datetime(2025, 11, 15, 12, 0, 0),
        )

        total_volume = sum(p.volume for p in positions)
        assert total_volume == Decimal("1000000")

    def test_positions_have_correct_liq_prices(self):
        """Each position should have correctly calculated liquidation price."""
        from src.liquidationheatmap.models.time_evolving_heatmap import create_positions

        from src.liquidationheatmap.models.position import calculate_liq_price

        positions = create_positions(
            entry_price=Decimal("100000"),
            volume=Decimal("1000000"),
            side="long",
            timestamp=datetime(2025, 11, 15, 12, 0, 0),
        )

        for pos in positions:
            expected_liq = calculate_liq_price(
                entry_price=pos.entry_price,
                leverage=pos.leverage,
                side=pos.side,
            )
            assert pos.liq_price == expected_liq

    def test_positions_for_short_side(self):
        """Should create short positions with correct liq prices."""
        from src.liquidationheatmap.models.time_evolving_heatmap import create_positions

        positions = create_positions(
            entry_price=Decimal("100000"),
            volume=Decimal("500000"),
            side="short",
            timestamp=datetime(2025, 11, 15, 12, 0, 0),
        )

        # All should be short
        assert all(p.side == "short" for p in positions)

        # Short liq prices should be above entry
        for pos in positions:
            assert pos.liq_price > pos.entry_price


class TestRemoveProportionally:
    """Tests for remove_proportionally() function (T014)."""

    def test_removes_volume_proportionally(self):
        """Should remove volume proportionally from all positions."""
        from src.liquidationheatmap.models.time_evolving_heatmap import (
            remove_proportionally,
        )

        from src.liquidationheatmap.models.position import LiquidationLevel

        # Create active positions
        active_positions: dict[Decimal, list[LiquidationLevel]] = {
            Decimal("91000"): [
                LiquidationLevel(
                    entry_price=Decimal("100000"),
                    liq_price=Decimal("91000"),
                    volume=Decimal("100000"),
                    side="long",
                    leverage=10,
                    created_at=datetime(2025, 11, 15, 12, 0, 0),
                )
            ],
            Decimal("80000"): [
                LiquidationLevel(
                    entry_price=Decimal("100000"),
                    liq_price=Decimal("80000"),
                    volume=Decimal("100000"),
                    side="long",
                    leverage=5,
                    created_at=datetime(2025, 11, 15, 12, 0, 0),
                )
            ],
        }

        # Remove 50% of total volume
        remove_proportionally(active_positions, Decimal("100000"))

        # Each position should have 50% remaining
        for positions in active_positions.values():
            for pos in positions:
                assert pos.volume == Decimal("50000")

    def test_removes_all_when_exceeds_total(self):
        """Should remove all volume when removal exceeds total."""
        from src.liquidationheatmap.models.time_evolving_heatmap import (
            remove_proportionally,
        )

        from src.liquidationheatmap.models.position import LiquidationLevel

        active_positions: dict[Decimal, list[LiquidationLevel]] = {
            Decimal("91000"): [
                LiquidationLevel(
                    entry_price=Decimal("100000"),
                    liq_price=Decimal("91000"),
                    volume=Decimal("50000"),
                    side="long",
                    leverage=10,
                    created_at=datetime(2025, 11, 15, 12, 0, 0),
                )
            ],
        }

        # Try to remove more than exists
        remove_proportionally(active_positions, Decimal("100000"))

        # Position should be removed (volume < 0.01 threshold)
        assert len(active_positions[Decimal("91000")]) == 0

    def test_no_change_when_empty(self):
        """Should handle empty positions dict without error."""
        from src.liquidationheatmap.models.time_evolving_heatmap import (
            remove_proportionally,
        )

        active_positions: dict[Decimal, list] = {}

        # Should not raise
        remove_proportionally(active_positions, Decimal("100000"))

        assert len(active_positions) == 0


class TestProcessCandle:
    """Tests for process_candle() function (T015)."""

    def test_consumes_positions_when_price_crosses(self):
        """Should mark positions as consumed when price crosses liq level."""
        from src.liquidationheatmap.models.time_evolving_heatmap import process_candle

        from src.liquidationheatmap.models.position import LiquidationLevel

        active_positions: dict[Decimal, list[LiquidationLevel]] = {
            Decimal("91000"): [
                LiquidationLevel(
                    entry_price=Decimal("100000"),
                    liq_price=Decimal("91000"),
                    volume=Decimal("50000"),
                    side="long",
                    leverage=10,
                    created_at=datetime(2025, 11, 15, 12, 0, 0),
                )
            ],
        }

        candle = MockCandle(
            open_time=datetime(2025, 11, 16, 8, 0, 0),
            open=Decimal("92000"),
            high=Decimal("92500"),
            low=Decimal("90000"),  # Below liq_price - triggers liquidation
            close=Decimal("91500"),
        )

        oi_delta = Decimal("0")  # No new positions

        consumed, created = process_candle(candle, oi_delta, active_positions)

        assert len(consumed) == 1
        assert consumed[0].consumed_at == candle.open_time
        assert len(created) == 0

    def test_creates_positions_from_positive_oi_delta(self):
        """Should create new positions when OI increases."""
        from src.liquidationheatmap.models.time_evolving_heatmap import process_candle

        active_positions: dict[Decimal, list] = {}

        candle = MockCandle(
            open_time=datetime(2025, 11, 15, 12, 0, 0),
            open=Decimal("95000"),
            high=Decimal("96000"),
            low=Decimal("94500"),
            close=Decimal("95500"),  # Bullish - infers long
        )

        oi_delta = Decimal("1000000")  # 1M new OI

        consumed, created = process_candle(candle, oi_delta, active_positions)

        assert len(consumed) == 0
        assert len(created) == 5  # 5 leverage tiers
        assert sum(p.volume for p in created) == Decimal("1000000")

    def test_removes_positions_from_negative_oi_delta(self):
        """Should remove positions proportionally when OI decreases."""
        from src.liquidationheatmap.models.time_evolving_heatmap import process_candle

        from src.liquidationheatmap.models.position import LiquidationLevel

        active_positions: dict[Decimal, list[LiquidationLevel]] = {
            Decimal("91000"): [
                LiquidationLevel(
                    entry_price=Decimal("100000"),
                    liq_price=Decimal("91000"),
                    volume=Decimal("100000"),
                    side="long",
                    leverage=10,
                    created_at=datetime(2025, 11, 15, 12, 0, 0),
                )
            ],
        }

        candle = MockCandle(
            open_time=datetime(2025, 11, 16, 8, 0, 0),
            open=Decimal("95000"),
            high=Decimal("96000"),
            low=Decimal("94500"),  # Doesn't cross liq
            close=Decimal("95500"),
        )

        oi_delta = Decimal("-50000")  # 50K OI decrease

        consumed, created = process_candle(candle, oi_delta, active_positions)

        assert len(consumed) == 0
        assert len(created) == 0
        # Volume should be reduced by 50%
        assert active_positions[Decimal("91000")][0].volume == Decimal("50000")


class TestCalculateTimeEvolvingHeatmap:
    """Tests for calculate_time_evolving_heatmap() main function (T016)."""

    def test_returns_list_of_snapshots(self):
        """Should return a list of HeatmapSnapshot objects."""
        from src.liquidationheatmap.models.time_evolving_heatmap import (
            calculate_time_evolving_heatmap,
        )

        # Create minimal test data
        candles = [
            MockCandle(
                open_time=datetime(2025, 11, 15, 12, 0, 0),
                open=Decimal("95000"),
                high=Decimal("96000"),
                low=Decimal("94500"),
                close=Decimal("95500"),
            ),
            MockCandle(
                open_time=datetime(2025, 11, 15, 12, 15, 0),
                open=Decimal("95500"),
                high=Decimal("96500"),
                low=Decimal("95000"),
                close=Decimal("96000"),
            ),
        ]

        oi_deltas = [Decimal("100000"), Decimal("50000")]

        snapshots = calculate_time_evolving_heatmap(
            candles=candles,
            oi_deltas=oi_deltas,
            symbol="BTCUSDT",
        )

        assert len(snapshots) == 2
        assert all(s.symbol == "BTCUSDT" for s in snapshots)

    def test_snapshots_track_consumption(self):
        """Snapshots should reflect position consumption over time."""
        from src.liquidationheatmap.models.time_evolving_heatmap import (
            calculate_time_evolving_heatmap,
        )

        # First candle creates positions, second liquidates them
        candles = [
            MockCandle(
                open_time=datetime(2025, 11, 15, 12, 0, 0),
                open=Decimal("100000"),
                high=Decimal("101000"),
                low=Decimal("99500"),
                close=Decimal("100500"),  # Bullish - creates longs
            ),
            MockCandle(
                open_time=datetime(2025, 11, 15, 12, 15, 0),
                open=Decimal("95000"),
                high=Decimal("95500"),
                low=Decimal("88000"),  # Crashes below all liq prices
                close=Decimal("89000"),
            ),
        ]

        oi_deltas = [Decimal("1000000"), Decimal("0")]

        snapshots = calculate_time_evolving_heatmap(
            candles=candles,
            oi_deltas=oi_deltas,
            symbol="BTCUSDT",
        )

        # First snapshot should have positions created
        assert snapshots[0].positions_created > 0

        # Second snapshot should have positions consumed
        assert snapshots[1].positions_consumed > 0

    def test_empty_input_returns_empty_list(self):
        """Should return empty list for empty input."""
        from src.liquidationheatmap.models.time_evolving_heatmap import (
            calculate_time_evolving_heatmap,
        )

        snapshots = calculate_time_evolving_heatmap(
            candles=[],
            oi_deltas=[],
            symbol="BTCUSDT",
        )

        assert len(snapshots) == 0
