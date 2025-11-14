#!/bin/bash
# Setup script for daily volume_profile_daily cache updates
# This script provides instructions and templates for setting up a cron job

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_PATH="$PROJECT_DIR/scripts/create_volume_profile_cache.py"
LOG_DIR="/var/log/liquidationheatmap"
LOG_FILE="$LOG_DIR/cache-update.log"

echo "======================================"
echo "LiquidationHeatmap Cache Update Setup"
echo "======================================"
echo ""
echo "This script will help you set up automatic daily updates for the"
echo "volume_profile_daily cache table used by the OpenInterest model."
echo ""

# Check if script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "❌ ERROR: Cache creation script not found at:"
    echo "   $SCRIPT_PATH"
    exit 1
fi

echo "✅ Cache creation script found at:"
echo "   $SCRIPT_PATH"
echo ""

# Check UV installation
if ! command -v uv &> /dev/null; then
    echo "❌ ERROR: UV not found in PATH"
    echo "   Please install UV first: https://github.com/astral-sh/uv"
    exit 1
fi

echo "✅ UV found: $(which uv)"
echo ""

# Prepare log directory
echo "📁 Log file will be saved to:"
echo "   $LOG_FILE"
echo ""

if [ ! -d "$LOG_DIR" ]; then
    echo "⚠️  Log directory does not exist yet. Creating it requires sudo:"
    echo "   sudo mkdir -p $LOG_DIR"
    echo "   sudo chown $USER:$USER $LOG_DIR"
    echo ""
    read -p "Create log directory now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo mkdir -p "$LOG_DIR"
        sudo chown "$USER:$USER" "$LOG_DIR"
        echo "✅ Log directory created"
    else
        echo "⚠️  Skipping log directory creation. Update LOG_FILE path in cron entry."
    fi
else
    echo "✅ Log directory exists"
fi
echo ""

# Generate cron entry
CRON_ENTRY="# LiquidationHeatmap: Daily cache update (runs at 00:05 UTC)
5 0 * * * cd $PROJECT_DIR && uv run python scripts/create_volume_profile_cache.py >> $LOG_FILE 2>&1"

echo "======================================"
echo "CRON JOB SETUP INSTRUCTIONS"
echo "======================================"
echo ""
echo "1. Open your crontab:"
echo "   crontab -e"
echo ""
echo "2. Add this entry at the end:"
echo ""
echo "$CRON_ENTRY"
echo ""
echo "3. Save and exit the editor"
echo ""
echo "4. Verify the cron job was added:"
echo "   crontab -l | grep liquidation"
echo ""
echo "======================================"
echo "MANUAL TEST"
echo "======================================"
echo ""
echo "To test the cache update manually, run:"
echo "   cd $PROJECT_DIR"
echo "   uv run python scripts/create_volume_profile_cache.py"
echo ""
echo "Expected output:"
echo "   Creating volume_profile_daily table..."
echo "   ✅ Created volume_profile_daily with 7,345 rows (approx)"
echo ""
echo "======================================"
echo "MONITORING"
echo "======================================"
echo ""
echo "To monitor cache updates:"
echo "   tail -f $LOG_FILE"
echo ""
echo "To check last update time:"
echo "   ls -lh $LOG_FILE"
echo ""
echo "======================================"
echo "IMPORTANT NOTES"
echo "======================================"
echo ""
echo "• The cache update takes ~30 seconds"
echo "• No need to stop/restart the API server (DuckDB handles concurrent reads)"
echo "• The cron job runs at 00:05 UTC daily"
echo "• Logs are appended to $LOG_FILE"
echo "• Check logs regularly for any errors"
echo ""
echo "✅ Setup instructions complete!"
echo ""

# Offer to copy cron entry to clipboard (if xclip is available)
if command -v xclip &> /dev/null; then
    read -p "Copy cron entry to clipboard? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "$CRON_ENTRY" | xclip -selection clipboard
        echo "✅ Cron entry copied to clipboard!"
        echo "   Just paste it into your crontab with: crontab -e"
    fi
else
    echo "💡 TIP: Install xclip to enable clipboard copy: sudo apt install xclip"
fi

echo ""
echo "Done! 🎉"
