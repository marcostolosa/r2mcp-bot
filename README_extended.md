# r2agent - Extended Documentation

Complete documentation for the r2agent automated reverse engineering system.

## System Overview

r2agent orchestrates binary analysis using radare2, the r2mcp MCP server, and OpenCode AI agents.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    User / Telegram Bot                       │
└────────────────────────────┬────────────────────────────────┘
                         │
                         ▼
                ┌─────────────────────┐
                │  run_r2agent.sh   │
                └────────┬───────────┘
                         │
            ┌────────────┴────────────┐
            │                         │
            ▼                         ▼
     ┌──────────────┐         ┌──────────────┐
     │ Docker Mode  │         │ Local Mode   │
     └──────┬───────┘         └──────┬───────┘
            │                        │
            ▼                        ▼
     ┌──────────────────┐   ┌──────────────────┐
     │  run_analysis.sh │   │  local analysis  │
     └────────┬─────────┘   └────────┬─────────┘
              │                       │
              └───────────┬───────────┘
                          ▼
                ┌─────────────────────┐
                │     OpenCode       │
                └────────┬───────────┘
                         │
                         ▼
                ┌─────────────────────┐
                │   Report.md        │
                └─────────────────────┘
```

## run_r2agent.sh - Analysis Script

Main entry point for running binary analysis.

### Usage

```bash
./run_r2agent.sh --mode <local|docker> --file /path/to/binary [options]
```

### Required Arguments

- `--mode <local|docker>`: Execution mode
  - `docker`: Runs analysis in isolated Docker container (recommended)
  - `local`: Uses local radare2 and OpenCode installation

- `--file <path>`: Path to the binary file to analyze

- `--agent <file>` OR `--prompt <text>`: At least one required
  - `--agent <file>`: Path to agent/task file (e.g., `agents/crackme.task.md`)
  - `--prompt <text>`: Direct prompt text (can be combined with `--agent`)

### Optional Arguments

- `--model <model>`: OpenCode model to use (default: `opencode/grok-code`)
  - Available models: `opencode/grok-code`, `opencode/big-pickle`, `opencode/gpt-5-nano`, `opencode/glm-4.7-free`

- `--tag <tag>`: Tag for organizing jobs (useful for grouping analyses)

- `--help, -h`: Show help message

### Examples

```bash
# Basic docker analysis
./run_r2agent.sh --mode docker --file ./binary --agent agents/analyze.task.md

# With custom model and tag
./run_r2agent.sh --mode docker --file ./crackme.bin --agent agents/crackme.task.md --model opencode/gpt-5-nano --tag "ctf_challenge_1"

# Local mode with direct prompt
./run_r2agent.sh --mode local --file ./binary --prompt "Find all vulnerabilities in this binary"

# Combined agent + prompt
./run_r2agent.sh --mode docker --file ./binary --agent agents/crackme.task.md --prompt "Focus on crypto functions"
```

### Output

Each analysis creates a job directory under `analysis/job_<timestamp>_<id>/`:

- `input.bin`: Copy of analyzed binary
- `prompt_agent.md`: Agent prompt used
- `Report.md`: Analysis report (main deliverable)
- `opencode.log`: OpenCode execution log
- `docker.log` or `local.log`: Container/host execution log
- `meta.json`: Job metadata (job_id, created_at, binary_name, binary_size, tag, mode)
- `FINISHED_<seconds>`: Completion marker with duration

Global index: `analysis/reports.md`

## Docker Mode

### Building the Image

```bash
# Build for current platform
docker build -t r2agent:dev -f docker/Dockerfile .

# Build for Apple Silicon (arm64)
docker build --platform linux/arm64 -t r2agent:dev -f docker/Dockerfile .
```

### Container Contents

- **radare2**: Built from source with full analysis capabilities
- **r2mcp**: MCP server for radare2 integration
- **OpenCode CLI**: AI-powered code analysis
- **Plugins**: r2ghidra, r2ghidra-sleigh

### Container Architecture

- **Base**: Ubuntu 24.04
- **User**: `op`
- **Workspace**: `/workspace` (mount point from host)
- **Entry point**: `/usr/local/bin/run_analysis.sh`

### Automatic Image Aging Check

When running in Docker mode, `run_r2agent.sh` automatically checks if the Docker image is older than 5 days. If so, it prompts to rebuild via `docker/check_docker_age.py`.

## Local Mode

### Requirements

Local mode requires the following tools installed and available in PATH:

```bash
# Check requirements
opencode --version
r2 -v
r2pm -v
```

### Installing Required r2pm Plugins

```bash
r2pm -ci r2mcp r2ghidra r2ghidra-sleigh
```

### Verification

Run `./run_r2agent.sh --mode local --file ./binary --agent agents/analyze.task.md` to verify your setup.

## Scripts in docker/

### watchdog.py - Container Monitoring

Monitors Docker containers and stops those running longer than a specified timeout.

**Usage:**

```bash
python3 docker/watchdog.py [options]
```

**Options:**

- `--once`: Run once and exit
- `--interval <seconds>`: Check interval (default: 60)
- `--timeout <seconds>`: Container timeout (default: 900 = 15 minutes)

**Purpose:**
- Useful when running the Telegram bot in production
- Prevents runaway containers from consuming resources
- Logs actions to `analysis/_watchdog_logs/watchdog_<YYYYMMDD>.log`

**Example:**

```bash
# Run once
python3 docker/watchdog.py --once

