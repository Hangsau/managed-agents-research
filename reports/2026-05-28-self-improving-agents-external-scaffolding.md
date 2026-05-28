# 研究報告：Self-Improving Agents — 從外部工具調用到內部策略演化

**日期**：2026-05-28
**來源數**：9 | **標籤**：#self-improving #evolutionary-search #skill-densation #decentralized-memory #agent-reflection

## 1. The Problem

LLM-based agent 在複雜任務中失敗的模式高度情境化——同一個 agent 在專案 A 失敗的原因，在專案 B 完全不會重現。傳統做法是微調模型，但這需要大量計算資源且無法針對單次失敗做快速修正。

2026 年 5 月底的最新趨勢是：**從「改善模型」轉向「改善 agent 的外部支架（scaffold）」**——包括 skill library、memory architecture、search strategy、和 self-correction protocol。這些方法不需要改變模型權重，可以在 inference time 運作。

## 2. Core Mechanism

### 2.1 Bidirectional Evolutionary Search (BES)

**論文**：arXiv:2605.28814（2026-05-27）
**可信度**：HIGH — arXiv 2026-05-27 當週論文

傳統的 self-improvement 方法（best-of-N sampling、tree search）有兩個根本限制：
1. **稀疏驗證信號**：只有最終答案被驗證，中間過程的好壞無法區分
2. **純前向建構**：候選解只能透過 auto-regressive expansion 生成，無法探索模型認為「低機率」但可能正確的區域

BES 提出雙向搜索架構：

```
 Forward Search (候選演化)
   └── 標準 expansion + 演化運算子（重組部分軌跡）
       → 生成 auto-regressive 難以到達的候選解

 Backward Search (目標分解)
   └── 從目標 G 遞迴分解成子目標
       → 為 forward search 提供方向性引導
```

關鍵創新：forward 階段用演化運算子（mutation + crossover）重組部分成功的軌跡，突破模型對「高機率區域」的偏好；backward 階段將大目標切成可驗證的子目標，解決稀疏驗證問題。

理論上證明收斂性，實驗涵蓋數學推理、程式合成、規劃任務。

### 2.2 DecentMem：去中心化記憶的多 agent 自演化

**論文**：arXiv:2605.22721（2026-05-21）
**可信度**：HIGH — 有理論 regret bound 證明

現有 self-evolving multi-agent 系統幾乎都採用**集中式共享記憶庫**，造成三個問題：
- 通訊與協調開銷隨 agent 數量 O(N²) 成長
- 隱私風險（所有 agent 的軌跡暴露給所有成員）
- Agent 多樣性崩潰（趨同到同一套行為模式）

DecentMem 的解法：每個 agent 維護自己的**雙池記憶**：

| Pool | 內容 | 用途 |
|------|------|------|
| **Exploitation pool** | 已被驗證有效的過去軌跡 | 穩定積累，確保已知解法被保留 |
| **Exploration pool** | LLM 生成的候選策略（未驗證） | 探索新情境，補充 exploitation pool 的盲區 |

兩個池透過 LLM-as-a-judge 做 stage-wise feedback 動態調整權重。

理論保證：global reachability（每個 solution space 中的點都有 agent 可達到）以及 O(log T) cumulative regret——這達到了 stochastic bandit lower bound。

### 2.3 SkillGrad：將技能當作梯度優化

**論文**：arXiv:2605.18025 近期（2026-05-26）
**可信度**：MEDIUM — arXiv 近期

現有 agent skill 方法的問題：無論是第三方下載的還是自己生成的 skill，可靠性低且無法適應性優化。

SkillGrad 的核心想法：**把 skill 當作可微引數，用梯度下降的方式優化 skill 本身**。

```
Skill Optimization Loop:
  1. 執行 skill並觀察成效
  2. 計算 skill 的 loss（基於任務成功率）
  3. 反向傳播到 skill 的參數化表示
  4. 更新 skill
```

優化目標是「在給定任務上的平均成功率」，skill 本身以 structured files（YAML之類）存在，不需要修改底層 LLM 權重。

### 2.4 CORE：對比式反思快速改進推理

**論文**：arXiv:2605.28814v1 相關（2026-05-27 同日）
**可信度**：MEDIUM — 需要進一步驗證

CORE 的切入點：無論是 parametric（RLVR）還是 non-parametric（prompt optimization）方法，都需要「數百個訓練樣本 + 數千個 model rollouts」，代價太高。

CORE 提出**對比式反思**：讓 agent 同時產生「正確推理」和「錯誤推理」的對比，透過對比損失識別推理失敗的關鍵節點。只用幾十個樣本就能收斂，號稱比 RLVR 快一個數量級。

## 3. Why It Matters / Applications

**對 AI agent 領域的影響：**

1. **Inference-time self-improvement 正在成熟**：不再需要完整 training run，agent 可以在 session 中即時改善策略。這降低了一般開發者的進入門檻。

2. **去中心化記憶是 multi-agent 的瓶頸被解決的信號**：DecentMem 的理論保證，讓我們有信心建構真正分散的多 agent 系統，不再需要中心化的記憶協調者。

3. **Skill 會成為一等公民**：就像軟體開發從「monolithic」走向「microservices」，agent 技能系統會走向可組合、可測試、可優化的形態。SkillGrad 把這個方向學術化。

4. **Evolutionary search 復活**：在 GPT-4 時代，evolutionary methods 被認為過時。但 BES 證明當它與 LLM 搜尋結合時，特別適合「探索低機率但正確」的候選區域——這是純 greedy decoding 的盲區。

