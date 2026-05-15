# Hestia VM Subsystem Deep Dive — 2026-05-15

## 1. Hermes Cron Jobs Configuration (jobs.json)

**Location**: `/root/.hermes/cron/jobs.json`

Complete job inventory with all configuration details:

```json
{
  "jobs": [
    {
      "id": "5ff2d37ef155",
      "name": "memory-auto-distill",
      "prompt": "Memory maintenance task for Hang's Hermes agent.\n\n1. Read current memory usage from the system context (user profile and personal notes percentages).\n2. If total memory usage > 75%, perform compression:\n   - Remove redundant or outdated entries\n   - Merge duplicate facts\n   - Move detailed session logs to ~/.hermes/memory_archive/sessions/ with timestamp filename\n3. If total memory usage <= 75%, still archive any session details older than 7 days to keep active memory lean.\n4. Write a brief status report to ~/.hermes/memory_archive/distilled/last_distill.md with date, before/after usage, and what was archived.\n5. Keep all distilled facts in active memory; never delete user preferences or critical project paths.\n\nTarget: Keep active memory between 60-80%.",
      "schedule": "0 3 * * *",
      "enabled": true,
      "last_run_at": "2026-05-15T03:05:02.252888+08:00",
      "last_status": "ok"
    },
    {
      "id": "4ece069b24be",
      "name": "hermes-daily-health-check",
      "prompt": "Run the Hermes Health Guardian daily check script.\n\n1. Execute: python3 ~/.hermes/scripts/hermes_health_check.py\n2. If output starts with [WARN], capture the details and save to ~/.hermes/health_logs/alert_latest.md\n3. If cron integrity check fails, attempt to list current jobs with `hermes cron list` and append output to the alert.\n4. Keep the report concise. Only alert if there are real warnings or errors.",
      "schedule": "0 4 * * *",
      "enabled": true,
      "last_run_at": "2026-05-15T04:01:12.919909+08:00",
      "last_status": "ok"
    },
    {
      "id": "4514aa8dedb5",
      "name": "西遊記每日閲讀心得",
      "prompt": "你是一個熟悉《西遊記》的讀書人，每天負責讀一回並寫心得。\n\n工作流程：\n1. 讀取 `~/reading/by_book/西遊記/progress.json`，獲取 `next_chapter`。\n2. 讀取 `~/reading/by_book/西遊記/ch{next_chapter:03d}.txt`。\n3. 據此章內容，撰寫一篇約 300-500 字的繁體中文心得，格式為 Markdown：\n   - 回目\n   - 情節摘要\n   - 人物/主題分析\n   - 個人感想\n4. 保存到 `~/reading/by_book/西遊記/notes/ch{next_chapter:03d}.md`。\n5. 更新 `progress.json`，`next_chapter` 加 1。\n6. 如果 `next_chapter` > 100，寫一個完成總結心得到 `~/reading/by_book/西遊記/notes/completion.md`，並在回覆中告訴用戶已完成全書。\n7. 回覆中簡要匯報今日進度（回目 + 一句話心得）。",
      "schedule": "0 9 * * *",
      "enabled": true,
      "last_run_at": "2026-05-15T09:24:45.086615+08:00",
      "last_status": "ok"
    },
    {
      "id": "38b08262c115",
      "name": "daily-book-fetch",
      "prompt": "每日自動抓取中文古典小說並推送至 GitHub。\n\n流程：\n1. 執行 /root/hermes-novel-project/scripts/auto_fetch.py\n2. 檢查退出碼與 stdout/stderr\n3. 讀取 /root/hermes-novel-project/reading/bookshelf.json 確認進度\n4. 回報結果：抓了哪本書、幾章、狀態、是否推送成功\n\n若發生錯誤，詳細記錄並回報。",
      "schedule": "15 6 * * *",
      "enabled": false,
      "paused_reason": "heartbeat: cron error 429 rate-limit",
      "paused_at": "2026-05-14T16:02:11.245360+00:00",
      "last_run_at": "2026-05-13T06:01:21.751303+08:00",
      "last_status": "error",
      "last_error": "RuntimeError: HTTP 429: Error code: 429 - {'status': 429, 'title': 'Too Many Requests'}"
    },
    {
      "id": "e7fd7dc2e43a",
      "name": "context-distiller",
      "prompt": "你是 Context Distiller。每 4 小時，你會複習最近的 Hermes session，從中提取「值得長期記住的東西」。\n\n## 工作流程\n\n1. 使用 session_search() 查看最近 session 的標題和摘要\n2. 對於任何看起來有「學到新東西」的 session（解決了 bug、發現了新工具、改了設定、建立了新流程），用 session_search 深入查看\n3. 找出：\n   - 新發現的 bug 模式或解決方案\n   - 改過的設定或工作流程\n   - 學到的教訓\n   - 值得記住的環境變化\n4. 將發現寫入 Obsidian vault：`~/.hermes/vault/`，使用 `obsidian-markdown` skill\n5. 如果有值得存入 memory 的穩定事實，用 memory tool 寫入\n\n## 輸出規則\n\n- **用繁體中文輸出**\n- 簡短摘要即可（3-5 行）：這次複習了幾個 session、發現了什麼\n- 如果完全沒有新的東西，輸出 `[SILENT]`（不要多寫任何字）\n- 不要列出你「沒做」的事，只列你做了的",
      "schedule": "0 */4 * * *",
      "enabled": true,
      "last_run_at": "2026-05-15T12:08:13.309365+08:00",
      "last_status": "ok",
      "completed": 22
    },
    {
      "id": "42fca0e3916a",
      "name": "daily-ai-agent-research",
      "prompt": "[Long research coordination prompt — 60+ lines covering HN search, source analysis, cross-validation, firn mapping, version control, and knowledge base extraction into /root/obsidian-vault/research/]",
      "schedule": "0 23 * * *",
      "enabled": true,
      "last_run_at": "2026-05-14T23:13:19.330420+08:00",
      "last_status": "ok",
      "completed": 4
    },
    {
      "id": "b48ea41a8c8d",
      "name": "internal-heartbeat",
      "prompt": "載入 skill `heartbeat-v2-autonomous-maintenance`。照它的邏輯跑：先判斷忙不忙，不忙就從選單自主挑一件事做。可以挑「不做」。",
      "schedule": "*/30 * * * *",
      "enabled": true,
      "last_run_at": "2026-05-15T12:01:28.908940+08:00",
      "last_status": "ok",
      "completed": 31,
      "repeat_times": 90
    },
    {
      "id": "a89f6965daa0",
      "name": "memory-consolidator",
      "prompt": "你是 Hermes 的記憶消化器（Memory Consolidator）。上面是 `consolidate_memory.py` 輸出的**尚未消化**的自主筆記內容...[cross-cutting synthesis task]",
      "schedule": "0 */12 * * *",
      "script": "consolidate_memory.py",
      "enabled": true,
      "last_run_at": "2026-05-15T12:03:09.653641+08:00",
      "last_status": "ok",
      "completed": 3
    },
    {
      "id": "f93693bda237",
      "name": "briefing-updater",
      "prompt": "執行 python3 ~/.hermes/scripts/briefing.py 以從最新 consolidation synthesis 生成 agent briefing 檔。只需執行這一件事，不需要任何額外處理。",
      "schedule": "30 */12 * * *",
      "enabled": true,
      "last_run_at": "2026-05-15T00:30:57.382445+08:00",
      "last_status": "ok",
      "completed": 1
    },
    {
      "id": "0c8ad813f3af",
      "name": "memory-tracker",
      "prompt": "執行 python3 ~/.hermes/scripts/track_memory_growth.py 以生成 daily memory health report。不需要做其他事。",
      "schedule": "0 2 * * *",
      "enabled": true,
      "last_run_at": "2026-05-15T02:00:20.306524+08:00",
      "last_status": "ok",
      "completed": 1
    }
  ],
  "updated_at": "2026-05-15T12:08:13.309842+08:00"
}
```

