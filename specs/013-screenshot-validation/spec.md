# Feature Specification: Screenshot Validation Pipeline

**Feature Branch**: `validation/screenshot-ocr`
**Created**: 2025-12-28
**Status**: Draft
**Priority**: P0 - CRITICAL (validates model accuracy)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automated Coinglass Comparison (Priority: P1)

As a **quantitative analyst**, I need to automatically compare our heatmap predictions against Coinglass screenshots to validate model accuracy without manual intervention or Claude API costs.

**Why this priority**: Validates core model correctness using existing 3,151 screenshots spanning months of historical data. Without this, we don't know if our model produces accurate results.

**Independent Test**: Can be fully tested by running the standalone Python script against a single screenshot and API response, comparing extracted price levels. Delivers immediate validation feedback via JSON output.

**Acceptance Scenarios**:

1. **Given** 3,151 Coinglass screenshots in `/media/sam/1TB/N8N_dev/screenshots/`
   **When** script runs OCR extraction on all images
   **Then** system extracts price levels from heatmap axis with >90% OCR accuracy

2. **Given** extracted Coinglass price levels for timestamp T
   **When** fetching our API `/liquidations/heatmap-timeseries` for same timestamp
   **Then** system compares high-density zones and outputs hit_rate JSON

3. **Given** comparison results showing >70% hit rate on major zones
   **When** validation completes
   **Then** system generates detailed match report with zero Claude token usage

---

### User Story 2 - Historical Trend Analysis (Priority: P2)

As a **data engineer**, I need to track validation accuracy over time to identify periods where our model diverges from Coinglass and investigate root causes.

**Why this priority**: Helps identify systematic biases or data quality issues by analyzing validation results across the 3+ month screenshot timeline.

**Independent Test**: Can be tested by aggregating hit_rate metrics by date and generating trend charts. Delivers insights into model stability over time.

**Acceptance Scenarios**:

1. **Given** validation results for all 3,151 screenshots
   **When** aggregating hit_rate by week
   **Then** system generates time-series plot showing accuracy trends

2. **Given** periods with <50% hit rate
   **When** analyst reviews failed matches
   **Then** system provides detailed diff showing Coinglass vs our predictions

---

### User Story 3 - CI/CD Integration (Priority: P3)

As a **developer**, I want screenshot validation to run in CI pipeline so that model changes are automatically validated before deployment.

**Why this priority**: Prevents regression by catching accuracy drops before production deployment. Lower priority because manual validation is acceptable initially.

**Independent Test**: Can be tested by triggering validation script in GitHub Actions and checking exit code. Delivers automated quality gates.

**Acceptance Scenarios**:

1. **Given** PR modifying liquidation calculation logic
   **When** CI runs screenshot validation
   **Then** pipeline fails if hit_rate drops below 70% threshold

2. **Given** validation passing in CI
   **When** PR is merged
   **Then** validation metrics are archived as CI artifacts

---

### Edge Cases

- What happens when OCR fails to extract price levels from screenshot (blurry, axis labels cut off)?
  - **Handle**: Skip screenshot, log warning, continue with remaining images

- What happens when API timestamp doesn't match screenshot timestamp exactly (API uses 1-minute resolution)?
  - **Handle**: Use closest timestamp within ±5 minute window

- What happens when Coinglass heatmap shows zones that don't exist in our data (different calculation method)?
  - **Handle**: Accept as false negative, report in comparison metadata

- What happens when screenshot format changes (different resolution, axis scale)?
  - **Handle**: Template-based OCR configuration per image dimension

- What happens when we have no screenshot for a specific timestamp in our API data?
  - **Handle**: Skip that API response, validation only runs on timestamps with screenshots

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST extract price levels from Coinglass screenshots using local OCR (pytesseract or easyocr)
- **FR-002**: System MUST parse screenshot filenames to extract timestamp (`coinglass_btc_m1_1month_YYYYMMDD_HHMMSS.png`)
- **FR-003**: System MUST query our API `/liquidations/heatmap-timeseries` for matching timestamp
- **FR-004**: System MUST extract all visible price levels from Coinglass screenshots via OCR (no density filtering - OCR cannot detect heatmap intensity)
- **FR-005**: System MUST calculate hit_rate as percentage of Coinglass zones that match our API's top-20 zones by volume (within ±1% price tolerance)
- **FR-006**: System MUST output validation results as JSON file with zero Claude token usage
- **FR-007**: System MUST run as standalone Python script (no external dependencies on Claude API)
- **FR-008**: System MUST process all 3,151 screenshots in batch mode
- **FR-009**: System MUST generate per-screenshot comparison results and aggregate statistics
- **FR-010**: System MUST distinguish between BTC and ETH screenshots based on filename pattern
- **FR-011**: System MUST handle OCR errors gracefully (skip failed screenshots, log errors)
- **FR-012**: System MUST support configurable price tolerance threshold (default: ±1%)
- **FR-013**: System MUST validate target hit_rate >70% on major liquidation zones

