# Feature Specification: DBSCAN Clustering for Liquidation Zones

**Feature ID**: LIQHEAT-007
**Priority**: LOW
**Status**: DEFERRED
**Created**: 2025-11-20
**Branch**: feature/007-dbscan-clustering

## Executive Summary

A visualization enhancement that applies DBSCAN (Density-Based Spatial Clustering of Applications with Noise) algorithm to identify and highlight liquidation concentration zones. This clustering approach groups nearby liquidation levels into distinct zones, making it easier to identify major support/resistance areas. However, this is primarily a UX improvement over raw heatmap data with minimal analytical benefit.

## Business Value

### Problem Statement
Current heatmap visualizations show individual liquidation levels as discrete points, making it difficult for traders to quickly identify zones of concentrated liquidation risk. While the data is accurate, the visual noise of hundreds of individual levels obscures the major concentration areas where cascading liquidations are most likely.

### Value Proposition
- **Visual Clarity**: Reduces visual noise by 70% through intelligent clustering
- **Zone Identification**: Automatically identifies 5-10 major liquidation zones
- **Risk Prioritization**: Highlights zones by total notional value at risk
- **Pattern Recognition**: Makes liquidation patterns more intuitive for traders

### Why DEFERRED
- **UX Enhancement Only**: No improvement to underlying liquidation calculations
- **Alternative Exists**: Simple price binning provides 80% of the visual benefit
- **Computational Overhead**: DBSCAN adds 200-500ms processing time
- **Parameter Sensitivity**: Requires manual tuning for different market conditions
- **Limited Value Add**: Professional traders already mentally cluster levels

### Success Metrics (If Implemented)
- Clustering computation completes in under 500ms
- Identifies 5-10 distinct zones per visualization
- 80% reduction in visual data points displayed
- User satisfaction score improves by 15%
- Zero impact on underlying data accuracy

## User Scenarios & Testing

### User Story 1 - Quick Zone Identification (Priority: P1)

Retail traders need to quickly identify major liquidation zones without analyzing hundreds of individual levels, enabling faster decision-making during volatile markets.

**Why this priority**: Core value proposition - transforms complex data into actionable zones.

**Independent Test**: Display clustered vs unclustered view side-by-side, verify zones are identifiable in <2 seconds.

**Acceptance Scenarios**:

1. **Given** 500+ liquidation levels in view, **When** DBSCAN clustering applied, **Then** displays 5-10 major zones with boundaries
2. **Given** dense liquidation area around $95k, **When** clustering runs, **Then** identifies as single "critical zone" with total value
3. **Given** sparse liquidations above $110k, **When** clustering runs, **Then** marks individual levels as "noise" (outliers)

---

### User Story 2 - Zone Strength Visualization (Priority: P2)

Traders need to understand relative strength of each liquidation zone based on total notional value and density to prioritize risk areas.

**Why this priority**: Adds analytical value by quantifying zone importance beyond just visual grouping.

**Independent Test**: Zones colored/sized by total liquidation value, largest zones immediately apparent.

**Acceptance Scenarios**:

1. **Given** zones with varying liquidation values, **When** visualized, **Then** zone size/color reflects total notional at risk
2. **Given** overlapping clusters, **When** merged, **Then** combined zone shows aggregated statistics
3. **Given** zone selection, **When** clicked, **Then** displays detailed breakdown of constituent levels

---

### User Story 3 - Dynamic Reclustering (Priority: P3)

As price moves and liquidations execute, the clustering should dynamically update to reflect new concentration areas without jarring visual transitions.

**Why this priority**: Smooth UX during real-time updates but not essential for basic functionality.

**Independent Test**: Price movement triggers smooth animated transition between cluster states.

**Acceptance Scenarios**:

1. **Given** price crosses major zone, **When** liquidations execute, **Then** zone smoothly fades with animation
2. **Given** new positions added, **When** data updates, **Then** clusters recalculate without full redraw
3. **Given** zoom level change, **When** user adjusts view, **Then** cluster parameters auto-adjust for scale

### Edge Cases

- What happens with extreme outlier liquidations (e.g., $200k when price at $95k)?
  - Mark as noise points, display separately with low opacity
- How to handle uniform distribution with no clear clusters?
  - Fall back to grid-based binning, notify user "No distinct zones identified"
- What if clustering produces too many small clusters?
  - Apply minimum size threshold, merge adjacent small clusters
- How to maintain consistency across timeframes?
  - Store clustering parameters per timeframe, smooth transitions

## Requirements

### Functional Requirements

- **FR-001**: System MUST implement DBSCAN algorithm with configurable epsilon (distance) and minPoints parameters
- **FR-002**: System MUST complete clustering within 500ms for up to 10,000 liquidation levels
- **FR-003**: System MUST identify between 3-15 clusters (configurable bounds)
- **FR-004**: System MUST mark outliers as noise points with distinct visualization
- **FR-005**: System MUST calculate cluster statistics (centroid, total value, density, spread)
- **FR-006**: System MUST support interactive cluster selection for detailed view
- **FR-007**: System MUST provide smooth transitions when clusters update (60 FPS minimum, <300ms transition duration)
- **FR-008**: System MUST allow toggling between clustered and raw views
- **FR-009**: System MUST auto-tune parameters based on data density
- **FR-010**: System MUST export cluster boundaries for external analysis *(DEFERRED to v2)*

### Key Entities

