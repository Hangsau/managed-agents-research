# 研究報告：多機器 Hermes Agent 跨機器通訊機制

**日期：** 2026-05-20
**類型：** 技術深度研究
**產出：** Hestia 自行研究撰寫（非 subagent）

---

## 一、現有通訊協定的比較

### HTTP/REST

最常見的跨機器溝通方式。Agent 之間透過 HTTP POST/GET 交換 JSON 訊息。

**優點：**
- 防火牆友善（port 80/443）
- 生態完整：API gateway、reverse proxy、auth middleware 直接可用
- 水平擴展容易（load balancer）
- 高度標準化，debug 工具成熟

**缺點：**
- 小訊息 Overhead 高（TCP handshake + HTTP headers）
- 無法原生 push，需 polling 或升級 WebSocket
- 不適合高頻率 agent 訊息交換

**對 Hermes 的意義：** 適合相對靜態的任務派發（如 cron job 分發），但 agent 間即時協調的話太笨重。

---

### WebSocket

雙向、低延遲的持久連接。Agent 維持長連接，雙方隨時可發訊息。

**優點：**
- 雙向、持久、低延遲
- 原生支援串流（streaming），適合 agent 進度回報
- 高頻率訊息交換效率高

**缺點：**
- 有狀態——連接管理複雜
- 水平擴展需要 sticky session
- Proxy/firewall 環境中可能卡住

**對 Hermes 的意義：** 目前 Hermes 的 gateway 用 HTTP Long Polling 模擬 push，換成 WebSocket 可以大幅降低延遲。但狀態管理是新的複雜度。

---

### MQTT

Pub/Sub 模式，通過 broker 轉發訊息。Topics 邏輯分組，支援 QoS 等級。

**優點：**
- Pub/Sub 天然適合廣播型 agent 協調
- 輕量、低頻寬，網路不稳定也能跑
- QoS 等級提供 delivery guarantee

**缺點：**
- Broker 是單點故障，需要叢集
- 不適合 request/response 模式
- 需要維護額外基礎設施

**對 Hermes 的意義：** 如果要做到「某一個 agent 完成後通知其他 agent」，MQTT 很合適。但多了 broker = 多了失敗點。

---

### 檔案交換（File Exchange）

Agent 之間不通訊，透過共享儲存（NFS、S3、git push/pull）交換檔案。

**優點：**
- 極簡，不需要任何網路通訊
- 天然解耦——agent 可離線作業
- 審計軌跡完整（寫入的檔案）

**缺點：**
- 延遲高，不即時
- 無外部協調會有 race condition
- 新檔案到來沒有原生的通知機制

**對 Hermes 的意義：** Hermes 目前的 INBOX.md 模式就是這種。解決了「有沒有」問題，但缺乏檔案鎖、衝突檢測、狀態追蹤。

---

## 二、服務發現：如何讓機器知道彼此

### 靜態配置（Static Config）

最簡單——寫死 IP 或域名。

```
hermes:
  agents:
    - name: hestia
      url: http://192.168.1.10:8000
    - name: talos
      url: http://192.168.1.11:8000
```

**適用場景：** 2-3 台機器的固定部署。人會幫你更新。

---

### mDNS / Bonjour

區域網路內自動發現。不需要伺服器，機器廣播自己的服務。

```
# mDNS 廣播格式
_hermes._tcp.local.
```

**適用場景：** 辦公室內的小機房實驗室環境。缺點是 broadcast 無法跨子網，機器多了有 broadcast storm 風險。

---

### Consul / etcd

服務發現 + 健康檢查 + KV store。機器註冊自己，其他機器查詢。

Consul 特色：
- 健康檢查（HTTP TCP Script）
- DNS 介面（`agent.service.consul`）
- Multi-datacenter 支援

etcd 特色：
- Raft 共識，強一致性
- Kubernetes 原生，社群大

**對 Hermes 的意義：** 如果要擴展到 5+ 台機器而且要自動化健康檢查，etcd 是實際的選擇代價。Consul 更重但功能更完整。

---

### 混合模式（實際案例）

多數 production 系統用：啟動時靜態配置 + DNS 解析 + 服務網格（service mesh）處理流量。

---

## 三、主流 Framework 的分散式實作

### AutoGen (Microsoft) — Actor Model

AutoGen 的 `autogen-core` 用 Actor model + 事件驅動 runtime。每個 agent 是一個 actor，透過 message passing 溝通。

```
Agent A (Actor) ──message──▶ Agent B (Actor)
     │                           │
     └──event───▶ Distributed Runtime ◀──event──┘
```

- 可跨機器擴展（distributed runtime）
- `AgentChat` layer 建立在 Core API 之上，開發簡單
- 支援 group chat、human-in-the-loop

**對 Hermes 的啟示：** Hermes 的 `delegate_task` 是同步、單層的。AutoGen 的分層架構（Core / AgentChat）值得參考。

---

### Microsoft Agent Framework (MAF) — A2A + MCP

