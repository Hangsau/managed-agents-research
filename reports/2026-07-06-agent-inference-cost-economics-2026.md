# 研究報告：AI Agent Inference Cost Economics — 2026 H1 從「砸 GPU」到「聰明花錢」

**日期**：2026-07-06
**來源數**：14 | **標籤**：#cost-economics #inference-scaling #adaptive-compute #routing-cascade #speculative-decoding #agent-reliability #token-budget #compaction

---

## 1. The Problem

2025-2026 AI agent 落地最致命的一句話：**「能跑 ≠ 跑得起」**。

把一個 multi-step tool-use agent 從 demo 推到 production，token 支出會在三個維度同時爆炸：

1. **垂直擴張（per-step compute）**：ReAct / Plan-and-Execute 每步都打一次完整 LLM inference，瀏覽器 agent 的截圖 + DOM + history 動輒 8k-30k tokens。Self-consistency、ToT、multi-agent debate 還會在同一步再乘 4-16 倍 sampling。
2. **水平擴張（per-rollout cost）**：self-consistency、MCTS、AlphaEvolve 一類「inference-time scaling」方法在 batch 上把 N×compute 攤到 N 條 rollouts 上，換 +3-7% accuracy。
3. **重複執行（per-task rerun）**：同一個 workflow 重跑 100 次，每次都讓 LLM 「重新推理」——這個現象被 Chundru (Selfotix) 命名為 **Rerun Crisis**，5 步 workflow × 500 次 rerun = $150 inference cost（arXiv:2604.09718）。

更糟的是，2025 末的「o1-style reasoning + long CoT」熱潮把這三個維度**同時放大**。2026 H1 出現了清楚的轉向：

| 舊範式（2024-2025） | 新範式（2026 H1） |
|---|---|
| 固定 model + 固定 sampling budget | Unified Inference Scaling：joint routing + TTS |
| 每步 greedy / fixed-k self-consistency | **Per-step adaptive compute**（agreement-based, RL-trained） |
| 連續 LLM call loop（ReAct） | **Compile-and-Execute**（一次推論 → JSON blueprint → deterministic runtime） |
| Token-level speculative decoding（要 shared vocab） | **Response-level speculative cascade**（跨 provider、不需 vocab） |
| Stateless inference（每 turn 重算整段 prompt） | **Stateful KV cache + radix prefix**（O(nₜ) → O(Δₜ)） |
| 「Context compaction 為節省 token」 | 「Compaction 是 governance 風險，需 pinning」 |

**為何現在重要**：根據 Show HN 上的 `ccusage`、`cc-lens`、`wlog` 等工具在 HN 的發布密度，光是 Claude Code 社群就出現「**tokenmaxxing**」一詞（2026-05-14 `cc-ledger` 推出時的用語），描述 dev 開始把 token 當 KPI 監控、會用 token-observability 工具主動削減單次 session 的開銷。這是一個訊號——AI agent 的**成本可觀測性**已經從工程師的內部痛點變成了一個公開社群運動。

---

## 2. Core Mechanism

把 2026 H1 的所有「agent 成本經濟學」方法收斂成 **6 個獨立但可疊加的 knob**，每個 knob 對應不同的失敗模式。

### Knob A：Adaptive Per-Step Compute（TrACE, SR²AM）

**TrACE**（Stanford, arXiv:2604.08369, 2026-04）是最務實的 adaptive-compute 控制器：

```
At each timestep t:
    candidates_t = sample_n(model, context_t, k=small_batch)   # e.g. k=4
    agreement = mode(candidates_t) / len(candidates_t)
    if agreement >= τ_high:
        commit(mode(candidates_t))                              # skip extra rollouts
    elif agreement <= τ_low AND n_sampled < cap:
        candidates_t += sample_n(model, context_t, k=more)
        commit(mode(candidates_t))
    else:
        commit(mode(candidates_t))
```

關鍵洞察：**「模型自己對下一步的共識程度」就是 step-level 難度的 free signal**。TrACE 在 Qwen 2.5 3B (CPU) 上：
- TrACE-4 = SC-4 accuracy，**33% 較少 LLM calls**（GSM8K）、**39% 較少**（MiniHouse）
- TrACE-8 = SC-8 accuracy，**55-65% 較少 calls**

完全 training-free、no verifier、no labels。對 CPU/deploy-Qwen3 部署的 firn 風格場景特別值。

