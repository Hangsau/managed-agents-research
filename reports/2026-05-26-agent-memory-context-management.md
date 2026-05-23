# 研究報告：AI Agent 記憶與 Context 管理策略——從事實萃取到生成式記憶

**日期**：2026-05-26
**來源數**：10 | **標籤**：#agent #memory #context-management #retrieval #generative-memory

## 1. The Problem

為什麼 LLM agent 的記憶這麼難？

標準做法是這麼一套 pipeline：用相似度檢索從歷史對話中挖出「事實」，存進向量資料庫，每次回答問題時把這些事實塞進 prompt。這套東西在實驗室 benchmark 上有效，但到了 production 問題一堆：

- **記憶汙染**：不相關的事實會被錯誤檢索出來，汙染回應
- **顆粒度問題**：把對話壓縮成「原子事實」會丟失脈絡；不壓縮則 context window 爆炸
- **無法推理**：只知道「用戶有過敏」但不知道「這與當前任務無關」
- **靜態 schema**：記憶結構是人為定義的，沒有辦法隨 agent 成長自演化

2026 年 5 月的 arXiv 出現了大量新論文（至少 10 篇以上），加上 OpenViking（24k stars）、Letta（22.9k stars）這類生產級 framework，都指向同一個結論：**純 retrieval-based 記憶已經不夠了，field 正在往自適應生成式記憶遷移**。

## 2. Core Mechanism

### 2.1 從 Retrieval 到 Generation：Mem-π

傳統 retrieval-based 記憶的問題在於：它返回的是「static entries」——固定的過去紀錄，經常與當前 context 脫節。Mem-π（arXiv:2605.21463）提出了一個根本不同的做法：

**不是從記憶庫裡找回憶，而是即時生成對當前任務有用的引導。**

```
Agent Context → [Decoupled LLM] → "When to help" + "What to generate"
                                     ↓
                              RL-trained with:
                              - abstain when unhelpful
                              - concise, useful guidance
```

Mem-π 的關鍵設計：
- 一個獨立的小模型負責「何時生成 + 生成什麼」，與下游 agent 的主模型分開
- 用 RL objective 同時訓練「何時該介入」和「生成什麼內容」
- 可以在不需要幫助時選擇放棄（abstain），避免 hallucinated memory

在 web navigation、terminal tool use、text-based embodied interaction 三個 benchmark 上，Mem-π 比 retrieval-based 記憶高出 30% 以上。

### 2.2 三層記憶粒度：TriMem

TriMem（arXiv:2605.19952）的切入點是：現有事實萃取方法（handcrafted static prompts）無法定義一致的粒度——同一段對話可能被萃取成一件事也可能被切成十件事，取決於對話風格。

TriMem 同時維護三種記憶表示：

| 層級 | 內容 | 用途 |
|------|------|------|
| **Raw segments** | 原始對話，帶 source identifier | 儲存 fidelity，完整可審計 |
| **Atomic facts** | 萃取出來的單一事實 | 高效檢索，相似度匹配 |
| **Synthesized profiles** | 彙總分散事實成整體理解 | 深度推理，跨 session 理解 |

三層之間形成互補：raw segments 保留完整資訊，atomic facts 提供快速檢索入口，profiles 支撐高層次推理。TriMem 還用 TextGrad-based prompt optimization 自動調整萃取和 profile 生成 prompt，達成**終身學習而不更新任何參數**。

### 2.3 查詢時蒸餾：DeferMem

DeferMem（arXiv:2605.22411）的核心觀察：現有記憶系統在**查詢之前**就處理好記憶（pre-query processing），然後基於相似度找回候選——但相似度不等於「對回答這個問題有用」。

DeferMem 的 pipeline 分兩階段：
1. **高召回檢索**：用 lightweight segment-link 結構組織原始歷史，找回廣泛候選
2. **條件蒸餾**：用 RL 訓練的 memory distiller，把高召回但雜訊多的候選蒸餾成「faithful, self-contained, query-conditioned evidence」

