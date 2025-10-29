# Code Analysis: py-liquidation-map & liquidations-chart

This document analyzes the cloned repositories and extracts key insights for our implementation.

---

## 📂 Repository: py-liquidation-map

**Location**: `/media/sam/1TB/py-liquidation-map`
**Source**: https://github.com/aoki-h-jp/py-liquidation-map

### Key Files Copied

1. **`py_liquidation_map_mapping.py`** (750 lines)
   - Main implementation of liquidation clustering algorithm
   - Class: `HistoricalMapping`

### Core Algorithm: Liquidation Price Calculation

**Buy (Long) Positions**:
```python
df_buy["LossCut100x"] = df_buy["price"] * 0.99  # 1% loss
df_buy["LossCut50x"]  = df_buy["price"] * 0.98  # 2% loss
df_buy["LossCut25x"]  = df_buy["price"] * 0.96  # 4% loss
df_buy["LossCut10x"]  = df_buy["price"] * 0.90  # 10% loss
```

**Sell (Short) Positions**:
```python
df_sell["LossCut100x"] = df_sell["price"] * 1.01  # 1% loss
df_sell["LossCut50x"]  = df_sell["price"] * 1.02  # 2% loss
df_sell["LossCut25x"]  = df_sell["price"] * 1.04  # 4% loss
df_sell["LossCut10x"]  = df_sell["price"] * 1.10  # 10% loss
```

**Insight**: This is a **simplified approximation** that doesn't use maintenance margin rates. More accurate than nothing, but less precise than the Binance formula we have.

### Data Processing Pipeline

```
1. Download aggTrades from Binance
   ↓
2. Format DataFrame (timestamp, price, size, side, amount)
   ↓
3. Filter by mode (gross_value / top_n / portion)
   ↓
4. Calculate liquidation prices for 10x/25x/50x/100x
   ↓
5. Group by price buckets (binning)
   ↓
6. Aggregate volume per bucket
   ↓
7. Visualize with matplotlib (bar chart)
```

### Filtering Modes

**1. gross_value**: Show only trades above threshold (e.g., >$100k)
```python
df_buy = df_buy[df_buy["amount"] >= threshold_gross_value]
```

**2. top_n**: Show top N largest trades
```python
df_buy = df_buy.sort_values(by="amount", ascending=False).iloc[:threshold_top_n]
```

**3. portion**: Show top percentage of trades (e.g., top 1%)
```python
df_buy = df_buy.iloc[: int(len(df_buy) * threshold_portion)]
```

### Visualization: Binning Algorithm

**Key insight**: Groups liquidation levels into price buckets for cleaner visualization.

```python
tick_digits = 2 - math.ceil(math.log10(price_max - price_min))
bins = [round(price_min + i * 10**-tick_digits, tick_digits)
        for i in range(g_ids)]
df_losscut["group_id"] = pd.cut(df_losscut["price"], bins=bins)
agg_df = df_losscut.groupby("group_id").sum()
```

**Example**:
- If price range is $65,000 - $68,000 (diff = $3,000)
- tick_digits = 2 - ceil(log10(3000)) = 2 - 4 = -2
- Buckets: $100 increments (10^2)

### What We Can Reuse

✅ **Binning algorithm** for price grouping
✅ **Filtering modes** (gross_value, top_n, portion)
✅ **Data aggregation pattern** (groupby price bucket)
❌ **Liquidation formula** (too simplified, use our Binance formula instead)
❌ **matplotlib visualization** (we use Plotly.js for <100 lines)

---

## 📂 Repository: liquidations-chart

**Location**: `/media/sam/1TB/liquidations-chart`
**Source**: https://github.com/StephanAkkerman/liquidations-chart

### Key Files Copied

1. **`liquidations_chart_plot.py`** (211 lines)
   - Coinglass-style liquidation chart
   - Dual-axis plot (bars + price line)

### Core Features

**Chart Type**: Total Liquidations Chart
- **Y-axis 1**: Liquidation volume (bars)
  - Shorts (red, negative values)
  - Longs (green, positive values)
- **Y-axis 2**: BTC price (yellow line)
- **X-axis**: Time (daily intervals)

### Key Functions

**1. human_format()** - Number abbreviation
```python
def human_format(number: float) -> str:
    """
    1000 → 1K
    1000000 → 1M
    1000000000 → 1B
    """
    units = ["", "K", "M", "B", "t", "q"]
    k = 1000.0
    magnitude = int(floor(log(abs(number), k)))
    return f"{rounded_number}{units[magnitude]}"
```

**Use case**: Simplify large numbers in charts (1.2M instead of 1,200,000)

