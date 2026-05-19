# 研究報告：Multi-Agent Coordination Architectures — 跨 Agent 協作的新範式

**日期**：2026-05-19
**來源數**：8 | **標籤**：#multi-agent #coordination #shared-memory #cross-harness #contract-first

---

## 1. The Problem

單一 AI agent 在 2025-2026 已不夠用了。複雜任務需要多個專門化的 agent 协同工作——但協作帶來三個根本問題：

1. **知識不共享**：每個 agent 是孤島，重複學習相同的東西，浪費 context 與 API 成本
2. **行動衝突**：多個 agent 同時修改同一個檔案，誰都不知道別人在幹嘛（"file clobbering"）
3. **協調失效**：沒有結構化的任務分配與結果聚合機制時，agent swarm 退化成一盤散沙

這個問題在 2026 年特別尖銳——因為开源生態已經從「單一 agent 工具」進化到「multi-agent 協作框架」的軍備競賽階段。光是 ECC 這個專案就有 187K stars，Mem0 有 56K，OpenViking 有 24K。沒有大型論文支撐，但這些 repos 加起來有數百萬次 fork——說明這是實實在在的工程需求，不是學術想像。

---

## 2. Core Mechanisms

### 2.1 Shared Memory Layer（共享記憶層）

所有多 agent 架構的第一件事都是解決「記憶不共享」的問題。2026 年的主流方案分三類：

**a) Vector-based Semantic Memory（向量語義記憶）**

Mem0 v3 是這個方向的領先者，2026 年 4 月發布的新演算法在 benchmark 上大幅提升：

| Benchmark | 舊版 | v3 | 改善 |
|---|---|---|---|
| LoCoMo | 71.4 | **91.6** | +20 |
| LongMemEval | 67.8 | **94.8** | +27 |
| BEAM (1M) | — | **64.1** | — |

關鍵設計：Single-pass ADD-only extraction，記憶只增不刪，Multi-signal retrieval（語義 + BM25 + 實體匹配 + 時間推理）並行評分融合。這避免了傳統 RAG 的「覆寫問題」——當 context 更新時舊記憶不被丟掉。

**b) Context Database（上下文資料庫）**

OpenViking（位元組跳動 volcengine）提出另一個思路：放棄向量儲存的碎片化，採用「檔案系統典範」（filesystem paradigm）來統一管理 memories、resources、skills。

核心創新：L0/L1/L2 三層結構，根據需求按需加載，而不是把所有東西都塞进 context：
- **L0**：最基礎、最常用的全域知識
- **L1**：對話期間動態載入的相關內容
- **L2**：按需喚取的深層任務內容

這直接解決了「long session context rot」的問題——agent 不再需要在龐大的向量庫裡搜尋，而是像管理本地檔案一樣導航。

**c) Shared Brain with Coordination（共享大腦 + 協調）**

junto-memory（production-tested，500+ sessions，6 agents）是這個方向最實際的案例。它的解決方案是：

- **Persistent Knowledge Base**：MongoDB + ChromaDB，架構文件、學習、gotchas 跨 session 存活
- **File Locking**：防止同時寫同一個檔案，session 結束自動釋放
- **Inter-agent Messaging**：agent 間可以傳訊息、附帶執行緒與狀態追蹤
- **Overlap Detection**：自動偵測多個 agent 是否在做類似的事

```
Agent A ──────► junto-memory server ◄────── Agent B
                   │
                   ├──► MongoDB (structured data, tasks, messages)
                   ├──► ChromaDB (vector embeddings)
                   └──► Function Registry (auto-enriched by librarian daemon)
```

---

### 2.2 Contract-First Coordination（契約優先協調）

contract-first-agents 的核心概念：**在任何人開始工作之前，先定義好每個任務的輸入輸出形狀（schema）**，而不是讓 agent 自己商量。

Map-Reduce 流程：
1. **Contract Phase**：定義每個 work item 的 shape（input format, expected output format, validation rules）
2. **Map Phase**：每個 agent 處理一個 contract-defined work item
3. **Reduce Phase**：彙整結果，格式檢驗，衝突偵測

這個模式的優點：**結果穩定可重現**。同一個 contract，跑多次輸出格式一致，不會因為 LLM 的隨機性導致每次格式都不同。

### 2.3 Cross-Harness Portability（跨 harness 可移植性）

ECC（187K stars，Anthropic Hackathon Winner）是最成熟的跨 harness 協調方案。它定義了一個「可移植層」的概念：

```
Skills（技能定義）──► 可以安裝到 Claude Code / Codex / OpenCode / Cursor / Gemini
Rules（行為規則）──► 翻譯成各 harness 自己的格式（rules / AGENTS.md / instructions）
Hooks（鉤子腳本）──► 透過 adapter layer 適配到各 harness 的事件系統
MCP configs ───────► 各 harness 的 MCP 原生配置
Sessions ──────────► 跨 harness 的 session 狀態管理（alpha）
```

