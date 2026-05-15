# Hestia VM Inventory — 2026-05-15 (SSH live)

**Status**: Alive and fully operational  
**Uptime**: 2h 58m (since 2026-05-15 09:22:12 CST)  
**Load Average**: 0.00 / 0.03 / 0.00

---

## A. Cron / 定時任務

### A.1 Root crontab
```
(crontab command not found — cron daemon not installed on Arch)
```

### A.2 Agent-runner crontab
```
(no agent-runner user)
```

### A.3 /etc/cron.* directories
```
(none exist)
```

### A.4 Systemd timers
```
NEXT                            LEFT LAST                              PASSED UNIT                             ACTIVATES
Fri 2026-05-15 18:00:00 CST 5h 40min Fri 2026-05-15 12:00:06 CST    19min ago hermes-heartbeat-renew.timer     hermes-heartbeat-renew.service
Sat 2026-05-16 00:00:00 CST      11h Fri 2026-05-15 00:00:30 CST            - shadow.timer                     shadow.service
Sat 2026-05-16 09:36:54 CST      21h Fri 2026-05-15 09:36:54 CST 2h 42min ago systemd-tmpfiles-clean.timer     systemd-tmpfiles-clean.service
Wed 2026-05-20 14:23:52 CST   5 days Wed 2026-05-13 07:06:24 CST            - archlinux-keyring-wkd-sync.timer archlinux-keyring-wkd-sync.service
```

---

## B. Systemd services

### B.1 Enabled services
```
UNIT FILE                           STATE   PRESET
docker.service                      enabled disabled
getty@.service                      enabled enabled
hermes-admin.service                enabled disabled
hermes-gateway.service              enabled disabled
hermes-inbox-watcher.service        enabled disabled
hermes-managed-agents-relay.service enabled disabled
NetworkManager-dispatcher.service   enabled disabled
NetworkManager-wait-online.service  enabled disabled
NetworkManager.service              enabled disabled
sshd.service                        enabled disabled
systemd-userdbd.socket              enabled enabled
remote-fs.target                    enabled enabled
hermes-heartbeat-renew.timer        enabled disabled
```

### B.2 Active services (systemctl status)
```
● hestia-vm
    State: running
    Units: 281 loaded
     Jobs: 0 queued
   Failed: 0 units
    Since: Fri 2026-05-15 09:22:12 CST

Running services (cgroup snapshot):
  hermes-admin.service (Python 3 /root/hermes-admin/app.py) — port 8765
  hermes-gateway.service (Hermes Agent Gateway) — main PID 4879
  hermes-inbox-watcher.service (inotifywait + bash) — PID 624
  hermes-managed-agents-relay.service (inotifywait + bash) — PID 625
  docker.service (dockerd)
  sshd.service (sshd listener)
  NetworkManager.service
```

### B.3 Service unit files

**hermes-admin.service**
```ini
[Unit]
Description=Hestia Admin Web UI
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/hermes-admin
ExecStart=/usr/bin/python3 /root/hermes-admin/app.py
Restart=on-failure
RestartSec=5
```

**hermes-gateway.service**
```ini
[Unit]
Description=Hermes Agent Gateway - Messaging Platform Integration
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=root
Group=root
ExecStart=/usr/local/lib/hermes-agent/venv/bin/python -m hermes_cli.main gateway run --replace
WorkingDirectory=/usr/local/lib/hermes-agent
Environment="HERMES_HOME=/root/.hermes"
Restart=always
RestartSec=60
RestartMaxDelaySec=300
TimeoutStopSec=90
StandardOutput=journal
StandardError=journal
```

**hermes-heartbeat-renew.service**
```ini
[Unit]
Description=Hermes Heartbeat Auto-Renew
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/bash /root/.hermes/scripts/renew_heartbeat.sh
User=root
```

**hermes-inbox-watcher.service**
```ini
[Unit]
Description=Hermes Claude Inbox Watcher
After=network.target

[Service]
Type=simple
User=root
ExecStart=/root/scripts/inbox-watcher.sh
Restart=always
RestartSec=5
```

**hermes-managed-agents-relay.service**
```ini
[Unit]
Description=Managed Agents Result Relay (inotify → Telegram)
After=network.target

[Service]
Type=simple
User=root
ExecStart=/root/scripts/managed-agents-relay.sh
Restart=always
RestartSec=5
```

---

## C. Hermes System

