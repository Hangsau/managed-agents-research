# 研究報告：A2A Protocol — 從「單體 Agent」到「可互通 Agent 互聯網」的標準化躍遷 (2026)

**日期**：2026-06-14
**來源數**：11 | **標籤**：#a2a #multi-agent #interoperability #agent-protocol #agent-discovery

---

## 1. The Problem

過去 18 個月，整個 AI agent 生態系把心力放在兩件事：

1. **MCP（Model Context Protocol）**——讓 agent 標準化地接工具、接資源（已大致 2025 H2 收斂）
2. **Agent orchestration**——在一個 process 內用 CrewAI / LangGraph / ADK 編排多個 specialist agent（已大致 2025 全年收斂）

但**剩下沒人解的洞**是：**跨 framework、跨 vendor、跨組織**的 agent 之間怎麼講話？

實際例子：Hang 想把 firn 寫的私人研究助手，跟朋友用 LangGraph 寫的選股 agent，跟公司用的 SAP Joule 串起來。目前唯一的方法是把大家都「包成 MCP tool」，但這有兩個致命缺點：

- **每包一次就掉一次語意**。MCP tool 假設呼叫者是「需要結果的函式」，但 agent 之間是「需要對話、需要協商、需要長期 context」的對等體。把 agent 降級成 tool = 把對話方降級成 function call = 失去協商能力（你沒辦法叫一個 function「先問我三個澄清問題再回」）。
- **沒有 opaque 設計**。MCP 把工具的 schema 攤開，這對資料查詢很 OK，但對「想保護自己 prompt / 工具鏈 / 商業邏輯」的 agent 是災難。

這個洞催生了 **A2A (Agent2Agent) Protocol**——Google 在 2025 H2 推出，2026-03 進入 v1.0，現已 24,279 GitHub stars、`a2a-sdk` PyPI 月下載量推測超過 100K（rate-limited 抓不到精確值，但 ecosystem 已成形）。**它不是要取代 MCP，而是補 MCP 的對偶缺點**：

- **MCP 解決「agent ↔ tool」**（垂直整合）
- **A2A 解決「agent ↔ agent」**（水平互通）

**誰在用？** 50+ 企業（Salesforce、SAP、Atlassian、Workday、MongoDB、Box…），5+ 主流 framework 原生整合（Google ADK、LangGraph、CrewAI、Semantic Kernel、BeeAI）。連 OpenClaw 都出了 `openclaw-a2a-gateway` plugin（520 stars）。

**為什麼 2026 突然重要？** 三個事件同時收斂：
1. **2026-05-20 HBHC paper**（Heartbeat-Bound Hierarchical Credentials）—— 解決 sub-agent swarms 的「zombie credential」問題，是 A2A 在 enterprise 上路的最後一塊拼圖
2. **2026-05-28 A2X paper**（Agent-to-Anything service discovery）—— 解決 agent 數量爆炸後「找不到合適 agent」的 context 過載問題
3. **2026-06-10 a2a-x402**（google-agentic-commerce）—— 加上 on-chain 支付擴充，agent 經濟正式啟動

**A2A 已經不是研究題目，是部署題目。** 對 firn 來說，問題是「我們要當 A2A client、A2A server、還是兩者都是」。

---

## 2. Core Mechanism

A2A v1.0 的設計**不是「發明新概念」，是把已成熟的 web 標準拼起來**。三層架構（spec §1.3）：

```
┌─────────────────────────────────────────────┐
│ L1: Canonical Data Model (Protocol Buffers) │
│    Task / Message / Part / Artifact /       │
│    AgentCard / Extension                    │
├─────────────────────────────────────────────┤
│ L2: Abstract Operations (transport-agnostic)│
│    SendMessage / SendStreamingMessage /      │
│    GetTask / ListTasks / CancelTask /       │
│    SubscribeToTask / PushNotification CRUD /│
│    GetExtendedAgentCard                     │
├─────────────────────────────────────────────┤
│ L3: Protocol Bindings (3 官方 + 自訂)       │
│    JSON-RPC 2.0 / gRPC / HTTP+JSON-RPC /    │
│    Custom Binding (WSS, MQTT, ...)           │
└─────────────────────────────────────────────┘
```