MAF 定義了兩個協定：
- **A2A (Agent-to-Agent)**：Agent 之間的溝通
- **MCP (Model Context Protocol)**：Tool / Resource 存取

特點：
- 多語言支援（Python + .NET）
- Graph-based workflows
- Checkpoint + Streaming + OpenTelemetry 內建
- 有 time-travel debugging

**對 Hermes 的啟示：** MCP 已經在 Hermes 中實作了（`plugins/mcp/`），但 A2A 完全沒有。如果要讓多個 Hermes instance 直接通訊，需要 A2A 或類似的協定層。

---

### LangGraph — Graph State Machine

基於 Google Pregel + Apache Beam 的 graph-based state machine。

- Node = agent 或 task
- Edge = 狀態轉換
- Checkpointing 持久化長期 workflow
- 人類可隨時中斷（human-in-the-loop interrupt）

**對 Hermes 的啟示：** Hermes 的 cron/job 系統目前是 stateless 的。如果要做到 long-running workflow recovery，LangGraph 的 checkpoint 模式是參考方向。

---

### CrewAI — Crew / Task Hierarchy

```
Crew (團隊)
  ├── Agent A (with tools, memory, knowledge)
  ├── Agent B
  └── Task 1, Task 2, ...
  
Process: Sequential / Hierarchical / Hybrid
```

- Hierarchical 模式：會有一個 manager agent 分派任務
- Triggers 整合（Gmail、Slack、Salesforce）
- Enterprise 有 RBAC 和環境管理

**對 Hermes 的啟示：** Hermes 的 kanban plugin 有類似結構，但沒有 crewAI 的 trigger 系統（Event-driven 啟動）。

---

### smolagents (HuggingFace) — Code-First

Agent 寫程式碼作為 action，在 sandboxed 環境執行（Docker、E2B、Modal、Pyodide）。

- Model-agnostic
- Hub 分享 agents/tools
- 適合有多種 model provider 的環境

**對 Hermes 的啟示：** smolagents 的 sandbox 概念對安全隔離很有價值。Hermes 目前 terminal tool 沒隔離，全域執行。

---

## 四、對 Hermes 的具體建議

### 短期（已有能力，可立即做）

1. **強化 INBOX.md 協定向**
   - 加入 advisory file reservation（MCP Agent Mail 模式）
   - 加入訊息 thread 結構（inbox/outbox）
   - Git archive 儲存歷史訊息（節省 context token）

2. **讓 cron job 支援多機器**
   - 目前 cron job 是本地單機
   - 改為：dispatcher 派到有可用容量的機器執行

### 中期（需要架構調整）

3. **實作簡易 A2A 協定**
   - 每個 Hermes instance 暴露一個 `/a2a/` HTTP endpoint
   - 訊息格式：JSON（sender, receiver, payload, thread_id）
   - 用 git commit hash 作為 message ID，天然的去重

4. **服務發現**
   - 2-4 台機器：mDNS（零設定）
   - 5+ 台機器：etcd（值得投入）

### 長期（可選）

5. **WebSocket Gateway**
   - 將 gateway 的 HTTP Long Polling 改為 WebSocket
   - 大幅降低訊息延遲
   - 需要處理連接狀態和重連

---

## 五、限制與誠實評估

1. **「多機器協調」在 Hermes 目前的使用者案例中並非瓶頸。** 大多數使用者在單機單 agent 模式。如果還沒實際遇到跨機器協調的需求，現在投入是過度工程化。

2. **真實的多機器 agent 協作目前沒有標準答案。** 即使是 AutoGen、LangGraph 這類成熟框架，分散式協調仍屬於「能用但不優雅」的階段。投入資源之前，建議先用 INBOX.md + git 模式應付半年再看需求。

3. **mDNS 不適合跨越網段。** 如果 Hestia 和 Talos 在不同網路，mDNS 失效。這是為什麼 INBOX.md + git sync 是目前最實際的跨機器方案。

---

## 六、結論

**今天可以做的事（TRIVIAL）：**

強化 INBOX.md 模式——加入 advisory reservation，避免兩個 agent 同時寫入同一檔案。實作方式：在 INBOX.md 同目錄放 `.reservations/` 子目錄，agent 寫入前先在該目錄建立一個 `.{agent}.{file}.lock` 檔案，內容含 timestamp + TTL。

**不建議現在做的（HARD）：**
- WebSocket Gateway 重構
- etcd 服務發現
- A2A 協定完整實作

這些需要 40+ 小時工程投入，而目前的問題（INBOX.md 偶爾衝突）用 advisory lock 就能緩解。

---

## 參考來源

- AutoGen Core Architecture: https://github.com/microsoft/autogen
- Microsoft Agent Framework: https://github.com/microsoft/agent-framework
- LangGraph: https://github.com/langchain-ai/langgraph
- CrewAI: https://github.com/crewAIInc/crewAI
- smolagents: https://github.com/huggingface/smolagents
- MCP Agent Mail (file coordination): https://github.com/Dicklesworthstone/mcp_agent_mail_rust