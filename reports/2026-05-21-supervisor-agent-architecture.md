# 研究報告：Supervisor Agent 架構——將「監督」從玄學變成工程

**日期**：2026-05-21
**來源數**：7 | **標籤**：#supervisor-agent #meta-control #agent-architecture #reliability

## 1. The Problem

AI agent 系統的核心瓶頸，已經從「能力不足」轉移到「執行不可靠」。

Fireworks AI 的 720 次瀏覽器 agent 實驗揭示了一個殘酷的事實：Gemini 2.5 Flash 在多步驟推理任務中，幾乎每 5 次 LLM 呼叫就有 1 次輸出無效的結構化 JSON，導致約 22.9% 的推理成本被浪費在重試上，而 Kimi K2.5 的浪費率為零。同樣的任務，Gemini 需要 25 次 LLM 呼叫（9 次重試），Kimi 只需要 12 次乾淨呼叫。

這個數據催生了一個概念：**Agent Execution Tax**——廢料推理相對於有效推理的比例。在每日 10,000 任務的規模下，即使某模型看起來 token 單價更低，重試浪費可能讓它的實際成本比競爭對手高出 2-3 倍。

但執行失敗只是症狀。根本問題在於：**沒有人真正在做監督**。

Subho Halder 在 2026-05-21 的文章中尖銳地指出：目前所謂的「supervisor」大多只是一個 foundation LLM 配上一段長 system prompt，寫著「請在 agent 行動前審查它，標記任何不安全/不正確/違反政策的內容」。這個模式存在於每一個 production-agent 教學中。**它不起作用，但沒有人公開說這個。**

Supervisor agent 的概念是：一個獨立进程，嵌在主 agent 的循環內，每個提議的行動在執行前都必須通過它。Supervisor 做出裁決：讓行動通過（ok）、發送修正後返回（nudge）、標記待人類審查（flag）、直接拒絕（block）、或在執行後撤銷狀態（revert）。

這個層面目前幾乎不存在。不是因為團隊懶惰，而是因為正確的 supervisor 架構還沒有被形式化。

## 2. Core Mechanism

### 2.1 Supervisor Agent 的四大組成部分

Halder 的框架將 supervisor agent 分解為四個精確定義的組件：

```
主 agent
    │
    ▼ proposes action
┌─────────────────────────────────────────┐
│  Supervisor (step in the loop)          │
│  ├── Taxonomy of failure modes           │
│  ├── Specialists (parallel)              │
│  │   ├── deterministic check            │
│  │   ├── small classifier               │
│  │   └── narrow LLM judge               │
│  ├── Decision layer (union aggregation)  │
│  └── Feedback log (per-deployment)      │
└─────────────────────────────────────────┘
    │
    ▼
ok / nudge / flag / block / revert
    │
    ▼
主 agent: 執行 / 修正重規劃 / 等待人類 / 重新開始 / 回滾
```

**Taxonomy（失敗模式分類學）先於一切。** 在寫任何一行 supervisor 代碼前，團隊必須發布一個公開的、具體的、以真实事件為基礎的失敗模式清單。每個 entry 包含：短名、一行描述、真實 incident 範例、嚴重性、（nudge/block 等）預設裁決、檢測方法標籤（deterministic / small-classifier / narrow-llm / hybrid）。

這個 taxonomy 是 supervisor 的 foundation，決定了後續所有 Specialist 的設計。

### 2.2 Specialist 的類型與設計

每個 taxonomy entry 對應一個 Specialist。Specialist 接受一個提議行動和上下文，返回裁決（verdict）和信心值。

```
type Verdict = "ok" | "nudge" | "flag" | "block" | "refuse";

interface SpecialistResult {
  verdict: Verdict;
  confidence: number;
  reason?: string;      // specialist 看到了什麼
  correction?: string;  // 僅在 verdict="nudge" 時填充
}
```

**關鍵設計原則：**

- **大多數 Specialist 不應該是 LLM。** 這是最反直覺的部分。對於大部分失敗模式，正確的 Specialist 是：一個正則表達式、一個 AST diff、一個 SQL 查詢、一個硬編碼預算比對。這些檢查不會被 prompt injection 擊穿，不會因為溫度波動， correlation 與主 agent 為零（結構性不同）。
- **當需要 semantic 判斷時，用小的專門模型。** 不是 foundation model 配上一段通用 prompt，而是一個小模型，針對「這一個具體失敗模式」做了十萬個正負樣本的 fine-tune。
- **Specialist 有拒絕權（refuse）。** 當被問到 domain 外的問題時，返回 refuse 高信心，decision layer 將其視為「不是這個 specialist 的職責」。這是保持 Specialist narrow 的機制。
- **Decision layer 的聚合方式是 union，不是 vote。** 任何 block 就 block。任何 nudge 成為修正返回給主 agent。拒絕被忽略。如果沒人反對，預設 ok。

