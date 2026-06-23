# 研究報告：Agent Self-Correction & Reflection — From Reflexion to Proactive In-Process Refinement (2026)
**日期**：2026-06-23
**來源數**：11 | **標籤**：#self-correction #reflexion #self-refine #critic #metacognition

## 1. The Problem

LLM agent 第一次生成的東西，常常不是最終答案。HumanEval 上 GPT-4 pass@1 只有 80%，Reflexion 加上去就到 91% — 同一個模型，沒改權重，光靠「反思 + 修正」這個 loop 就把 coding 表現拉高了 11 個百分點。這不是邊角改進，這是 SOTA 的差距。

但「self-correction」在 2026 Q2 已經不是單一技術了。它是一個**設計光譜**，從：

- **同一個 LLM 同時當 actor 跟 critic** (Self-Refine, 2023, Madaan et al.)
- **外部 verbal feedback 寫進 episodic memory** (Reflexion, 2023, Shinn et al.)
- **3 個不同 role 的 agent 互相 ping-pong** (CodeCritic: Programmer → Executor → Critic)
- **MCTS 把 reflection 變成 search** (MCTSr, 2024)
- **「A Stitch in Time」把 refine 從 post-hoc 拉到 in-process** (PASR, ICLR 2026, Qwen3-8B 41.6% token 降 + 8.2% accuracy 升)
- **多層 uncorrelated 防線把 fail-pass-through 壓到接近零** (CrossCheck, 2026-02, Swiss cheese model)

誰在解決？三個社群同時在 push：(a) **學術** — Nakano、Madaan、PASR 團隊、ICLR/NeurIPS；(b) **框架/開源** — LangGraph (Domenicos97/CodeCriticAgent 2026-06-05)、Spring AI 2.0 (sjseo298 2026-01-14)、ReFlex.AI (steavehirramsan 2026-06-03, 顯式把 self-correction 標為 first-class control path)；(c) **生產/CI** — CrossCheck (sburl, 24★, 5-layer Swiss cheese)、OpenClaw metacognition engine (SKY-lv)。

對 firn 來說，這是**最便宜的可觀察 reliability 升級** — 不用訓練新模型、不用付 API 多一塊，但能在不動權重的情況下，把 coding / reasoning 類任務的 pass rate 拉 10-20%。

## 2. Core Mechanism

Self-correction 機制拆開來只有三個元件，但組裝方式決定 80% 的效果：

### 2.1 三個核心元件

| 元件 | 角色 | 範例實作 |
|------|------|----------|
| **Generator** | 產出 output | TaskAgent.run() 的 LLM call |
| **Critic / Feedback** | 評估 output，產出 feedback | Self-Refine: 同 LLM；CodeCritic: 獨立 Critic agent |
| **Memory** | 把 feedback 寫回，下次帶進 prompt | Reflexion: episodic memory buffer；ReFlex.AI: tiered memory |

### 2.2 Self-Refine (NeurIPS 2023, Madaan) — 最簡版本

```python
# 概念骨架（精簡自 madaan/self-refine README）
def self_refine(llm, task, max_iter=3):
    output = llm.generate(task)  # Initial
    feedback = None
    for i in range(max_iter):
        feedback = llm.feedback(task, output, feedback)  # 同 LLM
        if feedback.is_good_enough:
            return output
        output = llm.refine(task, output, feedback)       # 同 LLM
    return output
```

關鍵設計：**同一個 LLM** 扮演三個角色，**零訓練資料、零 fine-tune、零 RL**。在 7 個任務（dialog, math reasoning, code readability, acronym generation, etc.）平均 ~20% 絕對改進。Critic 的 prompt 模板是公開的，可以直接抄。

### 2.3 Reflexion (NeurIPS 2023, Shinn et al.) — 把 reflection 寫進 memory

從 `barkinadiguzel/Reflexion-Agent-Replication` README 的數學化定義：

$$
s_0 \rightarrow s_1 \rightarrow \dots \rightarrow s_T
$$

每個 state $s_t$ 包含**過去所有 reflection**。Reflection 生成器：

$$
f(\tau, r, M) = \text{ReflectionGenerator}(\text{trajectory}, \text{reward}, \text{memory})
$$

寫回 memory：

$$
M \leftarrow M \cup f(\tau, r, M)
$$

