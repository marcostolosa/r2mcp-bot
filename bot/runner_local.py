from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class RunResult:
    job_id: str
    job_dir: Path
    exit_code: int


_JOB_ID_RE = re.compile(r"^\[\+\] Job id:\s+(?P<job_id>\S+)\s*$")
_JOB_DIR_RE = re.compile(r"^\[\+\] Job dir:\s+(?P<job_dir>.+)\s*$")


async def run_r2agent(
    *,
    project_root: Path,
    binary_path: Path,
    agent_prompt_path: Optional[Path],
    tag: str,
    log_path: Path,
    llm_model: Optional[str] = None,
) -> RunResult:
    script_path = (project_root / "run_r2agent.sh").resolve()
    if not script_path.exists():
        raise FileNotFoundError(f"Missing script: {script_path}")

    # Build arguments using flag-based API (required by run_r2agent.sh)
    # Bot always uses docker mode
    args = [
        str(script_path),
        "--mode", "docker", # I would not change this to local.
        "--file", str(binary_path),
    ]
    
    # Agent prompt is required if no prompt text is provided
    if agent_prompt_path is not None:
        args.extend(["--agent", str(agent_prompt_path)])
    
    # Optional flags
    if tag:
        args.extend(["--tag", tag])
    if llm_model:
        args.extend(["--model", llm_model])

    log_path.parent.mkdir(parents=True, exist_ok=True)

    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(project_root),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    job_id: Optional[str] = None
    job_dir: Optional[Path] = None

    assert proc.stdout is not None
    with log_path.open("wb") as lf:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            lf.write(line)
            lf.flush()

            try:
                s = line.decode("utf-8", errors="replace").rstrip("\n")
            except Exception:
                s = ""

            if job_id is None:
                m = _JOB_ID_RE.match(s)
                if m:
                    job_id = m.group("job_id")
            if job_dir is None:
                m = _JOB_DIR_RE.match(s)
                if m:
                    job_dir = Path(m.group("job_dir")).expanduser().resolve()

    rc = await proc.wait()

    if job_id is None or job_dir is None:
        raise RuntimeError(
            f"Could not parse job id/dir from runner output. See log: {log_path}"
        )

    return RunResult(job_id=job_id, job_dir=job_dir, exit_code=rc)