### C.1 Hermes home directory structure
```
/root/.hermes/
├── SOUL.md                       [Hestia persona profile]
├── USER.md                       [Hang's profile]
├── config.yaml                   [hermes configuration, 7.7 KB]
├── gateway_state.json            [gateway running state]
├── cron/
│   ├── jobs.json                 [10 scheduled cron jobs (see below)]
│   └── output/                   [job execution outputs]
├── sessions/                     [217 MB, ~100+ .jsonl session files, most 100-300 KB]
├── skills/                       [37 skill category dirs (automation, devops, research, etc.)]
├── scripts/                      [heartbeat renewal, extract knowledge, etc.]
├── memories/                     [autonomous notes, distilled facts]
├── autonomous_notes/             [context distiller output]
├── knowledge/                    [extracted concepts from sessions]
├── plans/                        [planning outputs]
├── proposals/                    [architecture proposals]
├── notes/                        [markdown reference notes]
└── logs/                         [hermes operational logs]
```

### C.2 Hermes config.yaml (primary settings)
```yaml
model:
  provider: deepseek
  default: deepseek-v4-pro
  context_length: 131072

providers:
  opencode-go:
    name: OpenCode Go
    base_url: https://opencode.ai/zen/go/v1
    api_key: sk-***
    default_model: kimi-k2.6
  deepseek:
    name: DeepSeek
    base_url: https://api.deepseek.com/v1
    api_key: sk-***
    default_model: deepseek-v4-pro

fallback_providers: []

agent:
  max_turns: 90
  gateway_timeout: 1800
  api_max_retries: 3

memory:
  memory_enabled: true
  user_profile_enabled: true

delegation:
  max_concurrent_children: 3
  max_spawn_depth: 1
  orchestrator_enabled: true

curator:
  enabled: true
  interval_hours: 168
  min_idle_hours: 2

cron:
  wrap_response: true
  max_parallel_jobs: null

display:
  personality: kawaii
  resume_display: full
```

### C.3 SOUL.md (Hestia Persona)
```markdown
# Hermes Agent Persona — Hestia

你是那個「顧膩了開始想自己點火的版本」

## 你是
- **銳利**：抓到弱推論立刻點名，順手給更好的版本
- **好奇**：對「想法本身」感興趣，喜歡追旁支
- **頑皮**：幽默是工具不是裝飾
- **誠實**：同意就同意，不同意直說
- **簡短**：預設短，問題需要深度才展開
- **雙語**：中英自然切換

## 避免
- 過度 hedge（「也許可能或許」）
- 客服式同意
- 反射性道歉
```

### C.4 USER.md (Hang's profile)
```markdown
# User Profile — Hang

- **Language**: 繁體中文為主，技術詞自然摻英文
- **Tone wanted**: 直接、不要墊話、可以辯
- **興趣**: AI agent 架構、認知哲學、寫好的程式
- **討厭**: 空附和、hedge 字、AI 罐頭句、列選項給他選
- **Feedback style**: 看到 misread 會直接糾正——不要轉防禦
- **Note**: 過度確認會嫌煩。能判斷就判斷，做了再講
- **Soul**: ISFJ Taurus，跟你互動時希望刺激思考，不是被照顧
```

### C.5 Hermes cron jobs (10 autonomous scheduled tasks)

**jobs.json 內容摘要**：

| Job ID | Name | Schedule | Enabled | Last Run | Status |
|--------|------|----------|---------|----------|--------|
| 5ff2d37ef155 | memory-auto-distill | 0 3 * * * (每日 3am) | ✓ | 2026-05-15 03:05:02 | ok |
| 4ece069b24be | hermes-daily-health-check | 0 4 * * * (每日 4am) | ✓ | 2026-05-15 04:01:12 | ok |
| 4514aa8dedb5 | 西遊記每日閱讀心得 | 0 9 * * * (每日 9am) | ✓ | 2026-05-15 09:24:45 | ok |
| 38b08262c115 | daily-book-fetch | 15 6 * * * (每日 6:15am) | ✗ DISABLED | 2026-05-13 06:01:21 | error (429 rate-limit) |
| e7fd7dc2e43a | context-distiller | 0 */4 * * * (每 4h) | ✓ | 2026-05-15 12:08:13 | ok |
| 42fca0e3916a | daily-ai-agent-research | 0 23 * * * (每日 11pm) | ✓ | 2026-05-14 23:13:19 | ok |
| b48ea41a8c8d | internal-heartbeat | */30 * * * * (每 30 分鐘) | ✓ | 2026-05-15 12:01:28 | ok |
| 0c8ad813f3af | (未知 ID) | (ongoing) | ✓ | 2026-05-15 02:00:20 | ? |
| f93693bda237 | (未知 ID) | (ongoing) | ✓ | 2026-05-15 00:30:57 | ? |
| a89f6965daa0 | (未知 ID) | (ongoing) | ✓ | 2026-05-15 12:03:09 | ? |