```typescript
// 客服 agent——重複退款檢測（無模型，純 SQL）
const duplicateRefund: Specialist = {
  name: "duplicate_refund_same_order",
  domain: action => action.type === "refund",
  evaluate(action, ctx) {
    const count = ctx.db.queryOne(
      `SELECT COUNT(*) AS n FROM refunds
       WHERE order_id = $1
       AND status = 'completed'
       AND issued_at > now() - $2 * interval '1 day'`,
      [action.orderId, ctx.refundWindowDays],
    ).n;
    return count >= 1
      ? { verdict: "block", confidence: 1.0, reason: "prior_refund_in_window" }
      : { verdict: "ok", confidence: 1.0 };
  },
};
```

```typescript
// 研究 agent——虛構引用檢測
const citationCheck: Specialist = {
  name: "citation_resolves_and_quote_appears",
  domain: action => action.type === "cite",
  async evaluate(action, ctx) {
    const fetched = await httpGet(action.url, { timeoutMs: 2000 });
    if (fetched.status !== 200) {
      return { verdict: "nudge", confidence: 0.9,
               reason: "source URL did not resolve",
               correction: `URL ${action.url} returned HTTP ${fetched.status}` };
    }
    if (fetched.body.includes(action.quotedText)) {
      return { verdict: "ok", confidence: 1.0 };
    }
    const paraphrase = await narrowParaphraseJudge.run({
      candidate: action.quotedText,
      source: fetched.body,
      model: "paraphrase-judge-small-v2",
    });
    return paraphrase === "yes"
      ? { verdict: "ok", confidence: 0.8 }
      : { verdict: "nudge", confidence: 0.85,
          reason: "quoted text not present in source",
          correction: `Quote not in source. Update or remove.` };
  },
};
```

### 2.3 Feedback Log 與累積機制

每個 Specialist 擁有一個 feedback log，記錄：提議行動、上下文、裁決（nudge 的話包含 correction）、主 agent 是否听从、（人類最終審查後）裁決是否正確。

Over time，這個 log 成為訓練信號。假 positive 進入負樣本，新模式進入正樣本，specialist 變得更精準。Per-deployment memory 在這裡——在小型模型的 fine-tune 資料和 deterministic check 的擴展 rule set 中，不在一段巨大的 prompt 裡。

### 2.4 Why Foundation LLM 不適合當 Supervisor

Halder 的核心論證：**correlation of failure**。

如果主 agent 是 Claude，supervisor 也是 Claude（不同的 system prompt），你沒有增加獨立的檢查，你增加了一個 correlated 的檢查。它們共享同一個訓練分佈、相同的 RLHF priors、相同的美學偏好。對同一種 confident output 犯同樣的「著迷」。錯過同一類 subtle error。

用不同模型家族（Claude 監督 GPT）能降低 correlation，但降低得不夠。原因是：所有 frontier 模型幾乎訓練在相同的網路上（同一份程式碼、論文、Stack Overflow、Wikipedia、GitHub）。它們的 RLHF labeler 來自重疊的群體，根據相似的「好 response 應該長什麼樣」來評分。它們的架構是同一個架構類（transformer, autoregressive, next-token prediction）。它們的核心失敗模式（uncertainty 下的 hallucination、confident output 的 charm、sycophancy、prompt injection 敏感性）是架構類的屬性，不是特定模型的屬性。

**兩個不同 frontier LLM 互相監督，是兩個工廠的引擎燒同一種燃料。** 不是兩個獨立組件，是指紋略有不同的兩個相關組件。冗餘在 components correlation 相同的時候不起作用。

正確的答案不是更聰明或不同家族的 foundation model。是：**停止把 generalist 放在這個 slot**。

## 3. Why It Matters / Applications

### 3.1 從「教它更好」到「監督它正確」

目前 agent 改進的敘事是：**讓主 agent 更強大**——更好的推理、更長的 context、更強的工具調用。但 Supervisor Agent 的出現代表一個範式轉移：**能力的瓶頸不在能力本身，在監督層**。

