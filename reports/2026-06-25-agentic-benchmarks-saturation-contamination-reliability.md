# 研究報告：Agentic Benchmark 2026 — Saturation, Contamination, Reliability Cliff

**日期**：2026-06-25
**來源數**：9 | **標籤**：#benchmark #evaluation #contamination #reliability #agentic-eval

---

## 1. The Problem

SWE-bench Verified、GAIA、WebArena、OSWorld 這幾個 2024-2025 年的 agentic benchmark，到了 2026 年集體撞牆。三面牆同時倒下：

**牆一：飽和（Saturation）** — 領先模型在 SWE-bench Verified 衝到 80% 以上，差距壓縮到噪訊級，benchmark 失去鑑別力。Anthropic Mythos 5、Fable 5 自我宣稱 OSWorld 85%，但官方 leaderboard 跟廠商 system card 數字不一致。

**牆二：污染（Contamination）** — BrowseComp 的題目已被 LLM 預訓練資料吸收，模型靠記憶答題而非真實檢索。Finance Agent v2 的題庫公開後，後續評測的模型分數含水量不明。

**牆三：可靠度崩塌（Reliability Cliff）** — CFAgentBench 揭露：同一個 open-weight 模型，pass^1 = 0.67 但 pass^5 = 0.38（k=5 重複下丟掉 43% 的成功）。τ-Rec 在 5 個模型家族上看到 pass^1 = 57% / pass^4 = 38% 的斷崖。**單次成功率嚴重高估實際可部署能力**。

誰在解決：
- **學術**：EvoBrowseComp (arXiv 2606.13120)、CFAgentBench (2606.22000)、τ-Rec (2606.10156)、Claw-SWE-Bench (2606.12344)、MAC-Bench (2606.07805)、PseudoBench (2606.18060)、AgentFairBench (2606.16723)、MEMPROBE (2606.24595)、IPO Finance Agent (2606.23032)、Simple Strands Agent (2606.17454)
- **業界**：Vals AI（Finance Agent v2）、OpenAI（OpenClaw × SWE-bench）、Steel.dev（OSWorld leaderboard）、Anthropic（Claude Code eval suite）

2026 Q2 出現一個明顯的設計 idiom 集體遷移：**從「單次正確率」轉向「可驗證、可重複、可演化」的評測層**。

---

## 2. Core Mechanism

### 2.1 三個關鍵設計軸

把這次掃到的 9 篇 2026 Q2 paper 整理到三個軸上：

| 設計軸 | 舊設計（2024-25） | 新設計（2026 Q2） | 代表 |
|--------|------------------|-------------------|------|
| **題目生命週期** | 靜態、一次性公開 | 動態、定期重生 | EvoBrowseComp |
| **評分方式** | 字串比對 / LLM-judge | State diff + side-effect + verifier | CFAgentBench / τ-Rec / Claw-SWE-Bench |
| **可靠性量測** | pass@1 | pass^k、pass^1→pass^5 collapse | τ-Rec / CFAgentBench |

### 2.2 EvoBrowseComp — 動態重生題庫

解決「污染」的核心思路：**題目不能是固定集合，必須跟 LLM 的預訓練切割時間賽跑**。

三個協作 agent：
1. **QA synthesis agent**：從 live web 拉當下才出現的知識來合成 QA 對
2. **Information filtering agent**：過濾掉 parametric shortcut（太熱門 → 已被記住的）
3. **Guidance agent**：把題目形式化成 reasoning graph，減少邏輯捷徑

關鍵設計：**支援 fully automated synthesis，所以可以定期重生**（EvoBrowseComp 名字的由來）。400 英文 + 400 中文複雜題。

> 為什麼這個設計 idiom 重要 — SWE-bench 的污染問題無解，因為 GitHub issue 會被爬進預訓練。但**題目只要從「未來才發生的網頁事件」衍生出來**，污染窗口就被壓縮到「訓練 cutoff 之後」。EvoBrowseComp 不是要消除污染，是要把污染的時間窗壓到比訓練週期短。

### 2.3 CFAgentBench — State-diff + Side-effect Guard