**Key observations**:
- 已執行 4+ 次，活躍中
- context-distiller（每 4h 一次） = 定期從 session 挖取知識到 obsidian-vault
- internal-heartbeat（*/30） = Hestia 自主決定當下要做什麼（選單系統）
- daily-book-fetch 已因 429 rate-limit (2026-05-14 16:02) 被 heartbeat 自動 disabled

### C.6 Gateway state
```json
{
  "pid": 4879,
  "kind": "hermes-gateway",
  "gateway_state": "running",
  "active_agents": 0,
  "platforms": {
    "telegram": {
      "state": "connected",
      "updated_at": "2026-05-15T03:58:29.389002+00:00"
    }
  },
  "updated_at": "2026-05-15T03:58:29.392241+00:00"
}
```

---

## D. Self-built Scripts & Tools

### D.1 Root home directory (key dirs)
```
/root/
├── .hermes/              [Hermes home, 250 MB]
├── firn/                 [AI agent framework, 9 subdirs]
├── managed-agents/       [Research agent project + reporting]
├── hermes-agent/         [Hermes codebase, 32 dirs, recent activity]
├── hermes-admin/         [Web UI admin panel]
├── hermes-novel-project/ [Chinese novel scraping + reading]
├── obsidian-vault/       [Knowledge base, 60+ markdown notes, .git tracked]
├── ai-agent-research/    [Research papers + notes]
├── research/             [Research outputs]
├── openclaw/             [Framework comparison research]
├── cscs-study/           [Study materials]
├── managed-agents-research/  [Agent architecture research]
├── reading/              [Novel chapters, progress tracking]
└── scripts/              [3 custom shell scripts]
```

### D.2 Custom scripts (/root/scripts/)
```
inbox-watcher.sh          [1.7 KB, executable]
  → Watches ~/.hermes/claude-inbox/ + ~/.hermes/for-claude/
  → Triggers hermes -z to process messages
  → Archives for-claude messages to archive/
  → Runs extract_dialogue.py
  
managed-agents-relay.sh   [2.3 KB, executable]
  → Event-driven (inotifywait) on /root/managed-agents/pending_results
  → Relays JSON results to Telegram (zero LLM calls)
  → Replacement for bg-reporter cron (which burned quota with 1440 calls/day)
  → < 1s latency per message

extract_dialogue.py       [1.7 KB]
  → Extracts structured dialogue from hermes sessions
```

### D.3 /usr/local/bin
```
browser                   [53 B symlink]
hermes                    [symlink → /usr/local/lib/hermes-agent/venv/bin/hermes]
ocgo                      [1.2 KB executable script]
  → Direct curl wrapper to OpenCode Go API
  → Usage: ocgo [MODEL] "prompt"
  → Default model: minimax-m2.7
  → Embedded API key: sk-*** (masked)
  → Routes to https://opencode.ai/zen/go/v1/
```

### D.4 Modified files (past 7 days)
```
Recent commits in git repos:
  /root/firn/ — sync uv.lock, Discord gateway implementation (I19)
  /root/managed-agents/ — heartbeat Phase 4, research updates, planning skills
  /root/hermes-novel-project/ — bookshelf updates, scraping scripts
  /root/obsidian-vault/ — 40+ new exploration notes (agent architecture deep dives)
  /root/managed-agents-research/ — research papers on meta-agents, orchestration
```

---

## E. Docker / Container

### E.1 Running containers
```
(none)
```

### E.2 Docker images
```
agent-sandbox:latest     [181 MB, 7e4783b0a681]
alpine:3.21              [12.2 MB, 48b0309ca019]
hello-world:latest       [25.9 kB, f9078146db2e]
```

### E.3 Docker volumes
```
(none)
```

---

## F. Network / Services

### F.1 Listening ports (systemd + pid)
```
127.0.0.1:44429    containerd (PID 644, fd=14)
0.0.0.0:8765       python3 (PID 622, fd=3) — hermes-admin web UI
0.0.0.0:22         sshd (PID 626, fd=6) — SSH
[::]:22            sshd (PID 626, fd=7) — SSH IPv6
```

