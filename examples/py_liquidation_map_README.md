# py-liquidation-map Example

**Source**: https://github.com/aoki-h-jp/py-liquidation-map

## Purpose
Visualize liquidation maps for cryptocurrency futures trading using historical data from Binance and Bybit.

## Installation
```bash
pip install git+https://github.com/aoki-h-jp/py-liquidation-map
```

## Key Features
- Multiple visualization modes:
  - **gross_value**: Filter liquidations above a monetary threshold
  - **top_n**: Visualize top N largest trades
  - **portion**: Visualize top percentage of trades

## Example Usage

### Basic Liquidation Map
```python
from liqmap.mapping import HistoricalMapping

# Initialize mapping for specific timeframe
mapping = HistoricalMapping(
    start_datetime='2023-08-01 00:00:00',
    end_datetime='2023-08-01 06:00:00',
    symbol='BTCUSDT',
    exchange='binance'
)

# Generate liquidation map (filter by gross value)
mapping.liquidation_map_from_historical(
    mode="gross_value",
    threshold_gross_value=100000  # Show only liquidations > $100k
)
```

### Depth Map
```python
# Generate liquidation depth map
mapping.liquidation_map_depth_from_historical(
    mode="top_n",
    top_n=100  # Show top 100 largest trades
)
```

### Portion Mode
```python
# Show top 10% of trades by volume
mapping.liquidation_map_from_historical(
    mode="portion",
    portion=0.1  # Top 10%
)
```

## Concept
Different combinations of leverage and time frames depict various clusters of liquidations. The denser and higher the liquidation clusters, the greater their impact on price behavior when reached.

## Key Insights
- Liquidation maps show potential market price disruption points
- Helps traders understand mass liquidation risks
- Visualizes how forced position closures might impact market dynamics

## Leverage Tiers Visualization
The library calculates where large positions would be liquidated at:
- 10x leverage
- 20x leverage
- 50x leverage
- 100x leverage

**Disclaimer**: Educational purposes only, not financial advice.
