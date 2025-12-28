#!/usr/bin/env python3
"""Collect liquidations from Hyperliquid for validation.

Usage:
    python scripts/collect_liquidations.py           # Run for 5 min
    python scripts/collect_liquidations.py --minutes 30
"""

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

import websockets

OUTPUT = Path("data/validation/hyperliquid_liquidations.jsonl")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)


async def collect(minutes: int = 5):
    url = "wss://api.hyperliquid.xyz/ws"
    end_time = datetime.now().timestamp() + (minutes * 60)
    liq_count = 0
    trade_count = 0

    print(f"Collecting liquidations for {minutes} min...")
    print(f"Output: {OUTPUT}")

    async with websockets.connect(url) as ws:
        msg = {"method": "subscribe", "subscription": {"type": "trades", "coin": "BTC"}}
        await ws.send(json.dumps(msg))

        async for data in ws:
            if datetime.now().timestamp() > end_time:
                break

            resp = json.loads(data)
            if resp.get("channel") != "trades":
                continue

            for trade in resp.get("data", []):
                trade_count += 1
                if not trade.get("liquidation"):
                    continue

                liq = {
                    "ts": datetime.now().isoformat(),
                    "price": float(trade["px"]),
                    "size": float(trade["sz"]),
                    "side": "long" if trade["side"] == "A" else "short",
                    "source": "hyperliquid",
                }

                with open(OUTPUT, "a") as f:
                    f.write(json.dumps(liq) + "\n")

                liq_count += 1
                print(f"[{liq_count}] {liq['side'].upper()} ${liq['price']:,.0f} x {liq['size']}")

    print(f"\nDone: {liq_count} liquidations from {trade_count} trades")
    return liq_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=int, default=5)
    args = parser.parse_args()
    asyncio.run(collect(args.minutes))