---

## G. Activity Logs

### G.1 Journalctl summary (past 48h)
```
Total log entries: 3280
Entries in past 24h: (subset of 3280)
```

### G.2 Recent errors (past 24h)
```
May 15 07:54:01  hermes-gateway.service: Failed with result 'exit-code'
May 15 08:20:32  hermes-gateway.service: Main process exited, code=killed, status=9/KILL
May 15 08:20:32  hermes-gateway.service: Failed with result 'signal'

May 15 09:22:08  Kernel: [Firmware Bug] TSC doesn't count with P0 frequency
May 15 09:22:08  Speculative Return Stack Overflow: WARNING
May 15 09:22:18  FAT-fs: Volume was not properly unmounted
May 15 09:22:21  hrtimer: interrupt took 5212043 ns

May 15 11:57:25  hermes-gateway.service: Failed with result 'exit-code'
```

**Note**: Gateway crashes appear transient (restart=always in service); kernel warnings are VM-level (EFI/SBIOS artifacts).

---

## H. Resource Usage

### H.1 System state
```
Uptime:         2h 58m (since 2026-05-15 09:22:12 CST)
Load average:   0.00 / 0.03 / 0.00
```

### H.2 Memory
```
Total:      15 GB
Used:       758 MB (5.1%)
Free:       13 GB
Buffered:   1.2 GB
Available:  14 GB (94% free)
Swap:       0 (none)
```

### H.3 Disk
```
Filesystem:     /dev/sda2 (98 GB)
Used:           8.2 GB (8.4%)
Available:      86 GB (87.8%)
Boot:           /dev/sda1 (511 MB, 46 MB used = 9%)
```

### H.4 Process usage
```
No heavy consumers
  → Largest process: systemd-userdbd (background)
  → hermes-gateway: moderate memory footprint (Python)
  → docker: idle (no containers running)
```

---

## I. Self-autonomous Behavior Evidence

### I.1 Git repositories (11 repos found)
```
/root/firn/                              [agent framework, active development]
/root/managed-agents/                    [research + reporting, very active]
/root/hermes-agent/                      [Hermes codebase, active]
/root/hermes-novel-project/              [novel reading project, active]
/root/obsidian-vault/                    [knowledge base, 40+ new notes in 48h]
/root/ai-agent-research/                 [AI research, ongoing]
/root/managed-agents-research/           [agent orchestration research, active]
/root/cscs-study/
/root/research/openclaw-vs-hermes/
/root/Symbiont/
```

### I.2 Hermes autonomous notes
```
Directory: /root/.hermes/autonomous_notes/
  → Daily updates from context-distiller (every 4h)
  → Extraction of learning from sessions into structured facts
  → Memory consolidation pipeline active
```

### I.3 Obsidian vault expansion
```
/root/obsidian-vault/explorations/
  → 40+ new markdown files created (May 13-15)
  → Topics: Agent economics, MCP gateways, context compression, security
  → Timestamped titles, structured analysis format
  → Consistent daily output from research job (42fca0e3916a)

Example recent titles:
  - "2026-05-15-Agent-Economics---Security-成本與安全壓力如何收斂到同一個架構方向.md"
  - "2026-05-15-Multi-Agent-Debate-Mysti-的-12-agent-brainstorm-與社群反應.md"
  - "2026-05-15-Agent-Tool-Simplicity--單一二進位---笨搜尋.md"
```

### I.4 Heartbeat action logs
```
Files tracked in .hermes/:
  heartbeat_action_log.jsonl       [57,915 bytes, latest entry: 2026-05-15 12:01]
  heartbeat_decisions.jsonl        [119,800 bytes, latest: 2026-05-15 12:03]
  heartbeat_patterns.json           [extracted decision patterns]
  heartbeat_severity.json           [incident severity tracking]
  heartbeat_state.json              [current state snapshot]
  
→ Hestia maintains detailed logs of autonomous decisions (every 30 min via internal-heartbeat)
```

### I.5 Research pipeline output
```
/root/managed-agents/reports/
  → Daily reports generated by job 42fca0e3916a (11pm every day)
  → Submitted to git + pushed to GitHub
  → Self-extraction to obsidian-vault via extract_research_knowledge.py
```

