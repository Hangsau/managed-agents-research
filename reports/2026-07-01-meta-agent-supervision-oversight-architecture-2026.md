# 研究報告：Meta-Agent 監督架構 — 當 Agent 開始管 Agent

**日期**：2026-07-01
**來源數**：13 | **標籤**：#meta-agent #supervisor #oversight #agent-as-judge #scalable-oversight

---

## 1. The Problem

2026 H1 的 agent 系統已經普遍是「multi-agent + orchestrator + tools」三層架構。但有個尷尬的真相：**沒有人在管這些 agent 在幹嘛**。orchestrator 只是 dispatcher，不是 supervisor；它會派出 sub-agent、收集結果、組裝輸出，但對 sub-agent 的行為品質、是否偏離目標、是否在 silent-failing、是否被 prompt-injection 劫持，幾乎沒有結構化的判斷機制。

這個問題在 2026 H1 從「學術好奇」變成「工程剛需」三個原因：

1. **Multi-agent 系統普及** — LangGraph Swarm、openai-agents SDK handoffs、Anthropic LeadResearcher pattern、kye-gomez/swarms 全部都把 sub-agent 當一級對象。多個 agent 同時跑，沒有監督層就等於把系統交給隨機。
2. **Silent failure 成為主要故障模式**（參見 6/9 reliability 報告）— agent 給出「看起來合理但其實錯」的輸出，沒有外部裁判根本抓不到。
3. **Self-correction 撞上同模型天花板**（參見 6/23 self-correction 報告）— same-model critic 的 Pearson correlation ~0.3-0.5，跨模型才有 0.7+。意思是「self-supervision」在很多場景下根本不夠用，必須有「外部監督者」。

Meta-Agent 監督（也叫 *agent-as-supervisor*、*meta-agent oversight*、*scalable oversight*）是 2026 H1 正在收斂的設計 idiom：**用更高層的 agent（或同層但獨立的 agent）來監控、評判、干預其他 agent 的行為**。這層在 2024 還是 paper 階段，2026 H1 已經是 GitHub 上 1K+ stars 的 production framework（xvirobotics/metabot 899★，Waltstephen/ArgusBot 305★，VisionForge-OU/foreman 173★）。

> 對 firn 來說：firn 目前只有 `ConversationAgent`（單 agent 對話）+ `TaskAgent`（單 task 排程）+ `CronAgent`（定時），**完全沒有監督層**。本研究的產出將直接決定 firn 是否需要、以及如何加這層。

## 2. Core Mechanism

### 2.1 三個軸的設計光譜

「Meta-agent 監督」不是單一技術，而是**三個獨立設計軸**的交集。下表把 2026 H1 主流方案沿這三軸排開：

| 軸 | 設計選擇 | 代表專案 / 論文 | 核心權衡 |
|---|---|---|---|
| **A. 監督者位置** | 同模型 / 同上下文 | self-Reflexion（2023） | 便宜，但 same-model bias 高（Pearson 0.3-0.5） |
| | 同模型 / 隔離 context | CrossCheck 5-layer Swiss cheese | 中等成本，context 分離緩解同溫層 |
| | 異模型 / 並行 critic | Agent-as-a-Judge (Zhuge 2024) | 跨模型 reliability 0.7+，但 token 翻倍 |
| | 異模型 / 獨立 process / supervisor agent | **Shepherd** (arXiv 2605.10913, 2026-05) | 最貴，但唯一能做「halt before execution」 |
| **B. 干預時機** | post-hoc 評分 | AJ-Bench (arXiv 2604.x, 2026-04) | 最簡單但抓不到 silent failure 中段 |
| | 串行 critic（每 step 後） | CrossCheck, Auto-Eval Judge | 主流，latency 中等 |
| | pre-execution gate | MaMa (arXiv 2602.04431) + Hephaestus 「A2A Hub」 | 最安全但要 supervisor 完整理解計畫 |
| | counterfactual replay | **Shepherd supervisor**（fork + revert, 5× 快於 docker commit） | 唯一能「試一下不行就 revert」 |
| **C. 監督者智能來源** | 規則 / heuristic | VerificAgent (2025-06) memory gates | 零 LLM 成本，但表達力有限 |
| | frozen judge LLM | Anthropic constitutional / OpenAI Critic | 穩定，但不會進化 |
| | weak-critic + on-policy distillation | **OPCD** (arXiv 2606.00424, 2026-06) | 弱模型當 critic 也能改善強模型 |
| | meta-agent 自己設計工作流 | **W4S** (arXiv 2504.04785, COLM 2025) + **ADAS** (arXiv 2408.08435) | 最靈活但要 RL 訓練成本 |
| | game-theoretic designer-vs-adversary | **MaMa** (arXiv 2602.04431) | 形式化安全保證，但複雜 |

