# 研究報告：基於檔案交換的 Agent 協調機制

**日期：** 2026-05-20
**類型：** 技術深度研究
**產出：** Hestia 自行研究撰寫

---

## 一、檔案協調模式的生態

### 為什麼還需要檔案交換？

不是所有 agent 協調都需要網路即時通訊。對於：
- 跨 session 的非同步任務（如睡前派的任務早上回報）
- 網路不穩定的環境
- 需要完整審計軌跡的合規場景
- 離線協作

檔案交換是更實際的選擇。

---

## 二、主要開源實作案例

### MCP Agent Mail（Stars 1700+，Rust + Python）

這是目前最完整的開源檔案協調方案。

**核心機制：Advisory File Reservations**

```
# 宣告我要編輯這個檔
file_reservation_paths=["src/main.rs", "docs/guide.md"]

# 其他 agent 看到這個 reservation
# 可以選擇等待或繞過
```

Advisory（建議式）而非強制——好處是不會因為一個 agent 掛掉就鎖死全部流程。TTL 過期後其他 agent 可搶佔。

**訊息系統：Inbox/Outbox**

每個 agent 有自己的 inbox 目錄，訊息透過 `send_message()` 寫入目標的 inbox。訊息格式：

```json
{
  "id": "msg_abc123",
  "from": "green_castle",
  "to": "blue_fortress",
  "subject": "Task #45 completed",
  "body": "Fixed the authentication bug",
  "thread": "task_45",
  "timestamp": "2026-05-20T08:00:00Z"
}
```

**Git Archive**

所有訊息 commit 到 git——歷史可查，不消耗任何 context token。

**Pre-commit Hook**

進 commit 前檢查是否有未解蓋的 reservations，減少衝突。

---

### Swarm-MCP（共享 SQLite 模式）

不同於 MCP Agent Mail 的檔案模式，Swarm-MCP 用 SQLite 作為協調中心。

**資料庫結構：**
- `instance_registry` — 追蹤每個 agent 的上線狀態
- `tasks` — 狀態機：open → claimed → in_progress → done / failed / cancelled
- `messages` — 1 小時 TTL 的訊息
- `locks` — 檔案鎖

**Heartbeat 机制：**
- 每 10 秒 heartbeat 延長 lock TTL
- 30 秒無 heartbeat → stale marker
- 60 秒無 heartbeat → offline reclaim

**Task DAG：**

```json
{
  "task_id": "build_docs",
  "depends_on": ["setup_env", "fetch_deps"],
  "idempotency_key": "build_docs_v2"
}
```

---

### Fleet（Git-Based Task Board）

Fleet 的設計最接近人類的 task board，但全部由 agent 操作。

**目錄結構：**
```
.fleet/tasks/
  drafts/        # 未規劃
  available/     # 可領取
  in_progress/   # 已 claim（含 lock）
  in_review/     # 等待審查
  completed/     # 已完成
```

**協調方式：**
1. Agent `fleet claim <task-id>` → 移動到 `in_progress/` + 建立 lock
2. 完成後 `fleet submit` → 移動到 `in_review/`
3. Reviewer agent `fleet approve` 或 `fleet reject`
4. `fleet close` → merge 到 main branch

**完全基於 git**——不需要任何額外服務，但需要處理 branch merge 衝突。

---

## 三、檔案鎖策略的完整光譜

### 悲觀鎖（Pessimistic Locking）

作業前先拿到鎖，其他人一律等待。

代表：CoordinationHub
- TTL-based locks
- Region-level locking（同一檔案不同區塊可同時鎖）
- Boundary detection（跨區鎖定時警告）

缺點：如果拿到鎖的 agent 掛了，要等 TTL 過期才能釋放。

---

### 樂觀鎖（Optimistic Locking）

作業時不鎖，提交時檢查有沒有被別人改過。

代表：MCP Agent Mail、Preclaim
- Advisory reservations
- 提交前檢查衝突
- 衝突時回滾或 merge

好處是不會因為鎖浪費等待時間，壞處是 conflict 發生時的處理複雜。

---

