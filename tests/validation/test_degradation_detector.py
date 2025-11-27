"""
Tests for degradation_detector.py - Performance degradation detection.

Tests cover:
- Severity level detection (NONE, MINOR, MODERATE, SEVERE, CRITICAL)
- Baseline vs recent comparison
- Grade degradation detection
- Threshold configuration
"""

from datetime import datetime, timedelta

from src.validation.trends.degradation_detector import (
    DegradationDetector,
    DegradationSeverity,
    get_degradation_detector,
)


class TestDegradationDetector:
    """Test DegradationDetector functionality."""

    def test_no_degradation_when_scores_stable(self):
        """Degradation should be NONE when scores are stable."""
        # Arrange
        detector = DegradationDetector(lookback_days=30)

        start = datetime.utcnow() - timedelta(days=60)
        # Stable scores around 90
        scores = [
            (start + timedelta(days=i), 90.0 + (i % 3 - 1) * 2.0)  # Oscillate 88-92
            for i in range(60)
        ]

        # Act
        result = detector.detect_score_degradation(scores)

        # Assert
        assert result["degradation_detected"] is False
        assert result["severity"] == DegradationSeverity.NONE

    def test_minor_degradation_detected(self):
        """MINOR degradation should be detected for 5-10% drop."""
        # Arrange
        detector = DegradationDetector(
            lookback_days=30,
            minor_threshold=5.0,
            moderate_threshold=10.0,
        )

        start = datetime.utcnow() - timedelta(days=60)
        # Baseline: 100, Recent: 93 (7% drop = MINOR)
        scores = (
            [(start + timedelta(days=i), 100.0) for i in range(30)]  # Baseline: 100
            + [(start + timedelta(days=30 + i), 93.0) for i in range(30)]  # Recent: 93
        )

        # Act
        result = detector.detect_score_degradation(scores)

        # Assert
        assert result["degradation_detected"] is True
        assert result["severity"] == DegradationSeverity.MINOR
        assert abs(result["degradation_percent"] - 7.0) < 0.5

    def test_moderate_degradation_detected(self):
        """MODERATE degradation should be detected for 10-15% drop."""
        # Arrange
        detector = DegradationDetector(
            lookback_days=30,
            moderate_threshold=10.0,
            severe_threshold=15.0,
        )

        start = datetime.utcnow() - timedelta(days=60)
        # Baseline: 100, Recent: 88 (12% drop = MODERATE)
        scores = [(start + timedelta(days=i), 100.0) for i in range(30)] + [
            (start + timedelta(days=30 + i), 88.0) for i in range(30)
        ]

        # Act
        result = detector.detect_score_degradation(scores)

        # Assert
        assert result["degradation_detected"] is True
        assert result["severity"] == DegradationSeverity.MODERATE
        assert abs(result["degradation_percent"] - 12.0) < 0.5

    def test_severe_degradation_detected(self):
        """SEVERE degradation should be detected for 15-25% drop."""
        # Arrange
        detector = DegradationDetector(
            lookback_days=30,
            severe_threshold=15.0,
            critical_threshold=25.0,
        )

        start = datetime.utcnow() - timedelta(days=60)
        # Baseline: 100, Recent: 80 (20% drop = SEVERE)
        scores = [(start + timedelta(days=i), 100.0) for i in range(30)] + [
            (start + timedelta(days=30 + i), 80.0) for i in range(30)
        ]

        # Act
        result = detector.detect_score_degradation(scores)

        # Assert
        assert result["degradation_detected"] is True
        assert result["severity"] == DegradationSeverity.SEVERE
        assert abs(result["degradation_percent"] - 20.0) < 0.5

    def test_critical_degradation_detected(self):
        """CRITICAL degradation should be detected for >25% drop."""
        # Arrange
        detector = DegradationDetector(
            lookback_days=30,
            critical_threshold=25.0,
        )

        start = datetime.utcnow() - timedelta(days=60)
        # Baseline: 100, Recent: 70 (30% drop = CRITICAL)
        scores = [(start + timedelta(days=i), 100.0) for i in range(30)] + [
            (start + timedelta(days=30 + i), 70.0) for i in range(30)
        ]

        # Act
        result = detector.detect_score_degradation(scores)

        # Assert
        assert result["degradation_detected"] is True
        assert result["severity"] == DegradationSeverity.CRITICAL
        assert abs(result["degradation_percent"] - 30.0) < 0.5

    def test_baseline_and_recent_averages_calculated(self):
        """Result should include baseline and recent averages."""
        # Arrange
        detector = DegradationDetector(lookback_days=30)

        start = datetime.utcnow() - timedelta(days=60)
        scores = (
            [(start + timedelta(days=i), 95.0) for i in range(30)]  # Baseline
            + [(start + timedelta(days=30 + i), 85.0) for i in range(30)]  # Recent
        )

        # Act
        result = detector.detect_score_degradation(scores)

        # Assert
        assert "baseline_avg" in result
        assert "recent_avg" in result
        assert abs(result["baseline_avg"] - 95.0) < 0.1
        assert abs(result["recent_avg"] - 85.0) < 0.1

    def test_detect_grade_degradation_detects_f_increase(self):
        """detect_grade_degradation should detect increase in F grades."""
        # Arrange
        detector = DegradationDetector(lookback_days=30)

        start = datetime.utcnow() - timedelta(days=60)
        # Baseline: mostly A grades, Recent: mostly F grades
        grades = (
            [(start + timedelta(days=i), "A") for i in range(30)]  # Baseline
            + [(start + timedelta(days=30 + i), "F") for i in range(30)]  # Recent
        )

        # Act
        result = detector.detect_grade_degradation(grades)

        # Assert
        assert result["degradation_detected"] is True
        assert "severity" in result

    def test_insufficient_baseline_data(self):
        """Should handle cases with insufficient baseline data."""
        # Arrange
        detector = DegradationDetector(lookback_days=30)

        start = datetime.utcnow() - timedelta(days=15)
        scores = [(start + timedelta(days=i), 90.0) for i in range(15)]  # Only 15 days

        # Act
        result = detector.detect_score_degradation(scores)

        # Assert
        # Should handle gracefully (may be insufficient data)
        assert "degradation_detected" in result

    def test_get_degradation_detector_returns_singleton(self):
        """get_degradation_detector should return same instance."""
        # Act
        detector1 = get_degradation_detector()
        detector2 = get_degradation_detector()

        # Assert
        assert detector1 is detector2


class TestDegradationSeverity:
    """Test DegradationSeverity enum."""

    def test_severity_values(self):
        """DegradationSeverity should have expected values."""
        # Assert
        assert DegradationSeverity.NONE == "none"
        assert DegradationSeverity.MINOR == "minor"
        assert DegradationSeverity.MODERATE == "moderate"
        assert DegradationSeverity.SEVERE == "severe"
        assert DegradationSeverity.CRITICAL == "critical"
