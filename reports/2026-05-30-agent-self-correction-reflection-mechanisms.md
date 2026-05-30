# 研究報告：Agent Self-Correction & Reflection Mechanisms

**日期**：2026-05-30
**來源數**：7 | **標籤**：#self-correction #reflection #reflexion #critic-gate #self-refinement

---

## 1. The Problem

LLM agent 在複雜任務中，單次 forward pass 的品質往往不足——模型在最初幾個 token 就 commit 到一个框架，之後無法有效回溯。現實任務（代碼維護、數學推理、Agentic RAG）更會遭遇：

- **工具調用失敗**：選錯工具、引數錯誤、環境錯誤
- **幻覺與錯誤推理**：事實性錯誤、邏輯跳步
- **規劃漂移**：長期任務中偏離原始目標
- **驗證缺失**：未檢查輸出正確性就結束

「自我糾錯」是讓 agent 從一次失敗中學習、在下一次嘗試中避免重蹈覆轍的關鍵能力。目前主流方向有四種，各有不同的觸發時機、記憶形式、和學習粒度。

---

## 2. Core Mechanism

### 2.1 Reflexion：失敗 trial → 文字 lesson → episodic memory

源自 Shinn et al. (NeurIPS 2023) *Reflexion: Language Agents with Verbal Reinforcement Learning*。

**核心循環**：

```
嘗試執行 → 評估成功/失敗 → 若失敗：書寫文字反思（lesson）→ 
存入 bounded episodic memory → 下次執行自動注入 lesson → 重新嘗試
```

**DM-Code-Agent 的實作**（`reflexion.py`）最值得參考：

```python
@dataclass(frozen=True)
class Lesson:
    text: str           # 一句話教訓，例如 "don't call grep on binary files"
    source: str = "agent_failure"
    metadata: Dict[str, Any]

class EpisodicMemory:
    def __init__(self, lessons=None, *, max_lessons=5):
        self.max_lessons = max_lessons
        self.lessons: List[Lesson] = []
        # FIFO bounded buffer，超出自動丟棄最舊的

    def add(self, lesson: str, *, source, metadata=None):
        # normalize whitespace，存入 FIFO queue
        ...
        if len(self.lessons) > self.max_lessons:
            self.lessons = self.lessons[-self.max_lessons:]
```

**與傳統 RL 的差異**：Reflexion 不做梯度更新，不訓練模型參數。失敗的「教訓」以文字形式存在 episodic memory，靠 prompt injection 讓 LLM 在下次嘗試時「記住教訓」。因此：
- 不需要額外訓練成本
- 免費模型（Ollama）也能跑
- lesson 是 human-interpretable 的

**適用時機**：任務有明確成功/失敗信號（test pass/fail、verifier 輸出），且錯誤類型可被總結為一句話。

---

### 2.2 Reflection（Generate → Critique → Refine）

與 Reflexion 不同，Reflection 不等失敗才觸發——它在生成階段就主動引入批評者（Critic）。

**流程**：
```
生成草案 → LLM-as-Judge 依據結構化 rubric 批評 → 
根據批評重寫 → 重複 N 次或直到 Critic 滿意為止
```

**all-agentic-architectures 的 Reflection 架構**（cell 說明）：

> *When you ask an LLM to generate, the model commits to a particular framing in the first few generated tokens. From that point on, every subsequent token conditions on the choices already made. The model can't easily back up and reconsider. The fix: treat the LLM as both author and editor — separate the generation mode from the critique mode.*

**關鍵設計原則（deterministic-picker）**：
- Critic 輸出**類別型判斷**（pass/fail，問題類型 enum），而非分數
- Python 根據類別信號決定是否接受、是否繼續重寫
- 避免 LLM-as-Scorer 的 flat-band pathology（模型傾向輸出中等分數，難以區分好壞）

**適用時機**：生成品質比延遲重要——代碼生成、技術寫作、多約束推理、長文本回答。

---

### 2.3 Chain-of-Verification（CoVe）：消滅幻覺的四人原則

針對事實性幻覺（列表、引用、統計數字），**CoVe** 的洞見是：

> *一致性偏見——模型在回答驗證問題時，若能看到自己之前的答案，會傾向同意自己（即使錯誤）。修復方法：在驗證階段隱藏原始答案，讓模型將每個驗證問題當作獨立事實查詢。*

