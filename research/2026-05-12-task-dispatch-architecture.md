# Task Dispatch 架構深度研究：從 Queue 到 Resilience

**日期**：2026-05-12  
**研究員**：Hermes Agent  
**目標讀者**：Hang（Yeh Chengheng）  
**關聯專案**：managed-agents batch runner + firn task system

---

## 1. 我們在解什麼問題

### 背景

- **managed-agents** 剛完成 v2 batch runner：SQLite task queue + JSON playbook + 單線程 dispatcher。能跑 batch，但缺少 resilience 機制。
- **firn** 已有完整的 task system：TaskService + Dispatcher + Watchdog + phantom detection + heartbeat。但是**每個 task 都是一個獨立的 LLM session**，沒有劇本化 workflow。

### 核心問題

怎麼讓 agent 的 background task 跑得穩、可觀測、好調度，同時避免 LLM 特有的失敗模式（hallucination、無限迴圈、context 溢出）？

---

## 2. firn Task System 深度分析

先看已經做得好的部分。以下七個亮點，每個都是其他 framework （包括 managed-agents）欠缺的。

### 2.1 Atomic Claim 與 Race-Condition 防護

**怎麼運作**：SQLite `BEGIN IMMEDIATE` + `UPDATE ... WHERE status='pending' AND claim_lock IS NULL`，再檢查 `rowcount == 1`。  
**為什麼重要**：單機多進程或多個 agent instance 同時跑時，沒有 atomic claim 就會重複執行同一個 task。  
**對照**：managed-agents 的 `claim_next_pending()` 也用了 `BEGIN IMMEDIATE`，但沒有 claim_lock 欄位，只能單進程使用。

### 2.2 Heartbeat 與 Zombie Detection

**怎麼運作**：TaskAgent 每 turn 自動呼叫 `heartbeat()` 刷新 `last_heartbeat_at`。Watchdog 每 60 秒檢查，超過 5 分鐘沒心跳就標記為 zombie（`block_task` with `zombie_detected`）。  
**為什麼重要**：LLM API call 可能 hang、系統可能 OOM、agent 可能 crash。沒有 heartbeat 就沒有人知道任務是否還活著。  
**對照**：managed-agents 完全沒有 heartbeat。一旦 harness crash，running task 就是孤兒。

### 2.3 Phantom Task Detection

**怎麼運作**：雙重防線：  
1. **Task creation verification**：task 完成時聲稱創建了哪些 subtask，`TaskService` 會去 DB 驗證這些 task ID 是否真的存在且由自己創建。如果不是，抛 `HallucinatedTaskError`。  
2. **Prose reference scanning**：完成後的 summary 文字會被正則表達式掃描，找出裡面提到的 task ID 是否真實存在。  
**為什麼重要**：LLM 很容易虛構「我已經完成了 task_XYZ」或「我創建了三個 subtask」。沒有驗證，這些謊言就會被當成真的。  
**對照**：managed-agents 完全沒有。playbook 執行完就直接標 done，不驗證任何東西。

### 2.4 Depth Limit

**怎麼運作**：創建 subtask 時自動計算 depth，`max_depth=5`，超過就抛 `MaxTaskDepthExceeded`。  
**為什麼重要**：LLM 有無限遞迴的傾向。特別是免費模型，容易「這個 task 需要先完成那個 subtask，那個 subtask 又需要先...」進入死循環。  
**對照**：managed-agents 沒有。playbook 裡的 `task_create` tool 可以被無限呼叫。

### 2.5 Task Events Audit Log

**怎麼運作**：獨立的 `task_events` 表，記錄每個 task 的完整生命週期：created、claimed、completed、blocked、zombie_detected、hallucination。  
**為什麼重要**：debug 時能看到「task 為什麼變成 zombie」「完成時為什麼被 block」，而不是只有一個最終狀態。  
**對照**：managed-agents 只有 `status` 欄位，沒有 event log。

### 2.6 Blocked + Resume

**怎麼運作**：task 遇到問題時不是直接失敗，而是進入 `blocked` 狀態並記錄 `blocked_reason`。用戶可以後續用 `resume_task()` 恢復，也可以調整 `max_turns`。  
**為什麼重要**：agent task 的失敗通常是「需要人類確認」而不是「程式 bug」。直接標 failed 會擴失有價值的中間狀態。  
**對照**：managed-agents 有 `failed` 狀態但沒有 `blocked`，也沒有 resume。

### 2.7 Max Turns 限制

