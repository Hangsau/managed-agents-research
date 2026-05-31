# 研究報告：Agent 自我糾錯與反思機制
**日期**：2026-05-31
**來源數**：10 | **標籤**：#agent #self-correction #reflection #self-improvement

---

## 1. The Problem

為什麼這個問題重要？誰在解決它？目前進展到哪？

LLM-based agent 在執行多步驟任務時，犯錯是常態而非例外。錯誤來源多元：規劃偏差（planner hallucinates）、工具調用失誤（wrong API params）、context 遺忘關鍵前提、或純粹的推理漏洞。沒有自我糾錯機制的 agent，第一次失敗等於任務失敗。

這個領域的核心張力在於：**LLM 無法直接修改自己的權重**——它們只能在當前 context 內修正。因此「自我糾錯」變成了「如何有效利用語言反饋，讓同一個模型在下次嘗試時避開上次的錯誤」。

主要研究者/機構：
- **Reflexion**（NeurIPS 2023）— Noah Shinn et al.，哈佛/史丹佛，首創語言強化學習框架
- **DMAD**（ICLR 2025）— 多智慧體辯論中「心理定勢」問題的突破
- **SWE-agent / DM-Code-Agent** — 程式碼維護領域的自我糾錯實作
- 生態系：LangGraph、AutoGPT、CrewAI、Microsoft Semantic Kernel 都在實作各自的糾錯 loop

---

## 2. Core Mechanism

核心方法是什麼？

### 2.1 Reflexion — Verbal Reinforcement Learning

Reflexion 的核心洞察是：**把強化信號翻譯成語言（verbal），而不是純獎勵值**。

```
Actor (LLM) → 執行任務 → 產生軌跡 (trace)
     ↓
Evaluator → 根據環境回饋（成功/失敗）打分
     ↓
Reflection Agent → 分析失敗軌跡，生成「口語化自傳」（verbal reflection）
     ↓
記憶模組（Shallow Episodic / Deep Semantic）→ 儲存 reflection
     ↓
下次執行時 → 從記憶中檢索相關 reflection，注入 context
```

關鍵設計：`ReflexionStrategy` 有四種——NONE、LAST_ATTEMPT、REFLEXION、LAST_ATTEMPT_AND_REFLEXION。研究發現 REFLEXION 策略在 AlfWorld（決策）和 HotPotQA（推理）上顯著優於基線，特別是在 **LAST_ATTEMPT_AND_REFLEXION** 組合時。

### 2.2 DMAD — Diverse Multi-Agent Debate（ICLR 2025）

傳統 Multi-Agent Debate（MAD）讓多個 agent 互相辯論，但**所有 agent 用同樣的思考策略**（如同樣是 Chain-of-Thought），這導致「心理定勢」（mental set）——他們會集體卡在同一個錯誤推理模式裡。

DMAD 的核心創新：每個 agent 被賦予**不同的推理方法**（IO、CoT、DDCoT 等），讓錯誤可以被不同視角檢視。

```
Agent-IO (Input-Output thinking)  ─┐
Agent-CoT (Chain-of-Thought)       ─┼─→ 辯論回合 ─→ 收斂共識
Agent-DDCoT (Diverse CoT)          ─┘
```

實驗顯示：即使 DDCoT agent 單獨準確率高於 IO agent，**三者的辯論過程**讓所有 agent 的最終準確率都提升了。關鍵在於不同推理風格之間的「視角碰撞」。

### 2.3 Self-Healing Web Agent（最新 repo，2026-05-25）

針對 UI 操作自動化場景：當按鈕選擇器失效（CSS 改變、元素消失），傳統 agent 就卡住了。Self-healing agent 的做法：

```
錯誤發生 → Playwright 截圖 + DOM 分析 → 找出新路徑 → 重試
```

不走傳統的「再問一次 LLM 看看怎麼辦」，而是**結構化錯誤分類** + **領域特定的修復策略**。這種 hybrid 架構（LLM + 確定性修復腳本）在生產環境更可靠。

### 2.4 Cognitive Observability — Styxx（無 LLM 的自我監控）

一個正交的重要方向：**如何在不依賴額外 LLM 判斷的情況下，檢測 agent 行為是否異常？**

Styxx 的做法：用純統計 heuristics（logprobs 分佈、相位檢測）在 API 層拦截任何 LLM call，輸出：
- `phase4_late.predicted_category` — 當前輸出是 'reasoning' | 'refusal' | 'fact' | etc.
- `gate` — 'pass' | 'warn' | 'fail'

9-for-9 on K=1 phase transition（意思是對 hallucination 的檢測在特定條件下高度準確）。**不需要 LLM 就能做到**，這對資源受限場景極為重要。

### 2.5 記憶系統 — Kyros

Kyros 將 agent 記憶分為三層，配合生物學啟發的衰減曲線：

