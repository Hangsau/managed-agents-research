# Managed Agents Framework — Code Review Report

**Date:** 2026-05-12
**Scope:** `/root/managed-agents/` core + research modules
**Reviewer:** Hermes Agent (subagent)

---

## 1. Architecture — Session/Harness/Sandbox Separation

### Verdict: **Partially correct, with critical isolation flaws.**

The framework implements a three-layer architecture:
- **Session** → SQLite append-only event log (`sessions.db`)
- **Harness** → LLM planner loop (`harness.py`)
- **Sandbox** → Docker container execution (`docker_exec.py`)

### Issues

| # | Issue | Severity | Details |
|---|-------|----------|---------|
| 1.1 | **Sandbox mounts host project dir read-write** | **Critical** | `docker_exec.py` mounts `/root/managed-agents` into the container twice (`/workspace/managed-agents` and `/root/managed-agents`). Any `bash` action can read the API key, modify source code, or corrupt the SQLite DB. The sandbox is cosmetic, not functional. |
| 1.2 | **No session metadata table** | Medium | `schema.sql` only has an `events` table. There is no `sessions` table to track `created_at`, `status`, `goal`, `turn_count`, or `completed_at`. Querying session state requires expensive aggregation over events. |
| 1.3 | **Host filesystem ops bypass sandbox entirely** | Medium | `read_file` and `write_file` in `harness.py` operate directly on the host filesystem. This is by design per the system prompt, but it means the "sandbox" only applies to `bash`, creating an inconsistent security model. |
| 1.4 | **Harness auto-corrects docker commands** | Low | The regex-based stripping of `docker run ...` in `harness.py` (lines 91–102) is a tight coupling smell. The harness should not need to know that the sandbox is Docker-based. |
| 1.5 | **No clear agent-session lifecycle** | Low | `run_agent.py` drives the loop, `dispatch.py` spawns it, and `ma` is the CLI, but there is no state machine (e.g., `CREATED → RUNNING → WAITING → COMPLETED`). Status is inferred from the last event type via SQL subqueries. |

---

## 2. Security

### Verdict: **Multiple critical vulnerabilities. Not production-safe.**

### Issues

