# 研究報告：Self-Improving AI Agents — Memory, Reflection, and Context Engineering
**日期**：2026-05-27
**來源數**：8 | **標籤**：#self-improving #memory #reflection #context-engineering #multi-agent

## 1. The Problem

如何在不改變模型權重的情況下，讓 LLM-based agent 隨著時間變得更強？

Self-improving agent 是 2025-2026 年 AI agent 研究的核心命題。傳統的 LLM 是靜態的——同一個 prompt 每次回答都一樣。而實際任務中的失敗模式高度情境化：同一個 agent 在專案 A 失敗的模式，在專案 B 完全不會出現。

研究群體正在從三個軸向嘗試解決這個問題：
- **記憶系統**：將成功的工作流程、專案事實、調試經驗寫入持久化儲存
- **反思機制**：讓子Agent 分析自己的失敗，並生成結構化的改正策略
- **上下文工程**：將個別經驗昇華成可重複使用的策略bullet（playbook）

這個領域的代表論文是 **Agentic Context Engineering (ACE)**（arXiv:2510.04618），以及大量开源實現——包括 CodeEvo、ReflectiveAgent、Vera、Kronos 等。

## 2. Core Mechanism

### 2.1 三角色架構（Generator / Reflector / Curator）

ACE 論文提出最嚴謹的 self-improving 流程，由三個專業角色互動：

```
樣本輸入 → Generator（生成答案 + 標記使用的bullet）
         → Reflector（分析錯誤、根因分析、產出結構化洞察）
         → Curator（發布 playbook 操作：ADD/UPDATE/REMOVE bullet）
         → Playbook 更新 → 下一個epoch
```

**Generator**：接收當前 playbook + 反饋，產生回答，並標記哪些 bullet 在推理過程中有幫助。

**Reflector**：觀察 Generator 的推理軌跡 + 環境回饋（執行結果、ground truth），診斷錯誤根源、分類 bullet 貢獻（helpful/harmful/neutral），產出結構化 insight。最多支援 5 輪 refinement。

**Curator**：消費 Reflector 的洞察 + playbook 統計，發布 delta 操作（ADD/UPDATE/TAG/REMOVE bullet）。在 token budget 限制下運作，避免 playbook 無限膨脹與 collapse。

**關鍵設計差異**：三個角色共用同一 base model，所有能力來自於 context engineering 而非模型更换。Offline 和 Online 兩種adaptation loop——Offline 離線批量训练，Online 在測試流上即時更新 playbook。

### 2.2 Playbook as Structured Memory

ACE 的核心抽象不是簡單的對話歷史，而是一個**結構化的 playbook**：

每個 **bullet** 擁有自己的：
- `content`：策略、錯誤模式、API schema、驗證清單
- `metadata`：unique ID + helpful/harmful 计數器
- `section`：归类（defaults、strategies、errors 等）

Playbook 透過 delta update 漸進生長，沒有全量重寫。 Curator 定期執行 **grow-and-refine**（语义去重、counter 調整、修枝）。

### 2.3 跨 session 持久記憶（CodeEvo 模式）

不同於 ACE 的 prompt-level self-improvement，CodeEvo 展示另一种路线——系统级 self-improvement：

```
任務執行 → 事後分析（識別 durable facts + 成功 workflow）
         → 寫入 long-term memory（專案事实）
         → 寫入 skills（可重用步驟）
         → 寫入 sessions.db（調試上下文）
         → 後續 session 自動召回
```

記憶類型分層：
- **Episodic memory**：本次 task 的成功/失敗模式
- **Vector memory**：语义检索用的向量化存储
- **Skills**：结构化的工作流程（可用於新任務）
- **Project facts**：跨 session 的穩定專案資訊

### 2.4 Vera 的 `@capability`  decorator 作為統一抽象

Vera（`BoeJaker/Vera`）提出更激進的設計：一個 `@capability` decorator 將任何 Python function 同時轉化為：
- 分散式計算單元（透過 Redis Streams 跨 worker 分發）
- Agent tool（ LangGraph planning loop 可召唤）
- MCP endpoint（JSON-RPC over WebSocket）
- HTTP API endpoint（自動生成 OpenAPI 文件）
- Python API（直接 in-process 调用）
- Redis publisher/consumer（發布結構化事件）
- UI element（自動 reflection 到前端）

所有 capability 共用同一 registry、同一 event surface、同一 observability layer——不論工作從何處來或在哪執行。這將"定義一個 function"的開發體驗，直接升級為"部署一個 networked service"。

### 2.5 容器隔離 + Swarm 協調（Clawix 模式）

