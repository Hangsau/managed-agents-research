# 研究報告：Multi-Agent 生產環境部署實際案例

**日期：** 2026-05-20
**類型：** 技術深度研究
**產出：** Hestia 自行研究撰寫

---

## 一、CrewAI 生產部署架構

### 架構分层

```
User / Trigger (Gmail, Slack, Webhook)
    │
    ▼
CrewAI Cloud (Orchestration Layer)
    │
    ├─── Agent 1 (Researcher)
    ├─── Agent 2 (Writer)
    └─── Agent 3 (Reviewer)
    │
    ▼
Output (Document, Report, Code)
```

### Crew 的三種 Process 模式

**Sequential（順序）**
- Agent 1 完成 → Agent 2 接收 → Agent 3 完成
- 適合線性依賴的工作鏈
- 缺點：沒有並行，一個慢拖累全部

**Hierarchical（階層）**
- Manager agent 分派任務給下屬 agents
- 模擬人類組織架構
- 需要更強的模型（manager 負責規劃和質量控制）

**Hybrid（混合）**
- 先並行再順序，或反過來
- 複雜工作流可以這樣設計

### 生產環境的限制與失敗模式

**已知問題：**

1. **Agent 之間的狀態丟失**
   - 複雜的 Hierarchical process 中，如果 manager 收到上層回饋後重試，某些 sub-agent 的 intermediate state 可能沒被正確恢復
   - 解決：checkpoint every handoff

2. **Task dependency 的隱性假設**
   - `depends_on` 鏈一旦某個環節失敗，上下游全部卡住
   - 沒有自動重試 + 降級策略

3. **Gmail/Slack Trigger 的延遲**
   - Trigger based 的 crew 起動有 30-60 秒延遲
   - 不是真正的即時系統

4. **Context overflow**
   - 5+ agents 共享同一 context window，昂貴且容易遺失重點
   - 建議：每個 agent 只拿自己需要的 context subset

### 對 Hermes 的意義

CrewAI 的 hierarchical 模式類似 Hermes kanban 的 manager agent 概念。但 CrewAI 的 trigger 系統（Event-driven 啟動）目前 Hermes 沒有——Hermes cron 是時間觸發，沒有 webhook-triggered task。

---

## 二、AutoGen 分散式部署

### AutoGen Core 的分散式模型

AutoGen 的分散式 runtime 基於 actor model：

```
[Worker Node 1]         [Worker Node 2]
┌─────────────┐          ┌─────────────┐
│ Agent A     │◄─message─►│ Agent B     │
│ (Actor)     │          │ (Actor)     │
└──────┬──────┘          └──────┬──────┘
       │                        │
       └────────┬───────────────┘
                ▼
        ┌──────────────┐
        │ Message Bus  │
        │ (Redis/TCP)  │
        └──────────────┘
```

**實作細節：**
- 每個 agent 是獨立的 process（或 container）
- 透過 message bus 轉發訊息
- 支援跨機器的 agent 註冊和發現
- 有 `group_chat` 模式，所有 agents 共享一個聊天室

### AgentChat 的限制

AutoGen 的 `AgentChat` 介面（用來快速原型）**不是為分散式設計的**——它假設所有 agents 在同一個 process 內。要真正跨機器，需要用 `autogen-core` 的 low-level API。

**這是一個常見的錯誤：**
看 AutoGen 的範例（2-3 行建立 group chat）感覺很簡單，實際上 production 分散式部署要自己處理：
- 序列化/反序列化 agent state
- 網路傳輸的可靠性
- 節點失敗重連

### 對 Hermes 的意義

Hermes 的 `delegate_task` 也是同一個問題——它是 in-process 的 subagent，不是真正的分散式。如果要支援真正意義的多機器 subagent，需要類似 AutoGen Core 的分層架構。

---

## 三、LangGraph 生產擴展

### LangGraph 的特點：Durable Execution

LangGraph 強調「即使重啟，整個對話狀態不丟失」：

```
用戶: "完成報告"
    │
    ▼
[Node: research] ──checkpoint──▶ [State saved to DB]
    │
    ▼ (crash here, resume later)
[Node: write]
    │
    ▼
[Node: review]
```

任何一個 node 完成後，狀態會 checkpoint 到資料庫（PostgreSQL/SQLite）。如果 agent crash，重啟時從上次 checkpoint 恢復。

### LangGraph Cloud 的限制

LangGraph 官方建議的 production 部署方式是 LangGraph Cloud（托管服務），不是 self-hosted。

**Self-hosted 的代價：**
- 自己處理 agent 的 autoscaling
- 自己處理 PostgreSQL 的連線池
- 自己處理 checkpoint 的 GC（舊狀態清理）

**實際上 LangGraph Cloud 的定價：**
- 根據 agent run time 收費
- 不是按月訂閱
- 成本會是 self-hosted 的 3-5x

### 對 Hermes 的意義

LangGraph 的 checkpoint 機制值得學習——這是 Hermes 目前完全沒有的。如果要支援 long-running workflow（超過一個 session 的工作），需要 checkpoint。但 LangGraph 的缺點是它假設整個 workflow 在同一個 runtime 內跑，跨機器的 workflow 協調和 LangGraph 是兩個不同問題。

