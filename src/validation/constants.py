"""
Validation suite configuration constants.

Defines thresholds, parameters, and settings for the liquidation model
validation framework.
"""

from decimal import Decimal
from typing import Dict, List

# ============================================================================
# Time Windows
# ============================================================================

# Historical data window for validation (days)
VALIDATION_WINDOW_DAYS = 30

# Data retention period (days)
DATA_RETENTION_DAYS = 90

# Validation execution schedule
VALIDATION_CRON_DAY = 6  # Sunday (0=Monday, 6=Sunday)
VALIDATION_CRON_HOUR = 2  # 2 AM UTC
VALIDATION_CRON_MINUTE = 0

# ============================================================================
# Grading System
# ============================================================================

# Grade thresholds (score percentages)
GRADE_A_MIN = Decimal("0.90")  # 90%+
GRADE_B_MIN = Decimal("0.80")  # 80-89%
GRADE_C_MIN = Decimal("0.70")  # 70-79%
# Below 70% = F

# Grade labels
GRADE_A = "A"
GRADE_B = "B"
GRADE_C = "C"
GRADE_F = "F"

# Alert trigger grades (send notifications)
ALERT_GRADES = [GRADE_C, GRADE_F]

# ============================================================================
# Statistical Test Parameters
# ============================================================================

# Funding Rate Correlation Test
FUNDING_CORRELATION_MIN_ACCEPTABLE = Decimal("0.70")  # Minimum correlation coefficient
FUNDING_CORRELATION_P_VALUE_MAX = Decimal("0.05")  # Statistical significance threshold

# Open Interest Conservation Test
OI_CONSERVATION_ERROR_MAX = Decimal("0.01")  # Maximum 1% error tolerance

# Directional Positioning Test
DIRECTIONAL_ACCURACY_MIN = Decimal("0.95")  # 95% directional correctness

# ============================================================================
# Test Weights (for overall score calculation)
# ============================================================================

TEST_WEIGHTS: Dict[str, Decimal] = {
    "funding_correlation": Decimal("0.40"),  # 40% weight
    "oi_conservation": Decimal("0.35"),  # 35% weight
    "directional_positioning": Decimal("0.25"),  # 25% weight
}

# Verify weights sum to 1.0
assert sum(TEST_WEIGHTS.values()) == Decimal("1.0"), "Test weights must sum to 1.0"

# ============================================================================
# Performance Limits
# ============================================================================

# Maximum validation execution time (seconds)
MAX_VALIDATION_DURATION = 300  # 5 minutes

# Maximum report generation time (seconds)
MAX_REPORT_GENERATION_TIME = 10

# Maximum dashboard query time (seconds)
MAX_DASHBOARD_QUERY_TIME = 3

# Maximum memory usage during validation (GB)
MAX_MEMORY_USAGE_GB = 2

# ============================================================================
# Queue Management
# ============================================================================

# Maximum concurrent validation runs
MAX_CONCURRENT_VALIDATIONS = 1

# Maximum queue size for manual triggers
MAX_QUEUE_SIZE = 10

# Queue timeout (seconds)
QUEUE_TIMEOUT = 3600  # 1 hour

# ============================================================================
# Data Quality
# ============================================================================

# Minimum data completeness for valid test (percentage)
MIN_DATA_COMPLETENESS = Decimal("0.80")  # 80% of expected data points

# Maximum allowed data gap (hours)
MAX_DATA_GAP_HOURS = 6

# ============================================================================
# API Rate Limits
# ============================================================================

# Binance API rate limit (requests per minute)
BINANCE_API_RATE_LIMIT = 1200

# Request throttling delay (seconds)
API_REQUEST_DELAY = 0.05  # 50ms between requests

# ============================================================================
# Retry Configuration
# ============================================================================

# Maximum retry attempts for transient failures
MAX_RETRY_ATTEMPTS = 3

# Exponential backoff base (seconds)
RETRY_BACKOFF_BASE = 2

# Maximum backoff time (seconds)
MAX_BACKOFF_TIME = 60

# ============================================================================
# Report Configuration
# ============================================================================

# Supported report formats
REPORT_FORMATS: List[str] = ["json", "text", "html"]

# Default report format
DEFAULT_REPORT_FORMAT = "json"

# Report storage path
REPORT_STORAGE_PATH = "data/validation/reports"

# ============================================================================
# Alert Configuration
# ============================================================================

# Alert channels
ALERT_CHANNELS: List[str] = ["email", "slack", "webhook"]

# Default alert channel
DEFAULT_ALERT_CHANNEL = "email"

# Alert suppression window (hours) - don't send duplicate alerts
ALERT_SUPPRESSION_WINDOW = 24

# ============================================================================
# Database Configuration
# ============================================================================

# DuckDB database path for validation results
VALIDATION_DB_PATH = "data/validation/validation_results.duckdb"

# Table names
TABLE_VALIDATION_RUNS = "validation_runs"
TABLE_VALIDATION_TESTS = "validation_tests"
TABLE_VALIDATION_REPORTS = "validation_reports"
TABLE_HISTORICAL_TRENDS = "historical_trends"

# ============================================================================
# Logging Configuration
# ============================================================================

# Log level for validation module
LOG_LEVEL = "INFO"

# Log file path
LOG_FILE_PATH = "logs/validation.log"

# Log rotation settings
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5