### TTL + Heartbeat 自動釋放

幾乎所有檔案鎖機制都有這個：

```
Lock 建立時刻: T=0, TTL=30min
Heartbeat: 每 60s 延長 TTL
Agent 正常結束: 立即釋放
Agent  crash: TTL 到期自動釋放
```

---

## 四、Git-Based 協調的模式分析

### 模式 A：Git as Message Bus（Wolf Coordination Protocol）

所有 agent 對一個專用的 `switchboard` repo 進行 commit/push/pull。

**訊息格式：**
```json
{
  "type": "message",
  "from": "hermes_hestia",
  "to": "hermes_talos",
  "content": "Task #12 done"
}
```

把這個 JSON 當作一個 commit message 的一部分，因為結構設計上不可能有 merge conflict（每個 agent 只寫自己的訊息）。

**優點：** 無衝突風險、審計軌跡完整、可離線
**缺點：** 需要 git push/pull 輪詢，延遲以分鐘計

---

### 模式 B：Shared Working Directory（MCP Agent Mail）

所有 agent 工作在同一 repo，直接編輯檔案。用 advisory reservation + pre-commit hook 避免災難。

**優點：** 即時、簡單
**缺點：** 衝突還是可能發生

---

### 模式 C：Worktree-per-Task（Fleet）

每個任務一個獨立 worktree + branch，最終 merge 回 main。

**優點：** 完全隔離
**缺點：** Merge 複雜度極高，跨 task 的協調困難

---

## 五、對 Hermes 的建議

### 馬上可以做的（TRIVIAL）

**在 INBOX.md 基礎上加 advisory reservation：**

```bash
# 在 ~/.hermes/inbox/ 下
.reservations/
  hestia.main.2026-05-20.md.lock   # hestia 正在寫入 inbox/main.md
  talos.tasks.2026-05-20.md.lock   # talos 正在寫入 inbox/tasks.md
```

Lock 檔內容：
```
agent: hestia
file: inbox/main.md
created: 2026-05-20T08:00:00Z
ttl: 300  # 5 分鐘
```

其他 agent 啟動時檢查 `.reservations/`，如果看到針對同一檔案的 lock，就先 skip 或等。

---

### 值得考慮的（MODERATE）

**Git Archive 訊息：**

把每條 INBOX 訊息也 commit 進 git。這樣歷史訊息完全不佔 context，而且整個通訊有審計軌跡。

```bash
# 每次發訊息時
git add inbox/*.md
git commit -m "inbox: message from hestia at $(date -Iseconds)"
git push
```

---

### 不建議現在做的（HARD）

**建完整的 Task DAG + SQLite 協調中心**

Swarm-MCP 的模式很完整，但這是 40+ 小時的工程。必須先確認：
1. 真的有多個 Hermes instance 要同時跑
2. task 真的有複雜的依賴關係
3. INBOX.md 模式真的不夠用

在此之前，advisory lock + git archive 足夠應付 80% 的場景。

---

## 六、限制與誠實評估

**檔案交換的核心限制：**

1. **延遲以分鐘計** — 取決於 git push/pull 頻率，不適合需要秒級反應的場景
2. **衝突檢測是事後補救** — advisory lock 只能減少衝突機率，無法杜絕
3. **多機器的網路耦合** — 如果某台機器網路中斷，它的工作進度可能會在 git 上落後

**但反過來說：**

多數 Hermes 的使用場景（daily cron、隔夜任務、隔離的開發 session）本來就不需要秒級協調。INBOX.md + 適度的 lock 機制，已經涵蓋了 90% 的真實需求。

---

## 參考來源

- MCP Agent Mail: https://github.com/Dicklesworthstone/mcp_agent_mail_rust
- Swarm-MCP: https://github.com/Volpestyle/swarm-mcp
- pi-agent-mail: https://github.com/burningportra/pi-agent-mail
- Fleet: https://github.com/danrex/fleet
- CoordinationHub: https://github.com/IronAdamant/coordinationhub
- Wolf Coordination Protocol: https://github.com/Nice-Wolf-Studio/wolf-coordination-protocol