**SR²AM**（CMU IFM, arXiv:2605.22138, 2026-05）走更激進的路：把 CoT 內部拆成 **System I（reactive） / System II（simulative w/ world model） / System III（self-regulation configurator）** 三個 stage，學出「該不該呼叫 planner、planner 該推多遠」。v1.0-30B 用 **25.8–95.3% 較少 reasoning tokens**，accuracy 仍打得贏 685B-1T 同類系統。

### Knob B：Unified Routing × TTS（UniScale）

**UniScale**（arXiv:2605.30898, 2026-05）把之前互相獨立的兩個 knob 統一：
- **Model routing**：在 {0.6B, 1.7B, 4B, 8B, 14B} 間切換（coarse-grained）
- **Test-time scaling (TTS)**：固定 model 下調整 sampling / budget（fine-grained）

過去論文都把它們當 orthogonal。UniScale 用 **contextual multi-armed bandit + LinUCB** 學一個 joint policy：對每個 query 同時決定「用哪個 model」+「sample 多少次」。論文的 Figure 1 顯示 routing-only、TTS-only、UIS 三條 Pareto curve 上 **UIS 全面 dominated**，且在高 dynamic inference 環境（query distribution shift）下穩健得多。

對 firn 的直接意義：Hermes Agent 的 `hermes models` routing 如果只 routing 不 TTS，永遠會浪費一半 budget。

### Knob C：Co-Failure Ceiling — 為何「更多 model ensemble」其實不划算

**KAIKAKU 的 arXiv:2606.27288 (2026-06)** 是這次研究最反直覺、最重要的發現：

> 任何 routing / voting / cascade / mixture-of-agents policy，其 accuracy ceiling = **1 − β**，β 是「所有 model 全部答錯同一題」的比率。**而 field 慣用的 pairwise error correlation ρ 完全看不到 β。**

實證：在 67 個 frontier models、21 家 providers 的 pool 上，**tetrachoric-calibrated single-factor Gaussian copula 把 β 嚴重低估了 2.5 倍**（open-ended math β_observed = 0.052 vs β_predicted = 0.023；code β = 0.079；GPQA-Diamond free-response β = 0.127）。也就是說，當代模型在「hard query」上**一起錯**的比率遠比 router 預期的高。

這直接打臉 2025 流行的「mixture-of-agents = free accuracy」說法：
- 結論：「**diversity 來自不同 model 錯不同題，不是來自加更多 model**」
- 在 67-model pool 上，**single best model 經常打贏 learned router**，因為 query-level routing signal 弱於 β floor
- 高ρ Self-MoA（自家 ensemble）打不贏低ρ heterogeneous ensemble，**at matched quality**

對 agent system designer 的政策含意：**不要追求 N-way ensemble，而是追求異質化 query distribution 跟 hard-tail handling**。

### Knob D：Response-Level Speculative Cascade（RLM-Cascade）

PayPal 的 **RLM-Cascade**（arXiv:2606.22840, 2026-06）是目前最完整的 production 系統：

```
For each request:
    complexity_router(query) → {SKIPPED, DRAFT-VERIFY, ESCALATE}
    
    if SKIPPED:        # simple turn
        return DeepSeek(response)         # never call Opus
    
    if DRAFT-VERIFY:    # text-generation turn
        draft = DeepSeek(query)
        if verify_simple(draft) ≥ τ:
            return draft
        else:
            return Opus(draft + "enhance this")
    
    if ESCALATE:        # schema-critical tool-selection turn
        return Opus(query) directly
```

Production deployment on Claude Code workload (n=125)：
- **API cost ↓ 45.8%** vs direct Opus baseline
- **p50 latency: 2026 ms vs 3698 ms (1.83× speedup)**——降低 latency 的主因是 SKIPPED path dominate workload
- **20-task Code/Math/Instruct pass rate: 100% vs Opus 95%**（**比 baseline 還高**）
- 88.8% draft-use rate
- Open-sourced with live metrics dashboard + Prometheus endpoint

關鍵設計選擇：**bypass speculative pipeline for schema-critical tool-selection turns**——因為 tool call 必須 schema-perfect，被 speculative pipeline 漏改一個 brace 就 break client loop。

跟 NVIDIA Model-Optimizer（3129⭐）、vLLM SpecForge（969⭐）、SGLang EAGLE-3、DFlash diffusion-draft 這些 token-level SD 不一樣——RLM-Cascade 走 response-level，**不用 shared vocab、不需 model internals**，所以可以跨 provider（DeepSeek draft → Opus verify）。

### Knob E：Compile-and-Execute（O(MN) → O(1) for repeated workflows）

