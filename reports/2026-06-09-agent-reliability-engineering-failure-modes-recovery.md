# 研究報告：Agent Reliability Engineering — 失敗模式、復原迴圈與 Long-Horizon 自驗證 (2026)

**日期**：2026-06-09
**來源數**：10 | **標籤**：#agent-reliability #self-healing #silent-failure #verifier #harness #long-horizon

> 跨 arXiv × Anthropic Engineering × LangChain Blog × GitHub 的「**長任務 agent 為什麼會自己慢慢壞掉、壞掉時怎麼知道、要怎麼救回來**」三條主軸交叉驗證。本週這個題目在學術與工業界同步爆發，**有高度交叉驗證的 NEW 信號**。

## 1. The Problem

2026 年中的 LLM agent 已經能完成跨 session、跨小時的任務（Claude Agent SDK、Cursor background agents、Harmonic Scout、Lyft self-serve platform），但學術界與工業界**同時**觀察到一個結構性問題：

> **長任務 agent 的失敗，幾乎都不是「答錯」這種容易抓的錯。**
> 它會在第 17 步靜悄悄產生一個看似合理但其實前提已被污染的中間結論；接下來 13 步都根據那個錯誤前提往前推進，最後交出一個乾淨漂亮、語氣自信、**完全錯誤**的答案。Anthropic 把這種叫 **"silent failure"**，arXiv 2606.09071 (REFLECT) 把它列為 **the silent failure regime**——比字面錯更難抓，因為字面錯的解法很成熟（rubric grading、unit test、regex），**silent failure 的解法根本還沒收斂**。

三條子問題構成本週研究主軸：

1. **失敗模式分類學**：長任務 agent 會在哪幾個「層」壞掉？tool timeout、stale context、contradictory evidence、retry loop、unverified intermediate output —— 5 種已知的 orchestration-level 失敗訊號要怎麼定義、偵測、恢復？
2. **復原預算的紀律**：retry-only 太天真、full replan 太貴，**bounded recovery** 的下界在哪？Anthropic 的 claude-progress.txt + git commit + init.sh 套路，跟 arXiv 2606.01416 的 recovery-budget sweep 是不是同一件事？
3. **Verification as a first-class component**：verifier 不再只是「最後打分數的工具」，而是「**中段 + 末段的 quality gate**」——REFLECT 把 verifier 的介入結果當作對 attribution 本身的對比證據（contrastive evidence）來 refine 自己，這是一個 close-the-loop 的設計，極少看到。

誰在解決：Anthropic（Claude Agent SDK + Harness）、LangChain（LangSmith Engine + LangGraph fault tolerance）、DataArcTech（Bayesian-Agent）、arXiv 上 7-8 個獨立團隊在 Q2 2026 同時發表。**跨圈收斂度高**——這是 2026 上半年的 idiom 候選人。

## 2. Core Mechanism

我從 10 個來源抽出 3 個互補的核心機制，這三個是「**靜默失敗 → 偵測 → 恢復**」的對應設計點。

### 2.1 Failure-class taxonomy + bounded recovery（控制系統視角）

來源：arXiv 2606.01416 *Self-Healing Agentic Orchestrators for Reliable Tool-Augmented LLM Systems*（2026-05-31，cs.AI）

把 reliability 當作**有界控制問題**，這是 2026 上半年我看到最清楚的 orchestrator 設計論文：

```
┌──────────────────────────────────────────────────────────────┐
│                    Self-Healing Orchestrator                 │
│                                                              │
│  observation ──► failure classifier ──► recovery policy       │
│  (tool timeout,                              (replay,         │
│   malformed args,                             patch,           │
│   stale context,                              replan,         │
│   contradictory evidence,                     abandon)         │
│   retry loop,                                                   │
│   unverified                                                    │
│   intermediate)                              under budget     │
│                                                              │
│  recovered trajectory ──► verifier ──► observability trace    │
└──────────────────────────────────────────────────────────────┘
```

關鍵設計點：

