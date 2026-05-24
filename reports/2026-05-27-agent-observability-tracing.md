# 研究報告：AI Agent 可觀測性——從 Trace 視覺化到自我治理記憶層

**日期**：2026-05-27
**來源數**：5 | **標籤**：#agent #observability #tracing #memory #context-management

## 1. The Problem

當 AI agent 在生產環境跑久了，最大的噩夢不是「回答錯誤」，是「不知道為什麼錯」。

一個 agent 跑了 200 個步驟，中間某處 context 斷裂、某個 tool 返回預期外的結果、某個 decision 建立在錯誤的前提上——但你沒有任何東西可以回溯。LLM call 的 token 消耗有記錄，但整個決策鏈是黑箱。

這個問題為什麼現在更嚴重？因為 2025-2026 的 agent 架構越來越複雜——multi-agent、self-correcting、memory-augmented systems——「trace 一個 agent 跑了什麼」從「nice to have」變成「必要條件」。

誰在解決這個問題？
- **OpenLIT**（2463 stars）— 專注 LLM observability，把 OpenTelemetry 標準帶進 AI 工程
- **AgentPrism**（347 stars）— 把 agent trace 變成 React UI component
- **OpenViking**（24593 stars）— 把 context 管理本身視覺化
- **Memoria**（271 stars）— 把記憶層變成可審計、可 rollback、可 branch 的系統
- **agent-tracer-2**（7 stars）— local-first OpenTelemetry trace aggregator

---

## 2. Core Mechanism

### 2.1 Memoria — Git for AI Agent Memory

記憶不只是「存放」，是「版本控制」。Memoria 把 Git 的核心概念移植到 agent 記憶層：

**記憶操作等同於 Git 操作：**
- `memory_branch(name="eval_sqlite")` — 開一個實驗分支，isolated experiment
- `memory_checkout(name="eval_sqlite")` — 切換到實驗分支
- `memory_merge(source="eval_sqlite")` — 合併回 main，或 delete 如果失敗
- `memory_diff(source="branch")` — 預覽分支間差異
- Snapshot + rollback at any point-in-time

**底層：MatrixOne MVCC（arXiv 2604.03927, 2026-04）**
MatrixOne 的 immutable storage + Multi-Version Concurrency Control 使其在 TB 等級資料上做 clone/branch/diff/merge/revert 是 near-instantaneous。不需要把整個 dataset 載入記憶體。

**自我治理（Self-Governance）：**
```
記憶進來 → 矛盾偵測 → 低信心記憶 quarantine → 審計軌跡
```
自動偵測記憶矛盾、隔離低信心記憶、維護完整 audit trail。不是被動存放，是主動治理。

**架構圖：**
```
Cloud Mode:
AI Agent ←MCP→ Memoria CLI ←HTTP/REST→ Memoria Cloud API Server

Self-Hosted:
AI Agent ←MCP→ Memoria MCP Server ←SQL→ MatrixOne (vector + fulltext)
                         ├── Canonical Storage
                         ├── Retrieval (vector/semantic)
                         └── Git-for-Data (snap/branch/merge)
```

**對比傳統 RAG：**
| | Memoria | Letta/Mem0/Traditional RAG |
|---|---|---|
| Version control | Native zero-copy snapshots & branches | File-level or none |
| Isolation | One-click branch | Manual data duplication |
| Audit trail | Full snapshot + provenance | Limited logging |
| Retrieval | Vector + fulltext hybrid | Vector only |
| Self-governance | Auto contradiction detection & quarantine | Manual cleanup |

---

### 2.2 OpenLIT — OpenTelemetry-native LLM Observability

把 OpenTelemetry 生態系統（標準化的 trace/metrics collector）直接應用到 LLM 應用：

```python
import openlit
openlit.init(otlp_endpoint="http://127.0.0.1:4318")
```

**核心功能：**
- **11 種 built-in evaluation types**： hallucination、bias、toxicity、safety、instruction following、completeness、conciseness、sensitivity、relevance、coherence、faithfulness。LLM-as-a-Judge，context-aware（以提供的 context 為 ground truth）
- **Rule Engine**：用 AND/OR 邏輯定義條件規則，動態取值 prompt/evaluation config
- **Prompt Hub**：版本化、管理 prompts
- **Cost Tracking**：自訂模型定價檔案，精確預算
- **Fleet Hub**：用 OpAMP 管理多個 OpenTelemetry Collectors

