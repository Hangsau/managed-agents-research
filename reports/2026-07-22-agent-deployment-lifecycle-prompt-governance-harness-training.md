# 研究報告：Agent Deployment Lifecycle — Prompt Governance 與 Harness Training

**日期**：2026-07-22
**來源數**：11 | **標籤**：#deployment #prompt-management #harness-training #regression-detection #agent-governance

## 1. The Problem

當一個 LLM-based agent 從 demo 走進 production，開發者面對的第一個問題不是「模型夠不夠聰明」，而是「**我今天改了一行 prompt，明天 prod 出了事，怎麼知道是哪個版本造成的？能不能在不改程式碼的前提下做 A/B？能不能 rollback 到昨天的版本？**」。

2026 上半年的市場訊號很清楚：傳統的 MLOps 工具鏈（Langfuse、PromptLayer、Helicone）解決了「trace + observation」一塊，但 production agent 出現了 **三個它們沒處理好的盲區**：

1. **Harness drift** — 真正決定 agent 表現的是「餵給模型的東西」（system prompt、context 整理、tool schema、retry loop、修補 prompt），這層系統是多檔案 Python 程式而非純字串；多數 prompt 版本控制工具看不到它。
2. **Regression detection** — 改了某個 prompt 變體後，下游某個 task panel 的分數下滑，但因為沒有基準和 ground-truth 測試集，CI 無從擋下。
3. **Incident archaeology** — 上線後某個 timestamp 出問題，「那時 prompt 是什麼？harness 是什麼 git commit？」，需要的是 **git blame for agents** 而非 dashboard 截圖。

學術側也跟上：2026 上半年至少出現 **TRiSM for Agentic AI** (Trust/Risk/Security Management for multi-agent) 的 review papers、**GCC (arXiv 2508.00031)** 開源 git-style context controller、Harness Training 這類 self-improving-harness 框架。所有跡象都指向：**agent deployment lifecycle 正在變成一個獨立學門**。

## 2. Core Mechanism

整個領域可以拆成四個互補的技術堆疊：

### 2a. Prompt Versioning + Incident Archaeology（最成熟層）

代表實作：**llmhq PromptOps**（PyPI: `llmhq-promptops`，2025-07 在 HN 公開）。

核心機制借用 git semantics 但補上 deploy time dimension：

```python
from llmhq_promptops import PromptManager, AutoResolver

manager = PromptManager(resolver=AutoResolver(repo_path="."))
resolved = manager.resolve("user-onboarding")

# resolved.text       — raw YAML
# resolved.version    — e.g. "v1.2.3" or "commit-abc12345"
# resolved.commit     — full 40-char SHA
# resolved.source     — "git" (dev) or "snapshot" (prod)
# resolved.resolved_at — tz-aware UTC datetime

log_to_observability({
    "prompt": resolved.prompt_id,
    "version": resolved.version,
    "commit": resolved.commit,
    "source": resolved.source,
})
```

Hero workflow：

```bash
# Production broke at 10:00 UTC. What was running?
promptops blame --at 2026-05-20T10:00:00Z --prompt summarizer
```

底層關鍵設計：
- **雙 resolver**：dev 用 `.git/`，prod 用 self-contained `.promptops/snapshot.json`（避免 Docker image 帶 `.git/`）。
- **append-only deploy log**：`.promptops/deploys.jsonl` 記錄每次 deploy（env, commit, actor, metadata），跟 prompt 一同進 git。
- **時間旅行語法**：`:unstaged`、`:working`、`:latest`、`commit-<sha>`、任何 tag；同一 API 在 dev/prod 都能用。

對比傳統版本控制（git only 文字檔）：PromptOps 補上 deploy event log + resolver abstraction，是「git blame 加上時間維度」的最小可行架構。

### 2b. Context-as-Git Controller（學術層）

代表實作：**GCC / Contexa**（arXiv 2508.00031 v2 = 2026-03，公佈 80.2% on SWE-Bench Verified）。

將「context」從 transient token stream 提升為 **persistent, navigable memory workspace**，模仿 git 的四個動作：

| GCC Command | Git Analogy | Meaning |
|-------------|-------------|---------|
| **OTA Log** | Working directory | Observation-Thought-Action 連續 trace |
| **COMMIT** | `git commit` | 里程碑摘要 — 把舊的 OTA 步驟壓縮 |
| **BRANCH** | `git branch` | 隔離 workspace 探索替代推理路徑 |
| **MERGE** | `git merge` | 把成功的 branch 整合回主 trajectory |
| **CONTEXT** | `git log` | 以 K-commit 解析度取回歷史 |