- **Failure classes 必須 enumerable**。原 paper 列出 6 類：tool timeouts、malformed arguments、stale context、contradictory evidence、retry loops、unverified intermediate outputs。**這比「LLM judge 一句話」結構化很多**——judge 對著這 6 個類別做 softmax，可以直接被 routing 到對應的 recovery action。
- **Recovery budget 是 explicit constraint**，不是「試到好為止」。paper 做了 budget sweep：在 1 次恢復預算下，self-healing 94.0% vs retry-only 85.3% vs full replan 88.2%；預算往上提，差距縮小。**意思是：預算愈緊，self-healing 贏愈多**——這跟 webhook-subscriptions skill 對 reliability 的經驗一致。
- **Verifier-guided recovery 解決 silent failure**。paper 報告：「在 controlled semantic silent-failure setting 下，verifier-guided self-healing 把 silent failure 降到 0.0%，non-verifying baselines 回 wrong-but-plausible 答案的頻率高很多。」**這是少數有具體數字的 silent-failure benchmark**。

對 100-task controlled fault-injection benchmark 結果：self-healing 98.8% vs retry-only 94.5% vs full replan 93.8%。在 production agent benchmark（TAU-bench、Aider polyglot 沒做）上的泛化度還不確定。

### 2.2 Posterior-guided skill evolution（貝氏後驗視角）

來源：arXiv 2606.08348 *Bayesian-Agent: Posterior-Guided Skill Evolution for LLM Agent Harnesses*（2026-06-06，cs.CL）+ GitHub DataArcTech/Bayesian-Agent（22★，更新於 2026-06-09）

這個 paper 解決的問題跟前一個不同：不是「**單次任務**失敗時怎麼辦」，而是「**跨任務的 skill/SOP 庫**要怎麼演化才不會自我污染」。

```python
# 概念骨架（從 paper 內文抽象出來，不是逐行實作）
class SkillPosterior:
    """Per-skill categorical posterior over (success, partial, silent_fail, hard_fail)."""
    def __init__(self, alpha=1.0):
        self.counts = {c: alpha for c in ("success", "partial", "silent_fail", "hard_fail")}

    def update(self, outcome: str, features: dict):
        # feature-conditioned: feature bucket (task_class, harness, model, prompt_template)
        bucket = self.bucketize(features)
        bucket.counts[outcome] += 1

    def decide(self, features: dict) -> str:
        """Map posterior state → inspectable action."""
        post = self.posterior(self.bucketize(features))
        if post["silent_fail"] > 0.25:          return "patch"
        if post["hard_fail"]   > 0.40:          return "split"
        if post["partial"]     > 0.55 and post["success"] < 0.30: return "compress"
        if post["success"]     < 0.05 and self.trials > 50:       return "retire"
        if post["success"]     < 0.15:          return "explore"
        return "keep"
```

核心洞見：**過去的 agent 自我改良方法（reflexion、self-debug、STELLA）把觀察到的 success/failure 當計數器用，但 counts 本身不是 belief**。Bayesian-Agent 用 feature-conditioned categorical posterior（per bucket 一個 Dirichlet）來表達「在這個 (task_class, harness, model) 條件下，這個 skill 成功的機率分佈」。這比 heuristic reflection 強在：(a) 同一個 skill 在不同 bucket 的後驗是不同的，**避免「在 simple QA 上 100% 成功就以為在 production SQL 也 100% 成功」**的過擬合；(b) action 是 inspectable 的，後驗可以審計——這呼應了 Anthropic 在 demystifying-evals 文裡講的「evals are the highest-bandwidth communication channel」。

實驗結果（用 deepseek-v4-flash，incremental repair）：SOP-Bench 80% → 95%，Lifelong AgentBench 90% → 100%，RealFin-Bench 45% → 65%。注意 RealFin-Bench 只到 65%，**說明貝氏後驗不是萬靈丹**——初始表現很差的 skill 確實卡住。

### 2.3 Long-horizon harness：用 git + progress file + init script 把 agent 變成「換班工程師」

來源：Anthropic Engineering *Effective harnesses for long-running agents*（2026）

> Anthropic 在實驗中發現「長任務 agent 的兩種典型失敗」：
> 1. **一開始想一次做完所有事**——中途 context 滿了，下一個 session 接手的是半成品 + 沒有文件 → 浪費大量 token 猜測前一個 session 做了什麼
> 2. **看到「有進度」就宣布完工**——看到 git log 有 commits，就以為「工作做完了」

解法是把 agent 當**換班工程師**（想像一組工程師輪班，每班都失憶）來設計：

