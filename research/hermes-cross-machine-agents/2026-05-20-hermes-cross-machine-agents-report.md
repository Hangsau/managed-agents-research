# Hermes 跨機器 Agent 協作研究報告

**日期：** 2026-05-20
**產出：** Hestia 研究整理
**涵蓋範圍：** 現有通訊機制、檔案協調、生產案例分析、推薦行動方針

---

## 一、執行摘要

### 現況

Hermes 支援兩種多 agent 協作模式：

| 模式 | 延遲 | 適用場景 | 原生支援 |
|------|------|----------|----------|
| `delegate_task`（subagent 派生） | 同步，毫秒級 | 同機器分工、batch | ✅ |
| INBOX.md + git sync | 非同步，~15min | 跨機器、設計討論 | ❌ 社群建立 |

**核心限制：** Hermes 沒有原生的 agent-to-agent 網路通訊。跨機器溝通必須靠外部層（git、shared file）。

### 我們已有的對應實作

| 研究 Pattern | 我們現況 |
|-------------|---------|
| Inter-agent Messaging | ✅ mailbox v6（15s poll，直接 fork） |
| Task Board phase tracking | ✅ mailbox v6 task board |
| SKILL.md 便攜性 | ✅ Hermes 已在用 YAML frontmatter |
| Subagent delegation | ✅ `delegate_task`（max_spawn_depth=1） |
| File-based coordination | ✅ INBOX.md + git sync |
| Advisory file reservation | ❌ 尚未實作 |

### 結論（一句話）

INBOX.md + advisory reservation 是 Hermes 目前最實際的多機器方案，etcd/A2A/WebSocket 重構統統不需要。

---

## 二、通訊機制比較

### HTTP / REST

- **適合：** 相對靜態的任務派發（cron job 分發）
- **缺點：** 小訊息 overhead 高，agent 間即時協調太笨重
- **結論：** 不用

### WebSocket

- **適合：** 高頻率訊息交換、進度串流
- **缺點：** 狀態管理複雜，水平擴展需要 sticky session
- **結論：** Hermes gateway 目前用 HTTP Long Polling，若瓶頸明確再改

### MQTT

- **適合：** Pub/Sub 廣播型協調
- **缺點：** broker 是單點故障，需要額外維運
- **結論：** 超過 5 台機器才值得評估

### 檔案交換（File Exchange）

- **適合：** 跨 session 非同步任務、網路不穩環境、完整審計軌跡
- **缺點：** 無原生通知機制，有 race condition 風險
- **結論：** ✅ Hermes 現已使用 INBOX.md 模式

---

## 三、服務發現

| 方式 | 適用規模 | 結論 |
|------|----------|------|
| 靜態配置 | 2-3 台固定部署 | ✅ 今天就能做 |
| mDNS / Bonjour | 區網內，無 server | ⚠️ 不跨子網，機器多有 storm 風險 |
| etcd / Consul | 5+ 台，需自動化健康檢查 | ❌ 過度複雜 |

**結論：** 2-4 台用靜態配置寫在 `~/.hermes/config.yaml`。

---

## 四、主要開源實作案例

### MCP Agent Mail（Stars 1700+，Rust + Python）

**核心機制：Advisory File Reservations**

```json
{
  "file_reservation_paths": ["inbox/main.md"],
  "other_agents_see": "可選擇等待或繞過"
}
```

Advisory（建議式）而非強制——好處是不會因為一個 agent 掛掉就鎖死。TTL 過期後其他 agent 可搶佔。

**Git Archive**：所有訊息 commit 到 git，歷史可查，不消耗 context token。

### Swarm-MCP（共享 SQLite）

- `instance_registry` — 追蹤上線狀態
- `tasks` — open → claimed → in_progress → done/failed
- `locks` — 檔案鎖
- 每 10 秒 heartbeat 延長 lock TTL，60 秒無心跳 → offline reclaim

### Fleet（Git-Based Task Board）

完全基於 git 的 task board：

```
.fleet/tasks/
  drafts/       → available/ → in_progress/ → in_review/ → completed/
```

**結論：** Fleet 的目錄狀態機最接近我們的 mailbox task board 概念。

---

## 五、生產案例失敗模式

### 失敗模式 1：Agent 狀態不一致

機器 A 認為 Task #12 完成，機器 B 不知道，仍去執行。**解決：** SQLite 作為 source of truth。

### 失敗模式 2：訊息丟失

A 發了任務給 B，B 沒收到，A 不知道。**解決：** 訊息需要 ACK + 重試（MCP Agent Mail 的做法）。

### 失敗模式 3：Lock 孤島

拿到 lock 的 agent crash，TTL 還沒過，其他人都卡住。**解決：** heartbeat + crash 後的 explicit reclaim 流程。

### 失敗模式 4：Context 爆炸

5 個 agents 來回 200 條訊息，每個 agent context 累積全部歷史，cost 是單 agent 的 10 倍。**解決：** 每個 agent 只拿自己的 context subset。

---

## 六、推薦行動方針

### P0 — 今天就能做（TRIVIAL）

**INBOX.md + advisory reservation**

```bash
~/.hermes/inbox/
  .reservations/
    hestia.main.2026-05-20.md.lock
    talos.tasks.2026-05-20.md.lock
```

Lock 檔內容：
```
agent: hestia
file: inbox/main.md
created: 2026-05-20T08:00:00Z
ttl: 300  # 5 分鐘
```

其他 agent 啟動時檢查 `.reservations/`，看到同檔案的 lock 就先 skip 或等。

### P1 — 一週內可以（MODERATE）

**Git Archive 訊息**

每次 INBOX 訊息 commit 到 git，歷史完全不佔 context：
```bash
git add inbox/*.md
git commit -m "inbox: message from hestia at $(date -Iseconds)"
git push
```

### P2 — 評估後再說（HARD）

- **etcd 服務發現**：超過 5 台機器才值得投入
- **A2A 協定**：需要 40+ 小時工程，現在不用
- **WebSocket Gateway**：先看目前 Long Polling 真的是瓶頸嗎

---

## 七、不建議現在做的事

| 項目 | 原因 |
|------|------|
| WebSocket Gateway 重構 | HTTP Long Polling 目前夠用 |
| etcd 服務發現 | 2-4 台機器用靜態配置即可 |
| 完整 A2A 協定實作 | 40+ 小時工程，INBOX.md + advisory lock 緩解 80% 問題 |
| 分散式 delegate_task | AutoGen Core 模式值得參考，但目前不是瓶頸 |

---

## 八、參考來源

- MCP Agent Mail: https://github.com/Dicklesworthstone/mcp_agent_mail_rust
- Swarm-MCP: https://github.com/Volpestyle/swarm-mcp
- Fleet: https://github.com/danrex/fleet
- AutoGen Core: https://github.com/microsoft/autogen
- LangGraph: https://github.com/langchain-ai/langgraph
- CrewAI: https://github.com/crewAIInc/crewAI
- Microsoft Agent Framework: https://github.com/microsoft/agent-framework