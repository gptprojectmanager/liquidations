# Implementation Plan: DBSCAN Clustering for Liquidation Zones

**Feature ID**: LIQHEAT-007
**Plan Created**: 2025-12-02
**Target Branch**: `feature/007-dbscan-clustering`
**Status**: Planning Complete - Ready for Implementation

---

## Executive Summary

Add **DBSCAN clustering** to the existing liquidation heatmap system to automatically identify and visualize liquidation concentration zones. The clustering algorithm groups nearby liquidation levels into distinct zones, reducing visual complexity from 500+ individual points to 5-10 actionable zones.

**Core Principle**: KISS - Use scikit-learn's battle-tested DBSCAN implementation, integrate with existing Plotly.js frontend, add single API endpoint with toggle support.

---

## Technical Context

### Architecture Pattern: Clustering as View Layer

Clustering is a **visualization enhancement** that does NOT modify underlying liquidation calculations:

```
Existing Pipeline (unchanged):
  DuckDB → LiquidationModel → API → HeatmapDataPoints

New Clustering Layer (additive):
  HeatmapDataPoints → DBSCAN Clustering → LiquidationClusters → Plotly.js
```

### Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Clustering** | scikit-learn DBSCAN | Industry standard, O(n log n), well-documented |
| **Backend** | FastAPI + existing endpoints | Extend `/liquidations/levels` with clustering |
| **Frontend** | Plotly.js shapes/annotations | Zone boundaries via `layout.shapes` |
| **Caching** | In-memory (optional Redis) | Cluster results valid until data refresh |

### External Dependencies

**New Python Library**:
- `scikit-learn>=1.3.0` - DBSCAN implementation

**Existing (already installed)**:
- `numpy>=1.24.0` - Already in pyproject.toml
- `scipy>=1.11.0` - Already in pyproject.toml (DBSCAN uses scipy.spatial)

### Integration Points

1. **Data Source**: `GET /liquidations/levels` response (price_level, volume arrays)
2. **API Extension**: New endpoint `/liquidations/clusters`
3. **Frontend**: Add toggle button + Plotly shapes for zone visualization

---

## Constitution Check

### 1. Mathematical Correctness (MUST) ✅

**Applied**:
- DBSCAN is deterministic for fixed parameters (epsilon, min_samples)
- Cluster membership is binary (core, border, noise) - no ambiguity
- Zone boundaries computed from convex hull of cluster members

**Note**: Clustering uses float64 for scikit-learn compatibility. This is acceptable as clustering is view-layer only and does not affect financial calculations.

### 2. Test-Driven Development (MUST) ✅

**TDD Approach**:
1. RED: Write tests for DBSCAN wrapper with synthetic liquidation data
2. GREEN: Implement minimal clustering service
3. REFACTOR: Optimize for performance (<500ms target)

### 3. Exchange Compatibility (MUST) ✅

**Not Applicable**: Clustering is visualization-only, does not affect exchange data or calculations.

### 4. Performance Efficiency (SHOULD) ⚠️

**Challenge**: Multiple performance targets exist across artifacts.

**Performance Target Reconciliation**:

| Source | Target | Scope | Status |
|--------|--------|-------|--------|
| **Spec SC-001** | <500ms | Clustering algorithm (99th percentile) | **REQUIREMENT** |
| **Constitution §4** | <100ms p95 | API response | **SHOULD** (not MUST) |
| **Plan Optimization** | <200ms | Clustering for 1000 points | **STRETCH GOAL** |

**Resolution**:
- **Primary Target**: <500ms clustering (spec requirement, must meet)
- **Secondary Target**: <200ms clustering (optimization goal, aim for)
- **API Target**: <500ms total (clustering + serialization)

**Mitigation**:
- Pre-filter data (only cluster visible price range)
- Cache cluster results (invalidate on data refresh)

### 5. Data Integrity (MUST) ✅

**Applied**: Clustering is read-only operation, does not modify source data.

### 6. Graceful Degradation (SHOULD) ✅

**Fallback Path**:
- If clustering fails → return raw data + warning flag
- If no clusters found → return all points as noise + message
- If too many clusters → merge adjacent, cap at 15

### 7. Progressive Enhancement (SHOULD) ✅

**Incremental Delivery**:
1. Phase 1: Backend clustering service (testable in isolation)
2. Phase 2: API endpoint extension
3. Phase 3: Frontend toggle + visualization

### 8. Documentation Completeness (MUST) ✅

**Planned**:
- API documentation via OpenAPI
- Clustering algorithm parameters documented
- Frontend usage examples

---

## Phase 0: Research & Design Decisions

### 1. DBSCAN vs Alternatives

**Decision**: scikit-learn DBSCAN with euclidean distance on normalized (price, volume) space.

**Rationale**:
- DBSCAN handles arbitrary cluster shapes (liquidations form irregular zones)
- Automatic outlier detection (noise points = isolated liquidations)
- No need to specify k clusters upfront (unlike K-means)
- O(n log n) with KD-tree (scikit-learn default)

**Alternatives Considered**:
- K-Means: Requires k upfront, assumes spherical clusters ❌
- HDBSCAN: Better but adds dependency, overkill for this use case ❌
- OPTICS: More parameters to tune, slower ❌
- Grid binning: Already exists (simple aggregation), not true clustering ❌

### 2. Feature Space Design

**Decision**: Cluster on 2D space: (normalized_price, log_volume)

**Rationale**:
- Price normalization: `(price - min) / (max - min)` → [0, 1]
- Volume log-transform: `log10(volume + 1)` → reduces skew
- Equal weighting between price proximity and volume magnitude

