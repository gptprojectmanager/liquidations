# Real-time WebSocket Streaming - Specification Summary

**Created**: 2025-12-28
**Status**: Complete and ready for implementation
**Estimated Duration**: 2-3 weeks (3 phases)

---

## Deliverables Created

### 1. Technical Specification
**File**: `spec.md` (1,064 lines, 37 KB)

**Contents**:
- Problem statement and goals
- User stories (3 scenarios)
- Architecture design (single-server + multi-server)
- API specification (WebSocket protocol)
- Connection management strategy
- Backpressure handling
- Testing strategy
- Deployment considerations
- Monitoring & observability
- Migration path (3 phases)
- Risks & mitigations

**Key Technical Decisions**:
- KISS: In-memory broadcast first (no Redis until Phase 3)
- Backpressure: 1s timeout to prevent slow clients blocking fast clients
- Update frequency: 5s default (configurable)
- No authentication for MVP (CORS only)

### 2. Implementation Tasks
**File**: `tasks.md` (873 lines, 25 KB)

**Task Breakdown**:
- **Phase 1 (MVP)**: T001-T010 (10 tasks, ~1 week)
  - ConnectionManager with backpressure
  - WebSocket endpoint
  - Background update task
  - JavaScript client
  - Unit + integration tests

- **Phase 2 (Production)**: T011-T019 (9 tasks, ~1 week)
  - Monitoring (Prometheus, logging)
  - Load testing with k6
  - Frontend integration
  - Staging + production deployment

- **Phase 3 (Scaling)**: T020-T022 (3 tasks, ~4 days)
  - Redis pub/sub integration
  - Multi-server deployment
  - Load testing at scale

- **Documentation**: T023-T025 (3 tasks, ~1 day)
  - API documentation
  - Architecture updates
  - Troubleshooting guide

**Total**: 25 tasks, ~2.5 weeks estimated

### 3. Quick Start Guide
**File**: `README.md` (143 lines, 4 KB)

**Contents**:
- Overview and benefits
- Architecture diagram (text)
- Implementation plan summary
- Quick start examples (server + client)
- Testing commands
- Success metrics
- Technical decisions rationale
- Next steps

### 4. Architecture Diagrams
**File**: `ARCHITECTURE_DIAGRAM.md` (421 lines)

**Visual Documentation**:
- High-level data flow (browser → FastAPI → DuckDB)
- Message flow examples (subscribe, broadcast, slow consumer)
- Multi-server architecture (Phase 3 with Redis)
- Backpressure handling detail
- Data change detection logic
- Monitoring integration
- Configuration flow
- Error recovery scenarios

---

## Architecture Highlights

### Single-Server (Phase 1)
```
Browser WebSocket
    ↓
FastAPI /ws/heatmap
    ↓
ConnectionManager (in-memory dict)
    ↓
Background Task (query DuckDB every 5s)
    ↓
Broadcast to subscribed clients
```

**Capacity**: 1000 concurrent connections

### Multi-Server (Phase 3)
```
Clients
    ↓
Nginx Load Balancer (ip_hash)
    ↓
FastAPI Server 1, Server 2, ...
    ↓
Redis Pub/Sub (heatmap:BTCUSDT, heatmap:ETHUSDT)
    ↓
Local ConnectionManager per server
```

**Capacity**: 2000+ concurrent connections (horizontally scalable)

---

## Implementation Checklist

### Prerequisites
- [x] FastAPI already in use
- [x] Redis client in dependencies (`redis>=5.0.0`)
- [x] WebSockets library in dependencies (`websockets>=12.0`)
- [x] Existing heatmap calculation logic (`calculate_time_evolving_heatmap`)
- [x] DuckDB with klines and OI data

### Phase 1: MVP (Week 1)
- [ ] T001: Create ConnectionManager class
- [ ] T002: Add /ws/heatmap endpoint
- [ ] T003: Implement backpressure handling
- [ ] T004: Create background task
- [ ] T005: Implement snapshot helper
- [ ] T006: Add startup/shutdown hooks
- [ ] T007: JavaScript client library
- [ ] T008: Environment variable config
- [ ] T009: Unit tests for ConnectionManager
- [ ] T010: Integration tests for endpoint

**Exit Criteria**: 
- All tests passing
- Can connect 100 clients
- Snapshots broadcast every 5s
- Slow consumers detected

### Phase 2: Production (Week 2)
- [ ] T011: /ws/stats endpoint
- [ ] T012: Prometheus metrics
- [ ] T013: Structured logging
- [ ] T014: k6 load test script
- [ ] T015: Frontend integration
- [ ] T016: Feature flag
- [ ] T017: Deploy to staging
- [ ] T018: Run k6 load test (1000 clients)
- [ ] T019: Production deployment (gradual rollout)

**Exit Criteria**:
- 1000 concurrent connections sustained
- p95 latency <500ms
- Memory usage <2GB
- No errors in logs (24h monitoring)

