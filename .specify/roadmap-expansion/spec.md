# LiquidationHeatmap Expansion Roadmap

**Created**: 2025-12-28
**Status**: Draft
**Scope**: Post-validation expansion features (BTC validated at 77.8% hit rate)

---

## Executive Summary

LiquidationHeatmap has achieved **P0 validation milestone** with 77.8% hit rate on BTC/USDT using 4 years of historical data across 9 timeframes. This roadmap prioritizes expansion features by **ROI** (Return on Investment) and **technical risk**, following KISS/YAGNI principles.

**Current State**:
- ✅ BTC/USDT heatmap (4 years data)
- ✅ 9 timeframes (48h → 1y)
- ✅ FastAPI + DuckDB pipeline
- ✅ Validation pipeline (77.8% hit rate)
- ✅ Hyperliquid WebSocket tested (working)

**Investment to Date**: ~15 days development + 185GB database

**Next Phase Goal**: Maximize user value with minimal incremental effort

---

## Prioritization Framework

Features ranked by **Weighted Score** = (User Value × Technical Feasibility) / Effort

| Feature | User Value (1-10) | Feasibility (1-10) | Effort (days) | Weighted Score | Priority |
|---------|-------------------|-------------------|---------------|----------------|----------|
| ETH Symbol Support | 8 | 9 | 2-3 | **24** | **P1** |
| Real-time Streaming | 9 | 7 | 5-7 | **12.6** | **P2** |
| Exchange Aggregation | 7 | 6 | 7-10 | **4.2** | **P3** |
| Alert System | 6 | 8 | 3-4 | **12.8** | **P2b** |
| Historical Backtesting | 5 | 9 | 2-3 | **15** | **P2a** |
| Mobile App | 4 | 3 | 15-20 | **0.6** | **P5** |
| TradingView Plugin | 7 | 4 | 10-12 | **2.8** | **P4** |

**Priority Tiers**:
- **P1** (Ship Next): Critical mass features, low-hanging fruit
- **P2** (Ship Soon): High value, moderate complexity
- **P3** (Ship Later): Complex infrastructure, longer ROI
- **P4+** (Backlog): Low priority, evaluate quarterly

---

## P1 Features (Ship Next: 2-3 weeks)

### P1.1 - ETH/USDT Symbol Support

**Effort**: 2-3 days
**User Value**: 8/10 (2nd largest crypto asset)
**Technical Risk**: LOW (identical pipeline to BTC)

#### Rationale
- **Quick Win**: Reuse 100% of existing pipeline (DuckDB ingestion, liquidation models, clustering)
- **Market Coverage**: BTC + ETH = 60%+ of derivatives market volume
- **Data Availability**: ETH aggTrades readily available in Binance historical data
- **Validation**: Can immediately leverage existing 77.8% hit rate validation

#### User Stories

**User Story 1 - ETH Trader Access** (Priority: P1)
As an ETH futures trader, I want liquidation heatmaps for ETH/USDT so I can avoid liquidation cascades in Ethereum markets.

**Why this priority**: ETH is the 2nd largest crypto by market cap; traders need this data as much as BTC.

**Independent Test**: Can be tested by accessing `/liquidations/heatmap?symbol=ETHUSDT` and verifying data structure matches BTC output.

**Acceptance Scenarios**:
1. **Given** I select ETH/USDT symbol, **When** I request 24h heatmap, **Then** I receive ETH-specific liquidation levels with <5s latency
2. **Given** I compare ETH vs BTC heatmaps, **When** I toggle symbols, **Then** data updates without requiring page reload

**User Story 2 - Multi-Symbol Analysis** (Priority: P1)
As a portfolio manager, I want side-by-side BTC vs ETH liquidation zones to understand cross-asset correlation.

**Why this priority**: Professional traders manage multiple assets simultaneously.

**Independent Test**: Open two browser tabs with BTC and ETH heatmaps; verify both load independently.