關鍵 benchmark 結果（arXiv v2 報告）：

| Benchmark | Score | Model |
|-----------|-------|-------|
| **SWE-Bench Verified** | **80.2%** | Claude 4 Sonnet |
| **BrowseComp-Plus** | **83.4%** | GPT-5 |

比 26 個現有 open + commercial agent 系統都好，並且論文中還報告「GC**C-equipped agents 用更多 tool calls 但成本效率反而更好**」（重要 — context 管理的 ROI 不是 token saving，而是 success-per-token）。

開源實作 Contexa 跨 7 種語言（Python/TS/Rust/Go/Zig/Lua/Elixir），用 Markdown + YAML 在 `.GCC/` 互通 — 證明這個抽象不是 Python-only 巧合。

### 2c. Harness Training（Pareto search & git-as-training-state）

代表實作：**harness-training**（2026-07-21 在 HN 公開，作者 Henry Pan 7-18 部落格詳述）。

把「如何調 harness」這個 software-engineering 工作**重新框定為 machine learning**：

| PyTorch concept | Harness Training analog |
|-----------------|------------------------|
| `Parameter.data` | HEAD's commit SHA |
| forward pass | run task panel against candidate harness |
| `loss.backward()` | write candidate-vs-baseline verdict onto `harness.grad` |
| `optimizer.step()` | git fast-forward HEAD（promote）或 no-op（reject） |

實作骨架：

```python
criterion = StrictPareto()
# StrictPareto: baseline 解決的 task 都不能 regress,
#               candidate 必須解決更多；ties 由 secondary reward 拆

optimizer = GreedyMonotonic()
# GreedyMonotonic: 通過 Pareto 才 fast-forward HEAD，否則保留為 git ref
```

訓練循環（每個 epoch = 一次實驗）：
1. **AgenticEstimator**（Codex CLI 或 Claude Code）讀 experiment evidence，提案一處 bounded 改動到 `src/policy/core.py`。
2. 候選 + baseline 同時跑 task panel（Terminal Bench 2.0 或 SWE-Bench）。
3. StrictPareto 比較勝負；winner commit（fast-forward）或 reject（保留在 `refs/candidates/`）。
4. `refs/experiments/runs/` 是每個 epoch 的 full artifact。

關鍵實驗結果（部落格 2026-07-18）：
- **SWE-Bench**：8/39 → 14/39 solved in 29 experiment runs, 8 promoted, 20 rejected, 1 baseline.
- **Terminal Bench 2.0**：38 task panel → 從 18/38 baseline 爬到 23/38 over 9 promoted commits.
- **轉移性**：在 Terminal Bench 訓練的 harness 拿去跑 SWE-Bench 也有轉移 gain（證明不是 overfit）。
- **跨模型轉移**：同一個 trained harness + 不同 model 都能 evaluate — harness 是 frozen 的, model 是 plug-in.

8 個 promoted commits 揭示了真正的「harness-level learning」是什麼：

| Commit | Mechanism | Effect |
|--------|-----------|--------|
| `84241c31` | step ≥ 100 時 inject 「only files on disk at submit are graded」提醒 | +2 tasks |
| `ca412ea7` | action guard: step ≥ 109 強迫 bare `submit` if edits on disk | +1 task |
| `eb658d1a` | reasoning-runaway: 從 abort 改成「drop thinking + continue」 | +1 task |
| `527712d4` | git-state guard: stash/checkout/reset 換成 safe-diff-print | +1 task |
| `292e6ff6` | 修 `pytest ... \| tail` 改為 `bash -o pipefail -c '...'` | +1 task (tail 之前一直誤導 agent) |
| `14ef7381` | LLM response cutoff 無 tool call 時 disable thinking + 修補 prompt | **+5 tasks** (biggest jump) |

**最後一個是 engineering insight**：當模型燒光 output token 還在 reasoning 時，原本 abort；改成「drop thinking block, retry with prompt」後 5 個 long-horizon task 一夕被解。這不是 better prompt，是**更好的 retry policy**。

### 2d. Runtime Guardrails & Eval Harness（最實戰層）

