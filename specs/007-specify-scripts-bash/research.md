# Research: DBSCAN Clustering for Liquidation Zones

**Feature ID**: LIQHEAT-007
**Research Date**: 2025-12-02
**Status**: Complete

---

## 1. Algorithm Selection

### DBSCAN vs Alternatives Analysis

| Algorithm | Pros | Cons | Verdict |
|-----------|------|------|---------|
| **DBSCAN** | No k required, handles noise, arbitrary shapes, O(n log n) | Epsilon sensitivity, struggles with varying density | ✅ SELECTED |
| K-Means | Fast, simple | Requires k upfront, assumes spherical clusters | ❌ Rejected |
| HDBSCAN | Better varying density, fewer parameters | Extra dependency, overkill for this use case | ❌ Rejected |
| OPTICS | Handles varying density | More parameters, slower | ❌ Rejected |
| Grid Binning | Already exists, simple | Not true clustering, loses density info | ❌ Rejected |

### Why DBSCAN

1. **No cluster count required**: Liquidation zones vary by market conditions
2. **Noise handling**: Outlier liquidations (extreme prices) automatically excluded
3. **Arbitrary shapes**: Liquidation zones are irregular, not spherical
4. **scikit-learn implementation**: Battle-tested, O(n log n) with KD-tree
5. **Deterministic**: Same parameters = same clusters (reproducible)

---

## 2. Feature Space Design

### Decision: 2D Normalized Space

**Dimensions**:
1. `normalized_price = (price - price_min) / (price_max - price_min)` → [0, 1]
2. `log_volume = log10(volume + 1)` → reduces skew from large liquidations

### Rationale

- **Price normalization**: Makes epsilon distance-metric agnostic of price scale
- **Log transform**: Liquidation volumes follow power-law distribution
- **Equal weighting**: Both dimensions contribute equally to distance

### Implementation

```python
def _prepare_features(self, price_levels: np.ndarray, volumes: np.ndarray) -> np.ndarray:
    """Prepare normalized feature matrix for DBSCAN."""
    # Normalize price to [0, 1]
    price_min, price_max = price_levels.min(), price_levels.max()
    if price_max - price_min > 0:
        norm_price = (price_levels - price_min) / (price_max - price_min)
    else:
        norm_price = np.zeros_like(price_levels)

    # Log-transform volume
    log_vol = np.log10(volumes + 1)
    log_vol_max = log_vol.max()
    if log_vol_max > 0:
        norm_vol = log_vol / log_vol_max
    else:
        norm_vol = np.zeros_like(log_vol)

    return np.column_stack([norm_price, norm_vol])
```

---

## 3. Parameter Selection Strategy

### Epsilon (Neighborhood Radius)

**Decision**: Auto-tune using k-distance graph elbow method

**Algorithm**:
1. Compute k-nearest neighbor distances for all points (k = min_samples)
2. Sort distances in ascending order
3. Find "elbow" point where curvature is maximum
4. Use elbow distance as epsilon

**Fallback**: If auto-tune fails, use `epsilon = 0.1` (10% of normalized range)

### Min Samples

**Decision**: Fixed at `min_samples = 3`

**Rationale**:
- Small clusters are valid for liquidations (2-3 nearby levels)
- Lower values = more clusters (finer granularity)
- Higher values = fewer clusters (coarser grouping)
- 3 is a good balance for financial data

### Auto-Tune Implementation

```python
def _auto_epsilon(self, features: np.ndarray, min_samples: int = 3) -> float:
    """Calculate optimal epsilon using k-distance graph."""
    from sklearn.neighbors import NearestNeighbors

    # Compute k-nearest neighbor distances
    nn = NearestNeighbors(n_neighbors=min_samples)
    nn.fit(features)
    distances, _ = nn.kneighbors(features)
    k_distances = np.sort(distances[:, -1])

    # Find elbow using maximum curvature
    # Simplified: use percentile-based approach
    epsilon = np.percentile(k_distances, 90)

    # Bounds check
    return max(0.01, min(0.5, epsilon))
```

---

## 4. Visualization Strategy

### Decision: Plotly.js layout.shapes

**Approach**: Rectangular zone boundaries via `layout.shapes` array

