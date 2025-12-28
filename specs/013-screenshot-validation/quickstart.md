# Quick Start: Screenshot Validation Pipeline

**Feature**: 013-screenshot-validation
**Time to first result**: ~5 minutes

## Prerequisites

### 1. Install System Dependencies

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-eng

# Verify installation
tesseract --version
# Expected: tesseract 5.x.x
```

### 2. Install Python Dependencies

```bash
cd /media/sam/1TB/LiquidationHeatmap

# Add validation dependencies
uv add pytesseract easyocr pillow opencv-python httpx

# Or install from optional group
uv sync --group validation
```

### 3. Verify Screenshot Access

```bash
# Check screenshots exist
ls /media/sam/1TB/N8N_dev/screenshots/ | head -5

# Expected output:
# coinglass_btc_m1_1month_20251030_145708.png
# coinglass_btc_m1_1month_20251030_160122.png
# ...

# Count total screenshots
ls /media/sam/1TB/N8N_dev/screenshots/*.png | wc -l
# Expected: 3151
```

### 4. Start API Server

```bash
# In a separate terminal
cd /media/sam/1TB/LiquidationHeatmap
uv run python -m src.liquidationheatmap.api.main

# Verify API is running
curl http://localhost:8000/health
# Expected: {"status": "ok"}
```

---

## Quick Validation (Single Screenshot)

### Test OCR Extraction

```bash
# Pick a sample screenshot
SCREENSHOT="/media/sam/1TB/N8N_dev/screenshots/coinglass_btc_m1_1month_20251030_145708.png"

# Run single screenshot validation
uv run python scripts/validate_screenshots.py \
    --screenshots "$SCREENSHOT" \
    --api-url http://localhost:8000 \
    --output test_result.json \
    --verbose
```

**Expected Output**:
```
[INFO] Processing: coinglass_btc_m1_1month_20251030_145708.png
[INFO] Symbol: BTC, Timestamp: 2025-10-30 14:57:08
[INFO] OCR extracted 6 price levels (confidence: 0.89)
[INFO]   Long zones: [87000, 85000, 83000]
[INFO]   Short zones: [90000, 92000, 95000]
[INFO] Fetching API data for BTCUSDT @ 2025-10-30T14:57:08
[INFO] API returned 12 high-density zones
[INFO] Comparison results:
[INFO]   Hit rate: 0.33 (2/6 zones matched)
[INFO]   Matched: $87k→$86.3k (0.8%), $90k→$90.9k (1.0%)
[INFO] Result saved to: test_result.json
```

---

## Batch Validation (All Screenshots)

### Full Run

```bash
# Process all 3,151 screenshots
uv run python scripts/validate_screenshots.py \
    --screenshots /media/sam/1TB/N8N_dev/screenshots/ \
    --api-url http://localhost:8000 \
    --output data/validation/screenshot_results.jsonl \
    --workers 8

# Estimated time: 30-45 minutes
```

### View Results

```bash
# Check aggregate summary
cat data/validation/screenshot_summary.json | jq .

# Sample output:
# {
#   "total_screenshots": 3151,
#   "processed": 2847,
#   "ocr_failures": 304,
#   "metrics": {
#     "avg_hit_rate": 0.72,
#     "median_hit_rate": 0.75,
#     "pass_rate": 0.68
#   }
# }
```

---

## CLI Options Reference

```bash
uv run python scripts/validate_screenshots.py --help

Options:
  --screenshots PATH        Screenshot file or directory (required)
  --api-url URL             API base URL (default: http://localhost:8000)
  --output FILE             Output JSONL file (default: data/validation/validation_results.jsonl)
  --workers N               Parallel workers (default: 1, use 8 for batch)
  --tolerance PCT           Price match tolerance (default: 1.0%)
  --threshold FLOAT         Pass/fail threshold (default: 0.70)
  --fail-below-threshold    Exit code 1 if avg hit_rate < threshold
  --filter-symbol SYM       Filter by symbol: BTC or ETH
  --summary                 Show aggregate summary after validation
  --verbose, -v             Enable verbose logging
  --dry-run                 List screenshots without processing
```

---

## Common Tasks

### Filter by Symbol

```bash
# BTC only
uv run python scripts/validate_screenshots.py \
    --screenshots /media/sam/1TB/N8N_dev/screenshots/ \
    --filter-symbol BTC \
    --output btc_results.jsonl
```

### Custom Tolerance

```bash
# Allow 2% price difference
uv run python scripts/validate_screenshots.py \
    --screenshots /media/sam/1TB/N8N_dev/screenshots/ \
    --tolerance 2.0 \
    --output results_2pct.jsonl
```

### CI Integration

```bash
# Fail if accuracy < 70%
uv run python scripts/validate_screenshots.py \
    --screenshots /media/sam/1TB/N8N_dev/screenshots/ \
    --threshold 0.70 \
    --fail-below-threshold
# Exit code: 0 if pass, 1 if fail
```

### View Historical Accuracy Summary

```bash
uv run python scripts/validate_screenshots.py --summary

# Output:
# Historical Validation Summary
# =============================
# Total runs: 12
# Avg hit rate: 0.74
# Best: 0.82 (2025-12-15)
# Worst: 0.65 (2025-11-20)
```

---

## Troubleshooting

### OCR Extraction Fails

```bash
# Test Tesseract directly
tesseract /path/to/screenshot.png stdout

# If empty output, try:
# 1. Check image format (must be PNG)
# 2. Increase contrast in preprocessing
# 3. Use EasyOCR fallback
```

### API Connection Error

```bash
# Verify API is running
curl http://localhost:8000/health

# Check API has data for timestamp
curl "http://localhost:8000/liquidations/heatmap-timeseries?symbol=BTCUSDT&limit=1"
```

### Low Hit Rate

Common causes:
1. **Timestamp mismatch**: Increase `--tolerance-minutes` to 10
2. **Different zone calculation**: Accept as methodology difference
3. **OCR errors**: Check `ocr_confidence` in results, use `--ocr-engine easyocr`

---

## Integration Examples

### Python Script

```python
from scripts.validate_screenshots import ValidationRunner

runner = ValidationRunner(
    api_url="http://localhost:8000",
    tolerance_pct=1.0,
    workers=8
)

# Single screenshot
result = runner.validate_single("/path/to/screenshot.png")
print(f"Hit rate: {result['comparison']['hit_rate']:.1%}")

# Batch validation
results = runner.validate_directory("/media/sam/1TB/N8N_dev/screenshots/")
summary = runner.get_summary(results)
print(f"Average hit rate: {summary['metrics']['avg_hit_rate']:.1%}")
```

### GitHub Actions

A GitHub Actions workflow is available at `.github/workflows/screenshot-validation.yml`.

**Trigger manually** with optional parameters:
- `threshold`: Hit rate threshold (default: 0.70)
- `filter_symbol`: Filter by BTC or ETH
- `workers`: Parallel workers (default: 4)

```yaml
# Example workflow usage
- name: Run screenshot validation
  run: |
    uv run python scripts/validate_screenshots.py \
      --screenshots ./test-screenshots/ \
      --threshold 0.70 \
      --fail-below-threshold
```

---

## Success Criteria Checklist

- [ ] OCR extracts prices from >90% of screenshots
- [ ] Average hit_rate > 70%
- [ ] Total runtime < 4 hours
- [ ] Zero Claude API tokens used
- [ ] Results match manual spot-check
