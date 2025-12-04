"""
Tests for chart_formatter.py - Chart.js/Plotly data formatting.

Tests cover:
- Line chart formatting
- Bar chart formatting
- Multi-line chart formatting
- Grade distribution (pie chart)
- Heatmap formatting
"""

from datetime import datetime

from src.validation.visualization.chart_formatter import ChartFormatter, get_chart_formatter


class TestChartFormatter:
    """Test ChartFormatter functionality."""

    def test_format_line_chart_with_data_points(self):
        """Line chart should be formatted correctly."""
        # Arrange
        formatter = ChartFormatter()

        data_points = [
            (datetime(2025, 11, 1), 85.0),
            (datetime(2025, 11, 2), 88.0),
            (datetime(2025, 11, 3), 90.0),
        ]

        # Act
        chart = formatter.format_line_chart(
            data_points=data_points,
            x_label="Date",
            y_label="Score",
            title="Validation Scores",
        )

        # Assert
        assert chart["type"] == "line"
        assert "data" in chart
        assert "labels" in chart["data"]
        assert "datasets" in chart["data"]
        assert len(chart["data"]["labels"]) == 3

    def test_format_bar_chart_with_categories(self):
        """Bar chart should be formatted correctly."""
        # Arrange
        formatter = ChartFormatter()

        categories = ["Model A", "Model B", "Model C"]
        values = [95.0, 85.0, 75.0]

        # Act
        chart = formatter.format_bar_chart(
            categories=categories,
            values=values,
            title="Model Comparison",
        )

        # Assert
        assert chart["type"] == "bar"
        assert chart["data"]["labels"] == categories
        assert chart["data"]["datasets"][0]["data"] == values

    def test_format_multi_line_chart_with_multiple_series(self):
        """Multi-line chart should handle multiple datasets."""
        # Arrange
        formatter = ChartFormatter()

        datasets = {
            "Model 1": [
                (datetime(2025, 11, 1), 90.0),
                (datetime(2025, 11, 2), 92.0),
            ],
            "Model 2": [
                (datetime(2025, 11, 1), 85.0),
                (datetime(2025, 11, 2), 87.0),
            ],
        }

        # Act
        chart = formatter.format_multi_line_chart(
            datasets=datasets,
            title="Multi-Model Comparison",
        )

        # Assert
        assert chart["type"] == "line"
        assert len(chart["data"]["datasets"]) == 2
        assert chart["data"]["datasets"][0]["label"] == "Model 1"
        assert chart["data"]["datasets"][1]["label"] == "Model 2"

    def test_format_grade_distribution_pie_chart(self):
        """Grade distribution should be formatted as pie chart."""
        # Arrange
        formatter = ChartFormatter()

        grade_counts = {"A": 10, "B": 5, "C": 3, "F": 2}

        # Act
        chart = formatter.format_grade_distribution(
            grade_counts=grade_counts,
            title="Grade Distribution",
        )

        # Assert
        assert chart["type"] == "pie"
        assert set(chart["data"]["labels"]) == {"A", "B", "C", "F"}
        assert len(chart["data"]["datasets"][0]["backgroundColor"]) == 4

    def test_format_heatmap_with_2d_data(self):
        """Heatmap should be formatted correctly."""
        # Arrange
        formatter = ChartFormatter()

        data = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
        x_labels = ["X1", "X2", "X3"]
        y_labels = ["Y1", "Y2"]

        # Act
        chart = formatter.format_heatmap(
            data=data,
            x_labels=x_labels,
            y_labels=y_labels,
            title="Validation Heatmap",
        )

        # Assert
        assert chart["type"] == "heatmap"
        assert chart["data"][0]["z"] == data
        assert chart["data"][0]["x"] == x_labels
        assert chart["data"][0]["y"] == y_labels

    def test_empty_data_returns_empty_chart(self):
        """Empty data should return empty chart structure."""
        # Arrange
        formatter = ChartFormatter()

        # Act
        chart = formatter.format_line_chart(
            data_points=[],
            title="Empty Chart",
        )

        # Assert
        assert "No Data" in chart["options"]["plugins"]["title"]["text"]

    def test_get_chart_formatter_returns_singleton(self):
        """get_chart_formatter should return same instance."""
        # Act
        formatter1 = get_chart_formatter()
        formatter2 = get_chart_formatter()

        # Assert
        assert formatter1 is formatter2
