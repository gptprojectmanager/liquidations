# Data Models: DBSCAN Clustering for Liquidation Zones

**Feature ID**: LIQHEAT-007
**Created**: 2025-12-02
**Status**: Ready for Implementation

---

## Precision Trade-off Documentation

### Constitution Requirement

The project constitution (§1 Mathematical Correctness) requires:
> "All financial calculations MUST use Decimal128 for monetary values"

### Clustering Exception

**Decision**: Clustering operations use `float64` (NumPy/scikit-learn native type)

**Rationale**:
1. **View-layer only**: Clustering is a visualization enhancement, NOT a financial calculation
2. **scikit-learn requirement**: DBSCAN requires NumPy arrays (float64)
3. **No monetary impact**: Cluster boundaries are approximate visual aids
4. **Acceptable precision**: ±0.0001% error in cluster boundaries has zero trading impact

**Mitigation**:
- Source data (price_level, volume) remains Decimal128 in DuckDB
- Conversion to float64 happens at clustering boundary
- Cluster statistics (total_volume, avg_price) are for display only
- No cluster values feed back into financial calculations

---

## Entity Definitions

### 1. ClusterParameters

Configuration for DBSCAN algorithm.

```python
from pydantic import BaseModel, Field, field_validator
from typing import Literal


class ClusterParameters(BaseModel):
    """DBSCAN clustering configuration parameters."""

    epsilon: float = Field(
        default=0.1,
        ge=0.01,
        le=1.0,
        description="Neighborhood radius in normalized space [0.01, 1.0]"
    )
    min_samples: int = Field(
        default=3,
        ge=2,
        le=10,
        description="Minimum points to form a cluster [2, 10]"
    )
    auto_tune: bool = Field(
        default=True,
        description="Auto-calculate epsilon using k-distance graph"
    )
    distance_metric: Literal["euclidean", "manhattan"] = Field(
        default="euclidean",
        description="Distance metric for DBSCAN"
    )

    @field_validator("epsilon")
    @classmethod
    def validate_epsilon(cls, v: float) -> float:
        """Ensure epsilon is within valid range."""
        if v < 0.01 or v > 1.0:
            raise ValueError(f"epsilon must be in [0.01, 1.0], got {v}")
        return round(v, 4)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"epsilon": 0.1, "min_samples": 3, "auto_tune": True},
                {"epsilon": 0.05, "min_samples": 5, "auto_tune": False}
            ]
        }
    }
```

---

### 2. LiquidationCluster

A cluster of grouped liquidation levels.

```python
from pydantic import BaseModel, Field, computed_field
from typing import List


class LiquidationCluster(BaseModel):
    """A cluster of nearby liquidation levels."""

    cluster_id: int = Field(
        ge=0,
        description="Unique cluster identifier (0-indexed)"
    )
    price_min: float = Field(
        description="Lower price boundary of cluster"
    )
    price_max: float = Field(
        description="Upper price boundary of cluster"
    )
    centroid_price: float = Field(
        description="Volume-weighted center price"
    )
    total_volume: float = Field(
        ge=0,
        description="Sum of all liquidation volumes in cluster"
    )
    level_count: int = Field(
        ge=1,
        description="Number of liquidation levels in cluster"
    )
    density: float = Field(
        ge=0,
        le=1,
        description="Cluster density score [0, 1]"
    )

    @computed_field
    @property
    def price_spread(self) -> float:
        """Price range of the cluster."""
        return self.price_max - self.price_min

    @computed_field
    @property
    def avg_volume_per_level(self) -> float:
        """Average volume per liquidation level."""
        return self.total_volume / self.level_count if self.level_count > 0 else 0.0

    @computed_field
    @property
    def zone_strength(self) -> str:
        """Qualitative strength rating based on density and volume."""
        if self.density > 0.7 and self.level_count > 10:
            return "critical"
        elif self.density > 0.4 or self.level_count > 5:
            return "significant"
        else:
            return "minor"

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "cluster_id": 0,
                    "price_min": 94500.0,
                    "price_max": 95200.0,
                    "centroid_price": 94850.0,
                    "total_volume": 15000000.0,
                    "level_count": 45,
                    "density": 0.72
                }
            ]
        }
    }
```

---

### 3. NoisePoint

An outlier liquidation level not belonging to any cluster.

```python
from pydantic import BaseModel, Field


class NoisePoint(BaseModel):
    """Outlier liquidation not belonging to any cluster."""

    price_level: float = Field(
        description="Price level of the outlier liquidation"
    )
    volume: float = Field(
        ge=0,
        description="Volume at this price level"
    )
    distance_to_nearest: float = Field(
        ge=0,
        description="Distance to nearest cluster centroid (normalized)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "price_level": 120000.0,
                    "volume": 50000.0,
                    "distance_to_nearest": 0.85
                }
            ]
        }
    }
```

---

### 4. ClusterMetadata

Metadata about the clustering operation.