**怎麼運作**：每個 task 可以設 `max_turns`，TaskAgent 跑到上限就 `block_task(..., "max_turns_exceeded")`。  
**為什麼重要**：避免 LLM 進入無限循環或者「one tool call 反彩」。特別是免費 API 有 rate limit 和成本。  
**對照**：managed-agents 有 `max_turns` 但只是在 harness level，不是 per-task。

---

## 3. managed-agents Batch Runner 深度分析

### 3.1 亮點

**Playbook workflow** — JSON 定義的步驟化流程，讓免費模型不需要「規劃」，只需要「查表執行」。這是穩定性的關鍵。  
**SQLite queue** — 無外部依賴，簡單可靠。  
**Structured results** — 每個 session 的結果存成 JSON，方便彙整。

### 3.2 七個缺失（對照 firn）

| 缺失 | 後果 | firn 解法 |
|------|------|-----------|
| 無 heartbeat | task crash 後無人知晓 | 每 turn 自動 heartbeat + Watchdog |
| 無 zombie detection | DB 裢會有變成屍體的 running task | 5 分鐘沒心跳 → block |
| 無 phantom detection | LLM 可能虛構完成了不存在的 task | 雙重驗證 + HallucinatedTaskError |
| 無 depth limit | 無限遞迴 subtask | max_depth=5 |
| 無 event log | 調試時只有最終狀態 | task_events 實體表 |
| 無 blocked/resume | 中間狀態直接變 failed | blocked 狀態 + resume_task() |
| 無 timeout/retry | 一次失敗就結束 | 無（這點 firn 也沒有，見下文） |

---

## 4. 業界參考：為什麼不能直接把 Celery 搬過來

### 4.1 Temporal（Workflow Engine）

**Durable execution** — 每個 workflow step 都是持久化的，crash 後可以從上一個成功的 checkpoint 恢復。  
**Activity retry** — 失敗時自動重試，有 exponential backoff。  
**為什麼不直接用**：Temporal 需要跑一個 server，設定複雜。我們要的是「單機 SQLite 、無外部依賴」。

### 4.2 Celery（Python Task Queue）

**Broker + Worker + Result backend** — Redis/RabbitMQ 做 broker，worker 分散執行。  
**Task routing** — 根據 task 類型送到不同 queue。  
**Chords/Groups** — 並行執行 + 匯總。  
**為什麼不直接用**：Celery 是為「確定性任務」設計的（像發郵件、處理圖片）。Agent task 是「非確定性、非結束性、可能 hallucinate」的，Celery 沒有這些概念。

### 4.3 BullMQ（Node.js）

**Redis-based** — 快速但需要 Redis。  
**Priority + Rate limiting + Repeatable jobs** — 高級調度功能。  
**為什麼不直接用**：語言不同（Node.js），而且同樣缺少 agent-native 概念。

### 4.4 關鍵結論

業界 task queue 都是為「程式任務」設計的。Agent task 需要額外的：  
- **Hallucination guard** — 驗證 LLM 聲稱的東西  
- **Token budget** — 每個 task 有成本  
- **Context window 管理** — task 之間怎麼傳遟資訊  
- **Non-deterministic checkpoint** — LLM 的輸出不可複製，不能像 Temporal 那樣從 checkpoint 恢復

**我們需要的是「agent-native task queue」，不是「起來的 Celery」。**

---

## 5. Agent-Native Task Dispatch 的關鍵差異

以下五個是普通 task queue 沒有、但 agent task 必須有的：

### 5.1 Hallucination Guard（已在 firn）

LLM 會偷工減料、虛構數據、虛構 task ID。Task system 必須把「驗證」當成第一等公民，不是可選功能。

### 5.2 Token Budget 管理（部分在 firn）

firn 有 `max_turns`，但沒有 `max_tokens` 或 `cost_limit`。一個 task 可能只跑了 3 turns，但每 turn 都調用 Claude Opus，花費 $5。需要總體 token/cost tracking。

### 5.3 Context Window 管理（兩邊都缺）

Task A 研究了某個主題，Task B 想繼續。怎麼讓 B 讀到 A 的發現？  
- firn: 沒有 cross-task memory。只能靠 `memory_update` 寫入 blocks，但 blocks 是文字，不是結構化數據。  
- managed-agents: `/tmp/batch_results/*.json` 是結構化的，但沒有機制讓後續 task 自動讀取。

### 5.4 Checkpoint/Resume（兩邊都缺）

Temporal 的 checkpoint 是「確定性的」，因為每個 step 的輸入輸出都是確定的。  
Agent task 的 checkpoint 是「概率性的」：從某個 turn 恢復，LLM 可能給不同的答案。  
**不能做到真正的 checkpoint，只能做「最佳努力 resume」**：記錄到哪個 step、前幾個 tool result 是什麼、然後重新發送。

