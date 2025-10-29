# LiquidationHeatmap - Code Examples

This directory contains reference implementations from open-source projects for building cryptocurrency liquidation heatmaps.

## 📁 Contents

### 1. **py_liquidation_map_README.md**
Documentation and examples from the `py-liquidation-map` library.

**Source**: https://github.com/aoki-h-jp/py-liquidation-map

**Key Features**:
- Historical liquidation map generation from Binance/Bybit data
- Multiple visualization modes (gross_value, top_n, portion)
- Clustering algorithm for identifying liquidation zones

**Use Case**: Reference implementation for clustering and heatmap generation.

---

### 2. **binance_liquidation_formula_reference.txt**
Official Binance liquidation price calculation formula.

**Source**: https://gist.github.com/highfestiva/b71e76f51eed84d56c1be8ebbcc286b5

**Key Features**:
- Maintenance margin lookup table
- Position-based liquidation calculation
- Leverage-based liquidation calculation

**Formula**:
```python
liq_price = (wallet_balance + maint_amount - contract_qty*entry_price) /
            (abs(contract_qty) * (maint_margin_rate - direction))
```

**Use Case**: Core implementation for Model A (Binance Standard).

---

### 3. **matplotlib_chart_reference.txt**
Liquidation chart generation using matplotlib.

**Source**: https://github.com/StephanAkkerman/liquidations-chart

**Key Features**:
- Fetch historical data from Binance via CCXT
- Candlestick chart with volume overlay
- Comparison charts (price vs volume)

**Use Case**: Fallback visualization if Plotly.js doesn't meet requirements.

---

## 🎯 How These Examples Relate to Our Project

### Architecture Mapping (MVP - Historical Data Only)

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Data (DuckDB)                                     │
│  Source: Binance historical CSV (symlinked from 3TB-WDC)   │
│  ├─ trades/ (actual execution prices)                       │
│  ├─ metrics/ (Open Interest data)                           │
│  ├─ fundingRate/ (8h funding rates)                         │
│  └─ klines/ (OHLCV for price overlay)                       │
│  Agent: data-engineer                                        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Black Box Models                                  │
│  ├─ Model A: binance_liquidation_formula_reference.txt ✅   │
│  │   └─ Official Binance formula with MMR tiers            │
│  ├─ Model B: Custom (funding rate adjustment)               │
│  │   └─ Adjust liquidation by funding rate pressure        │
│  └─ Model C: py-liquidation-map library ✅                  │
│      └─ Clustering algorithm from external library          │
│  Agent: quant-analyst                                        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: API (FastAPI)                                     │
│  ├─ /liquidations/heatmap (2D time × price)                 │
│  ├─ /liquidations/levels (current OI-based levels)          │
│  └─ /liquidations/compare-models (ensemble view)            │
│  Note: Historical data only, no real-time WebSocket         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: Visualization (Plotly.js)                         │
│  Reference: Coinglass screenshots (purple→yellow gradient)  │
│  Implementation: <100 lines of JavaScript ✅                │
│  Agent: visualization-renderer                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Future: Real-time Integration (Phase 2+)                   │
│  Nautilus Trader integration (not WebSocket) ⏭️             │
│  Trading signals based on liquidation clusters              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Usage in Our Project

### Phase 1: Historical Analysis (MVP - Current Focus)

**From binance_liquidation_formula_reference.txt**:
```python
# src/liquidationheatmap/models/binance_standard.py
from examples.binance_liquidation_formula import binance_btc_liq_leverage

class BinanceStandardModel(AbstractLiquidationModel):
    def calculate_liquidations(self, oi_data, current_price):
        # Use reference formula for liquidation price calculation
        pass
```

**From py-liquidation-map**:
```python
# src/liquidationheatmap/models/py_liquidation_map.py
from liqmap.mapping import HistoricalMapping

class PyLiquidationMapModel(AbstractLiquidationModel):
    def calculate_liquidations(self, oi_data, current_price):
        # Wrapper around external library
        pass
```

### Phase 2: Nautilus Trader Integration (Future)

**Integration with Nautilus Trader** (not WebSocket):
```python
# src/liquidationheatmap/nautilus/signal_generator.py
from nautilus_trader.core.message import Signal

def generate_liquidation_signal(liquidation_cluster, current_price):
    """Generate trading signals based on liquidation clusters."""
    if abs(current_price - liquidation_cluster['price']) / current_price < 0.02:
        return Signal(action="AVOID", reason="Liquidation cluster at $66,000")
    # ...
```

**Note**: MVP uses historical Binance CSV data only. No real-time streaming.

---

## 📊 Screenshots Reference

### Coinglass Examples (Saved in examples/)
- `coinglass_map.png` - Liquidation map (bar chart by leverage)
- `coinglass_model1.png` - Heatmap visualization (time × price)
- `coinglass_model3.png` - Alternative heatmap view

**Visual Style to Replicate**:
- Purple → Blue → Teal → Yellow color gradient
- Current price as red dashed line
- Leverage tiers as colored bars (5x, 10x, 25x, 50x, 100x)

---

## 🔧 Dependencies

### For Reference Examples:

```bash
# py-liquidation-map (if testing library)
pip install git+https://github.com/aoki-h-jp/py-liquidation-map

# Note: Other examples are text references only (no code execution needed)
```

### For Our Project (Already Installed):

```bash
uv sync  # Installs all dependencies from pyproject.toml
```

---

## 📝 Key Learnings

### 1. Liquidation Formula (Binance Standard)
- **Maintenance margin** varies by position size (tiered system)
- **Direction matters**: Long positions liquidate BELOW entry, shorts ABOVE
- **Formula is reliable** but doesn't account for funding rate pressure

### 2. py-liquidation-map Approach
- Uses **actual trade data** (not Open Interest)
- Filters by gross value, top N, or portion
- Generates **visual heatmaps** showing liquidation density

### 3. Binance Historical Data
- **CSV files contain**: trades, Open Interest, funding rates, klines
- **DuckDB zero-copy ingestion**: 10GB in ~5 seconds
- **No real-time streaming needed for MVP**

### 4. Visualization
- **Matplotlib** is heavyweight (100+ lines for custom styling)
- **Plotly.js** is simpler (50 lines for interactive heatmap)
- Coinglass uses **2D heatmap** (time × price) with color density

---

## ✅ Next Steps

1. **Phase 1 (MVP - Historical Data)**:
   - Ingest Binance CSV → DuckDB
   - Implement Models A, B, Ensemble using reference formulas
   - Build Plotly.js heatmap (<100 lines)
   - FastAPI endpoints for historical analysis

2. **Phase 2 (Nautilus Integration)**:
   - Create trading signals based on liquidation clusters
   - Integrate with Nautilus Trader (not WebSocket)
   - Backtesting on historical liquidation patterns

3. **Phase 3 (Advanced Models)**:
   - Ensemble tuning with backtest validation
   - Multi-symbol support (ETH, SOL, etc.)
   - Order book depth integration

---

## 📚 Additional Resources

- **Binance Liquidation Docs**: https://www.binance.com/en/support/faq/liquidation
- **Coinglass Heatmap**: https://www.coinglass.com/LiquidationData
- **Binance WebSocket API**: https://binance-docs.github.io/apidocs/futures/en/#liquidation-order-streams
- **CCXT Library**: https://github.com/ccxt/ccxt (for multi-exchange support)

---

**License**: Examples are from open-source projects (MIT/Apache 2.0). See individual repositories for details.
