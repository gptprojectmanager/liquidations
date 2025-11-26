# Mathematical Foundation

## Tiered Margin System

### Overview

The tiered margin system ensures **continuous** margin requirements across position sizes, eliminating sudden jumps at tier boundaries through the Maintenance Amount (MA) offset.

### Margin Calculation Formula

For a position with notional value `N` in tier `i`:

```
Margin = N × rate[i] - MA[i]
```

Where:
- `N` = notional value (position size × entry price)
- `rate[i]` = maintenance margin rate for tier i
- `MA[i]` = maintenance amount offset for tier i

### Maintenance Amount Derivation

The MA values are derived to ensure **mathematical continuity** at tier boundaries:

```
MA[i] = MA[i-1] + boundary[i] × (rate[i] - rate[i-1])
```

**Example** (Tier 1→2 boundary at $50,000):
- Tier 1: rate = 0.5%, MA = 0
- Tier 2: rate = 1.0%, MA = ?

At boundary ($50,000):
- Tier 1 margin: `50000 × 0.005 - 0 = 250`
- Tier 2 margin: `50000 × 0.010 - MA[2] = ?`

For continuity: `250 = 500 - MA[2]`
Therefore: `MA[2] = 250` ✓

### Binance Tier Configuration

| Tier | Range ($) | Rate | MA | Max Leverage |
|------|-----------|------|-----|--------------|
| 1 | 0 - 50k | 0.5% | 0 | 200x |
| 2 | 50k - 250k | 1.0% | 250 | 100x |
| 3 | 250k - 1M | 2.5% | 4,000 | 40x |
| 4 | 1M - 10M | 5.0% | 29,000 | 20x |
| 5 | 10M - 50M | 10.0% | 529,000 | 10x |

### Liquidation Price Formulas

**Long Position**:
```
Liq Price = Entry × (1 - 1/Leverage + MMR - MA/Notional)
```

**Short Position**:
```
Liq Price = Entry × (1 + 1/Leverage - MMR + MA/Notional)
```

### Continuity Proof

**Theorem**: The margin function is continuous across all tier boundaries.

**Proof**: At boundary `B` between tiers `i` and `i+1`:

Left limit (tier i):
```
lim[N→B⁻] Margin = B × rate[i] - MA[i]
```

Right limit (tier i+1):
```
lim[N→B⁺] Margin = B × rate[i+1] - MA[i+1]
```

By construction:
```
MA[i+1] = MA[i] + B × (rate[i+1] - rate[i])
```

Therefore:
```
B × rate[i+1] - MA[i+1]
= B × rate[i+1] - [MA[i] + B × (rate[i+1] - rate[i])]
= B × rate[i+1] - MA[i] - B × rate[i+1] + B × rate[i]
= B × rate[i] - MA[i]
```

Hence: `lim[N→B⁻] = lim[N→B⁺]` ∴ Continuous ∎

### Precision Requirements

- **Decimal Type**: Decimal128 (28 significant digits)
- **Rounding**: Round to 2 decimal places for USD amounts
- **Tolerance**: ±$0.01 acceptable for continuity tests

## References

- [Binance Margin Mode Documentation](https://www.binance.com/en/support/faq/liquidation)
- [Maintenance Margin Rates](https://www.binance.com/en/futures/trading-rules/perpetual/leverage-margin)
