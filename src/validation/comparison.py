"""
Model comparison utilities for validation.

Provides tools for comparing validation results across multiple models.
"""

from typing import Dict, List, Optional

from src.models.validation_run import ValidationRun
from src.models.validation_test import ValidationTest
from src.validation.logger import logger


class ModelComparison:
    """
    Compares validation results across multiple models.

    Analyzes performance differences and generates insights.
    """

    def __init__(self):
        """Initialize model comparison."""
        logger.info("ModelComparison initialized")

    def compare_scores(
        self,
        runs: Dict[str, ValidationRun],
    ) -> Dict[str, float]:
        """
        Compare overall scores across models.

        Args:
            runs: Dict mapping model_name to ValidationRun

        Returns:
            Dict mapping model_name to overall_score
        """
        scores = {}

        for model_name, run in runs.items():
            score = float(run.overall_score) if run.overall_score else 0.0
            scores[model_name] = score

        logger.info(f"Compared scores for {len(scores)} models")
        return scores

    def compare_grades(
        self,
        runs: Dict[str, ValidationRun],
    ) -> Dict[str, str]:
        """
        Compare grades across models.

        Args:
            runs: Dict mapping model_name to ValidationRun

        Returns:
            Dict mapping model_name to grade
        """
        grades = {}

        for model_name, run in runs.items():
            grade = run.overall_grade.value if run.overall_grade else "N/A"
            grades[model_name] = grade

        logger.info(f"Compared grades for {len(grades)} models")
        return grades

    def compare_test_performance(
        self,
        tests: Dict[str, List[ValidationTest]],
        test_type: str,
    ) -> Dict[str, Optional[float]]:
        """
        Compare performance on specific test type.

        Args:
            tests: Dict mapping model_name to List[ValidationTest]
            test_type: Test type to compare

        Returns:
            Dict mapping model_name to test score
        """
        scores = {}

        for model_name, model_tests in tests.items():
            # Find test of specified type
            test = next(
                (t for t in model_tests if t.test_type and t.test_type.value == test_type),
                None,
            )

            if test:
                scores[model_name] = float(test.score)
            else:
                scores[model_name] = None

        logger.info(f"Compared {test_type} performance for {len(scores)} models")
        return scores

    def rank_models(
        self,
        runs: Dict[str, ValidationRun],
    ) -> List[tuple[str, float, str]]:
        """
        Rank models by overall score.

        Args:
            runs: Dict mapping model_name to ValidationRun

        Returns:
            List of (model_name, score, grade) tuples, sorted by score descending
        """
        rankings = []

        for model_name, run in runs.items():
            score = float(run.overall_score) if run.overall_score else 0.0
            grade = run.overall_grade.value if run.overall_grade else "N/A"
            rankings.append((model_name, score, grade))

        # Sort by score descending
        rankings.sort(key=lambda x: x[1], reverse=True)

        logger.info(f"Ranked {len(rankings)} models by score")
        return rankings

    def calculate_score_delta(
        self,
        model_a: str,
        model_b: str,
        runs: Dict[str, ValidationRun],
    ) -> Optional[float]:
        """
        Calculate score difference between two models.

        Args:
            model_a: First model name
            model_b: Second model name
            runs: Dict mapping model_name to ValidationRun

        Returns:
            Score delta (model_a - model_b), or None if models not found
        """
        run_a = runs.get(model_a)
        run_b = runs.get(model_b)

        if not run_a or not run_b:
            logger.warning("Cannot calculate delta - model not found")
            return None

        score_a = float(run_a.overall_score) if run_a.overall_score else 0.0
        score_b = float(run_b.overall_score) if run_b.overall_score else 0.0

        delta = score_a - score_b

        logger.info(
            f"Score delta: {model_a} vs {model_b} = {delta:.2f} ({score_a:.2f} - {score_b:.2f})"
        )

        return delta

    def identify_outliers(
        self,
        runs: Dict[str, ValidationRun],
        threshold: float = 2.0,
    ) -> List[str]:
        """
        Identify models with outlier scores (using standard deviation).

        Args:
            runs: Dict mapping model_name to ValidationRun
            threshold: Number of standard deviations for outlier (default: 2.0)

        Returns:
            List of model names with outlier scores
        """
        if len(runs) < 3:
            logger.warning("Need at least 3 models to identify outliers")
            return []

        # Calculate mean and std dev
        scores = [float(run.overall_score) if run.overall_score else 0.0 for run in runs.values()]

        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        std_dev = variance**0.5

        # Find outliers
        outliers = []
        for model_name, run in runs.items():
            score = float(run.overall_score) if run.overall_score else 0.0
            z_score = (score - mean) / std_dev if std_dev > 0 else 0

            if abs(z_score) > threshold:
                outliers.append(model_name)
                logger.info(
                    f"Outlier detected: {model_name} (score={score:.2f}, z-score={z_score:.2f})"
                )

        return outliers

    def get_statistics(
        self,
        runs: Dict[str, ValidationRun],
    ) -> dict:
        """
        Calculate statistical summary of model scores.

        Args:
            runs: Dict mapping model_name to ValidationRun

        Returns:
            Dict with statistical measures
        """
        if not runs:
            return {}

        scores = [float(run.overall_score) if run.overall_score else 0.0 for run in runs.values()]

        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        std_dev = variance**0.5

        sorted_scores = sorted(scores)
        median = (
            sorted_scores[len(sorted_scores) // 2]
            if len(sorted_scores) % 2 != 0
            else (
                sorted_scores[len(sorted_scores) // 2 - 1] + sorted_scores[len(sorted_scores) // 2]
            )
            / 2
        )

        stats = {
            "count": len(scores),
            "mean": mean,
            "median": median,
            "std_dev": std_dev,
            "min": min(scores),
            "max": max(scores),
            "range": max(scores) - min(scores),
        }

        logger.info(
            f"Statistics calculated for {len(scores)} models: mean={mean:.2f}, std_dev={std_dev:.2f}"
        )

        return stats

    def recommend_best_model(
        self,
        runs: Dict[str, ValidationRun],
        tests: Dict[str, List[ValidationTest]],
    ) -> tuple[str, str]:
        """
        Recommend best model based on multiple criteria.

        Args:
            runs: Dict mapping model_name to ValidationRun
            tests: Dict mapping model_name to List[ValidationTest]

        Returns:
            Tuple of (model_name, recommendation_reason)
        """
        if not runs:
            return None, "No models to compare"

        # Criteria 1: Highest overall score
        best_by_score = max(
            runs.items(),
            key=lambda x: float(x[1].overall_score) if x[1].overall_score else 0,
        )

        # Criteria 2: All tests passed
        all_pass_models = []
        for model_name, model_tests in tests.items():
            if all(t.passed for t in model_tests):
                all_pass_models.append(model_name)

        # Criteria 3: Grade A
        grade_a_models = [
            name
            for name, run in runs.items()
            if run.overall_grade and run.overall_grade.value == "A"
        ]

        # Decision logic
        if best_by_score[0] in grade_a_models and best_by_score[0] in all_pass_models:
            reason = (
                f"Highest score ({best_by_score[1].overall_score:.2f}), grade A, all tests passed"
            )
            return best_by_score[0], reason

        elif best_by_score[0] in grade_a_models:
            reason = f"Highest score ({best_by_score[1].overall_score:.2f}), grade A"
            return best_by_score[0], reason

        else:
            reason = f"Highest score ({best_by_score[1].overall_score:.2f})"
            return best_by_score[0], reason


# Global comparison instance
_global_comparison: Optional[ModelComparison] = None


def get_model_comparison() -> ModelComparison:
    """
    Get global model comparison instance (singleton).

    Returns:
        ModelComparison instance
    """
    global _global_comparison

    if _global_comparison is None:
        _global_comparison = ModelComparison()

    return _global_comparison
