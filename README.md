# r2agent (radare2 + r2mcp + OpenCode)

Repo layout:

- `docker/`: Docker build context (Dockerfile, OpenCode config, container entrypoint)
- `agents/`: analysis task prompts (e.g., `analyze.task.md`)
- `scripts/`: host-side helper scripts (e.g., `run_r2agent.sh`)
- `analisis/`: per-job outputs (created by `scripts/run_r2agent.sh`)

This repo builds a Docker image for an Ubuntu 24.04 (arm64 by default on Apple Silicon) container that:

- Builds and installs radare2 from source (git clone + sys/install.sh)
- Installs r2pm plugins: r2ghidra, decai, r2ai, r2mcp, r2ghidra-sleigh
- Installs OpenCode CLI
- Configures OpenCode MCP to start r2mcp via `r2pm -r r2mcp`
- Uses /workspace as the shared mount for binaries + tasks + report

## Build (Apple Silicon / arm64)

From the repo root:

```bash
docker build -t r2agent:dev -f docker/Dockerfile .
```

If you want to force arm64 explicitly:

```bash
docker build --platform=linux/arm64 -t r2agent:dev -f docker/Dockerfile .
```

## Run (interactive debug)

```bash
mkdir -p /tmp/r2job
docker run --rm -it -v /tmp/r2job:/workspace r2agent:dev
```

## Debug the container with bash

```bash
mkdir -p /tmp/r2job
docker run --rm -it -v /tmp/r2job:/workspace r2agent:dev bash
```


## Rebuild Docker container (useful if you make any changes)

```bash
docker build --platform linux/arm64 -t r2agent:dev -f docker/Dockerfile .
```

## Run (analysis)

Use the helper script (recommended):

```bash
./scripts/run_r2agent.sh /path/to/binary
```

Outputs are written under `./analisis/<job_id>/`.

Notes:

- The container expects the report at `/workspace/report.md`.
- If an OpenCode run attempts to write `workspace/report.md` (relative path), the entrypoint script creates a small compatibility symlink so it still lands in `/workspace/report.md`.