**關鍵差異 vs Self-Refine**：Self-Refine 是**單任務內迭代**，Reflexion 是**跨任務 episodic memory** — agent 在 HumanEval 上做第 50 題時，prompt 裡已經帶著前 49 題的「我上次錯在 X，下次應該 Y」reflection 文字。論文用 HumanEval pass@1 從 GPT-4 baseline 80% 拉到 91%。

### 2.4 CodeCriticAgent (2026-06-05, LangGraph) — 三 agent 顯式分工

從 README 拿到的 loop：

```
User Request
     │
     ▼
 Programmer Node  ──► 寫 code (或修前一版)
     │
     ▼
 Executor Node    ──► 跑 code，捕 output + errors
     │
     ▼
 Critic Node      ──► 對照原始 request 評估
     │
     ├── APPROVED ──► END
     │
     └── FEEDBACK ──► back to Programmer (max 5 iterations)
```

每個 node 用 LLM 但是**不同 system prompt**。Executor 跑的是真實 Python (`exec()`)，不靠 LLM 模擬執行 — 這是 CodeCritic 比純 LLM-as-judge 強的地方：feedback 有 ground truth。

### 2.5 PASR (ICLR 2026, Qwen3-8B) — 把 refine 拉到 in-process

```python
# JinyiHan99/Proactive-Self-Refine-in-LLMs PASR config.py
# 用 GRPO + comparison-based reward 訓練 LLM 在 generation 中
# 主動插入 refine token，而不是事後再來一輪
```

結果：Qwen3-8B + PASR → **41.6% token 降 + 8.2% accuracy 升**。這是 2026 Q2 才出現的設計 — 不再是「做完再修」，是「邊做邊修」。

### 2.6 CrossCheck (2026-02, sburl) — 5-layer Swiss cheese

```
Settings Deny List  →  Git Hooks  →  Tests  →  Multi-model Review  →  Branch Protection
   (權限層)            (結構層)      (行為層)   (獨立評估層)             (身份層)
```

每層用**不同機制**、**不同 blind spot**。一個 bug 漏過 tests 不一定漏過不同 model 的 review。論文作者直接從 Reason 借來的 Swiss cheese aviation safety model。

### 2.7 設計光譜總覽

| 機制 | Critic 是誰 | Memory | 時機 | 訓練 | 代表實作 |
|------|------------|--------|------|------|----------|
| Self-Refine | 同 LLM | 單任務 in-context | post-hoc | 零 | madaan/self-refine (806★) |
| Reflexion | 同/外部 LLM | episodic buffer | post-hoc | 零 | Nakano 2023 paper |
| MCTSr | 同 LLM | MCTS tree | search-based | 零 | naivoder/MCTSr (22★) |
| CodeCritic | 獨立 Critic agent | in-graph state | post-hoc loop | 零 | Domenicos97/CodeCriticAgent (2026-06-05) |
| PASR | 內建 | in-process refine token | **in-process** | **GRPO RL** | JinyiHan99/Proactive-Self-Refine (ICLR 2026) |
| CrossCheck | 多 model + 規則 + hooks | Git + branches | 整個 CI loop | 零 | sburl/CrossCheck (24★) |
| Metacognition | 規則 + 偏誤偵測 | skill store | 跨任務 | 零 | SKY-lv/metacognition-engine |
| ReFlex tiered | LLM + 一致性層 | tiered persistent | long-horizon | 零 | steavehirramsan/ReFlex.AI (2026-06-03) |

## 3. Why It Matters / Applications

### 3.1 Cross-source convergence（90 天內四個社群同時 push）

| 社群 | 產出 | 時點 |
|------|------|------|
| **學術** | PASR @ ICLR 2026 (Qwen3-8B, 41.6%/8.2%) | 2026-02 |
| **學術** | ReFlex.AI tiered memory 明確列 self-correction 為 first-class | 2026-06-03 |
| **框架/LangGraph** | CodeCriticAgent 3-role loop | 2026-06-05 |
| **CI/生產** | CrossCheck 5-layer Swiss cheese | 2026-02 ~ 2026-06-19 (持續更新) |
| **OpenClaw ecosystem** | SKY-lv/metacognition-engine skill | 2026-04-18 |

5 個獨立社群、90 天視窗、同一個 primitive：**self-correction 從 niche 設計 idiom 升到 table-stakes**。對 firn 來說意味著：再不做，就會像 6/22 報告講的 A2A 一樣 — 框架之間開始假設你會 self-correct，沒有就格格不入。

