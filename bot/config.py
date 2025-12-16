from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BotConfig:
    telegram_bot_token: str
    allowed_users_file: Path
    sqlite_path: Path
    concurrency: int
    project_root: Path
    default_agent: Path
    jobs_root: Path
    uploads_dir: Path


def load_config(config_path: Path) -> BotConfig:
    data = json.loads(config_path.read_text(encoding="utf-8"))

    base_dir = config_path.parent
    project_root = (base_dir / data.get("project_root_relative", "..")).resolve()

    def resolve_path(value: str) -> Path:
        p = Path(value)
        return (base_dir / p).resolve() if not p.is_absolute() else p

    token = str(data["telegram_bot_token"]).strip()
    if not token or token == "REPLACE_ME":
        raise ValueError(
            "telegram_bot_token is missing. Edit bot/config.json and set a valid token."
        )

    concurrency = int(data.get("concurrency", 4))
    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")

    return BotConfig(
        telegram_bot_token=token,
        allowed_users_file=resolve_path(data.get("allowed_users_file", "allowlist.json")),
        sqlite_path=resolve_path(data.get("sqlite_path", "bot.sqlite3")),
        concurrency=concurrency,
        project_root=project_root,
        default_agent=resolve_path(data.get("default_agent", "../agents/analyze.task.md")),
        jobs_root=resolve_path(data.get("jobs_root", "../analisis")),
        uploads_dir=resolve_path(data.get("uploads_dir", "../analisis/_uploads")),
    )