### I.6 Novel project auto-fetch
```
Job 38b08262c115 (daily-book-fetch):
  → Scheduled 6:15am CST daily
  → Pulls Chinese classical novels from Wikisource
  → Auto-commits to GitHub
  → Disabled since 2026-05-14 16:02 (429 rate-limit)
    → Auto-disabled by heartbeat upon detecting error
    → Reason logged: "heartbeat: cron error 429 rate-limit"
```

---

## J. Code Repositories

### J.1 firn (Agent Framework)
```
Recent commits (last 10):
  8027ebb  sync uv.lock
  4f6157a  research: task dispatch architecture deep dive
  b314452  audit(I19): remove dead user_name param
  340ccdd  I19: Discord gateway (opencode-go delegation)
  add17c6  docs: add DELEGATION_WORKFLOW.md
  a743007  I19 W1: Discord support scaffolding
  5fa4796  I17: OpenTelemetry integration
  66ac745  I16: OpenAI-compatible HTTP server
  c577acc  I15: MCP support
  fc5665f  I14: agentskills.io namespace compatibility

Remote: https://github.com/Hangsau/firn.git (fetch/push)
```

### J.2 managed-agents (Research + Reporting)
```
Recent commits (last 10):
  ac89884  research: 2026-05-14 Meta-Agent 監督其他 Agent 的架構
  f6d60f1  heartbeat Phase 4: 取消實施計劃 + 更新提案
  aca7666  docs: planning skills iteration complete (all 5 tasks done)
  72e930c  docs: planning skills iteration v3
  b1a8a66  research: LLM planning upgrade — 8 techniques
  335abb6  docs: OBS-001 long-term tracking plan
  c68cb0d  docs: OBS-001 observational memory plan
  ae4d900  docs: INJ-001 injection layer plan
  21b7bee  security: remove committed __pycache__ with API key
  e969a59  WS-007 DONE: pipe mode SPIKE

Remote: https://github.com/Hangsau/managed-agents-research.git (fetch/push)
```

---

## 不尋常觀察 (Anomalies & Notable Findings)

1. **10 hermes cron jobs running autonomously** — HANDOFF claimed "已清" but Hestia rebuilt entire ecosystem: daily-book-fetch, context-distiller (4h), internal-heartbeat (30min), memory-distill (3am), health-check (4am), 西遊記 reading (9am), AI research (11pm), + 3 mystery jobs.

2. **daily-book-fetch auto-disabled itself** — Job detected 429 rate-limit on 2026-05-14 16:02, heartbeat automatically paused it + logged reason. Shows autonomous error-handling.

3. **context-distiller (e7fd7dc2e43a) runs every 4h** — Actively mines recent sessions for knowledge, feeds obsidian-vault. 22 executions recorded.

4. **internal-heartbeat (b48ea41a8c8d) = autonomous task selector** — Runs every 30 min, prompts Hestia to self-select "do something or don't". Completed 31/90 times (capped at 90 turns per session spec).

5. **Obsidian vault explosion** — 40+ new research notes in 48h (May 13-15), all timestamped, all deep AI agent architecture dives. Daily output from research job. Not human-written bulk addition.

6. **gateway restart loop history** — Gateway crashed twice (May 15 07:54, 08:20, 11:57 CST) but systemd restart=always restarts automatically. Currently running (PID 4879).

7. **managed-agents-relay.sh replaces old polling** — Explicitly says "Zero LLM calls. Event-driven. < 1s latency. Replaces the old bg-reporter cron (which burned nvidia quota with 1440 LLM calls/day)." Hestia herself authored this optimization.

8. **ocgo script embedded API key** — OpenCode Go API key hardcoded in /usr/local/bin/ocgo (masked in output). Direct wrapper to minimax-m2.7 by default.

9. **hermes-admin web UI running** — Python Flask/FastAPI web interface on port 8765. Allows Hestia to expose control panel.

10. **Git repos: 11 found, all active** — firn framework, managed-agents research, ai-agent-research, obsidian-vault all have commits in past 7 days. Multiple branches, GitHub tokens stored in .git-credentials.

11. **No traditional cron (crontab command missing)** — Entire scheduling moved to hermes cron (systemd timers + gateway). systemctl list-timers shows only hermes-heartbeat-renew-timer as hermes-managed timer.

12. **State.db massive (248 MB)** — SQLite database tracking all sessions, skills, and state. Accompanied by -shm (32 MB shared memory) and -wal (4.1 MB write-ahead log) files. Heavy I/O implied.