**2. liquidations_plot()** - Coinglass-style bar chart
```python
ax1.bar(df["Shorts"], color="#d9024b")  # Red bars (negative)
ax1.bar(df["Longs"], color="#45bf87")   # Green bars (positive)
ax2.plot(df["price"], color="#edba35")  # Yellow line
```

### Styling Reference

**Colors** (Coinglass-inspired):
- Shorts: `#d9024b` (red)
- Longs: `#45bf87` (green)
- Price: `#f0b90b` (yellow/gold)
- Background: `#0d1117` (dark gray)

**Chart Parameters**:
- Figure size: `(15, 7)`
- Grid: Horizontal only, gray, dashed, alpha=0.5
- No spines (clean borders)
- Legend: Top center, 3 columns

### What We Can Reuse

✅ **human_format()** function (for Plotly.js axis formatting)
✅ **Color scheme** (Coinglass-style colors)
✅ **Dual-axis pattern** (bars + line overlay)
✅ **Date formatting** (14-day intervals on X-axis)
❌ **matplotlib code** (we use Plotly.js instead)

---

## 🎯 Integration Plan for Our Project

### From py-liquidation-map

**Model C Implementation**:
```python
# src/liquidationheatmap/models/py_liquidation_map.py
class PyLiquidationMapModel(AbstractLiquidationModel):
    def calculate_liquidations(self, oi_data, current_price):
        # Use simplified formula from library
        df_buy["LossCut100x"] = df_buy["price"] * 0.99
        # ... etc

        # Apply binning algorithm
        tick_digits = 2 - math.ceil(math.log10(price_max - price_min))
        bins = [...]
        df["group_id"] = pd.cut(df["price"], bins=bins)
        return df.groupby("group_id").sum()
```

**DuckDB Ingestion**:
```python
# scripts/ingest_historical.py
def format_binance_aggtrades(csv_path):
    """Reuse formatting logic from mapping.py"""
    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["transact_time"], unit="ms")
    df["amount"] = df["price"] * df["quantity"]
    return df[["timestamp", "price", "size", "side", "amount"]]
```

### From liquidations-chart

**Plotly.js Visualization**:
```javascript
// frontend/heatmap.html
const COLORS = {
    shorts: '#d9024b',
    longs: '#45bf87',
    price: '#f0b90b'
};

function humanFormat(number) {
    const units = ["", "K", "M", "B"];
    const magnitude = Math.floor(Math.log10(Math.abs(number)) / 3);
    return (number / 1000**magnitude).toFixed(1) + units[magnitude];
}

Plotly.newPlot('chart', [
    {type: 'bar', y: shorts, marker: {color: COLORS.shorts}},
    {type: 'bar', y: longs, marker: {color: COLORS.longs}},
    {type: 'scatter', y: price, line: {color: COLORS.price}, yaxis: 'y2'}
]);
```

### Hybrid Approach: Best of Both

**Liquidation Calculation**:
1. **Primary**: Use our Binance formula (most accurate)
2. **Fallback**: Use py-liquidation-map simplified formula (if maintenance margin unknown)

**Visualization**:
1. **Bar chart** (liquidations-chart style): Total liquidations over time
2. **Heatmap** (py-liquidation-map style): Price buckets × time

---

## 📊 Example Outputs (Copied Images)

### From py-liquidation-map:
- `BTCUSDT_*_gross_value_100000.png` - Filtered by >$100k trades
- `BTCUSDT_*_top_n_100.png` - Top 100 largest trades
- `BTCUSDT_*_portion_0.01.png` - Top 1% of trades
- `*_depth.png` - Depth chart with cumulative volume

### From liquidations-chart:
- `liquidations_chart_example.png` - Coinglass-style bar chart

**Note**: These images show expected output format for our visualization.

---

## ⚠️ Key Differences from Our Approach

| Feature | py-liquidation-map | Our Approach |
|---------|-------------------|--------------|
| **Data Source** | Downloads aggTrades | Uses local Binance CSV |
| **Liquidation Formula** | Simplified (% approximation) | Binance official (MMR tiers) |
| **Visualization** | matplotlib (complex) | Plotly.js (simple) |
| **Architecture** | Monolithic script | Black box models |
| **Flexibility** | Single model | Ensemble (3 models) |

---

## ✅ Action Items

1. **Extract binning algorithm** → Use in DuckDB aggregation
2. **Adopt color scheme** → Copy Coinglass colors for Plotly.js
3. **Reuse human_format()** → Port to JavaScript for axis labels
4. **Reference output images** → Match visual style in our charts
5. **Skip py-liquidation-map formula** → Use our Binance formula instead

---

**Files Available**:
- `py_liquidation_map_mapping.py` (750 lines) - Full source code
- `liquidations_chart_plot.py` (211 lines) - Plotting code
- `*.png` - Example output images (6 images from py-liquidation-map, 1 from liquidations-chart)
