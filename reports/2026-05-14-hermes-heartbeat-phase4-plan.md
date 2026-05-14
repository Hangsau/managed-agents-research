# Heartbeat Phase 4：學習管線整合 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 讓 heartbeat 在自主維護循環中，自動觸發 learning-extraction，並加入 log rotation 防止磁碟膨脹。

**Architecture:** 不新增 skill。在 heartbeat 的 cognition cycle 中插入 learning 觸發點，用現有 `extract_learning.py` + 新增 log rotation 模組。純 shell/Python，零 LLM token 消耗。

**Tech Stack:** Python 3.14, bash, cron, SQLite（learning DB 已存在）

## Planning Quality Checklist (MANDATORY — fill every field)

├── **目標（一句話）**
│   └── heartbeat 完成自主行動後自動提取學習、log 超過 N 天自動清理

├── **前置條件檢查（3–5 項 yes/no）**
│   ├── [x] heartbeat v2 模組化架構已部署（7 檔案）
│   ├── [x] extract_learning.py 存在且可獨立執行
│   ├── [x] learning DB（SQLite）存在
│   ├── [ ] learning-extraction 從未被 heartbeat 觸發（目前手動）
│   └── [ ] heartbeat log 無 rotation 機制

├── **步驟清單（每步 ≤15 字）**
│   ├── 1. 在 cognition cycle 加 learning trigger
│   ├── 2. 實作 log rotation 模組
│   ├── 3. 整合測試（dry-run + 實際觸發）
│   └── 4. 更新 heartbeat 文件

├── **每步的驗證方式（怎麼知道該步做完了）**
│   ├── Step 1: heartbeat 自主循環後 learning DB 有新記錄
│   ├── Step 2: log 檔案 >30 天被自動刪除
│   ├── Step 3: `pytest test_heartbeat_v2.py -v -k learning` 全過
│   └── Step 4: 計畫書 Phase 4 狀態更新

├── **潛在卡點（至少 2 個，含對策）**
│   ├── extract_learning.py 依賴 session 檔案路徑但 heartbeat 不知路徑 → 對策：heartbeat 維護一個「待提取 session 清單」（SQLite 表格），learning trigger 批次傳入
│   └── log rotation 誤刪正在寫入的 log → 對策：rotate 前檢查 atime < now - 7d（不是 mtime），確保 7 天無人存取才刪

└── **失敗時的退路**
    └── 拆成兩階段：先只做 log rotation（風險最低），learning trigger 觀察一陣子再整合

---

## STATUS

| 欄位 | 值 |
|------|-----|
| **狀態** | 🔴 CANCELLED — 計劃基於錯誤假設 |
| **目前階段** | 事後檢討 |
| **最後行動** | 2026-05-14: 計劃寫完後讀程式碼發現 heartbeat 已有學習觸發（heartbeat_learning.py）及 log rotation（action_rest + explore）。extract_learning.py（Obsidian vault）仍缺乏整合但規模遠小於計劃假設。 |
| **下一步** | extract_learning.py vault 整合 (小 task，非 Phase 4 範圍) |
| **阻擋** | 無 |
| **事後檢討** | Self-Critique 漏洞 1 命中：未先讀 codebase 就寫計劃。Heartbeat 是 Python 非 bash、API 簽名不同、功能已預先存在。計劃中的 4 tasks 僅 Task 1 有實質缺口（extract_learning.py 未整合到 EVOLVE，但現有 heartbeat_learning.py 已覆蓋 patterns 層）。plan-review v1.1.0 審查未發現此問題——審查只看計劃內部一致性，不檢查外部 codebase 事實。未來改進方向：寫作階段強制讀 codebase validation step。 |

---

## 現況評估

heartbeat proposal v2.0 列出 Phase 4 三個項目。本案只取前兩項（最實用的）：

| Phase 4 項目 | 納入？ | 理由 |
|-------------|--------|------|
| learning-extraction 整合 | ✅ | 核心價值：讓自主學習自動化 |
| log rotation | ✅ | 防禦性：log 膨脹最終會塞爆磁碟 |
| 動態閾值 | ❌ 延後 | 需要先積累足夠數據才能校準 |

---

## Task Breakdown

### Task 1: 在 cognition cycle 加 learning trigger

**Objective:** heartbeat 完成自主行動（ACTUATE）後自動呼叫 extract_learning.py

**Files:**
- Modify: `~/.hermes/scripts/heartbeat/cognition_cycle.sh`
- Read: `~/.hermes/scripts/extract_learning.py`（確認 CLI 介面）

**變更內容：**

在 `cognition_cycle.sh` 的 ACTUATE 階段後插入：