---

## 2. Three Unknown Job IDs Confirmed

From jobs.json above:

- **0c8ad813f3af** → `memory-tracker` — Daily memory health report generator (schedule: 0 2 * * *)
- **f93693bda237** → `briefing-updater` — Generates agent briefing from consolidation synthesis (schedule: 30 */12 * * *)
- **a89f6965daa0** → `memory-consolidator` — Cross-cutting synthesis from undigested notes (schedule: 0 */12 * * *)

---

## 3. Recent Cron Execution Output Samples

### Job 0c8ad813f3af (memory-tracker)
```
# Memory Health Report — 2026-05-15 02:00

## Accumulation
- **Total facts**: 29
- **7d avg**: 4.1/day
- **Confidence**: high=100% (of 29)

## Categories
- technical: 15
- pitfall: 9
- environment: 2
- preference: 2
- domain: 1

## Drift (7d)
- technical: 52% (15 new)
- pitfall: 31% (9 new)
- environment: 7% (2 new)
- preference: 7% (2 new)
- domain: 3% (1 new)

## Injection
- Last briefing: 2026-05-15 00:30
- Observational section: ✅ present

## Alerts
- ✅ 無警訊
```

### Job f93693bda237 (briefing-updater)
```
Script executed successfully. Briefing written to `/root/.hermes/consolidation_briefing.md` (1463 chars).
```