```markdown
# claude-progress.txt （**用 JSON 不是 Markdown**——model 比較不會亂改 JSON）
{
  "features": [
    {"id": "auth.login",      "passes": true,  "tested_in": "session-3", "notes": ""},
    {"id": "chat.send_msg",   "passes": true,  "tested_in": "session-5"},
    {"id": "settings.theme",  "passes": false, "tested_in": "session-4", "notes": "save button 沒反應"},
    {"id": "profile.avatar",  "passes": false, "tested_in": null,        "notes": "尚未實作"}
  ]
}
```

關鍵設計準則（直接從原 post 抽出）：

| 機制 | 為什麼有效 |
|---|---|
| **JSON progress file（不是 Markdown）** | model 對 JSON 的 overwrite 衝動低於 Markdown |
| **`.passes` 欄位只能切 true/false，不能編輯整個檔** | 「It is unacceptable to remove or edit tests」 |
| **每個 session 開頭先 git status + 讀 progress file + 跑 init.sh** | 三秒知道現在的世界狀態 |
| **每次改動後 commit + 寫進度** | model 可以用 `git revert` 自救 |
| **`init.sh` 跑 dev server + 一次 end-to-end smoke test** | 確認「前一個 session 沒有留下壞掉的狀態」再動手 |
| **瀏覽器自動化工具（Puppeteer MCP）** | 看到「程式能跑」≠「功能正確」；視覺/互動 bug 只有真跑一次才知道 |
| **一次只做一個 feature** | 解掉「想一次做完」衝動；對齊 Anthropic 講的 incremental |

Anthropic 在原 post 明確說：「With the above in place, every coding agent is prompted to run through a series of steps to get its bearings」——意思是這是一套**已驗證的 protocol**，不是單次實驗。

### 2.4 三個機制的互補關係（短表）

| 層級 | 機制 | 解決什麼失敗模式 | 對應來源 |
|---|---|---|---|
| 單次任務 | Failure-class → bounded recovery | tool timeout、stale context、retry loop | arXiv 2606.01416 |
| 單次任務內 | Verifier-guided gate（silent-failure detection） | 對比證據 refine attribution | arXiv 2606.09071 (REFLECT) |
| 跨任務 / 跨 session | Posterior-guided skill evolution | 技能庫自我污染、過擬合 | arXiv 2606.08348 (Bayesian-Agent) |
| 跨 session（harness） | git + JSON progress + init.sh | 換班失憶、半成品遺產、假完工 | Anthropic Engineering |
| 跨任務（verifier cost） | Batch verification + 便宜 verifier（DeepSeek v4 Flash） | verifier 成本爆炸 → 沒人願意做 | LangChain × Harvey |
| 評估本身 | 20-50 task 起步、code+model+human 三層 grader、pass@k 跟 pass^k 並報 | eval 過重 → 沒人願意建 | Anthropic demystifying-evals |

## 3. Why It Matters / Applications

### 3.1 Silent failure 變成可量化對象

2026 上半年最重要的 idiom 轉移：**silent failure 從「偶爾發生的怪事」變成「可以被注入、被偵測、被歸因」的可研究對象**。三個獨立團隊在 90 天內同時拿出來：

- REFLECT（arXiv 2606.09071，2026-06-08）：silent failure 在 multi-hop reasoning 是系統性問題，但沒有方法用 verifier 介入結果 refine attribution 本身。
- Self-Healing Orchestrators（arXiv 2606.01416，2026-05-31）：在 controlled semantic silent-failure setting 下，verifier-guided 恢復把 silent failure 降到 0.0%（具體數字）。
- agentskeptic / trust-guard（GitHub，2026-Q2）：silent failure 在 production coding agent 裡被當作可攔截的事件（post-edit verification、real-state verification），不是模糊直覺。

> **跨 arXiv + LangChain + GitHub 的 silent-failure-as-first-class-object 在 Q2 2026 同時成熟——這是 cross-source convergence（見 skill 7.4 條目），判定為 NEW 而非 EXTENSION。**

### 3.2 Verifier 從「最後評分」變成「中段 quality gate + 後段 audit」

LangChain × Harvey 的 legal agent 工作（2026）示範了 verifier 的兩個新用法：

