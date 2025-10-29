# Feature Specification: Liquidation Heatmap System

**Feature ID**: 001-liquidation-heatmap-mvp
**Created**: 2025-10-28
**Status**: Draft
**Team**: liquidation-development (data-engineer, quant-analyst, visualization-renderer)

---

## Problem Statement

### Current Gap

Traders lack visibility into **where liquidation cascades will occur**, making it impossible to:
- Predict price zones with high liquidation risk (support/resistance)
- Avoid entering positions near liquidation clusters
- Identify arbitrage opportunities when cascades trigger

**Existing solutions** (Coinglass, Kingfisher) provide:
- ✅ Real-time liquidation events (reactive)
- ❌ **Predictive** liquidation levels from open positions (proactive)
- ❌ Historical liquidation patterns analysis
- ❌ Ensemble models for confidence scoring

### Opportunity

**Build predictive liquidation heatmap** using Binance historical data:
- Calculate liquidation prices from Open Interest + leverage tiers
- Cluster liquidations by price levels (heatmap density)
- Compare multiple models (Binance formula, funding rate adjusted, ensemble)
- Visualize as Coinglass-style heatmap with **<100 lines of Plotly.js** (KISS)

**Value**: Proactive risk management vs reactive event tracking.

---

## Architecture: Black Box Design

### Principle: "Infrastructure ≠ Business Logic"

Following UTXOracle pattern, **separate concerns**:

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Data Infrastructure (DuckDB)                      │
│  ├─ Binance CSV → DuckDB ingestion (symlinked data)         │
│  ├─ Schema: trades, openInterest, fundingRate, liquidations │
│  └─ Responsibility: data-engineer agent                     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Black Box Models (Reusable Components)            │
│  ├─ Model A: Binance Liquidation Formula                    │
│  │   └─ liquidation_price = entry * (1 ± 1/lev ± mmr/lev)  │
│  ├─ Model B: Funding Rate Adjusted                          │
│  │   └─ Adjust liquidation by funding rate pressure         │
│  ├─ Model C: py-liquidation-map (external)                  │
│  │   └─ Leverage existing clustering algorithm              │
│  └─ Ensemble: Weighted average (A=0.5, B=0.3, C=0.2)        │
│                                                              │
│  Interface: AbstractLiquidationModel                         │
│    - calculate_liquidations(oi_data, leverage) → DataFrame  │
│    - confidence_score() → float [0-1]                        │
│  Responsibility: quant-analyst agent                         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: API (FastAPI - Historical Only for MVP)           │
│  ├─ REST: /liquidations/heatmap?symbol=BTCUSDT&timeframe=1d │
│  ├─ REST: /liquidations/levels?model=ensemble                │
│  ├─ REST: /liquidations/history (historical events)         │
│  └─ Nautilus Integration: /trading/signals (Phase 2)        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: Visualization (Plotly.js - Single HTML)           │
│  ├─ Heatmap: 2D (time × price) with density color scale     │
│  ├─ Liquidation Map: Bar chart by leverage (5x-100x)        │
│  ├─ Ensemble View: Compare 3 models side-by-side            │
│  └─ ~50 lines JS (vs 500+ lines Canvas custom code) - KISS  │
│  Responsibility: visualization-renderer agent                │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Sources & Schema

### Binance Historical Data (Symlinked from 3TB-WDC)

**Location**: `data/raw/BTCUSDT/` → `/media/sam/3TB-WDC/binance-history-data-downloader/downloads/BTCUSDT`

