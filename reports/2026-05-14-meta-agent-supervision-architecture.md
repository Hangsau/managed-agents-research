# 研究報告：Meta-Agent 監督其他 Agent 的架構
**日期**：2026-05-14
**來源數**：12 | **標籤**：#meta-agent #supervisor-pattern #multi-agent #orchestration

## 1. The Problem

當一個組織同時運行數十甚至數百個 AI agent 時，誰來確保它們不會一起壞掉？誰來決定哪個 agent 該接手哪個任務？當 agent 中途卡住、提前放棄、或產生幻覺決策時，誰來發現並糾正？

這就是 **meta-agent 監督架構** 要解決的核心問題：**如何建立一個上層控制平面，讓 agent 不是各自為政，而是被有效管理、監督、協調、復原**。

2025-2026 年，這個領域出現了幾個關鍵拐點：
- **OpenAI** 自己開源了 **Symphony**（★23,758），一個正式的 agent orchestrator，並附帶完整 SPEC.md
- **Anthropic** 在「Building Effective Agents」中正式定義了 **orchestrator-workers** 模式
- **Erlang/BEAM 的 actor 監督模型被大量借鑒**到 agent 管理（Symphony 的 Elixir 實現、ZeptoPM 的 Rust 實現、Sagents 的原生 Elixir/OTP）
- **24/7 自主監督 agent** 模式出現（ArgusBot、metabot），讓 meta-agent 本身也是 agent，形成遞迴監督

## 2. Core Mechanism

2026 年的 meta-agent 架構可歸納為 **三大流派 + 一個趨勢**：

### 流派 A：Orchestrator-Workers（任務級調度）

Anthropic 定義的經典模式，由 LangGraph、OpenAI Agents SDK、CrewAI 實作：

```
         ┌──────────────┐
         │  Orchestrator │  ← 中央 LLM：分解任務、分配、整合結果
         └──┬──┬──┬─────┘
            │  │  │
    ┌───────┘  │  └───────┐
    ▼          ▼          ▼
┌──────┐  ┌──────┐  ┌──────┐
│Worker│  │Worker│  │Worker│  ← 專門化 agent（各有自己的 tools + prompt）
│  A   │  │  B   │  │  C   │
└──────┘  └──────┘  └──────┘
```

**關鍵特性**：
- Orchestrator **動態決定**要 spawn 哪些 worker、給什麼子任務
- 與 parallelization 不同：子任務不是預定義的，而是 orchestrator 根據輸入動態分解
- **Handoff 機制**（OpenAI Swarm → Agents SDK）：agent 可在對話中途將控制權轉交另一個 agent

**程式碼範例**（OpenAI Swarm 的 handoff 原語）：
```python
from swarm import Swarm, Agent

def transfer_to_agent_b():
    return agent_b

agent_a = Agent(
    name="Agent A",
    instructions="You are a helpful agent.",
    functions=[transfer_to_agent_b],  # handoff 就是一個 function
)
agent_b = Agent(
    name="Agent B",
    instructions="Only speak in Haikus.",
)

client = Swarm()
response = client.run(
    agent=agent_a,
    messages=[{"role": "user", "content": "I want to talk to agent B."}],
)
```

### 流派 B：Process Supervision（OS 層級監督）

直接從 Erlang/BEAM 的「let it crash」哲學借鑒。**每個 agent 是獨立 OS process，supervisor 只負責生命週期**：

| 專案 | 語言 | 核心機制 |
|------|------|----------|
| **Symphony** (OpenAI) | Elixir/BEAM | Per-issue workspace isolation, orchestrator owns poll tick + retry queue + reconciliation |
| **ZeptoPM** | Rust | ~7 MB per agent, daemon supervisor with auto-restart + exponential backoff, hot config reload |
| **Sagents** | Elixir/OTP | Native OTP supervision trees, middleware composition, sub-agent delegation |

**ZeptoPM 的設計哲學**（直接引用）：
> "One agent leaks memory, the whole thing goes down. One agent panics, every agent dies with it. [...] Each agent runs as a separate OS process — isolated memory, isolated state, independent crash domains."