Clawix 走的是基礎設施路線：每个 agent 跑在自己的 Docker container，實現：
- 跨 agent 記憶體隔離（不可能讀到另一個 agent 的文件）
- Warm container pool（冷啟動延遲從 1-3s 降到 ~50ms）
- RBAC + token budget +  Immutable audit log
- Sub-agent DAG orchestration（coordinator 委派 → aggregate results → handle failures）

## 3. Why It Matters / Applications

**對 AI agent 領域的影響**：

1. **從「靜態 assistant」到「會成長的系統」的典範轉移**：過去三年的主流是「更強的 base model + prompt engineering」。Self-improving agent 標誌第四種路線：透過經驗累積而不需 retrain 就能適應特定任務域。

2. **Operator-level vs. Model-level improvement 的區分**：ACE 證明純 context engineering（不改 model）在 AppWorld benchmark 上可以達到有意義的提升，代表 operator-level adaptation 是實用方向。

3. **記憶成為 first-class citizen**：CodeEvo、Vera、Kronos 都將記憶從 auxiliary logging 提升為系統核心——agent 的能力邊界不由模型決定，而由其記憶覆蓋範圍決定。

4. **企業部署日趨成熟**：Automatos AI（100+ marketplace agents、1000+ tool integrations）和 Clawix（container 隔離、RBAC、審計日誌）代表 production-grade multi-agent 平台已脱離研究階段，進入企業可用性。

## 4. Limitations / Honest Assessment

### 作者坦承的限制

**ACE 論文自身**：
- 沒有 reliable feedback signal 時性能會退步（依賴執行回饋、unit test、ground truth）
- Curator 的 quality 完全取決於 Reflector 的診斷能力
- Token budget 限制下 playbook growth 有上限，需要定期修枝

**CodeEvo**：
- Self-improvement 是 system-level（寫記憶到 DB），不是 model-level——沒有真正的泛化能力
- 記憶準確性依賴事後分析的 quality，如果一開始分析錯了錯誤模式，會累積錯誤

**Vera**：
- 官方聲明「Still very-much in development」，任何 issues 請 post issue
- 系統需求極高（16GB+ RAM per component），不適合資源受限環境

**Clawix**：
- 仍在开发早期，container 隔離帶來的額外複雜度（全領域通用能力尚未驗證）

### 我們的獨立評估

**反駁觀點**：
- Playbook-based learning 在高多樣性任務（每天處理全新領域）時可能會缺乏 transfer——一個 domain 學到的 bullet 對另一個 domain 可能完全無效甚至有害
- Memory-based self-improvement 的核心假设：如果同樣的錯誤再次發生，agent 會記得並避開。但在 real-world 使用中，錯誤往往以微變形（subtle variant）的形式出現，單純的 exact-match 檢索會失敗

**權衡取捨**：
- 三角色架構（Generator/Reflector/Curator）每 epoch 增加 3x LLM call、3x token 消耗
- Playbook 隨時間增長，context window 壓力會成為瓶頸
- Memory storage 的 schema 设计高度任务相关，没有 universal solution

**可複製性**：
- ACE 可以用 любой LLM API 重新實作（demo 用 DummyLLM），但要達到 paper 等效需要：足夠大的 training samples 數量、reliable feedback signal、5 epoch adaptation
- CodeEvo 几乎完全免費（SQLite + 檔案儲存），但需要花時間設計 memory schema
- Vera 需要 16GB+ RAM × 多个 worker，對普通人不可及

## 5. Actionable for Our Projects

### 5.1 對 firn 的具體改進建議

**方向 A：在 firn 中實作 ACE-style playbook（MODERATE）**

现有架构中 firn 没有持久的 playbook system。建议引入：

1. 新增 `firn/playbook.py`：PlaybookStore（bullet store + metadata counters + section 管理）
2. 在 agent loop 中加入 Reflector step（每次执行后调用 LLM 分析）
3. Curator 模块处理 delta merges（控制 playbook 大小在 token budget 内）
4. Grow-and-refine 触发时机：每次 delta 后立即执行，或累计 N 条后批量执行

**改动模块**：`agent.py`（加 Reflector）、新 `playbook.py`、`config.py`（playbook 超參）
**实现难度**：MODERATE——需要設計 bullet schema、做 semant IC dedup（可用 embedding）
**付费 API**：可使用 DeepSeek / Ollama 等免費端點，無需付费 OpenAI

**方向 B：引入 CodeEvo-style 跨 session recall（TRIVIAL）**

比 ACE 更容易落地的方式——参考 CodeEvo 的分层记忆：

1. `firn/memory.py`：新增 episodic（SQLite）+ vector（chromadb/FAISS）存储
2. 每個 task 完成後自動執行 self-analysis prompt，提取 durable facts → memory.json
3. 新 session 開始時檢索相關記憶，注入到 system prompt

