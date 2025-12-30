from __future__ import annotations

import asyncio
import re
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

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
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
    get_user_llm_model,
    init_schema,
    list_jobs_for_user,
    mark_failed,
    mark_finished,
    mark_running,
    set_user_agent,
    set_user_llm_model,
)
from bot.runner_local import run_r2agent


FREE_LLM_MODELS = (
    "opencode/gpt-5-nano",
    "opencode/big-pickle",
    "opencode/glm-4.7-free",
    "opencode/grok-code",
)
DEFAULT_LLM_MODEL = "opencode/grok-code"


@dataclass(frozen=True)
class JobRequest:
    user_id: int
    chat_id: int
    file_path: Path
    original_name: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_paths(text: str) -> str:
    """Redact file system paths from text to avoid exposing server directory structure."""
    # Match Unix-like paths (absolute paths with / separators)
    # Match Windows paths (C:\path\to\file or \\server\share\path)
    # Match relative paths (path/to/file)
    patterns = [
        r"\/[a-zA-Z0-9_\-\.\~\/]+[a-zA-Z0-9_\-\.]+",  # /path/to/file (Unix absolute)
        r"[a-zA-Z]:\\[a-zA-Z0-9_\-\.\\]+[a-zA-Z0-9_\-\.]+",  # C:\path\to\file (Windows absolute)
        r"\\\\[a-zA-Z0-9_\-\.\\]+[a-zA-Z0-9_\-\.\\]+",  # \\server\share\path (Windows UNC)
        r"[a-zA-Z0-9_\-\.]+\/[a-zA-Z0-9_\-\.\/]+[a-zA-Z0-9_\-\.]+",  # relative/path/to/file
    ]
    for pattern in patterns:
        text = re.sub(pattern, "<redacted path>", text)
    return text


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


def build_main_menu() -> InlineKeyboardMarkup:
    """Build the main menu inline keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("📄 Select Agent", callback_data="menu:agent"),
            InlineKeyboardButton("🧠 Select Model", callback_data="menu:llm"),
        ],
        [
            InlineKeyboardButton("📊 Job Status", callback_data="menu:status"),
            InlineKeyboardButton(
                "📥 Download Agents", callback_data="menu:agents_list"
            ),
        ],
        [
            InlineKeyboardButton("ℹ️ Help", callback_data="menu:help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_agent_menu(
    cfg: BotConfig, conn, user_id: int
) -> tuple[str, InlineKeyboardMarkup]:
    """Build the agent selection menu with current agent info."""
    agents_dir = (cfg.project_root / "agents").resolve()
    files = (
        sorted([p.name for p in agents_dir.iterdir() if p.is_file()])
        if agents_dir.exists()
        else []
    )

    current_pref = get_user_agent(conn, user_id)
    current_path = Path(current_pref).resolve() if current_pref else cfg.default_agent
    current_name = current_path.name

    # Build message text
    lines = [
        "📄 Select Agent Prompt",
        "",
        f"✨ Current: {current_name} ⭐"
        if current_path == cfg.default_agent.resolve()
        else f"✨ Current: {current_name}",
        "",
        "Available agents:",
    ]

    # Build keyboard buttons
    keyboard = []
    for idx, name in enumerate(files, start=1):
        agent_path = (agents_dir / name).resolve()
        is_default = agent_path == cfg.default_agent.resolve()
        is_selected = name == current_name

        # Button label with emojis
        label_parts = []
        # Add number emoji
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        if idx <= len(number_emojis):
            label_parts.append(number_emojis[idx - 1])
        else:
            label_parts.append(f"{idx}.")

        label_parts.append(name)
        if is_default:
            label_parts.append("⭐")
        if is_selected:
            label_parts.append("✅")

        label = " ".join(label_parts)
        keyboard.append(
            [InlineKeyboardButton(label, callback_data=f"agent:select:{name}")]
        )

    # Add back button
    keyboard.append(
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu:main")]
    )

    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


def build_llm_menu(conn, user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Build the LLM model selection menu with current model info."""
    current = get_user_llm_model(conn, user_id) or DEFAULT_LLM_MODEL

    # Build message text
    lines = [
        "🧠 Select LLM Model",
        "",
        f"✨ Current: {current} ⭐"
        if current == DEFAULT_LLM_MODEL
        else f"✨ Current: {current}",
        "",
        "Free models:",
    ]

    # Build keyboard buttons
    keyboard = []
    number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    for idx, model in enumerate(FREE_LLM_MODELS, start=1):
        is_default = model == DEFAULT_LLM_MODEL
        is_selected = model == current

        # Button label with emojis
        label_parts = []
        if idx <= len(number_emojis):
            label_parts.append(number_emojis[idx - 1])
        else:
            label_parts.append(f"{idx}.")

        label_parts.append(model)
        if is_default:
            label_parts.append("⭐")
        if is_selected:
            label_parts.append("✅")

        label = " ".join(label_parts)
        keyboard.append(
            [InlineKeyboardButton(label, callback_data=f"llm:select:{model}")]
        )

    # Add back button
    keyboard.append(
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu:main")]
    )

    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    welcome_text = (
        "🤖 Welcome to r2agent Bot!\n\n"
        "Send me a binary as a document and I'll analyze it.\n\n"
        "Choose an option from the menu below:"
    )
    await update.message.reply_text(welcome_text, reply_markup=build_main_menu())


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

    if update.message is None:
        return
    with agent_path.open("rb") as f:
        await update.message.reply_document(
            document=f,
            filename=agent_path.name,
            caption=f"📄 {agent_path.name}",
        )


