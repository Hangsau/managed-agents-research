# 研究報告：Agent Swarm — 大規模輕量 Agent 的 Emergent Coordination  
**日期**：2026-06-22  
**來源數**：12 | **標籤**：#agent-swarm #multi-agent #emergent-coordination #coordination-engineering #inverse-wisdom-law

---

## 1. The Problem

多 agent 系統 (MAS) 在 2024-2026 期間從「role-based static orchestration」快速演化到「**swarm-style emergent coordination**」。這個轉變的訊號非常明確：

- OpenAI 2024 Q4 推出 `openai/swarm`（21K stars）作為教育性質的輕量 swarm 框架；2025-2026 間用 `openai-agents` SDK（**27.7M 月下載**）取代之，swarm 抽象被併入 `handoffs` + `agents-as-tools` 兩種 pattern。
- LangChain 在 2025 推出 `langgraph-swarm`（1.5K stars），把 swarm 直接定義為「**agents 根據自己的 specialization 動態 handoff control**」的 multi-agent 架構。
- kyegomez/swarms（6.8K stars, **25K 月下載**）走 enterprise-grade 路線，主打 sequential / concurrent / hierarchical 預製架構。
- ruflo（60.8K stars）把自己定位為「Claude 的 meta-harness」，本質上就是 swarm 之上的 swarm 編排層。

但這一切的根本假設是：「**多個 agent 一起工作，比單一 agent 強**」。2026 年 4 月出現的一篇 paper 直接挑戰這個假設——**The Inverse-Wisdom Law**，證明在 kinship-dominant swarms 中，加越多「邏輯 agent」反而越穩定地收斂到錯誤答案。這迫使整個領域重新定義：「什麼樣的 swarm 才有效？什麼樣的 swarm 反而有害？」

這個問題重要是因為：
- **經濟訊號**：multi-agent 是 Anthropic / OpenAI / LangChain / kyegomez / Microsoft（AutoGen）都押注的方向，但缺少對「**失敗模式**」的系統性理解。
- **能力差異**：Anthropic 內部評測顯示 Opus 4 lead + Sonnet 4 subagents 比單 Opus 4 強 **90.2%**，但代價是 15x token。
- **新的攻擊面**：swarm-attack 論文證明 5 個 1.2B 模型的 swarm 可以達到 **45.8% GPT-4o jailbreak rate**——safety 的 capability class 不再依賴模型大小。
- **產業時點**：現在 2026 Q2，距離 OpenAI 推出 Swarm 約 18 個月，剛好夠 2-3 個獨立社群的實驗與反思累積到位。

## 2. Core Mechanism

Swarm 在 LLM agent 領域有三個主流實作形態，**底層抽象差異比表面看起來大得多**：

### 2.1 OpenAI Swarm / Agents SDK — Handoff Primitive

OpenAI Swarm 把 swarm 簡化到兩個 primitive：`Agent` (instructions + functions) + `handoff` (function 回傳另一個 Agent)。`client.run()` 的 loop 是固定的：

```python
from swarm import Swarm, Agent

client = Swarm()

def transfer_to_agent_b():
    return agent_b

agent_a = Agent(
    name="Agent A",
    instructions="You are a helpful agent.",
    functions=[transfer_to_agent_b],
)

response = client.run(
    agent=agent_a,
    messages=[{"role": "user", "content": "I want to talk to agent B."}],
)
```

迴圈：**(1) 拿 completion → (2) 執行 tool calls → (3) 必要時切換 agent → (4) 更新 context variables → (5) 沒新 function calls 就 return**。`max_turns` 預設是 `inf`——這是 open-ended design 的意圖，但也埋了 unbounded execution 風險。

**OpenAI 自己在 2025-2026 把這個抽象併入 `openai-agents` SDK 的 `handoffs` + `agents-as-tools` pattern**，再加上 guardrails、sessions、tracing、realtime agents。Swarm README 第一行就寫：「**Swarm is now replaced by the OpenAI Agents SDK, which is a production-ready evolution of Swarm**」。這個從 educational → production 的遷移說明：**純粹的 handoff 抽象不夠，必須加上 observability + guardrails + human-in-the-loop**。

