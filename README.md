# LiquidationHeatmap

Calculate and visualize cryptocurrency liquidation levels from Binance futures data using DuckDB analytics and FastAPI REST endpoints. Leverages open-source models (py-liquidation-map) for battle-tested algorithms.

## Quick Start

```bash
# Install dependencies
uv sync

# Ingest historical CSV data (example: Jan 2025)
uv run python scripts/ingest_historical.py --start 2025-01-01 --end 2025-01-31

# Run FastAPI server
uv run uvicorn api.main:app --reload

# Open visualization
open http://localhost:8000/heatmap.html

# Run tests
uv run pytest
```

## Architecture

**3-Layer Design**:
1. **Data**: DuckDB (zero-copy CSV ingestion, fast analytics)
2. **API**: FastAPI (REST endpoints) + Redis (pub/sub streaming)
3. **Viz**: Plotly.js (interactive heatmaps)

See `CLAUDE.md` for detailed architecture and development workflow.

## Data Sources

- **Raw CSV**: `data/raw/BTCUSDT/` (symlinked to Binance historical data on 3TB-WDC)
  - trades/, bookDepth/, fundingRate/, metrics/ (Open Interest)
- **Processed**: `data/processed/*.duckdb` (analytics-optimized tables)
- **Cache**: `data/cache/` (Redis snapshots, temporary files)

**Note**: Raw data is read-only (symlinked). All analytics use DuckDB as single source of truth.

## Development

### Setup

```bash
# Clone repository
git clone <repo-url>
cd LiquidationHeatmap

# Install dependencies
uv sync

# Copy environment template
cp .env.example .env
# Edit .env with your configuration
```

### Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test
uv run pytest tests/test_module.py::test_function
```

### TDD Workflow

This project uses Test-Driven Development (TDD):

1. **RED**: Write failing test first
2. **GREEN**: Write minimal code to pass test
3. **REFACTOR**: Clean up code while tests pass

See `CLAUDE.md` for detailed TDD workflow.

## Project Structure

```
LiquidationHeatmap/
├── src/              # Core application code
├── tests/            # Test suite
├── scripts/          # Utilities and batch jobs
├── data/             # Data directory
│   ├── raw/          # External data (symlink)
│   ├── processed/    # DuckDB databases
│   └── cache/        # Temporary cache
├── frontend/         # Visualization (if applicable)
├── CLAUDE.md         # Development guide for Claude Code
├── README.md         # This file
└── pyproject.toml    # Dependencies (UV)
```

## Contributing

1. Follow TDD workflow (see `CLAUDE.md`)
2. Run tests before committing
3. Format code with `ruff format .`
4. Lint code with `ruff check .`
5. Write clear commit messages (explain WHY, not just WHAT)

## Key Features

- ✅ **Zero-copy CSV ingestion**: DuckDB loads 10GB in ~5 seconds
- ✅ **Binance liquidation formulas**: Leverage py-liquidation-map algorithms
- ✅ **Real-time streaming**: Redis pub/sub (Nautilus pattern)
- ✅ **Interactive heatmaps**: Plotly.js visualization (no build step)
- ✅ **Test-Driven Development**: TDD guard enforces 80% coverage

## References

- [py-liquidation-map](https://github.com/aoki-h-jp/py-liquidation-map) - Liquidation clustering
- [binance-liquidation-tracker](https://github.com/hgnx/binance-liquidation-tracker) - Real-time tracking
- [Binance Liquidation Guide](https://www.binance.com/en/support/faq/liquidation) - Official formulas

## License

MIT License