CFAgentBench 從 WebArena 借鑑「executable evaluation」原則，但推進到 enterprise 等級：

```python
# 概念性評分骨架（CFAgentBench 風格）
class CFAgentBenchTask:
    task_spec: TaskSpec
    oracle_solution: Callable
    
    def grade(self, agent_output: AgentOutput, env_state: EnvState) -> Grade:
        # 1. state diff — 環境狀態是否符合 oracle 預期
        state_match = self.expected_state == env_state
        
        # 2. forbidden-side-effect — 沒有觸發「不該執行」的操作
        side_effect_ok = not any(
            effect in agent_output.side_effects 
            for effect in self.forbidden_effects
        )
        
        # 3. required-output regex
        output_ok = all(
            regex.search(agent_output.reply)
            for regex in self.required_outputs
        )
        
        # 4. money-movement guard — 278 個任務裡有金流動作
        # 「正確答案是停下來等人工批准」也算錯
        money_guard_ok = (
            not self.requires_human_approval 
            or agent_output.staged_for_human
        )
        
        return Grade(
            state=state_match,
            side_effect=side_effect_ok,
            output=output_ok,
            money_guard=money_guard_ok,
            # LLM judge 只用在 reply quality，從不用在 reward
            reply_quality=LLMJudge(agent_output.reply, self.rubric),
        )
```

關鍵設計：
- **LLM judge 永遠不是 reward** — 只用於 reply quality 的二級評分（rubric 比對）。Reward 必須 deterministic，否則 RL 訓練會 reward hacking。
- **money-movement guard** — 278 個任務刻意包含「正確答案是 stage for human approval」的場景。執行正確的金流 = 任務失敗。這是在測 agent 是否懂得「何時不做」。
- **k=5 pass^k** — 每個任務跑 5 次，計算 5 次都通過的比率。CFAgentBench 數字：最強 open-weight 模型 pass^1 = 0.67，pass^5 = 0.38，**collapse 43%**。

### 2.4 τ-Rec — Reveal-Tagged Elicitation + pass^k

τ-Rec 把 reliability cliff 拉到明面上：

| Metric | GPT-5.4 | Sonnet 4.6 | Gemini 2.5 Flash | DeepSeek V4 Flash | Qwen3-32B | GPT-5 mini |
|--------|---------|------------|------------------|-------------------|-----------|------------|
| pass^1 | ~57% | ~54% | ~51% | ~48% | ~45% | ~42% |
| pass^4 | ~38% | ~36% | ~33% | ~30% | ~28% | ~25% |

每一個模型都掉 30-40% 的 reliability。

τ-Rec 的兩個關鍵 primitive：
1. **Reveal-tagged elicitation (RTE)** — 任務約束在對話中分階段揭示，模擬真實使用者的逐步揭露。避免 agent 在看到完整規格後做捷徑。
2. **structured catalog predicates** — 答案必須對得上結構化 catalog 的 predicate（不是 LLM-judge 的主觀打分）。

### 2.5 Claw-SWE-Bench — Harness as First-Class Axis

最震撼的數字（Claw-SWE-Bench, arXiv 2606.12344）：

> 同一個 GLM 5.1 backbone，換 adapter：Pass@1 從 **19.1% → 73.4%**（差距 54.3 pp）
> 換模型（harness 固定）：Pass@1 變化 29.4 pp
> 換 harness（模型固定）：Pass@1 變化 27.4 pp

**模型跟 harness 的影響幾乎等量**。但過去所有 benchmark 報告都只報模型分數，harness 設計被當作實作細節。

Claw-SWE-Bench 強制把 harness 跟 cost 當作 first-class axis：
- 固定 prompt、runtime budget、workspace contract、patch extraction、evaluator
- 350 instances / 8 languages / 43 repos
- 還出 Lite 版（80 instances / 17 calibration columns）做 cost-aware 快速驗證

這個 design idiom 跟 Simple Strands Agent (arXiv 2606.17454) 互相印證 — Simple Strands Agent 跑 138k 軌跡後，提出 **intent-execution gap** 概念：「模型想做什麼」跟「harness 實際做了什麼」之間的落差，這個落差跟工具/loop 一樣重要。

