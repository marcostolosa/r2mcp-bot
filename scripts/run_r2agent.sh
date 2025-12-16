#!/usr/bin/env bash
# Run r2agent container against a binary and store reports under ./analysis/<job_id>/
# Usage: ./scripts/run_r2agent.sh /path/to/binary [optional_task_md] [optional_tag] [optional_llm_model]
#
# Outputs per job:
#   ./analysis/<job_id>/input.bin
#   ./analysis/<job_id>/prompt_agent.md (if provided)
#   ./analysis/<job_id>/Report.md
#   ./analysis/<job_id>/opencode.log
#   ./analysis/<job_id>/docker.log
#   ./analysis/<job_id>/meta.json
#   ./analysis/<job_id>/FINISHED_<seconds>
# Global index:
#   ./analysis/reports.md

set -euo pipefail

IMAGE="r2agent:dev"
PLATFORM="linux/arm64"

START_EPOCH="$(date +%s)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Always mark job completion so it's easy to see when a job is finished and how long it took.
on_exit() {
  local rc=$?
  set +e

  local end_epoch duration
  end_epoch="$(date +%s)"
  duration="$(( end_epoch - START_EPOCH ))"

  if [[ -n "${JOB_DIR:-}" && -d "${JOB_DIR}" ]]; then
    : > "${JOB_DIR}/FINISHED_${duration}"
  fi

  # Best-effort: avoid leaving a stale reports lock behind on abort.
  rm -rf "${BASE_DIR:-}/.reports.lock" >/dev/null 2>&1 || true

  set -e
  return "${rc}"
}
trap on_exit EXIT

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 /path/to/binary [optional_task_md] [optional_tag] [optional_llm_model]"
  exit 1
fi

BIN_PATH="$1"
TASK_PATH="${2:-}"
TAG="${3:-}"
LLM_MODEL="${4:-}"

if [[ ! -f "$BIN_PATH" ]]; then
  echo "[!] Binary not found: $BIN_PATH"
  exit 1
fi

if [[ -n "$TASK_PATH" && ! -f "$TASK_PATH" ]]; then
  echo "[!] Task file not found: $TASK_PATH"
  exit 1
fi

BASE_DIR="${PROJECT_ROOT}/analysis"
INDEX_FILE="${BASE_DIR}/reports.md"
mkdir -p "$BASE_DIR"

# Job dir (unique, pipefail-safe)
TS="$(date +"%Y%m%d_%H%M%S")"
JOB_DIR="$(mktemp -d "${BASE_DIR}/job_${TS}_XXXXXX")"
JOB_ID="$(basename "$JOB_DIR")"

echo "[+] Job id:  $JOB_ID"
echo "[+] Job dir: $JOB_DIR"

# Copy artifacts into job dir
cp "$BIN_PATH" "$JOB_DIR/input.bin"
if [[ -n "$TASK_PATH" ]]; then
  # The container expects /workspace/prompt_agent.md (see docker/run_analysis.sh)
  cp "$TASK_PATH" "$JOB_DIR/prompt_agent.md"
  # Optional compatibility copy for humans/older runs.
  # cp "$TASK_PATH" "$JOB_DIR/analyze.task.md" >/dev/null 2>&1 || true
fi

# Sanity-check: make sure the binary is really present inside the mounted workspace.
if [[ ! -s "$JOB_DIR/input.bin" ]]; then
  echo "[!] Failed to copy binary into job workspace (missing or empty): $JOB_DIR/input.bin"
  echo "    Source: $BIN_PATH"
  exit 1
fi
COPIED_SIZE="$(stat -f%z "$JOB_DIR/input.bin" 2>/dev/null || stat -c%s "$JOB_DIR/input.bin" 2>/dev/null || echo "unknown")"
echo "[+] Copied input.bin: $JOB_DIR/input.bin (${COPIED_SIZE} bytes)"