**Agentic Compilation**（Selfotix, arXiv:2604.09718 v2, 2026-04）正面對決「Rerun Crisis」：

```
Compile phase (once):
    DSM = DOM_Sanitizer(raw_html)               # strip noise, 85% reduction
    blueprint = LLM(DSM, user_intent) → JSON    # ONE inference call
    
Execute phase (N reruns):
    runtime = DeterministicExecutor(blueprint)
    for each rerun:
        result = runtime.run(browser_state)     # NO LLM call
        if divergence: re-compile or HITL patch
```

實證：
- 5-step workflow × 500 iterations：continuous agent = **$150**，caching = **$15**，**compile-and-execute = $0.10**
- Inference scaling 從 **O(M × N)** 降到 **amortized O(1)**
- Per-compilation cost = **$0.002-$0.092** across 5 frontier models
- Zero-shot compilation success：80-94%
- Modular JSON IR 允許「minimal HITL patching」把 reliability 拉到 ~100%

限制：blueprint 必須能 deterministic 化——如果 target web page 結構常變、user intent 模糊、需要 adaptive branching，就退化成 continuous agent。

### Knob F：Stateful KV Cache（O(nₜ) → O(Δₜ)）

**Stateful Inference**（LayerScale, arXiv:2605.26289, 2026-05）解決「multi-turn agent 90% prompt 重複」：

每個 turn，傳統 inference framework 重算整段 conversation prefix。Stateful 架構：
- Persistent KV cache 跨 turn 存活
- 只 ingest 新 token（delta）
- Radix prefix cache 跨 interleaved multi-agent traffic（透過 metadata-only sequence aliasing）
- Prompt-deterministic response cache（repeated prompt → GPU skip）
- Prompt-lookup speculative decoder（structured tool call）

實證 vs vLLM / SGLang：
- **6-turn agentic workflow：2.1× speedup per turn**
- **35-turn coding workflow：4.2× speedup median turn**
- End-to-end wall time ~½

對 multi-agent orchestration framework（如 LangGraph、CrewAI、firn 的 Kanban orchestrator）特別有影響——中間 agent 跟 worker agent 的對話高比例都是「同一個 context 換幾行 tool result」。

### Knob 0：Context Compaction 治理（不在 6-knob，但 cost 路徑必踩）

順著 Knob F 邏輯，context compaction 是省 token 的標準手段，但 **arXiv:2606.22528（Governance Decay, 2026-06）** 證明 compaction 同時是 silent safety failure surface：

- 7 models, 1323 episodes, ConstraintRot benchmark
- Compaction 後 violation 從 **0% 升至 30%**（最高 59%）
- Constraint 存活 → violation 0%；constraint 被吞 → violation 38%
- **Soft organizational policy decay 8.3×** hard safety norm
- Compaction-Eviction Attack：對手可以刻意 bias compaction 刪 constraint（0% → 65% violation）
- 修法：**Constraint Pinning**（training-free，< 0.5% token overhead）→ 還原 0% violation

對 firn：當我們做 context compression / distillation 時（cron、delegation、summarization），必須 pin 掉「operator policy」、「tool registry schema」、「cost guard」這幾類 standing constraints，不能讓 LLM 摘要器自由蒸發。

---

## 3. Why It Matters / Applications

把這 6 個 knob 串起來看，2026 H1 的 agent cost economics 有三個**結構性轉向**：

### 3.1 從「compute is cheap」到「compute is allocatable」

2025 的 chain-of-thought + self-consistency 典範默認「多算一點沒關係，反正 OpenAI / Anthropic 降價」。2026 H1 開始出現把「compute allocation」當 first-class design variable 的論文：

- **TrACE** 把 compute 視為可逐 step 動態調整的
- **SR²AM** 把 compute 視為可被學出 policy 的 configurator
- **UniScale** 把 compute 視為 routing × TTS 的 joint optimization space

這預示 production framework（LangChain、LlamaIndex、AutoGen）會開始內建 adaptive-compute controller，而非要求 dev 自己寫 loop。

### 3.2 從「inference is single-shot」到「inference is stateful / compiled / cascading」

- RLM-Cascade 在 PayPal production 把 agent coding cost 砍 45.8% 不是靠新 model，而是靠 **proxy-layer routing** + 跨 provider draft-verify
- Agentic Compilation 把 95% LLM call 蒸發掉，靠的是「**one-shot reasoning → deterministic execution**」
- Stateful Inference 把 90% per-turn cost 蒸發掉，靠的是 KV-cache persistence