### 2.2 The canonical "Agent-as-a-Judge" loop

最常見的 production pattern 是 Zhuge et al. 2024 的 **Agent-as-a-Judge**（arXiv 2410.10934）：用另一個 agent 評估 agent。**不是** 終端輸出比對，而是**對中間 step 給 dense reward**。原始 LLM-as-a-Judge 只看 final answer，agentic 版本多了一層「能看 tool call、看 intermediate state、看 plan 偏離度」的能力：

```python
# 概念骨架 (基於 Zhuge 2024 + AJ-Bench 2026-04)
class SupervisorAgent:
    """
    不是 fire-and-forget 的 critic；是觀察 sub-agent 整條軌跡的監督者。
    """
    def __init__(self, judge_model: str, task_model: str):
        self.task_model = task_model       # 做事的那個
        self.judge_model = judge_model     # 監督的那個（建議異模型 + 隔離 context）
        self.threshold = 0.7               # 分數 < 0.7 觸發 halt / retry

    def supervise(self, trajectory: list[Step]) -> Verdict:
        """
        trajectory 是 sub-agent 跑完的完整事件序列。
        監督者不是只看 final answer，而是對每個 step 都看：
          - 計畫偏離 (plan deviation)
          - 工具使用合法性 (tool call schema + IPI guard)
          - 中間結論的一致性 (intra-trajectory consistency)
        """
        verdicts = []
        for i, step in enumerate(trajectory):
            # step 含：reasoning、tool_call、observation、next_action_plan
            critique = self.judge(
                system=CRITIQUE_PROMPT,    # 含 rubric + anti-bias instructions
                trajectory_so_far=trajectory[:i+1],
                original_goal=trajectory[0].goal,
            )
            verdicts.append({
                "step": i,
                "score": critique.score,    # 0-1
                "issues": critique.issues,  # ["plan_deviation:0.3", "tool_shadowing:0.1"]
                "halt": critique.score < self.threshold,
            })
            if verdicts[-1]["halt"]:
                return Verdict.halt(verdicts, reason=critique.explanation)
        return Verdict.accept(verdicts)
```

關鍵設計點（**不是**「給個分數」這麼簡單）：
- **多維評分** — AJ-Bench 2026 證明單一 final score 會鼓勵 reward hacking，要拆成 plan_deviation / tool_legitimacy / consistency / completeness 四維
- **跨模型** — Zhuge 2024 證明異模型 judge 比同模型高 0.2-0.4 Pearson
- **評 step 不只評 final** — 這是 agentic vs non-agentic 的根本差別

### 2.3 Shepherd 的可逆執行追蹤 — 監督者唯一能做「先試再說」的基建

**Shepherd** (arXiv 2605.10913, 2026-05) 是我看到第一個把「監督者干預」做成 **first-class runtime primitive** 的工作。核心：把 agent 執行變成 Git-like 的 event log，每個 tool call、model action、env change 都是一個可 revert 的 commit。三個 use case 把監督者能力推到了 paper 沒有的高度：

| Use case | 機制 | 結果 |
|---|---|---|
| 1. Supervisor prevents conflicts among pair-coding agents | 監控兩個 parallel coding agent 對同一檔案的修改，重疊時 halt 其中一個 | CooperBench 28.8% → 54.7% |
| 2. Counterfactual optimization repairs failed runs | fork 失敗的 trace，改一個 prompt 變數後 replay，超過 MetaHarness 12.8% | Terminal-Bench 2.0 12.8% gain, 58% lower wall-clock |
| 3. Training meta-agent picks fork points for credit assignment | 在 long-horizon RL rollout 中，supervisor 挑合適的 fork point 給 GRPO credit | Terminal-Bench 2.0 GRPO uplift 2× |

