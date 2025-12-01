"""
Report storage interface for validation suite.

Handles persistence of validation results to DuckDB.
"""

from typing import Optional

import duckdb

from src.models.validation_report import ValidationReport
from src.models.validation_run import ValidationRun
from src.models.validation_test import ValidationTest
from src.validation.constants import VALIDATION_DB_PATH
from src.validation.exceptions import StorageError
from src.validation.logger import logger


class ValidationStorage:
    """
    Storage interface for validation results.

    Persists ValidationRun, ValidationTest, and ValidationReport
    objects to DuckDB database.
    """

    def __init__(self, db_path: str = VALIDATION_DB_PATH):
        """
        Initialize storage interface.

        Args:
            db_path: Path to validation database
        """
        self.db_path = db_path
        self.conn: Optional[duckdb.DuckDBPyConnection] = None

    def connect(self):
        """Establish database connection."""
        if self.conn is None:
            try:
                self.conn = duckdb.connect(self.db_path)
                logger.debug(f"Connected to validation database: {self.db_path}")
            except Exception as e:
                raise StorageError(f"Failed to connect to database: {e}")

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.debug("Closed validation database connection")

    def init_schema(self):
        """
        Initialize database schema.

        Executes schema creation SQL if tables don't exist.
        """
        self.connect()

        try:
            # Load and execute schema SQL
            schema_path = "src/validation/db/migrations/001_create_validation_tables.sql"
            with open(schema_path, "r") as f:
                schema_sql = f.read()

            self.conn.execute(schema_sql)
            logger.info("Validation database schema initialized")

        except Exception as e:
            raise StorageError(f"Failed to initialize schema: {e}")

    def save_run(self, run: ValidationRun) -> None:
        """
        Save validation run to database.

        Args:
            run: ValidationRun instance to save
        """
        self.connect()

        try:
            # Convert Pydantic model to dict
            run_dict = run.model_dump()

            # Insert into validation_runs table
            self.conn.execute(
                """
                INSERT INTO validation_runs (
                    run_id, model_name, trigger_type, triggered_by,
                    started_at, completed_at, duration_seconds,
                    status, error_message,
                    data_start_date, data_end_date, data_completeness,
                    overall_grade, overall_score,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    run_dict["run_id"],
                    run_dict["model_name"],
                    run_dict["trigger_type"].value
                    if hasattr(run_dict["trigger_type"], "value")
                    else run_dict["trigger_type"],
                    run_dict.get("triggered_by"),
                    run_dict["started_at"],
                    run_dict.get("completed_at"),
                    run_dict.get("duration_seconds"),
                    run_dict["status"].value
                    if hasattr(run_dict["status"], "value")
                    else run_dict["status"],
                    run_dict.get("error_message"),
                    run_dict["data_start_date"],
                    run_dict["data_end_date"],
                    run_dict.get("data_completeness"),
                    run_dict.get("overall_grade"),
                    run_dict.get("overall_score"),
                    run_dict["created_at"],
                    run_dict["updated_at"],
                ],
            )

            logger.info(f"Saved validation run: {run.run_id}")

        except Exception as e:
            raise StorageError(f"Failed to save validation run: {e}")

    def save_test(self, test: ValidationTest) -> None:
        """
        Save validation test result to database.

        Args:
            test: ValidationTest instance to save
        """
        self.connect()

        try:
            test_dict = test.model_dump()

            self.conn.execute(
                """
                INSERT INTO validation_tests (
                    test_id, run_id, test_type, test_name,
                    passed, score, weight,
                    primary_metric, secondary_metric,
                    diagnostics, error_message,
                    executed_at, duration_ms, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    test_dict["test_id"],
                    test_dict["run_id"],
                    test_dict["test_type"].value
                    if hasattr(test_dict["test_type"], "value")
                    else test_dict["test_type"],
                    test_dict["test_name"],
                    test_dict["passed"],
                    test_dict["score"],
                    test_dict["weight"],
                    test_dict.get("primary_metric"),
                    test_dict.get("secondary_metric"),
                    test_dict.get("diagnostics"),  # JSON column
                    test_dict.get("error_message"),
                    test_dict["executed_at"],
                    test_dict.get("duration_ms"),
                    test_dict["created_at"],
                ],
            )

            logger.debug(f"Saved validation test: {test.test_id}")

        except Exception as e:
            raise StorageError(f"Failed to save validation test: {e}")

    def save_report(self, report: ValidationReport) -> None:
        """
        Save validation report to database.

        Args:
            report: ValidationReport instance to save
        """
        self.connect()

        try:
            report_dict = report.model_dump()

            self.conn.execute(
                """
                INSERT INTO validation_reports (
                    report_id, run_id, format, report_content,
                    summary, recommendations,
                    alert_sent, alert_sent_at, alert_recipients,
                    generated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    report_dict["report_id"],
                    report_dict["run_id"],
                    report_dict["format"].value
                    if hasattr(report_dict["format"], "value")
                    else report_dict["format"],
                    report_dict["report_content"],
                    report_dict["summary"],  # JSON column
                    report_dict["recommendations"],  # JSON array
                    report_dict["alert_sent"],
                    report_dict.get("alert_sent_at"),
                    report_dict["alert_recipients"],  # JSON array
                    report_dict["generated_at"],
                ],
            )

            logger.info(f"Saved validation report: {report.report_id}")

        except Exception as e:
            raise StorageError(f"Failed to save validation report: {e}")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
