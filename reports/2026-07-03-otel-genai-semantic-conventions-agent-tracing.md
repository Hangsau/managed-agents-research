# 研究報告：OpenTelemetry GenAI Semantic Conventions — Agent 執行 Trace 的形式化（2026 H1）

**日期**：2026-07-03
**來源數**：7 | **標籤**：#observability #tracing #opentelemetry #genai-semantic-conventions #openinference #phoenix

---

## 1. The Problem

「Agent 執行 trace 形式化」這個問題在 2024 還只是少數 production 團隊在苦惱——他們寫了幾千行 custom log，自己拼 JSONL、想辦法接 Jaeger、寫 Grafana dashboard。**2026 H1 這個問題從「各家自幹」變成「業界正在收斂到一份官方規範」**，而且這份規範不是 vendor-specific 的（不是 LangChain 的、不是 OpenAI 的），是 **OpenTelemetry 官方 GenAI semantic conventions**。

為什麼這件事突然變得這麼重要？三個驅動力：

1. **Multi-agent 系統把 trace 複雜度推過了人腦可承受的臨界點**。一個 lead agent 派出 3 個 sub-agent，每個 sub-agent 平均呼叫 5 次 LLM + 8 次 tool call + 2 次 MCP server call。一次任務就 100+ 個 span。沒有形式化規範，debugger 看到的只是一坨沒結構的 log。
2. **「Agent 觀測性」已經是 agent-as-a-service 的核心賣點**。Arize Phoenix 10.4K stars、Langfuse 30K stars、Traceloop 7.3K stars——三巨頭全部把自己的 SDK 對齊到 OpenInference（OpenTelemetry 互補規範）上面。意思是：**不在 OTel 規範裡 = 不被任何主流後端支援 = 沒人用**。
3. **Token 成本治理是 2026 H1 agent 團隊的第一痛點**。Anthropic prompt caching、Bedrock agent sessions、OpenAI Assistants thread——每個 provider 都有自己的 cache 計價規則。沒有一份能跨 provider 比較的 metric 標準，你根本算不清「哪個 agent 在燒錢」。

OTel 的解法是定義一組**跨 provider、跨 runtime、跨 backend 都通用**的 span 類型、attribute 命名、metric 維度。2026 H1 這份規範已經從 development stage 走到 production-ready，主流 OTel SDK、主流 observability backend 全部開始實作。

> 對 firn 來說：firn 目前每個 task 寫自己的 JSONL trace（`traces.jsonl` 在 `~/.hermes/runs/<run_id>/`），後面接的是 custom Grafana / Logfire。這份規範是 firn 把 trace 升級到「**跟 Langfuse/Phoenix/Tempo/Honeycomb 任何一個都能直接接**」的技術路徑。

## 2. Core Mechanism

### 2.1 規範的權威來源

OpenTelemetry 官方 GenAI semantic conventions 在 2026 H1 已經**從主 semantic-conventions repo 搬到獨立 repo**——`open-telemetry/semantic-conventions-genai`（125 stars，2026-07-03 last push）。這個搬遷本身就是信號：GenAI 是大到要獨立維護的領域。

```bash
# 主入口
https://github.com/open-telemetry/semantic-conventions-genai
# 規範文件目錄
docs/gen-ai/
├── gen-ai-spans.md           # 客戶端 LLM 呼叫 (90KB)
├── gen-ai-agent-spans.md     # Agent 特有的 span 類型 (87KB)
├── gen-ai-metrics.md         # Token usage、duration 等 metric
├── gen-ai-events.md          # Streaming chunk 事件
├── mcp.md                    # MCP 工具呼叫規範 (111KB)
└── anthropic.md / openai.md  # provider-specific 屬性
```

關鍵設計原則：**「spec 由 Weaver 從 YAML 自動生成 markdown」**——整個註解 `<!-- weaver .registry.spans[] | select(.type == "gen_ai.create_agent.client") -->` 顯示 source of truth 是 `model/` 下的 YAML。這比手寫 markdown 規範好太多——schema 跟 docs 永遠不會 drift。

### 2.2 Agent 專屬的 6 種 Span 類型

OTel 把 agent 行為拆成 6 種**語意明確**的 span 類型，每種有專屬 attribute schema：