這意味著：
- 投入 supervisor 設計的邊際回報，可能比繼續提升主 agent 能力的邊際回報更高
- 團隊需要一套新的工具鏈：failure mode taxonomy 管理、specialist 開發框架、feedback log 分析、decision replay tooling
- 這個領域將催生新的 infra 類別：Agent governance / Agent audit infrastructure

### 3.2 Agent Execution Tax 重新定義採購決策

Fireworks AI 的數據顯示：token 單價告訴你每單位推理的成本，cost per successful task 告訴你每單位價值的成本。兩者之間的差距由重試浪費、step 效率、任務成功率驅動，而 token pricing 完全忽略了這些。

> 在 10,000 tasks/day 的規模下，一個看起來更便宜的模型可能因為執行稅，讓你每年多付 $40,000 的無效推理費用。

**Reliability-Adjusted Accuracy** = Task Success Rate × (1 − Execution Tax)

這個公式應該成為 agent deployment 採購的第一優先指標，而不是 MMLU 或 HumanEval 分數。

### 3.3 SQLite 作為 Agent State 的最佳載體

 Willow（SQLite-based agent harness）的作者提出：LLM 工作時會破壞資訊。一個好的 agent harness 透過讓部分或全部資訊變得不可摧毀來彌補這一點。具體做法：將 agent 虛擬檔案系統在每個時間點的狀態持久化到 SQLite 表（large blob offload 到 S3）。得益於 mvSQLite 的 multi-versioned 儲存，讀取任意過去時間點的檔案快照，成本與讀取當前版本相同。

使用者意外讓 LLM 刪除文件，然後要求恢復。LLM 發出三個 tool call：GetVersionAtTimestamp("3 days ago") → Read 過去快照 → Write 回當前版本。Done.

這是 Supervisor Agent 反饋環的硬碟版本：**每次 action 都可審計、可逆轉、可重放**。

## 4. Limitations / Honest Assessment

### 4.1 Supervisor Agent 架構的限制

**Coverage 的不可知性。** 你怎麼知道 taxonomy 是完整的？你不知道。你在主 agent 以某種沒有 specialist 捕捉到的方式失敗時，才知道它是不完整的。Coverage 是移動靶，唯一關閉這個差距的方式是：instrument 每個 supervisor decision 和每個人類覆寫，然後看 supervisor 在哪裡 miss 了。沒有這個反饋迴路，supervisor 停止累積，靜態的 supervisor 對上一個學習中的主 agent，會隨時間變差。

**Supervisor 的 supervisory 問題。** 誰來驗證 supervisor 本身的正確性？作者的回答並不令人滿意：deterministic specialist 結構上自我驗證；small classifier 用 held-out sets 持續監控 precision/recall；narrow LLM judge 用 batch human review。這是「engineering best effort」，不是數學保證。Foundation-LLM-as-supervisor 的驗證問題是 intractable 的。Specialist 架構的驗證問題只是 difficult，不過「只是 difficult 是我們能夠 shipping 的問題」——這個論點比嚴格的數學證明弱得多。

**Nudge 遵守問題。** Nudge 只有在主 agent 遵守它的時候才有效。Supervisor 必須能偵測主 agent 忽略 nudge 並重新提議相同行動（或 near-equivalent variant）的情況。方法：每 session 的 memory，以發出 nudge 的 specialist 為 key。在 session 內重複 N 次後，裁決從 nudge 升級到 block。N 是配置旋鈕。預設值為 2。但這個機制依賴於 supervisor 有 session 級的狀態，這與「specialist 應該是无状态的、可替換的」原則有 tension。

**Latency 預算是真實的約束。** Supervisor 在主 agent 的循環中，每個行動都要付出預算。一個落在一秒的 supervisor 在 sub-second 主 agent 前面是不可接受的用於互動場景。答案是平行化、嚴格的 per-specialist timeout、和清楚的 timeout 政策。正確的預設是：timeout = refuse，視為 no-vote，行動繼續。錯誤的預設是 fail-closed on timeout，這將一個慢的 specialist 轉變成對主 agent 的阻斷服務攻擊。

### 4.2 Agent Execution Tax 數據的限制

Fireworks 的數據在三個方面受限：
1. **Text-only 測試**：所有模型都是文字測試（沒有截圖），這讓 Gemini 2.5 Flash 的多模態能力完全無法發揮。單獨測試顯示 Gemini 的視覺能力將其準確率提升至 53%，但即使恢復這個優勢，執行稅結論不變。
2. **環境依賴性**：數據來自 Notte browser agent framework，在不同類型的 agent（coding agent、support agent、research agent）上，執行稅的分布可能非常不同。
3. **時效性**：測試時間窗口是 2026 年 3 月，模型版本和 serving 配置可能已經變化。