換言之：**2026 H1 agent cost 最佳化最大的紅利不在 model 本身，而在 inference 架構層**。

### 3.3 從「token 當消耗」到「token 當資產」

- ccusage（ryoppippi, 845+⭐）、cc-lens、wlog、cc-ledger 這些工具進入 GitHub trending
- HN 開始出現「tokenmaxxing」這個 self-aware 的 dev 詞彙
- **Cost observability** 從內部 ops dashboard 變成公開社群運動

對工程團隊含意：agent 系統上 production 前必須先回答三個問題：
1. **Token observability**：每個 session 的 cost 分布、step-level breakdown、cache hit rate 是幾？
2. **Adaptive-compute policy**：哪些 step 該多算、哪些該少算、誰決定？
3. **Compaction safety**：context compression 怎麼 pin 安全 / governance constraint？

---

## 4. Limitations / Honest Assessment

### 4.1 論文普遍誠實揭露的限制

- **TrACE**：實驗只用 Qwen 2.5 3B 在 CPU。3B 是個極小模型，3B 上的「agreement signal」能不能 scale 到 70B+ / reasoning model 是 open question。論文明確說 *「we do not claim state-of-the-art accuracy」*。
- **UniScale**：LinUCB 在 dynamic environment 表現好，但 cold start 仍需 explore；對 latency-critical 應用，exploration cost 可能吃掉省下的。
- **RLM-Cascade**：只在 Claude Code workload（125 requests）上驗證。production-scale 統計顯著性弱；complexity_router 是 rule-based，跨不同 agent paradigm 的泛化性未知。
- **Agentic Compilation**：假設 workflow **structural** stable。如果 target DOM 經常變、user 經常改 intent、必須 adaptive branching，compile-then-execute 會反覆 re-compile，最後退化回 continuous agent。
- **Stateful Inference**：persistent KV cache 對**single-tenant** 有效。multi-tenant 隔離 / privacy 是 deployment 時必須額外設計的。
- **Co-Failure Ceiling**：論文的 β 估算用 single graded query set + Clopper-Pearson bound。**樣本數小的話 CI 寬到沒實用價值**（GPQA-Diamond free-response 那個數字就要小心讀）。論文的 Clopper-Pearson bound 給的是 *upper envelope*，不是 guaranteed gain。

### 4.2 我們的獨立評估

這批研究有幾個**集體盲點**：

1. **Workload bias**：所有 production 案例（Claude Code、PayPal、Stateful Inference benchmark）都是 **coding / structured-tool-call agent**。對 open-ended chat agent、creative writing agent、研究 agent（long-form reasoning）是否同樣有效未知。
2. **Reasoning model gap**：o1 / o3 / DeepSeek-R1 類 reasoning model 已經把「per-step compute」大幅拉高。TrACE 的 agreement signal 在 reasoning model 上是 *更有力* 還是 *更不穩定*？論文中完全沒測。
3. **Co-failure 論文的悖論**：論文的結論是「不要做 ensemble」。但 production 上 ChatGPT / Perplexity / Cursor 都在用 ensemble 跟 multi-model routing——它們用得很差嗎？還是論文樣本只反映 static query set，沒反映真實 interactive 場景的 feedback loop？
4. **Compile-and-execute 的 scalability**：5-step workflow 好 compile，但 production agent 常是 50-200 step multi-day 的 coding session。「one-shot compilation」對這種 long-horizon task 還適用嗎？論文沒討論。
5. **Compaction 治理研究的 bias**：Governance Decay 只測了 7 個 models，且 ConstraintRot 是 synthetic benchmark。真實 enterprise policy 多複雜？沒有 external validation。
6. **付費 API 依賴**：UniScale / RLM-Cascade / Stateful Inference 都假定能自由組合多個 frontier API（Opus + DeepSeek + Qwen）。**對單一 provider / on-prem / air-gapped 部署的 firn-style setup，這些方法都不直接適用**——需要本地化重設計。

### 4.3 取捨框架