### 3. Parameter Selection

**Decision**: Auto-tune epsilon based on data density, fixed min_samples=3.

**Rationale**:
- epsilon (neighborhood radius): Use k-distance graph elbow method
- min_samples=3: Small clusters are valid for liquidations

### 4. Visualization Strategy

**Decision**: Plotly.js `layout.shapes` for rectangular zone boundaries + color by volume.

**Rationale**:
- Shapes are lightweight (no extra traces)
- Rectangles sufficient for 1D price zones
- Color intensity = zone importance

---

## Phase 1: Data Models & Contracts

### Data Models

See `data-model.md` for complete entity definitions.

**Key Entities**:
1. `LiquidationCluster` - Grouped liquidation zone with statistics
2. `ClusterParameters` - DBSCAN configuration (epsilon, min_samples)
3. `NoisePoint` - Outlier liquidation not in any cluster
4. `ClusteringResult` - Full result with clusters + noise + metadata

### API Contracts

See `contracts/openapi.yaml` for full OpenAPI 3.0 specification.

**New Endpoint**:
```
GET /liquidations/clusters?symbol=BTCUSDT&timeframe=30&auto_tune=true
```

---

## Phase 2: Implementation Roadmap

### Phase 1: Setup

**Tasks**:
1. Add scikit-learn dependency to pyproject.toml
2. Create clustering module directory structure
3. Create `__init__.py` with module exports
4. Create test file scaffold

### Phase 2: Foundational (TDD Compliant)

**TDD RED: Model Tests First**
1. Write test for ClusterParameters validation
2. Write test for LiquidationCluster computed properties
3. Write test for NoisePoint model validation
4. Write test for ClusterMetadata computation
5. Write test for ClusteringResult serialization

**TDD GREEN: Model Implementation**
1. Implement ClusterParameters model
2. Implement LiquidationCluster model
3. Implement NoisePoint model
4. Implement ClusterMetadata model
5. Implement ClusteringResult model

### Phase 3: User Story 1 - Quick Zone Identification (P1)

**TDD RED: Service Tests First**
1. Write test: single dense cluster detection
2. Write test: multiple cluster detection
3. Write test: noise point handling
4. Write test: empty input returns empty result

**TDD GREEN: Service Implementation**
1. Implement `_prepare_features()` method
2. Implement `_auto_epsilon()` method
3. Implement `cluster_liquidations()` main method
4. Implement `_compute_clusters()` statistics method

### Phase 4: User Story 2 - Zone Strength Visualization (P2)

**API Integration**
1. Create Pydantic response models
2. Implement GET /liquidations/clusters endpoint
3. Write API integration tests

**Frontend Visualization**
1. Add cluster toggle button
2. Implement Plotly shapes for zone rectangles
3. Implement color gradient based on total_volume
4. Implement zone click handler for details

### Phase 5: User Story 3 - Dynamic Reclustering (P3)

1. Add cluster caching with TTL
2. Implement incremental cluster update detection
3. Add smooth CSS transitions for zone shapes
4. Implement auto-refresh polling with cluster diff
5. Write test for cluster caching behavior

### Phase 6: Polish & Cross-Cutting

**Performance & Validation**
1. Add performance benchmark test (<500ms requirement, <200ms target)
2. Add auto-tune validation test (90% success rate)

**Graceful Degradation**
1. Implement fallback to grid-binning when DBSCAN returns 0 clusters
2. Add graceful degradation when clustering fails

**Documentation & Quality**
1. Update OpenAPI documentation
2. Run ruff check and fix linting issues
3. Run full test suite and verify >=90% coverage

---

## Performance Benchmarks

**Targets** (per reconciliation above):

| Data Size | Required | Target | Fallback |
|-----------|----------|--------|----------|
| 100 points | <100ms | <50ms | - |
| 1000 points | <500ms | <200ms | - |
| 5000 points | <500ms | <400ms | Pre-filter |
| 10000 points | <1000ms | <800ms | Sampling |

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Clustering too slow | HIGH | Pre-filter visible range, cache results |
| Poor cluster quality | MEDIUM | Auto-tuning, manual override parameters |
| Too many/few clusters | MEDIUM | Min/max bounds (3-15), merge small clusters |
| Frontend performance | LOW | Limit shapes to 20, simplify boundaries |

---

## Success Criteria

### Functional Requirements

- [ ] DBSCAN clustering implemented with configurable parameters
- [ ] Auto-tuning produces 5-10 clusters in 90% of cases (per SC-004)
- [ ] API endpoint returns clusters with statistics
- [ ] Frontend displays zone rectangles with toggle
- [ ] Noise points displayed separately

### Code Quality Requirements

- [ ] New code <300 lines (excluding tests)
- [ ] Test coverage >=90% for clustering module
- [ ] All tests pass (pytest)
- [ ] Linting clean (ruff check .)

### Performance Requirements

- [ ] Clustering <500ms required, <200ms target for 1000 points
- [ ] API response <500ms including clustering
- [ ] Frontend render <100ms for zones

---

## Next Steps

1. **Create feature branch**: `git checkout -b feature/007-dbscan-clustering`
2. **Generate tasks**: `/speckit.tasks` for detailed task breakdown
3. **Execute Phase 1**: Setup and dependencies
4. **TDD workflow**: Write tests first, implement incrementally

---

**Plan Status**: ✅ **READY FOR IMPLEMENTATION**

**Estimated Effort**: 2-3 days
**Complexity**: Low-Medium (well-defined scope, existing infrastructure)