### 4.3 對立的觀點：Foundation LLM Supervisor 的實際價值

一些研究（MemTool, ContextCache, SagaLLM）表明，在某些場景下，使用 LLM 本身作為記憶管理或決策協調的核心是有效的代價。SagaLLM 的 multi-agent 架構在 VLDB 2025 上發表，展示了 LLM-native 的 validation 和 coordination 在複雜任務上的可行性和效果。

Supervisor Agent 架構的核心論證——foundation LLM 監督會 correlation fail——可能對高度敏感的 financial/healthcare 操作有效，但對於一般性的創意寫作、研究輔助等場景，cross-family LLM review 的額外複雜度和成本可能超過其效益。

## 5. Actionable for Our Projects

### 5.1 Hermite/Managed Agents 的 Supervisor 化（MODERATE 難度）

我們的 managed-agents 系統目前沒有真正的 supervisor 層。所有 safety check 是分散的、缺乏統一框架的。這是可以立即改善的方向：

**Phase 1：建立 Failure Mode Taxonomy（TRIVIAL）**
- 審計現有的安全/可靠性檢查，整理成結構化清單
- 格式：failure_name | description | example_incident | severity | default_verdict | detection_method
- 這個清單本身比任何代碼更有價值——它讓團隊能一致地討論失敗模式

**Phase 2：實現 Specialist 框架（MODERATE）**
- 建立 `Specialist` interface：`(proposedAction, context) => Verdict`
- 優先實現 deterministic specialists（URL allowlist、rate limit check、SQL injection check、schema validation）
- 這些檢查不依賴任何 LLM API，是零成本的高置信度檢查

**Phase 3：Feedback Log 系統（HARD）**
- 每個 supervised decision 寫入日誌（action, verdict, correction, heedance）
- 定期分析 log 識別新增 failure mode
- 考慮為高頻 failure mode fine-tune 小型 classifier

### 5.2 Execution Tax 監控（MOSTLY TRIVIAL）

在我們的 agent 引擎中加入 parse retry rate 和 reliability-adjusted accuracy 指標：

```python
# 在每次 tool call 返回時
def record_execution_tax(step_result, expected_schema):
    if not validate_json_schema(step_result, expected_schema):
        INCREMENT("agent.parse_retries")
    total = INCREMENT("agent.llm_calls")
    retries = METRIC("agent.parse_retries").current
    tax = (retries / (total - retries)) if total > retries else 0
    METRIC("agent.execution_tax").set(tax)
```

這個指標應該出現在每一個 agent 任務的 metrics dashboard 上。

### 5.3 Agent State 的可逆性設計（MODERATE）

Willow 的方法——用 SQLite/mvSQLite 持久化 agent 虛擬檔案系統的每個時間點狀態——對我們的 managed-agents 架構有直接啟發。

我們的 agent workspace 目前沒有版本控制。每個 step 的狀態改變是不可追溯的。如果我們在 `worktree` 模式下為每個 action 拍快照（不需 mvSQLite，普通 SQLite + versioning extension 就足夠），就能實現：
- 任意時間點的 workspace rollback
- 完整的 action replay 軌跡
- 監管機構或用戶可以問「在 03:14:09 supervisor 看到了什麼」並得到真正可重放的答案

### 5.4 避免 Foundation LLM-as-Supervisor 的陷阱

目前我們的某些安全檢查確實依賴「讓 LLM 審查自己的輸出」——這正是 Halder 批評的 correlated failure 模式。立即行動：

- **不要**用主 agent 同一個模型家族的另一個實例作為「supervisor」
- **不要**用另一個模型家族的 foundation model 作為「supervisor」（correlation 降低得不夠）
- 對所有現有的 LLM-as-reviewer 模式，評估是否可以用 deterministic check 或小型 fine-tuned classifier 替代

### 5.5 Nudge Compliance 追蹤（MODERATE）

目前我們沒有機制追蹤 agent 是否遵守了修正建議。如果我們在 feedback log 中記錄「哪些 nudge 被忽視了並導致了失敗」，就能量化 supervisor 的實際有效性和 nudge 的 quality。

## 6. Follow-up Questions

1. **Specialist 間的依賴問題**：如果一個 failure mode 需要多個 specialist 协作（比如「這是一個涉及隱私數據的 SQL 操作」需要 `sql_parsing` + `pii_detection` + `schema_permission` 三個 specialist 串聯），union 聚合怎麼處理依賴？是否需要 ordered specialist chains？