async def cmd_use(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: BotConfig = context.application.bot_data["cfg"]
    conn = context.application.bot_data["db"]
    user = update.effective_user
    if user is None:
        return

    agents_dir = (cfg.project_root / "agents").resolve()
    if not agents_dir.exists():
        await update.message.reply_text("❌ No agents directory found.")
        return

    files = sorted([p.name for p in agents_dir.iterdir() if p.is_file()])
    if not files:
        await update.message.reply_text("❌ No agent prompts found.")
        return

    current_pref = get_user_agent(conn, user.id)
    current_path = Path(current_pref).resolve() if current_pref else cfg.default_agent
    current_name = current_path.name

    def normalize_agent(raw: str) -> Optional[str]:
        s = (raw or "").strip()
        if not s:
            return None
        if s.isdigit():
            i = int(s)
            if 1 <= i <= len(files):
                return files[i - 1]
            return None
        if s in files:
            return s
        return None

    if not context.args:
        # Show inline menu instead of text list
        text, keyboard = build_agent_menu(cfg, conn, user.id)
        await update.message.reply_text(text, reply_markup=keyboard)
        return

    chosen_name = normalize_agent(context.args[0])
    if chosen_name is None:
        await update.message.reply_text(
            "❌ Invalid agent. Use /use to see available agents."
        )
        return

    agent_path = (agents_dir / chosen_name).resolve()
    # Prevent path traversal: resolved file must be inside agents/.
    try:
        agent_path.relative_to(agents_dir)
    except Exception:
        await update.message.reply_text("❌ Invalid agent path.")
        return
    if not agent_path.exists() or not agent_path.is_file():
        await update.message.reply_text(f"❌ Agent not found: {chosen_name}")
        return

    set_user_agent(conn, user.id, str(agent_path))
    await update.message.reply_text(f"✅ Selected agent: {chosen_name}")


def _normalize_llm_model(raw: str) -> Optional[str]:
    s = (raw or "").strip()
    if not s:
        return None
    if s.isdigit():
        i = int(s)
        if 1 <= i <= len(FREE_LLM_MODELS):
            return FREE_LLM_MODELS[i - 1]
        return None
    if s in FREE_LLM_MODELS:
        return s
    # Allow short names like "grok-code" / "big-pickle" / "gpt-5-nano".
    for m in FREE_LLM_MODELS:
        if s == m.split("/", 1)[-1]:
            return m
    return None


async def cmd_llm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: BotConfig = context.application.bot_data["cfg"]
    conn = context.application.bot_data["db"]
    user = update.effective_user
    if user is None:
        return

    current = get_user_llm_model(conn, user.id) or DEFAULT_LLM_MODEL

    if not context.args:
        # Show inline menu instead of text list
        text, keyboard = build_llm_menu(conn, user.id)
        await update.message.reply_text(text, reply_markup=keyboard)
        return

    chosen = _normalize_llm_model(context.args[0])
    if chosen is None:
        await update.message.reply_text(
            "❌ Invalid model. Use /llm to see the available free models."
        )
        return

    set_user_llm_model(conn, user.id, chosen, default_agent=str(cfg.default_agent))
    await update.message.reply_text(f"✅ Model set to: {chosen}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = context.application.bot_data["db"]
    user = update.effective_user
    if user is None:
        return
    jobs = list_jobs_for_user(conn, user.id, limit=10)
    if not jobs:
        await update.message.reply_text("🗂️ No jobs yet.")
        return

    lines = ["📌 Recent Jobs:", ""]
    icon = {"queued": "⏳", "running": "🟡", "finished": "✅", "failed": "❌"}

    for j in jobs:
        job_icon = icon.get(j.status, "•")
        dur = f"{j.duration_s}s" if j.duration_s is not None else "-"
        agent_name = Path(j.agent).name

        lines.append(f"{job_icon} {j.job_id}")
        lines.append(f"   └─ 📊 Status: {j.status}")
        lines.append(f"   └─ ⏱️  Total time: {dur}")
        lines.append(f"   └─ 📄 Prompt agent: {agent_name}")
        lines.append("")  # Empty line between jobs

    await update.message.reply_text("\n".join(lines))


async def safe_edit_message_text(query, text: str, reply_markup=None) -> None:
    """Safely edit message text, ignoring BadRequest if message is unchanged."""
    try:
        await query.edit_message_text(text, reply_markup=reply_markup)
    except BadRequest as e:
        # Ignore "Message is not modified" error - it means the message is already in the desired state
        if "Message is not modified" not in str(e):
            raise


async def handle_callback_query(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle callback queries from inline keyboard buttons."""
    query = update.callback_query
    if query is None:
        return

    await query.answer()  # Acknowledge the callback

    cfg: BotConfig = context.application.bot_data["cfg"]
    conn = context.application.bot_data["db"]
    user = update.effective_user
    if user is None:
        return

    callback_data = query.data

    if callback_data == "menu:main":
        # Show main menu
        welcome_text = (
            "🤖 Welcome to r2agent Bot!\n\n"
            "Send me a binary as a document and I'll analyze it.\n\n"
            "Choose an option from the menu below:"
        )
        await safe_edit_message_text(
            query, welcome_text, reply_markup=build_main_menu()
        )

    elif callback_data == "menu:agent":
        # Show agent selection menu
        text, keyboard = build_agent_menu(cfg, conn, user.id)
        await safe_edit_message_text(query, text, reply_markup=keyboard)

    elif callback_data == "menu:llm":
        # Show LLM model selection menu
        text, keyboard = build_llm_menu(conn, user.id)
        await safe_edit_message_text(query, text, reply_markup=keyboard)

    elif callback_data == "menu:status":
        # Show job status
        jobs = list_jobs_for_user(conn, user.id, limit=10)
        if not jobs:
            await safe_edit_message_text(
                query, "🗂️ No jobs yet.", reply_markup=build_main_menu()
            )
            return

        lines = ["📌 Recent Jobs:", ""]
        icon = {"queued": "⏳", "running": "🟡", "finished": "✅", "failed": "❌"}

        for j in jobs:
            job_icon = icon.get(j.status, "•")
            dur = f"{j.duration_s}s" if j.duration_s is not None else "-"
            agent_name = Path(j.agent).name

            lines.append(f"{job_icon} {j.job_id}")
            lines.append(f"   └─ 📊 Status: {j.status}")
            lines.append(f"   └─ ⏱️  Total time: {dur}")
            lines.append(f"   └─ 📄 Prompt agent: {agent_name}")
            lines.append("")

        # Add back button
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu:main")]]
        )
        await safe_edit_message_text(query, "\n".join(lines), reply_markup=keyboard)

    elif callback_data == "menu:agents_list":
        # Show agents as downloadable buttons
        agents_dir = (cfg.project_root / "agents").resolve()
        if not agents_dir.exists():
            await safe_edit_message_text(
                query, "❌ No agents directory found.", reply_markup=build_main_menu()
            )
            return
        files = sorted([p.name for p in agents_dir.iterdir() if p.is_file()])
        if not files:
            await safe_edit_message_text(
                query, "❌ No agent prompts found.", reply_markup=build_main_menu()
            )
            return

        text = "📥 Download Agent Prompts\n\nClick on an agent to download it:"

        # Build keyboard with buttons for each agent
        keyboard = []
        for agent_name in files:
            # Use callback instead of text to avoid Telegram opening browser for .md files
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"📄 {agent_name}", callback_data=f"agent:download:{agent_name}"
                    )
                ]
            )

        # Add back button
        keyboard.append(
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu:main")]
        )

        await safe_edit_message_text(
            query, text, reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif callback_data == "menu:help":
        # Show help
        help_text = (
            "ℹ️ Help\n\n"
            "Commands:\n"
            "/start - Show main menu\n"
            "/agents - List available agent prompts\n"
            "/read <agent_filename> - Send the agent prompt file\n"
            "/use <agent_filename> - Select agent prompt\n"
            "/llm - List/select the OpenCode model\n"
            "/status - Show your recent jobs\n\n"
            "Or use the menu buttons above! 👆"
        )
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu:main")]]
        )
        await safe_edit_message_text(query, help_text, reply_markup=keyboard)

    elif callback_data.startswith("agent:select:"):
        # Handle agent selection
        agent_name = callback_data.replace("agent:select:", "")
        agents_dir = (cfg.project_root / "agents").resolve()
        agent_path = (agents_dir / agent_name).resolve()

        # Prevent path traversal
        try:
            agent_path.relative_to(agents_dir)
        except Exception:
            await query.answer("❌ Invalid agent path.", show_alert=True)
            return

        if not agent_path.exists() or not agent_path.is_file():
            await query.answer(f"❌ Agent not found: {agent_name}", show_alert=True)
            return

        set_user_agent(conn, user.id, str(agent_path))
        await query.answer(f"✅ Selected agent: {agent_name}")

        # Update menu to show selection
        text, keyboard = build_agent_menu(cfg, conn, user.id)
        await safe_edit_message_text(query, text, reply_markup=keyboard)

    elif callback_data.startswith("llm:select:"):
        # Handle LLM model selection
        model_name = callback_data.replace("llm:select:", "")

        if model_name not in FREE_LLM_MODELS:
            # Try short name
            normalized = _normalize_llm_model(model_name)
            if normalized is None:
                await query.answer("❌ Invalid model.", show_alert=True)
                return
            model_name = normalized

        set_user_llm_model(
            conn, user.id, model_name, default_agent=str(cfg.default_agent)
        )
        await query.answer(f"✅ Model set to: {model_name}")

        # Update menu to show selection
        text, keyboard = build_llm_menu(conn, user.id)
        await safe_edit_message_text(query, text, reply_markup=keyboard)

    elif callback_data.startswith("agent:download:"):
        # Handle agent download
        agent_name = callback_data.replace("agent:download:", "")
        agents_dir = (cfg.project_root / "agents").resolve()
        agent_path = (agents_dir / agent_name).resolve()

        # Prevent path traversal
        try:
            agent_path.relative_to(agents_dir)
        except Exception:
            await query.answer("❌ Invalid agent path.", show_alert=True)
            return

        if not agent_path.exists() or not agent_path.is_file():
            await query.answer(f"❌ Agent not found: {agent_name}", show_alert=True)
            return

        # Send the agent file as document
        await query.answer(f"📥 Downloading {agent_name}...")
        try:
            with agent_path.open("rb") as f:
                await query.message.reply_document(
                    document=f,
                    filename=agent_path.name,
                    caption=f"📄 {agent_path.name}",
                )
        except Exception as e:
            await query.answer(f"❌ Error downloading file: {e}", show_alert=True)


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

    await msg.reply_text("📥 Received! Downloading...")
    await context.bot.send_chat_action(chat_id=msg.chat_id, action=ChatAction.TYPING)

    tg_file = await context.bot.get_file(file_id)
    await tg_file.download_to_drive(custom_path=str(dest))

    await msg.reply_text("⏳ Queued for analysis.")
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
        llm_model = get_user_llm_model(conn, req.user_id) or DEFAULT_LLM_MODEL

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
            await app.bot.send_message(
                chat_id=req.chat_id,
                text=f"🚀 Started: {job_id}\n🧠 Model: {llm_model}\n📄 Agent: {agent_path.name}",
            )
            result = await run_r2agent(
                project_root=cfg.project_root,
                binary_path=req.file_path,
                agent_prompt_path=agent_path,
                tag=req.original_name,
                log_path=runner_log,
                llm_model=llm_model,
            )

            # Verify job_dir exists and is accessible
            if not result.job_dir.exists():
                raise RuntimeError(
                    f"Job directory does not exist: {result.job_id}\n"
                    f"Exit code: {result.exit_code}"
                )

            if not result.job_dir.is_dir():
                raise RuntimeError(
                    f"Job directory path is not a directory: {result.job_id}\n"
                    f"Exit code: {result.exit_code}"
                )

            # Check exit code before looking for report
            if result.exit_code != 0:
                # Read log for error details
                error_details = ""
                if runner_log.exists():
                    try:
                        log_content = runner_log.read_text(
                            encoding="utf-8", errors="replace"
                        )
                        log_lines = log_content.strip().split("\n")
                        if log_lines:
                            # Redact paths from log lines before sending
                            error_details = redact_paths(
                                "\n".join(log_lines[-15:])
                            )  # Last 15 lines
                    except Exception:
                        pass

                error_msg = (
                    f"Analysis failed with exit code {result.exit_code}.\n"
                    f"Job ID: {result.job_id}"
                )
                if error_details:
                    error_msg += f"\n\nLast log lines:\n{error_details}"

                raise RuntimeError(error_msg)

            # Now check for report file
            report_path = result.job_dir / "Report.md"
            if not report_path.exists():
                alt = result.job_dir / "report.md"
                if alt.exists():
                    report_path = alt
                else:
                    # List what files ARE in the directory for debugging
                    existing_files = []
                    try:
                        existing_files = [f.name for f in result.job_dir.iterdir()]
                    except Exception:
                        pass

                    error_msg = (
                        f"Missing report file in job directory: {result.job_id}\n"
                        f"Exit code: {result.exit_code}"
                    )
                    if existing_files:
                        error_msg += f"\nFiles found: {', '.join(existing_files)}"
                    else:
                        error_msg += "\nDirectory appears to be empty"

                    raise FileNotFoundError(error_msg)

            duration_s = int(time.time() - started)
            mark_finished(
                conn,
                job_id,
                finished_at=utc_now_iso(),
                duration_s=duration_s,
                runner_job_id=result.job_id,
                runner_job_dir=str(result.job_dir),
            )

            await app.bot.send_message(
                chat_id=req.chat_id,
                text=f"✅ Finished: {result.job_id} ({duration_s}s). Uploading Report.md...",
            )
            await app.bot.send_document(
                chat_id=req.chat_id,
                document=report_path.open("rb"),
                filename="Report.md",
            )
        except Exception as e:
            duration_s = int(time.time() - started)

            # Try to get more context from logs if available
            # Redact paths from the exception message itself
            error_msg = redact_paths(str(e))
            if runner_log.exists():
                try:
                    log_content = runner_log.read_text(
                        encoding="utf-8", errors="replace"
                    )
                    log_lines = log_content.strip().split("\n")
                    if log_lines:
                        # Get last few error lines and redact paths
                        last_lines = redact_paths("\n".join(log_lines[-10:]))
                        if last_lines:
                            error_msg += (
                                f"\n\n📋 Last log lines:\n```\n{last_lines}\n```"
                            )
                except Exception:
                    pass

            # Try to get job_dir from result if available (for better error reporting)
            runner_job_id = None
            runner_job_dir = None
            try:
                if "result" in locals():
                    runner_job_id = result.job_id
                    runner_job_dir = str(result.job_dir)
            except Exception:
                pass

            mark_failed(
                conn,
                job_id,
                finished_at=utc_now_iso(),
                duration_s=duration_s,
                runner_job_id=runner_job_id,
                runner_job_dir=runner_job_dir,
                error=str(e),
            )

            # Truncate error message if too long for Telegram (max 4096 chars)
            if len(error_msg) > 4000:
                error_msg = error_msg[:3900] + "\n\n... (truncated)"

            await app.bot.send_message(
                chat_id=req.chat_id,
                text=f"❌ Job failed after {duration_s}s:\n\n{error_msg}",
            )
        finally:
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
    app.add_handler(CommandHandler("llm", wrap(cmd_llm)))
    app.add_handler(CommandHandler("status", wrap(cmd_status)))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
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
