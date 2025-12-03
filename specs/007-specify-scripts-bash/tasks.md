# Tasks: DBSCAN Clustering for Liquidation Zones

**Feature ID**: LIQHEAT-007
**Input**: Design documents from `/specs/007-specify-scripts-bash/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**TDD Mode**: Enabled (per constitution §2 - Test-Driven Development MUST)

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and clustering module structure

- [x] T001 Add scikit-learn>=1.3.0 dependency to pyproject.toml
- [x] T002 Create clustering module directory at src/clustering/
- [x] T003 [P] Create src/clustering/__init__.py with module exports
- [x] T004 [P] Create tests/test_clustering.py test file scaffold

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pydantic models that ALL user stories depend on

**⚠️ CRITICAL**: Models must be complete before ANY service implementation

### TDD RED: Model Tests First

- [x] T005 [P] Write test for ClusterParameters validation in tests/test_clustering.py
- [x] T006 [P] Write test for LiquidationCluster computed properties in tests/test_clustering.py
- [x] T007 [P] Write test for NoisePoint model validation in tests/test_clustering.py
- [x] T008 [P] Write test for ClusterMetadata computation in tests/test_clustering.py
- [x] T009 [P] Write test for ClusteringResult serialization in tests/test_clustering.py

### TDD GREEN: Model Implementation

- [x] T010 [P] Implement ClusterParameters model in src/clustering/models.py
- [x] T011 [P] Implement LiquidationCluster model in src/clustering/models.py
- [x] T012 [P] Implement NoisePoint model in src/clustering/models.py
- [x] T013 [P] Implement ClusterMetadata model in src/clustering/models.py
- [x] T014 Implement ClusteringResult model in src/clustering/models.py (depends on T010-T013)

**Checkpoint**: All model tests pass - service implementation can begin

---

## Phase 3: User Story 1 - Quick Zone Identification (Priority: P1) 🎯 MVP

**Goal**: Retail traders can quickly identify major liquidation zones without analyzing hundreds of individual levels

**Independent Test**: Display clustered vs unclustered view, verify zones are identifiable in <2 seconds

**Acceptance Criteria**:
1. 500+ liquidation levels → 5-10 major zones with boundaries
2. Dense liquidation area → single "critical zone" with total value
3. Sparse liquidations → marked as "noise" (outliers)

### TDD RED: Service Tests First

- [x] T015 [P] [US1] Write test: single dense cluster detection in tests/test_clustering.py
- [x] T016 [P] [US1] Write test: multiple cluster detection in tests/test_clustering.py
- [x] T017 [P] [US1] Write test: noise point handling in tests/test_clustering.py
- [x] T018 [P] [US1] Write test: empty input returns empty result in tests/test_clustering.py

### TDD GREEN: Service Implementation

- [x] T019 [US1] Implement `_prepare_features()` method in src/clustering/service.py
- [x] T020 [US1] Implement `_auto_epsilon()` method in src/clustering/service.py
- [x] T021 [US1] Implement `cluster_liquidations()` main method in src/clustering/service.py
- [x] T022 [US1] Implement `_compute_clusters()` statistics method in src/clustering/service.py
- [x] T023 [US1] Implement `_compute_noise()` noise point method in src/clustering/service.py

**Checkpoint**: Core clustering works - run `uv run pytest tests/test_clustering.py -v` all pass

---

## Phase 4: User Story 2 - Zone Strength Visualization (Priority: P2)

**Goal**: Traders understand relative strength of each liquidation zone based on total notional value and density

**Independent Test**: Zones colored/sized by total liquidation value, largest zones immediately apparent

**Acceptance Criteria**:
1. Zones with varying values → size/color reflects total notional at risk
2. Overlapping clusters → combined zone shows aggregated statistics
3. Zone selection → displays detailed breakdown of constituent levels

### TDD RED: API Tests First

- [ ] T024 [P] [US2] Write API contract test for GET /liquidations/clusters in tests/test_api_clustering.py
- [ ] T025 [P] [US2] Write test for error responses (400, 404, 500) in tests/test_api_clustering.py

### TDD GREEN: API Implementation

- [ ] T026 [US2] Create Pydantic response models in src/api/schemas/clustering.py
- [ ] T027 [US2] Implement GET /liquidations/clusters endpoint in src/api/routes/clustering.py
- [ ] T028 [US2] Register clustering router in src/api/main.py

### Frontend Visualization

- [ ] T029 [P] [US2] Add cluster toggle button in frontend/heatmap.html
- [ ] T030 [US2] Implement fetchAndShowClusters() function in frontend/heatmap.html
- [ ] T031 [US2] Implement Plotly shapes for zone rectangles in frontend/heatmap.html
- [ ] T032 [US2] Implement color gradient based on total_volume in frontend/heatmap.html
- [ ] T033 [US2] Implement zone click handler for details in frontend/heatmap.html

**Checkpoint**: API returns clusters, frontend displays zones with toggle

---

## Phase 5: User Story 3 - Dynamic Reclustering (Priority: P3)

**Goal**: Clustering dynamically updates as price moves and liquidations execute, with smooth visual transitions

**Independent Test**: Price movement triggers smooth animated transition between cluster states

**Acceptance Criteria**:
1. Price crosses major zone → zone smoothly fades with animation
2. New positions added → clusters recalculate without full redraw
3. Zoom level change → cluster parameters auto-adjust for scale

### TDD RED: Caching Tests First

- [ ] T034 [P] [US3] Write test for cluster caching with TTL in tests/test_clustering.py
- [ ] T035 [P] [US3] Write test for cache invalidation on data refresh in tests/test_clustering.py

### Implementation

- [ ] T036 [US3] Add cluster caching with TTL in src/clustering/cache.py
- [ ] T037 [US3] Implement incremental cluster update detection in src/clustering/service.py
- [ ] T038 [US3] Add smooth CSS transitions for zone shapes in frontend/heatmap.html (60 FPS, <300ms duration per FR-007)
- [ ] T039 [US3] Implement auto-refresh polling with cluster diff in frontend/heatmap.html

**Checkpoint**: Dynamic updates work smoothly at 60 FPS

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Performance validation, graceful degradation, and documentation

### Performance & Validation

- [ ] T040 [P] Add performance benchmark test (<500ms requirement, <200ms target) in tests/test_clustering.py
- [ ] T041 [P] Add auto-tune validation test (90% success rate) in tests/test_clustering.py

### Graceful Degradation

- [ ] T042 Implement fallback to grid-binning when DBSCAN returns 0 clusters in src/clustering/service.py
- [ ] T043 Add graceful degradation when clustering fails in src/clustering/service.py

### Documentation & Quality

- [ ] T044 [P] Update OpenAPI documentation in src/api/main.py
- [ ] T045 Run ruff check and fix linting issues
- [ ] T046 Run full test suite and verify >=90% coverage for clustering module

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup
    ↓
Phase 2: Foundational (Models)
    ↓ (BLOCKS all user stories)
Phase 3: US1 - Quick Zone ID (P1) ─┬─→ MVP Checkpoint
Phase 4: US2 - Zone Strength (P2) ─┤
Phase 5: US3 - Dynamic Recluster (P3)
    ↓
Phase 6: Polish
```

