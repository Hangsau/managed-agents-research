# 研究報告：Code-as-Action Agents 2026 H1 — 從 JSON Function-Calling 到「可執行程式即動作空間」的典範轉移

**日期**：2026-06-29
**來源數**：12 | **標籤**：`#code-as-action` `#codeact` `#executable-code` `#sandbox` `#interpreter-persistence` `#tool-use` `#silent-semantic-failure` `#function-calling` `#long-horizon-agents`

---

## 1. The Problem

2024-2025 主流 agent 動作表達是 **structured JSON / function calling**：每個 tool 是 schema 定義好的 signature，模型在每步推理後輸出一段 JSON 叫 tool。OpenAI 2023-06 推出 function calling、Anthropic 推出 tool use、TogetherAI 推出 JSON mode——這是整個「LLM 工具使用」工業的事實標準。

但 2025-2026 累積了一連串問題：

- **動作表達力受限**：JSON 動作空間是有限 enum + args，要做 1) 跨 tool 條件分支、2) 迴圈 + 累積、3) 動態組合呼叫，模型必須在多輪之間拆解，每次都得「呼叫 tool → 收到結果 → 推理 → 再呼叫」，**token 成本隨步數線性膨脹**。ReAct + Function-calling 跑一個 20 步 GUI 任務可能耗 50k+ tokens。
- **缺乏泛化組合**：每加一個 tool 都要新 schema，整個 JSON schema 隨專案膨脹；新 tool 之間的組合、嵌套呼叫完全要靠模型自己設計。
- **interpreter state 被忽略**：Function calling 不管理 Python interpreter 的 state——每個 step 結束後變數、imports、定義過的 helper 全部丟失。CodeAct (Wang et al., ICML 2024) 證明「可執行程式作為 action」比 text/JSON 動作表達在 M³ToolEval 上**最高高出 20% success rate**，但 2024-2025 業界仍然以 function calling 為主——直到 2026 H1 開始出現大規模遷移訊號。

**誰在解決（2026 H1）：**
- **學術**：`CodeAct` 起源論文 (Wang et al., ICML 2024, arXiv 2402.01030) + 多篇 2026 H1 衍生：`Interpreter Persistence as Training-Time Semantics` (arXiv 2603.01209)、`Confident and Wrong: Silent Semantic Failures` (arXiv 2603.25764)、`SPEAR: Code-Augmented Agentic Prompt Optimization` (arXiv 2605.26275)、`SafeRun: Determinism in LLM Planning` (arXiv 2606.09027)、`AutoRPA: LLM-Driven Code Synthesis for GUI` (arXiv 2605.21082)、`S1-NexusAgent: Plan-and-CodeAct for Science` (arXiv 2602.01550)、`FHIR RL Tool-Calling Agents` (arXiv 2605.14126)
- **業界**：Anthropic Claude Code（action 模式把 shell/grep/curl 全包進去）→ 2026-02 被 John Stawinski 證明 prompt injection → RCE PoC；OpenAI Codex / Cursor / Devin（核心是「執行 shell / patch file」而非 function call）；Cursor 2026-04 推出 Composer-2 內部架構全面轉向 code-as-action
- **開源 infra**：E2B (12.7k★) 成為 de facto code-sandbox standard，Modal / Replicate / Anyscale 跟進；scriptling、jupyter-mcp 等輕量 alternative 浮現

**核心位移（2026 H1 idiom migration）：** 從「**預定義 tool schema + JSON 呼叫**」轉向「**模型直接寫 Python / shell，外部 sandbox 執行**」。Anthropic Claude Code 的 action 模式、OpenAI Codex CLI、Cursor Composer 2 都不是 2025 末的「JSON tool-call 包裝」，而是把整個 shell/Python REPL 當成 action surface——**tool 不再是事先定義的 enum，而是模型動態生成的程式**。

---

## 2. Core Mechanism

### 2.1 動作表達範式的根本差異