**Acceptance Scenarios**:
1. **Given** BTC and ETH charts open, **When** liquidation event occurs, **Then** both charts update independently
2. **Given** time range selection, **When** I change to "7 days", **Then** both symbols reflect same time window

#### Implementation Tasks

**Phase 1: Data Ingestion** (Day 1)
- [ ] Ingest ETH historical aggTrades (same `ingest_aggtrades.py` script)
- [ ] Create `volume_profile_daily` cache for ETH
- [ ] Validate data quality (same thresholds as BTC)
- [ ] Estimated database size: +150GB (similar to BTC)

**Phase 2: Configuration** (Day 1-2)
- [ ] Add `config/tiers/ETHUSDT.yaml` (10 tiers, similar to BTC)
- [ ] Fetch ETH maintenance margin rates from Binance API
- [ ] Validate tier boundaries against Binance official docs
- [ ] Add ETH to symbol validation enum

**Phase 3: API Updates** (Day 2)
- [ ] Extend `/liquidations/heatmap` to accept `symbol` parameter
- [ ] Add symbol-specific cache keys (`ETHUSDT:...`)
- [ ] Update Pydantic models with symbol validation
- [ ] Add `/symbols` endpoint listing available symbols

**Phase 4: Frontend** (Day 2-3)
- [ ] Add symbol dropdown to all HTML pages
- [ ] Update charts to dynamically load symbol data
- [ ] Add symbol-specific color schemes (ETH = purple, BTC = orange)
- [ ] Test symbol switching UX

**Phase 5: Validation** (Day 3)
- [ ] Run price-level validation on ETH (expect similar 77% hit rate)
- [ ] Compare against Coinglass ETH heatmap
- [ ] Document any discrepancies vs BTC model performance

#### Success Criteria
- **SC-001**: ETH heatmap loads in <5s for 24h timeframe
- **SC-002**: Hit rate validation ≥70% (within 10% of BTC performance)
- **SC-003**: Symbol switching updates chart in <2s
- **SC-004**: Both symbols use <400GB total disk space

#### Dependencies
- None (fully independent of other features)

#### Risks & Mitigations
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| ETH tier configs differ significantly | Medium | Medium | Use Binance API to fetch live configs, not hardcode |
| ETH validation hit rate <60% | Low | High | Model should generalize; if fails, investigate ETH-specific factors |
| Disk space exhaustion (185GB + 150GB = 335GB) | Low | Medium | Monitor disk usage; consider monthly archival |

---

## P2 Features (Ship Soon: 4-8 weeks)

### P2.1 - Real-time Liquidation Streaming

**Effort**: 5-7 days
**User Value**: 9/10 (live market monitoring)
**Technical Risk**: MEDIUM (new WebSocket infrastructure)

#### Rationale
- **Killer Feature**: Real-time alerts >> historical analysis for active traders
- **Architecture Ready**: Redis pub/sub already planned in ARCHITECTURE.md
- **Data Source Proven**: Hyperliquid WebSocket validated and working
- **Revenue Potential**: Premium feature for subscription model

#### User Stories

**User Story 1 - Live Liquidation Alerts** (Priority: P1)
As a day trader, I want real-time notifications when liquidations occur near my positions so I can react to cascades.

**Why this priority**: Timely alerts can save traders from losses during cascade events.

**Independent Test**: Connect to WebSocket, trigger test liquidation event, verify alert received within 1 second.

**Acceptance Scenarios**:
1. **Given** I set alert at $95k, **When** $94.5k liquidation occurs, **Then** I receive alert within 1s
2. **Given** high volatility (>100 liq/min), **When** cascade starts, **Then** alerts don't flood (max 1 per 5s)

**User Story 2 - Heatmap Live Updates** (Priority: P2)
As a chart watcher, I want liquidation heatmap to update in real-time so I see market dynamics evolve.

**Why this priority**: Static heatmaps miss intraday position changes.

**Independent Test**: Open heatmap, connect to WebSocket, inject mock liquidation, verify chart updates.