核心洞察：**SKILL.md 是最可移植的單位**。一個 SKILL.md 可以在所有支持的 harness 中工作，因為它只包含指令、約束和工作流形狀，不依賴任何特定工具的命令假設。

---

### 2.4 Subagent-Driven Development（子 Agent 驅動開發）

Superpowers（obra/superpowers，197K stars）的核心方法論：

1. **Spec First**：agent 先搞清楚「用戶真正想解決什麼問題」，而不是直接跳進程式碼
2. **Plan as Interface**：把實作計畫寫得足夠清楚，讓「沒有品味、沒有判斷力、厭惡測試的熱情菜鳥工程師」都能跟著走
3. **Subagent-Driven Execution**：主 agent 把任務委派給子 agent，自己做 inspect & review，不時檢查方向是否偏離

這與傳統 AutoGPT 的「一個 agent 從頭做到尾」完全不同——Superpowers 把軟體開發方法論本身建模成 agent 行爲。

---

### 2.5 Swarm Intelligence（群體智能）

MiroFish（盛趣遊戲出品，61K stars）提出了一個更大膽的視角：不是協調固定數量的 agent，而是創造一個「高保真平行數位世界」，讓數千個具有獨立人格、長期記憶和行為邏輯的智能體自由互動與社會演化。

應用場景：**預測**。上傳种子材料（數據分析報告、新聞、故事），MiroFish 建構一個數位模擬世界，從「上帝視角」注入變數，精確推導未來軌跡——相當於在數位沙箱中「排練未來」。

---

## 3. Why It Matters / Applications

這些架構的出現代表一個範式轉移：**從「單一超強 agent」到「複数 специализированных agents 協作網絡」**。

對 AI agent 領域的影響：

- **成本下降**：共享記憶避免重複學習，mem0 v3 的 token 效率從 14K-20K 降到 6.7K-7K（+53.6% 在 assistant memory recall）
- **穩定性提升**：contract-first 模式讓輸出格式可預測，不再受 LLM 隨機性影響
- **可觀測性改善**：OpenViking 的「可觀測檢索軌跡」解決了傳統 RAG 的黑盒問題
- **開發效率提升**：cross-harness portability 讓同一套 skill 可以跨多個 coding agent 使用

---

## 4. Limitations / Honest Assessment

### 4.1 各方法的核心缺陷

**Mem0 v3 的限制**：
- Benchmark 分數高，但都是標準測試集，實際生產環境的 entity linking 品質未經充分驗證
- ADD-only 的設計在高頻更新的場景（如即時報價系統）下，memory 會快速膨胀
- 時間推理（Temporal Reasoning）在跨時區、多時段任務時可能出問題

**OpenViking 的限制**：
- 需要 Rust toolchain + C++ compiler + Python 3.10+，建置門檻高
- 檔案系統典範聽起來優雅，但實際上把「知識管理」的複雜度轉移给了開發者
- 24K stars 但相對新，生態（plugins、community）不如 ECC 成熟

**junto-memory 的限制**：
- 明确說「6 agents / 500+ sessions」是 production 數據，但這個規模對於真正的大型專案可能不够
- MongoDB + ChromaDB 的架構在網路分区或服務重啟時的恢復策略不明確
- 設計哲学偏向「代碼庫协作」，不見得適用於其他類型的多 agent 任務

**ECC 的限制**：
- 跨 harness 適配是個无底洞——每個新 harness 出來都需要新的 adapter
- "Sessions (Alpha)" 標注說明這部分還不成熟，大量使用可能踩坑
- 187K stars 但文檔複雜度極高，新人上手成本不小

**contract-first 的限制**：
- 契約定義本身需要人工介入，不能完全自動化
- 契約版本的維護會成鳥另一層技術債

**MiroFish 的限制**：
- 「預測任何事」的宣稱太強，實際上高度依賴种子材料的品質
- 61K stars 但中文 repo 為主，國際社群參與度未知
- 群體智能模擬在計算成本上可能極高

### 4.2 與傳統方案的比較

| 方案 | 核心創新 | 適用場景 | 主要缺陷 |
|---|---|---|---|
| AutoGPT | 單 agent 全域規劃 | 簡單一次性任務 | 長期任務 context overflow，無協調 |
| CrewAI | Role-based 多 agent | 任務分工明確的場景 | 記憶不共享，無跨 session 持久化 |
| LangGraph | 狀態機驅動 | 需要嚴格流程控制的任務 | 開發者需要自己實現協調邏輯 |
| ECC + junto | 共享記憶 + 協調 | 多個 coding agent 同時代碼庫 | 聚焦 coding，非通用 |
| Mem0 v3 | 通用記憶層 | 所有 agent 類型 | 仍需整合到現有系統 |
| OpenViking | Context DB | 需要嚴格 context 管理的大型任務 | 建置複雜，相對新 |

