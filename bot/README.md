## Telegram bot (local runner)

This bot accepts binaries from an allowlisted set of Telegram user IDs, runs the existing local Docker analysis via `scripts/run_r2agent.sh`, and sends back a zipped job folder when finished.

### Setup

- Edit `bot/config.json`:
  - `telegram_bot_token`
  - `concurrency` (default: 4)
- Edit `bot/allowlist.json` and add Telegram numeric user IDs.

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
- Uploaded binaries are downloaded to `analisis/_uploads/` and removed after the runner starts.
- Job outputs are under `analisis/job_*/` and a `result.zip` is created per job.


