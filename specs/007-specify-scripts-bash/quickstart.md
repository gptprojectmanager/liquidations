# Quickstart: DBSCAN Clustering for Liquidation Zones

**Feature ID**: LIQHEAT-007
**Time to Complete**: ~2 hours
**Difficulty**: Medium

---

## Prerequisites

- Python 3.11+
- UV package manager
- Existing LiquidationHeatmap project setup
- DuckDB with liquidation data loaded

---

## 1. Setup (5 minutes)

### Create Feature Branch

```bash
cd /media/sam/1TB/LiquidationHeatmap
git checkout -b feature/007-dbscan-clustering
```

### Add Dependency

```bash
uv add scikit-learn
```

### Create Module Structure

```bash
mkdir -p src/clustering
touch src/clustering/__init__.py
touch src/clustering/service.py
touch src/clustering/models.py
touch tests/test_clustering.py
```

---

## 2. TDD Workflow (Red-Green-Refactor)

### Step 1: Write Failing Test (RED)

```python
# tests/test_clustering.py
import pytest
import numpy as np
from src.clustering.service import ClusteringService
from src.clustering.models import ClusterParameters, ClusteringResult


class TestClusteringService:
    """Tests for DBSCAN clustering service."""

    def test_single_dense_cluster_detected(self):
        """Dense points should form a single cluster."""
        # Arrange
        service = ClusteringService()
        # 20 points clustered around price=100, volume=1000
        prices = np.array([100 + np.random.uniform(-1, 1) for _ in range(20)])
        volumes = np.array([1000 + np.random.uniform(-100, 100) for _ in range(20)])

        # Act
        result = service.cluster_liquidations(
            price_levels=prices,
            volumes=volumes,
            params=ClusterParameters(epsilon=0.1, min_samples=3)
        )

        # Assert
        assert len(result.clusters) == 1
        assert result.clusters[0].level_count == 20
```

### Step 2: Run Test - Should FAIL

```bash
uv run pytest tests/test_clustering.py::TestClusteringService::test_single_dense_cluster_detected -v
```

Expected output: `ModuleNotFoundError: No module named 'src.clustering.service'`

### Step 3: Implement Minimal Code (GREEN)

```python
# src/clustering/models.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class ClusterParameters(BaseModel):
    epsilon: float = Field(default=0.1, ge=0.01, le=1.0)
    min_samples: int = Field(default=3, ge=2, le=10)
    auto_tune: bool = Field(default=True)


class LiquidationCluster(BaseModel):
    cluster_id: int
    price_min: float
    price_max: float
    centroid_price: float
    total_volume: float
    level_count: int
    density: float


class NoisePoint(BaseModel):
    price_level: float
    volume: float
    distance_to_nearest: float


class ClusterMetadata(BaseModel):
    symbol: str = "BTCUSDT"
    timeframe_minutes: int = 30
    total_points: int = 0
    cluster_count: int = 0
    noise_count: int = 0
    parameters_used: ClusterParameters = Field(default_factory=ClusterParameters)
    computation_ms: float = 0.0
    auto_tuned: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ClusteringResult(BaseModel):
    clusters: List[LiquidationCluster] = Field(default_factory=list)
    noise_points: List[NoisePoint] = Field(default_factory=list)
    metadata: ClusterMetadata = Field(default_factory=ClusterMetadata)
    fallback_used: bool = False
    warning: Optional[str] = None
```