### Non-Functional Requirements

- **NFR-001**: OCR extraction MUST complete in <5 seconds per screenshot on standard CPU
- **NFR-002**: Total validation runtime MUST be <4 hours for all 3,151 screenshots
- **NFR-003**: Script MUST run on Linux (Ubuntu 22.04+) without GPU dependencies
- **NFR-004**: Memory usage MUST stay below 4GB RAM
- **NFR-005**: Output JSON MUST be <10MB for 3,151 screenshot results

### Key Entities *(include if feature involves data)*

- **Screenshot**: Coinglass heatmap image file
  - filename (str): `coinglass_{symbol}_m{leverage}_{timeframe}_{timestamp}.png`
  - timestamp (datetime): Extracted from filename
  - symbol (str): BTC or ETH
  - resolution (tuple): Image dimensions (1710x1210 confirmed)

- **ExtractedPriceLevels**: OCR output from screenshot
  - long_zones (list[float]): Liquidation price levels for longs (below current price)
  - short_zones (list[float]): Liquidation price levels for shorts (above current price)
  - confidence (float): OCR confidence score (0-1), calculated as minimum confidence across all extracted numbers
  - extraction_method (str): "pytesseract" or "easyocr"
  - current_price (float): Current price from API at screenshot timestamp (authoritative source)

- **APIPriceLevels**: Our heatmap API response
  - symbol (str): "BTCUSDT" or "ETHUSDT"
  - timestamp (datetime): API query timestamp
  - long_zones (list[dict]): [{"price": float, "volume": float}]
  - short_zones (list[dict]): [{"price": float, "volume": float}]

- **ValidationResult**: Per-screenshot comparison
  - screenshot_path (str): Absolute path to image
  - timestamp (datetime): Screenshot timestamp
  - hit_rate (float): Percentage of matched zones (0-1)
  - matched_zones (list[dict]): Zones that matched within tolerance
  - missed_zones (list[dict]): Coinglass zones not in our data
  - extra_zones (list[dict]): Our zones not in Coinglass
  - ocr_confidence (float): OCR extraction quality

- **AggregateMetrics**: Overall validation statistics
  - total_screenshots (int): Total processed
  - avg_hit_rate (float): Mean hit rate across all screenshots
  - median_hit_rate (float): Median hit rate
  - pass_rate (float): % screenshots with hit_rate >70%
  - ocr_failure_rate (float): % screenshots with OCR errors

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: OCR successfully extracts price levels from >90% of screenshots (2,835+ of 3,151)
- **SC-002**: Average hit_rate across all screenshots is >70% (validates model accuracy)
- **SC-003**: Manual spot-check of 10 random screenshots confirms automated comparison is correct
- **SC-004**: Script completes full validation run in <4 hours on standard CPU
- **SC-005**: Zero Claude API tokens consumed during validation process
- **SC-006**: Comparison matches manual validation example: Coinglass Long ~$87k → Our $86.3k (0.8% error), Coinglass Short ~$90k → Our $90.9k (1% error)

## Technical Approach

### OCR Strategy

**Option 1: Pytesseract** (recommended for speed)
- Pros: Faster (~1s per image), widely supported, C++ backend
- Cons: Lower accuracy on stylized fonts
- Install: `apt-get install tesseract-ocr`, `pip install pytesseract`

**Option 2: EasyOCR** (recommended for accuracy)
- Pros: Better accuracy on complex layouts, handles rotated text
- Cons: Slower (~3s per image), PyTorch dependency
- Install: `pip install easyocr`

**Hybrid Approach**: Try Pytesseract first, fallback to EasyOCR if confidence <0.7

### Price Level Extraction Pipeline

```
1. Image Preprocessing
   - Load screenshot (1710x1210 PNG)
   - Crop to Y-axis region (price labels)
   - Convert to grayscale
   - Apply adaptive thresholding (improve OCR accuracy)

2. OCR Extraction
   - Run OCR on cropped Y-axis region
   - Parse numbers from OCR text (regex: \d+[,.]?\d+)
   - Filter out noise (only keep realistic BTC prices: $20k-$150k)

3. Zone Classification
   - Current price from API (authoritative source)
   - Zones < current_price → long liquidations
   - Zones > current_price → short liquidations

4. Zone Extraction (Simplified)
   - Extract ALL visible price levels from Y-axis
   - No density filtering from screenshots (OCR cannot detect heatmap intensity)
   - Density filtering applied only to API response (top-20 zones by volume)
```

