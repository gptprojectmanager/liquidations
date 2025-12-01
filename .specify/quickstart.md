# Quick Start Guide: Liquidation Heatmap System

**Last Updated**: 2025-10-29
**Estimated Time**: 15 minutes
**Skill Level**: Intermediate Python developer

---

## Prerequisites

### System Requirements

- **OS**: Linux (Ubuntu 22.04+) or macOS
- **Python**: 3.11+ (installed via `uv`)
- **Disk Space**: 50GB+ available (for DuckDB + historical data)
- **RAM**: 8GB minimum, 16GB recommended

### Required Tools

✅ **Already Installed**:
- `uv` (Python package manager)
- `git` (version control)
- `pytest` (testing framework)

✅ **Data Source** (already symlinked):
- Binance historical CSV at `/media/sam/3TB-WDC/binance-history-data-downloader/downloads/BTCUSDT`
- Symlinked to `data/raw/BTCUSDT/`

---

## Step 1: Clone & Setup (2 minutes)

### Clone Repository

```bash
cd /media/sam/1TB/LiquidationHeatmap
git status  # Already initialized

# Create feature branch for development
git checkout -b feature/001-liquidation-heatmap-mvp
```

### Install Dependencies

```bash
# Install all dependencies via uv (already done, but verify)
uv sync

# Verify installation
uv run python -c "import duckdb; import fastapi; import plotly; print('✅ All dependencies OK')"
```

**Expected Output**:
```
✅ All dependencies OK
```

---

## Step 2: Verify Data Access (1 minute)

### Check Symlink

```bash
# Verify symlink to Binance data
ls -lh data/raw/BTCUSDT/

# Should show:
# metrics/  (Open Interest CSV files)
# fundingRate/  (Funding rate CSV files)
# klines/  (Price OHLCV data)
```

### List Available Data

```bash
# Check date range
ls data/raw/BTCUSDT/metrics/ | head -5
# Example: BTCUSDT-metrics-2024-10-01.csv
```

---

## Step 3: Initialize Database (3 minutes)

### Create DuckDB Schema

```bash
# Create database and tables
uv run python scripts/init_database.py

# Expected output:
# ✅ Created database: data/processed/liquidations.duckdb
# ✅ Created table: liquidation_levels
# ✅ Created table: heatmap_cache
# ✅ Created table: open_interest_history
# ✅ Created table: funding_rate_history
```

### Verify Schema

```bash
# Connect to DuckDB and check schema
uv run python << EOF
import duckdb
conn = duckdb.connect('data/processed/liquidations.duckdb')
print(conn.execute("SHOW TABLES").fetchall())
conn.close()
EOF

# Expected output:
# [('liquidation_levels',), ('heatmap_cache',), ...]
```

---

## Step 4: Ingest Sample Data (5 minutes)

### Ingest 7 Days of Historical Data

```bash
# Ingest Open Interest + Funding Rate data (7 days for testing)
uv run python scripts/ingest_historical.py \
  --symbol BTCUSDT \
  --start-date 2024-10-22 \
  --end-date 2024-10-29

# Expected output:
# 📥 Ingesting Open Interest data...
# ✅ Ingested 168 rows (7 days × 24 hours)
# 📥 Ingesting Funding Rate data...
# ✅ Ingested 21 rows (7 days × 3 funding periods)
# ⏱️  Ingestion completed in 1.2 seconds
```

### Verify Data

```bash
# Query ingested data
uv run python << EOF
import duckdb
conn = duckdb.connect('data/processed/liquidations.duckdb')
count = conn.execute("SELECT COUNT(*) FROM open_interest_history").fetchone()[0]
print(f"✅ Open Interest rows: {count}")
conn.close()
EOF

# Expected output:
# ✅ Open Interest rows: 168
```

---

## Step 5: Run Tests (2 minutes)

### Execute Full Test Suite

```bash
# Run all tests with coverage
uv run pytest --cov=src --cov-report=html -v

# Expected output:
# tests/test_smoke.py::test_imports PASSED
# tests/test_smoke.py::test_pytest_fixtures PASSED
# ============================== 2 passed in 3.49s ==============================
# Coverage: 100% (initial, no source code yet)
```

### Check Coverage Report