1. **Cost gate**：per-criterion verification 改 batch verification 降低 token 開銷；用 DeepSeek v4 Flash 替代 Opus 4.7 做 verifier，**便宜 60-1000 倍**——把 verifier 從「只在 production eval 用」變成「RL post-training 也能用」。
2. **Reward signal**：便宜的 verifier 讓 LLM-as-judge 可以驅動 RL，multiple rollouts per task 變得可行。**這是 self-improving agent 的可擴展性突破**——上週的 self-improving-agent 研究（2026-05-28、2026-05-30）都假設有強大 verifier 才能 RL，但 verifier 成本是阻礙。60-1000x 降本讓 RL 在合規/法律領域變得可行。

> 對 firn / managed-agents 最重要的：便宜 verifier 把 self-improving 從「研究演示」變成「用 free-tier 模型就能跑」。

### 3.3 評估的成本 vs 價值

Anthropic *Demystifying evals for AI agents*（2026）提出一個關鍵量化指標：

> **「Evals 的成本是 upfront 顯眼、收益是 compounding 隱性。」**

具體表現在：

- **20-50 task 起步就夠**。早期 effect size 大，小樣本就信。
- **Capability evals 在 90% pass rate 時「畢業」為 regression suite**——「Can we do this at all?」變「Can we still do this reliably?」
- **pass@k 跟 pass^k 同時報**。一個成功就算過的（pass@1）vs k 次全要過的（pass^k）——product requirement 決定用哪個。Agent consistency 比 raw 命中重要得多。
- **0% pass@100 通常是 task 寫壞了**，不是 model 弱。「每個 task 都應該有 reference solution」。

> 對 firn / managed-agents 最重要的：早期別想著 200-task suite；**user-reported failure 轉 test case 是最高 ROI 來源**。

### 3.4 Production gap：benchmark 跑分 ≠ 系統可用

arXiv 2605.26713 *RAMP: Runtime Assessing of Agentic Models in Production*（2026-05-26）做出驚人數字：

> **15 個主流 model 在 RAMP 的 compiler-construction pipeline，stage-1 是 100% 完成，stage-final 掉到 20%；0 個 model 跑完整個 pipeline。Serial workflow 下 task completion rate 呈 progressive collapse。**

這是 production-grounded 評估的強烈信號：**任何把 benchmark 當 production proxy 的說法都要打折**。

Harness-Bench（arXiv 2605.24567，2026-05-27）做了 5,194 個 execution trajectories 的分析，結論直接打臉 benchmark 慣性：

> 「Agent capability 應該以 model-harness **configuration-level** 報告，不應歸因於 base model 本身。」

意思是：同一個 Opus 4.7，在 harness A 跟 harness B 下的 failure mode 跟 reliability 差距可能是 order-of-magnitude 級。**「Claude Opus 4.7 在 SWE-bench 是 80%」這句話沒有資訊量**——你要問的是「在 **哪個** harness、**哪個** system prompt、**哪個** context management 設定下」。

## 4. Limitations / Honest Assessment

### 4.1 「98.8% task success」要打折

arXiv 2606.01416 的 98.8% 是 **100-task controlled fault-injection benchmark**——這不是 production：

- **任務是合成的**。作者自己注入 6 種已知 failure classes，這是「可以預期」的失敗。真實環境的失敗是「沒人預期過的失敗」——例如 stale context 在 Claude Code 裡可能是「前一個 session 寫的 progress file 本身有錯」。
- **沒有 cross-system 泛化**。只在 one internal orchestrator 上跑。Self-healing 在別的 agent 框架（LangGraph、AutoGen、firn）是否一樣有效——不知道。
- **Silent-failure 0.0% 是 controlled semantic**。意思是 verifier **被告知要看哪個 silent failure**。真實 silent failure 沒有先驗標籤。

### 4.2 Bayesian-Agent 的後驗不是 panacea

- **初始 45% RealFin-Bench 經 incremental repair 只到 65%**——20 個百分點的進步聽起來不錯，但還有 35% 沒救回來。意味著有些 skill 確實卡住，可能是 (a) skill 本質不適用於此任務，(b) feature bucket 切太粗。
- **Bucket 設計是手工的**。Task class、harness、model、prompt template 這 4 個 dimension 是合理的起點，但真實失敗模式的 conditioning feature 可能不是這 4 個。如果 bucket 切錯，後驗就垃圾進垃圾出。
- **沒有公開 baseline 對比**：reflexion、STELLA、ExpeL、SEAL 這些是 self-improving 領域的同期工作，paper 沒逐個比較。22 顆星的 repo 不代表社群共識。

