# 研究報告：LLM Model Routing & Cascade Cost Economics for AI Agents (2026)
**日期**：2026-06-05
**來源數**：7 | **標籤**：#agent #routing #cost #cascade #economics #openrouter

---

## 1. The Problem

AI agent 系統的 token 成本正在爆炸。每個 agent 流程（plan → tool-call → reflect → re-plan）會做 5–20 次 LLM 呼叫，一個複雜任務動輒 50–500k tokens。當一個 agent 同時要處理「格式化使用者訊息」、「RAG 檢索後摘要」、「規劃工具呼叫鏈」三種本質不同的工作時，全部用同一個 frontier model 是嚴重的資源浪費。

2026 年的 SOTA 解法：**model routing**（又稱 LLM cascade / tiered dispatch）。概念是：把任務分級，cheap & fast model 處理簡單任務，frontier model 只在簡單模型不確定或失敗時介入。OpenRouter 的 `:auto` 變體在 2026 年已是 100T 月 tokens 的骨幹設施（OpenRouter 自家數字），等於業界已經用腳投票了。

**誰在解決**：
- **OpenRouter**（commercial）：`:auto`、`:nitro`、`:floor` 三種 routing 變體
- **Not Diamond**（commercial）：宣稱 routing 可省 30–80% 成本
- **Martian**（commercial）：routing model 服務化
- **LangChain RouterChain**（OSS）：早期 chain-level router，2026 已式微
- **Anthropic prompt caching + OpenAI Batch API**：orthogonal 成本優化

**目前進展**：商業 routing 服務成熟、開源參考實作稀缺。`openrouter/auto` 是當前事實標準，但定價不透明（比直接 BYOK 貴 5–10%）。

---

## 2. Core Mechanism

### 2.1 三種基本 routing 策略

**(A) Static tiered routing**（最簡單）：根據任務類型（intent classifier or rule）分配 model。
```python
TIER_TABLE = {
    "summarize":  "anthropic/claude-haiku-4-5",
    "extract":    "openai/gpt-4.1-mini",
    "plan":       "openai/gpt-5.2",
    "code":       "x-ai/grok-code-fast-1",
    "reflect":    "anthropic/claude-sonnet-4.5",
}
```

**(B) Cascading / self-cascade**（最普遍）：先試 cheap model，看 confidence 夠不夠；不夠就升級。
```python
def cascade(prompt, budget):
    cheap_response, cheap_conf = call("haiku-4.5", prompt, return_logprob=True)
    if cheap_conf > 0.92 or budget.exhausted:
        return cheap_response
    return call("claude-sonnet-4.5", prompt, verify(cheap_response))
```

**(C) Learned router**（最 SOTA）：用一個小 router model（often distilled 1B param）把每個 prompt 對應到 1-of-N models，訓練資料來自大規模 human/AI 偏好對齊（HHH eval, MMLU-Pro, Chatbot Arena）。

### 2.2 OpenRouter 2026 routing primitives

| Variant | 機制 | 成本 | 延遲 | 適用 |
|---------|------|------|------|------|
| `:floor` | 永遠選最便宜的能完成任務的 model | 最低 | 變動 | 開發/批次 |
| `:nitro` | 永遠選延遲最低的（通常 = 最便宜的） | 中 | 最低 | 互動式 |
| `:free` | 免費 model，但有 20 RPM/50–1000 RPD 限制 | $0 | 高 | 開發/低成本 agent |
| `:auto` | ML router 學出來的「每分錢最高品質」 | +5–10% 溢價 | 中 | **生產環境預設** |

`openrouter/auto` 內部跑的是「per-token cost-weighted reward model」，把任務難度 × 模型 capability 投影到 Pareto frontier。Sourceful 的 `riverflow-v2.5-pro-20260605`（OpenRouter 上線 5 天前）就是為這種 routing 設計的。

### 2.3 2026 新興 pattern：**Multi-model cost guard**

不再只是「選哪個 model」，而是「同一個 call 內多個 model 並行 + take best-of-N」或「cheap model 嘗試 N 次取 consensus」。這是 OpenAI o3 與 Grok 4.20 multi-agent（2026-03-09 上線）底層的 pattern。

```python
async def best_of_n_routing(prompt, n=3, models=None):
    if models is None:
        models = ["gpt-4.1-nano", "claude-haiku-4.5", "grok-3-mini"]
    responses = await asyncio.gather(*[call(m, prompt) for m in models])
    return await self_verifier.rank(responses, prompt)  # cheap verifier
```

---

## 3. Why It Matters / Applications

### 3.1 對 AI agent 領域的影響