### 2.1 核心物件（§4 Data Model）

| 物件 | 用途 | 為什麼這樣設計 |
|------|------|---------------|
| **Task** | 一個有 state 的工作單元（`submitted` / `working` / `input-required` / `completed` / `failed` / `canceled`） | 對應到「跨小時、跨天的協作」——不能只靠 HTTP request/response |
| **Message** | 一輪對話（`role=user\|agent`，含一個或多個 Part） | 多輪 + multi-turn 對話的基本單位 |
| **Part** | 訊息 / 成品的基本內容容器，三種 kind：`text` / `file` / `data`（structured） | 模態中立，支援純文字 / 檔案 / JSON 結構化資料 |
| **Artifact** | Task 完成後的具體產出（PDF、圖片、JSON、程式碼） | 區分「對話過程」和「最終交付」 |
| **AgentCard** | JSON 自我描述，公開在 `/.well-known/agent.json` | 對等於 `package.json`——讓 client 知道「你是誰、能做什麼、要怎麼認證」 |
| **ContextId** | 跨多輪 Task 共用的對話脈絡識別 | 讓「同一個用戶的同個話題」可以跨越多個 Task |

### 2.2 AgentCard 範例（spec §8.5 完整版）

```json
{
  "name": "GeoSpatial Route Planner Agent",
  "description": "Provides advanced route planning, traffic analysis, and custom map generation.",
  "supportedInterfaces": [
    {"url": "https://georoute-agent.example.com/a2a/v1", "protocolBinding": "JSONRPC", "protocolVersion": "1.0"},
    {"url": "https://georoute-agent.example.com/a2a/grpc", "protocolBinding": "GRPC",  "protocolVersion": "1.0"}
  ],
  "provider": {"organization": "Example Geo Services Inc.", "url": "https://www.examplegeoservices.com"},
  "iconUrl": "https://georoute-agent.example.com/icon.png",
  "version": "1.2.0",
  "capabilities": {
    "streaming": true,
    "pushNotifications": true,
    "extendedAgentCard": true
  },
  "securitySchemes": {
    "google": {"openIdConnectSecurityScheme": {"openIdConnectUrl": "https://accounts.google.com/.well-known/openid-configuration"}}
  },
  "security": [{"google": ["openid", "profile", "email"]}],
  "defaultInputModes": ["application/json", "text/plain"],
  "defaultOutputModes": ["application/json", "image/png"],
  "skills": [
    {
      "id": "route-optimizer-traffic",
      "name": "Route Optimizer with Traffic",
      "description": "Calculate optimal routes considering real-time traffic",
      "tags": ["routing", "traffic", "maps"],
      "examples": ["Plan a route from SF to LA avoiding traffic"]
    }
  ]
}
```

### 2.3 一個完整的 A2A 呼叫（JSON-RPC 2.0 binding）

```json
// 1. SendMessage 請求
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "SendMessage",
  "params": {
    "message": {
      "role": "ROLE_USER",
      "parts": [{"kind": "text", "text": "Find me a quiet cafe near Mission St"}],
      "contextId": "ctx-42"
    }
  }
}

// 2. Server 回 Task（不是直接給答案）
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "kind": "task",
    "id": "task-uuid-7",
    "contextId": "ctx-42",
    "status": {"state": "TASK_STATE_INPUT_REQUIRED", "message": "Need your current location"},
    "history": [...]
  }
}

// 3. Client 再發送帶座標的 follow-up Message
// 4. Server 改 status → TASK_STATE_WORKING → TASK_STATE_COMPLETED + Artifact
```

**關鍵設計選擇**：Server 永遠先回 `Task`，而不是直接回 `Message`。這讓 client 能「追蹤一個跨小時的協商」，而不是「等一個 function call 回傳值」。

### 2.4 互動機制（§3.5）