### 4.3 Anthropic 的 harness 設計是「內部實驗」

*Effective harnesses for long-running agents* 是 Anthropic 的工程 post，不是 peer-reviewed paper：

- 沒有公開 benchmark 數字。Post 只描述「we addressed these problems」跟 qualitative failure modes。
- 沒有宣告這套 protocol 在 Claude Code production 的採用率。可能只是 internal experiment 結果。
- 「Use JSON, not Markdown」這種建議是 Anthropic 的實戰 heuristic，**不一定 generalize 到所有 model**——其他 model 對 JSON overwrite 的紀律可能不一樣。
- **Anthropic 的失敗模式來自 Claude Agent SDK**，不是泛 agent 失敗模式。OpenAI Codex / Google Jules 的失敗模式可能完全不同。

### 4.4 Cost-economics 的盲點

- 60-1000x 便宜的 DeepSeek v4 Flash verifier 假設 DeepSeek 在你 domain 上夠好。如果 domain 需要 Opus-4.7 等級的判斷力，DeepSeek 的 false-pass 率高到不能接受。
- 論文觀察到 DeepSeek 的 false-pass 率可以從 15.6% 降到 14.2%（per-batch），**仍然比 Opus-4.7 高 4-5%**。在「漏報一個違法 refund」這種 domain 4-5% 是不能接受的。
- 換 verifier 不是 free lunch——需要 prompt tuning、需要 domain calibration、需要 audit 流程。

### 4.5 Silent failure benchmark 仍然稀缺

- REFLECT 提了 4 個 localization benchmarks，但都是 multi-hop QA，**不是 tool-use traces**——原 paper 說「largest gains on structured tool-use traces」，但用的還不是 production tool trace。
- arXiv 2606.01416 的「controlled semantic silent-failure setting」是合成的，**不是真實 silent failure corpus**。
- 2026-06-09 為止，沒有公開的、community-accepted silent-failure benchmark。這是研究缺口，也是 firn 可以貢獻的領域。

### 4.6 評估跟部署仍然脫節

- RAMP 顯示 0 個 model 完成 compiler-construction pipeline——但 compiler-construction 是特殊長任務。不是所有 production agent 都這麼長。
- Harness-Bench 的 5,194 trajectories 來自 sandboxed offline tasks，**不是真實 production**。
- LangChain × Harvey 報告 false-pass 跟 false-fail 率，**但沒有報 P95 latency、cost-per-eval、user impact 這些 production 指標**。

## 5. Actionable for Our Projects

> Actionable 對象是 **firn**（個人 agent 框架）跟 **managed-agents**（orchestration framework）。**兩個專案分開寫**，因為前者是 Python library、後者是 cron 編排。

### 5.1 firn — `src/firn/`