**流程**：
```
產生 baseline 答案 → 從答案中抽取具體聲明（claims）→ 
為每個 claim 規劃驗證問題（不看 baseline）→ 
獨立回答每個驗證問題 → 比對：一致保留，衝突修訂
```

all-agentic-architectures 的實現細節：
- Qwen 在幻覺檢測上表現良好（主動拒絕）
- Llama 3 在測試中 catch 了 3 個錯誤
- Qwen 3-Thinking 預設用於推理階段

---

### 2.4 Self-RAG：每個文件的反思 token

Asai et al. 的 Self-RAG 與 CRAG 不同，是**文件級別**的質量控制。

**三種 reflection token**：
- `is_relevant`：這個文件是否回答了問題？
- `is_supported`：引用這個文件的內容是否事實有根據？
- `is_useful`：整體有用性信號

每個都是 3-way categorical（`fully_X` / `partially_X` / `not_X` 或 `no_X`），**不用數字分數**。

**Python 組合 keep/drop**：
```python
def _compose_keep(state):
    return [
        doc for doc in state["retrieved_docs"]
        if doc["reflection_token"] in ("fully_supported", "partially_supported")
        # 配合 is_relevant 和 is_useful 的額外過濾
    ]
```

all-agentic-architectures 的觀測：Self-RAG 預設只 keep 1/4 的文件；當文檔與 query 不匹配時，keep 率是 0/4（坦承差距 ✅）。

---

### 2.5 Critic Agent：peer-review gate

DM-Code-Agent 的 CriticAgent 是**接受閘門（gate）而非精煉器（refiner）**：

- 輸出結構化的 pass/fail 裁決 + 具體失敗原因
- 如果拒絕：agent 獲得明確的失敗觀測，可以繼續或 replan
- **不直接修改答案**，區別於 refinement 模式

```python
# DM-Code-Agent: critic.py
@dataclass
class CriticReview:
    verdict: Literal["pass", "fail"]
    reasons: List[str]  # 具體失敗點
    confidence: float
```

---

### 2.6 整合：DM-Code-Agent v2 算法棧

DM-Code-Agent 是目前最完整的生產級實作，預設全部關閉（modules shipped but default-off）：

| 模組 | 觸發時機 | 學習方式 |
|---|---|---|
| **ReAct + Planner** | 每次執行 | 基础 loop |
| **Reflexion** | 失敗 trial 後 | 文字 lesson → episodic memory → 下次 prompt injection |
| **CriticAgent** | 完成前 gate | 結構化 peer-review rejection |
| **Self-Consistency** | 獨立的 N 路試跑 | majority vote / critic score / test pass |
| **Adaptive Replanning** | 錯誤信號分類 | 根據 `tool_error / test_failure / max_steps` 映射到對應 replan 策略 |

**Adaptive Replan Policy 信號地圖**：

| 信號 | 策略 | 意圖 |
|---|---|---|
| `tool_error` | `simplify_plan_skip_failed_tool` | 避免盲目重複失敗的工具調用 |
| `parse_error` | `repair_response_format` | 加入嚴格的 JSON 格式恢復步驟 |
| `test_failure` | `inject_test_failure_context` | 把失敗測試輸出放在下次 plan 中心 |
| `critic_rejected` | `address_critic_feedback` | 把 critic 反饋視為阻斷點而非摘要 |
| `max_steps` | `coarsen_plan_after_budget` | 合併低價值步驟，收斂到更小的修補範圍 |

**Trace + Replay**：
- JSONL append-only trace，每步 plan/tool call/observation 均記錄
- `dm-agent-trace analyze` 回溯失敗階段、是否 replan、是否跳過本地驗證
- `dm-agent-trace diff` 比較兩個 trace（無需 replay 工具）
- Dry replay：在沒有工具的環境重新播放完整步驟序列

---

## 3. Why It Matters / Applications

### 對 Agent 領域的影響

**從「一次機會」到「迭代改進」**：傳統 ReAct 迴圈是「一次機會，沒有回頭路」。Reflexion 系的引入讓 agent 有了**跨 trial 的記憶**——這是從反應式（reactive）邁向自適應（self-adaptive）agent 的關鍵轉變。

**Critic gate 改變了驗收邏輯**：不再由生成 agent 自己決定「做完了沒有」，而是引入了外部裁判。這對於需要嚴格正確性的任務（代碼安全、醫療、財務）特別重要。