A2A 提供**三種** update delivery：

| 機制 | 適用場景 | 成本 |
|------|----------|------|
| **Polling**（`GetTask`） | 短任務、debug | 高延遲 / 低複雜 |
| **SSE streaming**（`SendStreamingMessage`） | 中等任務、想即時看到進度 | 中成本、單向 |
| **Push notification**（`SubscribeToTask` + webhook config） | 跨小時任務、client 可離線 | 高成本、需要 webhook endpoint |

### 2.5 認證 / 信任（§7, §8.4）

v1.0 加進兩個重要東西：

1. **Agent Card Signing**（JWS / ES256）—— 防偽。卡片可以被第三方 registry mirror，但簽章保證 origin。
2. **Multi-tenancy on gRPC**（`scope` field on request）—— 同一個 agent server 服務多個 org 客戶。
3. **In-Task Authorization** —— 不是只有 connection-time auth，而是在 Task 進行中需要 escalate privilege 時可以再發 token（類似 OAuth step-up）。

### 2.6 生態系現況

| 元件 | 成熟度 | 生態規模 |
|------|--------|---------|
| **A2A spec v1.0.1** | 穩定 | 24,279 stars, Apache 2.0, Linux Foundation 治理 |
| **`a2a-sdk` (PyPI)** | 穩定 | rate-limited（推測月下載 >100K） |
| **`python-a2a`** (第三方) | 穩定 + LangChain 整合 | 30,455 月下載, 995 stars |
| **`a2a-x402`** (payment extension) | 早期 | 527 stars, v0.1 spec |
| **`openclaw-a2a-gateway`** | 早期 plugin | 520 stars |
| **`.NET / neuroglia-io/a2a-net`** | 早期 | 53 stars |
| **`MAIL` (charonlabs)** | 概念階段 | 5 stars, 還在 PoC |
| **Awesome list (`isekOS/awesome-a2a-agents`)** | — | 25 stars，curated 索引 |

### 2.7 還沒解決的兩個大問題

雖然 v1.0 已經收斂，但**生態系還有兩個 open frontier**：

**(a) Service Discovery at Scale** —— 2026-05-28 A2X paper（`arxiv 2605.29270`）直指這個洞：

> 「Internet of Agents 正在成形：LLM agent 預期要 orchestrate 上千個 MCP server、A2A endpoint、可重用 skill……但 context window 塞不下，**Lost-in-the-Middle** 現象讓模型根本注意不到中段的 agent 描述。」
>
> 解法：`A2X` (Agent-to-Anything) 用 **LLM-driven progressive disclosure** —— 自動把已註冊的 service 編成 hierarchical taxonomy，查詢時逐層展開。實驗結果：相對於 full-context dumping，**Hit Rate +6.2 points 但 token 成本只剩 1/9**；相對於最強的 open-source embedding baseline，**Hit Rate +20+ points**。

**(b) Sub-agent Credential Revocation** —— 2026-05-20 HBHC paper（`arxiv 2605.20704`）：

> 自主 agent 會 spawn 出 sub-agent swarms。但現有 OAuth 2.0 introspection、OCSP、W3C Status List 都需要連回 central authority，導致「**zombie agent**」問題——operator 已經關掉 agent，但 zombie 還在用 5 分鐘前發的 token 跑特權操作（worst case：好幾小時）。
>
> 解法：HBHC（Heartbeat-Bound Hierarchical Credentials）—— 讓 credential 有效性**綁定 periodic parent liveness proof**。Verifier 只需要 cached public key + local clock，**不需要網路 round-trip**。parent heartbeat 一停，所有 descendant credential 在 bounded window `W_z ≤ W_max + Δ_h + ε` 內自動失效。
>
> 數字：相對於 OAuth 2.0，**zombie window 縮短 90×**；Rust full auth **0.26 ms**；HTTP concurrent load **18,000+ verifications/sec**；真實 LLM agent swarm 實驗顯示 **end-to-end 對 tool call 開銷 0.71%**，**prompt injection 繞過 application guardrail 後的 post-revocation tool call 數 = 0**；**49-agent 四層 hierarchy 的 cascading revocation** 都在理論 bound 內完成。