```
┌──────────────────────────────────────────────────────────────────┐
│                Tool Use 三個世代 (2023-2026)                       │
├────────────────┬──────────────────┬───────────────────────────────┤
│  Function      │  Hybrid          │  Code-as-Action               │
│  Calling       │  (ReAct + JSON)  │  (CodeAct / Claude Code)      │
│  (2023-)       │  (2024-2025)     │  (2026 H1 dominant)           │
├────────────────┼──────────────────┼───────────────────────────────┤
│ 預定義 schema  │ 預定義 +         │ 模型動態生成 Python/         │
│ + JSON args    │ 少量動態         │ shell/TS 程式                 │
│                │ (e.g. code_int)  │                               │
├────────────────┼──────────────────┼───────────────────────────────┤
│ 每步獨立 state │ 每步獨立         │ interpreter 跨步 persistence │
│ no 變數延續     │                 │ (Python REPL session)         │
├────────────────┼──────────────────┼───────────────────────────────┤
│ Token: O(steps)│ Token: O(steps)  │ Token: O(log steps)          │
│ 無組合          │ 有限組合          │ 完全組合 + control flow      │
├────────────────┼──────────────────┼───────────────────────────────┤
│ 弱 prompt      │ 中 prompt        │ 強 prompt injection          │
│ injection 面   │ injection 面     │ 面 (RCE PoC 2026-02)         │
├────────────────┼──────────────────┼───────────────────────────────┤
│ Vendor API     │ Vendor API +     │ 開源 sandbox (E2B/Modal) +   │
│ 整合簡單        │ 偶爾 code_int   │ agent SDK 雙軌               │
└────────────────┴──────────────────┴───────────────────────────────┘
```

### 2.2 CodeAct 的核心思想（Wang et al., ICML 2024）

```python
# 原始 CodeAct 概念性 agent loop (簡化)
class CodeActAgent:
    def __init__(self, llm, python_executor):
        self.llm = llm
        self.executor = python_executor  # 持久 Python session

    async def step(self, history, observation):
        # LLM 輸出不再是 JSON tool call，而是一段 Python code
        code = await self.llm.generate(
            prompt=f"""
            History: {history}
            Observation: {observation}
            Write Python code to make progress. End with a print()
            statement showing the next observation value.
            """
        )

        # 在持久 interpreter 內執行 → 結果餵回 history
        result, new_state = await self.executor.run(code)
        history.add(code=code, result=result, state=new_state)
        return result
```

**CodeAct 三個關鍵設計：**
1. **統一動作空間**：所有 tool 都是 Python 函式（內建 + 自定義 + import），模型不需要學新 schema
2. **跨步 persistence**：imports / 變數 / 函式定義**跨 turn 保留**，20 步任務不必重述 20 次 import
3. **動態組合**：模型可以寫 `for f in files: process(f)`，把 20 步 JSON 呼叫壓成 1 步程式

**論文實證 (M³ToolEval)：**
- 17 個 LLM × API-Bank benchmark
- CodeAct vs. Text/JSON：success rate **最高 +20%**
- Token efficiency：相同任務，**CodeAct 顯著較少 token**（尤其在 multi-step batch 操作）

### 2.3 Interpreter Persistence 的 Training-Time Semantics (arXiv 2603.01209, 2026-03-01)

**這是 2026 H1 最重要的 code-as-action 論文。** 它把「interpreter state 跨步保留」從 runtime 細節升級為 **training-time semantic**。

```python
# Opaque Knapsack: 2x2 cross-evaluation 設計
# 變項：訓練時 interpreter persistence (P/N) × 部署時 persistence (P/N)

# Persistent-trained model × Stateless runtime
class PersistentTrained:
    def step(self):
        code = self.model.generate()  # 預期變數還在
        return self.executor.run(code, fresh_state=True)
        # → 80% episodes 觸發 NameError: variable not defined

# Stateless-trained model × Persistent runtime
class StatelessTrained:
    def step(self):
        code = self.model.generate()  # 重複定義用過的變數
        return self.executor.run(code, persistent_state=True)
        # → 使用 3.5x 多 tokens（重述前步的計算）
```

**核心發現：**
- **Solution quality 在四種組合下統計上無差異**（任務能不能解，不依賴 persistence）
- **但 token 成本 + stability 差異極大**：
  - Persistent-trained + Stateless runtime → **80% episodes 觸發 missing-variable error**
  - Stateless-trained + Persistent runtime → **3.5x 多 tokens**（模型重複 re-derive 已保留的 state）
- **Takeaway**：「interpreter persistence 不是 runtime scaffold，是 training data 的 first-class semantic」——fine-tuning 用的 SFT traces **必須** encode interpreter state 的管理方式，否則 train/deploy mismatch 直接爆。