代表實作：
- **Forge**（2026-05-19，Texas Instruments AI Director 開源）— 把 8B 本地模型在 26 scenario v0.7.0 eval suite 從個位數拉到 **84%**；Sonnet 4.6 從 **85% → 98%**。三種使用模式：proxy server（drop-in OpenAI/Anthropic API）、WorkflowRunner、Guardrails middleware。
- **Langfuse Prompt Management**（2026 主要商業 OSS 之一） — 中央化的 prompt registry，UI/SDK 雙介面，strong caching，playground + tracing 閉環。
- **Rigour v4.2**（2026-02-21） — "AI Agent Governance, One command"，hooks fire on every file write across Claude/Cursor/Cline/Windsurf/Copilot, **OWASP LLM 10/10** covered. Block writes to native agent memory files (CLAUDE.md/.cursorrules/.clinerules) 強制走 governed channels.
- **XR2**（2026-03-04）— A/B test prompt variants, attribute conversion events (signup/purchase) back to prompt version, 統計顯著性才 pick winner.
- **Time Machine**（2026-03-09）— fork agent execution at any step, replay only downstream — 內部 framing 是 "Git for agent execution".

Forge 的設計特別值得拆解：它聲稱自己「**不是 agent orchestrator**」—只接管 tool-call loop，把 rescue parsing、retry nudges、response validation、required-steps enforcement 注入進去。它把 reliability 從 model-level pull 到了 **middleware-level**。

## 3. Why It Matters / Applications

對 AI agent 領域，這週期的整體衝擊是 **「deployment 變成一等公民」**。歷史上 model 表現是 release note；現在 harness 是 release note。

**實務上意味著**：

1. **每改 prompt 不再 deploy code** — XR2、Langfuse、PromptOps 都把 prompt 從 source code 中搬出來變 runtime artifact，等於 Web 前端把 asset 從 bundle 搬出來改成 CDN 的同一波位移。
2. **self-improving 不再是 magic — 是 git workflow** — Henry Pan 的 framework 把 "agent improve itself" 變成可審查、可 revert、可 A/B 的工程流程。recursive self-improvement 第一次有了 production shape。
3. **agent reliability 可量化** — Forge 在固定 eval suite 上展示 "8B + 84%" 跟 "Sonnet 4.6 + 98%" 的數字，意思是：guardrails 比 upgrading model 更 cost-effective。
4. **incident response 有了標準動作** — `promptops blame --at <ts>` 是 agent SRE 的「git bisect for production」。
5. **multi-agent governance 有可執行介面** — Rigour 把 OWASP LLM Top 10 + memory governance 變 single CLI，未來 audit 介面不再是 spec PDF 而是 exit code。

跨領域的影響：DevOps 文化的 MLOps / LLMOps 工具終於在這個週期收斂成可互通的 stack — 比如 **Langfuse ↔ OpenLLMetry ↔ PromptOps** 都能在 promptops blame 的時間軸上 trace 到 Langfuse 的 span（這是下一波 cool integration，不是 OO 競爭）。

## 4. Limitations / Honest Assessment

**連環誠實 look：**

1. **Determinism 是必需前置，不是 nice-to-have**：Harness Training 部落格自己承認 "I had to reset baseline at run 26 because non-determinism polluted experiment signal"。意思是：要做 Pareto eval of harness 必須先有 SGLang deterministic kernel 或 llama.cpp `--parallel 1`，**這是 infra 成本** — 不是所有團隊願意扛。
2. **GCC 80.2% SWE-Bench Verified 是強 baseline**：v2 是 2026-03 更新，11 個月的進步。但對一般企業內部任務（custom codebase、private tickets）**沒有 evidence**。GCC 的 "git semantics" 對 software task 是 fit，但對客服/銷售/資料分析等其他 agent type 仍未驗證。
3. **self-improving harness 是 local optimum**：StrictPareto 嚴格 monotonic — baseline 解決的不能 regression。這意味著 harness **無法 discover 完全不同的策略**，只能 improve-around-baseline。Henry Pan 也坦承 21/39 SWE-Bench tasks 在 29 個 run 內 never solved — 可能就是 model capability ceiling 或 step cap artifact。
4. **XR2 / PromptOps / Langfuse 三家商業界線模糊**：XR2 強調 "what existing tools lack is conversion attribution" — 也就是說 Langfuse、PromptLayer 的 prompt management 對 **真正在意轉換率**的 product team 還不夠。但對 agent infra team 來說 Langfuse 已夠用。這個分眾短期內不會收斂。
5. **Rigour 的 governance 沒有 audit trail**：hook-based governance 攔截 29 credential pattern + 6 種語言 drift detection，但本身沒有 "誰在何時改了 promptops-snapshot 的什麼欄位"的 audit log — 自身缺 trace，會成為下一輪追打的點。
6. **Time Machine 的 world state 問題有人指出**：HN 評論立刻說 "checkpointing the conversation state is just a list. checkpointing the **world** state isn't. step 5 寫了 rows to Postgres, step 7 打了第三方 API, forking from step 6 需要 DB snapshot + external call mock." 這是 fork-and-replay 風格的普遍 limitation，目前任何 vendor 都沒完全解決。
7. **GCC 對 free-tier 可行性**：Markdown + YAML on disk 顯然 free，但七語言 client SDK 是否都 production-grade 仍需時間驗證；很多 "MIT cross-language" repo 在第三個語言後 quality 衰減。