```bash
# Open HTML coverage report
open htmlcov/index.html

# Or view in terminal
uv run pytest --cov=src --cov-report=term-missing
```

---

## Step 6: Start Development Server (1 minute)

### Run FastAPI Server

```bash
# Start development server (will fail initially - no API code yet)
# This step is for after Milestone 3 (API layer) is implemented
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Expected (after API implementation):
# INFO:     Uvicorn running on http://0.0.0.0:8000
# INFO:     Application startup complete
```

### Access API Documentation

```bash
# Open browser (after server starts)
open http://localhost:8000/docs

# Should show Swagger UI with 4 endpoints:
# - GET /liquidations/heatmap
# - GET /liquidations/levels
# - GET /liquidations/compare-models
# - GET /health
```

---

## Step 7: View Visualization (1 minute)

### Open Plotly.js Heatmap

```bash
# After Milestone 4 (visualization) is complete
open frontend/heatmap.html

# Should open interactive heatmap in browser
# - Purple → Yellow color gradient
# - Zoom/pan enabled
# - Hover shows: time, price, density, volume
```

---

## Development Workflow

### TDD Cycle (Red-Green-Refactor)

**Example: Implementing Binance Standard Model**

#### 1. RED: Write Failing Test

```bash
# Create test file
touch tests/test_models/test_binance_standard.py

# Write test
cat > tests/test_models/test_binance_standard.py << 'EOF'
import pytest
from src.models.binance_standard import BinanceStandardModel

def test_binance_standard_calculate_liquidations():
    """Test liquidation price calculation for 10x long position."""
    model = BinanceStandardModel()

    # BTC price = $67,000, 10x leverage
    entry_price = 67000.0
    leverage = 10
    expected_liq_price = 60300.0  # Approx 10% below entry

    result = model.calculate_liquidations(
        open_interest=...,  # Mock data
        current_price=entry_price
    )

    assert result['price_level'].iloc[0] == pytest.approx(expected_liq_price, rel=0.01)
EOF

# Run test (should FAIL - no implementation yet)
uv run pytest tests/test_models/test_binance_standard.py -v

# Expected output:
# FAILED - ModuleNotFoundError: No module named 'src.models.binance_standard'
```

#### 2. GREEN: Minimal Implementation

```bash
# Create stub implementation
touch src/models/binance_standard.py

# Write minimal code to pass test
cat > src/models/binance_standard.py << 'EOF'
from src.models.base import AbstractLiquidationModel

class BinanceStandardModel(AbstractLiquidationModel):
    def calculate_liquidations(self, open_interest, current_price, **kwargs):
        # Minimal implementation
        return pd.DataFrame({'price_level': [60300.0]})

    def confidence_score(self):
        return 0.95

    @property
    def model_name(self):
        return "binance_standard"
EOF

# Run test again (should PASS)
uv run pytest tests/test_models/test_binance_standard.py -v

# Expected output:
# PASSED ✅
```

#### 3. REFACTOR: Clean Up

```bash
# Add full implementation with MMR tiers
# Add docstrings, type hints, error handling
# Re-run tests to ensure still passing

uv run pytest tests/test_models/test_binance_standard.py -v
```

---

## Common Commands

### Database

```bash
# Connect to DuckDB
uv run python -c "import duckdb; conn = duckdb.connect('data/processed/liquidations.duckdb')"

# Query data
uv run python << EOF
import duckdb
conn = duckdb.connect('data/processed/liquidations.duckdb')
print(conn.execute("SELECT * FROM liquidation_levels LIMIT 5").fetchdf())
EOF

# Export to CSV
uv run python << EOF
import duckdb
conn = duckdb.connect('data/processed/liquidations.duckdb')
conn.execute("COPY liquidation_levels TO 'data/export/liquidations.csv' (HEADER, DELIMITER ',')")
EOF
```

### Testing

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_models/test_binance_standard.py -v

# Run tests matching pattern
uv run pytest -k "liquidation" -v

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Watch mode (re-run on file change)
uv run pytest-watch
```

### Linting & Formatting

```bash
# Check code style
uv run ruff check src/

# Auto-fix issues
uv run ruff check src/ --fix

# Format code
uv run ruff format src/