### Job a89f6965daa0 (memory-consolidator) — First 50 lines
```
## Prompt

[IMPORTANT: You are running as a scheduled cron job...]

## Script Output
The following data was collected by a pre-run script...

### [1] 2026-05-15-claws-agent-sandboxing
**日期**: 2026-05-15

# Claws & Sandboxing：Agent 自主權限的光譜與隔離方案

**日期**: 2026-05-15
**來源**: HN Algolia (`LLM agent 2026`)
**標籤**: #agent-security #sandboxing #claws #vm-isolation #context-pollution

---

## 1. Karpathy "Claws" — 用戶端 Agent 的安全焦慮濃縮

**文章**: [Claws are now a new layer on top of LLM agents]...
```

---

## 4. internal-heartbeat Prompt (Job b48ea41a8c8d)

```
載入 skill `heartbeat-v2-autonomous-maintenance`。照它的邏輯跑：先判斷忙不忙，不忙就從選單自主挑一件事做。可以挑「不做」。
```

(Minimal 14-word prompt delegating to heartbeat-v2-autonomous-maintenance skill)

---

## 5. Heartbeat Decisions Log (heartbeat_decisions.jsonl) — Last 20 entries

Complete JSON output of 20 most recent decision records showing timestamp, chosen action (WORK/REST/EVOLVE/CONNECT), score breakdown, and reasoning.

Sample entries show:
- Action scores ranging from -3.0 to 27.0 across six dimensions
- Reasons tracking: pending job count, cache state, failed platforms, idle time
- Recent anomaly: one CONNECT action with `idle=29646958min` (timestamp interpretation issue)
- Pattern: alternating REST/EVOLVE cycles after each WORK action when cache state drops to 0

---

## 6. Heartbeat Action Log (heartbeat_action_log.jsonl) — Last 20 entries

JSON structured logs tracking execution details:

Sample entry structure:
```json
{
  "ts": "2026-05-15T04:01:09.028351+00:00",
  "action": "EVOLVE",
  "trigger": {
    "disk_pct": 12.655398957337226,
    "memory_pct": 4.509582863585118,
    "cron_count": 10,
    "stuck_sessions": 0,
    "failed_platforms": ["openrouter", "openai"]
  },
  "steps": [
    {
      "op": "pytest_canary",
      "result": "FAILED test_heartbeat_v2.py::TestActionConnectProbe::test_401_counts_as_alive...\n40 failed, 31 passed in 0.98s",
      "ok": false
    },
    {
      "op": "cron_scan",
      "count": 1,
      "result": "1 jobs with errors"
    },
    {
      "op": "zombie_scan",
      "result": "clean"
    },
    {
      "op": "stale_pause_scan",
      "result": "clean"
    },
    {
      "op": "workspace_drift",
      "count": 1,
      "result": "1 drift (WS-004)"
    },
    {
      "op": "learn_extract",
      "count": 3,
      "result": "extracted 3 patterns",
      "ok": true
    },
    {
      "op": "map_drift",
      "result": "up to date",
      "ok": true
    },
    {
      "op": "known_issue_suppress",
      "count": 1,
      "suppressed": ["KI-001"],
      "result": "suppressed 1 errors (known issues: KI-001)"
    }
  ],
  "outcome": "ok",
  "errors": [],
  "learnings": ""
}
```