**Symphony 的正式 SPEC 摘要**（OpenAI 開源的語言無關規格）：
- **8 個元件**：Workflow Loader → Config Layer → Issue Tracker Client → Orchestrator → Workspace Manager → Agent Runner → Status Surface → Logging
- Orchestrator 擁有：poll tick、in-memory runtime state、dispatch/retry/stop/release 決策權
- Per-issue workspace 隔離：agent 命令只在其 workspace 目錄內執行
- 支援 exponential backoff 重試、startup 時的 terminal-state cleanup
- **WORKFLOW.md** 合約：teams version the agent prompt and runtime settings with their code

### 流派 C：Autonomous Supervisor Agent（遞迴監督）

Meta-agent **本身也是一個 agent**，自主決定何時介入、何時放手：

**ArgusBot** 的架構：
```
        ┌──────────────────┐
        │   Main Agent     │ ← 執行實際任務（Codex CLI / Claude Code CLI）
        └────────┬─────────┘
                 │
        ┌────────▼─────────┐
        │  Reviewer Agent  │ ← 評估完成度：done / continue / blocked
        └────────┬─────────┘
                 │
        ┌────────▼─────────┐
        │  Planner Agent   │ ← 維護框架視圖，提出下一步目標
        └──────────────────┘
        
        Loop 只在 reviewer 說 "done" 且 acceptance checks 全過時停止
        max_rounds 預設 500（是的，五百輪）
```

**metabot** 的模式：透過飛書/Telegram/微信在手機上遙控 agent team。支援 Claude Code、Kimi Code、Codex CLI 三引擎，每個 bot 可獨立選引擎。

### 趨勢：Cloud-Native Orchestration

**AgentControlPlane (ACP)** 把 agent 調度搬上 Kubernetes：
- **LLM** → **Agent** (LLM + System Prompt + Tools) → **Task** (Agent + User Message + Context) → **ToolCall**
- Tools 可以是 MCP Servers、Humans、**Other Agents**（遞迴委派）
- 支援 long-lived outer-loop agents 的非同步工具調用
- 12-factor-agents 設計原則

## 3. Why It Matters / Applications

### 3.1 從「寫 agent」到「管 agent」

這是最根本的範式轉移。2024 年大家忙著做單一 agent 的 prompt engineering；2026 年的問題變成：**當你有 50 個 agent 同時跑，如何不失控**。

Symphony 的定位很精準："teams manage work instead of supervising coding agents" — 工程師從監督 agent 程式碼變成管理需要完成的工作。

### 3.2 隔離性 = 可靠性

Erlang 哲學的核心洞察：**你不能防止 crash，但你可以保證 crash 不擴散**。這在 agent 場景尤為關鍵 — 一個 agent 的幻覺不該拖垮整個系統。

Symphony 的 per-issue workspace 隔離、ZeptoPM 的 per-agent OS process 隔離，都遵循同一原則。

### 3.3 遞迴監督

當 meta-agent 本身也是 agent，系統就具備了 **自我改進** 的潛力：
- ArgusBot 的 Reviewer → Planner → Main Agent 形成閉環
- 理論上可以往上疊加更多層（meta-meta-agent？）
- 但這也帶來新的風險（見 Limitations）

### 3.4 對 firn 的直接影響

我們的 firn 專案本質上就是一個 meta-agent 系統。Kanban orchestrator 分解任務 → worker agents 執行 → 結果回傳。Symphony 的 SPEC 直接為我們提供了可參考的架構藍圖。

## 4. Limitations / Honest Assessment

### 4.1 Orchestrator 的單點故障

所有 orchestrator-workers 模式共享一個致命弱點：**orchestrator 本身就是瓶頸和單點故障**。如果 orchestrator 的 LLM 產生幻覺，整個下游都受影響。

Anthropic 自己承認：「這個模式適合複雜任務，但 orchestrator 的品質決定一切。」

### 4.2 成本爆炸