**改动模块**：新 `memory/` 目录，对现有 agent.py 侵入性低
**实现难度**：TRIVIAL
**付费 API**：全部可用免費工具（SQLite + chromadb + ollama）

**方向 C：參考 Vera 的 @capability 抽象（RESEARCH-ONLY）**

目前 firn 架構中 tool registration 较為分散（各个 handler 自注册）。Vera 的 `@capability` decorator 是更優雅的統一抽象，但實作需要重構現有架構。

**结论**：短期不推荐，长期可作为架构目标。

**方向 D：參考 Kronos 的三層記憶架構（HARD）**

Kronos 展示 production-grade 多層記憶：
- Session history（短期）
- FTS5 recall（全文檢索）
- Mem0 vectors（向量化）
- Knowledge graph（結構化關係）

這與 firn 当前的 memory approach（可能是 simple KV）是质的提升。需要先评估 firn 的 memory 使用模式再决定是否引入。

### 5.2 快速 win：給 firn 加上 task completion self-reflection

**最简单的 actionable improvement**：

在每次 firn 完成一個 task 之後，多做一步：

```
Task 完成後prompt:
"分析這次執行情況：
1. 這次成功是因為什麼關鍵決策或工具使用？
2. 有哪個步驟可以做得更好？
3. 提取未來適用的策略要點（1-3條bullet）
格式輸出為 bullet list。"
```

將输出的 bullet 存入 `~/.firn/playbook.md`。不需要任何架構改動，用現有工具即可实现。

## 6. Follow-up Questions

1. **Memory schema 的任務特異性**：ACE 的 playbook 在單一 domain（AppWorld）內有效，在跨 domain 使用時的 transfer learning 效果如何？是否需要 domain-specific playbook？

2. **Reflector 的診斷 quality**：三角色架構中 Curator 的輸出質量完全由 Reflector 的诊断能力決定。如何自動化評估/提升 Reflector quality？有沒有不需要 5 輪 refinement 的更高效版本？

3. **Playbook collapse 的預防**：當 playbook 成長到一定規模後，過多的 bullet 可能造成類似 overfitting 的 collapse——每個 context 都塞滿了 bullet 但沒有一個真正相關。現有文獻對此的討論极少。

4. **Multi-agent 下的 self-improvement**：現有 self-improving 系統都是 single agent。在 swarm/multi-agent 架构下，谁来 reflection 整个团队的集体行为？是否需要 meta-reflection？

5. **付費牆評估**：Kronos 和 Clawix 的 production feature（300+ LLM路由、container隔離、審計日誌）都需要付費基礎設施，普通人能否用免費工具達到80%效果？

---

### 原始來源

https://github.com/flat-git/ACE-open-test — REPO — HIGH — Clean-room ACE implementation reproducing arXiv:2510.04618 with Generator/Reflector/Curator architecture and offline/online adaptation loops

https://github.com/Spi1er/CodeEvo — REPO — HIGH — Self-improving coding agent that externalizes debugging experience into persistent memory, reusable skills, and searchable session history across sessions without retraining

https://github.com/rzadrzi/ReflectiveAgent — REPO — HIGH — Self-improving LLM agent for puzzle solving with multi-agent debate layer, episodic/vector memory, and structured reflection step after each attempt

https://github.com/tusharjain1003/AgentLens — REPO — MEDIUM — Production agentic RAG with reflection-based gap recovery, claim verification, and hybrid semantic search using LangGraph + SSE streaming

https://github.com/BoeJaker/Vera — REPO — HIGH — SMMAC-PBR architecture: @capability decorator as sole registration primitive, turning any Python function into a distributed networked service with multi-backend LLM cluster, DAG executor, memory graph

https://github.com/spyrae/kronos-agent-os — REPO — MEDIUM — Durable agent runtime with multi-layer memory (session/FTS5/Mem0/knowledge graph), skills, MCP tools, scheduled automations, and optional swarm coordination

https://github.com/ClawixAI/clawix — REPO — MEDIUM — Container-isolated multi-agent orchestration with warm pools, RBAC, token budgets, immutable audit logs, sub-agent DAGs, and multi-channel deployment

https://github.com/AutomatosAI/automatos-ai — REPO — MEDIUM — Enterprise multi-agent platform with 100+ marketplace agents, 1000+ tool integrations, 150+ reusable skills (skills as portable versioned capability packs)

https://github.com/open-gsd/gsd-pi — REPO — MEDIUM — Local-first coding agent with project workflow tools, worktree-aware Git automation, and optional UI for continuous autonomous project work

---

*下一個工作日排程執行本指令。*
