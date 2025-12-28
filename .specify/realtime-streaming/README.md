# Real-time WebSocket Streaming Feature

> **Status**: Specification Complete
> **Created**: 2025-12-28
> **Estimated Duration**: 2-3 weeks

## Quick Links

- [Specification](./spec.md) - Complete technical design
- [Tasks](./tasks.md) - Implementation tasks (25 total)

## Overview

Add real-time WebSocket streaming to push heatmap updates to connected clients, eliminating the need for polling.

**Key Benefits**:
- Sub-second update latency (vs 5-60s polling delay)
- 70% reduction in server load (no cache misses)
- Improved UX for traders during high volatility events

## Architecture

```
Client (Browser)
    ↓ WebSocket
FastAPI /ws/heatmap
    ↓
ConnectionManager (in-memory)
    ↓
Background Task (query DuckDB every 5s)
    ↓
Broadcast to subscribed clients
```

**Phase 1 (Week 1)**: Single-server, in-memory broadcast
**Phase 2 (Week 2)**: Production rollout with monitoring
**Phase 3 (Week 3-4)**: Redis pub/sub for multi-server scaling

## Implementation Plan

### Phase 1: MVP (Week 1)
1. **T001-T003**: ConnectionManager with backpressure handling
2. **T004-T006**: Background task + lifecycle hooks
3. **T007-T010**: JavaScript client + tests

**Deliverable**: Working WebSocket endpoint with 100 client capacity

### Phase 2: Production (Week 2)
1. **T011-T013**: Monitoring (Prometheus, logging, stats)
2. **T014-T015**: Load testing + frontend integration
3. **T017-T019**: Staging deployment → Production rollout

**Deliverable**: Production-ready with 1000+ client capacity

### Phase 3: Scaling (Week 3-4)
1. **T020**: Redis pub/sub integration
2. **T021-T022**: Multi-server deployment + load testing

**Deliverable**: Horizontally scalable (2000+ clients)

## Quick Start (After Implementation)

**Server**:
```bash
# Enable WebSocket
export WS_ENABLED=true
export WS_UPDATE_INTERVAL=5

# Start server
uv run uvicorn liquidationheatmap.api.main:app --reload
```

**Client** (JavaScript):
```javascript
const ws = new HeatmapWebSocket('ws://localhost:8000/ws/heatmap', {
    onSnapshot: (msg) => updateChart(msg.data),
    onStatusChange: (status) => showStatus(status)
});

ws.connect();
ws.subscribe(['BTCUSDT']);
```

## Testing

```bash
# Unit tests
uv run pytest tests/test_ws/

# Integration tests
uv run pytest tests/integration/test_ws_endpoint.py

# Load test (requires k6)
k6 run tests/load/ws_load_test.js
```

## Success Metrics

| Metric | Target | Status |
|--------|--------|--------|
| Update Latency (p95) | <500ms | Not measured |
| Concurrent Connections | 1000+ | Not tested |
| Bandwidth per Client | <50 KB/s | Not measured |
| Message Drop Rate | <0.1% | Not measured |

## Technical Decisions

### Why In-Memory First?
**KISS principle**: Simpler deployment, easier debugging. Redis adds complexity only when needed (multi-server).

### Why 5s Update Interval?
**Balance**: Real-time feel without overwhelming DuckDB with queries. Configurable via `WS_UPDATE_INTERVAL`.

### Why No Authentication?
**YAGNI**: CORS provides sufficient protection for MVP. Add JWT if abuse detected in production.

## Files Created

```
.specify/realtime-streaming/
├── spec.md               # Technical specification (42 KB)
├── tasks.md              # Implementation tasks (25 tasks)
└── README.md             # This file
```

## Next Steps

1. **Review spec.md**: Understand architecture and design decisions
2. **Start T001**: Implement ConnectionManager (TDD workflow)
3. **Run tests**: `uv run pytest` after each task
4. **Deploy staging**: After Phase 1 complete (T017)
5. **Load test**: Validate with k6 (T018)
6. **Production**: Gradual rollout (T019)

## Questions?

- **Technical**: See [spec.md](./spec.md) sections
- **Implementation**: See [tasks.md](./tasks.md) with TDD steps
- **Troubleshooting**: (Will be created as `docs/websocket_troubleshooting.md`)

---

**Remember**: Follow KISS & YAGNI. Start simple (in-memory), scale later (Redis).