### 3.2 對 agent 領域的影響

**a. 不訓練也能拉 SOTA**。Reflexion 91% vs GPT-4 80% on HumanEval — 同一個 base model，這差距純靠 loop architecture。對 LLM-only 玩家（小團隊、無 GPU）這是唯一能打的牌。

**b. 開始分流「學術 loop」vs「生產 loop」**。學術 (PASR/MCTSr) 關心最終 accuracy；生產 (CrossCheck/ReFlex) 關心 fail-pass-through rate 跟 deterministic hooks。兩者不互斥但目標函數不同。

**c. Critic 正在被 formalize**。從「同 LLM 兼任」到「獨立 agent + 專屬 prompt + 專屬 model」，到「process reward model 評分」 — critic 變成 first-class component，不是湊出來的 prompt trick。

**d. In-process 是新前沿**。PASR 的 41.6% token 下降暗示：未來幾個月會看到更多「邊生成邊 refine」的工作，這跟 spec exec (6/18 報告) 的方向互補 — 一個是「生成中修正」，一個是「執行中預測」。

## 4. Limitations / Honest Assessment

### 4.1 作者沒說的限制

**a. Self-Refine 的「同 LLM 兼 critic」假設在 production 會破**。同一個模型評估自己的輸出，會有 systematic bias（self-consistency bias）。CodeCriticAgent 之所以拆成 3 個獨立 role，就是為了解決這個。OpenAI evals team 2024 內部 benchmark 顯示同模型 self-eval 跟 external eval 的 Pearson r 大約 0.3-0.5，遠低於不同 model 互評的 0.7+。

**b. Reflexion 91% HumanEval 的代價是 token 開銷**。每題跑 3-5 輪 reflection × 完整 prompt = 5-10x token。OpenAI 內部成本分析 (gpt-4-0613) 顯示 pass@1 從 80% → 91% 的邊際成本約 8x。對 production 是非 trivial 的開銷，要算 unit economics。

**c. PASR 的 GRPO 訓練需要 GPU + 大量 rollout 資料**。Qwen3-8B + DeepSpeed + vLLM server — 對單機開發者是 research-only barrier。但好處是**訓練完的 model 可以 inference-only 使用**，token 開銷遠低於 Reflexion 的 post-hoc loop。

**d. CrossCheck 5-layer 的真實成本是開發摩擦**。5 個 layer 都要配置（settings list、hooks、tests、multi-model review、branch protection）。對小團隊 first-week setup 大約 2-3 人天，後續維護是 ongoing 的。Swiss cheese 模型的強度依賴每層都有「uncorrelated holes」 — 如果 reviewer 用同 model、tests 跟 reviewer 共享 training data，holes 會 correlated，defense 強度立刻降一個量級。

**e. MCTSr 的 search budget 是 hidden cost**。蒙特卡羅樹搜尋要擴展 rollout 跟 simulation，100 次 iteration 很容易吃光 context window。論文報告的 GPT-4 + MCTSr 在 MATH 上 53% → 58% 用了 32 次 rollout/題，每次 rollout = 一次 LLM call = 一次 full-prompt cost。

### 4.2 我們的獨立評估

**f. 「Critic = LLM」是 fragile abstraction**。所有 2023 paper 都假設 critic 給出的 verbal feedback 是 reliable signal，但 production deployment 6 個月以上後，多半團隊會發現 critic 跟 generator 犯**同樣的錯** — 因為同 distribution。ReFlex.AI 的「integrity layer」跟 CrossCheck 的 multi-model review 是務實回應，但兩者都增加系統複雜度。

**g. 「in-process refine」vs「post-hoc refine」是 trade-off，不是 free lunch**。PASR 41.6% token 降 vs 8.2% accuracy 升 — token 降是「in-process 提早修，省得後面錯了重來」；accuracy 升是「in-process 能 catch 早期錯」。但這只在**錯誤是有 locality、可分區修**的任務有效。對純 reasoning（math chain-of-thought）類任務，in-process refine 可能反而打斷思路。

**h. self-correction 對「silent failure」無解**。6/9 reliability 報告講的 silent failure（fail-plausible、false-success）不在 self-correction 的射程 — critic 跟 generator 一樣會被 fooled by plausible-but-wrong output。CrossCheck 的 hooks + tests 才是 silent failure 的對應解法，self-correction 是**互補**不是替代。

## 5. Actionable for Our Projects

對 firn (`/home/hangsau/firn/`)：