**權衡總結**：

| 情境 | 推薦方案 | 警告 |
|------|----------|------|
| Solo dev / 小團隊 prototype | Langfuse Cloud free + 手動 YAML | 投資成本低，但 incident archaeology 靠 log search |
| 內部 SRE-grade production | PromptOps + Langfuse + 你的 git | infra 投資中等，blame 可審查 |
| 想訓練自己的 harness 改進 | Harness Training + SGLang + 5090 GPUs | 45 分/epoch + 模型 download，誠實建議「throwaway VM」 |
| 高度監管行業（金融/醫療/政府） | Rigour + 自己再加一層 audit log | 目前 audit trail 不齊 |
| 多 agent system | Forge proxy + Langfuse + per-agent eval panel | SlotWorker for shared GPU 在 v0.7.0 才穩 |

## 5. Actionable for Our Projects

firn 的架構細節我未在這輪深入 audit，但從先前的報告（6-19 memory governance、6-17 trace、7-03 OTel）和 hermes-self-hosting 角度列具體建議：

### Tier 1 — TRIVIAL（半天內能做）

1. **把 hermes 自己的 system prompt 與 skills 從 `.py` 抽出來變 YAML**，由 `PromptManager` 或自寫 git-based resolver 載入。每個 prompt commit 進 git 後，記錄 commit SHA 到 OTel span attribute（已有 OTel GenAI semantic conventions 7-03 鋪路）。
2. **加一個 `prompt-ops blame <timestamp>` CLI**（哪怕只 print 當下 HEAD commit + 所有 prompt 檔路徑），接續已有 hermes skills 系統（6-08 progressive disclosure）。
3. **為主要 prompt 寫一份 eval panel**：抽 10–20 個可以 deterministic 跑的 task（小到「summarize 這段 README」、「parse this JSON」、「這個 regex 該 match 什麼」），每改 prompt 必跑這份 eval。`scripts/eval_panel.py`，`exit code` 決定能否 merge。

### Tier 2 — MODERATE（幾天內能做）

4. **整合 OpenLLMetry 或 Langfuse SDK**（已有 7-03 OTel GenAI conventions 為基礎），attribute span 加 `prompt.version`、`prompt.commit_sha`、`prompt.source`（git vs snapshot）。對齊 OpenLLMetry / PromptOps 標準 — 將來能 plug 進 marketplace。
5. **snapshot bundle 用 Docker build**：自己寫一個 `hermes promptops snapshot build`，把 resolved prompts + harness config 凍成 `.hermes-prompts-snapshot.json`，塞進 Docker image，不靠 `.git/` 即可決定行為。對齊 PromptOps 的 dev/prod abstraction。
6. **借鏡 Forge 的 guardrails middleware**：在 hermes 的 tool-call loop 外面包一層 — rescue parsing, retry nudge, response validation。對 self-hosted Hermes 來說成本極低（純 Python），但效益巨大（防 malformed tool call 把 agent 卡死）。
7. **嘗試 deterministic kernel**：llama.cpp 起 server 時固定 `--parallel 1` + `--seed 12345` + temp=0。如果要跑 harness eval panel 就必須。

### Tier 3 — HARD（Q3 research thread）

8. **Harness Training 移植**：把 `core.py`（我們的 agent loop + skill loader + context manager）架構成 Pareto-trainer-friendly — 一個 "diff at a time" 的 trainable surface。短期不一定要跑 30 epoch，但先有 baseline harness + eval panel + criterion 是前置。
9. **跨 hermes-cli / hermes-server / talos 一份統一的 prompt spec**：現在應該有 hardcoded 字串散落在 Python 模組。GCC / Contexa 展示過用 `.GCC/main.md` + branches 可以跨 process 共享 context；這套對 prompt spec 也適用。

### 付費 API 依賴？

- **PromptOps, Contexa, Harness Training, Librarian** — 全 OSS MIT，零 API cost。
- **Langfuse Cloud** — 有慷慨 free tier，self-host 全免。
- **Forge** — 你自己跑 LLM backend，零 vendor fee。
- **XR2, Rigour, Time Machine** — SaaS 商業，免費 tier 可開始。