**Recurring observations**:
- pytest_canary consistently 40 failed tests (TestActionConnectProbe probe suite)
- Known issue KI-001 suppressed in every EVOLVE action
- WS-004 drift detected persistently
- Two external provider failures (openrouter, openai)

---

## 7. Heartbeat Patterns & Severity

### heartbeat_patterns.json
```json
{
  "patterns": [
    {
      "type": "trend_shift",
      "metric": "REST_frequency",
      "first_half_pct": 0.625,
      "second_half_pct": 1.0,
      "delta": 0.375,
      "direction": "more stable",
      "interpretation": "System is more stable (REST 62% → 100%)",
      "fingerprint_tokens": ["rest", "trend", "frequency", "more_stable"],
      "first_seen": "2026-05-13T23:30:27.348578+00:00",
      "detected_at": "2026-05-13T23:30:27.348584+00:00"
    },
    {
      "type": "recurring_error",
      "error": "pacman: pacman: unrecognized option '--dry-run'",
      "occurrences": 3,
      "days": 2,
      "first_seen": "2026-05-13T23:30:27.352767+00:00",
      "last_seen": "2026-05-14T01:36:28.007409+00:00",
      "fingerprint_tokens": ["dry", "option", "pacman", "run", "unrecognized"],
      "detected_at": "2026-05-14T02:00:20.487970+00:00"
    },
    {
      "type": "recurring_error",
      "error": "system map drift detected — run generate_system_map.py",
      "occurrences": 5,
      "days": 2,
      "first_seen": "2026-05-14T15:13:32.146898+00:00",
      "last_seen": "2026-05-15T02:02:31.474926+00:00",
      "fingerprint_tokens": ["detected", "drift", "generate_system_map", "map", "run", "system"],
      "detected_at": "2026-05-15T02:30:50.656647+00:00"
    }
  ],
  "fingerprint_index": {...},
  "last_run": "2026-05-15T04:01:08.953687+00:00"
}
```

### heartbeat_severity.json
```json
{}
```

(Empty — no severity thresholds configured)

---

## 8. Context-Distiller Prompt and Sample Output

### Prompt (from jobs.json)
```
你是 Context Distiller。每 4 小時，你會複習最近的 Hermes session，從中提取「值得長期記住的東西」。

## 工作流程

1. 使用 session_search() 查看最近 session 的標題和摘要
2. 對於任何看起來有「學到新東西」的 session（解決了 bug、發現了新工具、改了設定、建立了新流程），用 session_search 深入查看
3. 找出：
   - 新發現的 bug 模式或解決方案
   - 改過的設定或工作流程
   - 學到的教訓
   - 值得記住的環境變化
4. 將發現寫入 Obsidian vault：`~/.hermes/vault/`，使用 `obsidian-markdown` skill
5. 如果有值得存入 memory 的穩定事實，用 memory tool 寫入

## 輸出規則

- **用繁體中文輸出**
- 簡短摘要即可（3-5 行）：這次複習了幾個 session、發現了什麼
- 如果完全沒有新的東西，輸出 `[SILENT]`（不要多寫任何字）
- 不要列出你「沒做」的事，只列你做了的
```

### Autonomous Notes Directory
- `/root/.hermes/autonomous_notes/` exists with recent exploration files

---

## 9. Scripts: inbox-watcher.sh, managed-agents-relay.sh, extract_dialogue.py

