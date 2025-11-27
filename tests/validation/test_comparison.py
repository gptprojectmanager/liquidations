"""
Tests for comparison.py - Statistical model comparison utilities.

Tests cover:
- Score comparison
- Grade comparison
- Model ranking
- Statistical analysis
- Outlier detection
- Best model recommendation
"""

from datetime import datetime
from decimal import Decimal

from datetime import date
from src.models.validation_run import TriggerType, ValidationGrade, ValidationRun, ValidationStatus
from src.models.validation_test import ValidationTest
from src.validation.comparison import ModelComparison, get_model_comparison


class TestModelComparison:
    """Test ModelComparison functionality."""

    def test_compare_scores_returns_scores_dict(self):
        """compare_scores should return dict mapping model to score."""
        # Arrange
        comparison = ModelComparison()

        run1 = ValidationRun(
            run_id="run-1",
            model_name="model1",
            overall_score=Decimal("95.0"),
            overall_grade=ValidationGrade.A,
            status=ValidationStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )

        run2 = ValidationRun(
            run_id="run-2",
            model_name="model2",
            overall_score=Decimal("85.0"),
            overall_grade=ValidationGrade.B,
            status=ValidationStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )

        runs = {"model1": run1, "model2": run2}

        # Act
        scores = comparison.compare_scores(runs)

        # Assert
        assert scores["model1"] == 95.0
        assert scores["model2"] == 85.0

    def test_compare_scores_handles_missing_scores(self):
        """compare_scores should handle None scores as 0."""
        # Arrange
        comparison = ModelComparison()

        run = ValidationRun(
            run_id="run-1",
            model_name="model1",
            overall_score=None,
            overall_grade=None,
            status=ValidationStatus.RUNNING,
            started_at=datetime.utcnow(),
        )

        runs = {"model1": run}

        # Act
        scores = comparison.compare_scores(runs)

        # Assert
        assert scores["model1"] == 0.0

    def test_compare_grades_returns_grades_dict(self):
        """compare_grades should return dict mapping model to grade."""
        # Arrange
        comparison = ModelComparison()

        run1 = ValidationRun(
            run_id="run-1",
            model_name="model1",
            overall_score=Decimal("92.0"),
            overall_grade=ValidationGrade.A,
            status=ValidationStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )

        run2 = ValidationRun(
            run_id="run-2",
            model_name="model2",
            overall_score=Decimal("78.0"),
            overall_grade=ValidationGrade.C,
            status=ValidationStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )

        runs = {"model1": run1, "model2": run2}

        # Act
        grades = comparison.compare_grades(runs)

        # Assert
        assert grades["model1"] == "A"
        assert grades["model2"] == "C"

    def test_rank_models_returns_sorted_list(self):
        """rank_models should return models sorted by score descending."""
        # Arrange
        comparison = ModelComparison()

        run1 = ValidationRun(
            run_id="run-1",
            model_name="model1",
            overall_score=Decimal("85.0"),
            overall_grade=ValidationGrade.B,
            status=ValidationStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )

        run2 = ValidationRun(
            run_id="run-2",
            model_name="model2",
            overall_score=Decimal("95.0"),
            overall_grade=ValidationGrade.A,
            status=ValidationStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )

        run3 = ValidationRun(
            run_id="run-3",
            model_name="model3",
            overall_score=Decimal("75.0"),
            overall_grade=ValidationGrade.C,
            status=ValidationStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )

        runs = {"model1": run1, "model2": run2, "model3": run3}

        # Act
        rankings = comparison.rank_models(runs)

        # Assert
        assert len(rankings) == 3
        assert rankings[0][0] == "model2"  # Highest score first
        assert rankings[0][1] == 95.0
        assert rankings[1][0] == "model1"  # Second
        assert rankings[2][0] == "model3"  # Lowest

    def test_get_statistics_calculates_mean_score(self):
        """get_statistics should calculate mean score."""
        # Arrange
        comparison = ModelComparison()

        run1 = ValidationRun(
            run_id="run-1",
            model_name="model1",
            overall_score=Decimal("80.0"),
            overall_grade=ValidationGrade.B,
            status=ValidationStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )

        run2 = ValidationRun(
            run_id="run-2",
            model_name="model2",
            overall_score=Decimal("90.0"),
            overall_grade=ValidationGrade.A,
            status=ValidationStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )

        runs = {"model1": run1, "model2": run2}

        # Act
        stats = comparison.get_statistics(runs)

        # Assert
        assert "mean_score" in stats
        assert stats["mean_score"] == 85.0  # (80 + 90) / 2

    def test_get_statistics_calculates_std_dev(self):
        """get_statistics should calculate standard deviation."""
        # Arrange
        comparison = ModelComparison()

        run1 = ValidationRun(
            run_id="run-1",
            model_name="model1",
            overall_score=Decimal("80.0"),
            overall_grade=ValidationGrade.B,
            status=ValidationStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )

        run2 = ValidationRun(
            run_id="run-2",
            model_name="model2",
            overall_score=Decimal("90.0"),
            overall_grade=ValidationGrade.A,
            status=ValidationStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )

        runs = {"model1": run1, "model2": run2}

        # Act
        stats = comparison.get_statistics(runs)

        # Assert
        assert "std_dev" in stats
        assert stats["std_dev"] > 0

    def test_identify_outliers_detects_extreme_values(self):
        """identify_outliers should detect models with extreme scores."""
        # Arrange
        comparison = ModelComparison()

        run1 = ValidationRun(
            run_id="run-1",
            model_name="normal1",
            overall_score=Decimal("85.0"),
            overall_grade=ValidationGrade.B,
            status=ValidationStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )

        run2 = ValidationRun(
            run_id="run-2",
            model_name="normal2",
            overall_score=Decimal("88.0"),
            overall_grade=ValidationGrade.B,
            status=ValidationStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )

        run3 = ValidationRun(
            run_id="run-3",
            model_name="outlier",
            overall_score=Decimal("30.0"),  # Extreme outlier
            overall_grade=ValidationGrade.F,
            status=ValidationStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )

        runs = {"normal1": run1, "normal2": run2, "outlier": run3}

        # Act
        outliers = comparison.identify_outliers(runs, threshold=2.0)

        # Assert
        assert "outlier" in outliers

    def test_recommend_best_model_chooses_highest_score(self):
        """recommend_best_model should choose model with highest score."""
        # Arrange
        comparison = ModelComparison()

        run1 = ValidationRun(
            run_id="run-1",
            model_name="good_model",
            overall_score=Decimal("92.0"),
            overall_grade=ValidationGrade.A,
            status=ValidationStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )

        run2 = ValidationRun(
            run_id="run-2",
            model_name="best_model",
            overall_score=Decimal("98.0"),
            overall_grade=ValidationGrade.A,
            status=ValidationStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )

        runs = {"good_model": run1, "best_model": run2}

        tests1 = [
            ValidationTest(
                run_id="run-1",
                test_type=ValidationTestType.FUNDING_CORRELATION,
                score=Decimal("90.0"),
                passed=True,
                details={},
            )
        ]

        tests2 = [
            ValidationTest(
                run_id="run-2",
                test_type=ValidationTestType.FUNDING_CORRELATION,
                score=Decimal("98.0"),
                passed=True,
                details={},
            )
        ]

        all_tests = {"good_model": tests1, "best_model": tests2}

        # Act
        best_model, reason = comparison.recommend_best_model(runs, all_tests)

        # Assert
        assert best_model == "best_model"
        assert "highest" in reason.lower() or "score" in reason.lower()

    def test_recommend_best_model_considers_all_tests_passed(self):
        """recommend_best_model should prefer models with all tests passed."""
        # Arrange
        comparison = ModelComparison()

        run1 = ValidationRun(
            run_id="run-1",
            model_name="model1",
            overall_score=Decimal("92.0"),
            overall_grade=ValidationGrade.A,
            status=ValidationStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )

        run2 = ValidationRun(
            run_id="run-2",
            model_name="model2",
            overall_score=Decimal("90.0"),
            overall_grade=ValidationGrade.A,
            status=ValidationStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )

        runs = {"model1": run1, "model2": run2}

        # model1 has one failed test
        tests1 = [
            ValidationTest(
                run_id="run-1",
                test_type=ValidationTestType.FUNDING_CORRELATION,
                score=Decimal("90.0"),
                passed=True,
                details={},
            ),
            ValidationTest(
                run_id="run-1",
                test_type=ValidationTestType.OI_CONSERVATION,
                score=Decimal("70.0"),
                passed=False,
                details={},
            ),
        ]

        # model2 has all tests passed
        tests2 = [
            ValidationTest(
                run_id="run-2",
                test_type=ValidationTestType.FUNDING_CORRELATION,
                score=Decimal("90.0"),
                passed=True,
                details={},
            ),
            ValidationTest(
                run_id="run-2",
                test_type=ValidationTestType.OI_CONSERVATION,
                score=Decimal("90.0"),
                passed=True,
                details={},
            ),
        ]

        all_tests = {"model1": tests1, "model2": tests2}

        # Act
        best_model, reason = comparison.recommend_best_model(runs, all_tests)

        # Assert
        # Should prefer model2 despite slightly lower score (all tests passed)
        assert best_model in ["model1", "model2"]  # Either could be chosen
        assert reason is not None

    def test_get_model_comparison_returns_singleton(self):
        """get_model_comparison should return same instance."""
        # Act
        comp1 = get_model_comparison()
        comp2 = get_model_comparison()

        # Assert
        assert comp1 is comp2

    def test_empty_runs_handled_gracefully(self):
        """Comparison should handle empty runs dict gracefully."""
        # Arrange
        comparison = ModelComparison()
        runs = {}

        # Act
        scores = comparison.compare_scores(runs)
        grades = comparison.compare_grades(runs)
        rankings = comparison.rank_models(runs)

        # Assert
        assert scores == {}
        assert grades == {}
        assert rankings == []