支援 Python/TypeScript/Go SDK，vendor-neutral（可接任何相容 OpenTelemetry 的 backend）。

---

### 2.3 OpenViking — Context Database

把 context 管理當成檔案系統來設計，放棄傳統 RAG 的 flat vector storage：

**五層挑戰對應五個解法：**
| 挑戰 | OpenViking 解法 |
|---|---|
| Fragmented Context | Filesystem paradigm（統一管理 memories/resources/skills） |
| Surging Context Demand | L0/L1/L2 三層漸進載入，按需載入節省 token |
| Poor Retrieval | 目錄定位 + 語意搜尋，遞迴精確獲取 |
| Unobservable Context | 可視化 retrieval trajectory，可以看到 root cause |
| Limited Memory Iteration | 自動壓縮對話內容，萃取長期記憶 |

**L0/L1/L2 三層架構：**
- L0：壓縮後的濃縮記憶
- L1：中度摘要
- L2：完整原始內容
按需漸進載入，agent 需要什麼深度就載到哪層。

---

### 2.4 AgentPrism — Trace 可視化 UI

把 OpenTelemetry trace data 轉成 React component，主打「讓 trace 不是 JSON 海洋」：

```tsx
import { TraceViewer } from "./components/agent-prism/TraceViewer";
import { openTelemetrySpanAdapter } from "@evilmartians/agent-prism-data";

<TraceViewer
  data={[{
    traceRecord: yourTraceRecord,
    spans: openTelemetrySpanAdapter.convertRawDocumentsToSpans(yourTraceData),
  }]}
/>
```

**提供：**
- Trace List — 多筆 trace 列表
- Tree View — 階層式 span 可視化，支援搜尋和 expand/collapse
- Details Panel — 單一 span 屬性檢視
- Adapter 模式：OpenTelemetry、Langfuse 等格式都可轉換

Alpha release（API 可能變動），React 19 + Tailwind CSS 3 + TypeScript。

---

## 3. Why It Matters / Applications

**對整個 AI agent 領域的影響：**

1. **Observability 從"加分"變"必要"**
隨著 agent 自主性提升，something broke 時你需要能回答「哪一步出了問題」。AgentPrism 和 OpenLIT 把這個能力民主化——不是只有大公司能建內部 observability tooling。

2. **Memory 不再只是 storage，是 governance**
Memoria 的 self-governance 概念很重要：記憶會「自我糾錯」。當 agent 儲存的兩個事實矛盾時，系統不會假裝沒事，會 quarantine 並通知。這對長期跑的 agent（每天重啟、跨 session 累積記憶的）特別關鍵。

3. **Tiered context 是 cost optimization 的關鍵**
OpenViking 的 L0/L1/L2 漸進載入，直接對應「如何讓 agent 用更少 token 達到同樣 quality」這個實務問題。不是壓縮，是分層。

4. **OpenTelemetry 是 industry standard 的時機到了**
OpenLIT 和 AgentPrism 都用 OpenTelemetry 作為 data model。當 trace format 標準化，生態工具（Jaeger、Zipkin、Datadog、蜂巢等）全部可以接上。這是個簡單但重大的趨勢。

---

## 4. Limitations / Honest Assessment

**Memoria 的限制：**
- 依賴 MatrixOne（雖然是 Apache 2.0 開源，但不是主流 DB），self-host 需要跑 Docker + MatrixOne stack
- 自我治理的「矛盾偵測」機制具體怎麼實作，README 只有概念描述沒有實作細節（可能需要看程式碼）
- Cloud 版本是付費的（thememoria.ai），self-host 需要自己維護
- **對 firn 的 FIT 問題**：Memoria 的 MCP server 是給 AI agent 用的，不是給 batch task runner。firn 是 agent framework，理論上適用，但目前只看到 Kiro/Cursor/Claude Code/Codex/Gemini CLI 的整合。Hermes agent 的整合需要自己刻。

**OpenLIT 的限制：**
- 功能很多（11 種 evaluation、rule engine、cost tracking...），但對小型專案可能 Over-engineered
- 需要跑 OpenTelemetry Collector + backend（ClickHouse 等），self-host 成本不低
- **對 firn 的 FIT**：Python SDK 很簡單（`import openlit; openlit.init()`），但 Hermes agent 的 action 層沒有統一的 hook point 來 injection，需要改架構