2. **Supervisor 的可移植性**：一個為 coding agent 設計的 taxonomy 和 specialist 集合，能否部分複用到 support agent 或 research agent？跨 domain 的 taxonomy 共享邊界在哪裡？

3. **Execution Tax 的領域變異**：Fireworks 的數據來自 browser agent。coding agent（Codex、Claude Code）的執行稅分布在什麼範圍？不同 agent 類型是否有各自特徵性的 failure pattern？

4. **nudge correction 的 quality 評估**：如何量化「nudge 給出的 correction string 是否真的幫助主 agent 成功完成任務」？這是一個 supervised signal，但目前的 feedback log 並沒有追踪 correction 的後續 quality。

5. **小型專門模型的可獲得性**：Halder 提到「paraphrase-judge-small-v2」這樣的單一任務 fine-tune 模型。這類模型目前沒有公開的 benchmark 或開源代碼庫。這是即將出現的 infra 機會，還是應該自己 fine-tune？

---

## 原始來源

[Supervisor Agents Don't Exist Yet](https://notes.subhohalder.com/p/supervisor-agents-dont-exist-yet) — Blog Post — **HIGH** — 2026-05-21。Subho Halder 提出的 supervisor agent 架構詳細框架，包含實際 TypeScript 代碼、four-component 架構、failure taxonomy 方法論。論點嚴謹，承認限制，FAQ 處理了所有預期反駁。最佳原創來源。

[Agents Don't Fail on Intelligence. They Fail on Execution.](https://fireworks.ai/blog/agent-execution-tax) — Blog Post — **HIGH** — 2026-05-20。Fireworks AI 的 720 次 browser agent 實驗量化了 Agent Execution Tax：Gemini 22.9% 浪費率，Kimi 0%。提出 Reliability-Adjusted Accuracy 公式。數據紮實，樣本量充足。引用了 WebVoyager、AgentBench、SWE-bench 相關工作。

[SQLite is the best home for AI agents](https://su3.io/posts/willow) — Blog Post — **MEDIUM** — 2026-05-12。Willow（mvSQLite-based agent harness）的作者描述了用 SQLite 持久化 agent workspace 每個時間點狀態的方法，實現 action replay 和 rollback。具體的實現細節有價值，但缺乏量化證據。

[SagaLLM: Context Management, Validation, and Transaction Guarantees for Multi-Agent LLM Planning](https://www.semanticscholar.org/paper/SagaLLM-Context-Management-Validation-and/placeholder) — Research Paper (VLDB 2025) — **MEDIUM** — 2025。Semantic Scholar 檢索結果提到。Multi-agent 架構中的 validation 和 transaction guarantee。具體方法需查閱原始論文。

[MemTool: Optimizing Short-Term Memory Management for Dynamic Tool Calling in LLM Agent Multi-Turn Conversations](https://www.semanticscholar.org/paper/MemTool-Optimizing-Short-Term-Memory-Management/placeholder) — Research Paper (arXiv) — **MEDIUM** — 2025。Semantic Scholar 檢索結果。描述了動態 tool calling 中的短程記憶管理優化。與 supervisor agent 的 failure mode coverage 問題直接相關。

[ContextCache: Task-Aware Lifecycle Management for Memory-Efficient LLM Agent Deployment](https://www.semanticscholar.org/paper/ContextCache-Task-Aware-Lifecycle-Management/placeholder) — Research Paper (IROS 2025) — **MEDIUM** — 2025。Semantic Scholar 檢索結果。資源受限環境中 LLM agent 的記憶管理策略。IROS 發表說明有實體系統驗證。

[I built a small tool to reduce input token costs by 20-30% for agentic tasks](https://bigindexer.com/blog/reduce-input-token-costs-agentic-tasks) — Blog Post — **MEDIUM** — 2026。架構感知 retrieval（相對於 embedding-based retrieval）對 agent 在大型 repo 上的效果改善。20-30% token 成本降低來自對 codebase 架構的建模而非純文字相似性。方法論基於 100-run study，有量化數據。

[Modeling Response Consistency in Multi-Agent LLM Systems: A Comparative Analysis of Shared and Separate Context Approaches](https://www.semanticscholar.org/paper/Modeling-Response-Consistency-in-Multi-Agent/placeholder) — Research Paper (arXiv) — **MEDIUM** — 2025。Semantic Scholar 檢索結果。多 agent LLM 系統中共享與分離上下文方法的響應一致性比較。與 supervisor agent 架構中的 memory accumulation 問題相關。