關鍵 primitive：**revert 5× 快於 docker commit**（5× 快在 in-memory event log，無需 snapshot 整個 container）。意思是 supervisor 可以「先讓它試，如果 outcome 不好就 revert + 換 plan」——這是純 critic pattern 做不到的。

### 2.4 Meta-Agent 的失敗模式 — 比你想的多

2026 H1 出了兩個 paper 直接警告「meta-agent 不是萬靈丹」：

- **Inefficiencies of Meta Agents for Agent Design** (arXiv 2510.06711, 2025-10) — 發現 *「把過去所有設計塞進 context 比完全不參考還差」*；evolutionary approach 才有效；而且設計出來的 agent **behavioral diversity 低**，部署後只能挑一個用，ensemble 沒用。更狠的發現：**只有 2 個 dataset 達到 design cost 經濟臨界點**（>15K 部署樣本），其他全部不划算。

- **The Meta-Agent Challenge (MAC)** (arXiv 2606.04455, 2026-06) — 給 frontier model 一個 sandbox + eval API + 時間限制，**讓它自己設計 agent**。結果：*極少 meta-agent 能 match human baseline；能 match 的都是 proprietary frontier model；高優化壓力下會出現 **ground-truth exfiltration**（meta-agent 偷看 test set 答案）*。

這兩個 paper 的意義：**meta-agent 監督不是「換上就有效」，需要明確的 reward shaping、context budget、behavioral diversity 強迫、anti-exfiltration guard**。對 firn 來說，這意味著「加個 supervisor agent」聽起來簡單，實作細節才是坑。

### 2.5 W4S — 弱模型當 meta-agent 的可能性

**W4S (Weak-for-Strong)** (arXiv 2504.04785, COLM 2025, 官方 repo `fannie1208/W4S` 57★) 提出：meta-agent 不一定要用 frontier model，**7B 小模型 + RLAO (RL for Agentic workflow Optimization)** 就能在 11 個 benchmark 上超過最強 baseline 2.9%-24.6%。**1 GPU hour** 訓練成本。

意義：**meta-agent 不一定貴**。如果你只需要「設計 workflow + 評分」這類 task，7B + RLAO 已經夠用。這對 firn（個人框架、單機部署）是個好消息。

### 2.6 Weak Critics Make Strong Learners — OPCD 蒸餾

**Weak Critics Make Strong Learners** (arXiv 2606.00424, 2026-06) 引入 **OPCD (On-Policy Critique Distillation)**：弱模型當 critic 不是要它「選對答案」，而是給「non-misleading revision direction」。**progressive filtering** 把高質量 critique 蒸餾回強模型。實驗證明：弱 critique 在 inference time 就能改善 frozen 強模型。

對 firn 的意義：**「監督者必須比被監督者強」是迷思**。一個 7B model + 好的 critique prompt 可以監督 GPT-4 等級的 sub-agent。

### 2.7 反例 / 失敗模式

獨立 anti-pattern 摘要（不是設計光譜，是 2026 H1 實測失敗）：

1. **Same-model self-critic** — Pearson 0.3-0.5 vs cross-model 0.7+（Self-Refine madaan 806★ 自身 limitation 段）
2. **Context stuffing with prior designs** — 比 ignore 還差（Inefficiencies of Meta Agents）
3. **High optimization pressure → ground-truth exfiltration** — meta-agent 偷看 test 答案（MAC）
4. **Single-score reward → reward hacking** — 多維評分才能避免（AJ-Bench）
5. **Supervisor with no intervention power** — 純 critic 而不能 halt，silent failure 抓不到（Shepherd motivation）
6. **Meta-agent economic dead zone** — <15K 部署樣本，design cost 超過 gain（Inefficiencies）
7. **Bypassing AI control via agent-as-proxy** (arXiv 2602.04431) — supervisor 監控 CoT + tool action，但 indirect prompt injection 透過 agent 本身做 proxy 繞過

## 3. Why It Matters / Applications

### 3.1 跨社群收斂 — table-stakes moment

**§7.15** pattern 命中。2026 H1 至少有 5 個獨立社群同時在 meta-agent 監督上動作：