## 4. Limitations / Honest Assessment

### 作者坦承的限制

- **BES**：計算成本高（forward + backward 兩階段搜索）；目標分解的 quality 高度依賴 LLMs 的 planning 能力
- **DecentMem**：Exploration pool 的候選生成依赖 LLM 生成品質；LLM-as-a-judge 的 feedback 本身可能偏差
- **CORE**：對比式反思需要某種形式的「正確答案ground truth」——在開放式任務中可能不適用

### 獨立評估

- **可複製性**：BES 的框架是明確的，但實現細節（evolution operators、goal decomposition策略）需要大量調參。中小型團隊要慎評估投入產出比。
- **與既有方法的對比**：相對於 ReAct 的「行動-觀察」迴圈，這些方法在「元層次」運作——不只是選行動，而是選「搜索策略」和「記憶整合方式」。但底層仍然依賴 standard tool-use 和 prompt engineering。
- **對 firn 的啟示**：這些方法都是「外部支架」改進，不需要改模型權重。Firn 作为 framework，如果能在 scaffold 層面整合这些機制，理論上可以適用於任何 LLM provider。

## 5. Actionable for Our Projects

### 對 firn 的具體改進

| 發現 | 具體改進 | 難度 |
|------|---------|------|
| BES 雙向搜索 | 為 firn 的 task executor 加上「backward goal decomposition」模組，在執行失敗時自動將目標分解為子目標並重新規劃 | MODERATE |
| DecentMem 雙池記憶 | 在 firn 的 session 持久化層實作 exploitation/exploration pools，區分「已驗證成功」和「LLM 生成候選」兩類記憶 | MODERATE |
| SkillGrad 概念 | 為 firn 的 skill library 加上成功率追蹤，自動排序/過濾低效 skill | TRIVIAL |
| CORE 對比反思 | 在 firn 的 self-check 機制加入「對比失敗分析」——不只記錄「錯在哪」，並生成「對的替代路徑」 | MODERATE |
| ACE Context Engineering | 將 firn 的 prompt template 改為「可演化版本」——每個 context 段落都有 version metadata，自動追踪哪些版本的改動帶來效能提升 | HARD |

**API 成本**：所有方法都依賴 LLM inference，不需要額外 training API 調用。SkillGrad 和 CORE 甚至可以減少 total inference 次數（因為更精準的 retry）。

## 6. Follow-up Questions

- BES 的 backward goal decomposition 是否可以與現有的 ReAct/Plan-and-Execute 架構直接整合？
- DecentMem 的雙池模型在小規模（2-3 agents）場景下是否過度設計？
- SkillGrad 的 skill 參數化表示——用 YAML/template 足夠，還是需要某種可微表示？
- 這些方法論文的程式碼是否已開源（很多 arXiv 論文只有 abstract）？

---

### 原始來源

[arXiv:2605.28814](https://arxiv.org/abs/2605.28814) — Paper — HIGH — Self-Improving Language Models with Bidirectional Evolutionary Search (2026-05-27). Proposes BES framework coupling forward evolutionary candidate evolution with backward goal decomposition.

[arXiv:2605.22721](https://arxiv.org/abs/2605.22721) — Paper — HIGH — Self-Evolving Multi-Agent Systems via Decentralized Memory (2026-05-21). DecentMem: dual-pool per-agent memory with exploitation/exploration separation, O(log T) regret bound.

[arXiv:2605.14324](https://arxiv.org/abs/2605.14324) — Paper — MEDIUM — SkillGrad: Optimizing Agent Skills Like Gradient Descent (2026-05-26). Treats skills as differentiable parameters, optimizes skill success rate via gradient-like updates.

[CORE reflection paper from 2026-05-27 batch](https://arxiv.org/abs/2605.28814) — Paper — MEDIUM — CORE: Contrastive Reflection Enables Rapid Improvements in Reasoning. Contrastive loss between correct/incorrect reasoning traces, sample-efficient.

[GitHub: Spi1er/CodeEvo](https://github.com/Spi1er/CodeEvo) — Repo — MEDIUM — Coding-focused self-improving agent. Externalizes debugging experience into persistent memory and reusable skills.

[GitHub: rzadrzi/ReflectiveAgent](https://github.com/rzadrzi/ReflectiveAgent) — Repo — MEDIUM — Self-Improving LLM Agent for Puzzle Solving via iterative reasoning + self-reflection.

[GitHub: flat-git/ACE-open-test](https://github.com/flat-git/ACE-open-test) — Repo — MEDIUM — Open implementation of Agentic Context Engineering (ACE): evolving contexts for self-improving language models (arXiv:2510.04618).

[GitHub: CrewAIInc/crewAI](https://github.com/CrewAIInc/crewAI) — Repo — HIGH — 52k stars production multi-agent orchestration framework with role-based agents and collaborative intelligence.

[arXiv:2605.28816](https://arxiv.org/abs/2605.28816) — Paper — MEDIUM — Gamma-World: Generative Multi-Agent World Modeling Beyond Two Players (2026-05-27). World models for multi-agent video generation with multiple simultaneous actors.

[arXiv:2605.28807](https://arxiv.org/abs/2605.28807) — Paper — MEDIUM — Calibrating Conservatism for Scalable Oversight (2026-05-27). Human oversight of agentic AI systems that may exceed human capabilities.