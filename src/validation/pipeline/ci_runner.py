"""CI runner entrypoint for GitHub Actions.

Provides a streamlined interface for running validation in CI/CD pipelines.
Designed for .github/workflows/validation.yml integration.
"""

import json
import sys
from pathlib import Path

from src.validation.pipeline.models import (
    GateDecision,
    PipelineStatus,
)
from src.validation.pipeline.orchestrator import run_pipeline


def run_ci_validation(
    symbol: str = "BTCUSDT",
    validation_types: list[str] | None = None,
    tolerance_pct: float = 2.0,
    output_path: str | None = None,
    fail_on_gate_fail: bool = True,
) -> int:
    """Run validation for CI pipeline.

    Args:
        symbol: Trading pair to validate
        validation_types: List of validation types (default: ['backtest'])
        tolerance_pct: Price tolerance percentage
        output_path: Path to write JSON results
        fail_on_gate_fail: Exit with code 1 if Gate 2 fails

    Returns:
        Exit code: 0 for success/pass, 1 for failure
    """
    if validation_types is None:
        validation_types = ["backtest"]

    print("🔬 CI Validation Runner")
    print(f"   Symbol: {symbol}")
    print(f"   Validation types: {validation_types}")
    print(f"   Tolerance: {tolerance_pct}%")
    print()

    # Run pipeline
    result = run_pipeline(
        symbol=symbol,
        validation_types=validation_types,
        trigger_type="ci",
        triggered_by="github-actions",
        tolerance_pct=tolerance_pct,
        verbose=True,
    )

    # Write output if path provided
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"\n📝 Results saved to: {output_path}")

    # Determine exit code
    print("\n" + "=" * 50)

    if result.status == PipelineStatus.FAILED:
        print(f"❌ Pipeline FAILED: {result.error_message}")
        print("=" * 50)
        return 1

    if result.gate_2_decision == GateDecision.PASS:
        print("✅ Gate 2 PASSED - Model validated")
        print(f"   F1 Score: {float(result.overall_score or 0):.2f}%")
        print(f"   Grade: {result.overall_grade}")
        print("=" * 50)
        return 0

    elif result.gate_2_decision == GateDecision.ACCEPTABLE:
        print("⚠️ Gate 2 ACCEPTABLE - Model has limitations")
        print(f"   F1 Score: {float(result.overall_score or 0):.2f}%")
        print(f"   Grade: {result.overall_grade}")
        print(f"   Reason: {result.gate_2_reason}")
        print("=" * 50)
        # Acceptable still passes CI
        return 0

    else:
        print("❌ Gate 2 FAILED - Model rework required")
        print(f"   F1 Score: {float(result.overall_score or 0):.2f}%")
        print(f"   Grade: {result.overall_grade}")
        print(f"   Reason: {result.gate_2_reason}")
        print("=" * 50)
        return 1 if fail_on_gate_fail else 0


def main() -> int:
    """Main entry point for CI runner.

    Parses environment variables or command line args for CI use.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Run validation pipeline for CI/CD",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic usage
    python -m src.validation.pipeline.ci_runner

    # With custom parameters
    python -m src.validation.pipeline.ci_runner --symbol ETHUSDT --tolerance 1.5

    # Save results to file
    python -m src.validation.pipeline.ci_runner --output reports/ci_result.json
        """,
    )

    parser.add_argument(
        "--symbol",
        default="BTCUSDT",
        help="Trading symbol to validate (default: BTCUSDT)",
    )
    parser.add_argument(
        "--validation-types",
        default="backtest",
        help="Comma-separated validation types: backtest,coinglass,realtime,full",
    )
    parser.add_argument(
        "--tolerance-pct",
        type=float,
        default=2.0,
        help="Price tolerance percentage (default: 2.0)",
    )
    parser.add_argument(
        "--output",
        help="Output JSON file path for results",
    )
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="Don't exit with error code on Gate 2 failure",
    )

    args = parser.parse_args()

    # Parse validation types
    validation_types = [vt.strip() for vt in args.validation_types.split(",")]

    return run_ci_validation(
        symbol=args.symbol,
        validation_types=validation_types,
        tolerance_pct=args.tolerance_pct,
        output_path=args.output,
        fail_on_gate_fail=not args.no_fail,
    )


if __name__ == "__main__":
    sys.exit(main())