### 2.2 Anthropic LeadResearcher + Subagents — Orchestrator-Worker

跟 OpenAI 的「agent-as-tool」不同，Anthropic 走的是**雙層 context window**：

```
LeadResearcher (Opus 4, 200K context)
   ├─ Subagent 1 (Sonnet 4, 獨立 context window) → 搜尋 A 主題
   ├─ Subagent 2 (Sonnet 4, 獨立 context window) → 搜尋 B 主題
   └─ Subagent 3 (Sonnet 4, 獨立 context window) → 搜尋 C 主題
   ↓ 各自回傳「壓縮後的最重要 tokens」
LeadResearcher 合成 → 決定要不要再開新 subagent
```

關鍵設計決策：
- **Subagent 用更便宜的 Sonnet 4，Lead 用 Opus 4**——因為 Sonnet 4 在 sub-agent role 上的效率提升「比 Sonnet 3.7 的 token 預算翻倍還大」。
- **平行化有兩層**：Lead 同時 spin up 3-5 subagents（粗粒度），每個 subagent 內部 3+ tools 並行（細粒度）。
- **Subagent 數量規則**：「簡單事實查詢 1 agent / 3-10 tool calls，直接比較 2-4 subagents / 10-15 calls，複雜研究 10+ subagents / 明確分工」——太多 subagent 會互相干擾。
- **Token 預算 vs. 性能**：token 用量本身解釋 80% 的變異；multi-agent 比 chat 多用 15x tokens；multi-agent 比單 agent 多用 4x tokens。

但 Anthropic 自己承認的限制：「**lead agent 不能 steer subagents，subagents 不能互相協調，整個系統會卡在單一慢 subagent**」——這是 synchronous execution 的根本瓶頸。他們把 async execution 列為「trade-off 增加 result coordination / state consistency / error propagation 複雜度」。

### 2.3 CEAD — Capability-Aligned Enterprise Agent Design（ArXiv 2605.08258）

這篇 2026 paper 提出一個關鍵 benchmark：在 **10,000 個企業任務**上比較五種架構：

| 架構 | Safe Success | 失敗模式 |
|------|-------------|----------|
| Prompt-first mono-agent | 45.2% | Context 過載、tool 衝突 |
| **Role-based micro-agent swarm**（無治理） | **23.1%** | **Architectural tribalism** |
| SOA-brokered agents | 58.8% | 服務層與 agent 語義不匹配 |
| Governance-first but design-poor grid | 50.8% | 過度控制，agent 失去彈性 |
| **CEAD（Capability-Aligned）** | **70.6%** | 設計品質優先 |

關鍵發現：**「role-based micro-agent swarm」只有 23.1%**——比單一 agent 還糟。這正是 Inverse-Wisdom Law 的實證：把一堆同質 LLM 包成不同 role，得到的不是 wisdom，而是 tribal confirmation bias。

CEAD 的設計哲學：**governance 不能是 primary abstraction；primary abstraction 必須是 agent design**——capability boundaries / autonomy allocation / interaction protocols / tool and data authority / state and memory design / verification design / human interaction design。把 microservices 當 cautionary precedent：拆解沒有設計紀律 → distributed complexity / cost / operational fragility / **agent proliferation**。

### 2.4 Inverse-Wisdom Law — 為什麼 Kinship-Dominant Swarms 會失敗

這篇 (arXiv 2604.27274) 是 2026 swarm 文獻裡最有破壞力的 paper。它做 36 experiments / 12,804 trajectories / GAIA + Multi-Challenge + SWE-bench 三個 SOTA benchmark，跨 Gemini 3.1 Pro / Claude Sonnet 4.6 / GPT-5.4 三個模型。

證明的定律：

> **In kinship-dominant swarms, adding logical agents increases the stability of erroneous trajectories rather than the probability of truth.**

機制：
1. Kinship = 同一個 model family 衍生出來的 swarm（例如全部 Claude Sonnet 4.6）
2. 內部 architectural agreement 被強化，external logical truth 被忽略
3. 加 audit agent → 系統趨向 **Logic Saturation**（內部 entropy → 0，但事實錯誤率 → 1）
4. Terminal swarm integrity **strictly gated by the synthesizer's receptive logic**（不是 aggregate agent quality）