### User Story Dependencies

| Story | Depends On | Can Parallelize? |
|-------|------------|------------------|
| US1 (P1) | Phase 2 (Foundational) | ✅ After Phase 2 |
| US2 (P2) | Phase 2 + US1 service | ⚠️ API needs service from US1 |
| US3 (P3) | Phase 2 + US1/US2 | ⚠️ Needs frontend from US2 |

### Within Each User Story

1. Tests MUST be written and FAIL before implementation (TDD RED)
2. Models before services
3. Services before endpoints
4. Backend before frontend
5. Core implementation before integration

### Parallel Opportunities

**Phase 1** (all parallel):
```
T001 ─┬─ T002
T003 ─┴─ T004
```

**Phase 2** (tests parallel, then models parallel):
```
T005 ─┬─ T006 ─┬─ T007 ─┬─ T008 ─┬─ T009
      ↓
T010 ─┬─ T011 ─┬─ T012 ─┬─ T013 → T014
```

**Phase 3 US1** (tests parallel, then sequential service):
```
T015 ─┬─ T016 ─┬─ T017 ─┬─ T018
      ↓
T019 → T020 → T021 → T022 → T023
```

**Phase 4 US2** (tests parallel, API sequential, frontend parallel):
```
T024 ─┬─ T025
      ↓
T026 → T027 → T028
      ↓
T029 ─┬─ (T030 → T031 → T032 → T033)
```

