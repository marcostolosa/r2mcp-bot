## Telegram bot (local runner)

This bot accepts binaries from an allowlisted set of Telegram user IDs, runs the existing local Docker analysis via `scripts/run_r2agent.sh`, and sends back the `Report.md` file when finished.

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


