# r2agent (radare2 + r2mcp + OpenCode)

With this VibeCode trending the README.md generated are too verboses. If you need more details, check the [README_extended.md](README_extended.md) file.

TL;DR:

There are five main components:

1. `scripts`:
   - `run_r2agent.sh` run the analysis in your shell.
   - `watchdog.sh` watches for long-running containers and stops them after a timeout. Useful if you deploy the Tg Bot

2. `agents`: Are the folder promtps. *Prompts are not universal for all the LLMs. You should try different prompts for different LLMs.*
   - `analyze.task.md` the agent prompt that is used to analyze the binaries.
   - `crackme.task.md` the agent prompt that is used to analyze the crackme binaries.

3. `docker`: The Docker image that contains the required tools.

4. `analysis`: The analysis results.

5. `bot`:
    - It uses an allow list of user `bot/allowlist.json` to restrict the usage of the bot. (`cp bot/allowlist.json.sample bot/allowlist.json` and edit it)
    - `bot/config.json` is the configuration file for the bot. (`cp bot/config.json.sample bot/config.json` and edit it)
    - It runs the existing local Docker analysis via `scripts/run_r2agent.sh`, and sends back the `Report.md` file when finished.
    - Check the [bot/README.md](bot/README.md) file for more details.

## How it works

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