---

## Parallel Example: Phase 2 Foundational

```bash
# Launch all model tests together (TDD RED):
Task: "Write test for ClusterParameters validation" [T005]
Task: "Write test for LiquidationCluster computed properties" [T006]
Task: "Write test for NoisePoint model validation" [T007]
Task: "Write test for ClusterMetadata computation" [T008]
Task: "Write test for ClusteringResult serialization" [T009]

# After tests written and failing, implement models in parallel:
Task: "Implement ClusterParameters model" [T010]
Task: "Implement LiquidationCluster model" [T011]
Task: "Implement NoisePoint model" [T012]
Task: "Implement ClusterMetadata model" [T013]
# Then T014 depends on all above
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T004)
2. Complete Phase 2: Foundational Models (T005-T014)
3. Complete Phase 3: User Story 1 (T015-T023)
4. **STOP and VALIDATE**: `uv run pytest tests/test_clustering.py -v`
5. Core clustering works - can demo/deploy

### Incremental Delivery

1. **Setup + Foundational** → Foundation ready
2. **Add US1** → Test independently → **MVP Ready!** 🎯
3. **Add US2** → Test independently → API + Frontend visible
4. **Add US3** → Test independently → Full dynamic experience
5. **Polish** → Performance verified, edge cases handled

### TDD Discipline

For EACH task:
1. **RED**: Write test, run it, see it FAIL
2. **GREEN**: Implement minimal code to pass
3. **REFACTOR**: Clean up while tests pass
4. **COMMIT**: `git add . && git commit -m "TDD [phase]: [description]"`

---

## Summary

| Metric | Value |
|--------|-------|
| **Total Tasks** | 46 |
| **Setup Tasks** | 4 |
| **Foundational Tasks** | 10 |
| **US1 Tasks** | 9 |
| **US2 Tasks** | 11 |
| **US3 Tasks** | 6 |
| **Polish Tasks** | 6 |
| **Parallelizable Tasks** | 24 (52%) |
| **MVP Scope** | T001-T023 (23 tasks) |

---

## Notes

- TDD is MANDATORY per constitution §2
- Performance target: <500ms clustering (required), <200ms (target)
- Float64 acceptable for clustering (view-layer only, documented in data-model.md)
- All [P] tasks can run in parallel within their phase
- Commit after each task or logical group
- Stop at any checkpoint to validate independently

---

## Deferred Requirements (Out of Scope for MVP)

Per analysis reconciliation, the following are explicitly **deferred**:

| Requirement | Status | Rationale |
|-------------|--------|-----------|
| **FR-010** (Export cluster boundaries) | DEFERRED to v2 | Nice-to-have, not core functionality |
| **Mobile-responsive clustering** | OUT OF SCOPE | Desktop-first approach; mobile can use raw heatmap |
| **Bezier boundaries** | DEFERRED | Rectangles sufficient; Bezier adds complexity |

These may be added in future iterations after MVP validation.

---

## Analysis Reconciliation

**Issues Addressed** (from `/speckit.analyze`):

| Issue ID | Resolution |
|----------|------------|
| A1 (FR-007 ambiguity) | Added "60 FPS, <300ms" to spec.md and T038 |
| U2 (FR-010 no tasks) | Marked DEFERRED in spec.md |
| G1 (Mobile not tasked) | Marked OUT OF SCOPE in spec.md |
| I1 (ClusterTransition entity) | Clarified as frontend-only in spec.md |
| I2 (80% vs 90% auto-tune) | Spec's 90% (SC-004) is authoritative |

**Coverage after reconciliation**: 100% of in-scope requirements have tasks.
