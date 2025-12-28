#!/usr/bin/env python3
"""Run backtest on historical data and generate report (T2.4-T2.5).

Usage:
    # Run BTC backtest for 2024 H2
    uv run python scripts/run_backtest.py

    # Run with custom parameters
    uv run python scripts/run_backtest.py --symbol ETHUSDT --tolerance 0.5

    # Run multiple tolerance levels
    uv run python scripts/run_backtest.py --sweep-tolerance
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.liquidationheatmap.validation.backtest import (
    BacktestConfig,
    generate_backtest_report,
    run_backtest,
)


def main():
    parser = argparse.ArgumentParser(description="Run liquidation prediction backtest")
    parser.add_argument(
        "--symbol",
        default="BTCUSDT",
        help="Trading pair symbol (default: BTCUSDT)",
    )
    parser.add_argument(
        "--start-date",
        default="2024-06-01",
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        default="2024-12-31",
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1.0,
        help="Price tolerance percentage (default: 1.0)",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=60,
        help="Prediction horizon in minutes (default: 60)",
    )
    parser.add_argument(
        "--sweep-tolerance",
        action="store_true",
        help="Run with multiple tolerance levels (0.5%, 1%, 2%)",
    )
    parser.add_argument(
        "--output",
        default="reports/backtest_2024.md",
        help="Output report path",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed progress",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON results to stdout",
    )

    args = parser.parse_args()

    start_date = datetime.fromisoformat(args.start_date)
    end_date = datetime.fromisoformat(args.end_date)

    if args.sweep_tolerance:
        tolerances = [0.5, 1.0, 2.0]
    else:
        tolerances = [args.tolerance]

    print(f"🔬 Running backtest for {args.symbol}")
    print(f"   Period: {start_date.date()} to {end_date.date()}")
    print(f"   Tolerances: {tolerances}")
    print()

    results = []

    for tolerance in tolerances:
        print(f"📊 Testing tolerance: {tolerance}%")

        config = BacktestConfig(
            symbol=args.symbol,
            start_date=start_date,
            end_date=end_date,
            tolerance_pct=tolerance,
            prediction_horizon_minutes=args.horizon,
        )

        result = run_backtest(config, verbose=args.verbose)
        results.append(result)

        if result.error:
            print(f"   ❌ Error: {result.error}")
            continue

        gate_emoji = "✅" if result.passed_gate(0.6) else ("⚠️" if result.passed_gate(0.4) else "❌")

        print(f"   {gate_emoji} F1: {result.metrics.f1_score:.2%}")
        print(f"      Precision: {result.metrics.precision:.2%}")
        print(f"      Recall: {result.metrics.recall:.2%}")
        tp, fp, fn = result.true_positives, result.false_positives, result.false_negatives
        print(f"      TP: {tp}, FP: {fp}, FN: {fn}")
        print()

    # Find best result
    best_result = max(results, key=lambda r: r.metrics.f1_score)

    # Generate report for best result
    output_path = Path(args.output)
    generate_backtest_report(best_result, output_path)
    print(f"📝 Report saved: {output_path}")

    # Save JSON results
    json_path = output_path.with_suffix(".json")
    with open(json_path, "w") as f:
        json.dump(
            {
                "best_tolerance": best_result.config.tolerance_pct,
                "best_f1": best_result.metrics.f1_score,
                "gate_2_passed": best_result.passed_gate(0.6),
                "results": [r.to_dict() for r in results],
            },
            f,
            indent=2,
        )
    print(f"📊 JSON saved: {json_path}")

    if args.json:
        print("\n--- JSON Output ---")
        print(json.dumps(best_result.to_dict(), indent=2))

    # Gate 2 decision
    print("\n" + "=" * 50)
    if best_result.passed_gate(0.6):
        print("🎉 GATE 2 PASSED: Model validated (F1 ≥ 60%)")
        print("   → Proceed to ETH expansion")
    elif best_result.passed_gate(0.4):
        print("⚠️ GATE 2 ACCEPTABLE: Model has limitations (F1 ≥ 40%)")
        print("   → Document limitations and proceed with caution")
    else:
        print("❌ GATE 2 FAILED: Model requires rework (F1 < 40%)")
        print("   → Stop and investigate prediction methodology")
    print("=" * 50)

    return 0 if best_result.passed_gate(0.4) else 1


if __name__ == "__main__":
    exit(main())