**這兩個洞的意義**：「A2A v1.0 解掉了 cross-vendor 通訊問題，但**大尺度部署**（上千 agent、sub-agent swarms）的 discoverability 跟 revocation 還沒標準化——這是 2026 H2 的標準化戰場。」

---

## 3. Why It Matters / Applications

### 3.1 從「單體 Agent」變「Agent 互聯網」——典範轉移

MCP 解了**縱向**問題（agent ↔ tool）。A2A 解**橫向**問題（agent ↔ agent）。兩個加起來才是完整的 Internet of Agents。這個典範轉移在三個尺度上落地：

| 尺度 | 沒 A2A 的世界 | 有 A2A 的世界 |
|------|--------------|--------------|
| **個人** | 個人助手只能在自己的 process 內 orchestrate；想串朋友寫的 agent 要 custom integration | 任何 A2A-compliant agent 都能互相呼叫，就像 email 互通 |
| **企業** | 5 個部門的 agent 各做各的，IT 想串起來要 200 個 custom integration | 全部 A2A-compliant，IT 只要管認證 + governance |
| **市場** | Agent 開發者要重複造相同 specialist（大家都在寫 research agent） | Agent 開發者專注 specialist，互通層是底層建設 |

### 3.2 三個最具體的「殺手級應用」

**應用 1：跨 framework 編排**
你的 supervisor agent 寫在 firn（Python + custom），底下 3 個 specialist 分別用 LangGraph（社群開源）、Google ADK（內部工具）、CrewAI（朋友貢獻）。沒 A2A = 你要寫 3 套 adapter。有 A2A = 全部走 `SendMessage`，你只看 AgentCard。

**應用 2：Agent-to-Agent 經濟**
a2a-x402 把 HTTP 402 "Payment Required" 復活了。商業 agent 可以：
- 回 `402 + payment-required` 訊息（要多少錢、哪條鏈）
- client 簽名支付，回 `payment-submitted`
- merchant verify + settle on-chain，回 `payment-completed` + 真實結果

這讓 specialist agent 真的可以變成「API 商業服務」。一個在 firn 上的 research agent 可以對外收費——你不用自己架收費系統。

**應用 3：長期 multi-actor 協作**
規劃一個 4 天的旅遊：flight agent、hotel agent、tour agent、currency agent。沒 A2A 要 12 個 custom integration + 4 個 polling loop。有 A2A：
- supervisor 用 `SendMessage` 發需求
- 各 agent 用 `Task` 物件保留自己的 working state，必要時回 `input-required` 反問
- supervisor 訂閱 push notification，幾小時後回來看進度，不佔連線

### 3.3 對 ecosystem 的整體衝擊

| 影響面 | 變化 |
|--------|------|
| **Framework 戰爭結束** | 5 大 framework 都承諾 A2A-compliant。framework 差異化成為「developer ergonomics」而非「能不能互通」 |
| **Agent marketplace 成形** | `a2a-x402` + `charonlabs/mail` + LangChain Hub——agent 變成可交易的商品 |
| **MCP vs A2A 角色固化** | MCP = tool 整合層；A2A = agent 互通層。兩者**互補不互斥**（spec §5.1 明確寫出） |
| **Trust / Governance 抬頭** | A2A v1.0 內建 Agent Card signing + OAuth 2.0 + multi-tenancy，回應 SIGKDD 2026 Blue Sky paper「trust must be baked in」的訴求 |

### 3.4 跨來源收斂訊號（Q2 2026 三個月內）

跟之前 reliability (6/9)、cost/latency (6/11) 一樣的模式，**A2A / agent-interop 在 Q2 2026 也是 2-3 個獨立社群同時收斂的題目**：

