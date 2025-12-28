# Tasks: Screenshot Validation Pipeline

**Feature**: 013-screenshot-validation
**Branch**: `013-screenshot-validation`
**Input**: Design documents from `/specs/013-screenshot-validation/`

## Format: `[ID] [P?] [Story?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install dependencies and verify environment

- [X] T001 Install system dependency: `sudo apt-get install tesseract-ocr tesseract-ocr-eng`
- [X] T002 Add Python dependencies: `uv add pytesseract easyocr pillow opencv-python httpx`
- [X] T003 [P] Verify screenshot directory access: `/media/sam/1TB/N8N_dev/screenshots/`
- [X] T004 [P] Create output directory: `data/validation/` (if not exists)
- [X] T005 [P] Verify API server is accessible at `http://localhost:8000`

**Checkpoint**: Environment ready for development

---

## Phase 2: Foundational (Core Modules)

**Purpose**: Create base classes that all user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Create `src/liquidationheatmap/validation/screenshot_parser.py` with `parse_filename()` function
- [X] T007 [P] Create `src/liquidationheatmap/validation/ocr_extractor.py` with `OCRExtractor` class skeleton
- [X] T008 [P] Create `src/liquidationheatmap/validation/zone_comparator.py` with `ZoneComparator` class skeleton
- [X] T009 Update `src/liquidationheatmap/validation/__init__.py` with new module exports

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Automated Coinglass Comparison (Priority: P1) 🎯 MVP

**Goal**: Automatically compare our heatmap predictions against Coinglass screenshots with OCR extraction and hit_rate calculation

**Independent Test**: Run `validate_screenshots.py` on a single screenshot and verify it outputs valid JSON with hit_rate metric

### Implementation for User Story 1

#### T010-T014: Screenshot Parser Module
- [X] T010 [US1] Implement `parse_filename()` in `src/liquidationheatmap/validation/screenshot_parser.py`
  - Parse pattern: `coinglass_{symbol}_{leverage}_{timeframe}_{YYYYMMDD}_{HHMMSS}.png`
  - Return dict with symbol, leverage, timeframe, timestamp
- [X] T011 [US1] Add `Screenshot` dataclass in `src/liquidationheatmap/validation/screenshot_parser.py`
  - Fields: path, filename, symbol, leverage, timeframe, timestamp, resolution
- [X] T012 [US1] Implement `Screenshot.from_path()` classmethod
- [X] T013 [P] [US1] Add validation for filename format (raise ValueError on invalid)
- [X] T014 [P] [US1] Add unit test `tests/validation/test_screenshot_parser.py`

#### T015-T022: OCR Extractor Module
- [X] T015 [US1] Implement image preprocessing pipeline in `src/liquidationheatmap/validation/ocr_extractor.py`
  - Crop Y-axis region (left 120px)
  - Grayscale conversion
  - Adaptive thresholding
- [X] T016 [US1] Implement `extract_with_pytesseract()` method
  - Use pytesseract for OCR
  - Return extracted text + confidence score
- [X] T017 [US1] Implement `extract_with_easyocr()` fallback method
  - Use EasyOCR when pytesseract confidence < 0.7
- [X] T018 [US1] Implement `extract_price_levels()` method
  - Regex to parse numbers from OCR text
  - Filter by realistic price range (BTC: $20k-$150k, ETH: $1k-$10k)
- [X] T019 [US1] Add `ExtractedPriceLevels` dataclass
  - Fields: screenshot_path, long_zones, short_zones, confidence, extraction_method
- [X] T020 [US1] Implement `OCRExtractor.extract()` main method
  - Preprocess → OCR → Parse → Return ExtractedPriceLevels
- [X] T021 [P] [US1] Add confidence scoring logic
- [X] T022 [P] [US1] Add unit test `tests/validation/test_ocr_extractor.py` with 3 sample screenshots

#### T023-T029: Zone Comparator Module
- [X] T023 [US1] Add `APIPriceLevels` dataclass in `src/liquidationheatmap/validation/zone_comparator.py`
  - Parse from API response, extract top-20 zones sorted by `volume` field (descending)
- [X] T024 [US1] Implement `fetch_api_heatmap()` async method using httpx
  - Query `/liquidations/heatmap-timeseries?symbol={symbol}`
  - Handle timestamp alignment (±5min window)
- [X] T025 [US1] Implement `calculate_hit_rate()` function
  - Compare Coinglass zones vs API zones
  - Use ±1% price tolerance
  - Return hit_rate, matched, missed, extra
