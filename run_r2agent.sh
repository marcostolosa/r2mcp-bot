#!/usr/bin/env bash
# Run r2agent container against a binary and store reports under ./analysis/<job_id>/
# Usage: ./run_r2agent.sh --mode <local|docker> --file /path/to/binary [options]
#
# Options:
#   --model <model>        OpenCode model to use (default: opencode/grok-code)
#   --tag <tag>            Tag for organizing jobs
#   --agent <file>         Path to agent/task file (e.g., agents/crackme.task.md)
#   --prompt <text>         Direct prompt text (alternative to --agent)
#   --help, -h              Show help message
#
# Outputs per job:
#   ./analysis/<job_id>/input.bin
#   ./analysis/<job_id>/prompt_agent.md (if provided)
#   ./analysis/<job_id>/Report.md
#   ./analysis/<job_id>/opencode.log
#   ./analysis/<job_id>/docker.log (docker mode) or local.log (local mode)
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

# Parse arguments: support flags and positional arguments
MODE=""
BIN_PATH=""
TASK_PATH=""
AGENT_PATH=""
PROMPT_TEXT=""
TAG=""
LLM_MODEL=""

# Parse flags first
while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      if [[ $# -lt 2 ]]; then
        echo "[!] Error: --mode requires a value (local or docker)"
        exit 1
      fi
      MODE="$2"
      shift 2
      ;;
    --file)
      if [[ $# -lt 2 ]]; then
        echo "[!] Error: --file requires a value (path to binary file)"
        exit 1
      fi
      BIN_PATH="$2"
      shift 2
      ;;
    --model|-m)
      if [[ $# -lt 2 ]]; then
        echo "[!] Error: --model requires a value"
        exit 1
      fi
      LLM_MODEL="$2"
      shift 2
      ;;
    --tag)
      if [[ $# -lt 2 ]]; then
        echo "[!] Error: --tag requires a value"
        exit 1
      fi
      TAG="$2"
      shift 2
      ;;
    --agent)
      if [[ $# -lt 2 ]]; then
        echo "[!] Error: --agent requires a value (path to agent file)"
        exit 1
      fi
      AGENT_PATH="$2"
      shift 2
      ;;
    --prompt)
      if [[ $# -lt 2 ]]; then
        echo "[!] Error: --prompt requires a value (prompt text)"
        exit 1
      fi
      PROMPT_TEXT="$2"
      shift 2
      ;;
    --help|-h)
      echo "Usage: $0 --mode <local|docker> --file /path/to/binary [options]"
      echo ""
      echo "Required:"
      echo "  --mode <local|docker>           Execution mode (required)"
      echo "  --file <path>                  Path to binary file to analyze (required)"
      echo "  --agent <file> OR --prompt <text>  At least one required"
      echo ""
      echo "Options (at least one required):"
      echo "  --agent <file>                 Path to agent/task file (e.g., agents/crackme.task.md)"
      echo "  --prompt <text>                Direct prompt text (can be combined with --agent)"
      echo ""
      echo "Other options:"
      echo "  --model <model>                 OpenCode model to use (default: opencode/grok-code)"
      echo "  --tag <tag>                     Tag for organizing jobs"
      echo "  --help, -h                      Show this help message"
      echo ""
      echo "Examples:"
      echo "  $0 --mode local --file ./binary --agent agents/crackme.task.md --tag test"
      echo "  $0 --mode docker --file ./binary --agent agents/crackme.task.md --prompt 'Focus on crypto functions' --tag ctf"
      echo "  $0 --mode local --file ./binary --prompt 'Tell me how many functions this binary has'"
      exit 0
      ;;
    *)
      # Not a flag, break to positional parsing
      break
      ;;
  esac
done

# Validate required parameters
if [[ -z "$BIN_PATH" ]]; then
  echo "[!] Error: --file parameter is required"
  echo "Usage: $0 --mode <local|docker> --file /path/to/binary [options]"
  echo "Run with --help for more information"
  exit 1
fi

# Validate mode is provided and valid
if [[ -z "$MODE" ]]; then
  echo "[!] Error: --mode parameter is required"
  echo "Usage: $0 --mode <local|docker> --file /path/to/binary [options]"
  echo "Run with --help for more information"
  exit 1
fi

if [[ "$MODE" != "local" && "$MODE" != "docker" ]]; then
  echo "[!] Error: mode must be 'local' or 'docker', got: $MODE"
  exit 1
fi

# Validate that at least one of --agent or --prompt is provided
if [[ -z "$AGENT_PATH" && -z "$PROMPT_TEXT" && -z "$TASK_PATH" ]]; then
  echo "[!] Error: Missing required option"
  echo ""
  echo "You must provide either:"
  echo "  --agent <file>    Path to agent/task file (e.g., agents/analyze.task.md)"
  echo "  --prompt <text>   Direct prompt text"
  echo ""
  echo "Usage: $0 --mode <local|docker> --file /path/to/binary [options]"
  echo "Run with --help for more information"
  exit 1
fi

# Validate agent file if provided
if [[ -n "$AGENT_PATH" && ! -f "$AGENT_PATH" ]]; then
  echo "[!] Error: Agent file not found: $AGENT_PATH"
  exit 1
fi

# Use TASK_PATH for backward compatibility if AGENT_PATH is not set
if [[ -z "$AGENT_PATH" && -n "$TASK_PATH" ]]; then
  AGENT_PATH="$TASK_PATH"
fi

if [[ ! -f "$BIN_PATH" ]]; then
  echo "[!] Binary not found: $BIN_PATH"
  exit 1
fi

# Validate task file if provided via positional argument (backward compatibility)
if [[ -n "$TASK_PATH" && ! -f "$TASK_PATH" ]]; then
  echo "[!] Task file not found: $TASK_PATH"
  exit 1
fi

# Check local requirements for local mode
check_local_requirements() {
  local errors=0

  echo "[+] Checking local requirements..."

  # Check opencode command
  if ! command -v opencode >/dev/null 2>&1; then
    echo "[!] Error: 'opencode' command not found in PATH"
    errors=$((errors + 1))
  else
    echo "[+] Found: opencode"
  fi

  # Check r2mcp (can be run via r2pm -r r2mcp)
  if ! command -v r2pm >/dev/null 2>&1; then
    echo "[!] Error: 'r2pm' command not found in PATH"
    errors=$((errors + 1))
  else
    echo "[+] Found: r2pm"
    # Try to run r2mcp via r2pm to verify it's available
    if ! r2pm -r r2mcp --help >/dev/null 2>&1; then
      echo "[!] Warning: 'r2pm -r r2mcp' may not be available"
    fi
  fi

  # Check r2pm plugins
  if command -v r2pm >/dev/null 2>&1; then
    local r2pm_list
    r2pm_list="$(r2pm -l 2>/dev/null || true)"
    
    local missing_plugins=()
    if ! echo "$r2pm_list" | grep -q "r2ghidra-sleigh"; then
      missing_plugins+=("r2ghidra-sleigh")
    fi
    if ! echo "$r2pm_list" | grep -q "r2ghidra"; then
      missing_plugins+=("r2ghidra")
    fi
    if ! echo "$r2pm_list" | grep -q "r2mcp"; then
      missing_plugins+=("r2mcp")
    fi

    if [[ ${#missing_plugins[@]} -gt 0 ]]; then
      echo "[!] Error: Missing required r2pm plugins: ${missing_plugins[*]}"
      echo "    Install with: r2pm -ci ${missing_plugins[*]}"
      errors=$((errors + 1))
    else
      echo "[+] Found: r2ghidra-sleigh, r2ghidra, r2mcp"
    fi
  fi

  if [[ $errors -gt 0 ]]; then
    echo "[!] Local mode requirements check failed"
    return 1
  fi

  echo "[+] All local requirements satisfied"
  return 0
}

# Run analysis locally (replicates docker/run_analysis.sh logic)
run_local_analysis() {
  local workdir="$JOB_DIR"
  local template_task="${PROJECT_ROOT}/agents/analyze.task.md"
  local task_file="${workdir}/prompt_agent.md"
  local bin_file="${workdir}/input.bin"
  local report_file="${workdir}/Report.md"
  local log_file="${workdir}/local.log"
  local opencode_log="${workdir}/opencode.log"

  cd "${workdir}"

  # Create workspace directory (needed for compatibility)
  mkdir -p "${workdir}/workspace"

  # Copy template if no task file provided
  if [[ ! -f "${task_file}" ]]; then
    echo "[i] No prompt_agent.md found in ${workdir}, copying template..."
    if [[ -f "${template_task}" ]]; then
      cp "${template_task}" "${task_file}"
    else
      echo "[!] Error: Template task file not found: ${template_task}"
      return 1
    fi
  fi

  if [[ ! -f "${bin_file}" ]]; then
    echo "[!] No input.bin found in ${workdir}."
    return 1
  fi

  echo "[+] input.bin detected, starting analysis..."

  # Set OpenCode model
  export OPENCODE_MODEL="${LLM_MODEL:-opencode/grok-code}"
  echo "[i] OpenCode model: ${OPENCODE_MODEL}"

  # Best-effort preflight checks
  command -v r2 >/dev/null 2>&1 && r2 -v || true
  command -v r2pm >/dev/null 2>&1 && r2pm -v || true
  command -v opencode >/dev/null 2>&1 && opencode --version || true

  local task_content
  task_content="$(cat "${task_file}")"

  # Replace /workspace with actual workdir path for local mode
  # This ensures paths in the prompt work correctly in local execution
  task_content="${task_content//\/workspace/${workdir}}"

  rm -f "${report_file}" "${log_file}" "${opencode_log}"

  echo "[+] Running OpenCode, logging to ${opencode_log} ..."

  set +e
  # Use script command if available for better output capture
  # Note: script syntax differs between Linux (util-linux) and macOS (BSD)
  if command -v script >/dev/null 2>&1; then
    # Detect OS: Linux uses -c flag, macOS/BSD uses different syntax
    if [[ "$(uname -s)" == "Linux" ]]; then
      # Linux (util-linux) syntax: script -q -e -c "command" file
      # Replace /workspace in the task content before passing to opencode
      script -q -e -c "python3 -c 'import os,pathlib,subprocess; model=os.environ.get(\"OPENCODE_MODEL\",\"opencode/grok-code\"); content=pathlib.Path(\"${task_file}\").read_text(encoding=\"utf-8\").replace(\"/workspace\",\"${workdir}\"); subprocess.run([\"opencode\",\"-m\",model,\"run\",content])'" "${opencode_log}" 2>&1 | tee -a "${log_file}"
      OC_RC=$?
    else
      # macOS/BSD syntax: script -q file command (no -c flag)
      # Fall back to tee method on macOS as script syntax is more complex
      if command -v stdbuf >/dev/null 2>&1; then
        stdbuf -oL -eL opencode -m "${OPENCODE_MODEL}" run "${task_content}" 2>&1 | tee "${opencode_log}" | tee -a "${log_file}"
      else
        opencode -m "${OPENCODE_MODEL}" run "${task_content}" 2>&1 | tee "${opencode_log}" | tee -a "${log_file}"
      fi
      OC_RC=${PIPESTATUS[0]}
    fi
  else
    # Fallback: best-effort line-buffering + tee to both files
    if command -v stdbuf >/dev/null 2>&1; then
      stdbuf -oL -eL opencode -m "${OPENCODE_MODEL}" run "${task_content}" 2>&1 | tee "${opencode_log}" | tee -a "${log_file}"
    else
      opencode -m "${OPENCODE_MODEL}" run "${task_content}" 2>&1 | tee "${opencode_log}" | tee -a "${log_file}"
    fi
    OC_RC=${PIPESTATUS[0]}
  fi
  set -e

  if [[ ${OC_RC} -ne 0 ]]; then
    echo "[!] OpenCode returned non-zero exit code: ${OC_RC}"
    echo "    See: ${opencode_log}"
    echo "    See: ${log_file}"
  fi

  # Compatibility shim: create symlinks AFTER checking where report was created
  # Some OpenCode runs may write to workspace/report.md (relative path)
  local alt_report_1="${workdir}/workspace/report.md"
  local alt_report_2="${workdir}/report.md"

  if [[ -f "${report_file}" ]]; then
    # Report.md exists in expected location, create symlinks for compatibility
    ln -sf ../Report.md "${alt_report_1}" 2>/dev/null || true
    ln -sf "${report_file##*/}" "${alt_report_2}" 2>/dev/null || true
  elif [[ -f "${alt_report_1}" ]]; then
    # OpenCode wrote to workspace/report.md, copy to Report.md and create symlink
    echo "[i] Found report at ${alt_report_1}, copying to ${report_file}"
    cp -f "${alt_report_1}" "${report_file}"
    ln -sf "${report_file##*/}" "${alt_report_2}" 2>/dev/null || true
  elif [[ -f "${alt_report_2}" ]]; then
    # OpenCode wrote to report.md, copy to Report.md and create symlink
    echo "[i] Found report at ${alt_report_2}, copying to ${report_file}"
    cp -f "${alt_report_2}" "${report_file}"
    ln -sf ../Report.md "${alt_report_1}" 2>/dev/null || true
  else
    echo "[!] report.md was not created at ${report_file}"
    echo "    See: ${opencode_log}"
    echo "    See: ${log_file}"
    return 2
  fi

  echo "[+] Done. Report written to ${report_file}"
  echo "[+] OpenCode log written to ${opencode_log}"
  echo "[+] Execution log written to ${log_file}"
  return ${OC_RC}
}

BASE_DIR="analysis"
INDEX_FILE="${BASE_DIR}/reports.md"
mkdir -p "$BASE_DIR"

# Job dir (unique, pipefail-safe)
TS="$(date +"%Y%m%d_%H%M%S")"
JOB_DIR="$(mktemp -d "${BASE_DIR}/job_${TS}_XXXXXX")"
# Convert to absolute path (required for Docker volume mounts)
JOB_DIR="$(cd "$JOB_DIR" && pwd)"
JOB_ID="$(basename "$JOB_DIR")"

echo "[+] Job id:  $JOB_ID"
echo "[+] Job dir: $JOB_DIR"

# Copy artifacts into job dir
cp "$BIN_PATH" "$JOB_DIR/input.bin"

# Handle agent/prompt file
if [[ -n "$AGENT_PATH" && -n "$PROMPT_TEXT" ]]; then
  # Both provided: combine agent content with user prompt
  if [[ ! -f "$AGENT_PATH" ]]; then
    echo "[!] Error: Agent file not found: $AGENT_PATH"
    exit 1
  fi
  {
    cat "$AGENT_PATH"
    echo ""
    echo ""
    echo "<IMPORTANT USER INSTRUCTIONS>"
    echo "$PROMPT_TEXT"
  } > "$JOB_DIR/prompt_agent.md"
  echo "[+] Combined agent file ($AGENT_PATH) with --prompt text"
elif [[ -n "$PROMPT_TEXT" ]]; then
  # Only prompt text provided
  echo "$PROMPT_TEXT" > "$JOB_DIR/prompt_agent.md"
  echo "[+] Created prompt_agent.md from --prompt text"
elif [[ -n "$AGENT_PATH" ]]; then
  # Only agent file provided
  if [[ ! -f "$AGENT_PATH" ]]; then
    echo "[!] Error: Agent file not found: $AGENT_PATH"
    exit 1
  fi
  cp "$AGENT_PATH" "$JOB_DIR/prompt_agent.md"
  echo "[+] Copied agent file: $AGENT_PATH -> $JOB_DIR/prompt_agent.md"
elif [[ -n "$TASK_PATH" ]]; then
  # Backward compatibility: use TASK_PATH if provided
  cp "$TASK_PATH" "$JOB_DIR/prompt_agent.md"
  echo "[+] Copied task file: $TASK_PATH -> $JOB_DIR/prompt_agent.md"
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
  echo "  \"tag\": \"${TAG}\","
  echo "  \"mode\": \"${MODE}\""
  echo "}"
} > "$JOB_DIR/meta.json"

# Run analysis based on mode
[[ -n "${JOB_DIR:-}" ]] || { echo "[!] JOB_DIR is empty"; exit 1; }

if [[ "$MODE" == "docker" ]]; then
  echo "[+] Checking Docker image age..."
  python3 "${SCRIPT_DIR}/docker/check_docker_age.py"

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
elif [[ "$MODE" == "local" ]]; then
  echo "[+] Running in local mode..."
  if ! check_local_requirements; then
    echo "[!] Local mode requirements not met. Exiting."
    exit 1
  fi
  set +e
  run_local_analysis 2>&1 | tee "$JOB_DIR/local.log"
  LOCAL_RC=${PIPESTATUS[0]}
  set -e
  if [[ ${LOCAL_RC} -ne 0 ]]; then
    echo "[!] Local analysis failed with exit code: ${LOCAL_RC}"
    exit ${LOCAL_RC}
  fi
fi

# Results
LOG_FILE=""
if [[ "$MODE" == "docker" ]]; then
  LOG_FILE="docker.log"
elif [[ "$MODE" == "local" ]]; then
  LOG_FILE="local.log"
fi

if [[ ! -f "$JOB_DIR/Report.md" && ! -f "$JOB_DIR/report.md" ]]; then
  echo "[!] No Report.md found."
  echo "    Check: $JOB_DIR/opencode.log"
  if [[ -n "$LOG_FILE" ]]; then
    echo "    Check: $JOB_DIR/$LOG_FILE"
  fi
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

# Determine log file name for index
INDEX_LOG_FILE=""
if [[ "$MODE" == "docker" ]]; then
  INDEX_LOG_FILE="docker.log"
elif [[ "$MODE" == "local" ]]; then
  INDEX_LOG_FILE="local.log"
fi

echo "- **${JOB_ID}** | ${BIN_NAME} | ${BIN_SIZE} bytes | tag: ${TAG:-none} | mode: ${MODE} | report: \`analysis/${JOB_ID}/Report.md\` | opencode: \`analysis/${JOB_ID}/opencode.log\` | ${MODE}: \`analysis/${JOB_ID}/${INDEX_LOG_FILE}\`" >> "$INDEX_FILE"
release_reports_lock

if [[ -f "$JOB_DIR/Report.md" ]]; then
  echo "[+] Report:  $JOB_DIR/Report.md"
else
  echo "[+] Report:  $JOB_DIR/report.md"
fi
echo "[+] OpenCode: $JOB_DIR/opencode.log"
if [[ "$MODE" == "docker" ]]; then
  echo "[+] Docker:   $JOB_DIR/docker.log"
elif [[ "$MODE" == "local" ]]; then
  echo "[+] Local:    $JOB_DIR/local.log"
fi
echo "[+] Index:   $INDEX_FILE"

echo
echo "----- report.md (head) -----"
sed -n '1,120p' "$JOB_DIR/Report.md" 2>/dev/null || sed -n '1,120p' "$JOB_DIR/report.md"