| # | Issue | Severity | Details |
|---|-------|----------|---------|
| 2.1 | **Hardcoded API key in source** | **Critical** | `harness.py` line 13 contains a live `sk-...` API key committed to source. Any user/process with read access to the file can extract it. Should use environment variables or a secrets manager. |
| 2.2 | **SQL injection in CLI wrapper** | **Critical** | `ma` (lines 64, 102) interpolates `$sid` and `$msg` directly into SQLite CLI commands without escaping. Example: `ma resume test "'; DROP TABLE events; --"` could corrupt the database. |
| 2.3 | **`check_guard` is called but never defined** | **Critical** | `harness.py` calls `check_guard("guard_path.py", [path])` at lines 121 and 146, but the function does not exist in the file. This will raise `NameError` and crash the harness on any `read_file` or `write_file` action. |
| 2.4 | **Docker container has unrestricted network** | **High** | `docker_exec.py` uses `--network bridge` without restriction. Sandboxed code can exfiltrate data, attack internal services, or download malware. Consider `--network none` or a dedicated isolated bridge. |
| 2.5 | **Guard regex case mismatch** | **High** | `guard_bash.py` lowercases the command (`cmd_lower = cmd.lower()`) but several `DENY_PATTERNS` contain uppercase literals (e.g., `r'DROP\s+DATABASE'`). These patterns will **never match**. `DROP DATABASE`, `DROP TABLE`, and `sudo` (pattern `r'sudo\s+'` is lowercase, so that's fine) — but the uppercase SQL patterns are dead code. |
| 2.6 | **Path guard vulnerable to symlink traversal** | **High** | `guard_path.py` uses `os.path.abspath` (does not resolve symlinks). A path like `/tmp/evil -> /etc/passwd` would pass the guard because `abspath` returns `/tmp/evil`, which starts with `/tmp/`. Should use `os.path.realpath`. |
| 2.7 | **Path guard overly permissive outside /root /home** | **Medium** | `guard_write` returns `{"blocked": False}` for any path not under `/root/` or `/home/` and not in `FORBIDDEN_ROOTS`. Writing to `/var/tmp`, `/mnt`, or `/data` is implicitly allowed. Default-deny is safer. |
| 2.8 | **Bash guard missing common escalation vectors** | **Medium** | `guard_bash.py` blocks `sudo` and `su` but misses `doas`, `pkexec`, `nc`, `ncat`, `python -c '...'`, and indirect execution via `find -exec`. Also, `curl | bash` patterns can be bypassed with `curl|bash` (no spaces) or `curl | /bin/bash`. |
| 2.9 | **Guard crash defaults to allow** | **Medium** | In `harness.py` line 105: if the guard process crashes (`returncode` neither 0 nor 2), the command is allowed (`{"blocked": False}`). Fail-closed is safer. |
| 2.10 | **No secrets management for GitHub API** | **Low** | `researcher.py` calls GitHub API unauthenticated (60 req/hour limit). While not a security vulnerability per se, it forces the tool to run without credentials and may leak IP/rate-limit info. |

---

## 3. Reliability

### Verdict: **Basic error handling present, but brittle under failure.**

### Issues

| # | Issue | Severity | Details |
|---|-------|----------|---------|
| 3.1 | **`dispatch.py` `--max-turns` parameter silently ignored** | **High** | `dispatch.py` passes `f"--max-turns={max_turns}"` (single token), but `run_agent.py` expects the next array element to be the value (`sys.argv[index+1]`). Since the token is combined with `=`, `"--max-turns" in sys.argv` is `False`, so it always defaults to 20. Custom max_turns values are ignored. |
| 3.2 | **Path mismatch between deep-dive and skill activation** | **High** | `deep_dive.py` writes skill drafts to `/root/managed-agents/research/skills-drafts/`, but `activate_skill.py` reads from `/root/managed-agents/internal/skills-drafts/`. The directories do not match; `activate_skill.py list` will always return empty unless files are manually copied. |
| 3.3 | **No retry or backoff on LLM/API failures** | **Medium** | `call_llm` catches exceptions and returns an error JSON string, but `run_agent.py` treats any non-`done`/`waiting` status as "continue" and sleeps 1 second. Transient network errors will burn through `MAX_TURNS` without recovery. |
| 3.4 | **Stuck-loop detection is shallow** | **Medium** | Duplicate detection only looks at the last 4 tool results and exact JSON signatures. It does not detect semantic loops (e.g., `ls`, `cat`, `ls`, `cat` cycling) or oscillating states. It also only checks `read_file`/`write_file` for path dups, not `bash` command dups. |
| 3.5 | **`run_agent.py` fragile output parsing** | **Medium** | It scans for `--- Turn Result ---` delimiter to extract JSON. If `harness.py` prints extra newlines or logging changes format, parsing fails and the turn is treated as an empty dict, causing the loop to continue blindly. |
| 3.6 | **`ma resume` inserts raw message without JSON escaping** | **Medium** | The shell interpolation of `$msg` into the SQLite payload means messages containing quotes or backslashes will create malformed JSON or SQL. |
| 3.7 | **No disk-full or DB-locked handling** | **Low** | `db_exec` in `harness.py` opens a new connection per query. If the DB is locked or the disk is full, the script will crash with an unhandled exception. |
| 3.8 | **Deep-dive README fetch only tries `main`/`master`** | **Low** | Many repos now use `develop`, `trunk`, or other default branches. `fetch_readme` will fail for these. |
| 3.9 | **`run_agent.py` continues on parse error** | **Low** | If `json.loads` fails, `turn_result` becomes `{}`, which is neither `done` nor `waiting`, so the loop continues until `MAX_TURNS`. A persistent format error wastes all turns. |

---

## 4. Scalability

### Verdict: **Will degrade as sessions age.**

### Issues

| # | Issue | Severity | Details |
|---|-------|----------|---------|
| 4.1 | **Event log fetches entire history then truncates in Python** | **High** | `get_events(session_id)` defaults to `since_seq=0`, so it `SELECT`s every event for the session. `run_turn` then slices `history[-15:]`. For long-running sessions (100s–1000s of turns), this wastes memory, I/O, and time. Should push the `LIMIT` into SQL. |
| 4.2 | **Unbounded event log growth** | **High** | `schema.sql` has no retention policy, archiving, or TTL. The `events` table grows forever. Old sessions will eventually cause the DB file to become unwieldy and slow down queries. |
| 4.3 | **SQLite connection per query** | **Medium** | Every `log_event` and `get_events` call opens and closes a SQLite connection. Under load (swarm, rapid turns), this creates unnecessary overhead and can hit SQLITE_BUSY. Connection pooling or a persistent connection per process is better. |
| 4.4 | **No token budgeting for LLM context** | **Medium** | The harness limits to the last 15 events, but does not count tokens. A single `read_file` result summarized into 500 characters plus 14 other events could exceed the model's context window (especially for smaller models). |
| 4.5 | **Log files grow unbounded** | **Low** | `dispatch.py` redirects stdout/stderr to `logs/{sid}.log` with no rotation. Long agent runs could fill disk. |
| 4.6 | **`read_file` reads file twice** | **Low** | Line-counting via `sum(1 for _ in open(...))` reads the entire file, then it is read again for content. For large files this is inefficient. |

---

## 5. Code Quality

### Verdict: **Functional but unmaintainable at scale.**

### Issues

| # | Issue | Severity | Details |
|---|-------|----------|---------|
| 5.1 | **Magic numbers scattered throughout** | **Medium** | `8000`, `4000`, `2000`, `15`, `60`, `1000`, `500`, `20`, `7` appear repeatedly with no named constants. Examples: file read truncation (`8000`), stdout truncation (`4000`), event history (`15`), timeouts (`60`), max turns (`20`). |
| 5.2 | **Hardcoded paths duplicated in every file** | **Medium** | `/root/managed-agents` is hardcoded in `harness.py`, `docker_exec.py`, `ma`, `swarm_runner.py`, `researcher.py`, `deep_dive.py`, etc. A single `config.py` or environment variable should centralize this. |
| 5.3 | **Imports inside functions** | **Low** | `harness.py` imports `subprocess`, `urllib.request`, `re`, and `os` inside functions. This hurts readability and has negligible performance benefit in a long-running process. |
| 5.4 | **Deprecated `datetime.utcnow()`** | **Low** | Used in `harness.py`, `swarm_runner.py`, `researcher.py`. Deprecated in Python 3.12; should use `datetime.now(datetime.timezone.utc)`. |
| 5.5 | **Missing encoding in `write_file`** | **Low** | `harness.py` line 151: `open(path, "w")` uses the platform default encoding. Should specify `encoding="utf-8"` for consistency with `read_file`. |
| 5.6 | **Dead/unused indexes** | **Low** | `schema.sql` creates `idx_type` on `events(type)`. Queries always filter by `session_id`; this index is unlikely to be used and adds write overhead. |
| 5.7 | **No type hints** | **Low** | Most functions lack type annotations, making refactors risky. |
| 5.8 | **Large `execute_action` function** | **Low** | `harness.py` `execute_action` handles 5 different actions in one 100-line function. Should be refactored into an action registry/dispatcher. |

---

## Summary Matrix

| Category | Critical | High | Medium | Low |
|----------|----------|------|--------|-----|
| Architecture | 1 | 0 | 1 | 2 |
| Security | 3 | 3 | 2 | 1 |
| Reliability | 0 | 2 | 3 | 3 |
| Scalability | 0 | 2 | 1 | 2 |
| Code Quality | 0 | 0 | 2 | 5 |
| **Total** | **4** | **7** | **9** | **13** |

---

## Top 5 Priority Fixes

1. **Remove the hardcoded API key** and load from environment variables (`os.environ.get(...)`).
2. **Fix or remove the broken `check_guard` call** in `harness.py` (currently causes `NameError`).
3. **Fix the SQL injection** in the `ma` bash script by using SQLite parameterized queries via a Python wrapper instead of shell interpolation.
4. **Fix sandbox isolation** in `docker_exec.py`: do not mount `/root/managed-agents` into the container, or mount it read-only if necessary.
5. **Align the skills-drafts path** between `deep_dive.py` and `activate_skill.py` (or create a shared config).

---

*Report generated by Hermes Agent subagent.*