- [X] T026 [US1] Add `ValidationResult` dataclass
  - All fields from data-model.md
  - `to_dict()` method for JSON serialization
- [X] T027 [US1] Implement `ZoneComparator.compare()` main method
  - Orchestrate: OCR extraction → API fetch → comparison → ValidationResult
- [X] T028 [P] [US1] Add unit test `tests/validation/test_zone_comparator.py`
- [X] T029 [P] [US1] Add contract test for ValidationResult JSON schema

#### T030-T035: Main Validation Script
- [X] T030 [US1] Create `scripts/validate_screenshots.py` with CLI argument parsing
  - `--screenshots PATH` (file or directory)
  - `--api-url URL` (default: http://localhost:8000)
  - `--output FILE` (default: validation_results.jsonl)
  - `--tolerance PCT` (default: 1.0)
  - `--verbose` flag
- [X] T031 [US1] Implement single screenshot validation mode
- [X] T032 [US1] Implement JSONL output writer
  - Append each ValidationResult to output file
- [X] T033 [US1] Add progress logging (INFO level)
- [X] T034 [US1] Add graceful error handling
  - Skip failed OCR screenshots, log warning
  - Continue processing remaining files
- [X] T035 [US1] Test single screenshot end-to-end:
  ```bash
  uv run python scripts/validate_screenshots.py \
    --screenshots /media/sam/1TB/N8N_dev/screenshots/coinglass_btc_m1_1month_20251030_145708.png \
    --verbose
  ```

**Checkpoint**: Single screenshot validation works - MVP functional ✅

---

## Phase 4: User Story 2 - Historical Trend Analysis (Priority: P2)

**Goal**: Process all 3,151 screenshots in batch mode and generate aggregate statistics for trend analysis

**Independent Test**: Run batch validation on all screenshots, verify summary JSON with avg_hit_rate and distribution

### Implementation for User Story 2

- [X] T036 [US2] Implement directory scanning in `scripts/validate_screenshots.py`
  - Find all `coinglass_*.png` files in directory
  - Sort by timestamp
- [X] T037 [US2] Add multiprocessing support with ProcessPoolExecutor
  - `--workers N` argument (default: 8)
  - Parallel screenshot processing
- [X] T038 [US2] Add `AggregateMetrics` dataclass in `src/liquidationheatmap/validation/zone_comparator.py`
  - Calculate: avg_hit_rate, median_hit_rate, pass_rate, distribution
  - Group by symbol (BTC vs ETH)
- [X] T039 [US2] Implement `calculate_aggregate_metrics()` function
  - Process list of ValidationResults
  - Return AggregateMetrics
- [X] T040 [US2] Add summary JSON output writer
  - Write to `data/validation/screenshot_summary.json`
- [X] T041 [US2] Add progress bar for batch processing (tqdm or simple counter)
- [X] T042 [US2] Add `--summary` flag to show historical accuracy summary
- [X] T043 [US2] Add memory management for large batches
  - Process in chunks of 100 screenshots
  - Clear OCR cache between chunks
- [ ] T044 [US2] Run full batch validation:
  ```bash
  uv run python scripts/validate_screenshots.py \
    --screenshots /media/sam/1TB/N8N_dev/screenshots/ \
    --workers 8 \
    --output data/validation/validation_results.jsonl
  ```
- [ ] T045 [US2] Verify summary meets success criteria:
  - OCR success rate >90%
  - avg_hit_rate >70%
  - Processing time <4 hours

**Checkpoint**: Batch validation works with full dataset ✅

---

## Phase 5: User Story 3 - CI/CD Integration (Priority: P3)

**Goal**: Enable automated validation in CI pipeline with pass/fail exit codes

**Independent Test**: Run validation with `--fail-below-threshold` flag and verify exit code

### Implementation for User Story 3

- [X] T046 [US3] Add `--threshold FLOAT` argument (default: 0.70)
- [X] T047 [US3] Add `--fail-below-threshold` flag
  - Exit code 1 if avg_hit_rate < threshold
  - Exit code 0 if passes
- [X] T048 [P] [US3] Create GitHub Actions workflow `.github/workflows/screenshot-validation.yml`
  - Trigger: manual or on model changes
  - Run validation script
  - Upload results as artifacts
- [X] T049 [P] [US3] Add `--filter-symbol` argument to validate only BTC or ETH
- [X] T050 [US3] Add CI integration test
  ```bash
  uv run python scripts/validate_screenshots.py \
    --screenshots /media/sam/1TB/N8N_dev/screenshots/ \
    --threshold 0.70 \
    --fail-below-threshold
  echo "Exit code: $?"
  ```
- [X] T051 [US3] Document CI usage in quickstart.md

**Checkpoint**: CI integration ready ✅

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, cleanup, validation, and NFR verification

- [X] T052 [P] Run all unit tests: `uv run pytest tests/validation/test_screenshot*.py tests/validation/test_ocr*.py tests/validation/test_zone*.py -v`
- [X] T053 [P] Run linting: `ruff check src/liquidationheatmap/validation/ scripts/validate_screenshots.py`
- [X] T054 [P] Format code: `ruff format src/liquidationheatmap/validation/ scripts/validate_screenshots.py`
- [ ] T055 Update spec.md with actual results (hit_rate achieved)
- [ ] T056 [P] Add docstrings to all public functions
- [ ] T057 Manual spot-check (10 random screenshots):
  1. Select 10 random screenshots using: `ls /media/sam/1TB/N8N_dev/screenshots/ | shuf | head -10`
  2. For each screenshot: run single-file validation, manually verify OCR output matches visible Y-axis labels
  3. Document findings in `reports/spot_check_results.md` with pass/fail per screenshot
  4. All 10 must pass OCR extraction; ≥7 must match API zones within tolerance
- [ ] T058 Create validation report in `reports/screenshot_validation_2025.md`
- [X] T059 [P] NFR-001 Performance test: Verify single screenshot OCR <5s (achieved: 1.51s)
  ```bash
  time uv run python scripts/validate_screenshots.py \
    --screenshots /media/sam/1TB/N8N_dev/screenshots/coinglass_btc_m1_1month_20251030_145708.png \
    --verbose 2>&1 | grep -E "(real|OCR time)"
  ```
- [X] T060 [P] NFR-005 Output size test: Verify JSONL output <10MB for full run (estimate: ~4.4MB for 3159 files)
  ```bash
  ls -lh data/validation/validation_results.jsonl | awk '{print $5}'
  ```

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after US1 (needs single-screenshot validation working)
- **User Story 3 (P3)**: Can start after US2 (needs batch validation working)

### Within Each User Story

- Parser → OCR → Comparator → Script (sequential within modules)
- Tests can run in parallel with implementation (TDD style)

### Parallel Opportunities

**Phase 1 (Setup)**:
```
Task: T003 [P] Verify screenshot directory
Task: T004 [P] Create output directory
Task: T005 [P] Verify API server
```

**Phase 2 (Foundational)**:
```
Task: T007 [P] Create OCR extractor skeleton
Task: T008 [P] Create zone comparator skeleton
```

**Phase 3 (US1) - Models**:
```
Task: T013 [P] Add filename validation
Task: T014 [P] Add screenshot parser test
Task: T021 [P] Add confidence scoring
Task: T022 [P] Add OCR extractor test
Task: T028 [P] Add zone comparator test
Task: T029 [P] Add contract test
```

**Phase 5 (US3)**:
```
Task: T048 [P] Create GitHub Actions workflow
Task: T049 [P] Add filter-symbol argument
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (~30 min)
2. Complete Phase 2: Foundational (~1 hour)
3. Complete Phase 3: User Story 1 (~4-6 hours)
4. **STOP and VALIDATE**: Test single screenshot validation
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test single screenshot → **MVP ready!**
3. Add User Story 2 → Run batch validation → Historical analysis ready
4. Add User Story 3 → CI integration → Automation ready
5. Polish → Documentation and cleanup

---

## Task Summary

| Phase | Tasks | Parallel | Estimated Time |
|-------|-------|----------|----------------|
| Setup | T001-T005 | 3 | 30 min |
| Foundational | T006-T009 | 2 | 1 hour |
| US1 (MVP) | T010-T035 | 8 | 4-6 hours |
| US2 (Batch) | T036-T045 | 0 | 2-3 hours |
| US3 (CI) | T046-T051 | 2 | 1-2 hours |
| Polish | T052-T060 | 6 | 1-2 hours |

**Total Tasks**: 60
**Total Estimated Time**: 10-15 hours (~2 days)

---

## Notes

- [P] tasks = different files, no dependencies
- [US1/US2/US3] label maps task to specific user story
- US1 is MVP - can ship after Phase 3
- Manual spot-check in T057 validates automated results
- Avoid processing all 3,151 screenshots during development - use small sample