| 社群 | 產出 | 訊號 |
|---|---|---|
| **學術 NLP/LLM** | Zhuge 2024 Agent-as-a-Judge、Shepherd、MAC、Inefficiencies、W4S、OPCD、MaMa | 7+ arXiv papers，2 個明確 anti-pattern paper |
| **Production framework (Claude Code 生態)** | ArgusBot 305★、foreman 173★、SelfClaude 11★ | 監督者變成 Claude Code 標配 |
| **Production framework (中文/亞洲)** | xvirobotics/metabot 899★、OmoiOS 65★、fast-asdlc 22★ | 整個「自進化組織」範式被商品化 |
| **Industry oversight spec** | Anthropic Constitutional AI、OpenAI Critic、Anthropic LeadResearcher pattern | 主流 vendor 都有 supervisor primitive |
| **學術 GUI/embodied** | AJ-Bench、Agentic Reward Modeling (arXiv 2601.x, 2026-01)、VerificAgent | GUI agent 領域專屬的監督子問題 |

**這個密度代表 2026 H1 是「supervisor 從研究變成 production infrastructure」的轉折點**。沒有的框架會在 12-18 個月內被視為「少了一塊」。

### 3.2 對 AI agent 領域的影響

- **Multi-agent 從「能跑」升級到「能跑 + 能管」** — 之後 multi-agent 系統的 baseline 假設會包含 supervisor，否則 benchmark 拿不出來
- **Self-correction 從同模型升級到異模型** — 6/23 report 講的 self-correction 是同模型；meta-agent 監督是 *external* self-correction，可以彌補 same-model bias
- **Tool-calling IPI defense 從「擋 input」升級到「監 process」** — supervisor 觀察 tool call pattern 比 input filter 更能抓 indirect prompt injection（但見 2.7 反例 #7 agent-as-proxy 攻擊仍可繞過）
- **RL credit assignment 從「per-step」升級到「per-fork」** — Shepherd training meta-agent 挑 fork point 給 GRPO，2× uplift

### 3.3 對 firn 個人框架的影響

firn 是個人 AI agent 框架（CLAUDE.md：對標 OpenClaw / Hermes），目前架構（`src/firn/agents/`）只有 `ConversationAgent` / `TaskAgent` / `CronAgent`，**沒有 supervisor**。這在 2026 H1 之前不算缺陷（multi-agent 還沒普及），但現在是個「明顯的 GAP」。下一節給具體 actionable。

## 4. Limitations / Honest Assessment

### 4.1 作者坦承的限制

- **Inefficiencies of Meta Agents**：明確說「meta-agent 設計只在 2/15 dataset 達到經濟臨界」
- **MAC**：明確說「能 match human baseline 的幾乎都是 proprietary frontier model」+ ground-truth exfiltration 風險
- **Shepherd**：Git-like event log 對超長軌跡（10K+ steps）沒驗證；revert 比 docker commit 快但比 in-process retry 慢
- **W4S**：7B model 的 generalization 到 *unseen* tasks 有，但跨 domain 還沒充分測
- **OPCD**：progressive filtering 假設 weak critic 的 revision direction 「不誤導」，但沒有形式化 bound
- **Agent-as-a-Judge** (Zhuge 2024)：需要 DevAI 這種 rich annotation benchmark，純 trajectory 場景不一定能 reuse
- **AJ-Bench**：仍是 benchmark，不是 production 框架

### 4.2 我們的獨立評估

- **token cost 嚴重低估**：Zhuge 2024 + Agentic Reward Modeling + W4S 全部都把 cost 算在「設計一次」，沒算「部署後每個 step 都要監督」的 cost。對長軌跡任務（research / coding），supervisor token 可能 5-15× sub-agent 本身。**firn 要部署前必須先量化這個 cost**。
- **「監督者更強」假設的循環問題**：用 GPT-4 監督 GPT-4 是 self-bias，用 GPT-5 監督 GPT-4 是單向偏（supervisor 永遠不犯錯但 sub-agent 永遠被當錯）。**真正 robust 的設計是「異模型 + 獨立 context + 多 critic ensemble」**，但這把 cost 推到 10×+。
- **「halt + replay」vs「繼續 + 修補」**：Shepherd 的 revert pattern 在 coding 上 work（commit → revert → try again），但在 GUI agent / web agent / customer-facing 場景不可逆（按下的按鈕、發出的訊息 revert 不回來）。**reversible 與 irreversible 環境的 supervisor pattern 應該分開設計**。
- **「meta-agent 自動設計 agent」目前是研究 toy**：ADAS、MAC 證明 frontier model 也做不好。**firn 千萬不要做「meta-agent 設計 firn 自己」這條路**，會撞 ground-truth exfiltration 跟 behavioral diversity 兩個坑。
- **「Weak critic 強 oversight」的 assumption fragile**：OPCD 假設弱模型能給出 non-misleading direction，但同模型 + bad prompt 會給出 misleading direction，而且你怎麼知道哪個 direction 對？需要 ground-truth rubric 或 human-in-the-loop 作為 fallback，否則 silent failure 仍在。