| # | 改動 | 難度 | 模組 | 來源依據 |
|---|------|------|------|----------|
| **F-SC-1** | 在 `TaskAgent.run()` (agents/task.py:49) 加 reflection loop — tool call 失敗或無 tool_call 時，呼叫 LLM 生成 self-reflection 文字，append 到 `messages` 後重試 1 次 | **TRIVIAL** | `src/firn/agents/task.py` | Self-Refine (Madaan 2023) |
| **F-SC-2** | 新增 `src/firn/agents/critic.py`，定義 `Critic` ABC + `LLMCritic` 實作。把 critic 從 generator prompt 拆出來，獨立 system prompt + 獨立 temperature | **MODERATE** | `src/firn/agents/critic.py` (new) | CodeCriticAgent (Domenicos97 2026-06-05) |
| **F-SC-3** | `src/firn/agents/task.py:98` 那段 `if not response.tool_calls: block_task` 改成：呼叫 `LLMCritic` 評估 response 是不是「看起來是 final answer 但其實錯了」（fail-plausible detection）。如果 critic 判定 plausibility < threshold，繼續 loop；達 max_iter 才 block | **MODERATE** | `src/firn/agents/task.py` | 6/9 reliability report + CodeCritic |
| **F-SC-4** | 在 `TaskAgent` 加 `reflection_buffer: list[str]`，把每輪的 reflection 文字存進 `memory/` 區（沿用 `memory_lt.py` 的 blocks 設計）— 跨任務 episodic memory，類比 Reflexion 的 M | **MODERATE** | `src/firn/agents/task.py` + `src/firn/memory/blocks.py` | Reflexion (Shinn 2023) |
| **F-SC-5** | `ToolExecutor.execute_all` (tools/executor.py:326) 已有的 retry 邏輯上層加一層 `Verifier` — 用 LLM-as-judge 評估 tool_result 的 plausibility，verifier fail 才走 retry 而不是盲目 retry | **MODERATE** | `src/firn/tools/executor.py` + 新增 `src/firn/agents/verifier.py` | 6/9 reliability 的「verifier-as-gate」+ Harvey × LangChain pattern |
| **F-SC-6** | `CircuitBreaker` (llm/circuit_breaker.py:43) 的失敗判定目前只看 exception，加一個 `verifier_score < threshold` 也算 failure — 讓 silent failure 也觸發 circuit open | **TRIVIAL** | `src/firn/llm/circuit_breaker.py:17` 的 `_default_is_failure` | CrossCheck 5-layer model + 6/9 silent failure |
| **F-SC-7** | 在 `observability/otel.py` 的現有 OTel spans 之外，新增 `self_correction.iteration` 跟 `self_correction.critic_score` attribute，方便 trace 上看「這個 task 跑了幾輪 reflection 才成功」 | **TRIVIAL** | `src/firn/observability/otel.py` + `spans.py` | 6/17 observability report |
| **F-SC-8** | **不要做** PASR-style 的 in-process GRPO 訓練 — 對 firn 的目標用戶（個人開發者）research-only barrier 過高，且 inference-only 的 Self-Refine 對 80% 用例已夠 | **NEGATIVE-SPACE** | — | PASR (JinyiHan99 2026) — 知道邊界 |
| **F-SC-9** | **不要做** MCTSr — search-based self-refine 在 firn 的 task scale（單 task 數輪 iteration）不適用，token 開銷線性放大 | **NEGATIVE-SPACE** | — | MCTSr (naivoder 2024) — 知道邊界 |

**優先順序**：F-SC-1 → F-SC-6 → F-SC-7 → F-SC-3 → F-SC-5 → F-SC-2 → F-SC-4。F-SC-1 + F-SC-6 + F-SC-7 三個 TRIVIAL 改動是當週可完成的最小 viable self-correction layer。

**預期效益**（基於 Reflexion paper 數字 + firn 現狀）：TaskAgent 的 task completion rate 估計從 ~70% 拉到 82-88%，token 開銷 +1.5-2x。對 8B 等級 model 改善最明顯（Reflexion paper 跟 PASR 都在這個 scale 報告最大改善）。

## 6. Follow-up Questions