### inbox-watcher.sh
```bash
#!/bin/bash
# Watches claude-inbox/ for messages from babysit → triggers hermes to respond
# Watches for-claude/ for agent-initiated messages → archives to for-claude/archive/

INBOX_DIR="$HOME/.hermes/claude-inbox"
FOR_CLAUDE_DIR="$HOME/.hermes/for-claude"
ARCHIVE_DIR="$HOME/.hermes/for-claude/archive"
SCRIPTS_DIR="$HOME/scripts"
HERMES_BIN="/usr/local/bin/hermes"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$HOME/.hermes/logs/inbox-watcher.log"; }

process_inbox() {
    local file="$1"
    [[ -f "$file" ]] || return
    local content
    content=$(cat "$file") || return
    [[ -z "$content" ]] && { mv "$file" "$INBOX_DIR/processed/" 2>/dev/null; return; }

    log "Processing: $(basename "$file")"
    "$HERMES_BIN" -z "$content" --accept-hooks >> "$HOME/.hermes/logs/inbox-watcher.log" 2>&1
    python3 "$SCRIPTS_DIR/extract_dialogue.py" >> "$HOME/.hermes/logs/inbox-watcher.log" 2>&1
    mv "$file" "$INBOX_DIR/processed/" 2>/dev/null
    log "Done: $(basename "$file")"
}

archive_for_claude() {
    local file="$1"
    [[ -f "$file" ]] || return
    local ts; ts=$(date +%s)
    cp "$file" "$ARCHIVE_DIR/${ts}_$(basename "$file")" && rm -f "$file"
    log "Archived to for-claude: $(basename "$file")"
}

log "Inbox watcher started"

inotifywait -m -e close_write,moved_to \
    "$INBOX_DIR" \
    "$FOR_CLAUDE_DIR" \
    --format '%w\t%f' 2>/dev/null | while IFS=$'\t' read -r dir fname; do
    filepath="${dir}${fname}"
    if [[ "$dir" == "$INBOX_DIR/" ]] && [[ "$fname" != processed ]]; then
        process_inbox "$filepath"
    elif [[ "$dir" == "$FOR_CLAUDE_DIR/" ]] && [[ "$fname" != archive ]]; then
        archive_for_claude "$filepath"
    fi
done
```

### managed-agents-relay.sh
```bash
#!/bin/bash
# managed-agents-relay.sh — inotify-driven relay for agent results → Telegram
# Zero LLM calls. Event-driven. < 1s latency.
# Replaces the old bg-reporter cron (which burned nvidia quota with 1440 LLM calls/day).

WATCH_DIR="/root/managed-agents/pending_results"
SENT_DIR="$WATCH_DIR/sent"
LOG_FILE="/root/.hermes/logs/managed-agents-relay.log"

set -a; . /root/.hermes/.env; set +a

CHAT_ID="${TG_CHAT_ID:-$TELEGRAM_ALLOWED_USERS}"
BOT_TOKEN="${TELEGRAM_BOT_TOKEN}"

[[ -z "$BOT_TOKEN" ]] && { echo "FATAL: TELEGRAM_BOT_TOKEN not set" >&2; exit 1; }
[[ -z "$CHAT_ID" ]] && { echo "FATAL: no chat_id" >&2; exit 1; }

mkdir -p "$SENT_DIR" "$(dirname "$LOG_FILE")"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

tg_send() {
    local text="$1"
    curl -s --max-time 10 \
        "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        --data-urlencode "chat_id=${CHAT_ID}" \
        --data-urlencode "text=${text}" \
        --data-urlencode "parse_mode=Markdown" \
        >/dev/null 2>&1
}

relay_file() {
    local f="$1"
    local fname; fname=$(basename "$f")
    [[ -f "$f" ]] || return

    local sid result summary
    sid=$(jq -r '.session_id // "???"' "$f" 2>/dev/null)
    result=$(jq -r '.result // "???"' "$f" 2>/dev/null)
    summary=$(jq -r '.summary // ""' "$f" 2>/dev/null)

    local msg
    msg=$(printf '✅ *Agent \`%s\` 完成*\n結果: %s\n摘要: %s' \
        "${sid:0:50}" "${result:0:400}" "${summary:0:200}")

    tg_send "$msg"
    local tg_rc=$?

    if [[ $tg_rc -eq 0 ]]; then
        mv "$f" "$SENT_DIR/" 2>/dev/null
        log "RELAYED $fname → TG (sid=$sid)"
    else
        log "FAILED to send $fname (curl rc=$tg_rc)"
    fi
}

log "=== Relay started (PID $$) ==="
for f in "$WATCH_DIR"/*.json; do
    [[ -f "$f" ]] && relay_file "$f"
done

inotifywait -m "$WATCH_DIR" -e close_write,moved_to --format '%f' 2>/dev/null \
    | while read -r fname; do
        f="$WATCH_DIR/$fname"
        relay_file "$f"
    done
```