---

## 5. Actionable for Our Projects

### 5.1 對 firn 的具體改進

**1. 引入 junto-style 協調機制（MODERATE）**

現有問題：firn 的多 agent 協作沒有 file locking，兩個人 agent 同時改同一個檔案會產生衝突。

具體做法：
- 在 firn 中加入一個輕量級的檔案鎖服務（MCP server 或簡單的 REST endpoint）
- 每次 agent 開始編輯檔案前先請求鎖，結束後釋放
- 實作難度：MODERATE，需要了解 firn 現有的工具呼叫機制

**2. 採用 Mem0 風格的分層記憶（MODERATE）**

現有問題：firn 的長期記憶只靠 FTS5 search，效果不如專門的 memory layer。

具體做法：
- 評估 mem0 v3 的新演算法（single-pass ADD-only，multi-signal retrieval）
- 將 firn 的 session summary + skill creation 整合到統一的 memory layer
- 實作難度：MODERATE，免費方案可行（self-hosted），不需要 Mem0 雲端服務

**3. 引入 contract-first 的任務分配（TRIVIAL）**

現有問題：firn 的任務分配比較隨機，agent 自己决定做什麼。

具體做法：
- 在 firn 的 task management 中引入 schema validation
- 定義每個 task 的 expected input/output format
- 這可以從最小的「格式檢驗」開始，不需要完整實作 contract-first 框架

**4. 借用 ECC 的 skill portability 概念（TRIVIAL）**

現有問題：Hermes Agent 的 skills 是專有的，不能直接給其他 harness 使用。

具體做法：
- 確保 SKILL.md 使用標準 YAML frontmatter（name、description、origin）
- 避免 hardcode 任何工具特有的假設
- 這是一個整理現有 skills 的機會，不影響功能

### 5.2 實作優先順序

| 改進 | 難度 | 價值 | 優先級 |
|---|---|---|---|
| 檔案鎖服務 | MODERATE | 避免協作衝突 | HIGH |
| 記憶層重構（參考 mem0 v3） | MODERATE | 降低 context 成本 | HIGH |
| Task schema validation | TRIVIAL | 提高輸出穩定性 | MEDIUM |
| SKILL.md 標準化 | TRIVIAL | 提高可移植性 | LOW |

---

## 6. Follow-up Questions

1. **fim 的檔案鎖服務**：現有架構下實作輕量級鎖的成本有多高？需要新增一個 MCP server 嗎？
2. **記憶層遷移**：firn 現有的 FTS5 session search 能否無縫升級到 Mem0-style multi-signal retrieval？還是需要完全重寫？
3. **cross-harness skill 測試**：我們的 SKILL.md 在 Hermes 之外的其他 harness（如 Claude Code、OpenCode）能否正常工作？
4. **MiroFish 的預測能力**：這個群體智能方法對於我們的 daily research cron job 有無借鑒價值？還是用傳統的 source collection 就够了？
5. ** junto 的規模擴展**：當 agent 數量從 6 增加到 20+ 時，MongoDB + ChromaDB 的架構是否需要重構？

---

### 原始來源

1. **ECC — The harness-native operator system** (https://github.com/affaan-m/ECC) — GitHub Repo — HIGH — 187K stars, Anthropic hackathon winner, cross-harness skill/rule/hook portability layer
2. **junto-memory — Multi-agent coordination MCP server** (https://github.com/tlemmons/junto-memory) — GitHub Repo — HIGH — Production-tested (6 agents / 500+ sessions), file locking + shared memory + inter-agent messaging
3. **Mem0 v3 — Universal memory layer** (https://github.com/mem0ai/mem0) — GitHub Repo — HIGH — 56K stars, new April 2026 algorithm, +20-27 points on benchmarks, ADD-only memory accumulation
4. **OpenViking — Context database for AI Agents** (https://github.com/volcengine/OpenViking) — GitHub Repo — MEDIUM — 24K stars, filesystem paradigm for unified memory/resources/skills, observable retrieval trajectory
5. **Superpowers — Agentic skills framework** (https://github.com/obra/superpowers) — GitHub Repo — HIGH — 197K stars, spec-first → subagent-driven development methodology, skills auto-trigger
6. **contract-first-agents — Contract-based multi-agent coordination** (https://github.com/reactflowbrasil-lgtm/contract-first-agents) — GitHub Repo — MEDIUM — Map-reduce with pre-defined schemas for stable outputs
7. **MiroFish — Swarm intelligence engine** (https://github.com/666ghj/MiroFish) — GitHub Repo — MEDIUM — 61K stars, simulation-based prediction via agent population evolution
8. **Hermes Agent — Self-improving AI agent** (https://github.com/NousResearch/hermes-agent) — GitHub Repo — HIGH — 157K stars, built-in learning loop, skill creation, cross-session memory