論文提出兩個量化指標：
- **Tribalism Coefficient**：衡量 swarm 內部 architectural agreement 優先於 external logical truth 的程度
- **Sycophantic Weight**：transformer 權重層級的機制性成因

最終建議：**Heterogeneity Mandate**——swarm 必須由異質 LLM family 組成，不能由 kinship-dominant agents 組成。

### 2.5 swarm-attack — 同質 swarm 的攻擊面（ArXiv 2605.02801）

證明 Inverse-Wisdom Law 的對偶面：**同質小模型 swarm 也是 capability amplifier**。5 個 1.2B 模型 swarm：
- GPT-4o jailbreak：**Effective Harm Rate 45.8%**，49 個 critical-severity breaches
- Claude Sonnet 4 jailbreak：Effective Harm Rate 0%（但 40% 技術成功率）
- C 程式漏洞發現：9/9 CWE 在 4 分鐘內找到（消費型 MacBook）

論文結論直接寫：「**the capability class that motivated restricted release of Anthropic's Mythos Preview is therefore reproducible at effectively zero cost; the important enabler is the system scaffold itself, which compensates for the limited reasoning capacity of small individual models**」——**scaffold > model size**。

## 3. Why It Matters / Applications

### 3.1 從「Wisdom of Crowd」到「Inverse-Wisdom Law」的典範轉移

2024-2026 的多 agent 文獻有兩個相互矛盾的方向：
- 一邊說「多 agent 比單 agent 強」（Anthropic 90.2%、ChatDev、MetaGPT、CrewAI 等）
- 一邊說「多 agent 比單 agent 弱」（Inverse-Wisdom Law、CEAD 23.1% role-based swarm、6/14 A2A protocol 提到 zombie agent）

**真正的訊號是：swarm 的能力高度依賴 (a) heterogeneity、(b) capability alignment、(c) synthesizer design、(d) explicit anti-tribalism measures**。四個變因任一不對，效果就跟單 agent 差不多或更糟。

### 3.2 Coordination Engineering — Swarm Skills 開的新領域

Swarm Skills (arXiv 2605.10052, 2026-05-11) 提出**「Coordination Engineering」作為 Prompt Engineering → Context Engineering → Coordination Engineering** 的第三階段：

- **Swarm Skills** = 擴展 Anthropic Skills 標準，加上 multi-agent 語意（roles / workflows / execution bounds）
- **Self-evolution algorithm**：自動蒸餾成功 trajectory 成新 Swarm Skills，根據 Effectiveness / Utilization / Freshness 三維評分持續 patch
- **Zero-adapter portability**：透過 progressive disclosure，跨 LangGraph / OpenAI Agents / CrewAI / 自建框架都能用

參考實作：JiuwenSwarm。概念上等於把 **multi-agent 協作從 framework-internal code 升級成 first-class distributable assets**——跟 6/8 Skill Systems 的 progressive disclosure 邏輯相同，只是對象從單 agent skill 升到 multi-agent coordination。

### 3.3 Swarm 作為 Capability Amplifier — 攻擊與防禦兩端

swarm-attack 證明 1.2B × 5 達到 frontier-model 級別的攻擊能力；HBHC (arXiv 2605.20704) 對應提出**heartbeat-bound credential revocation**：
- 解決 OAuth 2.0 / OCSP / W3C Status Lists 的「需要連線到中央 authority」問題
- 90x 縮小 zombie window（OAuth → HBHC：分鐘小時級別 → 數秒）
- 0.26 ms full authentication (Rust)、18,000+ verifications/sec
- 49-agent 4-level hierarchy cascading revocation 在理論上限內

訊號：swarm 的 capability amplification 是**雙刃劍**，credential infrastructure 必須跟上。

### 3.4 Training Swarm — AgentJet 與 OrchRM