```python
# src/clustering/service.py
import numpy as np
from sklearn.cluster import DBSCAN
from typing import Optional
import time

from src.clustering.models import (
    ClusterParameters,
    ClusteringResult,
    LiquidationCluster,
    NoisePoint,
    ClusterMetadata,
)


class ClusteringService:
    """DBSCAN clustering service for liquidation zones."""

    def cluster_liquidations(
        self,
        price_levels: np.ndarray,
        volumes: np.ndarray,
        params: Optional[ClusterParameters] = None,
    ) -> ClusteringResult:
        """Cluster liquidation levels using DBSCAN."""
        start_time = time.perf_counter()
        params = params or ClusterParameters()

        if len(price_levels) == 0:
            return ClusteringResult(
                metadata=ClusterMetadata(total_points=0, parameters_used=params)
            )

        # Prepare features
        features = self._prepare_features(price_levels, volumes)

        # Auto-tune epsilon if requested
        epsilon = params.epsilon
        if params.auto_tune:
            epsilon = self._auto_epsilon(features, params.min_samples)

        # Run DBSCAN
        dbscan = DBSCAN(eps=epsilon, min_samples=params.min_samples)
        labels = dbscan.fit_predict(features)

        # Build clusters
        clusters = self._compute_clusters(price_levels, volumes, labels)
        noise_points = self._compute_noise(price_levels, volumes, labels, clusters)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return ClusteringResult(
            clusters=clusters,
            noise_points=noise_points,
            metadata=ClusterMetadata(
                total_points=len(price_levels),
                cluster_count=len(clusters),
                noise_count=len(noise_points),
                parameters_used=params,
                computation_ms=elapsed_ms,
                auto_tuned=params.auto_tune,
            ),
        )

    def _prepare_features(
        self, price_levels: np.ndarray, volumes: np.ndarray
    ) -> np.ndarray:
        """Normalize features for DBSCAN."""
        # Normalize price to [0, 1]
        p_min, p_max = price_levels.min(), price_levels.max()
        if p_max - p_min > 0:
            norm_price = (price_levels - p_min) / (p_max - p_min)
        else:
            norm_price = np.zeros_like(price_levels)

        # Log-transform and normalize volume
        log_vol = np.log10(volumes + 1)
        v_max = log_vol.max()
        if v_max > 0:
            norm_vol = log_vol / v_max
        else:
            norm_vol = np.zeros_like(log_vol)

        return np.column_stack([norm_price, norm_vol])

    def _auto_epsilon(self, features: np.ndarray, min_samples: int) -> float:
        """Calculate epsilon using k-distance graph."""
        from sklearn.neighbors import NearestNeighbors

        nn = NearestNeighbors(n_neighbors=min_samples)
        nn.fit(features)
        distances, _ = nn.kneighbors(features)
        k_distances = np.sort(distances[:, -1])
        epsilon = np.percentile(k_distances, 90)
        return max(0.01, min(0.5, epsilon))

    def _compute_clusters(
        self, prices: np.ndarray, volumes: np.ndarray, labels: np.ndarray
    ) -> list[LiquidationCluster]:
        """Build cluster objects from labels."""
        clusters = []
        unique_labels = set(labels)

        for label in unique_labels:
            if label == -1:  # Skip noise
                continue

            mask = labels == label
            cluster_prices = prices[mask]
            cluster_volumes = volumes[mask]

            # Volume-weighted centroid
            centroid = np.average(cluster_prices, weights=cluster_volumes)

            # Density = count / price_spread (normalized)
            price_spread = cluster_prices.max() - cluster_prices.min()
            density = min(1.0, len(cluster_prices) / max(1, price_spread * 10))

            clusters.append(
                LiquidationCluster(
                    cluster_id=int(label),
                    price_min=float(cluster_prices.min()),
                    price_max=float(cluster_prices.max()),
                    centroid_price=float(centroid),
                    total_volume=float(cluster_volumes.sum()),
                    level_count=int(len(cluster_prices)),
                    density=float(density),
                )
            )

        return sorted(clusters, key=lambda c: c.centroid_price)

    def _compute_noise(
        self,
        prices: np.ndarray,
        volumes: np.ndarray,
        labels: np.ndarray,
        clusters: list[LiquidationCluster],
    ) -> list[NoisePoint]:
        """Build noise point objects."""
        noise_mask = labels == -1
        noise_prices = prices[noise_mask]
        noise_volumes = volumes[noise_mask]

        noise_points = []
        for price, volume in zip(noise_prices, noise_volumes):
            # Find distance to nearest cluster
            if clusters:
                distances = [abs(price - c.centroid_price) for c in clusters]
                dist = min(distances)
            else:
                dist = 0.0

            noise_points.append(
                NoisePoint(
                    price_level=float(price),
                    volume=float(volume),
                    distance_to_nearest=float(dist),
                )
            )

        return noise_points
```

