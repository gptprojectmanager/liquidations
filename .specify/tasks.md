# Tasks - Liquidation Heatmap MVP

## ✅ Completed

### Layer 1: Data Infrastructure (DuckDB)
- [x] Initialize DuckDB schema (5 tables)
- [x] Implement CSV loaders (Open Interest, Funding Rate, aggTrades)
- [x] Fix multi-format CSV support (2020-2025 compatibility)
- [x] Add aggTrades ingestion pipeline
- [x] Fix DECIMAL precision for large OI values
- [x] Implement dual-format aggTrades loader (header/no-header fallback)
- [x] Ingest 4 years of historical data (2021-2025)
  - 411,988 rows Open Interest
  - 4,119 rows Funding Rate
  - 1.9B rows aggTrades

### Layer 2: Black Box Models (Liquidation Calculations)
- [x] Implement BinanceLiquidationModel with TDD (8 tests passing, 93% coverage)
  - Long liquidation formula: `liq_price = entry * (1 - 1/lev + mmr/lev)`
  - Short liquidation formula: `liq_price = entry * (1 + 1/lev - mmr/lev)`
  - Distance calculations (percent + USD)
  - Risk level classification (high/medium/low)
  - Batch calculation for multiple leverages

### Layer 3: API (FastAPI REST Endpoints)
- [x] Create FastAPI app at `src/api/main.py`
- [x] Implement GET `/liquidations/levels` endpoint
  - Query params: `entry_price` (required), `leverage_levels` (optional), `maintenance_margin_rate` (optional)
  - Returns JSON: `{long_liquidations: [...], short_liquidations: [...]}`
  - Swagger UI auto-documentation at `/docs`
- [x] Test endpoint manually with curl (verified working)

## 🔄 In Progress
- [ ] Layer 4: Visualization (Plotly.js Frontend)
  - [ ] Create single HTML page with Plotly.js
  - [ ] 2D heatmap (time × price) with density color scale
  - [ ] Fetch data from `/liquidations/levels` endpoint
  - [ ] Interactive hover tooltips

## 📋 Pending
- [ ] Integrate API with DuckDB Open Interest data
  - [ ] Query real OI from `open_interest_history` table
  - [ ] Calculate liquidations based on real position data
  - [ ] Add timeframe selector (7d/30d/90d)
- [ ] Enhance Model with Binance MMR Tiers
  - [ ] Integrate official Binance maintenance margin rate tiers
  - [ ] Support position size-based MMR calculation
- [ ] Clustering & Heatmap Density
  - [ ] Implement density-based clustering (not continuous bands)
  - [ ] Price level aggregation for visualization
- [ ] Real-time WebSocket streaming (Phase 2)
  - [ ] Binance Futures liquidation stream integration
  - [ ] Redis pub/sub for live updates

## 🐛 Known Issues
- None currently

## 📝 Notes

### Recent Progress (2025-11-06)
**Layer 2 & 3 Implementation Complete** - Liquidation Model + API Endpoint

Completed full TDD implementation of Binance liquidation calculations:
- **9 commits** following strict RED-GREEN-REFACTOR cycle
- **8 automated tests** (all passing)
- **93% code coverage** on liquidation model
- **FastAPI endpoint** tested and working with curl

### Git Commits (Latest Session)
```
0865769 - TDD GREEN: Add FastAPI endpoint /liquidations/levels
c442572 - TDD GREEN: Add calculate_liquidation_levels() for multiple leverages
e688093 - TDD GREEN: Add risk_level classification
d4f8595 - TDD GREEN: Add distance calculations (percent and USD)
6f1b676 - TDD GREEN: Add short position liquidation support
1904402 - TDD GREEN: Implement Binance long liquidation formula
f1de9ac - TDD GREEN: Implement minimal Binance liquidation model stub
```

### API Usage Examples
```bash
# Default leverages [5, 10, 25, 50, 100, 125]
curl "http://localhost:8888/liquidations/levels?entry_price=50000"

# Custom leverages
curl "http://localhost:8888/liquidations/levels?entry_price=50000&leverage_levels=10,25,50"

# With custom maintenance margin
curl "http://localhost:8888/liquidations/levels?entry_price=50000&maintenance_margin_rate=0.005"

# Swagger UI
open http://localhost:8888/docs
```

### Data Infrastructure Status
- **DuckDB populated**: 4 years of historical data (2021-2025)
  - Open Interest: 411,988 rows
  - Funding Rate: 4,119 rows
  - aggTrades: 1,989,088,412 rows (1.9 billion)
- **Total data range**: 2021-12-01 → 2025-11-05

### Previous Notes
- Fixed critical gap issue: now supports both old (no-header) and new (header) CSV formats
- Commit: 6d29e8c - Multi-format CSV support