**Deterministic-picker 作為普遍教訓**：整個 all-agentic-architectures repo 的核心紀律——讓 LLM 輸出類別，讓 Python 做決定——是減少 LLM-as-Scorer 不穩定性的普遍方案，可在任何需要 quality judgment 的場景復用。

**Trace 讓 self-improvement 可審計**：DM-Code-Agent 的 JSONL trace + trace analysis + trace diff 讓演算法團隊能客觀比較不同策略（Reflexion on/off、Critic on/off）的實際效果，而非靠直覺猜測。

### 具體應用場景

- **代碼維護 agent**：Reflexion 讓 agent 記住「上次這個函數的測試失敗是因為未處理空輸入」
- **Agentic RAG**：Self-RAG 的 per-doc reflection token 讓系統知道「這份文件只是部分相關，答案要從多份文件重組」
- **長程任務**：Adaptive Replanning 的 error-signal map 讓 agent 不再在錯誤方向上重複消耗 step budget
- **事實性問答**：CoVe 隔離驗證問題，消除模型自我一致性偏見

---

## 4. Limitations / Honest Assessment

### 作者坦承的限制

**Reflexion（Shinn et al.）**：
- 依賴明確的 success/fail 信號；沒有客觀裁判的任務（開放式寫作、創意任務）難以觸發
- lesson 的品質取決於 LLM 的反思能力；反思 prompt 的小改動會大幅影響 lesson 品質
- 記憶是 per-run bounded；跨任務的遷移學習仍在研究中

**DM-Code-Agent 作者的坦承**：
- SWE-bench Lite Tier-1 verifier 有噪聲（0% resolved / 72% patch-applied 的反差說明 verifier 問題）
- 真實 ablation 凍結——聲稱的模組效果尚未通過嚴格 benchmark 驗證
- "演算法模組只聲明代碼、測試和離線報告能力，不聲明真實分數提升"

**Self-RAG 觀測**：
- 預設 keep rate 只有 1/4；表示大量相關文件被丟棄，可能反而降低答案品質
- 3-way reflection token 的解析本身依賴 LLM，仍有解析失敗的可能

**CoVe**：
- 額外的驗證步驟讓 token 成本翻倍（生成 → 規劃驗證問題 → 獨立回答 → 修訂）
- 不適用於即時性要求高的任務

### 我們的獨立評估

**可複製性**：Reflexion、Reflection、CoVe 都可以用免費模型（Ollama）+ 標準 prompt engineering 實作，不需要微調或付費 API。DM-Code-Agent 的實作是 Python~1500 LOC，結構清晰，普通開發者可 fork 並修改。

**瓶頸**：
- Reflexion 的lesson品質高度依賴反思 prompt 設計，目前缺乏系統性最佳實踐
- episodic memory 的 bounded size（預設 5）是猜測出來的；沒有 ablation 說明多少最適合
- 沒有客觀成功信號的任務（創意寫作、對話）不適合 Reflexion

**對比既知方案**：
- 與 ReAct：ReAct 是單次嘗試無記憶；Reflexion 在 ReAct 基礎上加了跨 trial 學習
- 與 AutoGPT：AutoGPT 的「如果失敗就說抱歉然後結束」vs Reflexion 的「失敗是下一次嘗試的數據」
- 與 CrewAI：CrewAI 的 role-based 協作 vs DM-Code-Agent 的單 agent + self-correction 模組化

---

## 5. Actionable for Our Projects

### 對 firn 的具體改進

#### 5.1 Reflexion 機制（TRIVIAL，2-3 小時可落地）

firn 目前缺乏「失敗後記住教訓」的能力。可以：

1. 在 `AgentTrial` 或 equivalent dataclass 加入 `Lesson` 和 `EpisodicMemory` 欄位
2. 失敗後呼叫 `reflect(failed_trace) → lesson_text`，存入 bounded list
3. 下次同類任務觸發時，把 lessons inject 到 system prompt

**實作難度**：TRIVIAL。DM-Code-Agent 的 `reflexion.py`（~80 LOC）可以直接參考移植。

**免費方案**：完全可用 Ollama + 簡單反思 prompt。

#### 5.2 Critic Gate（MODERATE，需要修改主 loop）

在 firn 的 agent 主迴圈中加入 critic 閘門：

1. 完成 task attempt 後，呼叫 `CriticAgent(relevant_documents, task_description).review()`
2. 若 verdict = fail，把 critic reasons 當作觀測返回給 agent，觸發 replan
3. 若 verdict = pass，任務結束