| Span 類型 | `gen_ai.operation.name` | Span Kind | 典型範例 | 用途 |
|---|---|---|---|---|
| `create_agent` | `create_agent` | CLIENT | OpenAI Assistants create, AWS Bedrock create-agent | 一次性建立 agent 資源 |
| `invoke_agent` (client) | `invoke_agent` | CLIENT | AWS Bedrock Agents invoke, OpenAI Assistants run | 跨進程呼叫 agent |
| `invoke_agent` (internal) | `invoke_agent` | INTERNAL | LangChain agents, CrewAI agents | 同進程內部 agent 呼叫 |
| `invoke_workflow` | `invoke_workflow` | — | LangGraph state machine, n8n flow | 整個 workflow 範圍 |
| `plan` | `plan` | — | ReAct planner, Plan-and-Execute | 規劃 / 任務分解階段 |
| `execute_tool` | `execute_tool` | — | 任何 tool 呼叫（包含 MCP） | 工具執行 |

這個分類很關鍵——它**第一次把「agent 跟普通 LLM 呼叫的差別」形式化**。一個普通 `chat` span 只看得到 model 進出的 prompt/completion。一個 `invoke_agent` span 會包含 `gen_ai.agent.name`（"Math Tutor"）、`gen_ai.agent.id`（`asst_5j66UpCpwteGg4YSxUnt7lPY`）、`gen_ai.conversation.id`（thread 或 session id），這些**直接讓你可以在 Grafana 上 group-by agent、算每個 agent 的 cost**。

### 2.3 Required / Recommended / Opt-In 三層屬性

OTel 用嚴格程度區分 attribute 的強制性，這是另一個聰明設計：

- **Required** — 一定要有，沒有就不算合規。例：`gen_ai.operation.name`、`gen_ai.provider.name`、`error.type`（出錯時）。
- **Conditionally Required** — 在某些情況下要有。例：`gen_ai.agent.id` 只在「應用有提供時」必填；`gen_ai.conversation.id` 只在「真的有 conversation id」時填，禁止用 trace_id 湊數（規範明文 `SHOULD NOT`）。
- **Recommended** — 強烈建議有，缺了會降級用戶體驗。例：`gen_ai.usage.input_tokens` / `output_tokens` / `cache_read.input_tokens` / `cache_creation.input_tokens`。
- **Opt-In** — 預設關閉，打開才有。例：`gen_ai.input.messages` / `gen_ai.output.messages`（**完整 prompt 與 completion 內容**）——因為包含 PII，預設關閉讓用戶主動 opt-in。

這個三層設計解決了 observability 領域最常見的「要資料但怕資料外洩」矛盾。

### 2.4 Token 計價標準的革命：`cache_creation.input_tokens` 和 `cache_read.input_tokens`

這是 2026 H1 規範新增的兩個 attribute，**直接對應 Anthropic prompt caching 的計價模型**：

- `gen_ai.usage.input_tokens`：總 input token（**包含** cache 讀寫的 token）
- `gen_ai.usage.cache_read.input_tokens`：從 cache 讀取的 token（**計價為 1/10**，以 Anthropic 為例）
- `gen_ai.usage.cache_creation.input_tokens`：寫入 cache 的 token（**計價為 1.25x** baseline）

這三個 attribute 讓你可以**精確算 cache hit rate 的 cost savings**——之前各家 instrumentation 都只報總 input tokens，cache 效益算不出來。OTel 直接把 cache 計價變成 first-class attribute。

### 2.5 MCP 規範：跨進程 trace context 傳播

