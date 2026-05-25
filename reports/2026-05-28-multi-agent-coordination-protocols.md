# 研究報告：Multi-Agent Coordination Protocols
**日期**：2026-05-28
**來源數**：8 | **標籤**：#multi-agent #coordination #swarm #agent-architecture

## 1. The Problem

單一 AI agent 的能力有上限。複雜任務需要不同專業領域的 agent 協作，但「如何讓多個 agent 高效溝通、協調、避免衝突」，是 2025-2026 年最活躍的研究與工程問題。

核心挑戰：
- **角色分工**：誰該做什麼？如何動態分配？
- **通訊協定**：agent 之間如何傳遞訊息、共享上下文？
- **故障韌性**：當某個 agent 產生幻覺、延遲、或行為異常，整個系統如何維持正確性？
- **可擴展性**：N 個 agent 的通訊复杂度是 O(N²)，如何控制？

這個領域的主要玩家：OpenBMB (ChatDev)、LangGraph (AgentFlow)、CrewAI、Microsoft (AutoGen)、以及新興的 MMCP。

---

## 2. Core Mechanism

### 2.1 角色制分工（Role-Based Orchestration）

**ChatDev 1.0** 是這個範式的經典代表——虛擬軟體公司，每個 agent 有固定角色（CEO、CTO、Programmer、Reviewer），透過結構化的「研討會」（seminar）流程溝通。Agent 在各自階段被激活，完成後將輸出傳給下一個 agent。

**ChatDev 2.0 (DevAll)** 將這個模型推展為零碼平台，使用者可以透過設定檔自訂 agent 角色與 workflow，不再需要寫死角色組合。

**LightAgent** 的 LightSwarm 機制，進一步實現意圖判斷與任務轉移——系統會自動辨識使用者意圖，並將任務動態交給最適合的 agent。

```python
# LightAgent 的多智能體協同概念
agents = [
    {"name": "Strategist", "specialty": "strategic planning"},
    {"name": "Technologist", "specialty": "technology trends"},
    {"name": "Economist", "specialty": "market economics"},
]
# 系統自動判斷任務該交給誰
```

### 2.2 去中心化 Swarm 協作

**AgentFlow** 的 Swarm Pattern 代表另一種方向：沒有中央協調者，agent 透過訊息傳遞共享資訊，共同達到結論。適用於需要多元視角的探索性任務（brainstorming、研究分析）。

```
Phase 1: Task Initiation → Agent Turn (所有 agent 貢獻) → Aggregator
                         ↑________________________________|
```

每個 agent 在每輪貢獻資訊，經過多輪後由 aggregator 綜合結論。適合創意發想、不適合有標準答案的任務。

### 2.3 階層式分工（Hierarchical Pattern）

與 Swarm 的去中心化相對，**Hierarchical Pattern** 有 manager agent 負責任務分解與結果彙整：

```
Task → Manager Agent → Worker Agents (並行執行) → Manager aggregates
```

Worker agent 不知道自己在一個更大的工作流中，只對 manager 負責。這簡化了每個 agent 的決策复杂度，但增加 manager 的單點失敗風險。

### 2.4 對抗式驗證（Verify Pattern）

**MMCP** 的 Verify 模式引入對抗概念：

```
Producer → Challenger → Judge
```

Producer 生成輸出，Challenger 刻意找漏洞，Judge 最終裁決是否通過。這種三方制衡機制可有效對抗單一 agent 的幻覺問題。

### 2.5 RL 驅動的智慧路由（Domain-Aware Routing）

**MMCP** 的核心創新是學習每個模型擅長什麼領域，動態路由任務：

| 任務 | 領域 | 模型 | 分數 |
|------|------|------|------|
| Write Python API with auth | code_generation | GPT-4o | 0.96 |
| Debug React component | code_review | Claude Sonnet | 0.91 |
| Prove calculus theorem | math_reasoning | DeepSeek R1 | 0.92 |

當模型更新升級，系統會重新 benchmark，並自動更新路由策略。這解決了「每個模型都有擅長領域」的觀察——不再需要人為指定模型角色。

---

## 3. Why It Matters / Applications

**從單體到生態**：AI agent 的進化正在從「強化單一 agent」轉向「建立 agent 協作生態」。2026 年的趨勢是：

1. **Swarm Intelligence 實踐化**：去中心化、多專家協作已成 production-ready 方案
2. **角色制框架標準化**：ChatDev 1.0 的 virtual company 模型被大量抄襲與改進
3. **故障韌性開始被認真對待**：MAS-Resilience 指出 CUHK 的研究顯示 agent 故障率約 5-20%，影響顯著
4. **跨框架協作需求浮現**：MMCP 嘗試標準化不同框架（LangChain、CrewAI、AutoGen）之間的 agent 協調
5. **Zero-code 平台搶佔市場**：ChatDev 2.0、AgentCloud 都在降低 multi-agent 的使用門檻

---

## 4. Limitations / Honest Assessment

### 作者坦承的限制

