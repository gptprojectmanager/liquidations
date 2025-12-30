# Quickstart: 014-validation-pipeline

**Feature**: Validation Pipeline
**Date**: 2025-12-30
**Purpose**: Get started with the validation pipeline quickly

---

## Prerequisites

1. **Database**: DuckDB with `liquidation_snapshots` table populated
   ```bash
   ls data/processed/liquidations.duckdb  # Should exist
   ```

2. **Dependencies**: All required packages installed
   ```bash
   uv sync
   ```

3. **Tesseract** (for Coinglass OCR validation, optional):
   ```bash
   sudo apt install tesseract-ocr tesseract-ocr-eng
   ```

---

## Quick Commands

### 1. Run Backtest Validation (Primary)

```bash
# Run backtest for BTCUSDT (last 30 days)
uv run python scripts/run_backtest.py --symbol BTCUSDT --days 30

# View results
cat reports/backtest_latest.md
```

**Expected Output**:
```
✅ Gate 2 PASSED: F1=80.93% >= 60%
```

### 2. Check Existing Results

```bash
# View latest backtest report
cat reports/backtest_2024.md

# View validation metrics
uv run python -c "
import duckdb
conn = duckdb.connect('data/processed/liquidations.duckdb', read_only=True)
print(conn.execute('SELECT * FROM validation_backtest_results ORDER BY created_at DESC LIMIT 5').fetchdf())
"
```

### 3. Run Full Pipeline

```bash
# Run validation pipeline with default settings
uv run python scripts/run_validation_pipeline.py --symbol BTCUSDT

# Run with tolerance sweep (0.5%, 1%, 2%)
uv run python scripts/run_validation_pipeline.py --sweep-tolerance

# Run with JSON output for CI
uv run python scripts/run_validation_pipeline.py \
    --symbol BTCUSDT \
    --output reports/validation_result.json \
    --ci  # Exit code 1 on Gate 2 FAIL

# Check gate status
jq '.gate_2_passed' reports/validation_result.json
```

### 4. View Dashboard

```bash
# Start API server
uv run uvicorn src.api.validation_app:app --reload --port 8000

# Open in browser
# API docs: http://localhost:8000/docs
# Dashboard: Open frontend/validation_dashboard.html in browser

# Or test API directly
curl http://localhost:8000/api/validation/dashboard?symbol=BTCUSDT
```

---

## Gate 2 Decision Matrix

| F1 Score | Grade | Decision | Action |
|----------|-------|----------|--------|
| ≥ 80% | A | PASS | Production ready, proceed to ETH expansion |
| ≥ 70% | B | PASS | Good, minor improvements possible |
| ≥ 60% | C | PASS | Acceptable, document limitations |
| ≥ 40% | - | ACCEPTABLE | Review model, fix issues before expansion |
| < 40% | F | FAIL | **STOP** - Model rework required |

**Current Status**: F1 = **80.93%** → Grade **A** → **PASS**

---

## Key Files

| File | Purpose |
|------|---------|
| `scripts/run_validation_pipeline.py` | **Unified CLI** for pipeline |
| `scripts/run_backtest.py` | Run historical backtest |
| `scripts/validate_vs_coinglass.py` | Run Coinglass comparison |
| `src/validation/pipeline/orchestrator.py` | Pipeline orchestrator |
| `src/validation/pipeline/models.py` | Data models & gate logic |
| `src/api/endpoints/dashboard.py` | Dashboard API endpoints |
| `frontend/validation_dashboard.html` | Dashboard UI |
| `.github/workflows/validation.yml` | CI workflow |

---

## Troubleshooting

### Database Not Found

```bash
# Check database path
ls -la data/processed/liquidations.duckdb

# If missing, run ingestion first
uv run python scripts/ingest_aggtrades.py --help
```

### No Snapshots for Backtest

```bash
# Check if liquidation_snapshots table exists
uv run python -c "
import duckdb
conn = duckdb.connect('data/processed/liquidations.duckdb', read_only=True)
print(conn.execute('SHOW TABLES').fetchdf())
print(conn.execute('SELECT COUNT(*) FROM liquidation_snapshots').fetchone())
"
```

### Gate 2 FAIL

If backtest returns F1 < 40%:
1. Check data quality: Are there gaps in the snapshot data?
2. Check tolerance: Try `--tolerance-pct 3.0` (wider tolerance)
3. Check period: Use a more recent date range
4. Review model: May need algorithm improvements

---

## Next Steps

After running validation:

1. **If PASS (F1 ≥ 60%)**:
   - Document results in `reports/`
   - Proceed to ETH expansion (feature 009)
   - Set up CI workflow for automated validation

2. **If FAIL (F1 < 40%)**:
   - Investigate missed liquidations (`false_negatives`)
   - Review tolerance settings
   - Consider model algorithm improvements

---

## CI Integration

```bash
# Trigger validation manually via GitHub CLI
gh workflow run validation.yml -f symbol=BTCUSDT

# View workflow results
gh run list --workflow=validation.yml

# The workflow runs:
# - Weekly on Monday 6am UTC
# - On model changes (src/liquidationheatmap/models/**)
# - Manual dispatch via GitHub UI or CLI
```

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/validation/dashboard` | GET | Dashboard metrics (F1, trends, alerts) |
| `/api/validation/pipeline/run` | POST | Trigger pipeline run |
| `/api/validation/pipeline/status/{run_id}` | GET | Check run status |
| `/api/validation/history` | GET | Validation history (paginated) |

**Example API Calls**:
```bash
# Get dashboard metrics
curl "http://localhost:8000/api/validation/dashboard?symbol=BTCUSDT&days=30"

# Trigger pipeline run
curl -X POST "http://localhost:8000/api/validation/pipeline/run" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT", "validation_types": ["backtest"]}'

# Check status
curl "http://localhost:8000/api/validation/pipeline/status/{run_id}"
```

See `specs/014-validation-pipeline/contracts/dashboard_api.json` for OpenAPI specification.