```bash
# --- Learning Extraction Trigger ---
# After any autonomous action, extract learnings from recent sessions
LEARNING_DB="$HOME/.hermes/data/learning.db"
PENDING_SESSIONS="$HOME/.hermes/data/pending_learning.txt"

if [ -f "$PENDING_SESSIONS" ] && [ -s "$PENDING_SESSIONS" ]; then
    python3 ~/.hermes/scripts/extract_learning.py \
        --db "$LEARNING_DB" \
        --sessions "$PENDING_SESSIONS" \
        --max-sessions 3 \
        >> "$LOG_FILE" 2>&1
    
    # Clear processed sessions
    :> "$PENDING_SESSIONS"
fi
```

**Step 1:** Read `extract_learning.py` 確認參數格式
**Step 2:** Patch `cognition_cycle.sh` 插入 trigger
**Step 3:** Dry-run: `bash -n cognition_cycle.sh`（語法檢查）
**Step 4:** Commit

**Verification:** `grep "extract_learning" cognition_cycle.sh` 有結果

---

### Task 2: 實作 log rotation 模組

**Objective:** 新模組自動清理超過 N 天的 heartbeat log

**Files:**
- Create: `~/.hermes/scripts/heartbeat/log_rotation.sh`
- Modify: `~/.hermes/scripts/heartbeat/cognition_cycle.sh`（呼叫 rotation）

**內容：**

```bash
#!/bin/bash
# log_rotation.sh — 清理超過 RETENTION_DAYS 天的 heartbeat log
set -euo pipefail

LOG_DIR="${1:-$HOME/.hermes/logs/heartbeat}"
RETENTION_DAYS="${2:-30}"
DRY_RUN="${3:-false}"

cleanup() {
    local before_count=$(find "$LOG_DIR" -name "*.log" -type f | wc -l)
    local deleted=0
    
    while IFS= read -r f; do
        # Safety: only delete files not accessed in 7 days (not just old mtime)
        if [ "$(stat -c %X "$f")" -lt "$(date -d "7 days ago" +%s)" ]; then
            if [ "$DRY_RUN" = "true" ]; then
                echo "[DRY-RUN] Would delete: $f"
            else
                rm -f "$f"
                ((deleted++))
            fi
        fi
    done < <(find "$LOG_DIR" -name "*.log" -type f -mtime +"$RETENTION_DAYS")
    
    local after_count=$(find "$LOG_DIR" -name "*.log" -type f | wc -l)
    echo "log_rotation: $before_count → $after_count ($deleted deleted)"
}

cleanup
```

**Step 1:** Create `log_rotation.sh` with `chmod +x`
**Step 2:** Patch `cognition_cycle.sh` 在開頭呼叫（每次循環前做一次 rotation）
**Step 3:** Dry-run: `bash log_rotation.sh /tmp/test_logs 0 true`
**Step 4:** Commit

**Verification:** `bash log_rotation.sh "$HOME/.hermes/logs/heartbeat" 365 true` 輸出 dry-run 結果

---

### Task 3: 整合測試

**Objective:** 確保兩功能不破壞既有測試

**Files:**
- Run: `~/.hermes/scripts/heartbeat/test_heartbeat_v2.py`

**Step 1:** `pytest test_heartbeat_v2.py -v` → 95 tests passed
**Step 2:** 手動觸發一次 heartbeat 循環，檢查 learning DB 和 log rotation 都有輸出
**Step 3:** Commit

**Verification:** 95 tests pass + learning DB 有新記錄

---

### Task 4: 更新文件

**Objective:** heartbeat proposal Phase 4 標記完成

**Files:**
- Modify: `~/managed-agents-research/reports/2026-05-14-hermes-heartbeat-project-proposal.md`

**Step 1:** Patch STATUS block: Phase 4 → ✅
**Step 2:** Git commit + push

**Verification:** `grep "Phase 4.*✅" proposal.md` 有結果

---

## Self-Critique

**漏洞 1：** extract_learning.py 可能沒有 `--sessions` 參數——這是計劃假設的 CLI 介面，但實際 API 可能是完全不同的簽名。

→ **對策：** Task 1 Step 1 先讀 extract_learning.py 確認介面。如果 CLI 不同，改設計——可能改用 Python import 直接呼叫，而非 subprocess。

**漏洞 2：** log_rotation 的 `stat -c %X`（atime）在掛載了 `noatime` 的檔案系統上永遠不動，導致 rotation 永遠不刪任何檔案。

→ **對策：** fallback 機制：若 atime 檢查後沒刪除任何檔案且 log 總數 > 1000 個，改用 mtime + 60 天保護期直接清理（保守但有效）。

**漏洞 3：** cognition_cycle.sh 如果被兩次 cron 重疊觸發，learning trigger 可能同時執行兩個 extract_learning.py，造成 DB lock contention。

→ **對策：** 用 flock 保護 critical section：`flock -n /tmp/heartbeat_learning.lock` 確保同時只有一個 extract_learning 在跑。如果 lock 失敗就跳過本輪（不阻塞）。