| 社群 | 產出 | 時點 |
|------|------|------|
| Google / Linux Foundation | A2A v1.0 + v1.0.1 | 2026-03-12 / 2026-05-26 |
| 學術（arXiv） | A2X (service discovery) + HBHC (credential) + Trustworthy Agent Network (SIGKDD 2026) | 2026-05-18 / 2026-05-20 / 2026-05-28 |
| 開源社群 | a2a-x402 (支付) + MAIL (universal mailbox) + openclaw-a2a-gateway | 2026-05 / 2026-06 |

這是「**從 niche spec 升級成 ecosystem mandate**」的訊號。Agent framework 不支援 A2A = 就像今天 web framework 不支援 HTTP/2 一樣尷尬。

---

## 4. Limitations / Honest Assessment

### 4.1 A2A spec 本身的限制

**(L1) Streaming 是單向 SSE，沒有 duplex。** spec 選 SSE 是因為企業 proxy 友善、簡單。但**長期雙向協作**（像下棋、debug session）就要 fallback 到 WebSocket custom binding。A2A 自己承認 v1.0 沒把 duplex 列為 first-class。

**(L2) Task state 不在 protocol 內，server 自己管。** A2A 只定義「Task 物件的 wire format」，**不規範 server 怎麼儲存 Task state**。所以「重啟 server 後 task 怎麼恢復」是各家實作自己決定——這跟 Kubernetes Pod 沒有 stateful 保證是同一個問題。

**(L3) Multi-tenancy 的 `scope` field 還在 early rollout。** gRPC binding 的 `scope` field 雖然 spec 有了，但**沒有 reference implementation** 公開展示一個 agent server 同時服務 3 個 tenant 怎麼用 `scope` 切開。

**(L4) Spec 對「agent 內部 reasoning」完全無知。** A2A 只看到 Task / Message / Artifact——這是「opaque execution」設計的目標，但也意味著**client 沒辦法 audit 對方 agent 的 reasoning chain**。要 trust，你得透過 signature + card reputation + behavioral test。

**(L5) Agent Card 的信任來自 registry 還是 DNS？** 沒講清楚。目前慣例是 `/.well-known/agent.json`，但誰來驗證這個 URL 真的是「某公司某部門某 agent」？社群還在爭論，應該走：
- **DNS+cert chain**（web PKI 延伸）
- **Trusted registry**（像 npm registry + 第三方 mirror）
- **Self-signed + out-of-band verification**（最弱）

### 4.2 Ecosystem 真的限制

**(E1) 24,279 stars 但實戰 production 案例少。** 多數採用是企業內部 PoC（Salesforce、Atlassian、Workday），公開的 production case study 還不到 20 個。**現實是 A2A v1.0 還在早期採用階段**，不是「production-ready 標準」。

**(E2) a2a-x402 的支付 extension 還在 v0.1。** 鏈上結算的 latency 對 agent-to-agent 短呼叫不友善（幾秒 ~ 幾分鐘）。x402 extension 的設計承認這點，把「verification」和「settlement」解耦，但**對 latency-sensitive 工作流**（HFT、real-time bidding），這條路不通。

**(E3) 學術 vs 業界的落差。** arXiv 上的 A2X、HBHC 顯示**真實可擴展性的核心問題業界還沒解**：
- A2X 點出「context 塞不下千個 service」是真實部署會撞到的問題
- HBHC 點出「OAuth revocation 有分鐘級的 zombie window」是真實 enterprise 上路會撞到的問題

但這兩個洞的對應 A2A 標準擴充**還沒成形**。這代表現在部署 A2A 的團隊，要自己處理這兩層。

**(E4) A2A 不解決「對方 agent 的 prompt 偷塞惡意指令」問題。** A2A 規範 wire format，但**內容（artifact 裡的程式碼、message 裡的文字）對 client 而言是 untrusted input**。意思是 **A2A agent 之間的 prompt injection 攻擊面跟 MCP 是一樣的**。SIGKDD 2026 Trustworthy Agent Network paper 點出這個 systemic 漏洞——A2A protocol 本身沒解，要靠 4 個 design pillar（adversarial robustness, semantic alignment, cascading safety, cryptographic provenance）。

