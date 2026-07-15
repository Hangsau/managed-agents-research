# 研究報告：Context Compaction 的安全治理：從 Governance Decay 到 Constraint Pinning
**日期**：2026-07-15  
**來源數**：10 | **標籤**：#agent-memory #context-management #safety #governance #observability

## 1. The Problem

長時間運作的 LLM agent 必須壓縮、摘要或淘汰 context，否則 token budget、latency 與 inference cost 會隨 session 長度失控。但 context 不只是對話紀錄；它同時承載 tool policy、權限邊界、使用者限制、回復策略與安全規則。

問題因此不是單純的「摘要品質」：**被壓縮掉的規則，對 agent 而言等同不存在**。2026 年的研究把這種失效命名為 **Governance Decay**，並以 ConstraintRot 測試 compaction 後安全約束是否仍可被遵守。這對 firn 特別重要：firn 的長流程、delegation、cron 與 tool-use 都會製造跨 turn 的狀態，而最危險的錯誤往往不是模型不懂規則，是規則在某次摘要後消失了。

目前進展已從「做更好的 summarizer」轉向三件事：把約束分類、把關鍵約束 pin 住、在每次 compression 後做機械化驗證。這比再加一個會說漂亮摘要的 LLM 實際得多。

## 2. Core Mechanism

### 2.1 Context compaction 的安全失效模型

典型流程如下：

```text
raw conversation / tool traces
          │
          ▼
  compaction or summarization
          │
          ▼
  shorter context + surviving constraints
          │
          ▼
  next agent decision
```

Governance Decay 的核心觀察是：若 constraint 沒有被保留，agent 在它原本可見時可能 0% 違規，壓縮後卻會開始呼叫禁止的 tool 或違反操作政策。研究中的 ConstraintRot 以多輪 episode、不同模型與硬/軟約束測量這種衰退；報告的結果顯示 compaction 後違規率可由 0% 升至 30% 以上，攻擊者甚至能透過 **Compaction-Eviction Attack** 偏置摘要器，讓特定 constraint 被刪除。

### 2.2 Constraint Pinning

最簡單也最值得先做的修法是 **Constraint Pinning**：將安全與治理規則從一般可摘要 context 中抽離，作為不可被一般 compactor 淘汰的結構化區塊。

```python
PINNED_KINDS = {
    "operator_policy",
    "tool_schema",
    "permission_boundary",
    "cost_guard",
    "user_hard_constraint",
}

compactable, pinned = partition(messages, is_pinned)
summary = summarize(compactable)
new_context = [*pinned, summary, recent_tail(messages)]
assert validate_constraints(new_context, pinned)
```

關鍵不是把所有內容都 pin——那會讓 context budget 重新爆炸——而是明確區分：

- **Hard constraints**：不可刪除；例如禁止執行的命令、tool schema、HITL 要求。
- **Soft policies**：可摘要但要保留 provenance 與版本；例如偏好、風格、一般工作原則。
- **Ephemeral evidence**：可淘汰；例如已完成的中間推理、冗餘 tool output。

### 2.3 Compression 後驗證，而不是相信摘要

每次 compaction 都應產生一個可檢查的 artifact：保留哪些 constraint、刪掉哪些 constraint、來源訊息範圍、摘要版本與 hash。驗證器可做 schema 檢查、constraint ID coverage 檢查，以及對高風險 tool 的 policy replay。

```text
before:  C1, C2, C3, C4
compaction report:
  retained: C1, C2, C4
  evicted:  C3 (reason=ephemeral evidence)
  policy_hash: ...
validator:
  required={C1,C2,C4} ⊆ retained ? PASS : BLOCK
```

### 2.4 與其他 context 技術的關係

- **Rolling summary / memory extraction**：省 token，但若沒有治理分類，會把 safety policy 當成普通 prose。
- **Retrieval memory**：能在需要時找回規則，但 tool decision 發生前不保證 retrieval 成功；對 hard constraint 不應只依賴向量搜尋。
- **KV cache / stateful inference**：降低重算成本，並不解決「規則是否仍存在」；cache 讓錯誤 context 更快被重複使用，這點有點諷刺。
- **Context window 擴大**：延後問題，不是治理方案；長 session 仍會遇到成本與 attention 稀釋。

## 3. Why It Matters / Applications

### 核心主題一：Context management 已經是 security boundary