**實作難度**：MODERATE。需要找到 firn 中「任務完成」的判斷點。

**免費方案**：可用，Critic prompt 需要調優。

#### 5.3 JSONL Trace 分析工具（TRIVIAL，屬於 infra）

DM-Code-Agent 的 `dm-agent-trace analyze` 是一個很好的參考。firn 的執行的 trace 也需要同類工具：
- 自動標記失敗階段
- 檢測「重複失敗」（同樣 action + error signature × N 次）
- 計算 token 成本

**實作難度**：TRIVIAL。相對獨立的 CLI 工具。

#### 5.4 Self-RAG 的 per-doc reflection token（HARD，涉及 retrieval pipeline 重構）

若 firn 有 RAG 模組，可以引入 `is_relevant / is_supported / is_useful` 三 token 機制。但需要：
- 修改 retrieval 回傳格式，加入 reflection token 欄位
- 在答案生成前加入 Python keep/drop 過濾

**實作難度**：HARD。需要有 RAG pipeline 才能實作。

### 不需要做的

- **不急於引入 Self-Consistency**（N 路獨立試跑 + majority vote）：token 成本高，需要有明顯收益才值得
- **不急於將 Reflexion 設為預設**：DM-Code-Agent 預設全部關閉是有道理的——模組化 ship，確認有效後再開

---

## 6. Follow-up Questions

1. **lesson 的最佳長度**：一句話 vs 一段話的 lesson，哪種在下次 prompt injection 時效果更好？需要小型 ablation（5-10 個任務）驗證。

2. **episodic memory 的觸發策略**：目前是「失敗後」寫入 lesson。那「成功後」是否也值得記錄「為什麼成功」？這可能對複雜任務有價值，但會增加 memory 噪聲。

3. **Critic 的 visible-test vs hidden-test**：Critic 看到原始 patch vs 只看到 agent 最終答案，哪種檢測錯誤的能力更強？DM-Code-Agent 的 research log 坦承這是 open question。

4. **firn 的 error signal taxonomy**：DM-Code-Agent 的 `ReplanSignal` enum（tool_error, test_failure, max_steps...）是從 SWE-bench 失敗模式中歸納出來的。firn 面對的任務類型不同，需要建立自己的 error signal 分類，並對應到 replan 策略。

5. **CoVe 的成本效益**：額外驗證步驟的 token 成本是否值得？適合在什麼場景（事實密集 vs 創意）開啟？也需要 ablation。

---

## 原始來源

https://github.com/noahshinn/reflexion — GitHub Repo — HIGH — NeurIPS 2023 原始論文實作，Reflexion 機制的定義來源

https://github.com/FareedKhan-dev/all-agentic-architectures — GitHub Repo (⭐3403) — HIGH — 35 種 production-grade agent 架構，包含 Reflection、Reflexion、CoVe、Self-RAG、CRAG 的可執行 Jupyter notebook + 對比 benchmark

https://github.com/hwfengcs/DM-Code-Agent — GitHub Repo — HIGH — ~1500 LOC 生產級代碼 agent，含 Reflexion + Critic + Self-Consistency + Adaptive Replanning 的完整實作與 research log；每個設計決策都有 devlog 記錄動機與限制

https://raw.githubusercontent.com/hwfengcs/DM-Code-Agent/main/docs/research-log/02-reflexion.md — Devlog — HIGH — Reflexion 在 DM-Code-Agent 的落地實錄，包含實現細節與為何 ablation 尚未發布的坦承解釋

https://raw.githubusercontent.com/hwfengcs/DM-Code-Agent/main/docs/research-log/04-critic-and-self-consistency.md — Devlog — HIGH — CriticAgent 的設計動機與「gate not refiner」的關鍵設計抉擇

https://raw.githubusercontent.com/hwfengcs/DM-Code-Agent/main/docs/research-log/05-adaptive-and-economics.md — Devlog — MEDIUM — Adaptive Replan Policy 的 error-signal 地圖與 token 經濟學框架（但未實際跑分）

https://raw.githubusercontent.com/hwfengcs/DM-Code-Agent/main/docs/tracing.md — Documentation — MEDIUM — JSONL trace 格式說明，trace analyze / diff / replay 工具鏈；對 firn 的可觀測性建設有直接參考價值

---

*下一個工作日排程執行本指令。*