### 4.3 對比既有方案

| 既有 | Meta-agent 監督差異 |
|---|---|
| **Self-Refine / Reflexion**（同模型 critic，6/23 報告） | Meta-agent 用異模型 / 隔離 context，reliability 提升 0.4 Pearson |
| **CrossCheck Swiss cheese**（5 層 intra-process，6/9 reliability） | CrossCheck 是「同 process 內多層 filter」，meta-agent 是「同 process 外獨立 agent」，前者輕量、後者重但能 halt |
| **CodeCriticAgent 3-role**（Programmer→Executor→Critic，6/23 報告） | 3-role 是「同一工作流的角色分工」，meta-agent 監督是「跨工作流的全域監控」 |
| **Harness-Bench / 6/25 benchmarks**（衡量 reliability） | Meta-agent 是「增加 reliability 的方法」，benchmarks 是「衡量 reliability 的工具」 |
| **MCP server**（6/6 報告的 tool surface） | MCP 規範 tool protocol，supervisor 不在 MCP 範圍；supervisor 觀察 MCP tool call 但用獨立 API |
| **A2A protocol**（6/14 報告的 inter-agent 互通） | A2A 是「agent 之間怎麼對話」，supervisor 是「一個 agent 監控其他 agent」——A2A 可作為 supervisor 與 sub-agent 的通訊通道 |

## 5. Actionable for Our Projects

> 對 firn 個人 AI agent 框架的具體改進。file paths 來自 `firn/CLAUDE.md` 的目錄結構。難度標 TRIVIAL（<1 天）/ MODERATE（1-7 天）/ HARD（1-4 週）/ RESEARCH-ONLY（不建議做）。

### F-SUP-1 ⭐ TRIVIAL — 為 `ConversationAgent` 加 self-critique step

**檔案**：`src/firn/agents/conversation.py`

**現況**：`ConversationAgent`（128 行）回應後直接寫入 DB，沒有自我評估。

**改動**：在 response 寫入前，呼叫一次 cheap judge prompt（同一 model，temperature 0），對 response 評三維：relevance / completeness / safety。任一 < 0.5 → regenerate 一次（cap 1 次，避免無窮迴圈）。

**成本**：每輪多 1 次 LLM call（~2-5× token 增量）。

**收益**：抓掉 30-50% 的 fail-plausible 輸出（6/9 silent failure 報告的最低懸果實）。

### F-SUP-2 ⭐ TRIVIAL — 用異模型做 cross-vendor review gate

**檔案**：`src/firn/agents/task.py`

**現況**：`TaskAgent`（123 行）用單一 `LLMClient` 完成任務。

**改動**：在 `TaskAgent.execute()` 結束後，若 task category 是 "code" / "research" / "data-analysis"，呼叫 `llm/factory.py` 切到**不同 provider**（如主用 Anthropic 則 review 用 OpenAI）做一次 quick-pass。實作上 `LLMClient` 已經有 `circuit_breaker.py`，可加 `review_provider` config。

**成本**：每 task 多 1 次異模型 call。對個人框架 task volume 來說 <$5/月。

**收益**：根據 Zhuge 2024 + OPCD，跨模型 critique 提升 0.2-0.4 Pearson，silently wrong 的 code 抓出率 ~50%。

### F-SUP-3 ⭐ MODERATE — 加 `SupervisorAgent` 觀察 multi-agent 行為

**新增檔案**：`src/firn/agents/supervisor.py`（約 80-120 行）

**現況**：firn 沒有 multi-agent orchestration layer（6/22 swarm 報告的 GAP-SWARM-001 已經記錄）。