**MAS-Resilience (CUHK)**：
- 目前只測試了幾個特定的攻擊手法（AutoTransform、AutoInject），真實世界的多樣化攻擊尚未覆蓋
- 防御方法（Inspector、Challenger）本身也是 LLM agent，可能被同樣的手法欺騙
- 防禦 overhead 會增加延迟與成本

**MMCP**：
- RL routing 需要累積足够 benchmark 數據，冷啟動問題存在
- Domain detection 準確度依賴任務描述的清晰度，模糊任務容易選錯領域

### 獨立評估

**過度設計風險**：Swarm Pattern 的多輪協作有吸引力，但複雜度也高。對於簡單任務（文書處理、翻譯），單一 agent 更有效。

**通訊瓶頸**：去中心化架構的最大問題是共識時間——每輪需要所有 agent 完成才能進入下一階段，瓶頸在最慢的 agent。

**可複製性**：
- Role-based 協作（ChatDev 模式）：TRIVIAL，任何人可用 REST API 重現
- RL 路由（MMCP 模式）：MODERATE，需要累積數據與持續優化
- 故障防御（MAS-Resilience）：RESEARCH-ONLY，學術階段還未 production-ready

---

## 5. Actionable for Our Projects

### 對 firn 的具體建議

#### 5.1 實作 Role-Based Multi-Agent 協調（MODERATE）

firn 目前是單一 agent 架構。可以參考 ChatDev 的 seminar 模型，實作一個簡單的協作流程：

```
提出者（提出任務）→ 規劃師（分解任務）→ 執行者（執行）→ 審查者（評估）→ 回應
```

**需要改動的模組**：
- `src/firn/agents/` — 新增 AgentCoordinator class
- `src/firn/tasks/` — 新增 RoleAssignment logic

**難度**：MODERATE（需要定義角色 schema、訊息傳遞格式）

#### 5.2 實作 LightSwarm 式的意圖偵測與任務轉移（MODERATE）

LightAgent 的 LightSwarm 機制——讓使用者輸入後，系統自動判斷意圖並轉交適合的 sub-agent。這對 firn 的 CLI 很有價值。

**需要改動的模組**：
- `src/firn/gateway/` — 新增 IntentDetector
- `src/firn/agents/` — 支援 sub-agent registry

#### 5.3 參考 AgentFlow 的 Pattern Library（TRIVIAL）

AgentFlow 的 10+ patterns（Reflection、Debate、MapReduce、Voting）都附有完整程式碼，可以直接搬過來作為 firn 的內建 workflow 模式。

**需要改動的模組**：
- `src/firn/skills/` — 新增 pattern discovery
- 或獨立 `src/firn/patterns/` 模組

#### 5.4 關注故障韌性（RESEARCH-ONLY）

MAS-Resilience 的 Inspector/Challenger 模式目前只是 research prototype，但方向有價值。建議關注，等成熟後再實作。

---

## 6. Follow-up Questions

1. **MMCP 的 RL Routing 實作細節**：Domain score 是如何持續更新的？多久重新 benchmark 一次？這部分沒有开源，需要追蹤。
2. **ChatDev 2.0 的零碼平台**：它的 orchestration engine 底層是什麼？是基於現有框架（LangGraph/LangChain）還是自研？這影響我們能整合到什麼程度。
3. **HearthNet 的 lease-based coordination**：和 MMCP 的 protocol operation 相比誰更適合？我們的 firn 應該用哪種模式？

---

### 原始來源

1. **OpenBMB/ChatDev** — GitHub Repo — HIGH — 33k stars，虚拟软件公司模式的开创者，2026-05-25 更新，最新 2.0 版已转向零码平台
2. **iuyup/AgentFlow** — GitHub Repo — HIGH — 10+ 设计模式（swarm/hierarchical/map-reduce/debate/voting），全部有完整代码，2026-05-19 更新
3. **CUHK-ARISE/MAS-Resilience** — GitHub Repo + arXiv:2408.00989 — MEDIUM — 研究多 agent 故障韌性的學術工作（2024），防禦方法尚在研究階段
4. **wanxingai/LightAgent** — GitHub Repo — MEDIUM — 991 stars，轻量 multi-agent 框架，支持 MCP，内建 LightSwarm 自动转单机制，2026-05-25 更新
5. **RagavRida/mmcp** — GitHub Repo — MEDIUM — 多模型协作管道，RL 路由 + 多验证器投票 + agent mesh，2026-05-03 更新，仍在早期階段
6. **Farama-Foundation/chatarena** — GitHub Repo — MEDIUM — 1547 stars，多 agent 語言對戰環境，用於研究 agent 溝通與協作能力，2026-05-21 更新
7. **generalbots/generalbots** — GitHub Repo — LOW — 79 stars，Rust 實現的 multi-agent 平台，較小眾但有參考價值
8. **yhzhu99/MedAgentBoard** — GitHub Repo — MEDIUM — NeurIPS 2025 論文，多 agent 醫療任務協作的 benchmark，驗證了角色分工協作的有效性