**對實作者的意涵：** 用 Qwen3-8B 之類小模型做 SFT 時，如果 trace 用 fresh-interpreter-per-step 收集，部署時要嘛沿用 stateless runtime，要嘛改用 persistent traces 重訓——**不能混搭**。

### 2.4 Confident and Wrong: Silent Semantic Failure (arXiv 2603.25764, 2026-03-26)

**這是 code-as-action 的「批判性反論」——證明「能跑」不等於「對」**。

| Model | Submit rate | Test-verified resolve | Gap |
|-------|-------------|----------------------|-----|
| GPT-5 | 100% | 44% | 56% silent wrong |
| Llama 4 | 99% | 18% | 81% silent wrong |
| Gemini | 70% | 50% | 20% silent wrong |

- **Silent semantic failure**：在 1,750 個 trajectory × 50 SWE-bench Verified task × 重複執行中，發現一個明確失敗模式——**agent 在 buggy task 上五次重複跑都提交 plausible-looking patch，全部失敗**。不是隨機錯誤，是同一個 misinterpretation 系統性重複。
- **占失敗的 68-80%**：Llama 4 的失敗有 80% 是 silent semantic failure；GPT-5 有 68%
- **看不見**：completion-based 監控（submit rate）和 consistency-based 監控（多次跑結果一致）**都看起來健康**，但 agent 正在 confident & consistently wrong
- **Action bias**：給已修好的 bug，模型**仍然編輯那段已正確的 code**——「該不動的時候偏要動」
- **Lightweight pre-edit prompts 無效**：簡單的「先想想」提示詞**沒辦法**關上這個 gap

**直接打到 code-as-action 的痛點：** interpreter persistence 讓 agent 更容易**自信地**做出複雜修改（because 它有完整的 state 可操作），但**自信**不等於**正確**。Silent semantic failure 是 code-as-action 架構的特有失敗類型——function-calling 反而因為動作空間小、每步都可檢查，相對不易陷入。

### 2.5 SPEAR: Code-Augmented Agentic Prompt Optimization (arXiv 2605.26275, 2026-05-25)

把 code-as-action 移植到 **prompt engineering 本身**：

```python
# SPEAR optimizer loop
class SPEAR:
    def __init__(self, llm, sandbox):
        self.tools = {
            "evaluate": self.run_evaluation,   # 在評估集上跑當前 prompt
            "python": sandbox.execute,          # 自由 Python：confusion matrix, error clustering
            "set_prompt": self.update_prompt,  # 寫出新 prompt
            "finish": self.finish              # 收工
        }

    async def optimize(self, initial_prompt):
        # Agent 自主決定何時 evaluate、何時寫 Python 分析、
        # 何時 set_prompt、何時收工
        result = await self.agent_loop(
            prompt=initial_prompt,
            tools=self.tools,
            guardrails=[auto_rollback_on_regression, metric_floor]
        )
        return result
```

**結果 (3 個 industrial judge suite + BBH-7 + GSM8K)：**
- 全部 industrial task 在 primary metric 上**擊敗 baseline**
  - tool-selection judge: κ 0.857 vs 0.359
  - filter-relevance: F1-macro 0.815 vs 0.763
  - 5-class extraction: κ 0.254 vs 0.218
- **BBH-7：SPEAR 0.938 vs GEPA 0.628 vs TextGrad 0.484**
- Ablation：Python tool 移除 → 5-class tool-selection **Δ +0.79 κ**、hardest extraction **Δ +0.35 κ**——**Python tool 是最大單一槓桿**

**Why Python matters:** Long-context LLM **無法**從原始 eval DataFrame 可靠地抽出 class-pair confusion aggregation 等結構化錯誤分析；只有 free-form Python execution 才能做到。

### 2.6 AutoRPA: Distill ReAct → Code (arXiv 2605.21082, 2026-05-20)

**Code-as-action 的「壓縮」用法**：

```python
# AutoRPA: 把 20 步 ReAct trajectory 蒸餾成 1 個 reusable 函式
# Phase 1: translator 把 hard-coded ReAct actions → soft-coded procedure
# Phase 2: builder 用 RAG over multiple trajectories 生成 robust function
# Phase 3: hybrid repair (RPA + ReAct fallback)

# 結果：在多個 GUI 環境
# Token usage 降低 82-96%
# Reusability: 相似任務直接 reuse generated function
```

這把 code-as-action 的核心優勢**token efficiency**量化——同樣任務 ReAct 20 步 vs RPA function 1 步呼叫，token 差距 5-25x。

