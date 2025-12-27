#!/bin/sh
# N8N wrapper script for klines DuckDB ingest
# Usage: ./n8n_klines_wrapper.sh START_DATE END_DATE MODE
# Ingests klines (5m, 15m) for BTCUSDT and ETHUSDT

START_DATE="$1"
END_DATE="$2"
MODE="$3"

cd /workspace/1TB/LiquidationHeatmap

echo ""
echo "=========================================="
echo "📊 Klines Ingestion Starting"
echo "=========================================="
echo "Date range: $START_DATE → $END_DATE"
echo "Mode: $MODE"
echo ""

# Track overall status
KLINES_5M_BTC=0
KLINES_5M_ETH=0
KLINES_15M_BTC=0
KLINES_15M_ETH=0

# Use python3 directly (N8N container environment)
PYTHON_CMD="python3"

echo "[1/4] Ingesting BTCUSDT 5m klines..."
$PYTHON_CMD scripts/ingest_klines_15m.py \
    --symbol BTCUSDT \
    --start-date "$START_DATE" \
    --end-date "$END_DATE" \
    --interval 5m \
    --data-dir /workspace/3TB-WDC/binance-history-data-downloader/data
KLINES_5M_BTC=$?

echo ""
echo "[2/4] Ingesting ETHUSDT 5m klines..."
$PYTHON_CMD scripts/ingest_klines_15m.py \
    --symbol ETHUSDT \
    --start-date "$START_DATE" \
    --end-date "$END_DATE" \
    --interval 5m \
    --data-dir /workspace/3TB-WDC/binance-history-data-downloader/data
KLINES_5M_ETH=$?

echo ""
echo "[3/4] Ingesting BTCUSDT 15m klines..."
$UV_CMD scripts/ingest_klines_15m.py \
    --symbol BTCUSDT \
    --start-date "$START_DATE" \
    --end-date "$END_DATE" \
    --interval 15m \
    --data-dir /workspace/3TB-WDC/binance-history-data-downloader/data
KLINES_15M_BTC=$?

echo ""
echo "[4/4] Ingesting ETHUSDT 15m klines..."
$UV_CMD scripts/ingest_klines_15m.py \
    --symbol ETHUSDT \
    --start-date "$START_DATE" \
    --end-date "$END_DATE" \
    --interval 15m \
    --data-dir /workspace/3TB-WDC/binance-history-data-downloader/data
KLINES_15M_ETH=$?

echo ""
echo "=========================================="
echo "📈 Klines Ingestion Summary"
echo "=========================================="
FAILED=0

if [ $KLINES_5M_BTC -eq 0 ]; then
    echo "✅ BTCUSDT 5m: Success"
else
    echo "❌ BTCUSDT 5m: Failed"
    FAILED=$((FAILED + 1))
fi

if [ $KLINES_5M_ETH -eq 0 ]; then
    echo "✅ ETHUSDT 5m: Success"
else
    echo "❌ ETHUSDT 5m: Failed"
    FAILED=$((FAILED + 1))
fi

if [ $KLINES_15M_BTC -eq 0 ]; then
    echo "✅ BTCUSDT 15m: Success"
else
    echo "❌ BTCUSDT 15m: Failed"
    FAILED=$((FAILED + 1))
fi

if [ $KLINES_15M_ETH -eq 0 ]; then
    echo "✅ ETHUSDT 15m: Success"
else
    echo "❌ ETHUSDT 15m: Failed"
    FAILED=$((FAILED + 1))
fi

if [ $FAILED -gt 0 ]; then
    echo ""
    echo "⚠️ $FAILED task(s) failed"
    exit 1
fi

echo ""
echo "✅ Klines ingestion complete!"
