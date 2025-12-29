# Implementation Plan: Real-time WebSocket Streaming

**Branch**: `011-realtime-streaming` | **Date**: 2025-12-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/011-realtime-streaming/spec.md`

## Summary

Add real-time WebSocket streaming to push heatmap updates to connected clients without polling. Uses FastAPI's native WebSocket support with in-memory broadcast (MVP) and optional Redis pub/sub for horizontal scaling.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI (existing), websockets (existing), asyncio (stdlib)
**Storage**: In-memory dict for connections; Redis pub/sub for multi-server (Phase 3)
**Testing**: pytest + pytest-asyncio (existing)
**Target Platform**: Linux server (Docker-ready)
**Project Type**: Single project (backend API extension + frontend client)
**Performance Goals**: <500ms p95 latency, 1000+ concurrent connections per server
**Constraints**: <2GB memory per server, no polling fallback during active WebSocket
**Scale/Scope**: 1000 concurrent clients (MVP), 2000+ with Redis (Phase 3)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| **Mathematical Correctness** | N/A | No financial calculations (streaming only) |
| **Test-Driven Development** | MUST | All tasks include TDD steps (RED→GREEN→REFACTOR) |
| **Exchange Compatibility** | MUST | Reuses existing heatmap calculation logic |
| **Performance Efficiency** | SHOULD | <500ms p95 latency target, load tests planned (T056, T057) |
| **Data Integrity** | N/A | Read-only streaming, no data modification |
| **Graceful Degradation** | SHOULD | Slow consumer handling (T042-T049), polling fallback (T051) |
| **Progressive Enhancement** | SHOULD | 8-phase rollout: Setup → MVP → Production → Redis scaling |
| **Documentation Completeness** | MUST | API docs (T060), architecture (T061), troubleshooting (T062) |

**All gates pass** - No violations requiring justification.

## Project Structure

### Documentation (this feature)

```
specs/011-realtime-streaming/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (WebSocket message schemas)
├── spec.md              # Feature specification
├── tasks.md             # Implementation tasks (79 tasks)
├── ARCHITECTURE_DIAGRAM.md
├── README.md
└── SUMMARY.md
```

### Source Code (repository root)

```
src/liquidationheatmap/
├── api/
│   ├── main.py              # Edit: Add WS endpoint, startup/shutdown hooks
│   ├── websocket.py         # NEW: ConnectionManager class
│   ├── websocket_background.py  # NEW: Background update generator
│   └── redis_pubsub.py      # NEW (Phase 3): Redis pub/sub integration
└── streaming/
    └── __init__.py          # Existing (may extend)

frontend/
├── js/
│   └── websocket-client.js  # NEW: JavaScript WS client library
└── coinglass_heatmap.html   # Edit: Integrate WS client

tests/
├── test_ws/
│   ├── test_connection_manager.py  # NEW: Unit tests
│   ├── test_update_generator.py    # NEW: Background task tests
│   └── test_snapshot_helper.py     # NEW: Snapshot helper tests
├── integration/
│   ├── test_ws_endpoint.py         # NEW: E2E WebSocket tests
│   └── test_ws_lifecycle.py        # NEW: Startup/shutdown tests
└── load/
    └── ws_load_test.js             # NEW: k6 load test script
```

**Structure Decision**: Single project extension - adds WebSocket layer to existing FastAPI API without new packages or major reorganization.

## Complexity Tracking

*No violations requiring justification - design follows KISS principles:*

- In-memory broadcast for MVP (no Redis dependency initially)
- Re-uses existing heatmap calculation logic
- Standard WebSocket protocol (JSON messages)
- Progressive enhancement to Redis only when multi-server needed

## Phase Summary

| Phase | Description | Tasks | Duration |
|-------|-------------|-------|----------|
| 1-2 | Setup + Foundational | T001-T009 | ~1 day |
| 3 | US1 MVP (Single-server) | T010-T032 | ~5 days |
| 4 | US2 Multi-Symbol | T033-T041 | ~2 days |
| 5 | US3 Graceful Degradation | T042-T052 | ~2 days |
| 6 | Production Readiness | T053-T059 | ~2 days |
| 7 | Documentation | T060-T065 | ~1 day |
| 8 | Redis Scaling (Optional) | T066-T079 | ~3 days |

**Total**: 79 tasks, ~16 working days (excluding optional Phase 8)

## Key Design Decisions

1. **In-memory first**: No Redis for MVP - simpler deployment, faster iteration
2. **Backpressure via timeout**: 1s send timeout, warn slow consumers, don't block fast ones
3. **Symbol-based subscriptions**: Reduce bandwidth, clients subscribe to what they need
4. **Hash-based change detection**: Only broadcast when data actually changes
5. **Polling fallback**: Frontend auto-falls back after 3 WebSocket failures

## References

- [FastAPI WebSocket Docs](https://fastapi.tiangolo.com/advanced/websockets/)
- [Redis Pub/Sub Pattern](https://redis.io/docs/manual/pubsub/)
- [k6 WebSocket Testing](https://k6.io/docs/using-k6/protocols/websockets/)