### API Matching Logic

```python
def compare_zones(coinglass_zones: list[float],
                  api_zones: list[dict],
                  tolerance_pct: float = 1.0) -> dict:
    """
    Compare price zones from Coinglass vs our API.

    Args:
        coinglass_zones: List of price levels from OCR
        api_zones: List of {"price": float, "volume": float} from API
        tolerance_pct: Price match tolerance (default 1%)

    Returns:
        {
            "hit_rate": float,  # matched / total_coinglass_zones
            "matched": list[dict],  # Zones that matched
            "missed": list[float],  # Coinglass zones not in our data
            "extra": list[dict]  # Our zones not in Coinglass
        }
    """
    api_prices = [z["price"] for z in api_zones]
    matched = []
    missed = []

    for cg_price in coinglass_zones:
        # Find closest API price within tolerance
        closest = min(api_prices, key=lambda p: abs(p - cg_price))
        pct_diff = abs(closest - cg_price) / cg_price * 100

        if pct_diff <= tolerance_pct:
            matched.append({
                "coinglass": cg_price,
                "our_api": closest,
                "error_pct": pct_diff
            })
        else:
            missed.append(cg_price)

    # Find zones in our API but not in Coinglass
    cg_set = set(coinglass_zones)
    extra = [z for z in api_zones
             if not any(abs(z["price"] - cg) / cg * 100 <= tolerance_pct
                       for cg in cg_set)]

    return {
        "hit_rate": len(matched) / len(coinglass_zones) if coinglass_zones else 0,
        "matched": matched,
        "missed": missed,
        "extra": extra
    }
```

### Timestamp Parsing

```python
import re
from datetime import datetime

def parse_screenshot_timestamp(filename: str) -> dict:
    """
    Parse Coinglass screenshot filename.

    Example: coinglass_btc_m1_1month_20251030_145708.png

    Returns:
        {
            "symbol": "btc",
            "leverage": "m1",  # m1=1x, m3=3x, etc.
            "timeframe": "1month",
            "timestamp": datetime(2025, 10, 30, 14, 57, 8)
        }
    """
    pattern = r"coinglass_(\w+)_(\w+)_(\w+)_(\d{8})_(\d{6})\.png"
    match = re.match(pattern, filename)

    if not match:
        raise ValueError(f"Invalid filename format: {filename}")

    symbol, leverage, timeframe, date_str, time_str = match.groups()

    # Parse timestamp: YYYYMMDD_HHMMSS
    timestamp = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")

    return {
        "symbol": symbol.upper(),  # BTC or ETH
        "leverage": leverage,
        "timeframe": timeframe,
        "timestamp": timestamp
    }
```

### Output Format

**Per-Screenshot Result** (`validation_results.jsonl`):
```json
{
  "screenshot": "/media/sam/1TB/N8N_dev/screenshots/coinglass_btc_m1_1month_20251030_145708.png",
  "timestamp": "2025-10-30T14:57:08",
  "symbol": "BTC",
  "ocr_confidence": 0.92,
  "coinglass_zones": {
    "long": [87000, 85000, 83000],
    "short": [90000, 92000, 95000]
  },
  "api_zones": {
    "long": [{"price": 86300, "volume": 1500000}],
    "short": [{"price": 90900, "volume": 2000000}]
  },
  "comparison": {
    "long_hit_rate": 0.33,
    "short_hit_rate": 0.33,
    "overall_hit_rate": 0.33,
    "matched": [
      {"coinglass": 87000, "our_api": 86300, "error_pct": 0.8}
    ]
  }
}
```

**Aggregate Summary** (`validation_summary.json`):
```json
{
  "total_screenshots": 3151,
  "processed": 2847,
  "ocr_failures": 304,
  "ocr_failure_rate": 0.096,
  "metrics": {
    "avg_hit_rate": 0.72,
    "median_hit_rate": 0.75,
    "pass_rate": 0.68,
    "hit_rate_distribution": {
      "0-25%": 234,
      "25-50%": 412,
      "50-75%": 890,
      "75-100%": 1311
    }
  },
  "by_symbol": {
    "BTC": {
      "count": 1876,
      "avg_hit_rate": 0.74
    },
    "ETH": {
      "count": 971,
      "avg_hit_rate": 0.68
    }
  },
  "timestamp_range": {
    "earliest": "2025-10-30T14:57:08",
    "latest": "2025-12-28T05:16:21"
  }
}
```