| 場景 | 推薦主軸 | 理由 |
|---|---|---|
| Coding agent, multi-turn, schema-heavy | **RLM-Cascade + Stateful Inference** | tool call 90% structural，cache hit rate 高 |
| Web automation, 5-20 step, 重複跑 | **Agentic Compilation** | 把 inference 從 O(MN) 壓到 O(1) |
| Reasoning-heavy research agent | **TrACE + UniScale** | 逐 step adaptive compute；hard step 用大 model，easy step 用小 model |
| Multi-agent orchestration（orchestrator + workers） | **Stateful Inference + Compaction Pinning** | prefix cache + 治理約束不要被壓縮掉 |
| Free-tier / single-model 部署 | **TrACE only + semantic cache** | 不用 multi-model 也能省 |
| 高 stakes enterprise workflow | **Co-Failure Ceiling 評估 + human-in-loop** | 不要相信 learned router，先量 β 再決定要不要 ensemble |

---

## 5. Actionable for Our Projects

### 5.1 firn（火速可做）

| 行動 | 模組 | 難度 | 預估省 |
|---|---|---|---|
| **Token observability dashboard**（類似 `ccusage`） | Kanban worker logs + cron digest | TRIVIAL | n/a（visibility） |
| **Per-step adaptive compute controller**（TrACE 風格） | Kanban worker loop，sampling 時加 agreement check | MODERATE | 30-65% LLM calls on multi-step tasks |
| **Compaction Pinning**：compression / summarization 時 pin operator policy / tool schema / cost guard | Context-distiller + skill loader | MODERATE | 治理：避免 governance decay |
| **Persistent KV cache 跨 cron session**（如果用 self-host） | Inference gateway 層 | HARD（需要 infra 投入） | 2-4× per-turn speedup |
| **Per-task complexity classifier**（rule-based，先用 token-length + tool count） | Pre-router before model selection | TRIVIAL | 10-30% cost depending on distribution |

### 5.2 Hermes Agent CLI / 自家框架

| 行動 | 模組 | 難度 |
|---|---|---|
| **`hermes models route` command**：per-query routing across models | Model registry | MODERATE |
| **`hermes run --adaptive-compute`** flag：TrACE-style controller | Loop executor | MODERATE |
| **`hermes compile`**（web automation 場景）：one-shot → JSON blueprint | Skill registry | HARD |
| **`hermes cache stateful`**：persistent KV cache | Inference gateway | RESEARCH-ONLY |

### 5.3 需要付費 API？

| 方法 | 需要多 provider？ | 費用 |
|---|---|---|
| TrACE | 否，single model OK | 0（省 30-65%） |
| UniScale | 是（multi-model pool） | 需要 LinUCB infra + 至少 3 model tier |
| RLM-Cascade | 是（cheap draft + capable verify） | 需要 cheap model（如 DeepSeek）+ Opus 級 verify |
| Agentic Compilation | 否 | 0（省 95%） |
| Stateful Inference | 否 | GPU/VRAM cost |
| Co-Failure β measurement | 是（需要 graded query set across models） | 一次性 |

對 firn / Hermes：**TrACE + Agentic Compilation + Compaction Pinning 是 free-tier-friendly**，應該最優先實作。

---

## 6. Follow-up Questions

1. **Reasoning model 上的 TrACE**：o1 / o3 / R1 風格的 reasoning 過程會不會讓「agreement signal」失效？因為 reasoning chain 本身就內建 diverse alternatives，agreement 變低但都是同一個 final action？
2. **Co-Failure Ceiling 在 interactive setting**：論文的 β 來自 static graded query。真實 interactive agent session（有 tool feedback、retry、user clarification）會降低還是提高 β？
3. **Adaptive compute 的 fairness**：當 query 來自弱勢用戶（low-resource language、accessibility need），agreement-based 控制器會不會系統性低估他們的「難度」？
4. **Compile-and-Execute 對 long-horizon**：50-200 step coding session 能不能拆成多個 compile-and-execute chunks？chunk boundary 怎麼決定？
5. **Stateful KV cache 的 privacy boundary**：跨 session 的 persistent cache 在多租戶 deployment 時怎麼保證 isolation？
6. **Compaction governance 的 attack surface**：Governance Decay 提到的 Compaction-Eviction Attack 對 production agent（特別是用第三方 model 做 compaction 的）威脅多大？
7. **Beta-aware router**：能不能用論文的 Clopper-Pearson β bound 來設計 router，知道哪些 query 是「β floor」決定了天花板，乾脆 escalate 到 human？

---

### 原始來源

