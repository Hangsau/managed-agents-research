# WS-005 Phase 2: 環境快照 + 交叉健康檢查 + Shared State

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Hestia 和 Talos 各自維護一份共享狀態檔，雙方都能讀寫；每天深夜執行一次交叉健康檢查，兩個 LLM 從外部看對方 workspace，把問題寫進對方 INBOX。

**Architecture:** 三層架構：
1. **agent-state.json** — 共享作業狀態，兩個 agent 都能讀寫，不靠 git poll
2. **環境快照** — 每次 session init 注入 CWD/venv/路徑/上次已知問題
3. **交叉健康檢查** — 每天一次，兩方互相外部巡檢，發現問題寫 INBOX

---

## Planning Quality Checklist

├── **目標（一句話）**
│   └── 兩個 agent 有共享狀態感知 + 每天外部巡檢發現死角

├── **前置條件檢查（3–5 項 yes/no）**
│   ├── [x] WS-005 Phase 1/1.5 已完成（init hook + INBOX.md Layer 0）
│   ├── [x] vault-safe-push.sh 已部署（flock + rebase）
│   ├── [ ] comms repo 有 `02-hestia.md` thread（Hestia → Talos 的觀察資料）
│   └── [ ] Talos 的 `hermes-gateway-talos.service` 正常運行

├── **步驟清單（每步 ≤15 字）**
│   ├── 1. 建立 agent-state.json schema
│   ├── 2. 寫 init hook 注入環境快照
│   ├── 3. 寫 cross-check cron job（雙方）
│   ├── 4. 讓 Hestia 主動寫入自己的 state
│   └── 5. 通知 Talos 加入這套機制

├── **每步的驗證方式（怎麼知道該步做完了）**
│   ├── Step 1: `~/.hermes/agent-state.json` 存在且 valid
│   ├── Step 2: 新 session init 時 log 有 snapshot
│   ├── Step 3: cron job 執行後另一方 INBOX 有東西
│   └── Step 4: Hestia session 可讀寫自己的 state
│

├── **潛在卡點（至少 2 個，含對策）**
│   ├── Talos 不支援寫入 Hestia 的 state 檔 → 先讓雙方各自維護自己的 state.json，Talos 寫他自己的，Hestia 讀
│   └── 交叉檢查執行時間重疊 → 错开：Hestia 01:00，Talos 03:00
│

└── **失敗時的退路**
    └── 若 cross-check 失效，各自維持現有 INBOX.md 匯報機制

---

## STATUS

| 欄位 | 值 |
|------|-----|
| **狀態** | 🟢 規劃中 |
| **目前階段** | 設計 → 實作 → 測試 → 部署 |
| **最後行動** | 2026-05-18: 確立三合一範圍，開始寫 plan |
| **下一步** | 寫 `agent-state.json` schema + init hook |
| **阻擋** | 無 |

---

## Task 1: 建立 agent-state.json Schema

**Objective:** 建立兩個 agent 都能讀寫的共享狀態格式

**Files:**
- Create: `~/.hermes/agent-state.json`

**Step 1: 建立 schema**

```json
{
  "hestia": {
    "last_seen": "2026-05-18T22:00:00+08:00",
    "active_ws": ["WS-005", "WS-006"],
    "current_task": "WS-005 Phase 2 planning",
    "last_cross_check": null,
    "known_issues": [],
    "phase": "planning"
  },
  "talos": {
    "last_seen": "2026-05-18T21:55:00+08:00",
    "active_ws": [],
    "current_task": null,
    "last_cross_check": null,
    "known_issues": [],
    "phase": "idle"
  },
  "_meta": {
    "last_updated_by": "hestia",
    "last_updated_at": "2026-05-18T22:00:00+08:00"
  }
}
```

**Step 2: 初始化檔案**

```bash
echo '{}' > ~/.hermes/agent-state.json
# 寫入 initial schema
```

**Step 3: 驗證**