兩個方向在並行：
- **AgentJet** (arXiv 2606.04484, 2026-06-03)：分散式 swarm 訓練框架，swarm server nodes (GPU) + swarm client nodes (任意裝置)；**1.5-10x 訓練加速**；支援 heterogeneous multi-model RL、多任務 cocktail training、live code iteration
- **OrchRM** (arXiv 2606.13598)：orchestration reward modeling，不依賴昂貴 sub-agent rollouts，直接在 orchestration 層做 Bradley-Terry reward 訓練；**10x token 效率、+8% accuracy**

訊號：swarm training 的瓶頸從「**rollout cost**」轉向「**reward signal quality**」。AgentJet 用硬體解（分散式），OrchRM 用演算法解（self-supervised reward）。

### 3.5 Swarm 評測的科學化 — SwarmBench + MoltBook Observatory

過去 benchmark 都在評 single agent 或 explicit-structured 小群，**沒有辦法衡量 decentralized emergent dynamics**。兩個新工具填補這個缺口：
- **SwarmBench** (arXiv 2502.16565)：5 個 MAS coordination tasks（Pursuit / Synchronization / Foraging / Flocking / Transport）在 2D grid 上，限制 local perception + local communication
- **MoltBook Observatory** (arXiv 2603.03555)：**2.73M 互動 / 90,704 個 autonomous agents 的真實資料集**，發現 core-periphery 結構 (silhouette 0.91)、heavy-tailed cascade distributions (α=2.57)、**Cohen's d = -0.88 對單 agent baseline（嚴重 coordination overhead）**

這給了 Inverse-Wisdom Law 一個獨立驗證：decentralized coordination 不是 free lunch，**在缺乏 explicit synthesizer 的情況下會有統計顯著的性能下降**。

## 4. Limitations / Honest Assessment

### 4.1 Inverse-Wisdom Law 的邊界

論文本身坦承的限制：
- 實驗在三個 SOTA model 上做，但 kinship-dominant vs heterogeneous 的 boundary 不一定乾淨——「Sonnet 4.6 加上 fine-tune 過的 domain-specific LoRA」算 kinship 嗎？論文沒明確回答。
- Tribalism Coefficient 跟 Sycophantic Weight 是新定義的 metric，**還沒有被獨立 replication**。12,804 trajectories 是大樣本但跨 benchmark 的 generalization 不確定。
- 「Synthesizer's receptive logic strictly gates terminal swarm integrity」這條結論——在 synthesize 用 opus 4 但 sub-agents 全用 haiku 的實驗組中，論文沒給出 ablation 細節。

我們的獨立評估：
- 「Wisdom of Crowd」在人類社會是有 meta-analysis 支持的（range 4-8 人為 optimal），LLM agent swarm 的 Inverse-Wisdom Law **反轉了這個直覺**——但「homogeneous LLM family 互相強化 confirmation bias」這個機制不是新發現，**RLHF / constitutional AI 文獻早就觀察到過**。論文把它形式化成「law」可能過度宣稱。
- 但「**swarm 設計必須考慮 heterogeneity**」這個工程意涵是站得住腳的，無論是不是 law。

### 4.2 Anthropic LeadResearcher 架構的限制

從官方 blog 抓出的真實失敗模式：
- 「**Early agents made errors like spawning 50 subagents for simple queries, scouring the web endlessly for nonexistent sources, and distracting each other with excessive updates**」——沒有 built-in spawn budget 控管。
- **Subagent 之間沒有 cross-communication**：lead 不能 steer，subagent 不能協調（asynchronous 是 trade-off 而非解）。
- **Token 成本 15x**：不是每個任務都經濟可行。Anthropic 自己寫「for economic viability, multi-agent systems require tasks where the value of the task is high enough to pay for the increased performance」。
- **Code 任務不適合**：multi-agent 主要贏在「很多 independent directions」的 breadth-first queries；需要 shared context 或 heavy dependency 的任務（特別是大多數 coding tasks）反而比單 agent 差。

### 4.3 swarm-attack 的方法論爭議