| 類型 | 內容 | 衰減 |
|------|------|------|
| Episodic | 具體事件（上次任務怎麼失敗的）| Ebbinghaus 曲線 |
| Semantic | 抽象事實（某 API 的正確用法）| 慢衰減 |
| Procedural | 操作步驟（如何重啟服務）| 最穩定 |

還有**自動矛盾檢測**（ Belief Propagation）——當新資訊與已有記憶衝突時，系統自動標記而非靜默覆寫。

---

## 3. Why It Matters / Applications

這個進步意味著什麼？對 AI agent 領域的影響。

### 直接影響

**1. 任務可靠度從「碰運氣」變成「可改進」**
沒有 self-correction 的 agent，能力上限就是「第一次就做對」。有了 Reflexion-style loop，能力上限變成「從每次失敗中學習」——這是根本性的躍升。

**2. 生產環境可用性**
Self-healing 機制讓 agent 不再是「跑跑看，錯了就重來」的玩具。DM-Code-Agent 的 JSONL trace + replay 讓開發者可以**審計每一個失敗**，而不是對著黑盒 log 猜測。這是企業採用的前提。

**3. 資源效率**
Styxx 展示了**不需要 LLM 也能做observability**——在 edge 部署或高流量場景，這省下的成本可觀。

### 應用場景

- **程式碼維護 agent**：Reflexion + Critic 讓 agent 能檢視自己產出的 patch，發現明顯錯誤後自我修正
- **RAG retrieval**：self-correcting retrieval（pertrai1/eslint-plugin-llm-core 的前身）讓問答系統能對抗 hallucinated facts
- **多智慧體協調**：DMAD 的多样化推理視角可以防止整個 swarm 集體誤判
- **長期任務**：Kyros 的 episodic memory 讓 agent 能跨 session 記住錯誤模式

---

## 4. Limitations / Honest Assessment

作者坦承的限制 + 我們的獨立評估。

### Reflexion 的限制（NeurIPS 2023 原文承認）
- **語言強化學習的信號是稀疏的**：只有成功/失敗二值信號，沒有細粒度的 credit assignment
- **reflection 可能過擬合**：如果失敗模式是系統性的，self-reflection 只會強化錯誤的方向
- **記憶衰減問題**：舊的 reflection 可能在新情境下誤導 agent
- **只在封閉環境有效**：AlfWorld、HotPotQA 是確定性環境，真實世界會有 noise

### DMAD 的限制
- **計算成本線性增加**：每多一個 agent 就多一次 LLM call，延遲和費用都翻倍
- **「多樣性」本身是個設計問題**：DDCoT、IO、CoT 的區分需要人工定義，模型無法自己發現更好的推理策略組合
- **收斂保證不足**：沒有理論證據證明辯論會收斂到正確答案

### Self-Healing Web Agent 的限制
- **領域強相關**：Playwright + DOM 分析的修復策略無法迁移到其他工具鏈
- **依賴結構化錯誤回饋**：若錯誤無法被結構化分類（例如 LLM 推理錯誤），此架構無用

### 我們的獨立評估

**可複製性**：Reflexion 是相對容易實作的——只需要一個 evaluator function + 一個 reflection prompt。對有 OpenAI API 的開發者，理論上 1-2 天可以做出 MVP。DMAD 需要更精細的 agent 角色設計，免費方案（Ollama 之類）能否承擔多 agent 辯論的延遲是問號。

**核心問題**：大多數 self-correction 機制都是**對同一個 LLM 的重試**，而不是真正的「修復」。若 LLM 本身有認知盲點（例如系統性誤解某類數學），reflection 無法突破。這是結構性限制，不是工程問題。

**最誠實的批評**（來自 Styxx 作者）：大多數 agent 框架專注於「trace 看起來怎樣」，而忽視「trace 為什麼出錯」。Styxx 試圖回答第二個問題，但代價是需要對每個 LLM API call 做複雜的 logprob 分析。

---

## 5. Actionable for Our Projects

具體可對 firn 或 managed-agents 采取的行動。

### firn 現況分析
根據 managed-agents-framework 的描述：firn 是「SQLite append-only event log + function calling + Playbook pre-defined workflows + host bash execution with guards」的 batch runner。它的 self-correction 目前應該是透過 retry logic / guard checks 實現的。

### 具體行動

**① 引入 Reflexion-style Self-Reflection Loop**（MODERATE難度）
- 對每個 task instance，記錄：attempt trace + success/fail outcome
- 新 attempt 啟動前，查詢相似失敗的 reflection summary
- 實作：`reflection_event_log` table — 存 `task_type`, `failure_signature`, `reflection_text`, `success_count_after`
- 免費方案可行：使用 Ollama 本地模型作為 reflection agent