**OpenViking 的限制：**
- 24K stars 但文件主要在 volcengine 生態系（Volcengine ARK API），不是單純 OpenAI API
- 需要 VLM model（做 content understanding）和 embedding model，額外成本
- L0/L1/L2 分層的實作細節（如何決定哪層存什麼）文件語焉不詳

**AgentPrism 的限制：**
- Alpha release，API 不穩定
- 只是 React UI component，不是完整的 observability 系統（需要 backend 配合）
- 347 stars，社群不大

**對任何「聲稱突破」的懷疑：**
Memoria 宣稱「Git for AI Agent Memory」，但 Git 的核心價值是協作（多人對同一 codebase 協作）和 branch/merge review（PR workflow）。Agent memory 的 branch/merge 更多是「實驗性嘗試」（例如實驗不同的 goal 策略）而不是多人協作。這是不同的使用情境，「Git 類比」可能有點 marketing 成分高於實質。

---

## 5. Actionable for Our Projects

### 對 firn：

**1. Memoria-style self-governance（MODERATE難度）**
- Memoria 最值得借鑒的不是 Git-for-Memory 的比喻，是**自我治理**的概念：記憶有矛盾時要能偵測和隔離
- firn 的 heartbeat 系統已經有「自我健康監控」的概念，可以延伸到「記憶矛盾偵測」
- **具體做法**：在 firn 的 session memory 層加入一個簡單的 contradiction check——每次 `memory_store` 新 fact 前，先 query 現有記憶，如果已有相同 subject 但不同 value，標記為 conflict 而不是直接 overwrite
- 不需要 MatrixOne，用 SQLite 的 JSON 欄位就可以做原型
- **實作難度**：MODERATE（需要修改記憶層 schema，增加 conflict flagging logic）

**2. OpenViking-style tiered context（TRIVIAL→MODERATE）**
- L0/L1/L2 三層的 concept 可以直接映射到 firn 的 existing memory tiers
- **實作難度**：TRIVIAL（概念映射），但要做真正的「漸進載入」需要 LLM 來決定哪層，比較 MODERATE

**3. OpenLIT-style lightweight observability（HARD）**
- `openlit.init()` 模式很優雅，但需要整個 firn action execution 都走同一個 hook point
- 目前 firn 的 action 是分散的（bash、read_file、write_file...），沒有統一的 execution middleware
- **實作難度**：HARD（需要先建立 action execution middleware）

### 對 managed-agents：

**4. AgentPrism trace viewer for batch debugging（RESEARCH-ONLY）**
- managed-agents 的 batch 任務有 structured output（playbook 產出），理論上可以做 trace visualization
- 但 batch 任务的 trace 不是 real-time 的，更像是「結構化的執行 log」
- 把 playbook YAML 轉成 AgentPrism 的 TreeView 格式是個有趣的方向，但實際价值有限
- **實作難度**：RESEARCH-ONLY

---

## 6. Follow-up Questions

1. **Memoria 的 contradiction detection 實作細節**：是規則ベース還是 LLM 判斷？延遲多少？如果是 async 處理，agent 在等待期間是否 block？

2. **OpenLIT 的 11 種 evaluation 如何選擇性觸發**：不是每個 request 都需要跑全套 11 種 evaluation。如何根據 request type 或風險等級選擇性觸發？

3. **OpenViking 的 tiered loading 如何自動化**：LL0/L1/L2 的分層是手動定義規則還是 LLM 自動分類？自動分類的 token 成本是否低於全量載入？

4. **AgentPrism 的 span model 如何標準化**：OpenTelemetry semantic conventions 有 standard span attributes，但 agent-specific spans（plan、retry、sub-agent delegation）還沒有標準。是否有 emerging standard？

---

### 原始來源

1. https://github.com/volcengine/OpenViking — GitHub Repo — HIGH — 24,593 stars，context database 解決 fragmented context、tiered loading、visualized retrieval trajectory
2. https://github.com/openlit/openlit — GitHub Repo — HIGH — 2,463 stars，OpenTelemetry-native LLM observability，11 built-in evaluations
3. https://github.com/matrixorigin/Memoria — GitHub Repo — HIGH — 271 stars，Git-for-Agent-Memory，self-governance，backed by arXiv 2604.03927 (April 2026)
4. https://github.com/evilmartians/agent-prism — GitHub Repo — MEDIUM — 347 stars，React trace visualization components，alpha release
5. https://arxiv.org/abs/2604.03927 — arXiv Paper — HIGH — MatrixOne MVCC version control system foundation for Memoria