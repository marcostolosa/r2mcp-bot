#!/usr/bin/env python3
"""
Watchdog for r2agent analysis containers.

This script scans Docker for containers launched by run_r2agent.sh
(identified via label r2agent.managed=1). If a container has been running
longer than TIMEOUT_SECONDS (default: 900 = 15 minutes), it is stopped and
the action is logged under ./analysis/_watchdog_logs/.

Usage:
  python3 watchdog.py --once
  python3 watchdog.py --interval 60 --timeout 900

Notes:
- Designed to be safe to run alongside the bot (in a separate terminal, cron, launchd, etc.).
- Works on macOS and Linux.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def run_command(*args: str) -> str:
    """Run a command and return its output as a string."""
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Command failed: {' '.join(args)}\n{e.stderr}")


def log_message(message: str, log_dir: Path) -> None:
    """Log a message to the daily log file and stdout."""
    timestamp = datetime.datetime.now().isoformat()
    day = datetime.datetime.now().strftime("%Y%m%d")
    log_file = log_dir / f"watchdog_{day}.log"

    log_line = f"{timestamp} {message}"
    print(log_line)

    try:
        with open(log_file, 'a') as f:
            f.write(log_line + '\n')
    except Exception as e:
        print(f"Warning: Failed to write to log file {log_file}: {e}", file=sys.stderr)


def check_container(container_id: str, timeout_seconds: int, log_dir: Path) -> None:
    """Check a single container and stop it if it exceeds the timeout."""
    try:
        # Inspect the container
        inspect_output = run_command("docker", "inspect", container_id)
        data = json.loads(inspect_output)[0]

        state = data.get("State", {})
        started_at = state.get("StartedAt", "")
        running = state.get("Running", False)
        name = (data.get("Name", "") or "").lstrip("/")
        labels = data.get("Config", {}).get("Labels", {})
        job_id = labels.get("r2agent.job_id", "")
        tag = labels.get("r2agent.tag", "")

        if not running or not started_at:
            return

        # Parse the start time
        # StartedAt is RFC3339/ISO-8601 like: 2025-12-16T12:34:56.123456789Z
        ts = started_at.replace("Z", "+00:00")
        try:
            start = datetime.datetime.fromisoformat(ts)
        except ValueError:
            # Fallback: drop nanoseconds if present
            if "." in ts:
                ts2 = ts.split(".", 1)[0] + "+00:00"
                start = datetime.datetime.fromisoformat(ts2)
            else:
                raise

        now = datetime.datetime.now(datetime.timezone.utc)
        age_seconds = int((now - start).total_seconds())

        if age_seconds <= timeout_seconds:
            return

        # Stop the container
        try:
            stop_output = run_command("docker", "stop", "-t", "10", container_id)
            result = f"stopped={stop_output}"
        except Exception as e:
            result = f"stop_failed={e}"

        message = (f"watchdog: action=stop age_s={age_seconds} timeout_s={timeout_seconds} "
                  f"id={container_id} name={name} job_id={job_id} tag={tag} "
                  f"started_at={started_at} result={result}")
        log_message(message, log_dir)

    except Exception as e:
        # Container may have exited between ps and inspect
        log_message(f"watchdog: error checking container {container_id}: {e}", log_dir)


def check_once(timeout_seconds: int, log_dir: Path) -> None:
    """Check all managed containers once."""
    try:
        # Get container IDs with the r2agent.managed label
        ids_output = run_command("docker", "ps", "-q", "--filter", "label=r2agent.managed=1")
        if not ids_output:
            return

        container_ids = ids_output.split('\n')
        for container_id in container_ids:
            if container_id.strip():
                check_container(container_id.strip(), timeout_seconds, log_dir)
    except Exception as e:
        log_message(f"watchdog: error in check_once: {e}", log_dir)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Watchdog for r2agent analysis containers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run once and exit'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Check interval in seconds (default: 60)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=900,
        help='Container timeout in seconds (default: 900 = 15 minutes)'
    )

    args = parser.parse_args()

    if args.interval <= 0 or args.timeout <= 0:
        parser.error("Interval and timeout must be positive integers")

    # Set up directories
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    log_dir = project_root / "analysis" / "_watchdog_logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_message(f"watchdog: started interval_s={args.interval} timeout_s={args.timeout} once={args.once}", log_dir)

    if args.once:
        check_once(args.timeout, log_dir)
        log_message("watchdog: finished once", log_dir)
        return

    # Main loop
    try:
        while True:
            check_once(args.timeout, log_dir)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        log_message("watchdog: interrupted by user", log_dir)
    except Exception as e:
        log_message(f"watchdog: unexpected error: {e}", log_dir)
        sys.exit(1)


if __name__ == "__main__":
    main()