訓練演算法叫 DistillPO，把蒸餾過程建模成「message 選擇 + evidence 重寫」兩個結構化動作，用 decomposed-and-gated reward 優化，零商業 API token 成本。

在 LoCoMo 和 LongMemEval-S 兩個 benchmark 上，同時達到最高 QA accuracy、最快 runtime、零 API 成本。

### 2.4 事件溯源架構：ActiveGraph

ActiveGraph（arXiv:2605.21997）從根本上翻轉了 agent 架構的層級：

**大多數 agent 框架**：對話 loop → tools → rules → logging（事後補上）
**ActiveGraph**：append-only event log 是 source of truth，working graph 是 log 的確定性投影，behaviors（LLM routine、functions）透過監聽 graph 變化來反應

```python
# ActiveGraph 核心概念
event_log.append(event)          # 追加事件
working_graph = project(log)      # 確定性投影
behaviors.react(working_graph)   # 行為響應變化
    → emit new events             # 發出新事件
```

這帶來三個 retrieval-summarization 記憶系統做不到的能力：
- **確定的 replay**：任何運行都可以從 event log 重放
- **便宜的 fork**：在任何 event 處分支，無需重新執行共享前綴
- **完整 lineage**：從高層目標一路追蹤到每個 model call 產生每個 artifact

### 2.5 檔案系統典範：OpenViking

OpenViking（Volcengine）把 agent 的 context 管理類比成作業系統的檔案系統：

- **L0/L1/L2 三層**：熱→暖→冷，按需加載
- **目錄遞迴檢索**：結合目錄定位 + 語意搜尋，達成遞迴精確檢索
- **可觀測的檢索軌跡**：視覺化目錄檢索路徑，方便 debug
- **自動 session 管理**：自動壓縮對話內容，萃取長期記憶

這種設計解決了碎片化 context（memories 在程式碼、resources 在向量資料庫、skills 散落各處）的問題。

### 2.6 去中心化記憶：Decentralized Memory for MAS

Self-Evolving Multi-Agent Systems via Decentralized Memory（2026-05-21）指出：現有 multi-agent 幾乎都採用集中式共享 repository，造成：
- 通訊和協調 overhead
- 隱私問題
- agent diversity 崩潰

提出 DecentMem：每個 agent 有本地記憶，只在高層次共享歸納知識，兼顧隱私與協作。

## 3. Why It Matters / Applications

這波記憶架構演進對 agent 生態有幾個重大影響：

**1. 從「找回了什麼」到「為什麼有用」**
過去評估記憶系統只看 recall、similarity；現在的論文（MemConflict benchmark、DeferMem）開始用「回答品質」來評估。這是範式轉變——記憶是手段，回答品質才是目的。

**2. 小模型勝過大記憶**
Mem-π 和 DeferMem 都用相對小的 specialized 模型來處理記憶，卻能超越大模型 + 龐大記憶庫的做法。意味著：與其擴充 context window，更重要的是「讓正確的資訊在正確的時機出現」。

**3. 可解釋性的需求在上升**
ActiveGraph 的事件溯源、OpenViking 的可觀測檢索軌跡、DeferMem 的 query-conditioned evidence——都在往「記憶系統不只要有用，還要被審計」的方向走。這對 production agent 至關重要。

**4. 從單一 agent 到協作記憶**
DecentMem 的去中心化設計對 multi-agent 系統特別重要。當多個 agent 協作時，不是把大家綁在同一個記憶庫，而是各自維護 + 選擇性共享——這是架構層面的創新。

## 4. Limitations / Honest Assessment

**Mem-π 的限制：**
- 需要訓練一個額外的小模型，inference cost 從 0 變成有
- RL 訓練需要大量互動資料，小團隊難以復現
- 在簡單 QA 任務上可能不如直接 retrieval