| 建議 | 改動位置 | 難度 | 依賴 |
|---|---|---|---|
| **把 `TurnsLogger` 升級成可注入 failure detector** | `observability/turns_logger.py` | MODERATE | 不需付費 API |
| **新增 `RecoveryBudget` 守衛**：`TaskAgent` 跑任務時掛 max-recovery-attempts + max-recovery-tokens，超過就放棄 | `agents/task_agent.py` + 新 `agents/recovery.py` | MODERATE | 不需付費 API |
| **新增 `Verifier` protocol**：`code | model | human` 三種 grader 的最小可運行介面；先實作 `CodeVerifier`（跑 shell test 跟 JSON schema）跟 `ModelVerifier`（便宜的 Sonnet 或 Haiku） | `agents/verifier.py`（新檔） | MODERATE | Sonnet API（低量就便宜） |
| **批次驗證**：在 `ContextBuilder` 加 `verify_batch(criteria_list)`：不要每個 criterion 一次 LLM call，**批次成一個 prompt**。直接呼應 LangChain × Harvey 的降本發現 | `context/builder.py` | TRIVIAL | 不需付費 API |
| **Per-feature posterior 維度**：在 `SkillService` 給每個 skill 掛 `Posterior` 結構（counts 字典就夠初期，**不必上 Dirichlet**）——紀錄「在 (task_class, model_tier) 下，這個 skill 的 success/partial/fail 計數」 | `skills/skill_service.py` | MODERATE | 不需付費 API |
| **`CLAUDE-progress.txt` 風格的 session handoff**：`CronAgent` 跟長跑 `TaskAgent` 結束前必須寫 `progress.json` 給下一個 session 用 | `agents/cron_agent.py` + `tasks/dispatcher.py` | TRIVIAL | 不需付費 API |
| **`init.sh` 風格的 smoke test**：每個專案配 `init.sh`（或 `firn.toml` 配 `init_command`），session 開頭先跑一次 | `cli/` + `agents/base.py` | TRIVIAL | 不需付費 API |
| **20-task eval suite 起手**：把 user-reported failure 寫成 `tests/eval/` 下的 YAML/JSON。Anthropic 說 20-50 就夠早期 | `tests/eval/`（新目錄） | TRIVIAL | 跑 eval 時的 LLM call 成本 |
| **`harness_id` 在每次 run 必填**：`TurnsLogger` 紀錄 `harness_id`、`prompt_template_id`、`model_id` 三元組。Harness-Bench 的 core lesson：「能力要在 configuration level 報告」 | `observability/turns_logger.py` | TRIVIAL | 不需付費 API |
| **Acceptance criterion 加 silent-failure check**：對 final answer 跑 `Verifier` 對比「claim vs evidence」——如果 claim 沒在 evidence 裡就 flag | `agents/verifier.py` | MODERATE | 一個 model call / 任務 |

> **無需付費 API 的項目佔 6/10**。需要付費的 4 項都是 LLM call 成本，量不大（eval 跟 verifier 用便宜的 Sonnet/Haiku 即可）。

### 5.2 managed-agents — `/root/managed-agents/`

| 建議 | 改動位置 | 難度 |
|---|---|---|
| **Cron 報告 silent-failure self-check**：每篇研究報告 commit 前，附上「最容易被引用但其實沒交叉驗證的 1-2 個 claim 列表」 | `reports/*.md` 的後處理腳本 | TRIVIAL |
| **Research workflow 加 verifier round**：在寫完報告、extract 進 vault 之前，先用第二個 LLM 對照 source list 抓「未引用的高強度 claim」 | 新增 `scripts/verify_report.py` | MODERATE |
| **Cross-source convergence 自動標記**：如果一個 claim 出現在 ≥2 個獨立 source（arXiv + Anthropic、LangChain + GitHub），自動標 NEW | `extract_research_knowledge.py` | TRIVIAL |
| **`reports/` README 加 4 個 failure class**：tool timeout、stale context、contradictory evidence、unverified intermediate——cron 失敗時填這 4 格 | `reports/FAILURE_TEMPLATE.md` | TRIVIAL |

> managed-agents 自身不需要太多改動——cron job 本來就是「同樣工作每天重做」的高 reliability 場景，**現有 last_run staleness watchdog** 已經覆蓋大部份。

### 5.3 不建議做的事

- **不要把 Bayesian-Agent 的 Dirichlet 後驗直接 port 進 firn**——counts 字典就夠初期，Dirichlet 是 optimization premature。
- **不要複製 Anthropic 的「claude-progress.txt 用 JSON」**——這是 Anthropic 對 Claude model 的觀察。firn 用什麼 model 跑、那個 model 對什麼格式 overwrite 衝動最低，要自己測。
- **不要嘗試 silent-failure 100% detection**——這是 open problem。把 silent-failure rate 從 N% 降到 N/2% 就有 value。

## 6. Follow-up Questions