# Type checking (if mypy configured)
uv run mypy src/
```

---

## Project Structure

```
LiquidationHeatmap/
├── src/                          # Source code
│   └── liquidationheatmap/
│       ├── models/               # Black box models
│       │   ├── base.py          # AbstractLiquidationModel
│       │   ├── binance_standard.py
│       │   ├── funding_adjusted.py
│       │   └── ensemble.py
│       ├── ingestion/           # Data loading
│       │   └── csv_loader.py
│       └── api/                 # FastAPI app
│           └── main.py
├── tests/                       # Test suite
│   ├── test_models/
│   ├── test_ingestion/
│   └── test_api/
├── scripts/                     # Utility scripts
│   ├── init_database.py
│   ├── ingest_historical.py
│   └── calculate_liquidations.py
├── frontend/                    # Visualization
│   ├── heatmap.html
│   └── liquidation_map.html
├── data/                        # Data files (gitignored)
│   ├── raw/                     # Symlink to Binance CSV
│   ├── processed/               # DuckDB files
│   └── cache/                   # Temp files
├── .specify/                    # SpecKit planning
│   ├── spec.md
│   ├── plan.md
│   ├── research.md
│   ├── data-model.md
│   └── contracts/openapi.yaml
├── examples/                    # Reference code
│   ├── py_liquidation_map_mapping.py
│   └── coinglass_*.png
├── pyproject.toml              # Dependencies
├── uv.lock                     # Lock file
├── CLAUDE.md                   # Development guide
└── README.md                   # User documentation
```

---

## Troubleshooting

### Issue: `uv sync` fails

**Solution**:
```bash
# Clear cache and retry
uv cache clean
uv sync --reinstall
```

### Issue: DuckDB connection error

**Solution**:
```bash
# Check file permissions
ls -lh data/processed/liquidations.duckdb

# Recreate database
rm data/processed/liquidations.duckdb
uv run python scripts/init_database.py
```

### Issue: Test imports fail

**Solution**:
```bash
# Ensure PYTHONPATH includes src/
export PYTHONPATH=$PWD:$PYTHONPATH

# Or use editable install
uv pip install -e .
```

### Issue: TDD guard blocks code

**Solution**:
```bash
# TDD guard enforces Red-Green-Refactor
# Write tests FIRST, then implement

# Temporarily disable (not recommended):
git commit --no-verify
```

---

## Next Steps

### For New Developers

1. ✅ Complete this quickstart guide
2. 📖 Read `CLAUDE.md` (architecture, principles, workflow)
3. 📖 Read `.specify/spec.md` (feature specification)
4. 📖 Read `.specify/plan.md` (implementation plan)
5. 🚀 Start with Milestone 1 (Data Layer) - assign yourself a task

### For Agents

**data-engineer**:
- Start with `scripts/ingest_historical.py` implementation
- TDD workflow: Write tests first, implement incrementally
- Goal: Ingest 30 days of data in <5 seconds

**quant-analyst**:
- Start with `src/models/base.py` (AbstractLiquidationModel interface)
- Implement `BinanceStandardModel` first (highest accuracy)
- Goal: 95% accuracy on 7-day backtest

**visualization-renderer**:
- Start with `frontend/heatmap.html` (Plotly.js)
- Use Coinglass color scheme from `examples/coinglass_model1.png`
- Goal: <100 lines of JavaScript

---

## Resources

### Documentation

- **Architecture**: `CLAUDE.md`
- **API Spec**: `.specify/contracts/openapi.yaml`
- **Data Models**: `.specify/data-model.md`
- **Research**: `.specify/research.md`

### Code Examples

- **py_liquidation_map**: `examples/py_liquidation_map_mapping.py`
- **Binance Formula**: `examples/binance_liquidation_formula_reference.txt`
- **Coinglass Viz**: `examples/coinglass_*.png`

### External Links

- **Binance Docs**: https://www.binance.com/en/support/faq/liquidation
- **DuckDB Docs**: https://duckdb.org/docs/
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **Plotly.js Docs**: https://plotly.com/javascript/

---

**Setup Status**: ✅ **READY FOR DEVELOPMENT**

**Questions?** Review `CLAUDE.md` or ask in team chat.