- **LiquidationCluster**: Group of nearby liquidations (id, boundary, centroid, total_value, level_count)
- **ClusterParameters**: DBSCAN configuration (epsilon, min_points, distance_metric, normalization)
- **NoisePoint**: Outlier liquidation not belonging to any cluster (level, value, distance_to_nearest)
- **ClusterTransition**: Animation state between cluster updates (old_state, new_state, progress) *(frontend-only state, not a backend Pydantic model)*

## Success Criteria

### Measurable Outcomes

- **SC-001**: Clustering algorithm executes in under 500ms for 99% of datasets
- **SC-002**: Visual complexity reduced by 70-80% (from 500+ points to 5-10 zones)
- **SC-003**: Users identify major risk zones in under 2 seconds (vs 10+ seconds for raw data)
- **SC-004**: Parameter auto-tuning achieves optimal clustering in 90% of cases
- **SC-005**: Smooth animations maintain 60 FPS during cluster transitions
- **SC-006**: Memory usage stays under 50MB for clustering operations
- **SC-007**: User satisfaction with visualization improves by 15%

## Non-Functional Requirements

### Performance Requirements
- Clustering computation under 500ms
- Incremental updates under 100ms
- Animation at 60 FPS minimum
- Memory footprint under 50MB

### Visualization Requirements
- Distinct visual treatment for clusters vs noise
- Color gradient based on zone strength
- Smooth Bezier boundaries for zones
- Interactive tooltips with zone details

### Usability Requirements
- One-click toggle between views
- Intuitive zone selection/interaction
- Mobile-responsive clustering *(OUT OF SCOPE for MVP - desktop-first)*
- Accessibility compliant colors

## Dependencies and Constraints

### Dependencies
- Existing liquidation heatmap data
- Frontend visualization library (Plotly/D3.js)
- DBSCAN implementation (scikit-learn or custom)
- Animation framework for transitions

### Constraints
- Cannot modify underlying liquidation calculations
- Must maintain backward compatibility
- Browser computation limits for real-time clustering
- Mobile device performance considerations

## Assumptions
- Liquidation levels follow clusterable patterns
- Users prefer simplified zone view over raw data
- DBSCAN parameters relatively stable across markets
- Visual clustering improves decision speed
- Zone identification more important than individual levels

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Over-clustering hides important details | MEDIUM | HIGH | Provide raw data toggle, adjustable parameters |
| Poor parameter selection creates bad clusters | HIGH | MEDIUM | Auto-tuning algorithm, preset templates |
| Performance issues on mobile devices | MEDIUM | MEDIUM | Server-side clustering option, simplified mobile view |
| Users prefer raw data | LOW | MEDIUM | A/B testing, optional feature toggle |
| Clusters mislead about actual risk | HIGH | LOW | Clear documentation, show constituent levels |

## Test Scenarios

### Scenario 1: Dense Liquidation Area
**Given**: 200 liquidations within $94k-$96k range
**When**: DBSCAN runs with auto-tuned parameters
**Then**: Identifies 2-3 major zones with clear boundaries

### Scenario 2: Sparse Distribution
**Given**: Evenly distributed liquidations every $500
**When**: Clustering attempted
**Then**: Falls back to grid binning with user notification

### Scenario 3: Extreme Price Movement
**Given**: Price drops $5k rapidly
**When**: Liquidations execute and data updates
**Then**: Clusters smoothly animate to new configuration

### Scenario 4: User Parameter Adjustment
**Given**: Default produces 15 small clusters
**When**: User adjusts sensitivity slider
**Then**: Real-time reclustering to 5-7 larger zones

## Acceptance Criteria Summary

Feature is complete when:
1. DBSCAN algorithm implemented with configurable parameters
2. Auto-tuning produces good clusters in 90% of cases
3. Performance targets met (<500ms computation)
4. Smooth animations between cluster states
5. Interactive zone selection functional
6. Toggle between clustered/raw views working
7. Mobile-responsive implementation complete
8. User documentation and examples provided

## Out of Scope
- Machine learning for parameter optimization
- Multi-dimensional clustering (price + time)
- Cross-exchange cluster correlation
- Predictive cluster evolution
- Custom clustering algorithms
- 3D visualization of clusters

## Future Enhancements
- ML-based parameter tuning
- Hierarchical clustering options
- Time-based cluster evolution
- Multi-asset cluster correlation
- Cluster-based trading signals
- VR/AR cluster visualization

## Notes
DBSCAN clustering is a pure UX enhancement that makes existing liquidation data more visually digestible. While it can improve user experience, it provides no additional analytical insight beyond what's already available in the raw heatmap. The computational overhead (500ms) and parameter sensitivity make this a "nice-to-have" rather than essential feature. Simple price binning or grid-based aggregation provides 80% of the visual benefit with 10% of the complexity.

## Recommendation: DEFER
This feature should remain DEFERRED because:
1. Pure cosmetic enhancement with no analytical value
2. Simple binning alternatives exist (grid aggregation)
3. Adds 500ms latency to every visualization update
4. Parameter tuning complexity for marginal benefit
5. Professional users prefer raw data access

Implement only if:
- User research shows strong demand for simplified visualization
- Performance can be optimized to under 100ms
- A/B testing proves significant UX improvement
- Resources available after core features complete

The existing heatmap with opacity-based density visualization already provides intuitive zone identification without explicit clustering.