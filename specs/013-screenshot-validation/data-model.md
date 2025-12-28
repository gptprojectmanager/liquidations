# Data Model: Screenshot Validation Pipeline

**Feature**: 013-screenshot-validation
**Date**: 2025-12-28

## Entities

### 1. Screenshot

Represents a Coinglass heatmap screenshot file.

```python
@dataclass
class Screenshot:
    """Coinglass heatmap screenshot metadata."""

    path: str                   # Absolute file path
    filename: str               # e.g., "coinglass_btc_m1_1month_20251030_145708.png"
    symbol: str                 # "BTC" or "ETH"
    leverage: str               # "m1", "m3", etc.
    timeframe: str              # "1month", "1week", "3month"
    timestamp: datetime         # Extracted from filename
    resolution: tuple[int, int] # (width, height) in pixels

    @classmethod
    def from_path(cls, path: str) -> "Screenshot":
        """Create Screenshot from file path."""
        filename = os.path.basename(path)
        parsed = parse_filename(filename)

        # Get resolution
        with Image.open(path) as img:
            resolution = img.size

        return cls(
            path=path,
            filename=filename,
            symbol=parsed["symbol"],
            leverage=parsed["leverage"],
            timeframe=parsed["timeframe"],
            timestamp=parsed["timestamp"],
            resolution=resolution
        )
```

**Validation Rules**:
- `path`: Must exist and be readable PNG file
- `filename`: Must match pattern `coinglass_{symbol}_{leverage}_{timeframe}_{date}_{time}.png`
- `symbol`: Must be "BTC" or "ETH"
- `timestamp`: Must be valid datetime in past

---

### 2. ExtractedPriceLevels

OCR extraction result from a screenshot.

```python
@dataclass
class ExtractedPriceLevels:
    """Price levels extracted via OCR from screenshot."""

    screenshot_path: str
    long_zones: list[float]      # Prices below current (liquidation longs)
    short_zones: list[float]     # Prices above current (liquidation shorts)
    current_price: float | None  # Current BTC/ETH price (if detectable)
    confidence: float            # OCR confidence score (0-1)
    extraction_method: str       # "pytesseract", "easyocr", or "hybrid"
    processing_time_ms: int      # Extraction time in milliseconds

    @property
    def all_zones(self) -> list[float]:
        """All extracted price levels."""
        return sorted(set(self.long_zones + self.short_zones))

    @property
    def is_valid(self) -> bool:
        """Check if extraction produced usable results."""
        return (
            len(self.all_zones) >= 2 and
            self.confidence >= 0.5
        )
```

**Validation Rules**:
- `confidence`: Must be 0.0-1.0
- `long_zones`: Prices should be < current_price (if known)
- `short_zones`: Prices should be > current_price (if known)
- `extraction_method`: One of ["pytesseract", "easyocr", "hybrid"]

---

### 3. APIPriceLevels

Heatmap data from our API.

```python
@dataclass
class APIPriceLevels:
    """Price levels from our heatmap API."""

    symbol: str                  # "BTCUSDT" or "ETHUSDT"
    timestamp: datetime          # API query timestamp
    long_zones: list[dict]       # [{"price": float, "volume": float}, ...]
    short_zones: list[dict]      # [{"price": float, "volume": float}, ...]
    total_long_volume: float     # Sum of long liquidation volumes
    total_short_volume: float    # Sum of short liquidation volumes

    @classmethod
    def from_api_response(cls, response: dict) -> "APIPriceLevels":
        """Parse API response into structured data."""
        meta = response.get("meta", {})

        # Extract high-density zones (top 20% by volume)
        levels = response.get("data", [{}])[0].get("levels", [])
        sorted_levels = sorted(levels, key=lambda x: x.get("volume", 0), reverse=True)
        top_20_count = max(1, len(sorted_levels) // 5)
        high_density = sorted_levels[:top_20_count]

        # Classify by side
        current_price = meta.get("current_price", 0)
        long_zones = [z for z in high_density if z["price"] < current_price]
        short_zones = [z for z in high_density if z["price"] > current_price]

        return cls(
            symbol=meta.get("symbol", ""),
            timestamp=datetime.fromisoformat(meta.get("timestamp", "")),
            long_zones=long_zones,
            short_zones=short_zones,
            total_long_volume=meta.get("total_long_volume", 0),
            total_short_volume=meta.get("total_short_volume", 0)
        )

    @property
    def all_prices(self) -> list[float]:
        """All price levels."""
        return [z["price"] for z in self.long_zones + self.short_zones]
```

---

### 4. ValidationResult

Per-screenshot comparison result.