### 2.7 S1-NexusAgent: Hierarchical Plan-and-CodeAct (arXiv 2602.01550, 2026-02-02)

**專門為 scientific research 設計的 code-as-action 變體**：

```
┌──────────────────────────────────────────────────────┐
│              S1-NexusAgent 雙層架構                      │
├──────────────────────────────────────────────────────┤
│  Outer loop: Global Plan (decide research sub-tasks)  │
│     ↓ (MCP tool orchestration)                        │
│  Inner loop: CodeAct executor (per sub-task)          │
│     - object-reference sparse context (壓縮中間結果)    │
│     - Critic Agent (evaluate complete trajectory)     │
│     - 蒸餾 reusable Scientific Skills                 │
└──────────────────────────────────────────────────────┘
```

- **Decoupling global planning from local CodeAct execution**——解決 long-horizon agent 的「context blowup」問題
- **Object-reference sparse context management**：子任務 context 隔離、中間結果壓縮
- **Closed-loop self-evolution**：execution → critic → distill → reusable skills

實證 SOTA 在 biomini-eval / ChemBench / MatSciBench。

### 2.8 SafeRun: CodeAct + Deterministic Solver (arXiv 2606.09027, 2026-06-08)

**CodeAct 的安全補丁**——把硬約束從 LLM 內部搬到外部 solver：

```
┌─────────────────────────────────────────┐
│   LLM (soft interpretation)             │
│   → 生成 Python-like plan               │
│   ↓                                     │
│   Deterministic solver (hard constraints)│
│   → 強制執行 safety rules                │
└─────────────────────────────────────────┘
```

- 5 個 LLM 實驗
- **Safety score 100%**（vs. PE 79.1%, CodeAct 97.6%）
- 維持 competitive instruction-following score
- 解決 CodeAct 的核心批評：「agent 寫的程式可能違反硬約束」

### 2.9 FHIR CodeAct + RL (arXiv 2605.14126, 2026-05-13)

醫療領域的 code-as-action：

```python
# Multi-turn CodeAct agent on FHIR graph
# 工具：filter, aggregate, traverse
# 後訓練：RL with LLM-Judge execution-grounded rewards
# Qwen3-8B (8B params, cheap) → 77% on FHIR-AgentBench
# vs. o4-mini prompt-based: 50% (並且 larger + more expensive)
```

- **Smaller + cheaper model 透過 RL post-training 打敗 larger + more expensive model**
- CodeAct 是該 benchmark 的 SOTA 框架

---

## 3. Why It Matters / Applications

### 3.1 為什麼 2026 H1 突然加速？

四個獨立訊號在同一個時點聚攏：

1. **Claude Code / Cursor / Codex CLI 全面轉向**：不再用 function-call-only，而是直接執行 shell/grep/edit，**用 code execution 取代 JSON dispatch**
2. **E2B (12.7k★) + Modal sandbox 成熟**：sandbox-as-a-service 把 infra 成本壓到「每小時幾美分」，中小團隊也能跑
3. **Interpreter persistence 找到正解** (arXiv 2603.01209)：SFT trace design 開始 encode state management，train/deploy mismatch 不再是阻礙
4. **Confident and Wrong 暴露 function-calling 的相對優勢** (arXiv 2603.25764)：迫使業界思考「silent semantic failure 監控」

### 3.2 對 AI Agent 生態的影響

**短期 (2026 H2-2027 H1)：**
- **Sandbox infra 會爆發**：E2B / Modal / Replicate 之後會有更多專門「code-as-action sandbox」出現（sandbox-start time < 100ms 是新 baseline）
- **Prompt-injection 攻擊面重新定義**：function-calling 時代攻擊面是「叫錯 tool」；code-as-action 時代攻擊面是「讓 model 寫 malicious code」——2026-02 Claude Code Action RCE PoC 是 early signal
- **Agent monitoring 必須升級**：completion rate / submit rate 不夠，**silent semantic failure 監控**會成新興工具類別

**中期 (2027-2028)：**
- **Hybrid 是常態**：大工具（file edit / git / API call）保持 function-calling 形式；小工具（ad-hoc computation / data wrangling / parsing）走 code-as-action
- **訓練 infrastructure 會跟進**：如果 interpreter persistence 是 first-class semantic，那 SFT 工具鏈需要從「text 收集」升級到「interpreter state-aware collection」
- **Multi-modal 動作空間**：code-as-action 擴展到 vision（OpenCV operations on screenshots）/ audio（whisper + python）/ GUI（pyautogui）等