**Acceptance Scenarios**:
1. **Given** heatmap open for 5 minutes, **When** 10 liquidations occur, **Then** density chart updates smoothly
2. **Given** network disconnection, **When** reconnected, **Then** missed data backfilled from cache

#### Implementation Tasks

**Phase 1: WebSocket Infrastructure** (Day 1-2)
- [ ] Add `websockets` dependency to `pyproject.toml`
- [ ] Create `src/streaming/liquidation_listener.py` (Binance + Hyperliquid)
- [ ] Implement reconnection logic with exponential backoff
- [ ] Add heartbeat/ping to detect dead connections
- [ ] Write integration tests for WebSocket stability

**Phase 2: Redis Pub/Sub** (Day 2-3)
- [ ] Add Redis to `docker-compose.yml` (optional deployment)
- [ ] Create `src/streaming/publisher.py` (publish liquidations to Redis channel)
- [ ] Create `src/streaming/subscriber.py` (subscribe to channel for API clients)
- [ ] Implement message schemas (Pydantic models)
- [ ] Add Redis health check to `/health` endpoint

**Phase 3: API Endpoints** (Day 3-4)
- [ ] Add `/ws/liquidations` WebSocket endpoint (FastAPI)
- [ ] Implement client authentication (optional API key)
- [ ] Add rate limiting (max 10 connections per IP)
- [ ] Create `/stream/status` endpoint (connection count, uptime)
- [ ] Document WebSocket protocol in `docs/api_guide.md`

**Phase 4: Frontend Integration** (Day 4-5)
- [ ] Add WebSocket client to `heatmap.html`
- [ ] Implement auto-reconnect on disconnect
- [ ] Add visual indicator (green = connected, red = disconnected)
- [ ] Create "Live" toggle switch (enable/disable streaming)
- [ ] Add notification sound for liquidation alerts (optional)

**Phase 5: Testing & Monitoring** (Day 5-7)
- [ ] Load test WebSocket (100 concurrent clients)
- [ ] Test failover scenarios (Redis crash, network partition)
- [ ] Add Prometheus metrics (message rate, latency)
- [ ] Create Grafana dashboard for stream monitoring
- [ ] Document deployment guide for Redis

#### Success Criteria
- **SC-001**: WebSocket delivers liquidations with <500ms latency
- **SC-002**: System handles 100 concurrent WebSocket clients
- **SC-003**: Automatic reconnection succeeds within 10s of disconnect
- **SC-004**: Zero message loss during Redis failover (buffered)

#### Dependencies
- Redis (optional - can fallback to in-memory pub/sub for single-server)
- FastAPI WebSocket support (already included)

#### Risks & Mitigations
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Binance WebSocket rate limits | Medium | High | Implement connection pooling, respect rate limits |
| Redis becomes SPOF | Medium | Medium | Use Redis Sentinel for HA, or implement fallback |
| WebSocket scaling challenges | Low | Medium | Start with single server; migrate to Redis when needed |

---

### P2.2 - Historical Backtesting Interface

**Effort**: 2-3 days
**User Value**: 5/10 (for quants/researchers)
**Technical Risk**: LOW (read-only database queries)

#### Rationale
- **Validation Extension**: Leverage existing 77.8% hit rate validation logic
- **Research Tool**: Enable users to test liquidation zone strategies
- **Academic Credibility**: Publish backtesting methodology for peer review
- **Low Complexity**: 90% code reuse from validation pipeline

#### User Stories

**User Story 1 - Strategy Backtesting** (Priority: P1)
As a quant researcher, I want to backtest a trading strategy that enters positions when price approaches liquidation clusters.

**Why this priority**: Enables systematic strategy development beyond manual chart analysis.

**Independent Test**: Upload strategy parameters (entry rule, exit rule), run backtest on 2024 data, receive P&L report.

**Acceptance Scenarios**:
1. **Given** I define "buy when price within 2% of liquidation cluster", **When** I run backtest, **Then** I receive trade-by-trade results
2. **Given** 365-day backtest, **When** I submit request, **Then** results return in <30 seconds