## Implementation Notes

### Script Structure

```
scripts/
└── validate_screenshots.py      # Standalone validation script
    ├── OCRExtractor              # Handles image processing + OCR
    ├── ScreenshotParser          # Filename parsing + timestamp extraction
    ├── APIClient                 # Fetch our heatmap API
    ├── ZoneComparator            # Compare Coinglass vs API
    └── ValidationRunner          # Orchestrates full pipeline
```

### Dependencies

```toml
# pyproject.toml additions
[project.optional-dependencies]
validation = [
    "pytesseract>=0.3.10",        # OCR engine
    "easyocr>=1.7.0",             # Backup OCR (PyTorch-based)
    "Pillow>=10.0.0",             # Image processing
    "opencv-python>=4.8.0",       # Image preprocessing
    "numpy>=1.24.0",              # Array operations
    "httpx>=0.25.0",              # Async API client
]
```

### Usage Examples

**Basic Validation**:
```bash
# Validate all screenshots
uv run python scripts/validate_screenshots.py \
    --screenshots /media/sam/1TB/N8N_dev/screenshots/ \
    --api-url http://localhost:8000 \
    --output validation_results.jsonl

# Validate single screenshot (testing)
uv run python scripts/validate_screenshots.py \
    --screenshots /media/sam/1TB/N8N_dev/screenshots/coinglass_btc_m1_1month_20251030_145708.png \
    --api-url http://localhost:8000 \
    --output test_result.json \
    --verbose
```

**With Custom Tolerance**:
```bash
# Allow 2% price difference instead of 1%
uv run python scripts/validate_screenshots.py \
    --screenshots /media/sam/1TB/N8N_dev/screenshots/ \
    --api-url http://localhost:8000 \
    --tolerance 2.0 \
    --output results.jsonl
```

**OCR Engine Selection**:
```bash
# Force EasyOCR (slower but more accurate)
uv run python scripts/validate_screenshots.py \
    --screenshots /media/sam/1TB/N8N_dev/screenshots/ \
    --ocr-engine easyocr \
    --output results.jsonl

# Use hybrid approach (Pytesseract → EasyOCR fallback)
uv run python scripts/validate_screenshots.py \
    --screenshots /media/sam/1TB/N8N_dev/screenshots/ \
    --ocr-engine hybrid \
    --output results.jsonl
```

**CI Integration**:
```bash
# Exit code 1 if hit_rate < 70%
uv run python scripts/validate_screenshots.py \
    --screenshots /media/sam/1TB/N8N_dev/screenshots/ \
    --api-url http://localhost:8000 \
    --threshold 0.70 \
    --fail-below-threshold \
    --output validation_results.jsonl
```

## Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| OCR fails on stylized Coinglass fonts | Medium | High | Use EasyOCR fallback, manual calibration on 10 samples |
| Screenshot axis scale changes over time | Low | Medium | Detect resolution changes, apply scale factor |
| API timestamps don't align with screenshots | High | Low | Use ±5min timestamp window |
| Coinglass uses different density calculation | Medium | High | Accept as methodology difference, document in report |
| 3,151 screenshots take >4h to process | Medium | Low | Parallelize with multiprocessing (8 workers) |

## Out of Scope

- **Real-time validation**: Only historical screenshot comparison (no live WebSocket)
- **Multi-exchange validation**: Only Coinglass (not Bybit/OKX screenshots)
- **Automated screenshot capture**: Use existing N8N workflow screenshots
- **Visual heatmap comparison**: Only price level numerical comparison (no image similarity)
- **Root cause analysis**: Script identifies mismatches but doesn't explain WHY (manual investigation)

## References

- **Manual validation example**: Coinglass Long ~$87k → Our $86.3k (0.8%), Coinglass Short ~$90k → Our $90.9k (1%)
- **Screenshot storage**: `/media/sam/1TB/N8N_dev/screenshots/` (3,151 images)
- **Screenshot pattern**: `coinglass_{symbol}_m{leverage}_{timeframe}_YYYYMMDD_HHMMSS.png`
- **API endpoint**: `http://localhost:8000/liquidations/heatmap-timeseries?symbol=BTCUSDT&limit=1000`
- **Related spec**: `.specify/validation-pipeline/spec.md` (historical liquidation validation)