### Phase 3: Scaling (Week 3-4)
- [ ] T020: Redis pub/sub integration
- [ ] T021: Multi-server deployment
- [ ] T022: Load test at 2000 clients

**Exit Criteria**:
- 2000+ concurrent connections
- Redis pub/sub working across servers
- Graceful fallback if Redis fails

---

## Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Update Latency (p95) | <500ms | Prometheus histogram: `ws_broadcast_duration_seconds` |
| Concurrent Connections | 1000+ | k6 load test: `k6 run --vus 1000 ws_load_test.js` |
| Bandwidth per Client | <50 KB/s | Monitor network traffic: `snapshot_size × update_frequency` |
| Message Drop Rate | <0.1% | Counter: `slow_consumer_warnings / messages_sent` |
| Connection Success Rate | >99% | k6 checks: `status is 101` |
| Memory Usage | <2GB | Docker stats or Prometheus: `process_resident_memory_bytes` |

---

## Key Features

### 1. Real-time Updates
- Push-based (no polling)
- Sub-second latency
- Configurable update interval (default: 5s)

### 2. Symbol Subscriptions
- Multi-symbol support: `["BTCUSDT", "ETHUSDT"]`
- Subscribe/unsubscribe dynamically
- Independent updates per symbol

### 3. Backpressure Handling
- 1s send timeout per client
- Slow consumer warnings
- Fast clients not blocked by slow clients

### 4. Auto-Reconnect
- Exponential backoff (max 5 attempts)
- Seamless re-subscription
- Fallback to polling after 3 failures

### 5. Horizontal Scalability
- Phase 1: Single-server (1000 clients)
- Phase 3: Multi-server via Redis (2000+ clients)
- Nginx load balancing with sticky sessions

---

## File Structure

```
.specify/realtime-streaming/
├── spec.md                    # Full technical specification
├── tasks.md                   # 25 implementation tasks
├── README.md                  # Quick start guide
├── ARCHITECTURE_DIAGRAM.md    # Visual diagrams and flows
└── SUMMARY.md                 # This file
```

**Total Documentation**: ~2,500 lines across 4 files

---

## Technologies Used

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| WebSocket Server | FastAPI + Uvicorn | Native WebSocket support, async/await |
| Connection Management | In-memory dict (Phase 1) | Simple, fast, no external dependencies |
| Pub/Sub (Phase 3) | Redis | Battle-tested, low latency, horizontal scaling |
| Client Library | JavaScript (vanilla) | No build step, browser-native WebSocket API |
| Load Testing | k6 | Modern, scriptable, WebSocket support |
| Monitoring | Prometheus + Grafana | Industry standard, rich metrics |

---

## Architectural Principles Applied

### KISS (Keep It Simple, Stupid)
- In-memory broadcast for MVP (no Redis until Phase 3)
- JSON over WebSocket (no custom protocol)
- Single background task (no complex scheduler)

### YAGNI (You Ain't Gonna Need It)
- No authentication for MVP (add JWT later if needed)
- No historical replay over WebSocket (use REST API)
- No bidirectional commands (WebSocket is push-only)

### Test-Driven Development
- 10 unit tests (T009)
- 7 integration tests (T010)
- Load tests with k6 (T014, T018, T022)
- Coverage target: 80%+

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| DuckDB blocks event loop | Medium | High | Use `asyncio.to_thread()` (T005) |
| Memory leak from disconnected clients | Low | High | Cleanup task + timeout (T003) |
| Redis single point of failure | Low | Medium | Fallback to in-memory (T020) |
| WebSocket incompatible with proxy | Medium | Medium | Document requirements, polling fallback |

---

## Next Steps

1. **Review specification**: Read `spec.md` thoroughly
2. **Understand tasks**: Review `tasks.md` task breakdown
3. **Set up environment**: Verify dependencies (FastAPI, websockets, Redis client)
4. **Start implementation**: Begin with T001 (ConnectionManager)
5. **Follow TDD**: Red → Green → Refactor for each task
6. **Test continuously**: `uv run pytest` after each task
7. **Deploy staging**: After Phase 1 complete (T017)
8. **Load test**: Validate with k6 (T018)
9. **Production rollout**: Gradual deployment (T019)

---

## Questions & Support

- **Technical questions**: See detailed sections in `spec.md`
- **Implementation guidance**: See TDD steps in `tasks.md`
- **Architecture clarification**: See diagrams in `ARCHITECTURE_DIAGRAM.md`
- **Troubleshooting**: Will be created as `docs/websocket_troubleshooting.md` (T025)

---

**Specification Status**: ✅ Complete and ready for development

**Estimated Timeline**:
- Week 1: MVP implementation (Phase 1)
- Week 2: Production deployment (Phase 2)
- Week 3-4: Scaling with Redis (Phase 3, optional)

**Total Effort**: 2-3 weeks for a single developer
