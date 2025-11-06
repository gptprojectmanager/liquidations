#!/usr/bin/env python3
"""
Safe DuckDB ingestion wrapper with lock detection and timeout.

Prevents stuck processes by:
1. Checking for existing locks before starting
2. Creating a PID file for monitoring
3. Auto-cleanup on exit/timeout
"""

import argparse
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SafeIngestionWrapper:
    """Wrapper with lock detection and timeout protection."""

    def __init__(self, db_path: Path, timeout_minutes: int = 120):
        self.db_path = Path(db_path)
        self.timeout_minutes = timeout_minutes
        self.pid_file = self.db_path.with_suffix('.pid')
        self.lock_file = self.db_path.with_suffix('.duckdb.wal')

    def check_existing_lock(self) -> bool:
        """Check if another process has a lock on the database."""

        # Check PID file
        if self.pid_file.exists():
            try:
                with open(self.pid_file, 'r') as f:
                    old_pid = int(f.read().strip())

                # Check if process is still running
                if self._is_process_running(old_pid):
                    logger.error(f"❌ Database locked by PID {old_pid}")
                    logger.error(f"   To force unlock: kill -9 {old_pid} && rm {self.pid_file}")
                    return True
                else:
                    logger.warning(f"⚠️  Stale PID file found (PID {old_pid} not running) - removing")
                    self.pid_file.unlink()
            except Exception as e:
                logger.warning(f"⚠️  Could not read PID file: {e}")

        # Check DuckDB WAL file (Write-Ahead Log = active lock)
        if self.lock_file.exists():
            logger.warning(f"⚠️  DuckDB WAL file exists: {self.lock_file}")
            logger.warning("   This may indicate an active connection or crash")

        return False

    def _is_process_running(self, pid: int) -> bool:
        """Check if a process is running by PID."""
        try:
            # Send signal 0 (does nothing but checks if process exists)
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def create_pid_file(self):
        """Create PID file for this process."""
        with open(self.pid_file, 'w') as f:
            f.write(str(os.getpid()))
        logger.info(f"📝 Created PID file: {self.pid_file} (PID {os.getpid()})")

    def cleanup_pid_file(self):
        """Remove PID file on exit."""
        if self.pid_file.exists():
            self.pid_file.unlink()
            logger.info(f"🗑️  Removed PID file: {self.pid_file}")

    def run_with_timeout(self, command: list) -> int:
        """Run command with timeout protection."""

        logger.info(f"⏱️  Starting with {self.timeout_minutes}min timeout")
        logger.info(f"📋 Command: {' '.join(command)}")

        start_time = time.time()
        timeout_seconds = self.timeout_minutes * 60

        try:
            # Start subprocess
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1  # Line buffered
            )

            # Stream output with timeout check
            while True:
                elapsed = time.time() - start_time

                # Check timeout
                if elapsed > timeout_seconds:
                    logger.error(f"❌ TIMEOUT after {self.timeout_minutes} minutes!")
                    process.kill()
                    process.wait()
                    return 124  # Standard timeout exit code

                # Read output (non-blocking with timeout)
                try:
                    line = process.stdout.readline()
                    if not line:
                        # Process finished
                        break
                    print(line, end='', flush=True)
                except Exception as e:
                    logger.error(f"Error reading output: {e}")
                    break

            # Get exit code
            exit_code = process.wait()

            elapsed_str = self._format_duration(elapsed)
            if exit_code == 0:
                logger.info(f"✅ Completed successfully in {elapsed_str}")
            else:
                logger.error(f"❌ Failed with exit code {exit_code} after {elapsed_str}")

            return exit_code

        except Exception as e:
            logger.error(f"❌ Execution error: {e}")
            return 1

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)

        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"


def main():
    parser = argparse.ArgumentParser(description='Safe DuckDB ingestion with lock detection')
    parser.add_argument('--symbol', default='BTCUSDT', help='Trading pair')
    parser.add_argument('--data-dir', required=True, help='Base data directory')
    parser.add_argument('--db', required=True, help='DuckDB database path')
    parser.add_argument('--mode', choices=['auto', 'full', 'dry-run'], required=True)
    parser.add_argument('--start-date', help='Start date for full mode (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='End date for full mode (YYYY-MM-DD)')
    parser.add_argument('--throttle-ms', type=int, default=200, help='Throttle milliseconds')
    parser.add_argument('--timeout', type=int, default=120, help='Timeout in minutes (default: 120)')

    args = parser.parse_args()

    # Initialize wrapper
    wrapper = SafeIngestionWrapper(
        db_path=Path(args.db),
        timeout_minutes=args.timeout
    )

    print("=" * 70)
    print("  SAFE DUCKDB INGESTION WRAPPER")
    print("=" * 70)
    print(f"Database: {args.db}")
    print(f"Timeout: {args.timeout} minutes")
    print(f"Mode: {args.mode}")
    print("=" * 70)
    print()

    # Step 1: Check for existing lock
    print("🔒 Step 1: Lock Detection")
    if wrapper.check_existing_lock():
        print("\n❌ BLOCKED: Another process has a lock on the database")
        print("   Resolution:")
        print(f"   1. Check if process is legitimate: ps aux | grep {wrapper.pid_file.stem}")
        print(f"   2. Kill if stuck: kill -9 <PID> && rm {wrapper.pid_file}")
        print("   3. Re-run this script")
        return 1
    print("✅ No locks detected\n")

    # Step 2: Create PID file
    print("📝 Step 2: PID File Creation")
    wrapper.create_pid_file()
    print()

    # Step 3: Setup cleanup handler
    def cleanup_handler(signum, frame):
        logger.info(f"\n⚠️  Received signal {signum} - cleaning up...")
        wrapper.cleanup_pid_file()
        sys.exit(1)

    signal.signal(signal.SIGTERM, cleanup_handler)
    signal.signal(signal.SIGINT, cleanup_handler)

    # Step 4: Run actual ingestion script
    print("🚀 Step 3: Execute Ingestion")
    print()

    # Build command
    cmd = [
        'python3',
        '/workspace/1TB/LiquidationHeatmap/ingest_full_history_n8n.py',
        '--symbol', args.symbol,
        '--data-dir', args.data_dir,
        '--db', args.db,
        '--mode', args.mode,
        '--throttle-ms', str(args.throttle_ms)
    ]

    if args.start_date:
        cmd.extend(['--start-date', args.start_date])
    if args.end_date:
        cmd.extend(['--end-date', args.end_date])

    try:
        exit_code = wrapper.run_with_timeout(cmd)
    finally:
        # Always cleanup PID file
        wrapper.cleanup_pid_file()

    return exit_code


if __name__ == '__main__':
    sys.exit(main())