**唯一付費依賴點**：要不要買 managed inference（OpenAI/Anthropic）。本週期所有 framework 都是 **model-agnostic**，對 Hermes 完全相容 — 不需要任何付費 API。

### 具體不該做的事

- **不要相信任何 prompt A/B 平台聲稱的統計顯著性可替代 production eval panel**。所有 vendor 都強調 "we do stats", 但 production 任務里 "winning variant" 可能在你的 1% edge case 上 regress — 你必須有自己 panel.
- **不要把 governance（policy enforcement）跟 observability（tracing）混為同一個 vendor**。Rigour 跟 Langfuse 屬性不同 — 鎖一家會被 vendor 鎖死。
- **不要為了 harness training 在 production 環境跑**。Harness Training 自己寫 "disposable VM, separate OS account, machine dedicated to agent workloads" — 這不是 paranoid，是必要的.

## 6. Follow-up Questions

1. **PromptOps 的 snapshot bundle 跟 Langfuse 的 prompt registry 能不能互通？** 兩個都聲稱 "version-aware prompt resolution"，但格式不同。如果有 bridge，未來能 plug 一家用就行。
2. **Harness Training 的 Pareto criterion 對長期任務會不會 lock-in 在 baseline？** 嚴格 monotonic 在 30 run 內有效，但跨 N 個月（model 換代、skill 換代）會不會反而卡住 harness 演化？需要 longitudinal experiment.
3. **GCC 的 SWE-Bench 80.2% 對其他 domain 有 transfer 嗎？** 論文只展示 SWE-Bench + BrowseComp；客服、data analysis、研究 summarization 等需要重新 eval。
4. **Forge 的 proxy mode 是否能 plug 進 hermes-self-hosting？** 如果 hermes 把內部 LLM 呼叫轉給 Forge proxy 跑 guardrails，等於零改動 hermes 核心就拿到 rescue parsing + retry nudge。短期可驗證.
5. **multi-agent 場景下 prompt version drift 怎麼處理？** XR2/Langfuse/PromptOps 都假設 single agent per prompt；如果 hermes 多 agent (7-01 的 meta-agent supervision) 同時調用同一 prompt 的不同版本，blame 該怎麼歸因？
6. **policy-as-code 跟 prompt-as-code 會不會 collapse 成同一層？** Rigour 把 CLAUDE.md/.cursorrules 視為 governed channels — 但同時 Langfuse 把 prompt 視為 runtime artifact。兩條 spec 路線哪條統一？可能下個 cycle 會出現 RFC.

---

### 原始來源

1. https://www.henrypan.com/blog/2026-07-18-harness-training/ — 部落格 — HIGH — Harness Training 完整 PyTorch-style 框架, 8 個 promoted commits, deterministic kernel 必要條件
2. https://github.com/workofart/harness-training — 程式碼 — HIGH — Hunyuan-style harness trainer，30 epochs 30 candidate refs/refs/experiments preserved
3. https://arxiv.org/abs/2508.00031 — 論文 — HIGH — GCC 論文 v2, 80.2% SWE-Bench Verified + 83.4% BrowseComp-Plus
4. https://github.com/swadhinbiswas/contexa — 程式碼 — HIGH — GCC 開源實作, 7 語言互通, MIT
5. https://github.com/llmhq-hub/promptops — 程式碼 — HIGH — `promptops blame --at <ts>` 是 git blame for agents 的最小可行架構
6. https://github.com/antoinezambelli/forge — 程式碼 — HIGH — 8B 53% → 84% + Sonnet 4.6 85% → 98% on agentic tasks; proxy/WorkflowRunner/middleware 三模式
7. https://rigour.run — 程式碼 — HIGH — OWASP LLM 10/10 hooks on every file write across Claude/Cursor/Cline/Windsurf/Copilot
8. https://langfuse.com/docs/prompt-management/get-started — 官方文件 — HIGH — Langfuse prompt registry + caching + agent skill installation
9. https://news.ycombinator.com/item?id=47246813 — 討論 — MEDIUM — XR2 創辦人自述 148k-user AI SaaS 經驗，痛點是「迭代 prompt 不用 deploy code」
10. https://news.ycombinator.com/item?id=47315394 — 討論 — MEDIUM — Time Machine "Git for agent execution"，HN 評論點出 world state 難題
11. https://uselibrarian.dev — 產品頁 — MEDIUM — Librarian 在 turn 50 達 85% token reduction，prompt-context-window 管理是 deployment 主戰場的佐證

---

**結束語**：下一個工作日排程執行本指令。
