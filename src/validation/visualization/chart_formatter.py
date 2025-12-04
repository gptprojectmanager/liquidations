"""
Chart data formatter for visualization.

Formats validation data for frontend chart libraries (Plotly, Chart.js, etc.).
"""

from datetime import datetime
from typing import Dict, List, Optional

from src.validation.logger import logger


class ChartFormatter:
    """
    Formats validation data for chart visualization.

    Converts raw data into chart-ready formats.
    """

    def __init__(self):
        """Initialize chart formatter."""
        logger.info("ChartFormatter initialized")

    def format_line_chart(
        self,
        data_points: List[tuple],
        x_label: str = "Date",
        y_label: str = "Score",
        title: str = "Validation Scores Over Time",
    ) -> Dict:
        """
        Format data for line chart.

        Args:
            data_points: List of (timestamp, value) tuples
            x_label: X-axis label
            y_label: Y-axis label
            title: Chart title

        Returns:
            Dict with chart data in Plotly format
        """
        if not data_points:
            logger.warning("No data points for line chart")
            return self._empty_chart(title)

        # Sort by timestamp
        sorted_data = sorted(data_points, key=lambda x: x[0])

        # Extract x and y values
        x_values = [ts.isoformat() if isinstance(ts, datetime) else ts for ts, _ in sorted_data]
        y_values = [val for _, val in sorted_data]

        chart_data = {
            "type": "line",
            "data": {
                "labels": x_values,
                "datasets": [
                    {
                        "label": y_label,
                        "data": y_values,
                        "borderColor": "rgb(75, 192, 192)",
                        "backgroundColor": "rgba(75, 192, 192, 0.2)",
                        "tension": 0.1,
                    }
                ],
            },
            "options": {
                "responsive": True,
                "plugins": {
                    "title": {"display": True, "text": title},
                    "legend": {"display": True},
                },
                "scales": {
                    "x": {"title": {"display": True, "text": x_label}},
                    "y": {"title": {"display": True, "text": y_label}},
                },
            },
        }

        logger.info(f"Line chart formatted: {len(data_points)} points")

        return chart_data

    def format_bar_chart(
        self,
        categories: List[str],
        values: List[float],
        title: str = "Comparison",
        x_label: str = "Category",
        y_label: str = "Value",
    ) -> Dict:
        """
        Format data for bar chart.

        Args:
            categories: Category labels
            values: Values for each category
            title: Chart title
            x_label: X-axis label
            y_label: Y-axis label

        Returns:
            Dict with chart data
        """
        if not categories or not values:
            logger.warning("No data for bar chart")
            return self._empty_chart(title)

        chart_data = {
            "type": "bar",
            "data": {
                "labels": categories,
                "datasets": [
                    {
                        "label": y_label,
                        "data": values,
                        "backgroundColor": "rgba(54, 162, 235, 0.6)",
                        "borderColor": "rgba(54, 162, 235, 1)",
                        "borderWidth": 1,
                    }
                ],
            },
            "options": {
                "responsive": True,
                "plugins": {
                    "title": {"display": True, "text": title},
                    "legend": {"display": True},
                },
                "scales": {
                    "x": {"title": {"display": True, "text": x_label}},
                    "y": {"title": {"display": True, "text": y_label}, "beginAtZero": True},
                },
            },
        }

        logger.info(f"Bar chart formatted: {len(categories)} categories")

        return chart_data

    def format_multi_line_chart(
        self,
        datasets: Dict[str, List[tuple]],
        title: str = "Multi-Series Comparison",
        x_label: str = "Date",
        y_label: str = "Score",
    ) -> Dict:
        """
        Format multiple data series for line chart.

        Args:
            datasets: Dict mapping series_name to List[(timestamp, value)]
            title: Chart title
            x_label: X-axis label
            y_label: Y-axis label

        Returns:
            Dict with multi-series chart data
        """
        if not datasets:
            logger.warning("No datasets for multi-line chart")
            return self._empty_chart(title)

        # Collect all unique timestamps
        all_timestamps = set()
        for series_data in datasets.values():
            for ts, _ in series_data:
                all_timestamps.add(ts)

        # Sort timestamps
        sorted_timestamps = sorted(list(all_timestamps))
        x_values = [ts.isoformat() if isinstance(ts, datetime) else ts for ts in sorted_timestamps]

        # Color palette
        colors = [
            "rgb(75, 192, 192)",
            "rgb(255, 99, 132)",
            "rgb(54, 162, 235)",
            "rgb(255, 206, 86)",
            "rgb(153, 102, 255)",
        ]

        # Build datasets
        chart_datasets = []
        for i, (series_name, series_data) in enumerate(datasets.items()):
            # Create dict for fast lookup
            data_dict = {ts: val for ts, val in series_data}

            # Fill y values (null for missing timestamps)
            y_values = [data_dict.get(ts, None) for ts in sorted_timestamps]

            color = colors[i % len(colors)]

            chart_datasets.append(
                {
                    "label": series_name,
                    "data": y_values,
                    "borderColor": color,
                    "backgroundColor": color.replace("rgb", "rgba").replace(")", ", 0.2)"),
                    "tension": 0.1,
                }
            )

        chart_data = {
            "type": "line",
            "data": {"labels": x_values, "datasets": chart_datasets},
            "options": {
                "responsive": True,
                "plugins": {
                    "title": {"display": True, "text": title},
                    "legend": {"display": True},
                },
                "scales": {
                    "x": {"title": {"display": True, "text": x_label}},
                    "y": {"title": {"display": True, "text": y_label}},
                },
            },
        }

        logger.info(f"Multi-line chart formatted: {len(datasets)} series")

        return chart_data

    def format_grade_distribution(
        self,
        grade_counts: Dict[str, int],
        title: str = "Grade Distribution",
    ) -> Dict:
        """
        Format grade distribution for pie chart.

        Args:
            grade_counts: Dict mapping grade to count
            title: Chart title

        Returns:
            Dict with pie chart data
        """
        if not grade_counts:
            logger.warning("No grade data for pie chart")
            return self._empty_chart(title)

        # Order by grade (A, B, C, F)
        grade_order = ["A", "B", "C", "F"]
        ordered_grades = [g for g in grade_order if g in grade_counts]

        labels = ordered_grades
        values = [grade_counts[g] for g in ordered_grades]

        # Grade colors
        grade_colors = {
            "A": "rgba(75, 192, 75, 0.8)",  # Green
            "B": "rgba(54, 162, 235, 0.8)",  # Blue
            "C": "rgba(255, 206, 86, 0.8)",  # Yellow
            "F": "rgba(255, 99, 132, 0.8)",  # Red
        }

        colors = [grade_colors.get(g, "rgba(200, 200, 200, 0.8)") for g in ordered_grades]

        chart_data = {
            "type": "pie",
            "data": {
                "labels": labels,
                "datasets": [
                    {
                        "data": values,
                        "backgroundColor": colors,
                        "borderWidth": 1,
                    }
                ],
            },
            "options": {
                "responsive": True,
                "plugins": {
                    "title": {"display": True, "text": title},
                    "legend": {"display": True, "position": "right"},
                },
            },
        }

        logger.info(f"Pie chart formatted: {len(grade_counts)} grades")

        return chart_data

    def format_heatmap(
        self,
        data: List[List[float]],
        x_labels: List[str],
        y_labels: List[str],
        title: str = "Validation Heatmap",
    ) -> Dict:
        """
        Format data for heatmap.

        Args:
            data: 2D array of values
            x_labels: X-axis labels
            y_labels: Y-axis labels
            title: Chart title

        Returns:
            Dict with heatmap data
        """
        if not data or not x_labels or not y_labels:
            logger.warning("Insufficient data for heatmap")
            return self._empty_chart(title)

        # Plotly heatmap format
        chart_data = {
            "type": "heatmap",
            "data": [
                {
                    "z": data,
                    "x": x_labels,
                    "y": y_labels,
                    "colorscale": "Viridis",
                    "type": "heatmap",
                }
            ],
            "layout": {
                "title": title,
                "xaxis": {"title": ""},
                "yaxis": {"title": ""},
            },
        }

        logger.info(f"Heatmap formatted: {len(y_labels)}x{len(x_labels)}")

        return chart_data

    def _empty_chart(self, title: str) -> Dict:
        """Return empty chart structure."""
        return {
            "type": "line",
            "data": {"labels": [], "datasets": []},
            "options": {
                "plugins": {
                    "title": {"display": True, "text": f"{title} (No Data)"},
                }
            },
        }


# Global formatter instance
_global_formatter: Optional[ChartFormatter] = None


def get_chart_formatter() -> ChartFormatter:
    """
    Get global chart formatter instance (singleton).

    Returns:
        ChartFormatter instance
    """
    global _global_formatter

    if _global_formatter is None:
        _global_formatter = ChartFormatter()

    return _global_formatter