```python
from pydantic import BaseModel, Field
from datetime import datetime


class ClusterMetadata(BaseModel):
    """Metadata about the clustering operation."""

    symbol: str = Field(
        description="Trading pair symbol (e.g., BTCUSDT)"
    )
    timeframe_minutes: int = Field(
        ge=1,
        description="Data timeframe in minutes"
    )
    total_points: int = Field(
        ge=0,
        description="Total liquidation levels processed"
    )
    cluster_count: int = Field(
        ge=0,
        description="Number of clusters identified"
    )
    noise_count: int = Field(
        ge=0,
        description="Number of noise points (outliers)"
    )
    parameters_used: ClusterParameters = Field(
        description="DBSCAN parameters used for clustering"
    )
    computation_ms: float = Field(
        ge=0,
        description="Clustering computation time in milliseconds"
    )
    auto_tuned: bool = Field(
        description="Whether epsilon was auto-tuned"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of clustering operation"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "symbol": "BTCUSDT",
                    "timeframe_minutes": 30,
                    "total_points": 523,
                    "cluster_count": 7,
                    "noise_count": 12,
                    "parameters_used": {"epsilon": 0.08, "min_samples": 3, "auto_tune": True},
                    "computation_ms": 145.3,
                    "auto_tuned": True,
                    "timestamp": "2025-12-02T10:30:00Z"
                }
            ]
        }
    }
```

---

### 5. ClusteringResult

Complete result of a clustering operation.

```python
from pydantic import BaseModel, Field, computed_field
from typing import List, Optional


class ClusteringResult(BaseModel):
    """Complete result of DBSCAN clustering operation."""

    clusters: List[LiquidationCluster] = Field(
        default_factory=list,
        description="List of identified clusters"
    )
    noise_points: List[NoisePoint] = Field(
        default_factory=list,
        description="List of outlier points"
    )
    metadata: ClusterMetadata = Field(
        description="Clustering operation metadata"
    )
    fallback_used: bool = Field(
        default=False,
        description="Whether fallback (grid binning) was used"
    )
    warning: Optional[str] = Field(
        default=None,
        description="Warning message if clustering had issues"
    )

    @computed_field
    @property
    def coverage_ratio(self) -> float:
        """Ratio of clustered points to total points."""
        total = self.metadata.total_points
        if total == 0:
            return 0.0
        clustered = sum(c.level_count for c in self.clusters)
        return clustered / total

    @computed_field
    @property
    def total_clustered_volume(self) -> float:
        """Sum of volumes in all clusters."""
        return sum(c.total_volume for c in self.clusters)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "clusters": [
                        {
                            "cluster_id": 0,
                            "price_min": 94500.0,
                            "price_max": 95200.0,
                            "centroid_price": 94850.0,
                            "total_volume": 15000000.0,
                            "level_count": 45,
                            "density": 0.72
                        }
                    ],
                    "noise_points": [
                        {"price_level": 120000.0, "volume": 50000.0, "distance_to_nearest": 0.85}
                    ],
                    "metadata": {
                        "symbol": "BTCUSDT",
                        "timeframe_minutes": 30,
                        "total_points": 523,
                        "cluster_count": 7,
                        "noise_count": 12,
                        "parameters_used": {"epsilon": 0.08, "min_samples": 3, "auto_tune": True},
                        "computation_ms": 145.3,
                        "auto_tuned": True
                    },
                    "fallback_used": False,
                    "warning": None
                }
            ]
        }
    }
```

---

## Entity Relationship Diagram

```
┌─────────────────────┐
│  ClusterParameters  │
├─────────────────────┤
│ epsilon: float      │
│ min_samples: int    │
│ auto_tune: bool     │
│ distance_metric: str│
└─────────┬───────────┘
          │
          │ used_by
          ▼
┌─────────────────────┐
│  ClusterMetadata    │
├─────────────────────┤
│ symbol: str         │
│ timeframe_minutes   │
│ total_points: int   │
│ cluster_count: int  │
│ noise_count: int    │
│ computation_ms: float│
│ auto_tuned: bool    │
│ timestamp: datetime │
└─────────┬───────────┘
          │
          │ part_of
          ▼
┌─────────────────────┐       ┌─────────────────────┐
│  ClusteringResult   │       │  LiquidationCluster │
├─────────────────────┤       ├─────────────────────┤
│ clusters: List      │──────▶│ cluster_id: int     │
│ noise_points: List  │       │ price_min: float    │
│ metadata: Metadata  │       │ price_max: float    │
│ fallback_used: bool │       │ centroid_price: float│
│ warning: str?       │       │ total_volume: float │
└─────────┬───────────┘       │ level_count: int    │
          │                   │ density: float      │
          │                   └─────────────────────┘
          │
          │ contains
          ▼
┌─────────────────────┐
│     NoisePoint      │
├─────────────────────┤
│ price_level: float  │
│ volume: float       │
│ distance_to_nearest │
└─────────────────────┘
```

---

## Validation Rules Summary

| Entity | Field | Validation |
|--------|-------|------------|
| ClusterParameters | epsilon | [0.01, 1.0] |
| ClusterParameters | min_samples | [2, 10] |
| LiquidationCluster | cluster_id | >= 0 |
| LiquidationCluster | level_count | >= 1 |
| LiquidationCluster | density | [0, 1] |
| NoisePoint | volume | >= 0 |
| NoisePoint | distance_to_nearest | >= 0 |
| ClusterMetadata | timeframe_minutes | >= 1 |
| ClusterMetadata | computation_ms | >= 0 |

---

## JSON Schema Export

All models support automatic JSON Schema generation via Pydantic:

```python
from pydantic import BaseModel
import json

# Export schema for any model
schema = ClusteringResult.model_json_schema()
print(json.dumps(schema, indent=2))
```

---

**Data Model Status**: ✅ **READY FOR IMPLEMENTATION**