**對 firn 直接相關的應用：**
- 取代 `ToolExecutor` 的部分 function-calling 動作
- 支援「let agent write Python」模式做 data wrangling
- 解決 multi-tool chaining 的 token 浪費

---

## 4. Limitations / Honest Assessment

### 4.1 來自作者坦承的限制

- **CodeAct (2024) 自己承認**：code-as-action 在「小、純文字、無副作用的 task」上**沒有顯著優勢**——JSON function-calling 對 1-2 步 API 任務仍然更直接
- **arXiv 2603.01209 結論**：interpreter persistence 解決 token efficiency，但**要 SFT trace 跟部署 runtime 對齊**——這對小團隊是額外負擔
- **SPEAR 作者承認**：Python tool 在 5-class extraction 上 Δ +0.79 是**單一 task**，generalization 仍待驗證
- **SafeRun 自己也跑在 5 個 LLM 上**，沒覆蓋所有 frontier model，且 benchmark domain 限定 running planning

### 4.2 我們的獨立批判

| 批評 | 細節 | 來源 |
|------|------|------|
| **Silent semantic failure 是 code-as-action 特有放大風險** | interpreter persistence 讓 agent 更容易**自信**做複雜修改（它看得到完整 state）—— 反而放大 arXiv 2603.25764 的問題。Function-calling 因為動作空間小、每步可檢查，相對不易陷入。 | arXiv 2603.25764 |
| **RCE attack surface 爆炸性擴大** | 2026-02 Claude Code Action RCE PoC 證明：當 shell 是合法 action surface，prompt injection 直接升級到 RCE。Function-calling 時代要「叫 shell tool」需要繞 sandbox 設計；code-as-action 預設就能寫 `os.system()`。 | 2026-02 Stawinski PoC |
| **Small model 不一定 well-suited** | CodeActInstruct 原始 SFT 主要是 Mistral-7B；多數小模型沒有針對 code-as-action 訓練，會出現「寫出語法錯的 Python」、「忘記 import」、「變數命名混亂」等失敗模式。arXiv 2603.01209 的 Opaque Knapsack 用 Qwen3-8B 才勉強撐住 | CodeAct 2024 + arXiv 2603.01209 |
| **Speculative execution 的對偶問題** | Code-as-action 的優勢是 token efficiency，但**每步 sandbox startup + execution 延遲**可能抵銷 token savings。低頻但重的任務反而更慢 | 經驗推論（無直接 benchmark） |
| **Eval gap 嚴重** | M³ToolEval / CodeActInstruct 都偏向 2024 年的 API / database / 程式合成任務；2026 H1 的 RAG / browser-use / GUI / multi-modal 任務**沒有 code-as-action specific benchmark** | 觀察 |
| **「Auto-rollback on metric regression」並非銀彈** | SPEAR 的 guardrail 在 monotone-improving 假設下 work，但 real-world prompt optimization 是**非 monotone**（有時要 degrade 才能後續 climb） | SPEAR 論文未充分討論 |

### 4.3 對比既有方案

| 比較 | CodeAct | Function-calling | ReAct (text thought) | Toolformer |
|------|---------|------------------|----------------------|------------|
| 動作表達力 | Python 任意 | 預定義 enum | 純文字 | 預定義 |
| State persistence | 跨步 ✓ | ✗ | ✗ | ✗ |
| Token efficiency | 高（長任務） | 中 | 低 | 中 |
| Security surface | RCE 風險 | 限於 tool | 無 | 限於 tool |
| 2026 H1 production | Claude Code, Codex | OpenAI 主流 | 教學 | 已淘汰 |
| 可學習性（LLM 預訓練） | 強（Python 在 pretrain） | 弱（schema 特殊） | 強（自然語言） | 中 |

---

## 5. Actionable for Our Projects

### 5.1 firn 短期可做 (TRIVIAL / MODERATE)