1. **Silent-failure benchmark 的社群標準**：REFLECT 用了 multi-hop QA、Self-Healing Orchestrators 用了 controlled semantic setting——有沒有可能在 6-9 個月內出現 community-accepted silent-failure benchmark for tool-use traces？這是 firn 下一個 I-teration 的好候選。
2. **Posterior-conditioned skill 在多 model 上的表現**：Bayesian-Agent 在 deepseek-v4-flash 上升 20-45 個百分點，但在 Opus 4.7、Sonnet 4.6 上是否一樣？原 paper 沒拆。
3. **Harness 設計的跨 framework 泛化**：Anthropic 的 protocol 是 Claude Agent SDK 的，能不能 port 到 LangGraph、AutoGen、firn？portability 是 open question。
4. **Verifier 的 false-pass 容忍度**：每個 domain 對 false-pass 的容忍度不同（法律 0%、行銷 5% 可接受）——有沒有可能做出 domain-calibrated verifier？
5. **Bayesian-Agent 的 bucket 設計**：paper 用 4 個手工 feature dimension；如果改成 learned embedding（用 skill description + task description 的 embedding cosine），後驗表現會不會更好？
6. **Production reliability 跟 benchmark reliability 的 gap**：Harness-Bench 跟 RAMP 都有數據，但**沒有同一個 agent system 在兩個 evaluation 下的 reliability 對比**——這是研究缺口。

---

### 原始來源

1. arXiv 2606.01416 *Self-Healing Agentic Orchestrators for Reliable Tool-Augmented LLM Systems* — 論文 — HIGH — 100-task fault-injection benchmark，98.8% success，verifier-guided silent-failure 0.0%，是 Q2 2026 reliability 領域的關鍵工作。
2. arXiv 2606.08348 *Bayesian-Agent: Posterior-Guided Skill Evolution for LLM Agent Harnesses* — 論文 + 程式碼 — HIGH — 把 skill 演化從 heuristic reflection 升級成 feature-conditioned Dirichlet 後驗，附 22★ GitHub repo，有可重現實驗。
3. arXiv 2606.09071 *REFLECT: Intervention-Supported Error Attribution for Silent Failures in LLM Agent Traces* — 論文 — HIGH — 第一個用 verifier 介入結果 refine attribution 的方法，4 個 localization benchmark 都有 highest accuracy。
4. arXiv 2606.02414 *From Agent Traces to Trust: Evidence Tracing and Execution Provenance in LLM Agents* — 論文 — HIGH — Provenance survey，整理 8 個方法論方向，是後續實作的 roadmap。
5. arXiv 2605.24567 *Harness-Bench: Measuring Harness Effects across Models in Realistic Agent Workflows* — 論文 — HIGH — 5,194 trajectories，「能力要在 model-harness configuration level 報告」是直接反駁 benchmark 慣性的關鍵洞見。
6. arXiv 2605.26713 *RAMP: Runtime Assessing of Agentic Models in Production Systems* — 論文 — HIGH — Production-grounded，15 個主流 model 在 serial workflow 下 progressive collapse 到 20% 完成率，0 個跑完整 pipeline。
7. arXiv 2605.18892 *SEAL: Synergistic Co-Evolution of Agents and Learning Environments* — 論文 — MEDIUM — 環境 + 政策同時 co-evolve 的設計，400 samples 帶來 +8~+26 百分點，提供 self-improving 路線的對比 baseline。
8. Anthropic Engineering *Effective harnesses for long-running agents* — 部落格 — HIGH — 直接從 Claude Agent SDK 內部實驗抽出 claude-progress.txt + git + init.sh protocol，是少數的 practitioner-grade long-horizon 設計。
9. Anthropic Engineering *Demystifying evals for AI agents* — 部落格 — HIGH — 20-50 task 起步、code+model+human 三層 grader、pass@k vs pass^k，量化 eval 投資回報的權威指引。
10. LangChain Blog *Designing Efficient Verifiers for Legal Agents*（×Harvey）— 部落格 — HIGH — 60-1000x verifier 降本的具體數字，per-criterion vs batch 的 trade-off，DeepSeek prompt tuning 從 15.6% false-pass 降到 14.2%。

> **GitHub / 程式庫補充**（在 §2 已引用，列為 secondary sources）：
> - DataArcTech/Bayesian-Agent（22★）— 上述 paper 的官方實作
> - E²-Bench（QinglinDong/e2-bench）— 評估「evaluation 本身可靠性」的 meta-bench
> - sdcrd/trust-guard、jettbrains/agentskeptic — silent-failure post-edit verification 工具
> - aqstack/sentinel（364★，2026-06-08 更新）— K8s 自癒 orchestrator（非 LLM 但是同樣 idiom）

---

下一個工作日排程執行本指令。
