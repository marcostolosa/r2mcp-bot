# Telegram Bot for r2agent

Telegram bot that accepts binaries from allowlisted users, runs Docker analysis via `run_r2agent.sh`, and sends back the `Report.md`.

## What It Does

- Accepts binary uploads from allowed Telegram users
- Runs automated binary analysis using r2agent (Docker mode)
- Sends `Report.md` back to user when analysis completes
- Provides inline menus for agent and model selection
- Tracks job history and status

## Setup

### 1. Create Configuration Files

The bot requires two configuration files that are **not** tracked in Git (for security):

```bash
# Copy configuration templates
cp bot/config.sample bot/config.json
cp bot/allowlist.json.sample bot/allowlist.json
```

### 2. Edit bot/config.json

```json
{
  "telegram_bot_token": "REPLACE_ME",
  "allowed_users_file": "allowlist.json",
  "sqlite_path": "bot.sqlite3",
  "concurrency": 4,
  "project_root_relative": "..",
  "default_agent": "../agents/analyze.task.md",
  "jobs_root": "../analysis",
  "uploads_dir": "../analysis/_uploads"
}
```

**Configuration options:**

- `telegram_bot_token`: Your Telegram bot token from [@BotFather](https://t.me/botfather) (required)
- `allowed_users_file`: Path to allowlist file (default: `allowlist.json`)
- `sqlite_path`: Path to SQLite database (default: `bot.sqlite3`)
- `concurrency`: Maximum concurrent analysis jobs (default: 4)
- `project_root_relative`: Relative path from `bot/` to project root (default: `..`)
- `default_agent`: Default agent prompt (default: `../agents/analyze.task.md`)
- `jobs_root`: Directory for job outputs (default: `../analysis`)
- `uploads_dir`: Directory for uploaded binaries (default: `../analysis/_uploads`)

### 3. Edit bot/allowlist.json

```json
{
  "allowed_user_ids": [
    123456789,
    987654321
  ]
}
```

To find your Telegram user ID:
1. Open [@userinfobot](https://t.me/userinfobot) in Telegram
2. Send it any message
3. It will reply with your numeric user ID

Only users in this list can use the bot.

## Installation

From the repository root:

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r bot/requirements.txt
```

## Running the Bot

From the repository root:

```bash
# Make sure virtual environment is active
source .venv/bin/activate

# Start bot
python -m bot
```

The bot will start listening for messages from allowed users.

## Bot Commands

### Text Commands

- `/start` - Show main menu with inline buttons
- `/agents` - List available agent prompts
- `/read <agent_filename>` - Send the agent prompt file as a document
- `/use <agent|number>` - Select analysis agent (or show selection menu)
- `/llm <model|number>` - Select LLM model (or show selection menu)
- `/status` - Show your recent jobs with status and duration

### Inline Menu Buttons

After sending `/start`, you can use inline buttons:

- **📄 Select Agent**: Choose from available agent prompts
- **🧠 Select Model**: Choose from available OpenCode LLM models
- **📊 Job Status**: View your recent analysis jobs
- **📥 Download Agents**: Download agent prompt files
- **ℹ️ Help**: Show help text with available commands

## Available Agent Prompts

Located in `agents/` directory:

- **analyze.task.md**: General security analysis focused on finding vulnerabilities (default)
- **crackme.task.md**: Specialized for CTF challenges and crackmes

### Changing Agents

**Via command:**
```
/use crackme.task.md
```

**Via inline menu:**
- Tap "📄 Select Agent"
- Select from numbered list

**Via number:**
```
/use 2    # Selects the second agent in the list
```

## Available LLM Models

- `opencode/grok-code` (default)
- `opencode/big-pickle`
- `opencode/gpt-5-nano`
- `opencode/glm-4.7-free`

### Changing Models

**Via command:**
```
/llm opencode/gpt-5-nano
```

**Via short name:**
```
/llm gpt-5-nano    # Automatically adds "opencode/" prefix
```

**Via inline menu:**
- Tap "🧠 Select Model"
- Select from numbered list

## Uploading Binaries for Analysis

Simply send any binary file as a document to the bot. The bot will:

1. Download the binary to `analysis/_uploads/`
2. Queue the analysis job
3. Use your selected agent and model (or defaults)
4. Run analysis via Docker container
5. Send `Report.md` back to you

### Bot Response Flow

1. **Download**: `📥 Received! Downloading...`
2. **Queue**: `⏳ Queued for analysis.`
3. **Start**: `🚀 Started: tg_<id>...` (includes model and agent)
4. **Finish**: `✅ Finished: tg_<id> (45s). Uploading Report.md...`
5. **Report**: Sends `Report.md` as a document

## Job Status

Use `/status` or tap **📊 Job Status** to see your recent jobs:

```
📌 Recent Jobs:

✅ tg_123456_1735209600_abc
   └─ 📊 Status: finished
   └─ ⏱️  Total time: 45s
   └─ 📄 Prompt agent: crackme.task.md
```

Status icons:
- ⏳ Queued
- 🟡 Running
- ✅ Finished
- ❌ Failed

## Technical Notes

### Database

- **File**: `bot/bot.sqlite3`
- **Location**: In `bot/` directory
- **Tables**:
  - `jobs`: Job metadata (job_id, user_id, agent, tag, status, created_at, finished_at, duration_s, runner_job_id, runner_job_dir, error)
  - `user_settings`: User preferences (user_id, agent, llm_model)
- **Auto-created**: Schema initialized on bot startup

### Uploaded Files

- **Location**: `analysis/_uploads/`
- **Naming**: `<timestamp>_<user_id>_<safe_filename>`
- **Retention**: Files are kept on disk

### Job Outputs

- **Location**: `analysis/job_<timestamp>_<id>/`
- **Contents**:
  - `input.bin`: Copy of uploaded binary
  - `prompt_agent.md`: Agent prompt used
  - `Report.md`: Analysis report (sent to user)
  - `opencode.log`: OpenCode execution log
  - `docker.log`: Container execution log
  - `meta.json`: Job metadata

### Bot Runner Logs

- **Location**: `analysis/_bot_runner_logs/`
- **Naming**: `<job_id>.log`
- **Content**: Full output of `run_r2agent.sh` for each job

### User Preferences

The bot remembers your preferences per user:
- Selected agent prompt
- Selected LLM model

These are stored in the SQLite database and used as defaults for future jobs.

## Integration with r2agent

The bot always uses **Docker mode** to run analysis. It calls `run_r2agent.sh` with:

```bash
./run_r2agent.sh \
  --mode docker \
  --file <binary_path> \
  --agent <agent_path> \
  --model <llm_model> \
  --tag <original_filename>
```

This ensures consistent behavior regardless of host system configuration.

## Monitoring and Cleanup

For production deployments, consider running the watchdog alongside the bot:

```bash
# In terminal 1: Run bot
python -m bot

# In terminal 2: Run watchdog to cleanup stuck containers
python3 docker/watchdog.py --interval 60 --timeout 900
```

The watchdog will stop containers running longer than 15 minutes (configurable).

## Troubleshooting

### Bot fails to start

- **Missing token**: Check `bot/config.json` has valid `telegram_bot_token`
- **Missing dependencies**: Run `pip install -r bot/requirements.txt`
- **Database locked**: Delete `bot/bot.sqlite3` and restart

### "Unauthorized" message

- Add your Telegram user ID to `bot/allowlist.json`
- Get your ID from [@userinfobot](https://t.me/userinfobot)
- Restart the bot after editing the file

### Jobs hanging

- Run `docker/watchdog.py` to cleanup stuck containers
- Check `analysis/_bot_runner_logs/` for errors
- Verify Docker image is not too old: `python3 docker/check_docker_age.py`

### Missing Report.md

- Check `analysis/_bot_runner_logs/<job_id>.log` for errors
- Verify job directory exists in `analysis/`
- Check Docker container logs: `docker logs r2agent_<job_id>`

## Security Notes

- **Allowlist only**: Only users in `bot/allowlist.json` can use the bot
- **No shell access**: Bot only runs predefined analysis via Docker
- **Isolated containers**: Each job runs in a fresh Docker container
- **No execution**: Analysis is static-only (no running of user binaries)
- **Token storage**: Keep `bot/config.json` private (not in Git)