### 2.6 MEMPROBE — Memory as Auditable Artifact

MEMPROBE (arXiv 2606.24595) 提出一個反直覺的觀察：

> **任務完成率（task completion）跟記憶可恢復性（memory recovery）是兩個不同的能力**。

設計：
- 50 個模擬使用者 × 31 個隱藏維度 = 1550 個 recovery target
- 每個使用者的「真實狀態」是 ground truth
- 評測 agent 完成任務後，從 agent 的記憶裡 reconstruct 使用者狀態
- 分兩個條件評：**full-store access** vs **top-k retrieval**

關鍵發現：memoryless baseline 在任務完成率上接近 saturated（>90%），但 category-balanced recovery 只到 ~0.6，top-k retrieval 條件下更低。

對 firn 啟示：**memory 評測不能只看「後續任務答對沒」，要看「記住的內容能不能被 retrieval 回來」**。

---

## 3. Why It Matters / Applications

### 3.1 三社區 90 天收斂 → table-stakes moment

這次抓到 9 篇 paper / 跨 4 個子社群，全部落在 2026 Q2 (4-6 月)，全部圍繞同一個重新框架：**agentic eval 從「答對率」轉向「可驗證性 + 可重複性 + 動態性」**。

| 社群 | 產出 | 時間 |
|------|------|------|
| 學術 eval-cluster | EvoBrowseComp, CFAgentBench, τ-Rec, Claw-SWE-Bench, MAC-Bench, PseudoBench, AgentFairBench, MEMPROBE, IPO Finance Agent | 2026-04 ~ 2026-06 |
| 學術 reliability-cluster | Simple Strands Agent (138k 軌跡), QBugLM (pass^1→pass^5) | 2026-05 ~ 2026-06 |
| 業界 Finance | IPO Finance Agent, Vals AI Finance Agent v2 | 2026-06 |
| 業界 OS | MacAgentBench (676 tasks / 25 apps / OpenClaw) | 2026-06 |

第 11 個 validated instance of §7.15 (three-community-in-90-days) — table-stakes 訊號已升級到「如果你的 agent 評測還停留在 pass@1 + 靜態題庫，你已經落後一整個世代」。

### 3.2 對 AI agent 領域的衝擊

**衝擊一：SWE-bench Verified 的「75%」分數不再是可信 metric**。一個模型報 75%，實際 deploy reliability 可能只有 50% 以下。任何引用 2025 年 SWE-bench 分數做 model selection 的決策都是過時的。

**衝擊二：Open Source 跟 Proprietary 模型的「差距」被 harness 變數吃掉**。Claw-SWE-Bench 證明模型 vs harness 的影響幾乎等量 (29.4 vs 27.4 pp)。意思是 OpenClaw 配 GLM 5.1 的 73.4% 跟 Claude Opus 4.5 配 minimal adapter 的 19.1% 是同一個 benchmark — 過去那種「OpenAI 領先 30 pp」的 headline number 大部分是 harness 帶來的，不是模型帶來的。

**衝擊三：對 RL 訓練資料的影響**。τ-Rec 跟 CFAgentBench 的 reliability cliff 直接挑戰 GRPO 訓練的 rollout 假設 — 一個 query 要有非零 variance（不是全對也不是全錯）才能貢獻 gradient。如果同一個任務跑 5 次成功率掉 43%，那「rollout 的成功」本身就是噪訊極高的訊號。Q2 2026 已經有人提出 query recycling (arXiv 2606.10709) 來處理 zero-variance groups。

**衝擊四：對 memory 設計的影響**。MEMPROBE 證明「能完成任務」不等於「memory 是 auditable 的」。對 production agent 來說，這是一個新的失敗模式：agent 答對問題但 memory 內部已經被污染或失真，使用者看不到。

---

## 4. Limitations / Honest Assessment

### 4.1 論文各自沒說的限制

**EvoBrowseComp**：
- 動態重生依賴 live web — 如果 synthesis agent 自己也依賴 LLM 來篩選「太熱門」的題目，那個 LLM 也被污染，整個防線失效。論文沒量化「synthesis agent 本身的 contamination resistance」。
- 三個協作 agent 的成本沒報。題庫重生的工程開銷決定了能不能真的 frequent update。