- ArgusBot 預設 max_rounds=500。如果 reviewer 一直說 "continue"，成本沒有上限
- 每增加一層 meta-agent 就增加一層 LLM 調用成本
- Symphony 的 concurrency limits 試圖控制這點，但仍然需要人工設定

### 4.3 遞迴監督的矛盾

誰來監督監督者？ArgusBot 的 reviewer 可能出錯（錯誤地說 done 或 continue）。理論上你需要無限層監督，實務上不可能。

**開源社群對此的誠實態度**：
- ArgusBot README 明確警告："Planner or reviewer quality can also cause repeated loops"
- 建議 "Always set clear acceptance checks, monitor runtime, and stop/re-scope when needed"
- ZeptoPM 的 README 坦承：「Symphony manages work at a high level. ZeptoPM manages the agents doing the work. **Same philosophy, different layer.**」— 暗示這不是 silver bullet

### 4.4 可複製性

| 方案 | 免費 API 可行？ | 瓶頸 |
|------|:---:|------|
| OpenAI Swarm / Agents SDK | ✅ | 但 handoff 品質在小模型上顯著下降 |
| LangGraph Supervisor | ✅ | 需要足夠聰明的 LLM 做 task decomposition |
| Symphony | ✅ | 開源（Apache 2.0），但最佳效果用 Codex + Linear |
| ArgusBot | ⚠️ | 需要 Claude Code / Codex CLI 訂閱 |
| ZeptoPM | ✅ | 完全開源，Rust 實作，支援 OpenRouter 等免費 provider |
| ACP | ⚠️ | 需要 Kubernetes + OpenAI API key |

### 4.5 反駁觀點：最簡單的方案往往最好

Anthropic 在 "Building Effective Agents" 中反覆強調一個觀點：**不要過早使用 agent 框架**。很多情況下，簡單的 workflow（prompt chaining → routing → parallelization）就夠了，不需要完整的 orchestrator-workers。

> "We suggest that developers start by using LLM APIs directly: many patterns can be implemented in a few lines of code."

這是對當前 multi-agent 框架爆炸的清醒反思。

## 5. Actionable for Our Projects

### 對 firn 的具體建議

#### 5.1 借鑒 Symphony 的 WORKFLOW.md 合約（實作難度：MODERATE）
- 目前 firn 的 agent prompt 散落在程式碼中
- Symphony 的 `WORKFLOW.md` 模式：YAML front matter（config）+ Markdown body（prompt），版本控制
- **行動**：將每個 firn worker 的 prompt 和設定提取為類似合約檔，放在 repo 根目錄

#### 5.2 引入 Per-Task Workspace 隔離（實作難度：MODERATE）
- Symphony 的核心安全機制：每個 issue/task 有獨立 workspace 目錄
- firn 已經在用 git worktree 隔離（見 `worktree-subagent-isolation` skill），但尚未強制執行
- **行動**：在所有 worker agent 執行前確保 workspace 隔離，防止跨任務污染

#### 5.3 實作 Reviewer-Planner Loop（實作難度：HARD）
- ArgusBot 的 done/continue/blocked 評估迴圈可以移植到 firn
- 目前 firn 的 kanban-worker 執行完就結束，沒有 review 迴圈
- **行動**：在 worker 完成後增加一個輕量 reviewer（用免費模型即可）檢查輸出品質

#### 5.4 採用 Erlang 風格的 Crash-Only 設計（實作難度：MODERATE）
- 不要試圖防止 agent crash，而是設計 crash 後的自動恢復
- ZeptoPM 的設計：exponential backoff restart、session persistence across restarts
- **行動**：firn worker 的 session state 應持久化，crash 後可恢復而非從頭開始

#### 5.5 輕量 Orchestrator 而非重型框架（實作難度：MODERATE）
- 不要引入 LangGraph/CrewAI 等重型依賴
- Anthropic 的建議：直接用 LLM API，coordinator 用 ~200 行 Python 就夠
- **行動**：保持 firn 的 kanban-orchestrator 輕量，只加 Symphonoy 的核心概念（retry queue、reconciliation）