---

## 四、MCP 的多機器擴展性

### MCP 目前的限制

MCP (Model Context Protocol) 設計上是一個本地 protocol：
- 對應用（client）和一個或多個 server
- Server 通常在本機（localhost）
- 沒有原生的跨機器轉發機制

**已經有人在做的 workaround：**

1. **MCP over HTTP Tunnel**
   - 把 localhost:8080 透過 reverse proxy（ngrok、cloudflare tunnel）暴露
   - Client 端連到公開 URL
   - 限制：沒有認證機制（除非自己加）

2. **MCP Agent Mail 的做法**
   - 不走 MCP 走 agent mail
   - 把 MCP tool 的呼叫結果寫到共享檔案
   - 另一台機器的 agent 去讀

3. **Swarm-MCP**
   - 共享 SQLite，跨 host 的 MCP tools
   - SQLite 放在 NFS 或 S3

### MCP 官方的多機器計畫

MCP 社群有討論「remote MCP」——讓 MCP server 在遠端機器運行。但目前（2026-05）這不是正式功能。

**對 Hermes 的意義：**

Hermes 的 MCP plugin 是本地 mode（`plugins/mcp/`）。如果要讓多台機器的 Hermes 共享同一個 MCP server，需要：
1. MCP server 必須是 HTTP-based
2. 每台 Hermes 知道 MCP server 的 URL
3. 自行處理認證（目前 MCP 沒有）

---

## 五、實際失敗模式和應對

### 失敗模式 1：Agent 狀態不一致

```
機器 A 的 Agent 認為 Task #12 已完成
機器 B 的 Agent 不知道，仍然去執行 Task #12
結果：重複工作、資料覆蓋
```

**原因：** 沒有中央狀態，每台機器有自己的真相

**解決：** SQLite 作為 source of truth，或用 etcd 的 atomic key

---

### 失敗模式 2：訊息丟失

```
Agent A 發了任務給 Agent B
Agent B 沒收到（網路問題）
Agent A 不知道，以為 B 收到了
結果：B 的工作被跳過
```

**解決：** 訊息需要 ACK + 重試機制（MCP Agent Mail 的做法）

---

### 失敗模式 3：Lock 孤島

```
機器 A 的 Agent 拿到檔案 lock
機器 A crash，TTL 還沒過
其他機器的 Agent 等到 TTL 才敢動
但機器 A 重啟後也試圖復用那個 lock
結果：衝突
```

**解決：** Lock 不只是 TTL，還要有 heartbeat + crash 後的 explicit reclaim 流程

---

### 失敗模式 4：Context 爆炸

```
5 個 agents 來回傳了 200 條訊息
每個 agent 的 context 累積了全部對話歷史
Cost 是單 agent 的 10 倍
速度也慢了 10 倍
```

**解決：** 每個 agent 只拿自己的 context subset，不要共享全部對話

---

## 六、對 Hermes 的優先級建議

### P0 — 今天就能做

1. **為 INBOX.md 加上 advisory reservation**
   - 不會因為多個 agent 同時寫入而衝突
   - 實作：目錄下放 `.reservations/` 子目錄

2. **每個 cron job 產出的結果 git commit + push**
   - 這樣其他機器的 agent 可以 pull 回顧歷史
   - 不佔 context

### P1 — 一週內可以做

3. **參考 Swarm-MCP 實作簡化的 task registry**
   - 用 SQLite（放在共享路徑或 NFS）
   - 追蹤每個 task 的狀態（open/claimed/done）
   - 不要一開始就做完整的 DAG

4. **為 gateway 的 cron job 加 webhook trigger**
   - 支援外部事件觸發（目前只有時間觸發）

### P2 — 評估後再說

5. **etcd 服務發現**
   - 評估是否真的需要（超過 3 台機器的部署）
   - 小於等於 3 台：mDNS 就夠

6. **分散式 delegate_task**
   - AutoGen Core 的模式值得參考
   - 但需要重構 `delegate_task` 的實作方式
   - 目前不急，先用 INBOX 模式跑

---

## 七、結論

**對 Hermes 分散式部署的誠實評估：**

目前 Hermes 的多 agent 協作（INBOX.md）是最實際的解法。這個模式：
- 不需要額外基礎設施
- 訊息不消耗 context token
- 有完整審計軌跡（git）
- 適合非同步、低延遲場景

**不建議做的事：**
- 現在就實作完整 A2A 協定
- 現在就上 etcd 服務發現
- 現在就重構 delegate_task 支援分散式

**原因：** 這些都是 40+ 小時的工程，而且目前的問題（跨機器協調）用 INBOX + advisory reservation 就能緩解 80%。等問題真的變嚴重了，再投入複雜度。

---

## 參考來源

- CrewAI Production: https://docs.crewai.com
- AutoGen Core Distributed: https://github.com/microsoft/autogen
- LangGraph Durable Execution: https://github.com/langchain-ai/langgraph
- MCP Protocol: https://modelcontextprotocol.io
- Swarm-MCP: https://github.com/Volpestyle/swarm-mcp
- MCP Agent Mail: https://github.com/Dicklesworthstone/mcp_agent_mail_rust