**TriMem 的限制：**
- 三層表示的存儲 overhead 比單層要大
- TextGrad prompt optimization 需要回饋訊號，初期可能不穩定
- 論文只在 LoCoMo 和 PerLTQA 上測試，泛化性待驗證

**DeferMem 的限制：**
- RL 蒸餾組件有一定 complexity，部署門檻
- zero API cost 的代價是本地模型 inference 仍需算力

**ActiveGraph 的限制：**
- 作者坦言「討論而不展示」——沒有實證 benchmark
- event log 的 storage 隨運行時間線性成長，需要 compaction 策略
- 確定性 contract 的實際實作細節不清

**OpenViking 的限制：**
- 檔案系統 paradigm 在理論上優雅，但實際上 agent 的 context 不是樹狀結構（知識圖譜比檔案系統更自然）
- L0/L1/L2 分層需要維護成本

**可複製性評估：**

| 方法 | 可免費實作 | 瓶頸 |
|------|-----------|------|
| Mem-π | ✗ 需要 RL 訓練基礎設施 | 訓練資料和算力 |
| TriMem | △ 部分可行（static 部分），prompt optimization 需來回迭代 | 需要可用的反饋訊號 |
| DeferMem | △ segment-link 可免費實作，DistillPO RL 複雜 | RL 訓練 |
| ActiveGraph | ✓ 核心概念可直接實作 | 高效能 event store 需要優化 |
| OpenViking | △ 核心概念免費，完整實作需 Rust toolchain | Rust 依賴 |

## 5. Actionable for Our Projects

### 對 Hermes 的具體改進

**高優先級（TRIVIAL–MODERATE）**

1. **借鑒 ActiveGraph 的事件溯源概念，用於 trace 可觀測性**
   - 目前 Hermes 的 trace 是事後追加的日誌，可以改成 append-only event log
   - 受益：deterministic replay、cheap fork、end-to-end lineage
   - 改動模組：`src/hermes/tracing/` → 新增 EventStore + Projection engine
   - 難度：MODERATE，但對 debug 和 audit 很有價值

2. **引入三層 context 的概念（L0/L1/L2）**
   - 目前 Hermes 的 context 只有「全部塞進去」或「手動切片」兩種
   - 可以實作 auto-tiered context：工作記憶（L0，完整）→ summarized 記憶（L1）→ long-term fact store（L2）
   - 受益：降低 token 消耗、提升相關資訊召回率
   - 改動模組：`src/hermes/context/` → 新增 TierManager
   - 難度：MODERATE

3. **Query-conditioned evidence retrieval（DeferMem 概念）**
   - 從「相似度檢索」升級成「utility-based retrieval」
   - 做法：在 retrieval 前加一個 lightweight filter，根據「對回答問題是否有幫助」重新排序候選
   - 受益：減少記憶汙染、提升回答品質
   - 改動模組：`src/firn/memory/` 或 Hermes 的 memory module
   - 難度：MODERATE，需要實驗驗證

**中優先級（HARD）**

4. **Mem-π 生成式記憶的可行性評估**
   - 目前不建議直接實作（需要 RL 訓練基礎設施）
   - 但可以做一個簡化版本：用一個小的專門模型（而非 LLM）來生成記憶摘要
   - 這需要在 local 模型或低成本 API 方向投入

5. **DecentMem 去中心化記憶的研析**
   - 適用場景：multi-agent 協作
   - 建議先做研究而非實作：研究 DecentMem 具體架構，評估是否適用於 Hermes 的多工作區設計

### 對 Firn 的具體改進

6. **將 TriMem 三層概念映射到 Firn 的記憶架構**
   - Firn 已有 `blocks`（raw）+ 萃取機制，可以加入 `profiles` 層
   - `ConsolidationAgent` 可以延伸為「生成 profiles 而不只是萃取 facts」
   - 受益：更好的深度推理能力
   - 難度：TRIVIAL（只需修改 `memory/consolidator.py` 的 logic）

