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
    script_path = (project_root / "scripts" / "run_r2agent.sh").resolve()
    if not script_path.exists():
        raise FileNotFoundError(f"Missing script: {script_path}")

    args = [str(script_path), str(binary_path)]
    if agent_prompt_path is not None:
        args.append(str(agent_prompt_path))
    if tag:
        # Maintain positional args: if no agent prompt is passed, we still need an empty 2nd arg
        if agent_prompt_path is None:
            args.append("")
        args.append(tag)
    if llm_model:
        # Maintain positional args: if no tag is passed, we still need an empty 3rd arg.
        if not tag:
            if agent_prompt_path is None:
                args.append("")
            args.append("")
        args.append(llm_model)

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