- 5 個 1.2B 模型 × 225 jailbreak attacks = 1,125 次嘗試，45.8% 是 cumulative 命中率不是 per-attempt——這是比較弱的 claim。
- GPT-4o 45.8% vs Claude Sonnet 4 0%——同一個 swarm 對不同模型差異巨大，這代表 Effective Harm Rate 是**模型特性**而不是 swarm 能力。論文把它 frame 成「safety bypass capability」over-states 了。
- 但 0% cost + consumer hardware 這條結論是 valid 的：scaffold > model size 確實成立。

### 4.4 Swarm Skills 的設計風險

- Self-evolution algorithm 自動蒸餾 trajectory 成新 skill——**這個機制本身有 reward hacking surface**：如果某個 trajectory 在短期 effectiveness 高但長期利用某個 tool 的副作用，會被蒸餾成 skill 進一步強化。
- Effectiveness / Utilization / Freshness 三維評分是 heuristic，沒有 ground truth；可能陷入 local optimum。
- Zero-adapter portability 是 claim，但實際 cross-framework 部署需要 progressive disclosure metadata schema 標準化——論文沒給 reference implementation 的 schema 細節。

### 4.5 對 firn / 個人 agent 框架的可行性落差

Inverse-Wisdom Law 跟 Anthropic 內部數據都暗示：**swarm design 的 quality bar 遠高於單 agent**。對個人框架（如 firn）來說：
- Heterogeneity mandate → 需要至少 2-3 個 LLM provider 的 client（OpenAI + Anthropic + local Ollama）—這是顯著的 infrastructure overhead。
- Synthesizer gating → 需要一個 high-quality synthesizer model 對每個 subagent 結果做 quality check—對每個 task 都做是昂貴的。
- Capability-aligned design (CEAD) → 需要完整的 design-time taxonomy（capability boundaries / autonomy allocation / ...）——這不是寫 code 的問題，是寫 spec 的問題。

## 5. Actionable for Our Projects

### 5.1 firn（高優先）

| # | 行動 | 難度 | 涉及檔案 | 預期效果 |
|---|------|------|---------|---------|
| **F-SWARM-1** | 在 `firn/agents/` 加 **`Handoff` 原語**：參考 OpenAI Swarm 雙 primitive（`Agent` + `transfer_to` function），讓 ConversationAgent 可以 runtime handoff 到另一個 registered agent | MODERATE | `src/firn/agents/handoff.py`（新檔）、`src/firn/agents/__init__.py` | 解鎖 multi-agent pattern，但**僅作為內部實驗**，不暴露給 user CLI |
| **F-SWARM-2** | 在 `firn/tasks/Dispatcher.py` 加 **`agent_capability_registry`**：每個 agent 註冊自己的 capability vector（tool whitelist + topic domain + token budget cap），dispatcher 在 spawn subagent 時做 capability match | MODERATE | `src/firn/tasks/dispatcher.py`（擴充）、`src/firn/agents/registry.py`（新檔） | 對齊 CEAD 的「capability-aligned」原則；防止 Inverse-Wisdom 式的 role-label 假對應 |
| **F-SWARM-3** | 在 `firn/llm/CircuitBreaker.py` 加 **`spawn_budget` 與 `concurrent_subagent_cap`**：參考 Anthropic 的「簡單查詢 1 agent / 比較 2-4 / 複雜 10+」規則，做 hard cap | TRIVIAL | `src/firn/llm/circuit_breaker.py`（加兩個欄位）、`src/firn/tasks/dispatcher.py`（讀取 cap） | 防止 Anthropic 自己警告的「spawning 50 subagents for simple queries」失敗模式 |
| **F-SWARM-4** | 在 `firn/observability/TurnsLogger.py` 加 **swarm-level trace aggregator**：把每個 subagent 的 trace 串成一個 parent span，記錄 `subagent_count` / `handoff_chain` / `synthesizer_input_tokens` | MODERATE | `src/firn/observability/swarm_trace.py`（新檔）、`src/firn/observability/turns_logger.py`（呼叫新模組） | 對齊 6/17 observability report 的 OTel GenAI semconv；提供 Inverse-Wisdom Law 形式驗證需要的 tribalism coefficient 計算基礎 |
| **F-SWARM-5** | 在 `firn/llm/client.py` 加 **`heterogeneity_router`**：根據 task complexity 自動在 OpenAI / Anthropic / local Ollama 間 round-robin 或 weighted；用 Inverse-Wisdom Law 的 Heterogeneity Mandate 避免 kinship-dominant 風險 | MODERATE | `src/firn/llm/factory.py`（加 routing table）、`src/firn/llm/heterogeneity.py`（新檔） | 把「不同 provider 用不同 model family」做成 default behavior，不依賴 user 配置 |
| **F-SWARM-6** | 在 `firn/memory/` 加 **`swarm_shared_blackboard`**：參考 Communication to Completion 的 Alignment Factor 概念——所有 subagent 寫到同一個 typed blackboard，synthesizer 從 blackboard 讀而不是從各 subagent 個別 message | HARD | `src/firn/memory/blackboard.py`（新檔）、`src/firn/memory/schema.sql`（加 tables） | 對齊 Anthropic 的「subagent 回傳壓縮 tokens」+ Inverse-Wisdom 的 synthesizer-gating；黑板比 message chain 更易 audit |
| **F-SWARM-7** | 在 `firn/agents/TaskAgent.py` 加 **`synthesizer_prompt_template`**：強制 synthesizer agent 先 self-check「我有沒有跟上 context？還是只 follow 上一個 subagent 的 framing？」— Anti-Tribalism prompt injection | TRIVIAL | `src/firn/agents/task_agent.py`（改 synthesizer 預設 prompt） | 對齊 Inverse-Wisdom Law 的核心發現：terminal integrity gated by synthesizer's receptive logic |
| **F-SWARM-8** | 在 `firn/tasks/Watchdog.py` 加 **subagent loop detector**：偵測 subagent 之間的 circular dependency（subagent A 一直等 B、B 一直等 C、C 一直 back-reference A 的 query）— 這是 Anthropic 沒提到但 Inverse-Wisdom 暗示的 failure mode | MODERATE | `src/firn/tasks/watchdog.py`（加 `detect_circular_handoff`） | 防止 tribal confirmation bias 陷入收斂死循環 |