**User Story 2 - Model Performance Analysis** (Priority: P2)
As a developer, I want to compare Binance Standard vs Ensemble model performance across different timeframes.

**Why this priority**: Helps optimize model selection for production.

**Independent Test**: Run backtest with `model=binance_standard` vs `model=ensemble`, compare precision/recall.

**Acceptance Scenarios**:
1. **Given** two models selected, **When** backtest completes, **Then** side-by-side comparison chart displayed
2. **Given** results, **When** I export CSV, **Then** all trade timestamps and P&L included

#### Implementation Tasks

**Phase 1: Backtest Engine** (Day 1)
- [ ] Extract backtest logic from `validate_vs_coinglass.py`
- [ ] Create `src/backtesting/engine.py` with configurable strategy interface
- [ ] Support custom entry/exit rules via Python expressions
- [ ] Add P&L calculator with transaction costs

**Phase 2: API Endpoint** (Day 1-2)
- [ ] Add `/backtest/run` endpoint (POST with strategy params)
- [ ] Implement async processing for long-running backtests
- [ ] Add job queue (or simple in-memory queue for MVP)
- [ ] Create `/backtest/results/{job_id}` endpoint

**Phase 3: Frontend** (Day 2-3)
- [ ] Create `backtest.html` with strategy builder form
- [ ] Add date range picker, model selector
- [ ] Display equity curve (Plotly.js line chart)
- [ ] Show statistics table (total return, Sharpe ratio, max drawdown)
- [ ] Add CSV export button

**Phase 4: Documentation** (Day 3)
- [ ] Write `docs/BACKTESTING.md` guide
- [ ] Provide example strategies (mean reversion, momentum)
- [ ] Document limitations (no slippage model, simplified fills)
- [ ] Add disclaimers (not financial advice)

#### Success Criteria
- **SC-001**: 365-day backtest completes in <60s
- **SC-002**: Results match manual validation within 1% error margin
- **SC-003**: Users can define custom strategies without code changes
- **SC-004**: CSV export includes all trades + metadata

#### Dependencies
- Existing validation pipeline
- DuckDB historical data

---

### P2.3 - Liquidation Zone Alerts

**Effort**: 3-4 days
**User Value**: 6/10 (convenience for traders)
**Technical Risk**: LOW (simple threshold monitoring)

#### Rationale
- **User Retention**: Email/SMS alerts keep users engaged off-platform
- **Mobile-First**: Addresses mobile use case without full app
- **Revenue Potential**: Premium alerts tier (unlimited alerts for subscribers)
- **Simple MVP**: Price crosses threshold → send notification

#### User Stories

**User Story 1 - Price Alert Creation** (Priority: P1)
As a swing trader, I want to set an alert when BTC price crosses above/below a liquidation cluster so I can enter positions.

**Why this priority**: Traders can't watch charts 24/7; alerts are essential.

**Independent Test**: Create alert at $95k, manually trigger price event, verify email received.

**Acceptance Scenarios**:
1. **Given** I set alert "BTC above $95k liquidation zone", **When** price hits $95.5k, **Then** I receive email within 1 minute
2. **Given** 5 active alerts, **When** I view dashboard, **Then** all alerts shown with status (active/triggered)

**User Story 2 - Alert Management** (Priority: P2)
As a user, I want to edit/delete alerts so I can adjust to changing market conditions.

**Why this priority**: Market moves fast; alerts become stale quickly.

**Independent Test**: Create alert, edit price threshold, verify new threshold takes effect.

**Acceptance Scenarios**:
1. **Given** I edit alert from $95k to $93k, **When** price hits $94k, **Then** no alert fires
2. **Given** I delete alert, **When** price crosses threshold, **Then** no notification sent

#### Implementation Tasks

**Phase 1: Alert Storage** (Day 1)
- [ ] Create `alerts` table in DuckDB (user_id, symbol, price_level, direction, status)
- [ ] Add CRUD endpoints (`POST /alerts`, `GET /alerts`, `DELETE /alerts/{id}`)
- [ ] Implement alert validation (max 10 per user for free tier)
- [ ] Add user authentication (simple API key for MVP)