### 實作優先級排序

| 建議 | 難度 | 影響 | 優先級 |
|------|:--:|:--:|:--:|
| WORKFLOW.md 合約 | Moderate | 高 | ★★★ |
| Per-task workspace 隔離 | Moderate | 高 | ★★★ |
| Crash recovery / state 持久化 | Moderate | 中 | ★★ |
| Reviewer loop | Hard | 中 | ★★ |
| 輕量 orchestrator 重構 | Moderate | 中 | ★ |

## 6. Follow-up Questions

1. **Orchestrator 的自我糾錯**：當 ArgusBot 的 reviewer 錯誤判斷時，有沒有辦法讓 orchestrator 自我修正？能否結合昨天的「自我糾錯與反思」研究成果（CCI、SAGE、SSRP）？
2. **Supervisor-as-Code**：Symphony 的 WORKFLOW.md 把 agent policy 變成程式碼倉庫的一部分。這能不能擴展到整個組織的 agent governance？
3. **跨 Agent 的共享記憶**：多個 worker 的 context 如何在 orchestrator 層匯總？現有方案（Session/Context Window）的極限在哪？
4. **Meta-meta-agent**：三層以上的遞迴監督在什麼場景下有意義？何時會變成過度工程？
5. **Agent 的「死亡」定義**：什麼算 agent crash？無限 loop？token 耗盡？產出品質低於閾值？需要形式化定義。

---

### 原始來源

1. https://github.com/openai/symphony — **GitHub Repo (OpenAI 官方)** — **HIGH** — OpenAI 開源的 agent orchestrator，附完整語言無關 SPEC.md，★23,758
2. https://www.anthropic.com/engineering/building-effective-agents — **Blog (Anthropic 官方)** — **HIGH** — 定義 orchestrator-workers 等關鍵 agentic workflow 模式
3. https://github.com/openai/swarm — **GitHub Repo (OpenAI)** — **HIGH** — 輕量 multi-agent handoff 框架，已演化為 Agents SDK，★21,485
4. https://github.com/waltstephen/ArgusBot — **GitHub Repo** — **MEDIUM** — 24/7 supervisor agent，含 Reviewer + Planner sub-agent 迴圈，★301
5. https://github.com/humanlayer/agentcontrolplane — **GitHub Repo** — **MEDIUM** — Kubernetes-based agent orchestrator，支援 long-lived outer-loop agents，★403
6. https://github.com/xvirobotics/metabot — **GitHub Repo** — **MEDIUM** — 受監督的自我進化 agent 組織，手機遙控 Claude/Kimi/Codex，★752
7. https://github.com/qhkm/zeptopm — **GitHub Repo** — **MEDIUM** — Erlang-inspired process supervision for LLM agents，~7 MB per agent，★5
8. https://github.com/SeemSeam/claude_codex_bridge — **GitHub Repo** — **MEDIUM** — Multi-agent CLI teams with tmux supervision and project memory，★2,568
9. https://github.com/sagents-ai/sagents — **GitHub Repo** — **MEDIUM** — Elixir/OTP native supervision for agents with middleware and HITL，★228
10. https://github.com/openai/openai-agents-python — **GitHub Repo (OpenAI 官方)** — **HIGH** — 生產級 Agents SDK，含 handoff、sandbox agents、guardrails、tracing
11. https://github.com/crewAIInc/crewAI — **GitHub Repo** — **HIGH** — 最流行的 role-playing multi-agent 框架，★51,398
12. https://github.com/StruggleY/Fo-Sentinel-Agent — **GitHub Repo** — **LOW** — Supervisor-Worker 分層推理架構用於企業安全，★8

---

**可信度摘要**：4 個 HIGH（官方來源）、6 個 MEDIUM（開源專案具實作但未經學術驗證）、1 個 LOW（單一企業專案）。核心主張（orchestrator-workers 模式、OS 層級隔離、遞迴監督）被多個來源交叉驗證。

---

*下一個工作日排程執行本指令。*
