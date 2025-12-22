#!/usr/bin/env bash
# Runner for the r2agent container.
# - Uses /workspace as the shared directory (mount from host).
# - Ensures an analyze.task.md exists in /workspace (copies template if missing).
# - Requires /workspace/input.bin
# - Runs OpenCode and writes /workspace/report.md and /workspace/opencode.log
#
# Parameter passing mechanism:
# - Agent prompt: Received via mounted file at /workspace/prompt_agent.md
#   The host script (scripts/run_r2agent.sh) copies the agent file into the job directory
#   before mounting it as /workspace. If no agent is provided, a template is copied from
#   /opt/prompt_agent.md (see lines 32-35).
# - LLM model: Received via environment variable OPENCODE_MODEL
#   The host script sets this variable when launching the Docker container (e.g.,
#   docker run -e OPENCODE_MODEL="opencode/grok-code" ...). Defaults to "opencode/grok-code"
#   if not set (see line 61).

set -euo pipefail

WORKDIR="/workspace"
TEMPLATE_TASK="/opt/prompt_agent.md"
TASK_FILE="${WORKDIR}/prompt_agent.md"
BIN_FILE="${WORKDIR}/input.bin"
REPORT_FILE="${WORKDIR}/Report.md"
LOG_FILE="${WORKDIR}/opencode.log"

cd "${WORKDIR}"

# Compatibility shim:
# Some OpenCode runs may try to write a relative path like "workspace/report.md"
# (missing the leading slash). Since we run from /workspace, that becomes
# "/workspace/workspace/report.md". Make that resolve to "/workspace/report.md".
#
# Important: /workspace is a host-mounted directory. Avoid creating absolute symlinks
# like "workspace -> /workspace" because they become broken on the host and can
# break post-processing (e.g., zipping job artifacts).
mkdir -p "${WORKDIR}/workspace"
ln -sf ../Report.md "${WORKDIR}/workspace/report.md"
# Compatibility for older tooling expecting /workspace/report.md
ln -sf "${REPORT_FILE##*/}" "${WORKDIR}/report.md"

if [[ ! -f "${TASK_FILE}" ]]; then
  echo "[i] No prompt_agent.md found in ${WORKDIR}, copying template..."
  cp "${TEMPLATE_TASK}" "${TASK_FILE}"
fi

if [[ ! -f "${BIN_FILE}" ]]; then
  echo "[!] No input.bin found in ${WORKDIR}."
  echo "    Put your binary at: ${BIN_FILE}"
  echo "    Task file is at:    ${TASK_FILE}"
  exec bash
fi

echo "[+] input.bin detected, starting analysis..."
echo "[i] OpenCode config: /home/op/.config/opencode/opencode.json"

# Ensure OpenCode is in PATH even in non-interactive shells
export PATH="/home/op/.opencode/bin:/home/op/.local/bin:/usr/local/bin:${PATH}"

# Best-effort preflight checks
command -v r2 >/dev/null 2>&1 && r2 -v || true
command -v r2pm >/dev/null 2>&1 && r2pm -v || true
command -v opencode >/dev/null 2>&1 && opencode --version || true

TASK_CONTENT="$(cat "${TASK_FILE}")"

rm -f "${REPORT_FILE}" "${LOG_FILE}"

echo "[+] Running OpenCode, logging to ${LOG_FILE} ..."

# LLM model selection: Read from OPENCODE_MODEL environment variable (set by host script).
# This allows the caller (scripts/run_r2agent.sh or bot) to specify which OpenCode model
# to use for analysis. Defaults to "opencode/grok-code" if not provided.
OPENCODE_MODEL="${OPENCODE_MODEL:-opencode/grok-code}"
echo "[i] OpenCode model: ${OPENCODE_MODEL}"

set +e
# Some OpenCode versions may buffer or suppress streaming output when stdout is not a TTY.
# When the container is launched from scripts (docker stdout is piped), that can make
# /workspace/opencode.log appear empty until the run finishes.
#
# Workaround: run under a pseudo-TTY (util-linux `script`) and write the session to LOG_FILE.
# Keep a fallback to the simple pipe if `script` is not available.
if command -v script >/dev/null 2>&1; then
  # Use Python to pass the prompt content as a single argv element (no shell-quoting edge cases),
  # while `script` provides a PTY to encourage streaming output.
  script -q -e -c "python3 -c 'import os,pathlib,subprocess; model=os.environ.get(\"OPENCODE_MODEL\",\"opencode/grok-code\"); subprocess.run([\"opencode\",\"-m\",model,\"run\",pathlib.Path(\"${TASK_FILE}\").read_text(encoding=\"utf-8\")])'" "${LOG_FILE}"
  OC_RC=$?
else
  # Fallback: best-effort line-buffering + tee
  if command -v stdbuf >/dev/null 2>&1; then
    stdbuf -oL -eL opencode -m "${OPENCODE_MODEL}" run "${TASK_CONTENT}" 2>&1 | tee "${LOG_FILE}"
  else
    opencode -m "${OPENCODE_MODEL}" run "${TASK_CONTENT}" 2>&1 | tee "${LOG_FILE}"
  fi
  OC_RC=${PIPESTATUS[0]}
fi
set -e

if [[ ${OC_RC} -ne 0 ]]; then
  echo "[!] OpenCode returned non-zero exit code: ${OC_RC}"
  echo "    See: ${LOG_FILE}"
fi

if [[ ! -f "${REPORT_FILE}" ]]; then
  echo "[!] report.md was not created at ${REPORT_FILE}"
  echo "    See: ${LOG_FILE}"

  # Fallback: try common alternate locations (observed in logs)
  ALT_REPORT_1="${WORKDIR}/workspace/report.md"
  ALT_REPORT_2="${WORKDIR}/report.md"
  if [[ -f "${ALT_REPORT_1}" ]]; then
    echo "[i] Found report at ${ALT_REPORT_1}, copying to ${REPORT_FILE}"
    cp -f "${ALT_REPORT_1}" "${REPORT_FILE}"
  elif [[ -f "${ALT_REPORT_2}" ]]; then
    echo "[i] Found report at ${ALT_REPORT_2}, copying to ${REPORT_FILE}"
    cp -f "${ALT_REPORT_2}" "${REPORT_FILE}"
  fi

  [[ -f "${REPORT_FILE}" ]] || exit 2
fi

echo "[+] Done. Report written to ${REPORT_FILE}"
echo "[+] Log written to ${LOG_FILE}"
exit ${OC_RC}