**Phase 2: Monitoring Service** (Day 2)
- [ ] Create `src/alerts/monitor.py` background service
- [ ] Poll current price every 10s (Binance API)
- [ ] Check active alerts against current price
- [ ] Trigger notifications when conditions met
- [ ] Update alert status to `triggered`

**Phase 3: Notification Channels** (Day 3)
- [ ] Implement email notifications (SMTP, SendGrid, or SES)
- [ ] Add webhook support (POST to user-provided URL)
- [ ] Optional: Add Telegram bot integration
- [ ] Create notification templates (HTML + plain text)

**Phase 4: Frontend** (Day 3-4)
- [ ] Add "Create Alert" button to heatmap page
- [ ] Modal form: symbol, price, direction (above/below)
- [ ] Alert list table with edit/delete actions
- [ ] Visual indicators on chart (dashed line at alert price)

#### Success Criteria
- **SC-001**: Alerts fire within 60s of price crossing threshold
- **SC-002**: 99% email delivery rate (use reputable SMTP provider)
- **SC-003**: Users can manage unlimited alerts (no hard cap)
- **SC-004**: Alert monitoring service uptime >99.5%

#### Dependencies
- User authentication system (can be simple API key for MVP)
- SMTP server or email service (SendGrid free tier = 100 emails/day)

---

## P3 Features (Ship Later: 2-3 months)

### P3.1 - Multi-Exchange Aggregation

**Effort**: 7-10 days
**User Value**: 7/10 (complete market view)
**Technical Risk**: MEDIUM-HIGH (complex data normalization)

#### Rationale
- **Market Completeness**: Binance alone ≠ full picture (Bybit, OKX, Hyperliquid all significant)
- **Arbitrage Opportunities**: Cross-exchange liquidation spreads exploitable
- **Competitive Moat**: Few competitors aggregate >2 exchanges
- **Technical Challenge**: Each exchange has different data formats, APIs, and liquidation rules

#### User Stories

**User Story 1 - Unified Heatmap** (Priority: P1)
As an institutional trader, I want a single heatmap showing liquidations across Binance, Bybit, and OKX so I understand total market risk.

**Why this priority**: Large positions impact multiple exchanges; need holistic view.

**Independent Test**: Request `/liquidations/heatmap?symbol=BTCUSDT&exchanges=binance,bybit,okx`, verify aggregated response.

**Acceptance Scenarios**:
1. **Given** I select "All Exchanges", **When** heatmap loads, **Then** I see combined liquidation density
2. **Given** exchange filter, **When** I toggle "Binance only", **Then** chart updates to show single exchange

**User Story 2 - Exchange Comparison** (Priority: P2)
As a market analyst, I want to compare liquidation levels across exchanges to identify arbitrage opportunities.

**Why this priority**: Enables exchange spread trading strategies.

**Independent Test**: Open comparison view, verify side-by-side charts for each exchange.

**Acceptance Scenarios**:
1. **Given** BTC at $95k on Binance, $95.2k on Bybit, **When** I view comparison, **Then** price discrepancy highlighted
2. **Given** liquidation cluster at $94k Binance, $94.5k Bybit, **When** cascade occurs, **Then** both clusters shown

#### Exchange Roadmap

**Phase 1: Bybit Integration** (Day 1-3)
- **Data Source**: Bybit historical API (similar to Binance)
- **Differences**:
  - Different tier structure (8 tiers vs 10 for Binance)
  - Unified margin system (cross vs isolated)
  - WebSocket format differs (already tested, working)
- **Tasks**:
  - [ ] Create `config/tiers/BYBIT_BTCUSDT.yaml`
  - [ ] Add Bybit API client (`src/exchanges/bybit.py`)
  - [ ] Implement Bybit-specific liquidation formula
  - [ ] Ingest Bybit aggTrades (if available) or use liquidation stream only
  - [ ] Add `exchange` column to database schema