# Metadata (useful later for the bot)
BIN_NAME="$(basename "$BIN_PATH")"
BIN_SIZE="$(stat -f%z "$BIN_PATH" 2>/dev/null || stat -c%s "$BIN_PATH" 2>/dev/null || echo "unknown")"
{
  echo "{"
  echo "  \"job_id\": \"${JOB_ID}\","
  echo "  \"created_at\": \"$(date -Iseconds)\","
  echo "  \"binary_name\": \"${BIN_NAME}\","
  echo "  \"binary_size\": \"${BIN_SIZE}\","
  echo "  \"tag\": \"${TAG}\""
  echo "}"
} > "$JOB_DIR/meta.json"

# Run container (bash -lc makes it resilient even if the shebang/ENTRYPOINT is broken)
[[ -n "${JOB_DIR:-}" ]] || { echo "[!] JOB_DIR is empty"; exit 1; }

echo "[+] Launching container..."
# Allocate a TTY when running interactively (helps some CLIs flush output).
DOCKER_TTY=()
if [[ -t 0 && -t 1 ]]; then
  DOCKER_TTY=(-t)
fi

docker run --rm -i "${DOCKER_TTY[@]}" --platform "$PLATFORM" \
  -v "$JOB_DIR:/workspace" \
  ${LLM_MODEL:+-e OPENCODE_MODEL="${LLM_MODEL}"} \
  --name "r2agent_${JOB_ID}" \
  --label "r2agent.managed=1" \
  --label "r2agent.job_id=${JOB_ID}" \
  --label "r2agent.tag=${TAG}" \
  "${AUTH_MOUNT[@]}" \
  --entrypoint bash \
  "$IMAGE" -lc "/usr/local/bin/run_analysis.sh" 2>&1 | tee "$JOB_DIR/docker.log"

# Results
if [[ ! -f "$JOB_DIR/Report.md" && ! -f "$JOB_DIR/report.md" ]]; then
  echo "[!] No Report.md found."
  echo "    Check: $JOB_DIR/opencode.log"
  echo "    Check: $JOB_DIR/docker.log"
  exit 2
fi

acquire_reports_lock() {
  local lock_dir="${BASE_DIR}/.reports.lock"
  local pid_file="${lock_dir}/pid"

  local i other_pid
  for i in {1..300}; do
    if mkdir "${lock_dir}" 2>/dev/null; then
      echo "$$" > "${pid_file}" 2>/dev/null || true
      return 0
    fi

    if [[ -f "${pid_file}" ]]; then
      other_pid="$(cat "${pid_file}" 2>/dev/null || true)"
      if [[ -n "${other_pid}" ]] && ! kill -0 "${other_pid}" 2>/dev/null; then
        rm -rf "${lock_dir}" >/dev/null 2>&1 || true
        continue
      fi
    fi

    sleep 0.1
  done

  echo "[!] Could not acquire reports.md lock after ~30s: ${lock_dir}"
  return 1
}

release_reports_lock() {
  rm -rf "${BASE_DIR}/.reports.lock" >/dev/null 2>&1 || true
}

# Update index (locked so concurrent runs don't clobber reports.md)
acquire_reports_lock || exit 1
if [[ ! -f "$INDEX_FILE" ]]; then
  {
    echo "# Reports index"
    echo
    echo "Format: job_id | binary | size | tag | paths"
    echo
  } > "$INDEX_FILE"
fi

echo "- **${JOB_ID}** | ${BIN_NAME} | ${BIN_SIZE} bytes | tag: ${TAG:-none} | report: \`analysis/${JOB_ID}/Report.md\` | opencode: \`analysis/${JOB_ID}/opencode.log\` | docker: \`analysis/${JOB_ID}/docker.log\`" >> "$INDEX_FILE"
release_reports_lock

if [[ -f "$JOB_DIR/Report.md" ]]; then
  echo "[+] Report:  $JOB_DIR/Report.md"
else
  echo "[+] Report:  $JOB_DIR/report.md"
fi
echo "[+] OpenCode: $JOB_DIR/opencode.log"
echo "[+] Docker:   $JOB_DIR/docker.log"
echo "[+] Index:   $INDEX_FILE"

echo
echo "----- report.md (head) -----"
sed -n '1,120p' "$JOB_DIR/Report.md" 2>/dev/null || sed -n '1,120p' "$JOB_DIR/report.md"


