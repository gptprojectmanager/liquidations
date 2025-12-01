# py-liquidation-map Logic Analysis

Reference implementation analysis from [py-liquidation-map](https://github.com/aoki-h-jp/py-liquidation-map)

This document extracts the **business logic** (formulas, algorithms) without matplotlib plotting code.

---

## 1. Liquidation Price Formulas

**Lines 193-211** in `py_liquidation_map_mapping.py`

### Long Positions (BUY)

```python
# LONG liquidations are BELOW entry price
df_buy["LossCut100x"] = df_buy["price"] * 0.99   # 1 - 1/100
df_buy["LossCut50x"]  = df_buy["price"] * 0.98   # 1 - 1/50
df_buy["LossCut25x"]  = df_buy["price"] * 0.96   # 1 - 1/25
df_buy["LossCut10x"]  = df_buy["price"] * 0.90   # 1 - 1/10
```

**Formula**: `LossCut = entry_price * (1 - 1/leverage)`

| Leverage | Multiplier | Example ($30k entry) |
|----------|-----------|----------------------|
| 10x      | 0.90      | $27,000             |
| 25x      | 0.96      | $28,800             |
| 50x      | 0.98      | $29,400             |
| 100x     | 0.99      | $29,700             |

### Short Positions (SELL)

```python
# SHORT liquidations are ABOVE entry price
df_sell["LossCut100x"] = df_sell["price"] * 1.01   # 1 + 1/100
df_sell["LossCut50x"]  = df_sell["price"] * 1.02   # 1 + 1/50
df_sell["LossCut25x"]  = df_sell["price"] * 1.04   # 1 + 1/25
df_sell["LossCut10x"]  = df_sell["price"] * 1.10   # 1 + 1/10
```

**Formula**: `LossCut = entry_price * (1 + 1/leverage)`

| Leverage | Multiplier | Example ($30k entry) |
|----------|-----------|----------------------|
| 10x      | 1.10      | $33,000             |
| 25x      | 1.04      | $31,200             |
| 50x      | 1.02      | $30,600             |
| 100x     | 1.01      | $30,300             |

---

## 2. Filtering Modes

**Lines 246-261** - Three modes to filter large trades:

### Mode 1: `gross_value` (Default)

Keep only trades with total value >= threshold

```python
if mode == "gross_value":
    df_buy = df_buy[df_buy["amount"] >= threshold_gross_value]
    df_sell = df_sell[df_sell["amount"] >= threshold_gross_value]
```

**Default threshold**: $100,000 USDT
**Use case**: Filter noise, focus on whales

### Mode 2: `top_n`

Keep only the top N largest trades

```python
elif mode == "top_n":
    df_buy = df_buy.sort_values(by="amount", ascending=False)
    df_buy = df_buy.iloc[:threshold_top_n]
    df_sell = df_sell.sort_values(by="amount", ascending=False)
    df_sell = df_sell.iloc[:threshold_top_n]
```

**Default threshold**: 100 trades
**Use case**: Show only the biggest market movers

### Mode 3: `portion`

Keep top N% of trades

```python
elif mode == "portion":
    df_buy = df_buy.sort_values(by="amount", ascending=False)
    df_buy = df_buy.iloc[: int(len(df_buy) * threshold_portion)]
    df_sell = df_sell.sort_values(by="amount", ascending=False)
    df_sell = df_sell.iloc[: int(len(df_sell) * threshold_portion)]
```

**Default threshold**: 0.01 (1%)
**Use case**: Adaptive filtering based on data volume

---

## 3. Dynamic Binning Algorithm

**Lines 342-344, 596-598** - Adaptive bin size based on price range

### Algorithm

```python
tick_degits = 2 - math.ceil(math.log10(df_merged["price"].max() - df_merged["price"].min()))
bin_size = 10 ** (-tick_degits)
```

### Examples

| Price Range | Log10 | Ceiling | tick_degits | Bin Size |
|------------|-------|---------|-------------|----------|
| $29k - $32k | 3.48  | 4       | -2          | $100     |
| $1k - $10k  | 3.95  | 4       | -2          | $100     |
| $100 - $1k  | 2.95  | 3       | -1          | $10      |
| $0.8 - $1.2 | -0.4  | 0       | 2           | $0.01    |

**Key insight**: Bin size adapts to price magnitude automatically!

### Bin Creation

```python
# Number of bins
g_ids = int(
    (
        round(df_losscut["price"].max(), tick_degits)
        - round(df_losscut["price"].min(), tick_degits)
    )
    * 10**tick_degits
)

# Create bin edges
bins = [
    round(
        round(df_losscut["price"].min(), tick_degits)
        + i * 10**-tick_degits,
        tick_degits,
    )
    for i in range(g_ids)
]
```

**Example** (BTC $29k-$30k, tick_degits=-1):
- g_ids = (30000 - 29000) * 10^(-(-1)) = 1000 * 10 = 10,000 bins
- bins = [29000, 29010, 29020, ..., 29990, 30000]

---

## 4. Aggregation Logic

**Lines 363-364** - Group liquidations into bins

```python
df_losscut["group_id"] = pd.cut(df_losscut["price"], bins=bins)
agg_df = df_losscut.groupby("group_id").sum()
```

**Process**:
1. Assign each liquidation to a price bin using `pd.cut()`
2. Group by bin and sum the amounts
3. Result: Total liquidation volume per price level

**Key point**: Separate aggregation **per leverage tier** (4 separate DataFrames)

---

## 5. Cumulative Calculations

### Long Cumulative (Lines 577-586)

```python
df_depth_buy = pd.concat([df_losscut_10x, df_losscut_25x, df_losscut_50x, df_losscut_100x])
df_depth_buy = df_depth_buy.sort_values(by="price", ascending=False)  # High to low
df_depth_buy = df_depth_buy[df_depth_buy["price"] <= current_price]   # Below current
df_depth_buy["cumsum"] = df_depth_buy["amount"].cumsum()               # Right to left
```

**Direction**: Right to left (highest price → lowest price)
**Meaning**: "If price drops to X, this much gets liquidated"

### Short Cumulative (Lines 677-685)

```python
df_depth_sell = pd.concat([df_losscut_10x, df_losscut_25x, df_losscut_50x, df_losscut_100x])
df_depth_sell = df_depth_sell.sort_values(by="price")                  # Low to high
df_depth_sell = df_depth_sell[df_depth_sell["price"] >= current_price] # Above current
df_depth_sell["cumsum"] = df_depth_sell["amount"].cumsum()              # Left to right
```

**Direction**: Left to right (lowest price → highest price)
**Meaning**: "If price rises to X, this much gets liquidated"

---

## 6. Visualization Approach

### Layout: 2 Panels (Line 264)

```python
fig, (ax1, ax2) = plt.subplots(nrows=1, ncols=2, sharey=True, figsize=(9, 9))
```

**Left panel (ax1)**: Price time series + scatter of large trades
**Right panel (ax2)**: Liquidation map (horizontal bars)

### Bar Orientation: Horizontal (Lines 365, 454)

```python
ax2.barh(
    [f.left for f in agg_df.index],  # Y-axis = price levels
    agg_df["amount"],                 # X-axis = volume
    height=10**-tick_degits,
    color=colors[i],
    label=labels[i],
    alpha=0.5,
)
```

**Axes**:
- **Y-axis**: Price levels (vertical)
- **X-axis**: Liquidation volume (horizontal)

### Colors (Lines 340-341, 429-430)

```python
labels = ["10x Leveraged", "25x Leveraged", "50x Leveraged", "100x Leveraged"]
colors = ["r", "g", "b", "y"]  # Red, Green, Blue, Yellow
```

---

## 7. Key Differences vs Current Implementation

| Feature | py-liquidation-map | Our Current Code |
|---------|-------------------|------------------|
| **Leverage separation** | 4 separate DataFrames | ❌ Aggregated into one |
| **Binning** | Dynamic (adaptive) | ❌ Static $100 |
| **Filtering modes** | 3 modes (gross_value/top_n/portion) | ❌ Only gross_value |
| **Bar orientation** | Horizontal (barh) | Vertical (bar) |
| **Layout** | 2 panels (time + map) | 1 panel |
| **API response** | Contains leverage field | ❌ Missing leverage field |

---

## 8. Implementation Priorities

To match py-liquidation-map behavior:

### P0 (Critical - Blocking)
1. **Fix API**: Preserve `leverage` field in aggregation (main.py:116-149)
2. **Fix frontend**: Parse leverage from API and create 4 separate traces

### P1 (High - Core functionality)
3. **Dynamic binning**: Replace `bin_size = Decimal("100")` with adaptive algorithm
4. **Filtering modes**: Add dropdown for gross_value/top_n/portion

### P2 (Medium - UX improvements)
5. **2-panel layout**: Add time series panel (left) + liquidation map (right)
6. **Horizontal bars**: Change `type: 'bar'` → `type: 'bar', orientation: 'h'`

### P3 (Low - Polish)
7. **Color coding**: Match leverage colors (r, g, b, y)
8. **Current price arrow**: Add annotation like line 464-472

---

## Next Steps

Before implementing, we need to decide:

1. **Layout**: 2 panels (py-liquidation-map) or 1 panel (Coinglass)?
2. **Bar orientation**: Horizontal (py-liquidation-map) or Vertical (Coinglass/current)?
3. **Filtering**: Start with all 3 modes or just fix gross_value first?

Once decided, implement with **TDD**:
- RED: Write test for leverage preservation
- GREEN: Fix API aggregation
- REFACTOR: Clean up and optimize