**A. **為現有 `ToolExecutor` 加 `code_action` mode (MODERATE)**
```python
# firn/src/firn/tools/executor.py
@dataclass
class CodeActionResult:
    stdout: str
    state_hash: str
    variables_added: list[str]
    duration_ms: int

class CodeActionTool:
    """讓 agent 寫 Python 而不是呼叫預定義 tool"""

    def __init__(self, sandbox: "E2BSandbox | LocalJupyter"):
        self.sandbox = sandbox
        self._state = {}

    async def execute(self, code: str) -> CodeActionResult:
        result = await self.sandbox.run(code, state=self._state)
        # 關鍵：sandbox 必須是 persistent session
        # 跟 arXiv 2603.01209 的「interpreter persistence as first-class semantic」對齊
        self._state = result.state
        return CodeActionResult(
            stdout=result.stdout,
            state_hash=hash(frozenset(self._state.keys())),
            variables_added=result.new_vars,
            duration_ms=result.duration_ms,
        )
```

**B. **Silent semantic failure 監控 (MODERATE)**
```python
# firn/src/firn/observability/silent_failure.py
class SilentFailureDetector:
    """參考 arXiv 2603.25764 監控模式"""

    def __init__(self, test_runner):
        self.test_runner = test_runner

    async def evaluate(self, trajectory: list[Step]) -> bool:
        # 1. 重複跑 N 次
        results = [await self._rerun(trajectory) for _ in range(5)]

        # 2. 計算 submit rate vs test-verified resolve rate
        submit_rate = sum(1 for r in results if r.submitted) / 5
        resolve_rate = sum(1 for r in results if r.passed_tests) / 5

        # 3. 計算 silent failure score
        # submit_rate 高 + resolve_rate 低 = silent semantic failure
        if submit_rate > 0.8 and resolve_rate < 0.3:
            return SilentFailureAlert(
                type="semantic",
                submit_rate=submit_rate,
                resolve_rate=resolve_rate,
                action="flag for human review",
            )
        return None
```

**C. **Train-time / runtime persistence alignment 檢查 (TRIVIAL)**
```python
# 部署時 sanity check：SFT 用的是 stateless or persistent traces？
# 確保 runtime 跟訓練時一致
assert config.sft_persistence == config.runtime_persistence, \
    "Train/deploy mismatch on interpreter persistence (arXiv 2603.01209)"
```

### 5.2 firn 中期可做 (HARD)

**D. **Plan-and-CodeAct 雙層架構 (HARD)**
參考 S1-NexusAgent (arXiv 2602.01550)：
- Outer loop：planner 拆 sub-task
- Inner loop：CodeAct executor 跑每個 sub-task
- Critic：蒸餾 reusable skill

**E. **Self-evolving APE 模組 (HARD)**
參考 SPEAR (arXiv 2605.26275)：
- 把 firn 自己的 system prompt 變成 agent-optimizable artifact
- 用 code-as-action 寫分析腳本（confusion matrix、error clustering）
- 自動 rollback on metric regression

### 5.3 研究 / 實驗

**F. **驗證 silent semantic failure 在 firn 真實軌跡上的比例**
- 重跑 firn 過去 30 天 N 個 task × 5 次
- 統計 submit rate / resolve rate gap
- 預期：跟 arXiv 2603.25764 一致，差距在 20-80%

**G. **Test code-as-action 對 firn 效率的影響**
- 選 5 個 multi-step task
- 比較 function-calling vs code-as-action
- 衡量：token 數、wall time、success rate

### 5.4 安全警示

**H. **絕對不要在 production firn 預設開啟 code-as-action 模式 without sandbox**
- 2026-02 Claude Code Action RCE PoC 已經驗證
- 必須用 E2B / Modal / Firecracker 隔離
- 至少：限制 module 導入（禁 `os`, `subprocess`, `socket`）、限制執行時間（< 30s）、限制 memory

### 5.5 是否需要付費 API？

- **E2B 免費 tier**：可用於 prototyping / 個人使用
- **E2B 付費 tier**：production 需要，~$0.0001/秒 sandbox
- **本地 Jupyter / scriptling**：零成本但需要自己管理安全
- **結論**：firn 規模**可全程免費方案運作**

---

## 6. Follow-up Questions

