# Manual Spot-Check Results

**Date**: 2025-12-28
**Feature**: 013-screenshot-validation

## Test Methodology

1. Selected 10 random screenshots using: `ls /media/sam/1TB/N8N_dev/screenshots/ | shuf | head -10`
2. Ran single-file validation on each screenshot
3. Documented OCR extraction status and hit rate

## Results

| # | Screenshot | Symbol | Status | OCR Conf | Hit Rate | Notes |
|---|------------|--------|--------|----------|----------|-------|
| 1 | coinglass_btc_m1_1month_20251124_050258.png | BTC | Pass | 56% | 33% | 1 zone matched |
| 2 | coinglass_btc_m1_3day_20251031_041709.png | BTC | Pass | 76% | 0% | 7 zones extracted, no API match |
| 3 | coinglass_btc_m1_3day_20251117_130027.png | BTC | Pass | 59% | 50% | 2 zones matched |
| 4 | coinglass_btc_m2_1month_20251121_050725.png | BTC | Pass | 60% | 0% | 5 zones extracted, no API match |
| 5 | coinglass_btc_m2_2week_20251220_210603.png | BTC | Pass | 54% | 25% | 1 zone matched |
| 6 | coinglass_btc_m3_2week_20251114_050431.png | BTC | FAIL | 71% | 0% | OCR extraction failed (low validity) |
| 7 | coinglass_eth_m1_1month_20251207_211145.png | ETH | Pass | 73% | 0% | 6 zones extracted, no ETH data in API |
| 8 | coinglass_eth_m1_3day_20251201_130910.png | ETH | Pass | 64% | 0% | 7 zones extracted, no ETH data in API |
| 9 | coinglass_eth_m3_1month_20251105_131704.png | ETH | FAIL | 68% | 0% | OCR extraction failed (low validity) |
| 10 | coinglass_eth_m3_1month_20251201_131725.png | ETH | FAIL | 69% | 0% | OCR extraction failed (low validity) |

## Summary Statistics

| Metric | Result | Target | Status |
|--------|--------|--------|--------|
| OCR Success Rate | 70% (7/10) | 100% (all 10) | FAIL |
| API Match Rate | 30% (3/10 with hits) | >= 70% (7/10) | FAIL |
| BTC OCR Success | 83% (5/6) | - | - |
| ETH OCR Success | 50% (2/4) | - | - |

## Observations

### 1. OCR Extraction Issues
- **3 screenshots failed OCR validation** (confidence threshold not met)
- Failed screenshots all used `m3` leverage setting
- OCR confidence ranged from 54% to 76% for successful extractions

### 2. API Matching Issues
- Even with successful OCR, only **3 out of 7 screenshots** had any zone matches
- **ETH screenshots showed 0% hit rate** due to missing ETH data in API
- **Price range mismatch**: Coinglass shows zones at $100k-$130k, API returns $70k-$96k

### 3. Root Causes
1. **Methodology Difference**: Our API calculates liquidation zones using different formulas than Coinglass
2. **ETH Data Gap**: API does not have ETH liquidation data loaded
3. **Leverage-specific images**: m3 leverage screenshots may have different Y-axis formatting

## Verdict

**CRITERIA NOT MET**

Per task T057 requirements:
- All 10 must pass OCR extraction: **FAIL** (7/10 passed)
- >= 7 must match API zones: **FAIL** (3/10 had matches)

The validation pipeline is technically functional, but reveals fundamental methodology differences between our liquidation calculations and Coinglass's approach.

## Recommendations

1. **Investigate Coinglass methodology** to understand their zone calculation approach
2. **Load ETH data** into the API to enable ETH validation
3. **Review OCR preprocessing** for m3 leverage screenshots
4. **Consider adjusting tolerance** from 1% to 5% for broader matching