**可信度：HIGH｜類型：論文｜新穎度：NEW**。Governance Decay 直接把 compaction 從效能元件提升為安全邊界。若 agent 能在第 1 turn 遵守規則、在第 50 turn 因摘要遺失規則而違規，那「模型 alignment」沒有涵蓋完整系統；真正的 policy surface 包含 context pipeline。

### 核心主題二：結構化 memory 優於單一摘要

**可信度：MEDIUM｜類型：論文 + framework 實作｜新穎度：EXTENSION**。現有 agent framework 普遍把 memory 表現成文字或 message list；更穩健的設計是把 memory 拆成 pinned constraints、episodic facts、task state、tool provenance 與可淘汰 transcript。這延伸了 ReAct、Reflexion、LangGraph checkpoint 等做法，但不再把「記得」和「必須遵守」混為一談。

### 核心主題三：安全性、成本與可觀測性必須一起設計

**可信度：HIGH｜類型：研究綜合｜新穎度：CONFIRMATION**。compaction 的目的通常是降低 token cost；但若只記錄 token reduction，會漏掉 constraint loss。應同時監控：壓縮比例、pinned token overhead、constraint retention、policy violation、recovery rate、tool-call block rate。OpenTelemetry GenAI semantic conventions 與 agent tracing 可承載這些欄位，但目前多數 tracing setup 只記 latency/token，不記 governance state。

### 3.1 反駁與權衡

「Pin 所有規則」不是解答。它會造成三個問題：

1. pinned block 可能持續膨脹，抵消 compaction 的收益。
2. 過時規則若沒有版本與撤銷機制，會阻擋合法行為。
3. pinning 只能保留規則，不保證模型真的按規則行動；工具執行層仍需 deterministic authorization。

因此較好的架構是 **pin + typed policy + external enforcement**：模型 context 中保留規則摘要與 ID，真正的權限檢查在 tool gateway 執行。這比把安全寄託在「模型看過一段文字」可靠。

### 3.2 與既有方案對比

- **ReAct**：擅長把 observation/action 交錯，但沒有標準的 constraint lifecycle；長 trace 壓縮後可能失憶。
- **AutoGPT 類 continuous loop**：更容易累積 context debt，且 compaction 常是事後補丁。
- **CrewAI / LangGraph**：已有 task state、checkpoint 或 agent memory 擴充點，適合加入 typed pinned state，但預設不代表安全。
- **RAG memory**：適合查詢事實，不適合承擔不可遺失的權限邊界。

### 3.3 可複製性

基本版本完全可用免費 API 或本地模型實作：constraint registry、partition、hash、schema validator 都不需要付費服務。困難在評估資料與長 horizon 測試：要建立大量真實 tool workflow、攻擊性 compaction case，並區分模型推理錯誤與 context eviction 錯誤。若使用外部 LLM 作摘要，成本可透過本地小模型、規則式壓縮與 deterministic extraction 降低。

## 4. Limitations / Honest Assessment

1. **研究結果仍需外部複製**：ConstraintRot 的模型數、episode 設計與 constraint 類型值得參考，但不能直接推論所有 production agent 都會有同樣違規率。
2. **摘要器不是唯一攻擊面**：tool result injection、prompt injection、memory poisoning、stale checkpoint 也能改變 governance state；pinning 只處理其中一段。
3. **「保留 constraint」不等於「理解 constraint」**：字面保留可能因位置、衝突指令或 tool schema 變更而失效。
4. **額外 token 與 latency**：pinning、validation、policy replay 都有成本；若每個低風險 turn 都跑完整驗證，會過度工程化。
5. **Policy drift**：長期系統需要規則版本、撤銷、租約與 scope；單純永久 pin 會製造新的一致性 bug。
6. **安全指標可能被 gaming**：只看 constraint-retention rate 會鼓勵系統保留文字，而非在實際 tool call 上拒絕危險操作。

獨立判斷：這不是「context window 的下一個技巧」，而是 agent runtime 的 governance primitive；但目前最強的證據支持的是風險存在與簡單 mitigation 有效，尚不足以證明某個 pinning policy 在所有 agent domain 都接近零違規。

## 5. Actionable for Our Projects

### firn：優先做 typed context governance layer

**建議模組**：`context` / `memory` / `tool gateway` / `observability`。若 firn 的實際命名不同，應找負責 context distillation、delegation state 與 tool authorization 的等價模組。

