# Managed Agents Swarm

Self-hosted multi-turn agent framework with Docker sandbox.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Dispatcher │────▶│   Harness    │────▶│   Docker    │
│  (dispatch) │     │  (harness)   │     │  (sandbox)  │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ SQLite Event │
                    │    Log       │
                    └──────────────┘
```

- **Dispatcher** (`dispatch.py`): Launch background agent runs, return immediately
- **Harness** (`harness.py`): Single-brain planner. Plan → execute → persist → sleep
- **Docker Sandbox** (`docker_exec.py`): Isolated bash execution
- **Event Log** (`sessions.db`): Append-only SQLite, wake/resume by `session_id`

## Quick Start

```bash
# Start a new agent task (background)
./ma run "Research OpenAI's latest blog post and summarize"
# → Returns session_id immediately

# Check all running sessions
./ma status

# Resume a waiting session (if it asked a question)
./ma resume <session_id> "answer: yes, proceed"

# View logs
./ma logs <session_id>

# List all sessions
./ma ls
```

## How It Works

1. You call `ma run "goal"`
2. Dispatcher creates `session_id`, forks background process
3. Harness loads history from SQLite (empty for new session)
4. Planner (LLM) decides ONE next action: `bash`, `read_file`, `write_file`, `complete`, `ask_user`
5. Action executes inside Docker sandbox
6. Result persisted to event log
7. Repeat until `complete` or `max_turns` reached

## Event Log Schema

```sql
CREATE TABLE events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    ts DATETIME DEFAULT CURRENT_TIMESTAMP,
    type TEXT NOT NULL,  -- 'user_goal', 'planner_decision', 'tool_call', 'tool_result', 'completion', 'error'
    payload TEXT NOT NULL  -- JSON
);
```

## When to Use Swarm vs delegate_task

| Use Swarm | Use delegate_task |
|---|---|
| Long-running research (needs state across turns) | One-off parallel tasks (review 10 files) |
| Needs to ask user mid-flight | Deterministic, no follow-up needed |
| Must survive disconnection | Quick < 2 min tasks |
| Multi-step with error recovery | Independent subtasks |

## Files

| File | Purpose |
|---|---|
| `core/harness.py` | Main planner loop |
| `core/dispatch.py` | Background launcher |
| `core/run_agent.py` | Auto-run turns until done |
| `core/docker_exec.py` | Docker sandbox wrapper |
| `core/guards/` | Bash and path guards |
| `sessions.db` | SQLite event log |
| `logs/` | Per-session stdout logs |
| `pending_results/` | Completed session results waiting for relay |

## Current Status

- Phase 1: Single-brain, OpenRouter free tier (`deepseek-v4-flash`)
- Phase 2 (planned): Multi-agent orchestrator, work distribution
- Phase 3 (planned): Persistent memory, skill library
- Phase 4 (blocked): KVM sandbox (this VM has no KVM)

## Daily Research Pipeline

The `research/` directory contains the daily AI research pipeline. It should be migrated to use this swarm framework instead of standalone cronjob scripts.