```python
@dataclass
class ValidationResult:
    """Comparison result for a single screenshot."""

    screenshot_path: str
    timestamp: datetime
    symbol: str
    status: str                  # "success", "ocr_failed", "api_failed", "no_match"

    # OCR results
    ocr_confidence: float
    ocr_long_zones: list[float]
    ocr_short_zones: list[float]

    # API results
    api_long_zones: list[dict]
    api_short_zones: list[dict]

    # Comparison metrics
    hit_rate: float              # Overall match rate (0-1)
    long_hit_rate: float         # Long zones match rate
    short_hit_rate: float        # Short zones match rate
    matched_zones: list[dict]    # [{"coinglass": float, "api": float, "error_pct": float}]
    missed_zones: list[float]    # Coinglass zones not in API
    extra_zones: list[dict]      # API zones not in Coinglass

    # Metadata
    processing_time_ms: int
    tolerance_pct: float

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "screenshot": self.screenshot_path,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "status": self.status,
            "ocr_confidence": self.ocr_confidence,
            "coinglass_zones": {
                "long": self.ocr_long_zones,
                "short": self.ocr_short_zones
            },
            "api_zones": {
                "long": self.api_long_zones,
                "short": self.api_short_zones
            },
            "comparison": {
                "hit_rate": self.hit_rate,
                "long_hit_rate": self.long_hit_rate,
                "short_hit_rate": self.short_hit_rate,
                "matched": self.matched_zones,
                "missed": self.missed_zones,
                "extra": self.extra_zones
            },
            "processing_time_ms": self.processing_time_ms,
            "tolerance_pct": self.tolerance_pct
        }
```

**State Transitions**:
```
Screenshot → OCR Extraction → API Fetch → Comparison → ValidationResult

Status flow:
  "pending" → "processing" → "success" | "ocr_failed" | "api_failed" | "no_match"
```

---

### 5. AggregateMetrics

Overall validation statistics.

```python
@dataclass
class AggregateMetrics:
    """Aggregate statistics across all screenshots."""

    total_screenshots: int
    processed: int
    ocr_failures: int
    api_failures: int

    # Hit rate statistics
    avg_hit_rate: float
    median_hit_rate: float
    std_hit_rate: float
    min_hit_rate: float
    max_hit_rate: float

    # Pass/fail counts
    pass_count: int              # hit_rate >= threshold
    fail_count: int              # hit_rate < threshold
    pass_rate: float             # pass_count / processed

    # Distribution
    hit_rate_distribution: dict  # {"0-25%": int, "25-50%": int, ...}

    # By symbol breakdown
    by_symbol: dict              # {"BTC": {...}, "ETH": {...}}

    # Time range
    earliest_timestamp: datetime
    latest_timestamp: datetime

    # Performance
    total_processing_time_ms: int
    avg_processing_time_ms: float

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "total_screenshots": self.total_screenshots,
            "processed": self.processed,
            "ocr_failures": self.ocr_failures,
            "ocr_failure_rate": self.ocr_failures / self.total_screenshots if self.total_screenshots else 0,
            "api_failures": self.api_failures,
            "metrics": {
                "avg_hit_rate": self.avg_hit_rate,
                "median_hit_rate": self.median_hit_rate,
                "std_hit_rate": self.std_hit_rate,
                "min_hit_rate": self.min_hit_rate,
                "max_hit_rate": self.max_hit_rate,
                "pass_rate": self.pass_rate,
                "hit_rate_distribution": self.hit_rate_distribution
            },
            "by_symbol": self.by_symbol,
            "timestamp_range": {
                "earliest": self.earliest_timestamp.isoformat(),
                "latest": self.latest_timestamp.isoformat()
            },
            "performance": {
                "total_time_ms": self.total_processing_time_ms,
                "avg_time_ms": self.avg_processing_time_ms
            }
        }
```

---

## Relationships

```
Screenshot (1) ──extracts──▶ (1) ExtractedPriceLevels
     │
     │ timestamp
     ▼
APIPriceLevels (1) ◀──matches──(1) Screenshot
     │
     │ compares
     ▼
ValidationResult (1) ◀──produces──(1) Screenshot + ExtractedPriceLevels + APIPriceLevels
     │
     │ aggregates
     ▼
AggregateMetrics (1) ◀──summarizes──(N) ValidationResult
```

---

## Storage Format

### Input: Screenshots

```
/media/sam/1TB/N8N_dev/screenshots/
├── coinglass_btc_m1_1month_20251030_145708.png
├── coinglass_btc_m1_1month_20251030_160122.png
├── coinglass_eth_m1_1month_20251030_145715.png
└── ... (3,151 files)
```

### Output: Validation Results

**Per-screenshot (JSONL)**:
```
data/validation/screenshot_results.jsonl
```

Each line is a `ValidationResult.to_dict()` JSON object.

**Aggregate Summary (JSON)**:
```
data/validation/screenshot_summary.json
```

Single `AggregateMetrics.to_dict()` JSON object.