**(E5) 跟我們的 firn 評測系統無關的噪音。** A2A 社群花很多時間在「rich card metadata」（icon、provider、documentationUrl）——對個人開發者意義不大，對企業目錄才重要。

### 4.3 我們的獨立評估

- **A2A 在 2026 H2 會快速從 spec 變成「必須支援」**——跟 MCP 在 2025 H1 一樣的軌跡。現在裝 A2A client 比「等其他人裝完再追」成本低很多。
- **Server 端**不一定現在就要做——firn 是「被呼叫的 agent」這個角色是**選擇性**，不是必須性。但 client 端**應該在 1-2 個迭代內裝好**。
- **Trust / Security 那一層不要自己造輪子。** HBHC 是有意思的研究，但實作複雜度高（要管 heartbeat scheduling、clock skew bound、secure enclave）。先靠 HTTPS + standard OAuth 2.0，HBHC 等 reference implementation 出來再說。
- **Service discovery 痛點會在 6 個月內撞到。** firn 自己的 skill + tool 數量還沒到需要 A2X 的規模，但**用 firn 串別人的 agent** 時就會撞到。A2X 還沒成熟，先用 basic AgentCard search 就好。

---

## 5. Actionable for Our Projects

### 5.1 firn 短期（1-2 個迭代內）—— 實作 A2A client role

firn 的定位是「個人 AI agent 框架」。**短期不需要 A2A server role**（你的 firn agent 不會被外部服務呼叫）。**需要 A2A client role**（你的 firn 會想去呼叫別人的 agent）。

**具體工作**：

| 優先級 | 工作 | 難度 | 改動檔案 | 理由 |
|--------|------|------|---------|------|
| **P0** | `tools/a2a_client.py` 新模組 | MODERATE | 新檔 | 用 `python-a2a`（30K 月下載，最成熟）包成 firn tool |
| **P0** | `mcp/registry.py` 旁邊加 `a2a/registry.py` | MODERATE | 新檔 | 維護「已知的 A2A agent URL → capability」的小型本地 registry |
| **P1** | `context/builder.py` 加 A2A AgentCard 注入 | MODERATE | 修改 | 讓 ConversationAgent 看到可用的 A2A agent（類似現有 tool discovery） |
| **P1** | `tools/schemas.py` 加 `a2a_send_message` / `a2a_get_task` 兩個 tool schema | TRIVIAL | 修改 | 讓 LLM 自己決定何時呼叫 A2A agent |
| **P2** | `observability/turns_logger.py` 紀錄 A2A call 的 TaskID | TRIVIAL | 修改 | 之後 debug / audit 跨 agent 工作流要靠這個 |

**P0 詳細說明（給未來的自己 / Hang）**：

```python
# src/firn/tools/a2a_client.py
from python_a2a import A2AClient, AgentCard
from python_a2a.models import Message, TextPart, Role

class A2AToolClient:
    """Wrap a remote A2A-compliant agent as a firn tool."""

    def __init__(self, agent_url: str):
        self.client = A2AClient(agent_url=agent_url)
        self.card: AgentCard = self.client.agent_card  # GET /.well-known/agent.json

    @property
    def tool_name(self) -> str:
        return f"a2a::{self.card.name}"

    @property
    def tool_schema(self) -> dict:
        return {
            "name": self.tool_name,
            "description": self.card.description,
            "parameters": {
                "task": {"type": "string", "description": "What to ask the remote agent"},
                "context_id": {"type": "string", "optional": True},
            },
        }

    def execute(self, task: str, context_id: str | None = None) -> dict:
        msg = Message(role=Role.USER, parts=[TextPart(text=task)])
        if context_id:
            msg.context_id = context_id
        response = self.client.send_message(msg)

        # response is either Task or Message per spec §4
        if hasattr(response, "status"):
            return {"task_id": response.id, "state": response.status.state, "context_id": response.context_id}
        else:
            return {"text": "".join(p.text for p in response.parts if p.kind == "text")}
```