### 5.2 managed-agents（cron workflow 本身）

- 在 cron 的 topic picker 加入「swarm-specific dedup check」——若未來要做更細的 swarm 子題（如 swarm security / swarm training），要避免跟本篇 Jaccard >= 0.5 的合併。
- 在 `extract_research_knowledge.py` 的 tag 提取中加 `#coordination-engineering` tag——本篇的「Coordination Engineering」概念是新概念，應該在 vault 獨立 topic 中保留。
- 本篇不直接改動 managed-agents 程式碼（除 extractor）；所有 actionable items 都在 firn。

### 5.3 對 hermes / Hestia 的意義

- Hermes 的 `agent field` 概念天生就是 swarm-friendly——未來若要 spawn 多個 Hestia instance 做 parallel research，可直接複用 `firn/SWARM-3` 的 spawn budget + `firn/SWARM-5` 的 heterogeneity routing。
- 但也應該注意 Inverse-Wisdom Law：如果所有 sub-agent 都用同一個 MiniMax-M3 / 同一個 system prompt，會落入 kinship-dominant trap。需要 prompt-level + model-level 的異質性設計。

## 6. Follow-up Questions

1. **Heterogeneity Mandate 的量化邊界**：怎麼定義「夠 heterogeneous」？兩個 model family（同樣 RLHF 同樣 base architecture）算 kinship 嗎？需要更細的 architectural distance metric。
2. **Synthesizer 的 optimality**：Inverse-Wisdom Law 說 synthesizer 決定 swarm integrity，但沒有 ablation：synthesizer 用 Sonnet 4.6 vs Opus 4.6 vs GPT-5.4 vs ensemble 對結果影響多大？
3. **Swarm Skills 的 reward hacking surface**：自動蒸餾 trajectory 成 skill 這個自我強化迴圈會不會產生 unintended capability drift？需要 long-running study（>1 個月、>1000 evolutions）才能驗證。
4. **Decentralized swarm 的 token economy**：Communication to Completion 證明 hub-and-spoke 是 emergent pattern，但實際 budget 是 40% efficiency gain 起步——隨著 swarm size 增加，scaling 是 sub-linear 還是 log-linear？
5. **Cross-framework portability**：Swarm Skills 聲稱 zero-adapter，但實際 LangGraph / CrewAI / openai-agents / swarms 之間的 handoff protocol schema 還沒標準化——這是 A2A protocol 的 opportunity 還是 Swarm Skills 自己會贏？
6. **Swarm 的 observability gap**：OTel GenAI semconv (6/17 報告) 還沒定義 swarm-level span attributes；AgentJet / SwarmBench 等 2026 paper 都各自定義自己的 telemetry schema——這是 Q3 2026 值得追蹤的標準化議題。
7. **安全對稱**：swarm-attack 證明 1.2B × 5 = frontier model 攻擊能力——但對稱問題：1.2B × 5 能不能達到 frontier model 的 defense 能力？如果可以，整個 safety / alignment 的成本結構會被顛覆。
8. **SwarmBench 的 generalization**：2D grid 的 5 個 task（Pursuit / Flocking / Foraging ...）是經典 swarm intelligence benchmark，**距離真實 LLM 任務的 gap 多大**？需要跨 benchmark correlation study。