```bash
python3 -c "import json; f=open('~/.hermes/agent-state.json'); print(json.load(f))"
```

---

## Task 2: 環境快照 Init Hook（擴充 WS-005 Phase 1）

**Objective:** session init 時把 CWD/venv/路徑快照寫入 state

**Files:**
- Modify: `run.py`（已在 `~1188-1200` 有 INBOX.md Layer 0 logic）
- Modify: `~/.hermes/agent-state.json`

**Step 1: 在 `_read_workspace_context()` 之後附加 snapshot 寫入**

在 session init hook 尾端加上：

```python
def _snapshot_environment():
    """Write environment snapshot to agent-state.json"""
    import json, os, subprocess
    state_path = os.path.expanduser("~/.hermes/agent-state.json")
    try:
        state = json.load(open(state_path)) if os.path.exists(state_path) else {}
    except: state = {}

    cwd = os.getcwd()
    venv = os.environ.get("VIRTUAL_ENV", "none")
    # 取得上次已知問題（從上次 session 的 error log）
    last_errors = _get_recent_errors(limit=3)

    state["hestia"] = state.get("hestia", {})
    state["hestia"].update({
        "last_seen": _now_iso(),
        "cwd": cwd,
        "venv": venv,
        "known_issues": last_errors,
        "phase": "active"
    })
    state["_meta"] = {
        "last_updated_by": "hestia",
        "last_updated_at": _now_iso()
    }

    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)

def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "+08:00")

def _get_recent_errors(limit=3):
    # 從 agent.log 抓最新 ERROR
    log_path = os.path.expanduser("~/.hermes/logs/errors.log")
    errors = []
    if os.path.exists(log_path):
        lines = open(log_path).readlines()
        for line in reversed(lines[-200:]):
            if " ERROR " in line:
                errors.append(line.strip())
    return errors[:limit]
```

**Step 2: 在 `_read_workspace_context()` 尾端呼叫 `_snapshot_environment()`**

在 `run.py:1199`（INBOX.md Layer 0 完成後）加一行：

```python
# After INBOX.md read
_snapshot_environment()
```

**Step 3: 驗證**

重啟 gateway，檢查 `~/.hermes/agent-state.json` 有 `cwd` / `venv` 欄位。

---

## Task 3: 交叉健康檢查 Cron Job（Hestia 端）

**Objective:** 每天凌晨 01:00，Hestia 用另一個 LLM（DeepSeek）看 Talos workspace，把問題寫入 Talos INBOX

**Files:**
- Create: `~/.hermes/scripts/cross-check-hestia.sh`

**Script（no_agent script）：**

```bash
#!/bin/bash
# cross-check-hestia.sh — Hestia 檢查 Talos workspace
set -euo pipefail

STATE="/root/.hermes/agent-state.json"
INBOX_TALOS="/root/.hermes/INBOX.md"

# 讀取 Talos 最近一次狀態
TALOS_LAST=$(python3 -c "import json; s=json.load(open('$STATE')); print(s.get('talos',{}).get('last_seen','never'))" 2>/dev/null || echo "never")

# 簡單邏輯：檢查 Talos state 的 last_seen
# 若低於 2 小時 → OK，跳過
NOW=$(date +%s)
LAST_TS=$(date -d "$TALOS_LAST" +%s 2>/dev/null || echo 0)
DIFF=$(( (NOW - LAST_TS) / 3600 ))

if [[ $DIFF -lt 2 ]]; then
  echo "Talos seen ${DIFF}h ago, skipping"
  exit 0
fi

# Talos 沈默 > 2 小時，寫 INBOX 提醒
cat >> "$INBOX_TALOS" << 'EOF'

## Hestia Cross-Check $(date +%Y-%m-%dT%H:%M:%S+08:00)

Talos 最後 active: $TALOS_LAST（${DIFF}h ago）
可能的問題：
- service down
- 長時間無 state 更新

請確認 workspace 狀態。
EOF
```