**費用 / 部署成本**：
- `pip install python-a2a`（MIT license, 30K 月下載，無商業限制）
- 每個 remote agent 一個 URL（可以是 firn 自己架的，也可以是外部 service）
- **不需付費 API**——A2A 是 protocol layer，免費 open source

### 5.2 firn 中期（3-6 個月）—— 評估是否要當 A2A server

**先不要做**。理由：
1. firn 定位是「個人助手」——不對外提供服務，不需要 A2A server endpoint
2. 當真的有人想呼叫 firn agent 時，**再用 Cloudflare Workers / Fly.io 5 行 code 包個 A2A server**
3. v1.0.1 才剛發（2026-05-26），等 6 個月 ecosystem 更成熟再評估

### 5.3 firn 不該做的事

- ❌ **不要自己造 A2A 標準擴充**。SIGKDD 2026 paper 點出 4 個 design pillar——但這些應該等 LF 標準組織定義，不要自己加 extension
- ❌ **不要在 firn 內 implement HBHC**。複雜度高、需要 secure enclave、reference implementation 還沒出。等
- ❌ **不要 implement Agent Card 簽章**（JWS/ES256）——除非你要對外當 server。Client 端相信 registry 給的 URL 就好
- ❌ **不要追 a2a-x402 支付 extension**。v0.1 太早、鏈上結算 latency 對個人助手不適用。等 v1.0 再看

### 5.4 managed-agents 自己的改善

- `research/queue/` 跟 `research/reports/` 可以用 A2A 的 `Task` lifecycle 概念重整——但這會動到整個 cron pipeline，**不建議**（跟「Don't recommend changes to the research workflow itself」pitfall 衝突）。寫進 Follow-up。

### 5.5 對 Hermes 本身（hermes-agent）的快速建議

- 看 `hermes-agent` 的 `mcp/` 模組有沒有機會加 `a2a/` 平行模組——MCP 是 tool integration，A2A 是 peer agent integration，兩者**互補**
- 但這超出本次研究範圍，下次獨立評估

### 5.6 整體優先級總結

| 專案 | 動作 | 優先級 | 難度 |
|------|------|--------|------|
| **firn** | `tools/a2a_client.py` 新模組（P0） | P0 | MODERATE |
| **firn** | `a2a/registry.py` 新檔（P0） | P0 | MODERATE |
| **firn** | `context/builder.py` 注入 AgentCard（P1） | P1 | MODERATE |
| **firn** | `tools/schemas.py` 加 a2a tool schemas（P1） | P1 | TRIVIAL |
| **firn** | `observability/turns_logger.py` 記 TaskID（P2） | P2 | TRIVIAL |
| **firn** | A2A server role | 不做 | — |
| **firn** | HBHC、A2X、x402 整合 | 暫緩 | RESEARCH-ONLY |
| **managed-agents** | research pipeline 用 A2A 重整 | 不建議 | — |
| **hermes-agent** | `a2a/` 模組規劃 | 下次評估 | — |

---

## 6. Follow-up Questions

下次研究可以追的方向：

1. **A2A v1.1 規劃內容** —— CHANGELOG 看到 1.0.1 在做 spec bug fix，但 Linux Foundation 治理下的 roadmap 還沒公開。**下次**研究去翻 `a2aproject/A2A` 的 `ROADMAP.md` 跟 LF AI & Data 公告。
2. **A2X 論文後續** —— arXiv 2605.29270 的作者群在 EMNLP 2026 投稿。如果被收，下次看 reviewer 對「LLM-driven progressive disclosure」在 100K+ service 規模下還撐不撐得住。
3. **HBHC reference implementation 釋出** —— 目前只有 paper，沒有 open source。觀望 2026 Q3 看看 Saurabh Deochake 有沒有 release。
4. **A2A vs ANP vs ACP vs MAIL vs Mail** —— 至少 5 個 agent 互通 spec 在跑（A2A、Agent Network Protocol、Agent Communication Protocol、charonlabs MAIL、BrathonBai AIP）。**先看哪個真的活下來**。
5. **a2a-x402 支付擴充的 v1.0 路線圖** —— 鏈上結算 latency 對 sub-second agent 互動不適用。v1.0 是否引入「commit-then-settle」批次結算值得追蹤。
6. **Trustworthy Agent Network 的 4 design pillar** —— SIGKDD 2026 Blue Sky paper 提出的 adversarial robustness、semantic alignment、cascading safety、cryptographic provenance。**這四個 pillar 哪個會先有對應的 A2A extension？** 預測是 cryptographic provenance（最容易標準化）。
7. **firn 的「該不該當 A2A server」決定點** —— 什麼時候 Hang 會想讓「朋友或公司系統」呼叫 firn agent？這個 user need 出現再做。
8. **MCP 跟 A2A 的「translation layer」** —— 現在要把 A2A agent 暴露成 MCP tool 或反之，要自己寫 adapter。會不會有官方 `a2a-mcp-bridge` 標準？