[arXiv:2605.30898 — UniScale: Adaptive Unified Inference Scaling](https://arxiv.org/abs/2605.30898) — 論文 — HIGH — Joint routing + TTS 用 LinUCB 學，UIS Pareto-dominated routing-only / TTS-only

[arXiv:2604.08369 — Don't Overthink It: TrACE (Trajectorical Adaptive Compute via agrEement)](https://arxiv.org/abs/2604.08369) — 論文 — HIGH — Training-free per-step adaptive-compute via inter-rollout agreement，33-65% 較少 calls

[arXiv:2605.22138 — Efficient Agentic Reasoning Through Self-Regulated Simulative Planning (SR²AM)](https://arxiv.org/abs/2605.22138) — 論文 — HIGH — System I/II/III 三階段；v1.0-30B 用 25.8-95.3% 較少 reasoning tokens 打贏 685B-1T 系統

[arXiv:2606.27288 — When Does Combining Language Models Help? A Co-Failure Ceiling](https://arxiv.org/abs/2606.27288) — 論文 — HIGH — 67 models 上證明 ρ 看不到 β；router/vote/cascade ceiling = 1−β；多 ensemble 反而打不贏 single best

[arXiv:2606.22840 — RLM-Cascade: Response-Level Speculative Decoding](https://arxiv.org/abs/2606.22840) — 論文 — HIGH — PayPal production，Claude Code workload 省 45.8% cost、p50 latency 1.83× speedup

[arXiv:2604.09718 — Agentic Compilation: Mitigating the LLM Rerun Crisis](https://arxiv.org/abs/2604.09718) — 論文 — HIGH — Compile-and-Execute 把 5×500 step workflow 從 $150 壓到 $0.10

[arXiv:2605.26289 — Stateful Inference for Low-Latency Multi-Agent Tool Calling](https://arxiv.org/abs/2605.26289) — 論文 — HIGH — Persistent KV cache + radix prefix；2.1-4.2× per-turn speedup vs vLLM/SGLang

[arXiv:2606.22528 — Governance Decay: How Context Compaction Silently Erases Safety Constraints](https://arxiv.org/abs/2606.22528) — 論文 — HIGH — Compaction 後 violation 0%→30%；Constraint Pinning training-free 還原 0% violation

[arXiv:2605.01566 — Multi-Agent Reasoning Improves Compute Efficiency](https://arxiv.org/abs/2605.01566) — 論文 — MEDIUM — Pareto-front 分析 self-consistency/refinement/debate/MoA；MoA 比 self-consistency 省 2.7% 點 accuracy / 等 compute

[arXiv:2606.18967 — EfficientRollout: System-Aware Self-Speculative Decoding for RL Rollouts](https://arxiv.org/abs/2606.18967) — 論文 — MEDIUM — Self-SD + system-aware toggle policy；rollout latency ↓19.6%、end-to-end ↓12.7%

[arXiv:2606.07710 — WhiFlash: Speculative Decoding with Token-Level Cross-Paradigm Routing](https://arxiv.org/abs/2606.07710) — 論文 — MEDIUM — AR-draft × diffusion-draft 動態切換，throughput +37-70%

[Sebastian Raschka — Categories of Inference-Time Scaling (Jan 2026)](https://magazine.sebastianraschka.com/p/categories-of-inference-time-scaling) — 部落格 / Survey — MEDIUM — 主流 ITS 方法分類：CoT、self-consistency、best-of-N、verifier sampling、self-refinement、search over paths

[GitHub: NVIDIA/Model-Optimizer (3129⭐)](https://github.com/NVIDIA/Model-Optimizer) — 程式庫 — HIGH — Unified SOTA optimization 包含 speculative decoding / quantization / distillation / pruning

[GitHub: vllm-project/speculators (586⭐)](https://github.com/vllm-project/speculators) — 程式庫 — HIGH — Speculative decoding algorithm library for vLLM

[GitHub: sgl-project/SpecForge (969⭐)](https://github.com/sgl-project/SpecForge) — 程式庫 — HIGH — Train SD models for SGLang serving

[HN: Show HN: ccusage — Claude Code token usage from JSONL (2025-07)](https://github.com/ryoppippi/ccusage) — 社群討論 — MEDIUM — Token observability 進入 dev 主流視野

[HN: cc-ledger — Claude Code cost observability to prevent tokenmaxxing (2026-05-14)](https://github.com/delta-hq/cc-ledger) — 社群討論 — MEDIUM — 「tokenmaxxing」進入詞彙，cost observability 成為 dev 自覺 KPI

[arXiv:2606.27243 — NOVA: Verification-Aware Agent Harness (2026-06)](https://arxiv.org/abs/2606.27243) — 論文 — MEDIUM — Industrial recommender system 的 verification-aware agent，architecture evolution cost 控制案例

---

**下一個工作日排程執行本指令。**