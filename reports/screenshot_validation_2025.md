# Screenshot Validation Report 2025

**Feature**: 013-screenshot-validation
**Date**: 2025-12-28
**Author**: Automated Pipeline

## Executive Summary

The screenshot validation pipeline was developed to automatically compare our heatmap liquidation predictions against Coinglass screenshots using OCR extraction. While the pipeline is technically functional, testing reveals significant methodology differences between our calculations and Coinglass's approach.

### Key Findings

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| OCR Success Rate | >90% | 66.4% | FAIL |
| Average Hit Rate | >70% | 12.4% | FAIL |
| Processing Time | <4 hours | 6 minutes | PASS |
| Claude API Tokens | 0 | 0 | PASS |

**Verdict**: Pipeline functional, but methodology alignment needed before validation is meaningful.

---

## 1. Pipeline Overview

### 1.1 Architecture

```
Coinglass Screenshot (.png)
        │
        ▼
┌───────────────────────┐
│   Screenshot Parser   │ ← Parse filename for metadata
│   (screenshot_parser) │   (symbol, leverage, timestamp)
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│    OCR Extractor      │ ← Extract Y-axis price levels
│   (ocr_extractor)     │   Pytesseract + EasyOCR fallback
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│   Zone Comparator     │ ← Match against API heatmap data
│   (zone_comparator)   │   Calculate hit_rate metrics
└───────────────────────┘
        │
        ▼
    ValidationResult
    (JSONL output)
```

### 1.2 Data Flow

1. **Input**: 3,159 Coinglass screenshots from `/media/sam/1TB/N8N_dev/screenshots/`
2. **Processing**: Parallel OCR extraction (8 workers), API comparison
3. **Output**: Per-screenshot JSONL results + aggregate summary JSON

---

## 2. Full Batch Results

### 2.1 Processing Statistics

| Metric | Value |
|--------|-------|
| Total Screenshots | 3,159 |
| Successfully Processed | 672 (21.3%) |
| OCR Failures | 1,061 (33.6%) |
| API Failures | 1,426 (45.1%) |
| Total Processing Time | 352 seconds (~6 minutes) |
| Avg Time per Screenshot | 111 ms |

### 2.2 Hit Rate Distribution

| Hit Rate Bucket | Count | Percentage |
|-----------------|-------|------------|
| 0-25% | 531 | 79.0% |
| 25-50% | 79 | 11.8% |
| 50-75% | 43 | 6.4% |
| 75-100% | 19 | 2.8% |

### 2.3 Results by Symbol

| Symbol | Screenshots | Avg Hit Rate |
|--------|-------------|--------------|
| BTC | 391 | 21.3% |
| ETH | 281 | 0.0% |

### 2.4 Time Range Covered

- **Earliest**: 2025-10-30 14:54:32
- **Latest**: 2025-12-28 13:17:24
- **Duration**: ~59 days of historical data

---

## 3. Root Cause Analysis

### 3.1 Low Hit Rate (12.4% vs 70% target)

**Primary Cause: Methodology Difference**

Example from sample validation:
```
Coinglass OCR zones: [100910, 105000, 115000, 120000, 125000, 130000]
Our API zones:       [78700, 83900, 85700, 79300, 84200, ...]
```

The zones don't overlap because:
1. Coinglass may use different leverage assumptions
2. Coinglass may use different liquidation formulas
3. Coinglass may incorporate real-time order book data we don't have

### 3.2 High OCR Failure Rate (33.6%)

**Causes**:
1. Some screenshots have non-standard Y-axis formatting (especially `m3` leverage)
2. OCR confidence threshold (50%) filters out borderline extractions
3. EasyOCR fallback improves accuracy but some images still fail

### 3.3 High API Failure Rate (45.1%)

**Causes**:
1. Timestamp misalignment: API may not have data for exact screenshot timestamp
2. ETH data gap: API primarily has BTC data loaded
3. 5-minute timestamp window may be too narrow

---

## 4. Manual Spot-Check Results

