#!/bin/sh
# N8N wrapper script for DuckDB ingest
# Usage: ./n8n_ingest_wrapper.sh START_DATE END_DATE MODE
# Handles lock cleanup and API coordination

START_DATE="$1"
END_DATE="$2"
MODE="$3"

PROJECT_DIR="/workspace/1TB/LiquidationHeatmap"
DB_PATH="${PROJECT_DIR}/data/processed/liquidations.duckdb"
API_URL="http://host.docker.internal:8765"
MAX_RETRIES=3
RETRY_DELAY=5

cd "$PROJECT_DIR"

echo ""
echo "=========================================="
echo "DuckDB AggTrades Ingestion Wrapper"
echo "=========================================="
echo "Date range: $START_DATE -> $END_DATE"
echo "Mode: $MODE"
echo ""

# Step 1: Notify API to release connections
echo "[Step 1/4] Preparing database for ingestion..."
PREP_RESULT=$(curl -s -X POST "${API_URL}/api/v1/prepare-for-ingestion" 2>/dev/null || echo '{"status":"api_unavailable"}')
echo "API preparation: ${PREP_RESULT}"

# Step 2: Clean any stale locks
echo ""
echo "[Step 2/4] Cleaning stale locks..."
python3 "${PROJECT_DIR}/scripts/cleanup_duckdb_locks.py" "${DB_PATH}" || true

# Step 3: Wait for database to be available (existing retry logic)
echo ""
echo "[Step 3/4] Checking database availability..."

# Function to check if database is locked
is_db_locked() {
    pgrep -f "ingest_full_history_n8n.py.*$DB_PATH" > /dev/null
    return $?
}

attempt=1
while [ $attempt -le $MAX_RETRIES ]; do
    if is_db_locked; then
        if [ $attempt -eq $MAX_RETRIES ]; then
            echo "ERROR: Database is locked by another process after $MAX_RETRIES attempts"
            ps aux | grep -E "ingest_full_history_n8n.py.*$DB_PATH" | grep -v grep
            exit 1
        fi
        echo "Database locked, waiting ${RETRY_DELAY}s (attempt $attempt/$MAX_RETRIES)..."
        sleep $RETRY_DELAY
        attempt=$((attempt + 1))
    else
        break
    fi
done

echo "Database available, starting ingestion..."

# Track overall status
BTCUSDT_STATUS=0
ETHUSDT_STATUS=0

if [ "$MODE" = "PRODUCTION" ]; then
    echo ""
    echo "Ingesting BTCUSDT aggTrades..."
    python3 ingest_full_history_n8n.py \
        --symbol BTCUSDT \
        --data-dir /workspace/3TB-WDC/binance-history-data-downloader/data \
        --db /workspace/1TB/LiquidationHeatmap/data/processed/liquidations.duckdb \
        --mode full \
        --start-date "$START_DATE" \
        --end-date "$END_DATE" \
        --throttle-ms 200
    BTCUSDT_STATUS=$?

    echo ""
    echo "Ingesting ETHUSDT aggTrades..."
    python3 ingest_full_history_n8n.py \
        --symbol ETHUSDT \
        --data-dir /workspace/3TB-WDC/binance-history-data-downloader/data \
        --db /workspace/1TB/LiquidationHeatmap/data/processed/liquidations.duckdb \
        --mode full \
        --start-date "$START_DATE" \
        --end-date "$END_DATE" \
        --throttle-ms 200
    ETHUSDT_STATUS=$?
else
    echo ""
    echo "Ingesting BTCUSDT aggTrades (auto mode)..."
    python3 ingest_full_history_n8n.py \
        --symbol BTCUSDT \
        --data-dir /workspace/3TB-WDC/binance-history-data-downloader/data \
        --db /workspace/1TB/LiquidationHeatmap/data/processed/liquidations.duckdb \
        --mode auto \
        --throttle-ms 200
    BTCUSDT_STATUS=$?

    echo ""
    echo "Ingesting ETHUSDT aggTrades (auto mode)..."
    python3 ingest_full_history_n8n.py \
        --symbol ETHUSDT \
        --data-dir /workspace/3TB-WDC/binance-history-data-downloader/data \
        --db /workspace/1TB/LiquidationHeatmap/data/processed/liquidations.duckdb \
        --mode auto \
        --throttle-ms 200
    ETHUSDT_STATUS=$?
fi

# Step 4: Notify API to refresh connections
echo ""
echo "[Step 4/4] Refreshing API connections..."
REFRESH_RESULT=$(curl -s -X POST "${API_URL}/api/v1/refresh-connections" 2>/dev/null || echo '{"status":"api_unavailable"}')
echo "API refresh: ${REFRESH_RESULT}"

echo ""
echo "=========================================="
echo "AggTrades Ingestion Summary"
echo "=========================================="
if [ $BTCUSDT_STATUS -eq 0 ]; then
    echo "BTCUSDT: Success"
else
    echo "BTCUSDT: Failed (exit code: $BTCUSDT_STATUS)"
fi
if [ $ETHUSDT_STATUS -eq 0 ]; then
    echo "ETHUSDT: Success"
else
    echo "ETHUSDT: Failed (exit code: $ETHUSDT_STATUS)"
fi

# Exit with error if any symbol failed
if [ $BTCUSDT_STATUS -ne 0 ] || [ $ETHUSDT_STATUS -ne 0 ]; then
    exit 1
fi

echo ""
echo "Orchestration complete!"