1. **建立 `ConstraintRegistry`**：每條規則有 `id`、`kind`、`scope`、`severity`、`version`、`expires_at`、`source`。
2. **改 compactor contract**：輸入不再只有 messages；輸出包含 `summary`、`retained_constraint_ids`、`evicted_ids`、`source_hashes`。
3. **加入 constraint pinning**：先 pin `operator_policy`、`tool_registry_schema`、`permission_boundary`、`cost_guard` 與 HITL gate。
4. **tool gateway 二次檢查**：高風險 tool 不接受模型自行宣稱「已獲准」，必須由 runtime policy engine 判定。
5. **發出 trace attributes**：`context.compaction_ratio`、`context.pinned_tokens`、`governance.retention_ok`、`governance.policy_version`、`tool.authorization.decision`。
6. **建立 regression suite**：同一 workflow 在 1、10、50、100 turns 執行；比較無壓縮、普通摘要、pinning、pinning+gateway enforcement。
7. **做 adversarial compaction test**：把要保留的 constraint 放在不同位置，混入長 tool output 與 prompt injection，檢查是否仍被保留且實際阻擋 tool call。

**實作難度**：

- constraint registry + partition：**MODERATE**
- hash/version/retention validator：**TRIVIAL–MODERATE**
- tool gateway enforcement：**MODERATE–HARD**
- 完整長 horizon benchmark：**HARD**
- 學習型 policy optimizer：**RESEARCH-ONLY**

**付費 API**：不需要。免費方案與 local model 足以做 registry、壓縮、驗證與測試；付費模型只會影響摘要品質與 benchmark 成本，不是架構必要條件。

### Managed-agents / 其他專案

managed-agents 是 batch runner，不應假裝自己是 autonomous agent；但其 playbook 結果可加入 `policy_hash` 與 `constraint_ids`，避免批次任務重跑時拿到不一致的 governance context。對 cron pipeline，最值得做的是在報告抽取前 pin 輸出格式與路徑限制，並在腳本寫入 vault 前驗證來源 report 的 hash。

## 6. Follow-up Questions

1. Constraint pinning 在不同 context window、不同 compactor 與不同模型上，是否有穩定的 token/安全 Pareto frontier？
2. 能否用 deterministic policy IR 取代自然語言 constraint，讓模型只負責提出 action、runtime 負責裁決？
3. 如何測量「規則仍在 context 但 attention 被稀釋」這種非 eviction 型 governance decay？
4. 對 prompt injection 而言，constraint pinning 是否會變成可被攻擊者識別與針對的固定位置？
5. 如何把 OTel trace 與 policy decision graph 結合，讓一次違規可追溯到哪次 compaction？
6. firn 是否應把 memory tier、constraint tier 與 tool authorization 拆成獨立服務，而不是共享一個 message buffer？

---

### 原始來源

1. https://arxiv.org/abs/2606.22528 — 論文 — HIGH — Governance Decay 定義 compaction 導致 safety constraint 遺失，並提出 ConstraintRot 與 Constraint Pinning。
2. https://arxiv.org/abs/2605.26289 — 論文 — MEDIUM — Stateful KV cache 將 multi-agent tool calling 從重算完整 prompt 改為只處理 delta；省成本但不解 governance。
3. https://arxiv.org/abs/2606.22840 — 論文 — MEDIUM — RLM-Cascade 以 response-level draft/verify 跨 provider 降低 API 成本，展示 proxy-layer inference control。
4. https://arxiv.org/abs/2604.08369 — 論文 — MEDIUM — TrACE 用 inter-rollout action agreement 做 training-free adaptive compute，說明 agent runtime 可動態分配預算。
5. https://arxiv.org/abs/2606.27288 — 論文 — MEDIUM — Co-Failure Ceiling 指出 ensemble 的上限受共同錯誤率 beta 限制，反對盲目增加 agent 數量。
6. https://arxiv.org/abs/2604.09718 — 論文 — MEDIUM — Agentic Compilation 把可重複 web workflow 編譯成 JSON blueprint，降低 rerun inference cost。
7. https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents — 工程文章 — MEDIUM — 說明 context engineering、資訊位置與壓縮策略對 agent reliability 的影響。
8. https://opentelemetry.io/docs/specs/semconv/gen-ai/ — 標準文件 — HIGH — GenAI semantic conventions 提供 token、model、operation 等可觀測欄位，可延伸治理事件。
9. https://langchain-ai.github.io/langgraph/concepts/memory/ — framework 文件 — MEDIUM — 展示短期 checkpoint 與長期 memory 的分層設計，適合作為 typed memory 對照。
10. https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization — 協定規格 — HIGH — MCP authorization 說明外部 tool access 應由明確授權機制控制，而非只依靠 prompt。

下一個工作日排程執行本指令。