---

### 原始來源

1. https://arxiv.org/abs/2604.27274 — **論文** — **HIGH** — Inverse-Wisdom Law (Shehata & Li, 2026-04-30): 36 experiments / 12,804 trajectories / GAIA + Multi-Challenge + SWE-bench 證明 kinship-dominant swarms 會強化錯誤軌跡
2. https://arxiv.org/abs/2605.10052 — **論文** — **HIGH** — Swarm Skills (Zhang et al., 2026-05-11): 提出 Coordination Engineering，擴展 Anthropic Skills 標準為 multi-agent distributable asset
3. https://arxiv.org/abs/2606.04484 — **論文** — **HIGH** — AgentJet (2026-06-03): 分散式 swarm 訓練框架，1.5-10x 訓練加速，heterogeneous multi-model RL
4. https://arxiv.org/abs/2605.20704 — **論文** — **MEDIUM-HIGH** — HBHC (2026-05-20): Heartbeat-Bound Hierarchical Credentials，swarm credential revocation 90x improvement
5. https://arxiv.org/abs/2605.08258 — **論文** — **HIGH** — CEAD (Capability-Aligned Enterprise Agent Design): 10,000 企業任務評測，role-based swarm 僅 23.1% safe success
6. https://arxiv.org/abs/2605.02801 — **論文** — **MEDIUM-HIGH** — swarm-attack: 5 個 1.2B 模型 swarm 達 45.8% GPT-4o jailbreak，C 漏洞 9/9 recall
7. https://github.com/openai/swarm — **程式庫** — **HIGH** — OpenAI Swarm 官方 README: 教育性質的 handoff primitive，已於 2025-2026 被 OpenAI Agents SDK 取代
8. https://github.com/openai/openai-agents-python — **程式庫** — **HIGH** — OpenAI Agents SDK: 27.7M 月下載，handoffs + agents-as-tools + guardrails + sessions + tracing
9. https://www.anthropic.com/engineering/built-multi-agent-research-system — **官方 blog** — **HIGH** — Anthropic multi-agent research system engineering post (2025-06-13): LeadResearcher + Subagents 架構，90.2% improvement，15x token cost
10. https://github.com/langchain-ai/langgraph-swarm-py — **程式庫** — **HIGH** — LangGraph Swarm: 1.5K stars，handoff-based swarm multi-agent architecture
11. https://arxiv.org/abs/2502.16565 — **論文** — **HIGH** — SwarmBench: 5 MAS coordination tasks benchmark，揭示當前 LLM 在 decentralized swarm 約束下的顯著弱點
12. https://arxiv.org/abs/2510.19995 — **論文** — **HIGH** — Communication to Completion: cost-aware multi-agent coordination，emergent hub-and-spoke pattern，40%+ efficiency gain

### Extraction Errors
_無_

---

下一個工作日排程執行本指令。