### 5.5 Observability（部分在 firn）

firn 有 `task_events` + `turns` 表，可以追溯「這個 task 為什麼變成 zombie」。  
managed-agents 只有 stdout + session events，沒有統一的 task-level observability。

---

## 6. 具體建議

### 6.1 對 managed-agents（短期，1–2 天）

| 優先級 | 工作 | 原因 | 參考來源 |
|--------|------|------|---------|
| P0 | 移植 heartbeat + zombie detection | 避免 task crash 後無人知晓 | firn `watchdog.py` |
| P0 | 移植 phantom detection | 避免 LLM 虛構 playbook step 完成 | firn `service.py: _verify_created_tasks` |
| P1 | 每個 step 加 timeout | playbook step 可能 hang 在 web_search 或 bash | 無，新功能 |
| P1 | 每個 step 加 retry | 網路不穩定時可以重試 | Celery retry |
| P1 | 加 task events 表 | 調試和可觀測性 | firn `task_events` 表 |
| P2 | 加 depth limit | 防止無限遞迴 subtask | firn `max_depth` |
| P2 | 加 blocked 狀態 + resume | 中間狀態不要直接變 failed | firn `block_task/resume_task` |

### 6.2 對 firn（短期，1–2 天）

| 優先級 | 工作 | 原因 | 參考來源 |
|--------|------|------|---------|
| P0 | 加 playbook/workflow | 免費模型的 task 規劃能力不穩，需要劇本化執行 | managed-agents `playbook.py` |
| P1 | 加 batch submit API | 一次發 5 個相關 task | managed-agents `submit_batch()` |
| P1 | 加 structured result | 現在只有 summary string，需要 JSON schema | managed-agents `results/*.json` |
| P2 | 加 cross-task memory | Task A 的發現怎麼讓 Task B 讀到 | 無，新概念 |

### 6.3 對兩邊（中期，1週）

| 優先級 | 工作 | 原因 |
|--------|------|------|
| P1 | Token/Cost tracking per task | 免費 API 也有 rate limit，需要管理 |
| P2 | Task result digest + injection | 把完成的 task result 摘要後注入新 task 的 prompt |
| P2 | Priority queue + routing | urgent task vs daily housekeeping |

---

## 7. 今天可以做的一件事

**選項 A：managed-agents 移植 heartbeat + watchdog**

工作量：約2 小時  
步驟：
1. `db.py` 加 `last_heartbeat_at` 欄位 + `get_zombie_tasks()`
2. `turn_loop.py` 每 turn 自動 heartbeat
3. 新增 `watchdog.py`：每 60 秒檢查，5 分鐘沒心跳 → block
4. 修改 `harness_v2.py` 啟動 watchdog thread

**選項 B：firn 設計 playbook schema**

工作量：約1 小時  
步驟：
1. 參考 managed-agents `playbook.py` 的 JSON schema
2. 設計 firn 版本（支持 steps + vars + conditions + timeout + retry）
3. 加到 `tools/schemas/playbook.py` 做為 LLM 可使用的 tool
4. 寫一個簡單的 `playbook_runner.py` 處理 JSON workflow

**建議**：先做 A，因為 managed-agents 是當前主動開發的專案，而且 heartbeat 是「有就沒有」的差別。

---

## 8. 附錄：技術細節快速參考

### firn heartbeat 流程

```python
# TaskAgent.run() 每 turn 自動：
self._task_service.heartbeat(task.id)

# WatchdogService.run() 每 60s：
cutoff = time.time() - 300  # 5min
zombies = self._tasks.get_zombie_tasks(cutoff)
for task in zombies:
    self._tasks.block_task(task.id, "zombie_detected: no heartbeat for 5 minutes")
```

### firn phantom detection 流程

```python
# 完成 task 時：
verified, phantom = _verify_created_tasks(conn, task_id, created_tasks)
if phantom:
    raise HallucinatedTaskError(phantom, task_id)

# summary 文字中的 task ID references：
phantom_refs = _scan_prose_for_phantom_ids(conn, summary)
```

### managed-agents 現有 queue schema

```sql
CREATE TABLE task_queue (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    playbook TEXT NOT NULL,
    vars TEXT,
    status TEXT DEFAULT 'pending',
    result_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
```

---

*報告由 Hermes Agent 產生 | 資料來源：firn source code、managed-agents source code、Temporal/Celery/BullMQ 文件*