**Phase 2: Hyperliquid Integration** (Day 3-5)
- **Data Source**: WebSocket only (no historical API)
- **Differences**:
  - Decentralized exchange (no tier system)
  - Real-time only (no 4-year historical data like Binance)
  - Different margin model (portfolio margin)
- **Tasks**:
  - [ ] Extend `collect_liquidations.py` to run continuously
  - [ ] Store Hyperliquid liquidations in separate table
  - [ ] Create conversion layer (Hyperliquid → common schema)
  - [ ] Add Hyperliquid to frontend exchange selector

**Phase 3: OKX Integration** (Day 5-7)
- **Data Source**: OKX API (to be tested)
- **Differences**:
  - Portfolio margin system (complex cross-collateral)
  - Different leverage limits (up to 125x)
  - May require separate WebSocket connection
- **Tasks**:
  - [ ] Test OKX WebSocket stability
  - [ ] Implement OKX liquidation formula
  - [ ] Add OKX tier configuration
  - [ ] Validate OKX data quality

**Phase 4: Aggregation Logic** (Day 7-9)
- [ ] Create exchange normalization layer (`src/exchanges/normalizer.py`)
- [ ] Implement weighted aggregation (by exchange volume)
- [ ] Add exchange-specific color coding in charts
- [ ] Create `/exchanges` endpoint listing supported exchanges
- [ ] Add exchange metadata (uptime, last update timestamp)

**Phase 5: Testing & Validation** (Day 9-10)
- [ ] Run price-level validation per exchange
- [ ] Compare aggregated heatmap vs Coinglass
- [ ] Test failover scenarios (one exchange down)
- [ ] Load test multi-exchange WebSocket connections
- [ ] Document exchange-specific quirks

#### Success Criteria
- **SC-001**: Aggregate heatmap loads in <7s (3 exchanges)
- **SC-002**: Each exchange validated at ≥70% hit rate individually
- **SC-003**: Exchange failures don't crash entire system (graceful degradation)
- **SC-004**: Cross-exchange price discrepancies <1% (sanity check)

#### Dependencies
- Exchange API access (free tier sufficient for MVP)
- Multi-exchange WebSocket infrastructure
- Extended database schema (`exchange` column)

#### Risks & Mitigations
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Exchange APIs unstable | High | Medium | Implement per-exchange health checks, fallback to cached data |
| Data normalization errors | Medium | High | Rigorous testing, schema validation per exchange |
| One exchange dominates volume (e.g., 90% Binance) | Medium | Low | Weight by volume, but still show all exchanges |
| Licensing issues (exchange ToS) | Low | High | Review ToS, use publicly available data only |

---

## P4+ Features (Backlog)

### P4.1 - TradingView Plugin

