"""Test streaming aggTrades ingestion (OOM fix).

Tests the file-by-file approach that prevents exit 137 OOM crash.
"""



from src.liquidationheatmap.ingestion.aggtrades_streaming import get_aggtrades_files


def test_get_aggtrades_files_returns_existing_files_in_range(tmp_path):
    """Should return only files that exist within date range."""
    # Arrange
    aggtrades_dir = tmp_path / "BTCUSDT" / "aggTrades"
    aggtrades_dir.mkdir(parents=True)

    # Create some files
    (aggtrades_dir / "BTCUSDT-aggTrades-2024-01-01.csv").touch()
    (aggtrades_dir / "BTCUSDT-aggTrades-2024-01-02.csv").touch()
    (aggtrades_dir / "BTCUSDT-aggTrades-2024-01-05.csv").touch()

    # Act
    files = get_aggtrades_files(tmp_path, "BTCUSDT", "2024-01-01", "2024-01-03")

    # Assert
    assert len(files) == 2
    assert files[0].name == "BTCUSDT-aggTrades-2024-01-01.csv"
    assert files[1].name == "BTCUSDT-aggTrades-2024-01-02.csv"
