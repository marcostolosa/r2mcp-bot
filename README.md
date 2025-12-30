# r2agent (radare2 + r2mcp + OpenCode)

Automated reverse engineering and malware analysis system using radare2, OpenCode AI agents, and Telegram bot integration.

## Quick Start

### Build Docker Image

```bash
docker build -t r2agent:dev -f docker/Dockerfile .
```

### Run Analysis

```bash
# Docker mode (recommended)
./run_r2agent.sh --mode docker --file /path/to/binary --agent agents/analyze.task.md

# Local mode (requires local radare2 + OpenCode installation)
./run_r2agent.sh --mode local --file /path/to/binary --agent agents/crackme.task.md
```

## Repository Structure

- `agents/`: Analysis task prompts (analyze.task.md, crackme.task.md)
- `analysis/`: Job outputs (job_*/, _uploads, _bot_runner_logs, _watchdog_logs)
- `bot/`: Telegram bot for remote analysis
- `docker/`: Docker image (Dockerfile, run_analysis.sh, watchdog.py, check_docker_age.py)
- `utilities/`: Maintenance scripts (deployer.sh)

For detailed documentation, see [README_extended.md](README_extended.md).