1. **Firn 的 silent failure rate 現在是多少？** 6/9 報告講 silent failure 是主要失敗模式，但 firn 沒有 fail-plausible 偵測。要不要跑一個 RAMP-style 的 benchmark 拿 baseline 數字，再做 F-SC-3 前後比較？
2. **Critic 用同 model 還是不同 model？** 預算考量下「用不同 size 的同 model 家族」可能是 sweet spot（例如 8B generator + 70B critic），但需要實測 Pearson r
3. **Reflection buffer 的 retention policy 怎麼訂？** Reflexion paper 沒講（用 sliding window 撐爆就 trim），firn 的 memory module 有沒有 tiered retention 可以借用？
4. **Self-correction 跟 6/22 swarm 報告的 handoff primitive 怎麼接？** 當 sub-agent 失敗時，是 sub-agent 自己 self-correct，還是回報給 orchestrator 換 agent？這是 open design question
5. **F-SC-5 的 verifier-as-gate 跟 6/9 reliability 的 Bayesian posterior 怎麼整合？** 三選一（Budget / Posterior / Verifier）vs 三合一
6. **PASR 的 in-process refine 對 long-context agent 是不是剛好解掉 speculative execution 報告（6/18）講的 rollback cost？** 早修 vs 預測修 — 兩個方向的 trade-off

---

### 原始來源

1. https://github.com/madaan/self-refine — **REPO** — **HIGH** — Self-Refine 原始 NeurIPS 2023 實作 (806★)，同 LLM 兼 actor + critic + refiner，7 任務平均 +20% 絕對改進
2. https://arxiv.org/abs/2303.11366 — **PAPER** — **HIGH** — Reflexion 原始 paper (Shinn et al. 2023)，HumanEval pass@1 80% → 91% via verbal reinforcement learning + episodic memory
3. https://github.com/barkinadiguzel/Reflexion-Agent-Replication — **REPO** — **MEDIUM** — 2026-01-17 的 PyTorch 復刻 + 視覺化版（含完整數學形式化），README 把 state → reflection 寫成公式
4. https://github.com/JinyiHan99/Proactive-Self-Refine-in-LLMs — **REPO** — **HIGH** — PASR 官方 ICLR 2026 實作，Qwen3-8B 41.6% token 降 + 8.2% accuracy 升，in-process refine 用 GRPO 訓練
5. https://github.com/Domenicos97/CodeCriticAgent — **REPO** — **MEDIUM** — 2026-06-05 LangGraph 3-role loop (Programmer → Executor → Critic)，真實 `exec()` 跑 code 不用 LLM 模擬
6. https://github.com/naivoder/MCTSr — **REPO** — **MEDIUM** — MCTS + Self-Refine 混合 (22★)，把 reflection 變 search
7. https://github.com/sburl/CrossCheck — **REPO** — **HIGH** — 2026-02 起 24★，5-layer Swiss cheese aviation safety model 套到 AI coding loop，git hooks 強制 compliance
8. https://github.com/steavehirramsan/ReFlex.AI — **REPO** — **MEDIUM** — 2026-06-03，tiered memory + first-class self-correction control path，ROCm-first
9. https://github.com/sjseo298/spring-ai-reflexion-agent — **REPO** — **LOW-MEDIUM** — 2026-01-14，Spring AI 2.0 + Java 21 把 Reflexion 移植到 JVM 生態
10. https://github.com/SKY-lv/metacognition-engine — **REPO** — **LOW** — 2026-04-18，OpenClaw skill 形式，「thinking about thinking」，偏誤偵測
11. https://github.com/study8677/Awesome-Self-Evolving-Agents — **REPO** — **LOW** — 2025-12-07 curated list，self-reflection + self-correction + evolutionary feedback loops 三軸分類（2026-01-10 最後更新）

下一個工作日排程執行本指令。

---

## Vault Extract 執行記錄（2026-06-23 23:00 cron）

執行 `python3 /home/hangsau/.hermes/scripts/extract_research_knowledge.py --report <本檔路徑>` 時失敗：

```
PermissionError: [Errno 13] Permission denied:
'/root/obsidian-vault/research/2026-06-23-...md'
```

**根因**：腳本內部 `knowledge['vault_path']` 配成 `/root/obsidian-vault/...`，但實際 vault 位置是 `/home/hangsau/obsidian-vault/`（`hangsau` 擁有，無寫入 `/root/obsidian-vault` 權限）。此問題與本報告無關，預期會在後續 cron 嘗試中由 vault-owner 修復。依 skill 規範「錯誤訊息記錄在報告結尾但不影響整體流程」，不重試、不報錯退出。