**Rationale**:
- Shapes are lightweight (no extra data traces)
- Rectangles sufficient for 1D price zones
- Color intensity via `fillcolor` opacity
- Interactive via `on('plotly_click')` events

### Shape Configuration

```javascript
{
    type: 'rect',
    x0: zone.price_min,
    x1: zone.price_max,
    y0: 0,
    y1: 1,  // Full height (normalized)
    fillcolor: `rgba(255, 0, 0, ${opacity})`,
    line: { width: 1, color: 'rgba(255, 0, 0, 0.8)' },
    layer: 'below'
}
```

### Color Gradient

- **Zone strength** = total_volume normalized to [0, 1]
- **Opacity** = 0.2 + (strength * 0.6) → range [0.2, 0.8]
- **Hue**: Red for high concentration, yellow for medium, green for low

---

## 5. Performance Considerations

### Complexity Analysis

| Operation | Complexity | Notes |
|-----------|------------|-------|
| Feature preparation | O(n) | NumPy vectorized |
| DBSCAN clustering | O(n log n) | With KD-tree (default) |
| Cluster statistics | O(n) | Single pass |
| Total | O(n log n) | Dominated by DBSCAN |

### Optimization Strategies

1. **Pre-filtering**: Only cluster visible price range
2. **Caching**: Store results until data refresh
3. **Sampling**: For >5000 points, use random sample
4. **Ball-tree**: Alternative spatial index for high dimensions

### Benchmark Targets

| Data Size | Required | Target |
|-----------|----------|--------|
| 100 points | <100ms | <50ms |
| 1000 points | <500ms | <200ms |
| 5000 points | <500ms | <400ms |

---

## 6. Edge Cases

### No Clusters Found

**Scenario**: Uniform distribution, all points marked as noise

**Solution**:
1. Return all points as noise with `clusters=[]`
2. Frontend displays notification: "No distinct zones identified"
3. Optionally fall back to grid binning

### Too Many Clusters

**Scenario**: Auto-tune produces >15 clusters

**Solution**:
1. Increase epsilon by 10% and re-run
2. Repeat until clusters <= 15
3. Cap iterations at 5 to prevent infinite loop

### Too Few Clusters

**Scenario**: Only 1-2 clusters for diverse data

**Solution**:
1. Decrease epsilon by 10% and re-run
2. Minimum clusters = 3 (unless data truly uniform)

### Empty Input

**Scenario**: No liquidation levels in visible range

**Solution**:
1. Return empty `ClusteringResult`
2. Frontend hides cluster toggle

---

## 7. scikit-learn Integration

### Dependency

```toml
# pyproject.toml
[project.dependencies]
scikit-learn = ">=1.3.0"
```

### Usage Pattern

```python
from sklearn.cluster import DBSCAN

# Create clusterer
dbscan = DBSCAN(
    eps=epsilon,
    min_samples=min_samples,
    metric='euclidean',
    algorithm='auto',  # Uses KD-tree when appropriate
    n_jobs=-1  # Use all cores
)

# Fit and get labels
labels = dbscan.fit_predict(features)

# Labels: -1 = noise, 0..n = cluster ID
```

### Thread Safety

scikit-learn DBSCAN is thread-safe for `fit_predict()` calls. Multiple concurrent requests can safely cluster different data.

---

## 8. References

1. **DBSCAN Paper**: Ester, M., et al. (1996). "A Density-Based Algorithm for Discovering Clusters"
2. **scikit-learn Documentation**: https://scikit-learn.org/stable/modules/clustering.html#dbscan
3. **py-liquidation-map**: GitHub reference implementation for liquidation clustering
4. **k-distance Graph**: Elbow method for epsilon selection

---

## 9. Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Algorithm | DBSCAN | No k required, handles noise |
| Feature space | 2D (price, volume) | Captures both location and magnitude |
| Normalization | Min-max + log | Equal weighting, handles skew |
| Epsilon | Auto-tune (k-distance) | Adapts to data density |
| min_samples | Fixed at 3 | Small clusters valid |
| Visualization | Plotly shapes | Lightweight, interactive |
| Fallback | Grid binning | When clustering fails |

---

**Research Status**: ✅ **COMPLETE**