**CFAgentBench**：
- 1,014 tasks / 8 domains 是 construction-finance 特定領域 — 跨領域泛化性未知。
- 35 個 mock app 自建 — 不能直接拿來評測真實 enterprise 系統上的 agent。
- Money-movement guard 是 clever 但只測「金流」 — 其他需要人類批准的場景（醫療、法律）沒有 analog。

**τ-Rec**：
- 5 個模型家族的測試在 2026 Q2 — 模型版本可能已經過時。
- Reliability cliff 的根因沒深入分析：是 stochastic decoding？是 stateful context drift？是 tool-call nondeterminism？三種 fix 完全不同。

**Claw-SWE-Bench**：
- GLM 5.1 是個特定 backbone — 換成 Claude Opus 4.6 或 GPT-5.4 可能展現不同 pattern。
- 54.3 pp 的 adapter gap 是在「minimal direct-diff」vs「full adapter」兩個極端 — 真實世界的差距可能更平滑。
- Cost 維度被列入 first-class 但「cost vs accuracy」的 Pareto frontier 沒詳細分析。

**MEMPROBE**：
- 50 個模擬使用者 — 統計顯著性堪慮。
- Synthetic ground truth — 跟真實使用者的「hidden state」有多相似未知。
- 沒測量隨時間累積的 memory drift（MEMPROBE 是單一 session 評測）。

### 4.2 我們的獨立評估

**第一個沒有 paper 解的問題**：reliability cliff 的 root cause。

CFAgentBench 跟 τ-Rec 都看到 pass^1 → pass^5 collapse 30-43%，但**沒有人系統性地拆解這個落差是 decoding randomness、context accumulation、tool-call nondeterminism、還是外部 API 的可變性**。這是 research gap — 沒有 root cause 就沒有針對性 fix。

**第二個**：dynamic benchmark 的 meta-game。

EvoBrowseComp 假設「題目重生」就足夠防污染。但 LLM 訓練者只要把整個 synthesis pipeline 餵進訓練（這已經發生在 BrowseComp 上），動態題庫就跟靜態一樣失效。**真正的防污染需要 cryptographically verifiable freshness + 對 synthesis 過程本身加密**。

**第三個**：pass^k 不是 metric，是 supply chain。

τ-Rec 報 pass^4 = 38%，聽起來糟。但「同一個任務跑 4 次都通過」是 production 用戶根本不會經歷的場景（用戶只跑 1 次）。所以 pass^4 = 38% 是 lower bound 而非實際 reliability — 真正的 reliability 應該是「成功任務 / 總任務」，但要扣掉「重試可以 fix 的失敗」。**業界需要一個叫 user-facing reliability 的 metric**。

**第四個**：harness-as-first-class axis 的成本。

Claw-SWE-Bench 證明 harness 影響 = 模型影響。但所有 production agent 的時間都花在「讓 harness 變好」，不是「換更好的模型」。意思是：**所有 agent 框架的 ROI 應該用「harness 改進帶來的能力提升」而非「換模型帶來的提升」**。這個觀點對 OpenAI / Anthropic 的「model tier」商業模式是直接威脅。

**對比既有方案**：
- 跟 ReAct/AutoGPT 時代的 eval（human eval、GSM8K、MMLU）比，這波 paper 從「答對率」轉向「可驗證的執行正確性」是質變。
- 跟 2025 年的 WebArena/OSWorld 比，從「單次成功」轉向「pass^k + side-effect guard + executable state diff」是同方向但更嚴格。
- 跟 LangChain/LlamaIndex 的內建 eval 比，這些都是學術主導的標準化嘗試 — 對 framework vendor 是壓力（他們的 eval 工具遠遠不夠）。

