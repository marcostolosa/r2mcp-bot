# Telegram bot (local runner)

This bot accepts binaries from an allowlisted set of Telegram user IDs, runs the existing local Docker analysis via `scripts/run_r2agent.sh`, and sends back the `Report.md` file when finished.

### How it works

The bot orchestrates the analysis workflow:

1. **User uploads binary** → Bot downloads it to `analysis/_uploads/`
2. **Bot selects agent & LLM** → Uses user preferences (set via `/use` and `/llm` commands) or defaults
3. **Bot calls runner** → Invokes `bot/runner_local.py` which executes `scripts/run_r2agent.sh`
4. **Host script prepares job** → Creates job directory, copies binary and agent prompt file
5. **Docker container runs** → Mounts job directory as `/workspace`, receives:
   - **Agent prompt**: Via mounted file `/workspace/prompt_agent.md` (copied by host script)
   - **LLM model**: Via environment variable `OPENCODE_MODEL` (set by host script)
6. **Container executes** → `docker/run_analysis.sh` runs OpenCode with the agent prompt and LLM model
7. **Results returned** → Bot sends `Report.md` back to the user via Telegram

**Key files:**

- `bot/app.py`: Main bot logic, handles Telegram commands and file uploads
- `bot/runner_local.py`: Wrapper that calls `scripts/run_r2agent.sh` with proper parameters
- `scripts/run_r2agent.sh`: Host-side script that prepares job directory and launches Docker container
- `docker/run_analysis.sh`: Container entrypoint that runs OpenCode analysis

### Setup

**Important**: `bot/config.json` and `bot/allowlist.json` are **local-only** files that are ignored by Git. You must create them from the sample files:

```bash
cp bot/config.sample bot/config.json
cp bot/allowlist.json.sample bot/allowlist.json
```

Then edit the files:

- `bot/config.json`: Set your `telegram_bot_token` and adjust `concurrency` (default: 4) if needed.
- `bot/allowlist.json`: Add your Telegram numeric user IDs to the `allowed_user_ids` array.

### Install

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r bot/requirements.txt
```

### Run

From the repo root:

```bash
python -m bot
```

### Notes

- The bot stores job metadata in `bot/bot.sqlite3`.
- Uploaded binaries are downloaded to `analysis/_uploads/` (and kept on disk).
- Job outputs are under `analysis/job_*/`. The bot only sends `Report.md` back to the user.