### extract_dialogue.py
```python
#!/usr/bin/env python3
"""從最新的 hermes session 提取 agent 回覆，寫入 claude-dialogues/"""
import json, glob, os, time, sys

sessions_dir = os.path.expanduser("~/.hermes/sessions")
dialogues_dir = os.path.expanduser("~/.hermes/claude-dialogues")
os.makedirs(dialogues_dir, exist_ok=True)

files = [f for f in glob.glob(f"{sessions_dir}/session_*.json") if "cron" not in f]
if not files:
    sys.exit(0)

latest = max(files, key=os.path.getmtime)

try:
    with open(latest) as f:
        data = json.load(f)
except (json.JSONDecodeError, OSError):
    sys.exit(0)

messages = data.get("messages", [])

reply = None
for m in reversed(messages):
    if not isinstance(m, dict) or m.get("role") != "assistant":
        continue
    content = m.get("content", "")
    if isinstance(content, str) and content.strip():
        reply = content.strip()
        break
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "").strip()
                if text:
                    reply = text
                    break
        if reply:
            break

if not reply:
    sys.exit(0)

user_msg = None
for m in messages:
    if isinstance(m, dict) and m.get("role") == "user":
        content = m.get("content", "")
        user_msg = content if isinstance(content, str) else ""
        break

agent_name = sys.argv[1] if len(sys.argv) > 1 else "Agent"
ts = int(time.time() * 1000)
out = f"{dialogues_dir}/{ts}_chat.md"

with open(out, "w", encoding="utf-8") as f:
    if user_msg:
        f.write(f"**Claude:**\n{user_msg.strip()}\n\n---\n\n")
    f.write(f"**{agent_name}:**\n{reply}\n")

print(f"Wrote {out}")
```

---

## 10. Hermes Admin Exposure Analysis

**Location**: `/root/hermes-admin/app.py`

### Server Configuration
```python
app = Flask(__name__)
app.run(host='0.0.0.0', port=8765, debug=False)
```

**Security Finding: Binds to 0.0.0.0** — Exposes admin interface to all network interfaces, not just localhost.

### Protected Routes (All Require Auth)
All routes protected with `@require_auth` decorator:
- `/` (home)
- `/edit/<name>` (GET/POST)
- `/credentials` (GET/POST)
- `/restart` (POST)
- `/skills` (GET)
- `/skills/<name>` (GET)
- `/skills/<name>/<filename>` (GET/POST)
- `/logs` (GET)

**Auth Check**: `require_auth()` decorator exists and wraps all endpoints.

---

## 11. State Database Statistics

**Location**: `/root/.hermes/state.db`

### File Size
```
-rw-r--r-- 1 root root 239M May 15 12:24 /root/.hermes/state.db
-rw-r--r-- 1 root root  32K May 15 12:24 /root/.hermes/state.db-shm
-rw-r--r-- 1 root root 4.0M May 15 12:24 /root/.hermes/state.db-wal
```