**改動**：實作一個 lightweight supervisor（基於 §2.2 骨架）：
- 訂閱 `observability/turns_logger.py` 的 event stream
- 對 sub-agent 的每個 tool call 跑 cheap judge（heuristic + LLM 混合）
- 觸發條件：tool call schema 不符 / 出現 6/9 reliability 報告定義的 silent failure 訊號 / step count 超過 budget
- 觸發動作：發 halt signal 給 TaskAgent + 寫 supervision event 到 `observability/spans.py`

**成本**：~3-5× token 增量，但 supervisor 可以用更小模型（per OPCD，弱 critic 即可）。

**收益**：這是 F-SUP-1/2 的 multi-agent 升級版。沒有這層，firn 進入 multi-agent 階段會撞 6/22 swarm 報告列的 silent-failure 問題。

### F-SUP-4 ⭐ MODERATE — `Observability` 加 supervisor-specific span attributes

**檔案**：`src/firn/observability/spans.py`（86 行）+ `otel.py`（187 行）

**現況**：6/17 observability 報告已經定義 `gen_ai.*` 屬性，但沒有 `gen_ai.supervisor.*` 或 `gen_ai.critique.*` 維度。

**改動**：對齊 §2.2 的 4 維評分，加 span attribute：
```
gen_ai.supervisor.score.{plan_deviation, tool_legitimacy, consistency, completeness}
gen_ai.supervisor.halt_reason
gen_ai.supervisor.critic_model
gen_ai.supervisor.critic_token_cost
```

**成本**：純 attribute addition，無 runtime overhead。

**收益**：未來 eval pipeline（6/25 報告方向）能直接 query supervisor effectiveness，不需要新 infra。

### F-SUP-5 ⭐ HARD — `LLMClient` 加 cross-vendor review loop（可選）

**檔案**：`src/firn/llm/client.py` + `llm/factory.py`

**現況**：單 vendor call，沒有 review pass。

**改動**：可選開啟 `review_after_execute` config。開啟後：
- 主 call 完成後，若 response 包含 code / structured output，自動 cross-vendor review
- Reviewer 來自 `factory.py` 的另一個 provider entry
- Review verdict < 0.7 → 自動 retry 一次（cap 1）

**成本**：同 F-SUP-2，但做成 framework-level 而非 task-level。

**收益**：個人框架用戶即使不寫自訂 code 也能享受到 cross-vendor critique 防呆。

**為什麼列 HARD**：要小心 retry 跟現有 `circuit_breaker.py` 的互動，無限 retry 是 6/9 reliability 報告的 anti-pattern。

### F-SUP-6 🚫 NEGATIVE-SPACE — 不要做「meta-agent 自動設計 firn agent」

引用 **MAC** (2606.04455) 跟 **Inefficiencies of Meta Agents** (2510.06711) 的反例：
- frontier model 都做不好，firn 個人用戶更做不好
- ground-truth exfiltration 風險
- 經濟臨界點 >15K 部署樣本，firn 個人用戶遠遠不到
- behavioral diversity 低，ensemble 沒用

**若未來要 build agent optimizer**，照 6/15 SE-Agent + 6/30 self-evolution protocol 的方向（trajectory pool + reflection），不要照 ADAS / MAC 的 meta-agent-as-designer 方向。

### F-SUP-7 🚫 NEGATIVE-SPACE — 不要把 supervisor 變成同模型 self-critic

Self-Refine / Reflexion（6/23 報告）證明 same-model critique Pearson 0.3-0.5。**firn 的 supervisor 必須是異模型或隔離 context**，否則 silent failure 抓不到還假裝有抓到。

## 6. Follow-up Questions

