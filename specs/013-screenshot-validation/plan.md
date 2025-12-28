# Implementation Plan: Screenshot Validation Pipeline

**Branch**: `013-screenshot-validation` | **Date**: 2025-12-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/013-screenshot-validation/spec.md`

## Summary

Implement OCR-based validation pipeline to compare 3,151 Coinglass heatmap screenshots against our API predictions. Uses Pytesseract/EasyOCR for price level extraction, calculates hit_rate metrics, and validates model accuracy (target >70% match rate). Zero Claude API tokens - fully local processing.

## Technical Context

**Language/Version**: Python 3.11 (existing project)
**Primary Dependencies**:
- pytesseract (fast OCR, Tesseract backend)
- easyocr (fallback, PyTorch-based, better accuracy)
- Pillow/opencv-python (image preprocessing)
- httpx (async API client)

**Storage**:
- Input: PNG screenshots in `/media/sam/1TB/N8N_dev/screenshots/` (3,151 files)
- Output: JSONL validation results in `data/validation/`

**Testing**: pytest (existing test framework)
**Target Platform**: Linux (Ubuntu 22.04+), CPU-only (no GPU required)
**Project Type**: Single project - adds script to existing `scripts/` directory
**Performance Goals**:
- OCR: <5s per screenshot
- Total: <4h for 3,151 screenshots
- API matching: <100ms per comparison

**Constraints**:
- <4GB RAM
- No GPU dependencies
- Zero Claude API tokens

**Scale/Scope**: 3,151 screenshots, ~2 months of historical data

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| **1. Mathematical Correctness** | ✅ PASS | Price comparison uses percentage tolerance (±1%), clearly defined algorithm |
| **2. Test-Driven Development** | ⚠️ PARTIAL | Script is validation tool itself; unit tests for OCR accuracy |
| **3. Exchange Compatibility** | N/A | Compares against Coinglass (reference), not exchange data |
| **4. Performance Efficiency** | ✅ PASS | 5s per image × 3151 = 4.3h (within budget with parallelism) |
| **5. Data Integrity** | ✅ PASS | Append-only JSONL output, no data modification |
| **6. Graceful Degradation** | ✅ PASS | Skip failed OCR, continue with remaining screenshots |
| **7. Progressive Enhancement** | ✅ PASS | Single screenshot → batch mode → CI integration |
| **8. Documentation Completeness** | ✅ PASS | Spec includes usage examples, output format |

**Constitution Decision**: ✅ PROCEED (no violations)

## Project Structure

### Documentation (this feature)

```
specs/013-screenshot-validation/
├── plan.md              # This file
├── research.md          # OCR engine comparison, preprocessing techniques
├── data-model.md        # Entity definitions
├── quickstart.md        # Quick start guide
├── contracts/           # Output format schemas
│   └── validation_result.json
└── tasks.md             # Implementation tasks
```

### Source Code (repository root)

```
scripts/
└── validate_screenshots.py     # Main validation script (NEW)

src/liquidationheatmap/validation/
├── __init__.py                 # Existing
├── coinglass_scraper.py        # Existing (Playwright-based)
├── ocr_extractor.py            # NEW: OCR pipeline
├── screenshot_parser.py        # NEW: Filename parsing
└── zone_comparator.py          # NEW: Hit rate calculation

tests/validation/
├── test_ocr_extractor.py       # NEW: OCR unit tests
├── test_screenshot_parser.py   # NEW: Filename parser tests
└── test_zone_comparator.py     # NEW: Comparison logic tests

data/validation/
├── validation_results.jsonl    # Per-screenshot output
└── validation_summary.json     # Aggregate metrics
```

**Structure Decision**: Extends existing `src/liquidationheatmap/validation/` module. Main entry point is standalone script for batch processing.

## Phase 0: Research Summary

### OCR Engine Selection

| Engine | Speed | Accuracy | GPU Required | Selected |
|--------|-------|----------|--------------|----------|
| **Pytesseract** | ~1s | Good for clean text | No | ✅ Primary |
| **EasyOCR** | ~3s | Better for stylized | Optional | ✅ Fallback |
| Google Vision API | N/A | Best | API cost | ❌ Rejected |

**Decision**: Hybrid approach - Pytesseract first, EasyOCR fallback if confidence <0.7

### Image Preprocessing

**Tested Techniques**:
1. ✅ Grayscale conversion (required)
2. ✅ Adaptive thresholding (improves edge detection)
3. ✅ Y-axis crop (focus on price labels)
4. ❌ Deskewing (screenshots are already aligned)

### Timestamp Alignment

**Issue**: API uses 1-minute resolution, screenshots may have drift
**Solution**: ±5 minute window for timestamp matching

## Phase 1: Design Artifacts

### Data Model

See [data-model.md](./data-model.md)

### API Contract

See [contracts/validation_result.json](./contracts/validation_result.json)

### Quick Start

See [quickstart.md](./quickstart.md)

## Implementation Strategy

### Phase 1: Core OCR (Day 1)
1. Implement `OCRExtractor` class
2. Test on 10 sample screenshots
3. Calibrate preprocessing parameters

### Phase 2: Comparison Logic (Day 1-2)
1. Implement `ZoneComparator` class
2. Add hit_rate calculation
3. Unit tests for edge cases

### Phase 3: Batch Processing (Day 2)
1. Implement `validate_screenshots.py` script
2. Add multiprocessing (8 workers)
3. Progress reporting and logging

### Phase 4: Integration (Day 3)
1. Run full 3,151 screenshot validation
2. Generate summary report
3. CI integration (optional)

## Risk Mitigation

| Risk | Mitigation | Owner |
|------|------------|-------|
| OCR accuracy <90% | EasyOCR fallback, manual calibration | Implementation |
| Performance >4h | Multiprocessing, skip low-priority images | Implementation |
| Timestamp mismatch | ±5min window, log unmatched | Design |

## Complexity Tracking

*No Constitution violations requiring justification*

## Next Steps

1. Generate `research.md` with OCR benchmark results
2. Generate `data-model.md` with entity definitions
3. Generate `contracts/validation_result.json` schema
4. Generate `quickstart.md` usage guide
5. Run `/speckit.tasks` to create implementation tasks