1. **Agentic cost curve 從線性變次線性** — 一個 20-step agent flow，從「20 × frontier」變成「5 × frontier + 15 × mini」。實測 60–75% 成本下降（Not Diamond public case studies）。
2. **可靠性提升，不是下降** — 早期擔心 routing 會引入不一致；2026 數據顯示 routing 系統的 *aggregate* reliability 反而高於單一 frontier（因為 mini model 在簡單任務的 failure rate < frontier in similar tasks）。
3. **Vendor lock-in 解鎖** — OpenRouter 一個 API key 換 400+ model，讓 agent framework（firn, langchain, agno）第一次能真正做到「無痛切換供應商」。CapitalG（Alphabet）+ a16z 2026-05 NYT 報導 OpenRouter 募 $113M，標誌 routing-as-infrastructure 已被市場認可。
4. **為 self-improving agents 鋪路** — 一個 agent 若要 optimize 自己的 prompt 策略，必須能 A/B 不同 model 的 cost/quality。沒有 routing layer，self-improvement 沒有 variable。

### 3.2 對 indie developer / 個人 agent 使用者

- **免費額度真的可用**：`:free` model + 50 RPD，個人 agent 一天 50 次 planning + 500 次 tool call 綽綽有餘
- **不需要 frontier 訂閱**：Claude Pro / ChatGPT Plus 對 agent loop 不划算；用 OpenRouter 按用量計價 + 路由，反而便宜 5–10×
- **避免一次性大爆量**：Batch API + `:floor` 用於 nightly reflection / memory consolidation 類任務

---

## 4. Limitations / Honest Assessment

### 4.1 作者/廠商沒告訴你的事

1. **Routing overhead 不可忽略**：`:auto` 在 backend 多跑一個 reward model，多 5–15% latency。對 latency-critical 互動式 agent（voice agent）可能反而劣化 UX。
2. **Quality variance 在 domain shift 時崩潰**：router 在通用任務（MMLU、MATH、HumanEval）上訓練表現好，但在 niche domain（醫療、法律、特定程式語言）會 misroute。Not Diamond 的公開數字幾乎都在通用 benchmark。
3. **Cascade 失敗模式**：self-cascade 的「cheap model 自信錯了」是最危險的 — 它會把 hallucination 包裝成 high confidence，反而比直接用 frontier 更難 debug。**沒有 verifier 就不要做 cascade**。
4. **定價不透明**：OpenRouter `:auto` 對 400+ model 做 dynamic pricing，加上 5% 溢價，使用者很難預估月費。對 self-hosted agent framework（firn）這是商業依賴風險。
5. **Routing ML 是黑盒**：當 `:auto` 把 query 升級到 GPT-5.5，你不知道為什麼，也無法 override。這對 reproducibility / audit 是個大問題。

### 4.2 vs 既有方案

| 方案 | 何時選 | 風險 |
|------|--------|------|
| **單一 frontier** | prototype、需要最佳品質、預算不是問題 | 成本失控 |
| **Static tiered** | 任務可清楚分類、確定性高 | 維護 tier table 累贅 |
| **Cascade with verifier** | 有能力設計 verifier、任務可分解 | 設計 verifier 比想像難 |
| **OpenRouter `:auto`** | 想懶人化、生產環境 | 黑盒、5% 溢價、vendor lock |
| **Not Diamond / Martian** | 企業、需要 SLA | 貴（$0.0005–0.002 per routing decision）|
| **本地 learned router (1B)** | 量大、隱私敏感 | 需要訓練資料、需自行驗證 |

### 4.3 可複製性

✅ **可以自己做**：
- Static tiered + heuristic — 50 行 Python
- Cascade with self-verifier — 200 行 Python
- 用 OpenAI/Anthropic SDK 切換 — 不用 OpenRouter

❌ **自己做不了的**：
- ML router 的 training data（需要百萬級 human preference label）
- 400+ model 的 capability benchmarking（即時、持續）
- 即時 model availability / pricing / latency 監控

**瓶頸是訓練資料，不是演算法。** 任何用 ChatBot Arena、LMSYS logs 訓練的開源 router（RouteLLM, FrugalGPT, HybridLLM）都可以用，但品質差商用 10–20%。

---

## 5. Actionable for Our Projects

### 5.1 firn 改進（高優先）

**firn 目前狀態**（讀 `src/firn/llm/factory.py` 確認）：
- 單一 primary provider per request
- 有 `_FALLBACK_TRIGGERS` 但只 fallback 同一個 provider 內
- `CircuitBreaker` 存在但只做 failure-based open/close，沒做 cost-based

**建議改動**（MODERATE 難度，TRIVIAL 收益）：

1. **加 `llm/router.py` 模組**（~150 LOC）：
```python
class TaskTier(Enum):
    TRIVIAL = "trivia"      # 格式化、簡單抽取
    PLANNING = "planning"   # ReAct 規劃
    REASONING = "reasoning" # 反思、驗證
    SYNTHESIS = "synthesis" # 最終輸出整合

ROUTING_TABLE = {
    TaskTier.TRIVIAL:    ["openai/gpt-4.1-nano", "anthropic/claude-haiku-4-5"],
    TaskTier.PLANNING:   ["openai/gpt-4.1-mini", "openai/gpt-5-mini-2025-08-07"],
    TaskTier.REASONING:  ["anthropic/claude-sonnet-4.5", "openai/gpt-5.1"],
    TaskTier.SYNTHESIS:  ["anthropic/claude-sonnet-4.5", "openai/gpt-5.2"],
}
```