7. **在 Firn 記憶中新增「來源鍊」追蹤**
   - TriMem 和 DeferMem 都強調 source identifier 的重要性
   - Firn 的 `Block` 已經有部分 metadata，可以延伸為完整的 lineage 追蹤
   - 改動：`src/firn/memory/service.py`
   - 難度：TRIVIAL

## 6. Follow-up Questions

1. **Mem-π 的 RL 蒸餾能否用 DPO/PPO 而非完整 RL 訓練？** 如果可以，小團隊也能實作，降低門檻。
2. **ActiveGraph 的確定性 contract 具體需要什麼機制？** 這決定了 replay 的 soundness，需要深入研究實作。
3. **三層 context（L0/L1/L2）在 Hermes 的實作優先順序？** 現有架構如何改造才能支援 auto-tiering？
4. **DeferMem 的 segment-link 結構是否可以用於 Firn 的 `Block` 系統？** 這是 TRIVIAL 的改動但可能有高價值。
5. **Elephant Agent 的「Personal Model」概念與 TriMem profiles 有何重疊？** 值得對比研究，看能否整合。

---

## 原始來源

1. [OpenViking - Volcengine](https://github.com/volcengine/OpenViking) — GitHub Repo — MEDIUM — 24k stars, filesystem paradigm context database for AI agents with L0/L1/L2 tiered loading and observable retrieval trajectories

2. [Letta (formerly MemGPT)](https://github.com/letta-ai/letta) — GitHub Repo — MEDIUM — 22.9k stars, stateful agent platform with advanced memory blocks and self-improvement capabilities

3. [Mem-$\pi$: Adaptive Memory through Learning When and What to Generate (arXiv:2605.21463)](https://arxiv.org/abs/2605.21463) — arXiv Paper — HIGH — RL-trained framework where a dedicated small model generates context-specific guidance on demand, outperforming retrieval-based baselines by >30% on web navigation

4. [The Log is the Agent: Event-Sourced Reactive Graphs for Auditable, Forkable Agentic Systems (arXiv:2605.21997)](https://arxiv.org/abs/2605.21997) — arXiv Paper — MEDIUM — Inverts agent architecture: append-only event log is source of truth, yielding deterministic replay, cheap forking, and end-to-end lineage

5. [TriMem: Beyond Atomic Facts in Lifelong LLM Agent Memory (arXiv:2605.19952)](https://arxiv.org/abs/2605.19952) — arXiv Paper — HIGH — Three-tier memory representation (raw segments + atomic facts + synthesized profiles) with TextGrad-based prompt optimization for lifelong evolution

6. [DeferMem: Query-Time Evidence Distillation via RL (arXiv:2605.22411)](https://arxiv.org/abs/2605.22411) — arXiv Paper — HIGH — Decouples memory into high-recall retrieval + query-conditioned distillation via DistillPO RL, achieving highest QA accuracy with fastest runtime and zero commercial API cost

7. [Elephant Agent](https://github.com/agentic-in/elephant-agent) — GitHub Repo — MEDIUM — Personal-model-first self-evolving AI agent with meaning-based memory that becomes care, context, and better judgment

8. [MemConflict: Evaluating Long-Term Memory Systems Under Memory Conflicts (arXiv:2605.20926)](https://arxiv.org/abs/2605.20926) — arXiv Paper — MEDIUM — Benchmark for evaluating memory systems when conflicting information appears across sessions

9. [CALMem: Application-Layer Dual Memory for Conversational AI (arXiv:2605.20724)](https://arxiv.org/abs/2605.20724) — arXiv Paper — MEDIUM — Application-layer dual memory addressing context window limits and session reset issues

10. [Self-Evolving Multi-Agent Systems via Decentralized Memory (2026-05-21)](https://export.arxiv.org/api/query?search_query=ti:self-evolving+AND+ti:multi-agent) — arXiv Paper — HIGH — DecentMem: decentralized memory architecture for multi-agent systems avoiding centralized repository bottlenecks