"""TDD tests for aggTrades CSV loading."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.liquidationheatmap.ingestion.csv_loader import load_aggtrades_csv


def test_load_aggtrades_csv_returns_dataframe_with_required_columns():
    """Test that load_aggtrades_csv returns DataFrame with timestamp, symbol, price, quantity, side, gross_value."""
    # Create temporary CSV with aggTrades format
    csv_content = """agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker
2867872924,113988.7,0.018,6669431038,6669431038,1759276800034,true
2867872925,114000.0,3.187,6669431039,6669431079,1759276801145,false
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        temp_path = f.name

    try:
        # Act
        df = load_aggtrades_csv(temp_path)

        # Assert - must have required columns
        required_columns = {"timestamp", "symbol", "price", "quantity", "side", "gross_value"}
        assert required_columns.issubset(df.columns), (
            f"Missing columns: {required_columns - set(df.columns)}"
        )

        # Assert - must have 2 rows
        assert len(df) == 2

        # Assert - timestamp must be datetime
        assert df["timestamp"].dtype == "datetime64[ns]"

        # Assert - side must be 'buy' or 'sell'
        assert set(df["side"].unique()).issubset({"buy", "sell"})

        # Assert - gross_value = price * quantity
        assert (df["gross_value"] == df["price"] * df["quantity"]).all()

    finally:
        Path(temp_path).unlink()


def test_load_aggtrades_csv_converts_transact_time_to_timestamp():
    """Test that transact_time (milliseconds) is converted to datetime timestamp."""
    csv_content = """agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker
2867872924,113988.7,0.018,6669431038,6669431038,1609459200000,true
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        temp_path = f.name

    try:
        df = load_aggtrades_csv(temp_path)

        # 1609459200000 ms = 2021-01-01 00:00:00 UTC
        expected_timestamp = pd.Timestamp("2021-01-01 00:00:00")
        assert df["timestamp"].iloc[0] == expected_timestamp

    finally:
        Path(temp_path).unlink()


def test_load_aggtrades_csv_maps_is_buyer_maker_to_side():
    """Test that is_buyer_maker=true → side='sell', is_buyer_maker=false → side='buy'."""
    csv_content = """agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker
1,100.0,1.0,1,1,1609459200000,true
2,100.0,1.0,2,2,1609459200001,false
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        temp_path = f.name

    try:
        df = load_aggtrades_csv(temp_path)

        # When is_buyer_maker=true, aggressor is selling (maker is buying)
        # So aggTrade is a SELL
        assert df[df.index == 0]["side"].iloc[0] == "sell"

        # When is_buyer_maker=false, aggressor is buying (maker is selling)
        # So aggTrade is a BUY
        assert df[df.index == 1]["side"].iloc[0] == "buy"

    finally:
        Path(temp_path).unlink()


def test_load_aggtrades_csv_raises_error_if_file_not_found():
    """Test that FileNotFoundError is raised if CSV doesn't exist."""
    with pytest.raises(FileNotFoundError):
        load_aggtrades_csv("/nonexistent/file.csv")