# Run continuously with 30-minute timeout
python3 docker/watchdog.py --interval 120 --timeout 1800
```

### check_docker_age.py - Automatic Image Rebuild

Checks if the Docker image is older than 5 days and rebuilds if necessary.

**Usage:**

```bash
python3 docker/check_docker_age.py
```

**Behavior:**
- If image age > 5 days: Rebuilds automatically
- If image age ≤ 5 days: Does nothing

### run_analysis.sh - Container Entry Point

Executed inside the Docker container to perform the analysis.

**Inputs:**
- `/workspace/input.bin`: Binary to analyze
- `/workspace/prompt_agent.md`: Agent prompt (mounted from host)
- `OPENCODE_MODEL` environment variable: LLM model to use

**Outputs:**
- `/workspace/Report.md`: Analysis report
- `/workspace/opencode.log`: OpenCode execution log

## Telegram Bot

The Telegram bot provides remote analysis capabilities. See [bot/README.md](bot/README.md) for detailed setup and configuration.

### Bot Workflow

1. User uploads binary → Bot downloads to `analysis/_uploads/`
2. Bot selects agent & LLM → Uses user preferences (set via `/use` and `/llm` commands) or defaults
3. Bot calls runner → Invokes `bot/runner_local.py` which executes `run_r2agent.sh`
4. Host script prepares job → Creates job directory, copies binary and agent prompt file
5. Docker container runs → Mounts job directory as `/workspace`
6. Container executes → `docker/run_analysis.sh` runs OpenCode
7. Results returned → Bot sends `Report.md` back to the user via Telegram

## Available Agents

Agent prompts are located in the `agents/` directory:

- **agents/analyze.task.md**: General security analysis focused on finding vulnerabilities (default)
- **agents/crackme.task.md**: Specialized for CTF challenges and crackmes

### Creating Custom Agents

Create a new `.md` file in `agents/` following the structure of existing agents. Agents define the analysis workflow, security focus areas, and output format requirements.

## Available LLM Models

- `opencode/grok-code` (default)
- `opencode/big-pickle`
- `opencode/gpt-5-nano`
- `opencode/glm-4.7-free`

These can be specified via `--model` flag in `run_r2agent.sh` or via `/llm` command in the bot.

## Maintenance Scripts

### utilities/deployer.sh - Clean Deployment

Creates a clean copy of the project for publishing to GitHub.

**Usage:**

```bash
./utilities/deployer.sh /path/to/r2agent [optional_dest_dir]
```

**What it cleans:**
- Removes all job outputs from `analysis/`
- Truncates `analysis/reports.md`
- Removes SQLite databases from `bot/`
- Removes `.log`, `.zip`, and `.tmp` files

**Result:**
- Clean project ready at `/path/to/r2agent_git` (or custom dest)

## Development

### Interactive Container Debug

```bash
# Start container with bash
mkdir -p /tmp/r2job
docker run --rm -it -v /tmp/r2job:/workspace r2agent:dev bash

# Manual analysis
cd /workspace
opencode -m opencode/grok-code run "$(cat prompt_agent.md)"
```

### Testing

Test your setup with a simple binary:

```bash
./run_r2agent.sh --mode docker --file /bin/ls --agent agents/analyze.task.md --tag test
```

## Troubleshooting

### Docker issues

- **Permission denied**: Ensure Docker is running and you have access
- **Image too old**: The script will prompt to rebuild; confirm with `docker images r2agent:dev`
- **Container not starting**: Check `docker logs r2agent_<job_id>` for errors

### Local mode issues

- **opencode not found**: Install from https://opencode.ai/install
- **r2pm plugins missing**: Run `r2pm -ci r2mcp r2ghidra r2ghidra-sleigh`
- **Analysis fails**: Check `opencode.log` and `local.log` in the job directory

### Bot issues

- **Unauthorized**: Add your Telegram user ID to `bot/allowlist.json`
- **Jobs stuck**: Run `docker/watchdog.py` to clean up stuck containers
- **No Report.md**: Check `analysis/_bot_runner_logs/` and the job directory

## Compatibility Notes

### Report File Compatibility

The container creates symlinks for report file compatibility:
- `workspace/report.md` → `../Report.md`
- `report.md` → `Report.md`

All report writes converge to `/workspace/Report.md`.

### Platform Support

- **macOS (Apple Silicon)**: Full support with `--platform linux/arm64`
- **Linux**: Native support
- **Windows**: Requires WSL2 for Docker mode

## Job Index

The `analysis/reports.md` file contains a global index of all analysis jobs:

```markdown
- **job_20241226_120000_abc123** | crackme.bin | 12345 bytes | tag: ctf | mode: docker | ...
```

This file is updated automatically after each job completes.

## Database

The bot uses SQLite (`bot/bot.sqlite3`) to store:
- Job metadata (job_id, user_id, status, duration)
- User preferences (selected agent, LLM model)
- Job history

The database is schema-initialized automatically on bot startup.