```python
# src/clustering/__init__.py
from src.clustering.service import ClusteringService
from src.clustering.models import (
    ClusterParameters,
    ClusteringResult,
    LiquidationCluster,
    NoisePoint,
    ClusterMetadata,
)

__all__ = [
    "ClusteringService",
    "ClusterParameters",
    "ClusteringResult",
    "LiquidationCluster",
    "NoisePoint",
    "ClusterMetadata",
]
```

### Step 4: Run Test - Should PASS

```bash
uv run pytest tests/test_clustering.py::TestClusteringService::test_single_dense_cluster_detected -v
```

Expected: `PASSED`

---

## 3. API Integration (30 minutes)

### Add Endpoint

```python
# src/api/routes/clustering.py
from fastapi import APIRouter, Query, HTTPException
from src.clustering import ClusteringService, ClusterParameters, ClusteringResult

router = APIRouter(prefix="/liquidations", tags=["clustering"])

clustering_service = ClusteringService()


@router.get("/clusters", response_model=ClusteringResult)
async def get_clusters(
    symbol: str = Query(..., description="Trading pair"),
    timeframe: int = Query(30, ge=1, le=1440),
    auto_tune: bool = Query(True),
    epsilon: float = Query(0.1, ge=0.01, le=1.0),
    min_samples: int = Query(3, ge=2, le=10),
):
    """Get DBSCAN clustered liquidation zones."""
    # TODO: Fetch liquidation data from existing service
    # price_levels, volumes = liquidation_service.get_levels(symbol, timeframe)

    params = ClusterParameters(
        epsilon=epsilon,
        min_samples=min_samples,
        auto_tune=auto_tune,
    )

    # result = clustering_service.cluster_liquidations(price_levels, volumes, params)
    # return result

    raise HTTPException(501, "Integration pending")
```

---

## 4. Frontend Toggle (30 minutes)

### Add Toggle Button

```html
<!-- frontend/heatmap.html -->
<button id="cluster-toggle" class="btn">Show Zones</button>

<script>
let showClusters = false;

document.getElementById('cluster-toggle').addEventListener('click', async () => {
    showClusters = !showClusters;
    document.getElementById('cluster-toggle').textContent =
        showClusters ? 'Show Points' : 'Show Zones';

    if (showClusters) {
        await fetchAndShowClusters();
    } else {
        removeClusters();
    }
});

async function fetchAndShowClusters() {
    const response = await fetch('/liquidations/clusters?symbol=BTCUSDT&timeframe=30');
    const data = await response.json();

    const shapes = data.clusters.map(cluster => ({
        type: 'rect',
        x0: cluster.price_min,
        x1: cluster.price_max,
        y0: 0,
        y1: 1,
        fillcolor: `rgba(255, 0, 0, ${0.2 + cluster.density * 0.6})`,
        line: { width: 1, color: 'rgba(255, 0, 0, 0.8)' },
        layer: 'below'
    }));

    Plotly.relayout('heatmap', { shapes });
}

function removeClusters() {
    Plotly.relayout('heatmap', { shapes: [] });
}
</script>
```

---

## 5. Test Coverage

### Run Full Test Suite

```bash
uv run pytest tests/test_clustering.py -v --cov=src/clustering --cov-report=term-missing
```

Target: >=90% coverage

---

## 6. Verification Checklist

- [ ] `uv run pytest` - All tests pass
- [ ] `ruff check .` - No linting errors
- [ ] `ruff format .` - Code formatted
- [ ] Clustering <500ms for 1000 points
- [ ] Auto-tune produces 5-10 clusters
- [ ] Frontend toggle works
- [ ] API documentation updated

---

## Troubleshooting

### scikit-learn Import Error

```bash
uv add scikit-learn --upgrade
```

### Clustering Too Slow

- Pre-filter to visible price range
- Use `algorithm='ball_tree'` for high dimensions
- Enable caching for repeated requests

### Too Many/Few Clusters

- Adjust `min_samples` (higher = fewer clusters)
- Set `auto_tune=False` and tune epsilon manually
- Check data distribution (uniform = no clusters)

---

## Next Steps

1. Run `/speckit.tasks` to generate detailed task breakdown
2. Follow TDD workflow for each task
3. Run `/speckit.implement` when ready

---

**Quickstart Status**: ✅ **READY**
