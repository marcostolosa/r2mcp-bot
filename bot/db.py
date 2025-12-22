from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class JobRow:
    job_id: str
    user_id: int
    agent: str
    tag: str
    status: str  # queued|running|finished|failed
    created_at: str
    started_at: Optional[str]
    finished_at: Optional[str]
    duration_s: Optional[int]
    runner_job_id: Optional[str]
    runner_job_dir: Optional[str]
    error: Optional[str]


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            agent TEXT NOT NULL,
            tag TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            duration_s INTEGER,
            runner_job_id TEXT,
            runner_job_dir TEXT,
            error TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_prefs (
            user_id INTEGER PRIMARY KEY,
            agent TEXT NOT NULL,
            llm_model TEXT NOT NULL DEFAULT 'opencode/grok-code'
        )
        """
    )
    # Lightweight migration: older DBs may not have llm_model yet.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(user_prefs)").fetchall()}
    if "llm_model" not in cols:
        # Adding a NOT NULL column requires a DEFAULT in SQLite.
        conn.execute(
            "ALTER TABLE user_prefs ADD COLUMN llm_model TEXT NOT NULL DEFAULT 'opencode/grok-code'"
        )
    # Migration: remove zip_path column if it exists (legacy field, no longer needed)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    if "zip_path" in cols:
        # SQLite doesn't support DROP COLUMN directly, so we recreate the table
        conn.execute("BEGIN TRANSACTION")
        conn.execute(
            """
            CREATE TABLE jobs_new (
                job_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                agent TEXT NOT NULL,
                tag TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                duration_s INTEGER,
                runner_job_id TEXT,
                runner_job_dir TEXT,
                error TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO jobs_new 
            SELECT job_id, user_id, agent, tag, status, created_at, started_at, 
                   finished_at, duration_s, runner_job_id, runner_job_dir, error
            FROM jobs
            """
        )
        conn.execute("DROP TABLE jobs")
        conn.execute("ALTER TABLE jobs_new RENAME TO jobs")
        conn.execute("COMMIT")
    conn.commit()


def set_user_agent(conn: sqlite3.Connection, user_id: int, agent: str) -> None:
    conn.execute(
        "INSERT INTO user_prefs(user_id, agent) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET agent=excluded.agent",
        (user_id, agent),
    )
    conn.commit()


def get_user_agent(conn: sqlite3.Connection, user_id: int) -> Optional[str]:
    cur = conn.execute("SELECT agent FROM user_prefs WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    return str(row[0]) if row else None


def set_user_llm_model(
    conn: sqlite3.Connection, user_id: int, llm_model: str, *, default_agent: str
) -> None:
    # Ensure the row exists (agent is NOT NULL).
    conn.execute(
        "INSERT INTO user_prefs(user_id, agent, llm_model) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET llm_model=excluded.llm_model",
        (user_id, default_agent, llm_model),
    )
    conn.commit()


def get_user_llm_model(conn: sqlite3.Connection, user_id: int) -> Optional[str]:
    cur = conn.execute(
        "SELECT llm_model FROM user_prefs WHERE user_id = ?", (user_id,)
    )
    row = cur.fetchone()
    return str(row[0]) if row else None


def create_job(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    user_id: int,
    agent: str,
    tag: str,
    created_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO jobs(job_id, user_id, agent, tag, status, created_at)
        VALUES (?, ?, ?, ?, 'queued', ?)
        """,
        (job_id, user_id, agent, tag, created_at),
    )
    conn.commit()


def mark_running(conn: sqlite3.Connection, job_id: str, started_at: str) -> None:
    conn.execute(
        "UPDATE jobs SET status='running', started_at=? WHERE job_id=?",
        (started_at, job_id),
    )
    conn.commit()


def mark_finished(
    conn: sqlite3.Connection,
    job_id: str,
    *,
    finished_at: str,
    duration_s: int,
    runner_job_id: str,
    runner_job_dir: str,
) -> None:
    conn.execute(
        """
        UPDATE jobs
        SET status='finished', finished_at=?, duration_s=?, runner_job_id=?, runner_job_dir=?
        WHERE job_id=?
        """,
        (finished_at, duration_s, runner_job_id, runner_job_dir, job_id),
    )
    conn.commit()


def mark_failed(
    conn: sqlite3.Connection,
    job_id: str,
    *,
    finished_at: str,
    duration_s: int,
    runner_job_id: Optional[str],
    runner_job_dir: Optional[str],
    error: str,
) -> None:
    conn.execute(
        """
        UPDATE jobs
        SET status='failed', finished_at=?, duration_s=?, runner_job_id=?, runner_job_dir=?, error=?
        WHERE job_id=?
        """,
        (finished_at, duration_s, runner_job_id, runner_job_dir, error, job_id),
    )
    conn.commit()


def list_jobs_for_user(
    conn: sqlite3.Connection, user_id: int, limit: int = 10
) -> list[JobRow]:
    cur = conn.execute(
        """
        SELECT job_id, user_id, agent, tag, status, created_at, started_at, finished_at,
               duration_s, runner_job_id, runner_job_dir, error
        FROM jobs
        WHERE user_id=?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    rows = []
    for r in cur.fetchall():
        rows.append(
            JobRow(
                job_id=r[0],
                user_id=int(r[1]),
                agent=r[2],
                tag=r[3],
                status=r[4],
                created_at=r[5],
                started_at=r[6],
                finished_at=r[7],
                duration_s=r[8],
                runner_job_id=r[9],
                runner_job_dir=r[10],
                error=r[11],
            )
        )
    return rows