See detailed results in: `reports/spot_check_results.md`

### Summary

| Criteria | Target | Actual | Status |
|----------|--------|--------|--------|
| OCR Success (all 10) | 100% | 70% | FAIL |
| API Match (>= 7/10) | 70% | 30% | FAIL |

---

## 5. Technical Implementation

### 5.1 Files Created/Modified

| File | Purpose |
|------|---------|
| `src/liquidationheatmap/validation/screenshot_parser.py` | Filename parsing |
| `src/liquidationheatmap/validation/ocr_extractor.py` | OCR extraction |
| `src/liquidationheatmap/validation/zone_comparator.py` | Zone comparison |
| `scripts/validate_screenshots.py` | CLI validation script |
| `.github/workflows/screenshot-validation.yml` | CI integration |

### 5.2 CLI Usage

```bash
# Single screenshot validation
uv run python scripts/validate_screenshots.py \
    --screenshots /path/to/screenshot.png \
    --verbose

# Batch validation
uv run python scripts/validate_screenshots.py \
    --screenshots /media/sam/1TB/N8N_dev/screenshots/ \
    --workers 8 \
    --output data/validation/results.jsonl

# CI integration (fail if below threshold)
uv run python scripts/validate_screenshots.py \
    --screenshots /path/to/screenshots/ \
    --threshold 0.70 \
    --fail-below-threshold
```

### 5.3 Output Formats

**Per-screenshot JSONL** (`validation_results.jsonl`):
```json
{
  "screenshot": "/path/to/screenshot.png",
  "timestamp": "2025-10-30T14:57:08",
  "symbol": "BTC",
  "status": "success",
  "ocr_confidence": 0.72,
  "coinglass_zones": {"long": [], "short": [100910, 105000]},
  "api_zones": {"long": [...], "short": [...]},
  "comparison": {"hit_rate": 0.0, "matched": [], "missed": [...]}
}
```

**Aggregate Summary** (`validation_summary.json`):
```json
{
  "total_screenshots": 3159,
  "processed": 672,
  "metrics": {
    "avg_hit_rate": 0.124,
    "pass_rate": 0.028
  }
}
```

---

## 6. Recommendations

### 6.1 Short-term

1. **Increase tolerance** from 1% to 5% to account for rounding differences
2. **Load ETH data** into the API to enable ETH validation
3. **Improve OCR preprocessing** for m3 leverage screenshots

### 6.2 Medium-term

1. **Investigate Coinglass methodology** by analyzing their published documentation
2. **Add visual diff output** to help debug mismatches
3. **Implement timestamp fuzzy matching** with larger windows

### 6.3 Long-term

1. **Align calculation methodology** with Coinglass if appropriate
2. **Consider alternative validation sources** (Bybit, OKX screenshots)
3. **Build regression test suite** with known-good examples

---

## 7. Conclusion

The screenshot validation pipeline successfully:
- Extracts price levels from Coinglass screenshots using OCR
- Compares against our API heatmap data
- Generates structured validation results
- Runs within performance targets (6 min vs 4 hour target)
- Uses zero Claude API tokens

However, the validation reveals a **fundamental methodology difference** between our liquidation calculations and Coinglass's approach. Before this pipeline can provide meaningful accuracy metrics, we need to either:

1. Align our calculation methodology with Coinglass, OR
2. Accept the differences and use this as a "divergence detector" rather than "accuracy validator"

---

## Appendix A: Output Files

- `data/validation/validation_full.jsonl` - Full batch results (3,159 screenshots)
- `data/validation/validation_summary.json` - Aggregate statistics
- `reports/spot_check_results.md` - Manual verification results

## Appendix B: Dependencies

```toml
[project.optional-dependencies]
validation = [
    "pytesseract>=0.3.10",
    "easyocr>=1.7.0",
    "Pillow>=10.0.0",
    "opencv-python>=4.8.0",
    "httpx>=0.25.0",
]
```

System requirement: `tesseract-ocr` and `tesseract-ocr-eng` packages