**Files**:
1. **trades/** - Individual trades (price, qty, timestamp, buyer_is_maker)
2. **bookDepth/** - Order book snapshots (bids/asks by price level)
3. **fundingRate/** - 8-hour funding rate (positive = longs pay shorts)
4. **metrics/** - Open Interest (total notional value of open positions)
5. **klines/** - OHLCV candlestick data (for visualization overlay)

### DuckDB Schema (Analytics-Optimized)

**Database**: `data/processed/liquidations.duckdb`

**Tables**:

```sql
-- Liquidation levels calculated from Open Interest
CREATE TABLE liquidation_levels (
    timestamp TIMESTAMP,
    symbol VARCHAR,
    model VARCHAR,  -- 'binance', 'funding_adjusted', 'ensemble'
    price_level DECIMAL(18,2),
    liquidation_volume DECIMAL(18,8),  -- Notional USD
    leverage_tier VARCHAR,  -- '5x', '10x', '25x', '50x', '100x'
    side VARCHAR,  -- 'long' or 'short'
    confidence DECIMAL(3,2)  -- 0.0 to 1.0
);

-- Historical liquidation events (actual occurred liquidations)
CREATE TABLE liquidation_history (
    timestamp TIMESTAMP,
    symbol VARCHAR,
    price DECIMAL(18,2),
    quantity DECIMAL(18,8),
    side VARCHAR,
    leverage INT
);

-- Heatmap cache (pre-aggregated for fast queries)
CREATE TABLE heatmap_cache (
    time_bucket TIMESTAMP,  -- 1-hour buckets
    price_bucket DECIMAL(18,2),  -- $100 buckets
    symbol VARCHAR,
    model VARCHAR,
    density BIGINT,  -- Count of liquidations in bucket
    volume DECIMAL(18,8)  -- Total USD liquidated
);
```

**Ingestion Pipeline** (data-engineer):
```bash
# scripts/ingest_historical.py
uv run python scripts/ingest_historical.py \
  --symbol BTCUSDT \
  --start-date 2024-01-01 \
  --end-date 2024-12-31
```

---

## Black Box Models: Liquidation Calculation

### Interface Definition

```python
# src/liquidationheatmap/models/base.py
from abc import ABC, abstractmethod
import pandas as pd

class AbstractLiquidationModel(ABC):
    """Base interface for liquidation models (black box pattern)."""

    @abstractmethod
    def calculate_liquidations(
        self,
        open_interest: pd.DataFrame,  # columns: timestamp, price, oi_volume, leverage
        current_price: float
    ) -> pd.DataFrame:
        """Calculate liquidation levels from open interest data.

        Returns:
            DataFrame with columns: price_level, volume, side, confidence
        """
        pass

    @abstractmethod
    def confidence_score(self) -> float:
        """Return model confidence [0-1] based on data quality."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Unique identifier for this model."""
        pass
```

### Model A: Binance Standard Formula

**Reference**: [Binance Liquidation Formula](https://www.binance.com/en/support/faq/liquidation)

```python
# src/liquidationheatmap/models/binance_standard.py
class BinanceStandardModel(AbstractLiquidationModel):
    """Official Binance liquidation formula."""

    model_name = "binance_standard"

    def calculate_liquidations(self, oi_data, current_price):
        """
        Long liquidation: entry_price * (1 - 1/leverage + mmr/leverage)
        Short liquidation: entry_price * (1 + 1/leverage - mmr/leverage)

        Where mmr = maintenance margin rate (varies by leverage tier)
        """
        # Maintenance margin rates (Binance BTCUSDT)
        MMR_TABLE = {
            5: 0.004,    # 0.4%
            10: 0.005,   # 0.5%
            25: 0.01,    # 1%
            50: 0.02,    # 2%
            100: 0.05    # 5%
        }

        liquidations = []
        for leverage in [5, 10, 25, 50, 100]:
            mmr = MMR_TABLE[leverage]

            # Long positions liquidate BELOW entry
            long_liq = current_price * (1 - 1/leverage + mmr/leverage)
            liquidations.append({
                'price_level': long_liq,
                'volume': oi_data[oi_data['leverage'] == leverage]['oi_volume'].sum(),
                'side': 'long',
                'leverage': leverage,
                'confidence': 0.95  # High confidence (official formula)
            })

            # Short positions liquidate ABOVE entry
            short_liq = current_price * (1 + 1/leverage - mmr/leverage)
            liquidations.append({
                'price_level': short_liq,
                'volume': oi_data[oi_data['leverage'] == leverage]['oi_volume'].sum(),
                'side': 'short',
                'leverage': leverage,
                'confidence': 0.95
            })

        return pd.DataFrame(liquidations)
```

### Model B: Funding Rate Adjusted

**Hypothesis**: Extreme funding rates predict liquidation pressure.

```python
# src/liquidationheatmap/models/funding_adjusted.py
class FundingAdjustedModel(AbstractLiquidationModel):
    """Adjust liquidation levels by funding rate pressure."""

    model_name = "funding_adjusted"

    def calculate_liquidations(self, oi_data, current_price, funding_rate):
        """
        If funding_rate > 0.1% (longs pay shorts):
          → Shift long liquidations CLOSER (more risk)
          → Shift short liquidations FARTHER (less risk)
        """
        base_model = BinanceStandardModel()
        base_liq = base_model.calculate_liquidations(oi_data, current_price)

        # Adjust by funding rate (example: 10% shift per 0.1% funding)
        adjustment_factor = funding_rate * 100  # Scale to percentage

        base_liq['price_level'] = base_liq.apply(lambda row:
            row['price_level'] * (1 - adjustment_factor * 0.01) if row['side'] == 'long'
            else row['price_level'] * (1 + adjustment_factor * 0.01),
            axis=1
        )
        base_liq['confidence'] = 0.75  # Lower confidence (experimental)

        return base_liq
```

### Model C: py-liquidation-map Integration

**Leverage existing library** (Code Reuse First principle):

```python
# src/liquidationheatmap/models/py_liquidation_map.py
from py_liquidation_map import BinanceLiquidationCluster  # External library

class PyLiquidationMapModel(AbstractLiquidationModel):
    """Wrapper around py-liquidation-map library."""

    model_name = "py_liquidation_map"

    def calculate_liquidations(self, oi_data, current_price):
        """Use external clustering algorithm."""
        cluster = BinanceLiquidationCluster(symbol='BTCUSDT')
        levels = cluster.calculate_heatmap(
            open_interest=oi_data['oi_volume'].values,
            prices=oi_data['price'].values
        )

        return pd.DataFrame({
            'price_level': levels['price'],
            'volume': levels['volume'],
            'side': levels['side'],
            'confidence': 0.80  # Medium confidence (external model)
        })
```

### Ensemble Model: Weighted Average

**Combine models for robustness**:

```python
# src/liquidationheatmap/models/ensemble.py
class EnsembleModel(AbstractLiquidationModel):
    """Weighted average of multiple models."""

    model_name = "ensemble"

    def __init__(self, weights=None):
        self.models = [
            (BinanceStandardModel(), 0.5),  # 50% weight
            (FundingAdjustedModel(), 0.3),  # 30% weight
            (PyLiquidationMapModel(), 0.2)  # 20% weight
        ]
        if weights:
            self.models = [(m, w) for (m, _), w in zip(self.models, weights)]

    def calculate_liquidations(self, oi_data, current_price, **kwargs):
        """Weighted average of model predictions."""
        all_predictions = []

        for model, weight in self.models:
            pred = model.calculate_liquidations(oi_data, current_price, **kwargs)
            pred['weight'] = weight
            all_predictions.append(pred)

        # Aggregate by price bucket ($100 buckets)
        combined = pd.concat(all_predictions)
        combined['price_bucket'] = (combined['price_level'] // 100) * 100

        ensemble = combined.groupby(['price_bucket', 'side']).apply(
            lambda x: pd.Series({
                'volume': (x['volume'] * x['weight']).sum(),
                'confidence': (x['confidence'] * x['weight']).sum()
            })
        ).reset_index()

        return ensemble.rename(columns={'price_bucket': 'price_level'})
```

---

## API Design: FastAPI REST Endpoints

### Endpoints

```python
# api/main.py
from fastapi import FastAPI, Query
from datetime import datetime

app = FastAPI(title="LiquidationHeatmap API")

@app.get("/liquidations/heatmap")
async def get_liquidation_heatmap(
    symbol: str = "BTCUSDT",
    model: str = Query("ensemble", enum=["binance_standard", "funding_adjusted", "ensemble"]),
    timeframe: str = "1d",  # 1h, 4h, 1d, 7d
    start: datetime = None,
    end: datetime = None
):
    """
    Get liquidation heatmap data (2D: time × price).

    Returns:
        {
            "symbol": "BTCUSDT",
            "model": "ensemble",
            "timeframe": "1d",
            "data": [
                {"time": "2024-01-01T00:00:00Z", "price_bucket": 45000, "density": 1234, "volume": 5.67},
                ...
            ],
            "current_price": 67234.56,
            "metadata": {
                "total_liquidation_volume": 123.45,
                "highest_density_price": 66000
            }
        }
    """
    # Query DuckDB heatmap_cache table
    pass

@app.get("/liquidations/levels")
async def get_liquidation_levels(
    symbol: str = "BTCUSDT",
    model: str = "ensemble",
    leverage: int = None  # Filter by leverage tier
):
    """
    Get current liquidation price levels (for active positions).

    Returns:
        {
            "symbol": "BTCUSDT",
            "model": "ensemble",
            "current_price": 67234.56,
            "levels": [
                {"price": 66000, "volume": 12.34, "side": "long", "leverage": "10x", "confidence": 0.85},
                {"price": 68500, "volume": 8.91, "side": "short", "leverage": "25x", "confidence": 0.82}
            ],
            "timestamp": "2024-10-28T12:00:00Z"
        }
    """
    pass

@app.get("/liquidations/history")
async def get_liquidation_history(
    symbol: str = "BTCUSDT",
    start: datetime = None,
    end: datetime = None
):
    """
    Get historical liquidation events (actual occurred liquidations).
    """
    pass

@app.get("/liquidations/compare-models")
async def compare_models(symbol: str = "BTCUSDT"):
    """
    Compare all models side-by-side.

    Returns:
        {
            "models": [
                {"name": "binance_standard", "levels": [...], "avg_confidence": 0.95},
                {"name": "funding_adjusted", "levels": [...], "avg_confidence": 0.75},
                {"name": "ensemble", "levels": [...], "avg_confidence": 0.85}
            ]
        }
    """
    pass

# Future: Nautilus Trader integration
@app.get("/trading/signals")
async def get_trading_signals(symbol: str = "BTCUSDT"):
    """
    Generate trading signals based on liquidation clusters.

    Logic:
    - If price approaching liquidation cluster (±2%): AVOID entry
    - If cascade triggered (actual liquidations > predicted): REVERSAL opportunity
    """
    pass
```

---

## Visualization: Plotly.js (KISS - Minimal Code)

### Goal: <100 lines of JavaScript

**Why Plotly.js > Custom Canvas**:
- ✅ 90% less code (50 lines vs 500+)
- ✅ Built-in zoom/pan/hover
- ✅ Responsive by default
- ✅ No WebGL debugging

### Heatmap View (Coinglass-style)

```html
<!-- frontend/heatmap.html -->
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
</head>
<body>
    <div id="heatmap" style="width:100%;height:600px"></div>
    <script>
        // Fetch data from API
        fetch('/liquidations/heatmap?symbol=BTCUSDT&model=ensemble&timeframe=1d')
            .then(r => r.json())
            .then(data => {
                // Prepare 2D heatmap (time × price)
                const times = [...new Set(data.data.map(d => d.time))];
                const prices = [...new Set(data.data.map(d => d.price_bucket))];

                // Create density matrix
                const z = prices.map(p =>
                    times.map(t => {
                        const point = data.data.find(d => d.time === t && d.price_bucket === p);
                        return point ? point.density : 0;
                    })
                );

                // Plotly heatmap
                Plotly.newPlot('heatmap', [{
                    type: 'heatmap',
                    x: times,
                    y: prices,
                    z: z,
                    colorscale: [
                        [0, 'rgb(68,1,84)'],      // Dark purple
                        [0.5, 'rgb(59,82,139)'],  // Blue
                        [0.75, 'rgb(33,145,140)'], // Teal
                        [1, 'rgb(253,231,37)']    // Yellow
                    ],
                    hovertemplate: 'Time: %{x}<br>Price: $%{y}<br>Density: %{z}<extra></extra>'
                }], {
                    title: 'BTC/USDT Liquidation Heatmap',
                    xaxis: {title: 'Time'},
                    yaxis: {title: 'Price (USD)'},
                    height: 600
                });

                // Overlay current price line
                const currentPrice = data.current_price;
                Plotly.addTraces('heatmap', {
                    type: 'scatter',
                    x: times,
                    y: Array(times.length).fill(currentPrice),
                    mode: 'lines',
                    line: {color: 'red', width: 2, dash: 'dash'},
                    name: 'Current Price'
                });
            });
    </script>
</body>
</html>
```

**Total**: ~50 lines (vs 500+ Canvas code) - **90% reduction** ✅

### Liquidation Map View (Bar Chart)

```javascript
// frontend/liquidation_map.html
fetch('/liquidations/levels?symbol=BTCUSDT&model=ensemble')
    .then(r => r.json())
    .then(data => {
        // Separate long/short
        const longs = data.levels.filter(l => l.side === 'long');
        const shorts = data.levels.filter(l => l.side === 'short');

        Plotly.newPlot('map', [
            {
                x: longs.map(l => l.price),
                y: longs.map(l => l.volume),
                type: 'bar',
                name: 'Long Liquidations',
                marker: {color: 'red'}
            },
            {
                x: shorts.map(l => l.price),
                y: shorts.map(l => l.volume),
                type: 'bar',
                name: 'Short Liquidations',
                marker: {color: 'green'}
            }
        ], {
            title: 'Liquidation Levels by Price',
            xaxis: {title: 'Price (USD)'},
            yaxis: {title: 'Volume (BTC)'}
        });
    });
```

**Total**: ~30 lines ✅

---

## User Stories & Acceptance Criteria

### Story 1: Calculate Future Liquidation Levels (Priority: P0)

**As a** quant analyst
**I want to** calculate liquidation prices from current Open Interest
**So that** I can predict where liquidation cascades will occur

**Acceptance Criteria**:
1. **Given** Open Interest data from DuckDB
   **When** I run `python scripts/calculate_liquidations.py --model ensemble`
   **Then** DuckDB `liquidation_levels` table contains predictions for all leverage tiers

2. **Given** BTC price = $67,234.56
   **When** I query `/liquidations/levels?model=binance_standard`
   **Then** API returns long liquidations BELOW current price and shorts ABOVE

3. **Given** Ensemble model combines 3 models
   **When** Individual models disagree by >5%
   **Then** Ensemble confidence score is <0.7 (low confidence flag)

**Test**: Compare predictions vs actual liquidations (±2% accuracy)

---

### Story 2: Visualize Historical Liquidation Patterns (Priority: P1)

**As a** trader
**I want to** see heatmap of past liquidation clusters
**So that** I can identify recurring support/resistance zones

**Acceptance Criteria**:
1. **Given** 30 days of historical data
   **When** I open `/heatmap.html?symbol=BTCUSDT&timeframe=30d`
   **Then** Plotly heatmap shows 2D density (time × price) with color gradient

2. **Given** Current price line overlayed on heatmap
   **When** Price approaches high-density zone (±2%)
   **Then** Warning indicator appears: "Liquidation cluster ahead"

3. **Given** Zoom/pan enabled by default
   **When** I zoom into specific date range
   **Then** Heatmap updates with higher resolution data

**Test**: Visual regression testing (screenshot comparison)

---

### Story 3: Compare Multiple Models (Priority: P1)

**As a** researcher
**I want to** compare 3 liquidation models side-by-side
**So that** I can validate which model is most accurate

**Acceptance Criteria**:
1. **Given** Binance Standard, Funding Adjusted, Ensemble models
   **When** I query `/liquidations/compare-models`
   **Then** API returns 3 prediction sets with confidence scores

2. **Given** Historical liquidation events
   **When** I backtest models against actual data (7 days)
   **Then** System reports accuracy: Model A=92%, Model B=85%, Ensemble=94%

3. **Given** Model comparison dashboard
   **When** I view side-by-side charts
   **Then** Differences are highlighted (±5% zones marked)

**Test**: Unit tests for each model + integration test for ensemble

---

### Story 4: Nautilus Trader Integration (Priority: P2 - Future)

**As a** algorithmic trader
**I want to** receive liquidation-based trading signals
**So that** Nautilus Trader can avoid dangerous zones or exploit cascades

**Acceptance Criteria**:
1. **Given** Price within 2% of liquidation cluster
   **When** Nautilus queries `/trading/signals`
   **Then** API returns `{action: "AVOID", reason: "Liquidation cluster at $66,000"}`

2. **Given** Liquidation cascade triggered (actual > predicted volume)
   **When** System detects cascade via WebSocket
   **Then** Signal: `{action: "REVERSAL_OPPORTUNITY", confidence: 0.85}`

3. **Given** Ensemble confidence <0.5
   **When** Nautilus requests signal
   **Then** Return `{action: "WAIT", reason: "Low model confidence"}`

**Test**: Paper trading backtest (30 days) - measure P&L vs no-signal baseline

---

## Success Criteria

### Functional Requirements

- ✅ **3 liquidation models** implemented (Binance, Funding Adjusted, Ensemble)
- ✅ **DuckDB ingestion** from Binance CSV (<5 seconds per GB)
- ✅ **FastAPI endpoints** respond <50ms (cached queries)
- ✅ **Plotly.js visualization** in <100 lines of code
- ✅ **Historical analysis** covers 30+ days of data

### Code Quality Requirements

- ✅ **Total codebase ≤800 lines** Python (excluding tests)
- ✅ **80%+ test coverage** (pytest)
- ✅ **Black box interface** enforced (AbstractLiquidationModel)
- ✅ **Zero code duplication** between models

### Performance Requirements

- ✅ **DuckDB queries** <50ms (heatmap cache)
- ✅ **Model calculation** <2 seconds for 30-day dataset
- ✅ **API latency** <100ms (p95)

---

## Non-Functional Requirements

### Error Handling

**When DuckDB query fails**:
- Retry 3 times with exponential backoff (1s, 3s, 9s)
- Log ERROR with full traceback
- Return HTTP 503 with retry_after header

**When model confidence <0.3**:
- Log WARNING
- Store result with `is_valid=false` flag
- API returns low confidence warning in response

### Configuration

```bash
# .env
DUCKDB_PATH=/media/sam/1TB/LiquidationHeatmap/data/processed/liquidations.duckdb
BINANCE_DATA_PATH=/media/sam/3TB-WDC/binance-history-data-downloader/downloads/BTCUSDT
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000
MODEL_WEIGHTS='{"binance_standard": 0.5, "funding_adjusted": 0.3, "py_liquidation_map": 0.2}'
```

### Logging

```python
import structlog
logger = structlog.get_logger("liquidation_heatmap")

logger.info(
    "liquidations_calculated",
    model="ensemble",
    symbol="BTCUSDT",
    levels_count=42,
    avg_confidence=0.87,
    duration_seconds=1.2
)
```

---

## Out of Scope (Future Work)

- ❌ Real-time WebSocket streaming → Not needed (Nautilus handles real-time)
- ❌ Multi-symbol support (ETH, SOL, etc.) → Defer to Phase 3
- ❌ Machine learning price prediction → Out of scope
- ❌ Mobile app → Not planned
- ❌ Order book depth integration → Phase 4
- ❌ Redis pub/sub → Not needed for MVP (historical analysis only)

---

## Dependencies

### Prerequisite

- ✅ Repository setup complete (dependencies installed)
- ✅ Binance historical data symlinked (3TB-WDC)
- ✅ DuckDB 1.4.0+
- ✅ Agents: data-engineer, quant-analyst

### External Libraries

- ✅ **py-liquidation-map** (pip install py-liquidation-map) - Model C
- ✅ **plotly** (already installed) - Visualization
- ✅ **fastapi** (already installed) - API
- ✅ **pandas** (already installed) - Data wrangling

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| py-liquidation-map unavailable | Medium | Low | Implement Model A+B first (80% value) |
| DuckDB performance on large datasets | High | Medium | Pre-aggregate in heatmap_cache table |
| Model accuracy <80% | Medium | Medium | Use ensemble + backtesting to tune weights |
| Plotly.js limited customization | Low | Low | Fallback to lightweight Canvas if needed |

---

## References

- **Parent Spec**: `/media/sam/1TB/UTXOracle/specs/003-mempool-integration-refactor/spec.md`
- **Coinglass Liquidation Heatmap**: https://www.coinglass.com/LiquidationData
- **py-liquidation-map**: https://github.com/aoki-h-jp/py-liquidation-map
- **Binance Liquidation Formula**: https://www.binance.com/en/support/faq/liquidation
- **Constitution**: `.specify/memory/constitution.md` (KISS, YAGNI, Code Reuse)

---

**Status**: Ready for `/speckit.plan` phase

**Next Command**:
```bash
/speckit.plan Use black box architecture with AbstractLiquidationModel interface. \
Implement 3 models: Binance Standard, Funding Adjusted, Ensemble (weighted average). \
DuckDB for storage (fast analytics). FastAPI for REST API. \
Plotly.js for visualization (<100 lines). Focus on KISS - minimal code.
```