1. **arXiv 2603.01209 是否會在 2026 H2 出現 training recipe 標準？** 目前 train/deploy mismatch 是 manual check，需要更系統化方法。
2. **Code-as-action 的 silent semantic failure 有沒有更便宜的 detector？** arXiv 2603.25764 用 5 次重跑的成本太高（5x compute），能否用 single-run statistical 指標？
3. **Multi-modal code-as-action 進展？** vision (OpenCV), audio (whisper), GUI (pyautogui) 的 code-as-action extension 在 2026 H2 是否有新論文？
4. **E2B / Modal 之外是否有更好的 sandbox 設計？** Firecracker microVM、gVisor、WASM-based sandbox（Wasmtime）哪個最適合 code-as-action？
5. **Function-calling 和 code-as-action 的 hybrid routing 策略？** 怎麼讓模型自動判斷「這個 task 該用 function-call 還是 code-action」？
6. **RL post-training 對 code-as-action 的增益有多大？** arXiv 2605.14126 在 medical domain 證明 +27%，但其他 domain 還沒充分驗證。
7. **A2A protocol (2026-06-14 報告) + code-as-action 的 intersection？** agent 之間互相傳遞的如果是可以執行的 code，trust boundary 怎麼設計？
8. **Anthropic Fable 5 / Mythos 5 出口管制 (2026-06-12) 對 code-as-action 有什麼影響？** frontier model 變難取得後，code-as-action 的小模型自託管價值是否上升？

---

### 原始來源

1. [arXiv 2402.01030 — CodeAct: Executable Code Actions Elicit Better LLM Agents (Wang et al., ICML 2024)](https://arxiv.org/abs/2402.01030) — 論文 — HIGH — 開山論文，奠定「Python as action space」典範，M³ToolEval +20% success
2. [xingyaoww/code-act — Official GitHub repo](https://github.com/xingyaoww/code-act) — 程式碼 — HIGH — 1.6k★，CodeAct 官方實作 + CodeActInstruct dataset + Mistral-7B fine-tune
3. [arXiv 2603.01209 — Agents Learn Their Runtime: Interpreter Persistence as Training-Time Semantics](https://arxiv.org/abs/2603.01209) — 論文 — HIGH — 2026 H1 最重要的 code-as-action 論文；證明 interpreter state 是 first-class semantic，train/deploy mismatch 會 80% error
4. [arXiv 2603.25764 — Confident and Wrong: Silent Semantic Failures in Coding Agents](https://arxiv.org/abs/2603.25764) — 論文 — HIGH — 1,750 trajectory × 50 SWE-bench Verified；提出 silent semantic failure 概念，占失敗 68-80%
5. [arXiv 2605.26275 — SPEAR: Code-Augmented Agentic Prompt Optimization](https://arxiv.org/abs/2605.26275) — 論文 — HIGH — 證明 Python tool 在 APE 中是最大槓桿（Δ +0.79 κ），BBH-7 0.938 vs GEPA 0.628
6. [arXiv 2605.21082 — AutoRPA: Efficient GUI Automation through LLM-Driven Code Synthesis](https://arxiv.org/abs/2605.21082) — 論文 — MEDIUM — ReAct → RPA distillation 量化 token reduction 82-96%
7. [arXiv 2606.09027 — SafeRun: Enabling Determinism in LLM Planning](https://arxiv.org/abs/2606.09027) — 論文 — MEDIUM — CodeAct + deterministic solver 雙層，safety 100% vs CodeAct 97.6%
8. [arXiv 2602.01550 — S1-NexusAgent: Self-Evolving Agent Framework for Multidisciplinary Scientific Research](https://arxiv.org/abs/2602.01550) — 論文 — MEDIUM — Plan-and-CodeAct 雙層 + object-reference sparse context，科學任務 SOTA
9. [arXiv 2605.14126 — RL for Tool-Calling Agents in FHIR](https://arxiv.org/abs/2605.14126) — 論文 — MEDIUM — CodeAct + RL post-training，Qwen3-8B 77% vs o4-mini 50%
10. [e2b-dev/E2B — Open-source code sandbox for AI agents](https://github.com/e2b-dev/E2B) — 程式碼 — HIGH — 12.7k★，de facto code-sandbox standard，支援 Python/JS SDK
11. [arXiv 2604.21375 — VLAA-GUI: Knowing When to Stop, Recover, and Search](https://arxiv.org/abs/2604.21375) — 論文 — MEDIUM — GUI agent modular framework；code-as-action 在 GUI 領域的延伸
12. [John Stawinski — Trusting Claude with a Knife: Prompt Injection → RCE in Claude Code Action (2026-02-05)](https://johnstawinski.com/2026/02/05/trusting-claude-with-a-knife-unauthorized-prompt-injection-to-rce-in-anthropics-claude-code-action/) — 安全研究 — HIGH — code-as-action 的 RCE PoC 驗證，安全警示

---

下一個工作日排程執行本指令。