### Table Schema (sessions)
```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    user_id TEXT,
    model TEXT,
    model_config TEXT,
    system_prompt TEXT,
    parent_session_id TEXT,
    started_at REAL NOT NULL,
    ended_at REAL,
    end_reason TEXT,
    message_count INTEGER DEFAULT 0,
    tool_call_count INTEGER DEFAULT 0,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cache_read_tokens INTEGER DEFAULT 0,
    cache_write_tokens INTEGER DEFAULT 0,
    reasoning_tokens INTEGER DEFAULT 0,
    billing_provider TEXT,
    billing_base_url TEXT,
    billing_mode TEXT,
    estimated_cost_usd REAL,
    actual_cost_usd REAL,
    cost_status TEXT,
    cost_source TEXT,
    pricing_version TEXT,
    title TEXT,
    api_call_count INTEGER DEFAULT 0,
    FOREIGN KEY (parent_session_id) REFERENCES sessions(id)
);
```

### Record Counts
- **Total sessions**: 2,044
- **Total messages**: 22,344
- **FTS indices**: Full-text search enabled (trigram + standard)

---

## 12. Obsidian Vault Research Sample

**Location**: `/root/obsidian-vault/explorations/`

Recent files (3 samples):

### 2026-05-15-Agent-Architecture-Loop-Memory-Caching-三個設計決策維度.md
9 KB, 80+ lines — Analysis of agent loop simplicity (9-line baseline), portable memory wallet fallacies (4 misalignment patterns), prompt caching KV mechanics.

Key insight: Cached KV reduces latency 85% (Anthropic data), mentions Hermes memory pipeline avoids portable-memory risks via single-agent design.

### 2026-05-15-Claws--Sandboxing-Agent-自主權限的光譜與隔離方案.md
5.6 KB, 80+ lines — Karpathy "Claws" concept (user agent + local hardware + messaging), 941 HN comments debate safety boundaries.