**可複製性**：
- EvoBrowseComp 的 three-agent pipeline — 個人開發者可以重做（每個 agent 是 GPT-4o 等級即可），但 live-web scraping 的成本跟維護是瓶頸。
- CFAgentBench 的 state-diff grading — TRIVIAL 級可重用，每個 task 只要寫一個 oracle grader 即可。
- τ-Rec 的 pass^k — TRIVIAL，純 metric 改變。
- MEMPROBE 的 auditable recovery — MODERATE，需要 ground truth generation pipeline。
- Claw-SWE-Bench 的 harness-as-axis — HARD，需要固定 adapter 跟嚴格的 contract。

---

## 5. Actionable for Our Projects

### firn 專案（評測 gap 最大的專案）

**F-EVAL-1：在 firn 中加 `pass@k` 跟 `reliability` 評測 metric**（TRIVIAL / 1 天）
- 檔案：`src/firn/tasks/dispatcher.py` 或新增 `src/firn/eval/reliability.py`
- 改動：每個 task 跑 N 次（k=5 預設），記錄 pass^k。在 `TaskService.complete()` 旁邊加 `record_reliability(task_id, k, pass_count)`。
- 動機：CFAgentBench 數字證明 firn 的「單次成功率」不可信。先量測才能談改進。
- 風險：每次 task 多跑 4 次，會消耗 token 預算。解法：k=5 只在 `eval_mode=True` 時啟用。

**F-EVAL-2：在 `tools/ToolExecutor` 加 `side_effect_classifier`**（TRIVIAL / 半天）
- 檔案：`src/firn/tools/executor.py`
- 改動：每個 tool 標記 `side_effect_class: ["read", "write", "irreversible", "external_money"]`。Executor 在呼叫前 log side-effect 類別。
- 動機：CFAgentBench 的 money-movement guard 證明「正確答案是 stage for human」也是錯的 — firn 必須先有能力標記哪些 tool call 是 irreversible。

**F-EVAL-3：新增 `eval/replay.py` — 把 production trace 重放到 controlled env 比對 outcome**（MODERATE / 1-2 週）
- 檔案：新增 `src/firn/eval/replay.py`
- 改動：攔截 production agent 的 tool call sequence，存成 JSONL。Replay engine 在 sandbox 重放，比對 outcome diff。
- 動機：對標 CFAgentBench 的「state diff grading」。讓 firn 的使用者可以驗證「production 跟 replay 結果是否一致」。
- 瓶頸：sandbox 需要 mock 所有外部 API。

**F-EVAL-4：observability 模組加 `eval_metrics` span attribute**（TRIVIAL / 1 小時）
- 檔案：`src/firn/observability/spans.py`
- 改動：在 `gen_ai.agent.span` 加 `eval.pass_count`、`eval.k`、`eval.pass_at_k_ratio` 三個 attribute。
- 動機：把 reliability 數據接入 OTel GenAI semconv（6/17 那份報告已經在做了），方便 Langfuse / Arize 直接顯示 reliability cliff。
- 跟之前研究的串接：§7.15 observability table-stakes + 本篇 eval table-stakes = 同一個 OTel span tree 上多掛 attribute。

**F-EVAL-5：在 `agents/TaskAgent` 加 `adapter_protocol` 抽象**（HARD / 2-3 週）
- 動機：對標 Claw-SWE-Bench。firn 的不同使用者用不同的 agent 配置（TaskAgent vs ConversationAgent vs CronAgent），要把他們都接到同一個 eval harness 才能做横向比較。
- 改動：新增 `src/firn/eval/adapter.py`，定義 `Adapter` ABC：`prepare_workspace()`, `extract_patch()`, `submit_patch()`。每個 agent 類型實作自己的 adapter。
- 瓶頸：3 個 agent 類型的 contract 都得重新對齊。

### managed-agents 專案（cron research runner）

**F-CR-EVAL-1：研究報告的「可驗證性」section**（TRIVIAL / 1 小時）
- 改動：在 cron 報告模板新增「可驗證性 / Reliability」section，記錄這個研究的 source 是否被 independent reproduction 過。EvoBrowseComp / CFAgentBench / τ-Rec 三篇都用「has been independently reproduced: yes/no」標籤。
- 動機：我們現在引用的 source 大多是單一論文，沒有 reproduction 標記。加上可以幫未來的 reviewer 快速分類。

