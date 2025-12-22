#!/usr/bin/env bash
# Create a clean copy of the r2agent project for publishing to GitHub.
# Usage:
#   ./deployer.sh /path/to/r2agent [optional_dest_dir]
#
# Example (from parent directory):
#   ./deployer.sh r2agent
#   -> creates r2agent_git with cleaned analysis/, logs and SQLite DB.

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 /path/to/r2agent [optional_dest_dir]" >&2
  exit 1
fi

SRC_DIR="$1"
SRC_DIR="${SRC_DIR%/}"  # strip trailing slash if present

if [[ ! -d "$SRC_DIR" ]]; then
  echo "[!] Source directory not found: $SRC_DIR" >&2
  exit 1
fi

if [[ $# -ge 2 ]]; then
  DEST_DIR="$2"
else
  DEST_DIR="${SRC_DIR}_git"
fi

if [[ -e "$DEST_DIR" ]]; then
  echo "[!] Destination already exists: $DEST_DIR" >&2
  echo "    Delete it or choose a different name." >&2
  exit 1
fi

echo "[+] Creating clean copy"
echo "    Source:      $SRC_DIR"
echo "    Destination: $DEST_DIR"

# Copy everything first (including hidden files).
cp -a "$SRC_DIR" "$DEST_DIR"

###############################################################################
# 1) Clean analysis outputs (but keep directory structure)
###############################################################################

ANALYSIS_DIR="$DEST_DIR/analysis"
if [[ -d "$ANALYSIS_DIR" ]]; then
  echo "[+] Cleaning analysis directory in destination"

  # Remove everything under analysis/ and recreate the structure empty.
  rm -rf "${ANALYSIS_DIR:?}/"*

  mkdir -p \
    "$ANALYSIS_DIR" \
    "$ANALYSIS_DIR/_bot_runner_logs" \
    "$ANALYSIS_DIR/_uploads" \
    "$ANALYSIS_DIR/_watchdog_logs"

  # Empty marker files so Git can track the folders.
  : > "$ANALYSIS_DIR/.gitkeep"
  : > "$ANALYSIS_DIR/_bot_runner_logs/.gitkeep"
  : > "$ANALYSIS_DIR/_uploads/.gitkeep"
  : > "$ANALYSIS_DIR/_watchdog_logs/.gitkeep"

  # If reports.md exists in the destination, truncate it (do not leak job metadata).
  if [[ -f "$ANALYSIS_DIR/reports.md" ]]; then
    echo "[+] Truncating analysis/reports.md in destination"
    : > "$ANALYSIS_DIR/reports.md"
  fi
fi

###############################################################################
# 2) Remove local SQLite databases
###############################################################################

if [[ -d "$DEST_DIR/bot" ]]; then
  echo "[+] Removing SQLite state from bot/"
  rm -f "$DEST_DIR"/bot/bot.sqlite3*
fi

###############################################################################
# 3) Remove logs and temporary artifacts
###############################################################################

echo "[+] Removing *.log and *.zip files from destination copy"
find "$DEST_DIR" -type f \( -name "*.log" -o -name "*.zip" -o -name "*.tmp" \) -delete || true

echo "[+] Done."
echo "    Clean project ready at: $DEST_DIR"