MCP 規範 (`docs/gen-ai/mcp.md`, 111KB) 解決了一個非常實際的問題：**MCP 的 trace parent 怎麼跨 JSON-RPC 訊息傳遞**？

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get-weather",
    "_meta": {
      "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
      "baggage": "userId=alice,serverNode=DF%2028,isProduction=false"
    }
  }
}
```

關鍵設計：W3C trace context 的 keys（`traceparent` / `tracestate` / `baggage`）在 MCP `params._meta` 裡**不帶 DNS prefix**——直接用裸 key。這跟其他 MCP `params._meta` 內容（必須帶 DNS prefix）不一樣。這個是 [SEP-414](https://modelcontextprotocol.io/community/seps/414-request-meta) 明確規定的。

這對 firn 的意義：firn 接 MCP server（firn-mcp）時，如果走的是 stdio transport，HTTP trace context 不會自動跨 JSON-RPC message 傳遞。**必須在 MCP client 端手動 inject W3C context 到 `_meta`**，server 端再 extract。

### 2.6 OpenInference：OTel 互補規範（不是替代）

[Arize-ai/openinference](https://github.com/Arize-ai/openinference) 1066 stars——它是 OTel 的**互補層**（不是競爭），處理 OTel 還沒收斂的細節：

- **LLM-specific 屬性**：`llm.input_messages` / `llm.output_messages`（完整 chat history）、`llm.token_count.prompt` / `completion` / `total`（更細的 token 計價）。
- **Retrieval 規範**：`retrieval.query` / `retrieval.documents`（vector store 回傳的 chunk 內容）。
- **Tool 規範**：`tool.name` / `tool.parameters` / `tool.description`。
- **Embedding 規範**：`embedding.embeddings` / `embedding.model_name`。

**OpenInference → OTel GenAI 規範的 mapping 是明確的**。看 OpenInference repo 的 `spec/` 目錄，它不是另起爐灶，而是 OTel GenAI 規範還沒涵蓋的部分先制定，等 OTel 收斂後再 bridge 過去。Phoenix（10.4K stars）和 Langfuse（30K stars）都支援**兩套規範並存**——同一個 span 可以同時帶 OpenInference attributes 和 OTel GenAI attributes。

### 2.7 主流生產實作

| 專案 | Stars | 對齊規範 | 語言 | 角色 |
|---|---|---|---|---|
| [Arize-ai/openinference](https://github.com/Arize-ai/openinference) | 1066 | OTel + 自己的 OpenInference | Python/JS/Java/Go | 規範 + 30+ instrumentation |
| [Arize-ai/phoenix](https://github.com/Arize-ai/phoenix) | 10390 | OpenInference native | Python/TS | Open-source AI observability 後端 |
| [langfuse/langfuse](https://github.com/langfuse/langfuse) | 30370 | OpenTelemetry native | Python/TS | Open-source AI engineering platform |
| [traceloop/openllmetry](https://github.com/traceloop/openllmetry) | 7263 | OpenTelemetry native | Python/JS/.NET | OpenLLMetry SDK + Traceloop 商業後端 |
| [alibaba/loongsuite-java](https://github.com/alibaba/loongsuite-java) | 76 | OTel GenAI v1.41.1 | Java | 阿里 LoongCollector GenAI util |
| [kidoz/trace-weft](https://github.com/kidoz/trace-weft) | 3 | OTel-compatible | Rust | Local-first LLM agent 觀測工具（sqlite + jsonl） |
| [Mandark-droid/genai_otel_instrument](https://github.com/Mandark-droid/genai_otel_instrument) | 2 | OTel GenAI 自動 wrap | Python | GenAI auto-instrumentation wrapper |

**OpenTelemetry 路線是業界共識**，但各家切入點不同：
- **Arize Phoenix** + **OpenInference**：open-source 起家，主打 self-host + 深度 eval。
- **Langfuse**：30K stars 巨頭，主打 prompt management + eval + 完整 SaaS 商業版。
- **Traceloop / OpenLLMetry**：更貼近 OTel 原生，後端商業化（Traceloop Cloud）。
- **阿里 LoongSuite**：Java 端的官方對齊實作，2026 H1 才剛起步（76 stars 但背後是阿里整個 OTel 團隊）。

## 3. Why It Matters / Applications

### 3.1 對 AI agent 領域的影響

1. **「跨 provider trace 統一查詢」變得可行**。之前你要看 Claude 的 token cost 跟 GPT-4 的 token cost 對比，得自己 parse 兩家 SDK 的 log。OTel GenAI 規範下，`gen_ai.provider.name` 跟 `gen_ai.usage.input_tokens` 是固定 attribute，直接 group-by provider 算 cost 就行。

2. **Agent observability 從「框架特性」變成「infra 基礎設施」**。OTel 已經是所有雲端 observability 的事實標準（Datadog、Honeycomb、Grafana Tempo、Jaeger 全都吃 OTel）。GenAI 規範一進去，**任何 LLM agent 框架寫出來的 trace 都能直接進企業既有的監控 stack**。這對 B2B agent 服務商是巨大利多——客戶不用為了觀測你的 agent 額外搞一套。

3. **Token 成本治理跨團隊可比較**。`gen_ai.usage.cache_creation.input_tokens` 跟 `cache_read.input_tokens` 兩個 attribute 讓 cache hit rate 變成可監控 metric。Anthropic prompt caching 已經上線 8 個月，但到 2026 H1 才有**標準 attribute 讓你算「誰在用 cache、用得怎樣」**。

### 3.2 對 firn 的具體意義

firn 目前在 `core/runner/agent.py` 跟 `core/runner/task.py` 裡用 Python `logging` 寫 trace 到 `~/.hermes/runs/<run_id>/traces.jsonl`，再用 custom script 餵進 Grafana Loki 或 Logfire。問題：

- **Schema 是 firn 自己的**，沒人認識。換到新後端要重寫 parser。
- **沒跟業界 token 計價 attribute 對齊**，cache hit rate 算不出來。
- **MCP server 的 trace context 沒跨進程傳遞**，firn-mcp 的 sub-tool call 跟主 agent 跑在不同的 trace 上。

把 firn 的 trace 升級到 OTel GenAI 規範，可以一次解決三個問題：跨後端、cache 計價、跨 MCP 進程。

## 4. Limitations / Honest Assessment

### 4.1 規範本身的限制

1. **GenAI spans 全部標記為 "Development" stability**。每個 attribute 的 markdown 文件都有 `![Development](https://img.shields.io/badge/-development-blue)` 標籤。意思是規範**還在快速變動**，production 用要鎖版本。對比來看 HTTP semantic conventions 早就是 "Stable"。

2. **`create_agent` 跟 `invoke_agent` 邊界模糊**。同一個 agent 既可以是「remote service」（用 `create_agent` + `invoke_agent.client`）也可以是「local framework object」（用 `invoke_agent.internal`）。對 LangGraph 這類「local state machine + remote LLM endpoint」混搭架構，要選哪個 span kind 完全靠 convention 沒強制規則。

3. **`gen_ai.input.messages` / `gen_ai.output.messages` schema 過於複雜**。從規範 example 看到多 part 結構（text / tool_call / tool_call_response）多層巢狀，OTLP protobuf encode 起來不便宜。如果預設 capture full content，單次 chat 50KB+ span size 很正常。

4. **跨 provider attribute 命名不一致**。AWS Bedrock 用 `aws.bedrock.*` namespace、Azure 用 `azure.ai.inference.*`、Anthropic 用 `anthropic.*`——沒有統一抽象 layer 讓你寫「所有 provider 都適用」的 query。

### 4.2 對「聲稱的突破」的懷疑

**官方說法是「OTel GenAI 規範讓 agent observability 標準化」**。我的批判：

- **規範本身標準化是事實**（OTel 是業界共識 protocol，跨 vendor 對齊）。
- **但 2026 H1 主流 backend 的 support 不完整**。Phoenix 對 OpenInference 第一類公民、對 OTel GenAI 規範是第二類公民；Langfuse 標榜 OTel native 但 production 觀察下來仍然自定 attribute 為主。意思是「**spec exists ≠ spec adopted**」。
- **OTel 在 agent 領域的實際穿透率有限**。Python 端靠 `opentelemetry-instrumentation-openai-agents` 等套件自動捕獲；但**對 LangGraph / CrewAI / AutoGen 這類「自己組裝 LLM call」的 framework，自動 instrumentation 覆蓋不到**，得自己用 `opentelemetry-api` 手寫 span。這等於「規範解決了 attribute 命名，沒解決 instrumentation 覆蓋率」。

### 4.3 與既有方案的對比

| 方案 | OTel GenAI 對齊 | Cache 計價 | MCP trace | 自架成本 | Vendor lock-in |
|---|---|---|---|---|---|
| **firn 現有 custom JSONL** | ❌ | ❌ | ❌ | 中（自己寫 parser） | 無（也沒價值） |
| **Langfuse** | ✅ native | ✅ | ✅ | 低（self-host docker） | 中（schema 仍以 Langfuse 為中心） |
| **Phoenix** | ⚠️ OpenInference 為主 | ⚠️ 透過 OpenInference | ⚠️ | 低（self-host pip install） | 低（純 OTel 輸出） |
| **Traceloop** | ✅ native | ✅ | ✅ | 中（OpenLLMetry SDK 需 import） | 高（後端商業） |
| **OpenLLMetry → 自接 Tempo** | ✅ 完全 OTel | ✅ | ✅ | 高（自己跑 OTel collector） | 無 |

### 4.4 可複製性

普通開發者能不能在 firn 規模重做？分三層：

- **Adopt 規範**（在 trace emit 端用對的 attribute 名）：**TRIVIAL**。`opentelemetry-api` 1 行 set attribute，照規範填。
- **完整 instrumentation**（自動 capture LLM call 跟 tool call）：**MODERATE**。每個 LLM 框架 hook 不同，30+ instrumentation 是大工程。
- **自己開 backend**（不接現成 SaaS）：**HARD**。Phoenix / Langfuse 都有幾年累積，跑起來才知道 schema 演進問題。

## 5. Actionable for Our Projects

### 5.1 對 firn 的具體升級路徑

按優先級排序，每個都給難度跟可不可繞過付費 API：

| # | 工作 | 模組 | 難度 | 付費 API | 立即可做 |
|---|---|---|---|---|---|
| 1 | **採 OTel GenAI attribute schema 在現有 trace emit 端** | `core/runner/agent.py`、`core/runner/task.py` | TRIVIAL | 否 | 改 `emit_trace_event()` 加 attribute 名對齊 |
| 2 | **MCP trace context 傳遞** | `mcp/registry.py`、`mcp/server_wrapper.py` | MODERATE | 否 | 參考 `mcp.md` 的 `_meta` 注入實作 |
| 3 | **加入 `gen_ai.usage.cache_read.input_tokens` / `cache_creation.input_tokens` 計算** | `actions/anthropic.py`（已有 prompt cache 邏輯） | MODERATE | 否 | 從 `response.usage` 拿 cache 欄位填進去 |
| 4 | **接 Langfuse 或 Phoenix 作為 trace sink** | `core/runner/sink.py` | MODERATE | 否 | Langfuse self-host 是 MIT，`pip install langfuse` 即可 |
| 5 | **完整 OTel Collector + Tempo + Grafana 取代 custom Logfire** | infra | HARD | 否 | 重寫整個 observability stack |

> **第一個 P0 工作的具體步驟**（TRIVIAL，30 分鐘內可完成）：
> 1. 在 `core/runner/trace.py`（或既有 trace emit 模組）加 `OPENTELEMETRY_GENAI_ATTRIBUTES = {...}` mapping，從 firn 內部 event name 對應 OTel `gen_ai.operation.name`：
>    - `task.start` → `invoke_agent.internal`
>    - `llm.call` → `chat`
>    - `tool.call` → `execute_tool`
>    - `mcp.tool_call` → `execute_tool`（with `gen_ai.tool.type=mcp`）
> 2. 在 `core/runner/trace.py` emit 處加 `gen_ai.provider.name`（"anthropic" / "openai" / "minimax-oauth"）、`gen_ai.usage.input_tokens` / `output_tokens` 從 `response.usage` 取出。
> 3. 不要動 OTel SDK——firn 內部 trace 仍然寫 JSONL，但 attribute 名字遵守 OTel 規範，這樣將來接 OTel Collector / Langfuse / Phoenix 任何一個都不需要 rewrite emit 端。

### 5.2 對 managed-agents 的影響

managed-agents 是 batch task runner，**不像 firn 有 LLM agent 行為要 trace**——但核心 v2 harness 的 turn loop 仍然有 task dispatch 跟 LLM call 兩段。如果 managed-agents 想加 trace，可以用同樣的 OTel GenAI attribute schema，**這樣 firn 跟 managed-agents 的 trace 能在同一個 Grafana dashboard 上**。

但這是 nice-to-have 不是 P0——managed-agents 的 failure mode 通常是「整批失敗」不是「某個 span 失敗」，更值得做的是 batch-level trace（`batch.start` / `batch.end`）不是 per-LLM-call trace。

### 5.3 不要做的事（negative space）

- **不要自己定義 GenAI trace schema**。firn custom JSONL 的 attribute name 一定要改成對齊 OTel，否則 6 個月後接 Langfuse 還是要重寫 emit 端。
- **不要裝 OTel SDK 然後希望自動 instrumentation 覆蓋所有 LLM call**。firn 跟 managed-agents 大部分 LLM call 是自組裝，自動 instrumentation 抓不到——得自己用 `opentelemetry-api` 手寫。
- **不要把所有 messages 預設 capture 進 trace**。`gen_ai.input.messages` / `gen_ai.output.messages` opt-in 才開，預設只記 token count + metadata，不然 PII 直接進 Loki。

## 6. Follow-up Questions

1. **OTel GenAI 規範何時從 Development 升到 Stable？** spec repo 沒有公開 roadmap，觀察 signal：
   - 多家 SDK 已經 1.0 化（OpenInference 1.0 出了，OpenLLMetry 1.0 也出了）？
   - 主流 backend（Phoenix / Langfuse）把 OTel attribute 提升為 first-class？
2. **MCP trace context 在 stdio transport 之外怎麼運作？** 規範只給 `_meta` 注入的 example，但 Streamable HTTP transport 下 HTTP headers 跟 `_meta` 哪個優先、怎麼 fallback？
3. **Token 計價 attribute 對 OpenAI Assistants / Azure OpenAI 這種「自己有 cache」的 provider 怎麼對應？** 規範 example 主要是 Anthropic + Bedrock 風格，OpenAI 風格還沒看到。
4. **「Agent loop」怎麼用 OTel 表達？** ReAct 風格的 agent 一次任務會有 10+ 次 LLM call + 5+ tool call，規範的 `plan` span 是包整個 ReAct loop 還是只包第一次 plan 階段？實作上各家差異很大。
5. **firn 的 OTel GenAI 升級先走 cache 計價還是先走 MCP trace？** 我的判斷：先走 cache 計價（立刻有 cost 治理效益），MCP trace 留到 P1。但要驗證 Anthropic / OpenAI 在 firn 內部 response 物件裡 cache token 的欄位位置。

---

### 原始來源

1. [open-telemetry/semantic-conventions-genai](https://github.com/open-telemetry/semantic-conventions-genai) — 官方 Spec 規範 — **HIGH** — 2026-07-03 last push，OTel 官方 GenAI 規範獨立 repo，125 stars
2. [gen-ai-agent-spans.md](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md) — 官方 Spec 規範 — **HIGH** — 定義 6 種 agent span 類型，87KB Weaver-generated 文件
3. [mcp.md](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/mcp.md) — 官方 Spec 規範 — **HIGH** — MCP trace context 跨 JSON-RPC 訊息傳遞規範，111KB
4. [Arize-ai/openinference](https://github.com/Arize-ai/openinference) — 程式庫實作 — **HIGH** — 1066 stars，OTel 互補規範 + 30+ Python/JS/Java/Go instrumentation
5. [Arize-ai/phoenix](https://github.com/Arize-ai/phoenix) — 程式庫實作 — **HIGH** — 10390 stars，open-source AI observability backend，OpenInference native
6. [langfuse/langfuse](https://github.com/langfuse/langfuse) — 程式庫實作 — **HIGH** — 30370 stars，OTel native AI engineering platform
7. [traceloop/openllmetry](https://github.com/traceloop/openllmetry) — 程式庫實作 — **HIGH** — 7263 stars，OpenLLMetry SDK，OpenTelemetry native
8. [alibaba/loongsuite-java](https://github.com/alibaba/loongsuite-java) — 程式庫實作 — **MEDIUM** — 76 stars 但阿里 OTel 團隊官方背書，OTel GenAI v1.41.1 對齊
9. [kidoz/trace-weft](https://github.com/kidoz/trace-weft) — 程式庫實作 — **MEDIUM** — 3 stars 但架構有趣：local-first Rust 工具，sqlite + jsonl，可作 firn local trace 模式參考
