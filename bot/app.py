from __future__ import annotations

import asyncio
import secrets
import sys
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Allow running as a script (e.g. `python bot/app.py` or `cd bot && python app.py`)
# without requiring `python -m bot`.
if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.allowlist import Allowlist, load_allowlist
from bot.config import BotConfig, load_config
from bot.db import (
    connect,
    create_job,
    get_user_agent,
    init_schema,
    list_jobs_for_user,
    mark_failed,
    mark_finished,
    mark_running,
    set_user_agent,
)
from bot.runner_local import run_r2agent
from bot.zip_utils import zip_dir


@dataclass(frozen=True)
class JobRequest:
    user_id: int
    chat_id: int
    file_path: Path
    original_name: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_allowed(allowlist: Allowlist):
    async def _guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        user = update.effective_user
        if user is None:
            return False
        if not allowlist.is_allowed(user.id):
            if update.effective_message:
                await update.effective_message.reply_text("Unauthorized.")
            return False
        return True

    return _guard


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Send me a binary as a document and I'll analyze it. Commands:\n"
        "/agents - list available agent prompts\n"
        "/read <agent_filename> - print agent prompt contents\n"
        "/use <agent_filename> - select agent prompt\n"
        "/status - show your recent jobs\n"
    )


async def cmd_agents(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: BotConfig = context.application.bot_data["cfg"]
    agents_dir = (cfg.project_root / "agents").resolve()
    if not agents_dir.exists():
        await update.message.reply_text("No agents directory found.")
        return
    files = sorted([p.name for p in agents_dir.iterdir() if p.is_file()])
    if not files:
        await update.message.reply_text("No agent prompts found.")
        return
    await update.message.reply_text("Available agents:\n" + "\n".join(files))


async def cmd_read(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: BotConfig = context.application.bot_data["cfg"]
    agents_dir = (cfg.project_root / "agents").resolve()

    if not context.args:
        await update.message.reply_text("Usage: /read <agent_filename>")
        return

    agent_name = context.args[0].strip()
    agent_path = (agents_dir / agent_name).resolve()

    # Prevent path traversal: the resolved file must be inside agents/.
    try:
        agent_path.relative_to(agents_dir)
    except Exception:
        await update.message.reply_text("Invalid agent path.")
        return

    if not agent_path.exists() or not agent_path.is_file():
        await update.message.reply_text(f"Agent not found: {agent_name}")
        return

    content = agent_path.read_text(encoding="utf-8", errors="replace")
    payload = f"Agent: {agent_path.name}\n\n{content}"

    # Telegram message limit is ~4096 chars; send in chunks.
    chunk_size = 3800
    for i in range(0, len(payload), chunk_size):
        await update.message.reply_text(payload[i : i + chunk_size])


async def cmd_use(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: BotConfig = context.application.bot_data["cfg"]
    conn = context.application.bot_data["db"]
    user = update.effective_user
    if user is None:
        return

    if not context.args:
        await update.message.reply_text("Usage: /use <agent_filename>")
        return

    agent_name = context.args[0].strip()
    agent_path = (cfg.project_root / "agents" / agent_name).resolve()
    if not agent_path.exists():
        await update.message.reply_text(f"Agent not found: {agent_name}")
        return

    set_user_agent(conn, user.id, str(agent_path))
    await update.message.reply_text(f"Selected agent: {agent_name}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = context.application.bot_data["db"]
    user = update.effective_user
    if user is None:
        return
    jobs = list_jobs_for_user(conn, user.id, limit=10)
    if not jobs:
        await update.message.reply_text("No jobs yet.")
        return
    lines = []
    for j in jobs:
        dur = f"{j.duration_s}s" if j.duration_s is not None else "-"
        lines.append(f"{j.job_id} | {j.status} | {dur} | {Path(j.agent).name}")
    await update.message.reply_text("Recent jobs:\n" + "\n".join(lines))


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: BotConfig = context.application.bot_data["cfg"]
    queue: asyncio.Queue[JobRequest] = context.application.bot_data["queue"]

    msg = update.message
    user = update.effective_user
    if msg is None or user is None or msg.document is None:
        return

    doc = msg.document
    file_id = doc.file_id
    original_name = doc.file_name or "binary"

    cfg.uploads_dir.mkdir(parents=True, exist_ok=True)
    safe_name = original_name.replace("/", "_")
    dest = cfg.uploads_dir / f"{int(time.time())}_{user.id}_{safe_name}"

    await msg.reply_text("Received. Downloading...")
    await context.bot.send_chat_action(chat_id=msg.chat_id, action=ChatAction.TYPING)

    tg_file = await context.bot.get_file(file_id)
    await tg_file.download_to_drive(custom_path=str(dest))

    await msg.reply_text("Queued for analysis.")
    await queue.put(
        JobRequest(
            user_id=user.id,
            chat_id=msg.chat_id,
            file_path=dest,
            original_name=original_name,
        )
    )


async def worker_loop(app: Application) -> None:
    cfg: BotConfig = app.bot_data["cfg"]
    conn = app.bot_data["db"]
    queue: asyncio.Queue[JobRequest] = app.bot_data["queue"]

    while True:
        req = await queue.get()
        created_at = utc_now_iso()
        job_id = f"tg_{req.user_id}_{int(time.time())}_{secrets.token_hex(3)}"

        agent_pref = get_user_agent(conn, req.user_id)
        agent_path = Path(agent_pref).resolve() if agent_pref else cfg.default_agent

        create_job(
            conn,
            job_id=job_id,
            user_id=req.user_id,
            agent=str(agent_path),
            tag=req.original_name,
            created_at=created_at,
        )

        started = time.time()
        mark_running(conn, job_id, utc_now_iso())
        try:
            # Run analysis
            runner_log = cfg.jobs_root / "_bot_runner_logs" / f"{job_id}.log"
            result = await run_r2agent(
                project_root=cfg.project_root,
                binary_path=req.file_path,
                agent_prompt_path=agent_path,
                tag=req.original_name,
                log_path=runner_log,
            )

            # Zip output (exclude input.bin just in case)
            zip_path = result.job_dir / "result.zip"
            zip_dir(
                src_dir=result.job_dir,
                dest_zip=zip_path,
                exclude_names=("input.bin",),
            )

            duration_s = int(time.time() - started)
            mark_finished(
                conn,
                job_id,
                finished_at=utc_now_iso(),
                duration_s=duration_s,
                runner_job_id=result.job_id,
                runner_job_dir=str(result.job_dir),
                zip_path=str(zip_path),
            )

            await app.bot.send_message(
                chat_id=req.chat_id,
                text=f"Finished: {result.job_id} ({duration_s}s). Uploading results...",
            )
            await app.bot.send_document(
                chat_id=req.chat_id,
                document=zip_path.open("rb"),
                filename=f"{result.job_id}.zip",
            )
        except Exception as e:
            duration_s = int(time.time() - started)
            mark_failed(
                conn,
                job_id,
                finished_at=utc_now_iso(),
                duration_s=duration_s,
                runner_job_id=None,
                runner_job_dir=None,
                error=str(e),
            )
            await app.bot.send_message(
                chat_id=req.chat_id, text=f"Job failed after {duration_s}s: {e}"
            )
        finally:
            # Best-effort cleanup of upload
            try:
                req.file_path.unlink(missing_ok=True)
            except Exception:
                pass
            queue.task_done()


def build_app() -> Application:
    config_path = Path(__file__).resolve().parent / "config.json"
    cfg = load_config(config_path)
    allowlist = load_allowlist(cfg.allowed_users_file)

    conn = connect(cfg.sqlite_path)
    init_schema(conn)

    app = Application.builder().token(cfg.telegram_bot_token).build()

    app.bot_data["cfg"] = cfg
    app.bot_data["db"] = conn
    app.bot_data["queue"] = asyncio.Queue()

    guard = require_allowed(allowlist)

    def wrap(handler):
        async def _wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if await guard(update, context):
                await handler(update, context)

        return _wrapped

    app.add_handler(CommandHandler("start", wrap(cmd_start)))
    app.add_handler(CommandHandler("agents", wrap(cmd_agents)))
    app.add_handler(CommandHandler("read", wrap(cmd_read)))
    app.add_handler(CommandHandler("use", wrap(cmd_use)))
    app.add_handler(CommandHandler("status", wrap(cmd_status)))
    app.add_handler(MessageHandler(filters.Document.ALL, wrap(handle_document)))

    async def _post_init(application: Application) -> None:
        # Start worker tasks (concurrency-limited by number of workers).
        for _ in range(cfg.concurrency):
            application.create_task(worker_loop(application))

    app.post_init = _post_init  # type: ignore[attr-defined]
    return app


if __name__ == "__main__":
    application = build_app()
    application.run_polling()