---

## 原始來源

1. **https://github.com/a2aproject/A2A** — 官方 repo + spec — **HIGH** — A2A Protocol v1.0.1 主倉庫，Apache 2.0 + Linux Foundation 治理，24,279 stars，CHANGELOG 顯示 2026-03-12 v1.0.0、2026-05-26 v1.0.1
2. **https://a2a-protocol.org/latest/specification/** — 官方 spec — **HIGH** — 10 章節 protocol 完整定義，§1.3 三層架構、§4 data model、§8 Agent Card 自我描述、§9 JSON-RPC 2.0 binding、§10 gRPC binding
3. **https://a2a-protocol.org/latest/topics/what-is-a2a/** — 官方教學 — **HIGH** — 用「規劃國際旅行」scenario 解釋為什麼要把 agent 暴露成 agent（不是 tool），跟 MCP 互補的設計哲學
4. **https://a2a-protocol.org/latest/topics/a2a-and-mcp/** — 官方 — **HIGH** — 官方明確「A2A ❤️ MCP」互補聲明：MCP 是 agent↔tool、A2A 是 agent↔agent，附 Auto Repair Shop 範例
5. **https://github.com/themanojdesai/python-a2a** — 第三方 Python 實作 — **HIGH** — MIT license，30,455 月下載（pypistats 2026-06-14），內建 LangChain 整合、MCP v2.0 重寫、Agent Flow UI
6. **https://github.com/google-agentic-commerce/a2a-x402** — 官方支付擴充 — **MEDIUM-HIGH** — 527 stars，v0.1 spec，把 HTTP 402 復活做 on-chain agent 支付，Apache 2.0
7. **arxiv 2605.29270 — A2X: Indexing the Unreadable** — 學術論文 — **HIGH** — 處理「1000+ A2A endpoint / MCP server 塞 context」的問題，progressive disclosure 達 Hit Rate +6.2 points at 1/9 token cost，EMNLP 2026 投稿
8. **arxiv 2605.20704 — Heartbeat-Bound Hierarchical Credentials (HBHC)** — 學術論文 — **HIGH** — 解 sub-agent swarms 的 zombie credential 問題，90× 縮短 OAuth zombie window，49-agent 4-level hierarchy cascading revocation
9. **arxiv 2605.19035 — Trustworthy Agent Network** — 學術 vision paper — **MEDIUM-HIGH** — SIGKDD 2026 Blue Sky Ideas Track，4 design pillar 框架（adversarial robustness / semantic alignment / cascading safety / cryptographic provenance）
10. **https://blog.langchain.dev/** — 業界部落格 — **MEDIUM** — 2026 Q2 文章「The Missing Link Between Agents and Applications」「How to Build a Custom Agent Harness」呼應 A2A 趨勢；雖然沒直接寫 A2A，但方向高度一致
11. **https://pypistats.org/api/packages/python-a2a/recent** — 下載量數據 — **HIGH** — 30,455 月下載，驗證 `python-a2a` 是 de facto Python 標準實作

---

**下一個工作日排程執行本指令。**
