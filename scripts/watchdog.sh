#!/usr/bin/env bash
# Watchdog for r2agent analysis containers.
#
# This script scans Docker for containers launched by scripts/run_r2agent.sh
# (identified via label r2agent.managed=1). If a container has been running
# longer than TIMEOUT_SECONDS (default: 900 = 15 minutes), it is stopped and
# the action is logged under ./analysis/_watchdog_logs/.
#
# Usage:
#   ./scripts/watchdog.sh --once
#   ./scripts/watchdog.sh --interval 60 --timeout 900
#
# Notes:
# - Designed to be safe to run alongside the bot (in a separate terminal, cron, launchd, etc.).
# - Works on macOS by using python3 for time parsing.

set -euo pipefail

INTERVAL_SECONDS=60
TIMEOUT_SECONDS=900
ONCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --once)
      ONCE=1
      shift
      ;;
    --interval)
      INTERVAL_SECONDS="${2:-}"
      shift 2
      ;;
    --timeout)
      TIMEOUT_SECONDS="${2:-}"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [--once] [--interval SECONDS] [--timeout SECONDS]"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      exit 2
      ;;
  esac
done

if [[ -z "${INTERVAL_SECONDS}" || -z "${TIMEOUT_SECONDS}" ]]; then
  echo "Invalid arguments."
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/analysis/_watchdog_logs"
mkdir -p "${LOG_DIR}"

log_line() {
  local msg="$1"
  local day
  day="$(date +%Y%m%d)"
  printf "%s %s\n" "$(date -Iseconds)" "${msg}" | tee -a "${LOG_DIR}/watchdog_${day}.log" >/dev/null
}

check_once() {
  local ids
  ids="$(docker ps -q --filter "label=r2agent.managed=1" || true)"
  if [[ -z "${ids}" ]]; then
    return 0
  fi

  local id
  while IFS= read -r id; do
    [[ -n "${id}" ]] || continue

    # Gather container details and decide whether to stop it.
    python3 - <<'PY' "${id}" "${TIMEOUT_SECONDS}" "${LOG_DIR}"
import datetime as dt
import json
import os
import subprocess
import sys

container_id = sys.argv[1]
timeout_s = int(sys.argv[2])

def sh(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()

try:
    raw = sh("docker", "inspect", container_id)
except Exception as e:
    # Container may have exited between ps and inspect.
    sys.exit(0)

try:
    data = json.loads(raw)[0]
except Exception:
    sys.exit(0)

state = data.get("State", {}) or {}
started_at = state.get("StartedAt") or ""
running = bool(state.get("Running"))
name = (data.get("Name") or "").lstrip("/")
labels = (data.get("Config", {}) or {}).get("Labels", {}) or {}
job_id = labels.get("r2agent.job_id", "")
tag = labels.get("r2agent.tag", "")

if not running or not started_at:
    sys.exit(0)

# StartedAt is RFC3339/ISO-8601 like: 2025-12-16T12:34:56.123456789Z
ts = started_at.replace("Z", "+00:00")
try:
    start = dt.datetime.fromisoformat(ts)
except Exception:
    # Fallback: drop nanoseconds if present.
    if "." in ts:
        ts2 = ts.split(".", 1)[0] + "+00:00"
        start = dt.datetime.fromisoformat(ts2)
    else:
        raise

now = dt.datetime.now(dt.timezone.utc)
age_s = int((now - start).total_seconds())

if age_s <= timeout_s:
    sys.exit(0)

try:
    out = sh("docker", "stop", "-t", "10", container_id)
    result = f"stopped={out}"
except Exception as e:
    result = f"stop_failed={e}"

print(f"watchdog: action=stop age_s={age_s} timeout_s={timeout_s} id={container_id} name={name} job_id={job_id} tag={tag} started_at={started_at} result={result}")
PY
  done <<< "${ids}" | while IFS= read -r line; do
    [[ -n "${line}" ]] || continue
    log_line "${line}"
  done
}

log_line "watchdog: started interval_s=${INTERVAL_SECONDS} timeout_s=${TIMEOUT_SECONDS} once=${ONCE}"

if [[ "${ONCE}" -eq 1 ]]; then
  check_once
  log_line "watchdog: finished once"
  exit 0
fi

while true; do
  check_once || true
  sleep "${INTERVAL_SECONDS}"
done