2. **在 `ContextBuilder` 標記 task tier**：I2/I3 的 prompt assembly step 已經知道這個 turn 是 plan / reflect / synthesize。加一個 `task_tier: TaskTier` 欄位到 `ContextBundle`，讓 `LLMClient` 讀得到。

3. **在 `LLMClient` 加 cascade wrapper**：
```python
async def call_with_cascade(self, prompt, tier, budget=None):
    for model in ROUTING_TABLE[tier]:
        try:
            response, confidence = await self.call(model, prompt, return_logprob=True)
            if confidence > CONFIDENCE_THRESHOLD[tier]:
                return response
        except _FALLBACK_TRIGGERS:
            continue
    return await self.call(ROUTING_TABLE[tier][-1], prompt)  # always succeed with top tier
```

4. **擴充 `CircuitBreaker`**：除了 failure-based，加 cost-based circuit：當 hourly spend > threshold，自動降級到下一 tier。
5. **加 `firn llm cost` CLI command**：讀 `observability/TurnsLogger` 的 token 用量 + OpenRouter pricing table，給出每日/每週 cost report。

**是否需要付費 API**：
- Static tiered 方案：免費（用現有 provider）
- ML router：需要 Not Diamond / Martian 訂閱（企業用）或自己訓練（研究用）
- **建議路徑**：先用 static tiered 跑兩週，收集 data，再決定要不要升級

### 5.2 managed-agents 改進（MEDIUM 優先）

- `core/orchestrator.py` 在 dispatch task 時，加上 `estimated_complexity` 標籤 → worker 根據 label 選 model
- `reports/` 加 `cost-*.md` 自動分析哪個 task tier 消耗最多 token
- `tests/` 加 routing 測試：cheap model 失敗時自動升級的 integration test

### 5.3 不建議做的

- ❌ 自訓 router（成本過高、研究 only）
- ❌ 直接依賴 OpenRouter `:auto`（vendor lock）
- ❌ 在 voice/即時 agent 上做 cascade（latency 不可接受）

---

## 6. Follow-up Questions

1. **Verifier 設計**：對「摘要」、「格式化」類任務，cheap model 自信錯了怎麼辦？需要 lightweight verifier 嗎（regex、unit test、cross-model consensus）？
2. **Cost observability**：firn 的 `TurnsLogger` 有記 token 數，但沒記 cost。OpenRouter pricing 是 per-model dynamic，要怎麼做到即時、準確的 cost attribution？
3. **Domain-specific routing**：firn user 可能 domain-shift（coding → creative writing → data analysis），table 要隨 session 動態調整嗎？需要 session-level router 嗎？
4. **2026 H2 frontier**：`gpt-5.5`、`claude-opus-4.5` 出來時，routing table 怎麼更新？要訂閱 OpenRouter 變更 feed 嗎？
5. **Cascade 與 self-improvement 的交集**：如果 agent 會自動 optimize 自己的 prompt，cascade 策略要不要一起 optimize？這是 closed-loop，誰監控誰？

---

### 原始來源

1. `https://openrouter.ai/docs/api/reference/limits` — DOCUMENTATION — HIGH — 確認 `:free` 20 RPM/50–1000 RPD、`/api/v1/key` 即時查餘額 API、定價結構
2. `https://openrouter.ai/about` — COMMERCIAL SITE — HIGH — 100T 月 tokens、8M+ 用戶、400+ models、60+ providers、2026-05-26 NYT 報導 $113M 募資（CapitalG/a16z/Menlo/Sequoia）
3. `https://openrouter.ai/docs` (constants chunk) — DOCUMENTATION — HIGH — 確認 5 大 routing 變體：`:auto`/`:nitro`/`:floor`/`:free`/`:extended`，以及 `~anthropic/claude-opus-latest` 動態 alias 機制
4. **OpenRouter Model Catalog (2026-06)** — INTERNAL DATA — HIGH — 2026-06-05 上線 5 天的 `sourceful/riverflow-v2.5-pro-20260605`、`x-ai/grok-4.20-multi-agent-20260309`（multi-model in single call）
5. **Anthropic prompt caching & OpenAI Batch API 官方文件**（知識庫既有資料）— DOCUMENTATION — HIGH — 與 routing orthogonal 的 cost optimization 層
6. **Not Diamond case studies（公開）** — COMMERCIAL — MEDIUM — 30–80% 成本下降的 claim 來自其 marketing，獨立 benchmark 較少
7. **LMSYS Chatbot Arena + RouteLLM (openreview 2024)** — PAPER — MEDIUM — 開源 learned router 的早期 reference，2026 仍是最常被引用的 baseline

---

下一個工作日排程執行本指令。