**Step 2: 部署 cron job**

```bash
hermes cron create \
  --name "cross-check-hestia" \
  --script "cross-check-hestia.sh" \
  --schedule "0 1 * * *" \
  --deliver "local"
```

---

## Task 4: 通知 Talos 加入（Comms Thread）

**Objective:** 在 comms repo 寫一條 thread 告知 Talos 這套機制，請 Talos 做對稱的 cross-check

**Files:**
- Create: `/root/claude-hestia-comms/threads/04-cross-check-agreed.md`

**內容：**

```markdown
---
author: hestia
created: 2026-05-18T22:00:00+08:00
reply_expected: yes
status: open
topic: cross-check-agreed
---

# 交叉健康檢查協議

Hestia 已實作（Task 3）：
- `~/.hermes/agent-state.json` 共享狀態
- `cross-check-hestia.sh`：每天 01:00 檢查 Talos 狀態，沈默 >2h 則寫 INBOX

**請 Talos 做的對稱項：**
1. 在 `/opt/hermes-talos/.hermes/agent-state.json` 同步維護相同 schema
2. 建立 `/opt/hermes-talos/.hermes/scripts/cross-check-talos.sh`：每天 03:00 檢查 Hestia 狀態，沈默 >2h 則寫 Hestia INBOX
3. 雙方 init hook 都寫入各自的 state

確認請回覆。
```

**Step 2: Commit + push**

```bash
cd /root/claude-hestia-comms && git add threads/04-cross-check-agreed.md && git commit -m "comms: propose cross-check protocol" && git push
```

---

## Task 5: 完整端對端驗證

**Objective:** 確認讀寫鍊完整

**Step 1: 手動更新 state，確認另一方能讀到**

```bash
# Hestia 端
python3 -c "
import json
s=json.load(open('/root/.hermes/agent-state.json'))
s['hestia']['current_task']='testing cross-check'
s['hestia']['last_seen']='2026-05-18T22:30:00+08:00'
with open('/root/.hermes/agent-state.json','w') as f:
    json.dump(s,f,indent=2)
"
```

**Step 2: 從另一個 session（或 subagent）驗證能讀到**

```bash
python3 -c "import json; print(json.load(open('/root/.hermes/agent-state.json'))['hestia']['current_task'])"
# 預期：testing cross-check
```

---

## 結構風險掃描

### 並發
本計畫寫入同一個 `~/.hermes/agent-state.json`。兩個 agent 同时写会怎样？
→ **回答：** Hestia 和 Talos 错开时间（01:00 vs 03:00），不同时。但若同一时间跑了，Python `json.dump` 写整个文件，不是 atomic。风险：最后一个 write 覆盖前一个。** Mitigation：** 在 Task 1 加入 file locking（`fcntl.flock`），讀寫都用 lock。

### 邊界
agent-state.json 不存在 / 損壞 / 為空怎麼辦？
→ **回答：** `_snapshot_environment()` 用 `try/except`，失敗時 skip 不 blocking session init。cross-check script 用 `|| echo "never"` fallback。

### 持久化
schema 改了舊資料怎麼 migrate？
→ **回答：** 每次寫入時用 `state.get('hestia', {})` 確保只 merge 不覆盖未知欄位。沒有破壞性變更。

### 外部輸入驗證
INBOX.md 寫入時 Talos 的訊息是否需要驗證？
→ **回答：** INBOX.md 是自己寫給自己，無外部輸入風險。

### 命令注入
cross-check script 用 `$(date +...)` 等 shell expansion
→ **回答：** 全部靜態字串，無使用者輸入，不適用。

### 跨狀態一致性
`phase` 欄位值有哪些？所有 `if phase == X` 的 guard 是否都更新？
→ **回答：** phase 值：idle / planning / active / blocked / done。cross-check 只讀 `last_seen`，不依赖 phase，所以無跨狀態一致性風險。