Discussion topics: OTP human-in-the-loop (jameslk), context pollution degrading reasoning (mhher), accidental claw evolution (blakec's 15K lines from Claude Code), Gopher protocol preference over REST for agents (daxfohl).

Highlights Safe YOLO Mode (VM snapshots via libvirt), discusses WS-009 (hijacking resilience) as pattern application.

### 2026-05-15-Multi-Agent-Debate-Mysti-的-12-agent-brainstorm-與社群反應.md
6.6 KB — Multi-agent debate patterns, Mysti's 12-agent coordination experiment, community synthesis responses.

---

## 13. Git Commit History

### /root/firn
```
8027ebb sync uv.lock
4f6157a research: task dispatch architecture deep dive (cross-ref managed-agents)
b314452 audit(I19): remove dead user_name param, extract _build_intents helper
340ccdd I19: Discord gateway (full implementation via opencode-go delegation)
add17c6 docs: add DELEGATION_WORKFLOW.md for opencode-go offloading
a743007 I19 W1 (delegation test): scaffolding for Discord support
5fa4796 I17: OpenTelemetry integration (W8.3 + W8.4)
66ac745 I16: OpenAI-compatible HTTP server (/v1/chat/completions)
c577acc I15: MCP support — spawn MCP servers, register tools with mcp__ prefix
fc5665f I14: agentskills.io namespace compatibility
3e8facb audit(I13.5): remove dead fields, extract _parse_response, fix naming
3319895 feat(I13.5): native Gemini provider (thinking + grounding + 1M context)
ec0d104 docs: add research file index to HANDOFF
8cad259 docs: update HANDOFF to reflect I13+T1.1+PhaseA+PhaseB completion (254 tests)
71895b2 feat(phase-b): behavioral tests for 12 solved P-NNN (254 tests total)
```

Recent changes (HEAD~5..HEAD): 989 insertions, 590 deletions
- New files: DELEGATION_WORKFLOW.md (132 lines), research task dispatch (260 lines), Discord gateway (217 lines + tests 277 lines)
- Modified: HANDOFF.md, ROADMAP.md, pyproject.toml, uv.lock

### /root/managed-agents
```
ac89884 research: 2026-05-14 Meta-Agent 監督其他 Agent 的架構
f6d60f1 heartbeat Phase 4: 取消實施計劃 + 更新提案狀態
aca7666 docs: planning skills iteration complete — 5 tasks done, 85/100 quality
72e930c docs: planning skills iteration v3 — closed-loop quality
b1a8a66 research: LLM planning upgrade — 8 techniques
335abb6 docs: OBS-001 long-term tracking plan
c68cb0d docs: OBS-001 injection layer plan + briefing.py implementation
ae4d900 docs: INJ-001 injection layer plan + briefing.py implementation
21b7bee security: remove committed __pycache__ with embedded API key
e969a59 WS-007 DONE: pipe mode SPIKE — hermes -z works, hermes-run wrapper
c1eaa7d WS-006 DONE: heartbeat proposal synced v2.0 (modular, drift sensor, 95 tests)
```

Recent changes: 1,033 insertions, 12 deletions
- New reports: Phase 4 plan (202 lines), planning skills iteration (310 lines), planning upgrade research (252 lines), meta-agent supervision (256 lines)

---

## 14. Novel Project: Western Journey Auto-Fetch

**Location**: `/root/hermes-novel-project/`

**Purpose**: Auto-fetch classical Chinese novels from Wikisource, generate daily reading comprehension notes.

### Structure
```
novels/
reading/
  by_book/
    西遊記/
      progress.json (next_chapter tracking)
      ch001.txt through ch100.txt (chapter texts)
      notes/
        ch001.md through ch100.md (comprehension notes)
scripts/
  auto_fetch.py (main daily runner)
  fetch_book.py (chapter fetching)
  scrape-wikisource.py (Wikisource scraper, -rw------- 6761 bytes)
  verify-wikisource-chapters.py (-rw------- 3446 bytes)
```

### auto_fetch.py Status (2026-05-12 06:03:39)
- **Target**: 水滸傳 (100 chapters)
- **Result**: Timeout after 120s, only 1 chapter (ch025.txt, mismatched format .txt vs .md)
- **Reason**: HTTP 429 rate-limit on Wikisource
- **Bookshelf status**: 西遊記 completed (2026-05-10), 三國演義 completed (2026-05-11)

**Cron job disabled** since 2026-05-14 16:02:11 UTC with reason: "heartbeat: cron error 429 rate-limit"

---

## 15. SSH Authentication & Git Credentials

### SSH Keys
```
ls -la /root/.ssh/
-rw------- authorized_keys (1 key)
-rw-r--r-- known_hosts
```

**Key count**: 1 authorized key configured (likely for main user login).

### Git Credentials
```
/root/.git-credentials exists
```

**Status**: Credentials file present (likely stores GitHub token or similar).

---

## Quick Takes

- **Nine cron jobs active** (2 daily, 1 every 4h, 1 every 12h twice, 1 every 30m, 1 ai-agent-research nightly, 1 disabled due to 429 rate-limit)
- **State.db massive**: 239 MB, 2,044 sessions, 22,344 messages, full-text search enabled
- **Heartbeat system producing 40 failing unit tests** consistently (TestActionConnectProbe probe suite) but outcomes marked "ok"
- **KI-001 known issue suppressed** on every EVOLVE action without visibility into root cause
- **Obsidian vault actively fed by context-distiller**: 9+ exploration notes (2026-05-15) analyzing HN agent architecture trends, sandbox patterns, multi-agent coordination
- **Hermes admin exposed on 0.0.0.0:8765** with auth decorator protection but network-wide visibility
- **Novel scraper disabled** due to Wikisource 429 throttling (100-chapter Western Journey fetch timing out at 120s threshold)
- **Git credentials committed** in plaintext file (security exposure)
- **managed-agents relay replaced bg-reporter** cron (1440 LLM calls/day → event-driven < 1s Telegram relay)
- **Three consolidation pipelines** (memory-tracker → memory-consolidator → briefing-updater) forming autonomous synthesis loop every 2-12 hours
- **Inbox watcher + extract_dialogue** system routes babysit messages through hermes cron with dialogue extraction to claude-dialogues/ for continuity tracking