**Effort**: 10-12 days
**User Value**: 7/10 (reach TradingView's 30M+ users)
**Technical Risk**: MEDIUM (TradingView API learning curve)

**Why Lower Priority**:
- Requires TradingView Pro account ($15/mo minimum)
- Plugin approval process (2-4 weeks review)
- Competes with existing liquidation heatmap indicators
- Better to build standalone credibility first

**User Story**:
As a TradingView user, I want liquidation heatmap overlay on my BTC chart so I don't need to switch platforms.

**Acceptance Criteria**:
- Plugin approved in TradingView marketplace
- Overlay renders liquidation zones as horizontal lines
- Real-time updates via webhook integration

**Defer Until**: After P1-P3 complete, user base >1000 DAU

---

### P5.1 - Mobile App (iOS/Android)

**Effort**: 15-20 days
**User Value**: 4/10 (mobile web sufficient for MVP)
**Technical Risk**: HIGH (new platform, app store approval)

**Why Lowest Priority**:
- Mobile web already works (responsive Plotly.js)
- App stores have approval friction
- Push notifications can be done via PWA (Progressive Web App)
- Maintenance burden (2 codebases)

**User Story**:
As a mobile-first trader, I want a native iOS app so I get push notifications for liquidation alerts.

**Acceptance Criteria**:
- App approved in App Store + Google Play
- Push notifications <1s latency
- Offline mode for cached heatmaps

**Defer Until**: Annual review if DAU >5000 and mobile web usage >50%

---

## Implementation Sequence (Gantt Estimate)

```
Week 1-2:    P1.1 - ETH Symbol Support ████████ (3d)
Week 3-4:    P2.2 - Historical Backtesting ████ (3d)
Week 4-5:    P2.3 - Alert System ██████ (4d)
Week 6-8:    P2.1 - Real-time Streaming ██████████████ (7d)
Week 9-12:   P3.1 - Multi-Exchange (Bybit) ████████████████████ (10d)
Week 13+:    P4+ features (evaluate based on metrics)
```

**Total Estimated Effort**: 27 days (~6 weeks with buffer)

**Parallelization Opportunities**:
- ETH + Backtesting can run in parallel (different developers)
- Alerts can start while Real-time Streaming in progress (shared WebSocket code)

---

## Success Metrics & KPIs

### P1 Success Metrics (ETH Launch)
- **Adoption**: ≥30% of users toggle to ETH within first week
- **Performance**: ETH hit rate ≥70% (within 10% of BTC)
- **Engagement**: Average session time increases by ≥15%

### P2 Success Metrics (Streaming + Alerts)
- **Streaming**: ≥50 concurrent WebSocket connections by week 4
- **Alerts**: ≥100 alerts created in first month
- **Retention**: Day-7 retention increases by ≥20%

### P3 Success Metrics (Multi-Exchange)
- **Coverage**: Binance + Bybit + Hyperliquid = 70%+ of derivatives volume
- **Accuracy**: Aggregated heatmap correlation vs Coinglass ≥0.75
- **Differentiation**: Feature parity with top 2 competitors

### Overall North Star Metrics
- **DAU** (Daily Active Users): Target 500 by end of P2, 2000 by end of P3
- **API Uptime**: ≥99.5% (measured monthly)
- **User Satisfaction**: NPS ≥40 (survey after 1 month usage)

---

## Resource Requirements

### Infrastructure
- **Compute**: Current 4-core VPS sufficient through P2; scale to 8-core for P3
- **Storage**:
  - P1: +150GB (ETH data)
  - P2: +50GB (alert logs, stream buffers)
  - P3: +300GB (Bybit + OKX data)
  - **Total**: ~700GB by end of P3 (consider S3 archival)
- **Memory**: 16GB RAM sufficient; upgrade to 32GB for P3 (multi-exchange)
- **Redis**: Optional for P2; required for P3 (shared cache)

### External Services
- **Email**: SendGrid free tier (100/day) → upgrade to $20/mo (40k/day) when alerts >100/day
- **Monitoring**: Prometheus + Grafana (self-hosted) or Datadog free tier
- **CDN**: Optional for P3 (CloudFlare free tier sufficient)

### Estimated Costs
- **P1**: $0 (same infrastructure)
- **P2**: ~$30/mo (SendGrid + Redis hosting)
- **P3**: ~$100/mo (larger VPS + bandwidth)

---

## Decision Gates

### Gate 1: After P1.1 (ETH Launch)
**Evaluate**:
- ETH hit rate ≥70%? → Proceed to P2
- ETH hit rate <60%? → Investigate model generalization issues before expansion
- User adoption <10%? → Reconsider multi-symbol priority

**Checkpoint**: Week 2

### Gate 2: After P2 Complete (Streaming + Alerts)
**Evaluate**:
- WebSocket stability ≥99%? → Proceed to P3
- Alert email delivery <95%? → Fix infrastructure before exchange expansion
- User engagement metrics flat? → Pivot to different features (e.g., TradingView earlier)

**Checkpoint**: Week 8

### Gate 3: After P3.1 (Bybit Integration)
**Evaluate**:
- Bybit data quality acceptable? → Add OKX + Hyperliquid
- Aggregation complexity too high? → Reassess multi-exchange ROI
- Infrastructure costs >$200/mo? → Optimize or pause expansion

**Checkpoint**: Week 12

---

## Risks & Contingencies

### Technical Risks
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| ETH model accuracy <60% | High | Low | Deep-dive into tier differences; may need ETH-specific tuning |
| WebSocket infrastructure unreliable | High | Medium | Use managed Redis (AWS ElastiCache); implement circuit breakers |
| Multi-exchange data conflicts | Medium | High | Implement data quality checks; flag discrepancies in UI |
| Database growth unsustainable (>1TB) | Medium | Medium | Archive old data to S3; keep only 90 days hot in DuckDB |

### Business Risks
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Competitors launch similar features | Medium | High | Focus on execution speed; differentiate on accuracy (77.8% hit rate) |
| Exchange APIs change/deprecate | High | Low | Monitor exchange announcements; maintain fallback data sources |
| User growth slower than expected | Low | Medium | Double down on marketing; consider freemium → premium conversion |
| Regulatory restrictions (GDPR, CCPA) | Medium | Low | Implement privacy controls early; no PII storage in MVP |

### Contingency Plans
- **If P1 fails validation**: Delay P2/P3; focus on improving BTC model accuracy to 85%+
- **If infrastructure costs exceed $200/mo**: Pause P3; optimize P1+P2 first
- **If user retention <20%**: Conduct user interviews; pivot roadmap based on feedback

---

## Open Questions & Clarifications Needed

### Technical
1. **ETH Tier Configuration**: Are Binance ETH tiers identical to BTC, or different? → Need API verification
2. **Bybit Historical Data**: Does Bybit provide aggTrades CSV like Binance? → Test API availability
3. **Hyperliquid Limitations**: Real-time only means no historical validation - acceptable trade-off?
4. **Redis HA**: Single Redis instance acceptable for P2, or need Sentinel from day 1?

### Business
1. **Monetization**: Free tier limits? (e.g., 5 alerts vs unlimited for paid)
2. **Competitive Analysis**: Who are top 3 competitors for each feature?
3. **User Personas**: Are institutional traders or retail traders the primary target?
4. **Marketing**: How to announce ETH launch? (Twitter, email, in-app banner?)

### Legal
1. **Exchange ToS**: Do Binance/Bybit/OKX allow commercial use of API data?
2. **Data Licensing**: Does Coinglass validation violate any IP?
3. **Disclaimer**: What legal disclaimers needed for backtest results?

---

## Appendix: Feature Comparison Matrix

| Feature | Coinglass | LiquidationHeatmap | Competitive Advantage |
|---------|-----------|-------------------|----------------------|
| BTC Heatmap | ✅ | ✅ | Parity |
| ETH Heatmap | ✅ | 🔄 P1 | Parity (after P1) |
| Real-time Streaming | ✅ | 🔄 P2 | Parity (after P2) |
| Multi-exchange | ✅ (4+) | 🔄 P3 (3) | Behind (but catching up) |
| Historical Backtesting | ❌ | 🔄 P2 | **Differentiation** |
| Validated Accuracy (77.8%) | ❌ | ✅ | **Differentiation** |
| Open Source | ❌ | ✅ (potential) | **Differentiation** |
| API Access | 💰 Paid | ✅ Free (rate-limited) | **Differentiation** |
| Mobile App | ✅ | 🔄 P5 | Behind |
| TradingView Plugin | ✅ | 🔄 P4 | Behind |

**Key Insight**: Compete on accuracy + openness, not feature count

---

## Revision History

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2025-12-28 | 1.0 | Initial roadmap draft | Claude (Opus 4.5) |

---

**Next Steps**:
1. Review roadmap with stakeholders
2. Finalize P1.1 (ETH) start date
3. Set up project tracking (GitHub Projects or Linear)
4. Create detailed task breakdown for P1.1 using SpecKit `/tasks`