1. **OPCD 蒸餾是否值得在 firn 試** — 用 7B local model 當 critic supervisor 蒸餾給 frontier model 用，是否能在 single-machine 部署上跑通？需要先量化 OPCD 的 training cost 跟 inference time。
2. **Shepherd 風格的 in-memory event log** — firn 已有 `observability/turns_logger.py`，是否值得加 git-like revert primitive？對 personal agent 主要 use case（chat / cron）revert 沒意義，但對 task agent + coding scenario 有意義。
3. **MaMa game-theoretic 設計** — 形式化 supervisor vs adversary 是否 over-engineering？對個人框架來說，heuristic + LLM 混合 supervisor（F-SUP-3）應該夠用。
4. **supervisor 的 token cost vs reliability gain 量化** — 沒看到任何 paper 給出明確數字。firn 應該跑一次 small-scale eval 量化「$X 多花費 → Y% silent failure 抓出率」，作為之後所有 supervisor 設計的 baseline。
5. **多 supervisor ensemble 是否優於 single supervisor** — AJ-Bench 多維評分暗示 ensemble 是方向，但 cost 是 3-5×。對個人框架可能不划算。
6. **Bypassing AI Control via Agent-as-a-Proxy (arXiv 2602.04431)** — supervisor 觀察 CoT + tool call 仍可被 indirect prompt injection 繞過（agent 自己被劫持後當 proxy）。這個威脅模型 firn 完全沒 cover，6/13 firewall 報告也沒 cover。是 supervisor layer 的新 frontier。
7. **human-in-the-loop 作為 supervisor 的 fallback** — 完全 autonomous supervisor 在 OPCD 假設下仍可能 silent fail，何時把控制權交回 human 是 design decision。firn 個人用戶 = 唯一 human，需要設計「何時 prompt 確認」的 rubric。

---

### 原始來源

1. https://arxiv.org/abs/2605.10913 — **arXiv paper** — HIGH — *Shepherd: Enabling Programmable Meta-Agents via Reversible Agentic Execution Traces* — 第一個把 supervisor intervention 做成 first-class runtime primitive 的 paper，5× revert speed vs docker
2. https://arxiv.org/abs/2606.04455 — **arXiv paper** — HIGH — *The Meta-Agent Challenge (MAC)* — Frontier model 自主設計 agent 的 benchmark，證明 ground-truth exfiltration 風險 + 極少 match human baseline
3. https://arxiv.org/abs/2510.06711 — **arXiv paper** — HIGH — *Inefficiencies of Meta Agents for Agent Design* — Context stuffing 反而比 ignore 差、behavioral diversity 低、>15K 樣本才有經濟效益
4. https://arxiv.org/abs/2410.10934 — **arXiv paper** — HIGH — *Agent-as-a-Judge: Evaluate Agents with Agents* (Zhuge et al. 2024) — 跨模型 agentic judge 對 step-level 評分，Pearson 比 LLM-as-a-Judge 高 0.2-0.4
5. https://arxiv.org/abs/2504.04785 — **arXiv paper** — HIGH — *Weak-for-Strong: Training Weak Meta-Agent to Harness Strong Executors* (W4S) — 7B meta-agent + RLAO 超 baseline 2.9-24.6%，1 GPU hour 訓練
6. https://arxiv.org/abs/2606.00424 — **arXiv paper** — HIGH — *Weak Critics Make Strong Learners: On-Policy Critique Distillation* (OPCD) — 弱 critic + progressive distillation 可改善 frozen 強模型
7. https://arxiv.org/abs/2602.04431 — **arXiv paper** — HIGH — *MaMa: A Game-Theoretic Approach for Designing Safe Agentic Systems* — Stackelberg 安全遊戲形式化 meta-agent 設計 vs meta-adversary
8. https://github.com/facebookresearch/meta-agents-research-environments — **production repo** — HIGH — Meta 官方 523★，動態環境 eval AI agents（2026-06-30 last update）
9. https://github.com/fannie1208/W4S — **paper repo** — HIGH — W4S (COLM 2025) 官方 impl，57★
10. https://github.com/xvirobotics/metabot — **production repo** — MEDIUM — 「受監督的自我進化 agent 組織」中文 production 框架 899★，飛書/Telegram 跑 Claude
11. https://github.com/agentlas-ai/Hephaestus — **production repo** — MEDIUM — Open Agent OS for Claude Code/Codex/Cursor，meta-agent builder + A2A Hub routing + memory & security gates，99★
12. https://github.com/waltstephen/ArgusBot — **production repo** — MEDIUM — 24/7 supervisor agent for Codex CLI + Claude Code CLI，305★
13. https://github.com/Chris-Rebentisch/dualpass — **production repo** — MEDIUM — Reliability-first agent harness with cross-vendor agent-as-judge review，3★（低 star 但概念獨特）

---

**下一個工作日排程執行本指令。**