**② 層級化 Memory System**（MODERATE-HARD難度）
- Kyros 的三層記憶（episodic/semantic/procedural）概念可以借鑒
- 對 managed-agents 來說：Procedural = Playbook snippets；Episodic = task execution logs；Semantic = domain KB
- 先做 episodic（最簡單）：每個 task 失敗後自動生成 2-3 句「教訓」寫入 SQLite

**③ 為 DM-Code-Agent 的 JSONL Trace + Replay 設計取經**（TRIVIAL-低優先）
- 現有 managed-agents-framework 已有 event log，但缺乏 replay 能力
- 加入 `--dry-run` flag，可以對舊 event log 做「只讀重播」用於離線審計
- 對我們內部的 agent 調試、生產問題排查極有價值

**④ Styxx-style 的 lightweight hallucination detector**（RESEARCH-ONLY）
- 不依賴額外 LLM，用 logprob 統計檢測輸出是否可能是 hallucination
- 目前處於學術階段，production-ready 尚需驗證
- 建議：先以實驗性質引入，用我們的 task logs 做 ablation

**⑤ 考慮 DMAD 的多視角推理**（LOW PRIORITY for now）
- 在重大決策（例如任務 planning）時，引入不同推理風格的「影子 agent」
- 目前對 batch runner 場景效益有限，優先級低

---

## 6. Follow-up Questions

未解決的問題，下次研究可追蹤的方向。

1. **Credit Assignment 的精細化**：目前 Reflexion 只有 binary success/fail，有沒有可能引入更細粒度的強化信號（例如每個 sub-step 的正確性）？這影響是否能真正做 automated RLHF。

2. **免費模型能否承擔 Reflexion**？Reflexion 原本用 GPT-4，我們的假設是 Ollama 可以。但本地模型生成高質量 reflection 的能力尚未被系統性測試。建議用 DeepSeek-R1 做一次 ablation。

3. **Kyros 的 belief propagation 實作細節**：它的「自動矛盾檢測」在實際使用中誤報率如何？記憶一致性 vs. 遺忘速度之間如何平衡？這影響我們能否直接拿來用。

4. **Styxx 的 phase transition 理論**：K=1 的 9-for-9 結果是否在開放世界（非 benchmark）同樣成立？這需要在我們自己的 task logs 上驗證。

5. **DMAD vs. Self-Consistency**：後者（多個樣本投票）比 DMAD 更簡單，但是否有同樣的「打破心理定勢」效果？成本效益比較是下一個值得做的實證問題。

---

### 原始來源

https://github.com/noahshinn/reflexion — GitHub Repo — HIGH — NeurIPS 2023 官方實現，Reflexion 框架開山之作，3168 stars，經過同行評審

https://github.com/FareedKhan-dev/all-agentic-architectures — GitHub Repo — HIGH — 35 種 production-grade agentic 架構集合，含 Reflexion、LATS、MemGPT 等， benchmark leaderboard，PyPI 發布

https://github.com/hwfengcs/DM-Code-Agent — GitHub Repo — MEDIUM-HIGH — ~1500 LOC 可審計 Python Code Agent，ReAct + Planner + Reflexion + Critic 模組化實作，含 JSONL trace replay，SWE-bench Lite baseline

https://github.com/MraDonkey/DMAD — GitHub Repo — HIGH — ICLR 2025 論文「Breaking Mental Set to Improve Reasoning through Diverse Multi-Agent Debate」，DMAD 首創，用不同推理方法打破心理定勢

https://github.com/fathom-lab/styxx — GitHub Repo — MEDIUM-HIGH — Cognitive observability，logprob 統計驅動的 hallucination 檢測，pure Python，no LLM required，9-for-9 on K=1 phase transition

https://github.com/Kyros-494/kyros-ai — GitHub Repo — MEDIUM — Memory OS for AI agents，三層記憶（episodic/semantic/procedural）+ Ebbinghaus 衰減曲線 + 矛盾檢測，60 stars，Apache 2.0

https://github.com/pavel493/self-healing-web-agent — GitHub Repo — MEDIUM — Playwright + Qwen 2.5，自修復 UI automation agent，按鈕選擇器失效後自動分析截圖找新路徑

https://github.com/MidasMulli/cognitive-stack-ane — GitHub Repo — MEDIUM — Apple Silicon 上的本地 LLM agent 棧，五層模型架構（Gemma 4 31B GPU verifier），self-correcting memory system

https://github.com/Y-sebaei/agentic-rag-assistant — GitHub Repo — MEDIUM — NestJS + LangGraph.js + pgvector，自糾正檢索（self-correcting retrieval）+ confidence-gated refusal，生產級 RAG

https://github.com/pertrai1/eslint-plugin-llm-core — GitHub Repo — MEDIUM — ESLint rules that catch patterns LLM agents get wrong — 從 linting 角度看 self-correction，概念新穎

---

*下一個工作日排程執行本指令。*