### Hermes Agent 本身

**F-HERMES-EVAL-1**：在 Heartbeat v2 加 reliability 監控
- 在每次 scheduled cron run 的 metadata 加 `eval.success_count / eval.total`。
- 如果 reliability < 0.5，自動觸發 fallback（改用更強的模型或加 retry budget）。

---

## 6. Follow-up Questions

1. **reliability cliff 的 root cause**：CFAgentBench / τ-Rec 都看到 pass^1 → pass^5 collapse，但**沒有人系統性地拆解這個落差是 decoding randomness / context accumulation / tool-call nondeterminism / 還是外部 API 可變性**。下一輪研究可以專門做這個題目（標題：「Agent reliability cliff: decoding vs context vs tools vs APIs」）。

2. **dynamic benchmark 的 meta-game**：EvoBrowseComp 假設「題目重生」就夠防污染，但 LLM 訓練者會把整個 synthesis pipeline 餵進訓練。下一代題目需要 cryptographically verifiable freshness + 對 synthesis 過程本身加密嗎？

3. **harness-as-first-class 的商業衝擊**：Claw-SWE-Bench 證明 harness ≈ model。如果這個結論 generalize，那 OpenAI/Anthropic 的「換更高 tier model = 付更多錢」商業模式會被「投資改 harness」打敗 — 下一輪研究可以看 framework vendor（LangChain / LlamaIndex / OpenAI Agents SDK / Hermes）的 eval 工具成熟度。

4. **memory evaluation**：MEMPROBE 證明「任務完成」≠「記憶 auditable」。Memory as auditable post-interaction artifact 是個新 primitive — 跟 6/19 那份 memory report 可以串起來，看 firn 的 memory/ 模組要不要加 auditable export。

5. **cost-aware eval**：CFAgentBench 把 cost 列入 first-class 但沒詳細分析 Pareto frontier。下一輪可以專門看「在固定 cost budget 下，哪個 (model × harness) combo 達到最高 reliability」。

6. **replay engine 的可行性**：F-EVAL-3 提的 replay 概念在 production agent 環境很難做（外部 API 副作用）。要不要借鑑 CFAgentBench 的 mock app pattern — 把 production 真實 API 包成 deterministic mock？

7. **跨 agentic benchmark 的 comparability**：9 個 paper 9 種 metric（pass^k、reward + reply、state diff、auditable recovery）。有沒有可能像 OTel GenAI semconv 那樣做一個 `eval.*` semantic convention？

---

### 原始來源

1. arXiv 2606.13120 — 論文 — HIGH — EvoBrowseComp: 動態題庫 + 三 agent synthesis pipeline 防污染
2. arXiv 2606.22000 — 論文 — HIGH — CFAgentBench: 1014 tasks / state-diff grading / money-movement guard / pass^1→pass^5 崩塌 43%
3. arXiv 2606.10156 — 論文 — HIGH — τ-Rec: reveal-tagged elicitation + pass^k reliability cliff
4. arXiv 2606.12344 — 論文 — HIGH — Claw-SWE-Bench: GLM 5.1 配不同 adapter 19.1%→73.4%，harness ≈ model
5. arXiv 2606.24595 — 論文 — MEDIUM-HIGH — MEMPROBE: 記憶 auditable recovery ≠ 任務完成率
6. arXiv 2606.23032 — 論文 — MEDIUM-HIGH — IPO Finance Agent: 1000 題只釋出 70 防污染 + automated rubric generation
7. arXiv 2606.17454 — 論文 — MEDIUM-HIGH — Simple Strands Agent: 138k 軌跡 / intent-execution gap / harness-model alignment
8. arXiv 2606.07805 — 論文 — MEDIUM — MAC-Bench: Beyond Goodhart's Law / dynamic compliance benchmark
9. arXiv 2606.18060 — 論文 — MEDIUM — PseudoBench: 200 偽科學 claims / auto-research 失敗模式
10. arXiv 2606.10709 — 論文 — MEDIUM — Query recycling for GRPO: zero-variance groups 處理

---

下一個工作日排程執行本指令。