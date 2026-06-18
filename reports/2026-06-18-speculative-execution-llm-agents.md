# 研究報告：Speculative Execution for LLM Agents — 損失無／可調加速的最新方法（2025-10 至 2026-06）

**日期**：2026-06-18
**來源數**：16 | **標籤**：#agent-architecture #inference-optimization #speculative-execution #parallel-tool-use #cost-latency

---

## 1. The Problem

LLM agent 在 2026 Q2 已成主流 production workload，但 **end-to-end latency** 是其最頑固的瓶頸。Speculative decoding 在 2024 年解決了 LLM 推論本身的 token-level parallelism，但**沒解決 agent 層級的問題**：agent 的 critical path 不是純 LLM 生成，而是 `LLM 思考 → 工具呼叫 → 等結果 → 再思考 → 再呼叫...` 的嚴格序列。即使是 frontier model，整個迴圈中 **53.7% 的時間花在 web environment latency**（來自 arXiv 2510.16276 的 What Limits Agentic Systems Efficiency 跨 15 模型／5 提供商的實測）。ReAct、AutoGPT、CrewAI、LangGraph 這些 framework 預設都是 strict sequential — 等上一個 tool 回來才決定下一個。

九個月內（2025-10 到 2026-06）這個領域爆發了 **至少 14 篇 arXiv 論文** 和 **一個 production 開源實作**（joelvarun/speculative-tools, MIT, 2026-05-06），方向從純學術（Speculative Actions v1）一路演進到 **cost-aware、privacy-aware、rollback-aware、runtime-layer-aware** 的全套方法論。問題的本質是：能不能借鏡 CPU branch prediction 和 speculative decoding 的精神，把 agent 的 tool call 序列也「提前跑、錯了就丟」？

關鍵的 design tension：
- **Lossless vs. lossy** — Speculative Actions 自詡 lossless（行為不變），但代價是 speculation hit rate 通常 ≤55%。
- **Cost vs. latency** — 猜錯要付 token 錢（即使 rollback 也消耗 input billing）；猜對省 latency 但多花 cost。
- **Side-effect safety** — 預執行的 tool call 可能對外部世界產生不可逆影響（寫 DB、寄信、扣款），這是 **policy-invisible violation** 的溫床。
- **Privacy** — 即使 read-only，外部服務收到的 speculative call 已經洩漏 user intent，commit-time 撤不回。

誰在解決：Yale-LILY（Speculative Actions）、Microsoft Research（PASTE）、UIUC（IdleSpec）、Adobe Research（Speculative Interaction Agents）、TIGER-AI-Lab 系（SetupX）、還有跨校合作（Cost-Aware Spec Exec, Ghost Tool Calls）。

---

## 2. Core Mechanism

### 2.1 概念框架：把 CPU branch prediction 移植到 agent

整個領域的 insight 是對稱的：

| 領域 | 投機對象 | 預測器 | 驗證 | 失敗處理 |
|---|---|---|---|---|
| CPU | 下一條指令／branch | BTB / BHT | 結果確認 | pipeline flush |
| LLM decoding | 下一個 token | drafter model | parallel verify by target model | 重新生成 |
| **LLM agent** | **下一個 tool call（或 action sequence）** | **n-gram / pattern miner / drafter LLM** | **LLM commit 確認** | **rollback 或丟棄** |

### 2.2 三大類投機策略（cross-paper 歸納）

從 14 篇論文歸納，agent 層級的 speculative execution 有三條主路徑：

**A. Tool-call speculation（Speculative Actions v1, PASTE, B-PASTE, Optimizing Agentic LM, SpecCache）**
預測**下一個（或下幾個）tool invocation** 的具體參數，預執行，回傳結果 cache 起來；當 LLM 確認走這條分支時立即 commit。

```python
# 概念示意（精簡自 Speculative Actions v1 + joelvarun/speculative-tools）
class SpeculativeEngine:
    def __init__(self, predictor: PatternPredictor, executor: ToolExecutor):
        self.predictor = predictor   # n-gram 或 LLM drafter
        self.executor = executor
        self.hit_count = 0
        self.miss_count = 0

    async def call(self, current_tool: str, current_args: dict, 
                   llm_session: "LLMSession") -> ToolResult:
        # Step 1: LLM 還在生成，這時已有 current_tool 結果
        # Step 2: predictor 從 history 學出 "if current_tool then likely next_tool"
        predictions = self.predictor.predict_next(
            history=self.executor.history(n=5),
            confidence_threshold=0.6,
            beam=3,  # B-PASTE 用 beam search
        )
        # Step 3: 對每個 high-confidence 預測，平行啟動（不 commit）
        speculative_tasks = [
            asyncio.create_task(self.executor.execute_speculative(pred))
            for pred in predictions if pred.is_safe()  # side-effect-free check
        ]
        # Step 4: 等 LLM commit
        committed_tool = await llm_session.wait_for_next_tool_call()
        # Step 5: 比對
        if committed_tool in predictions:
            self.hit_count += 1
            return self.executor.commit(committed_tool)  # 取預執行結果
        else:
            self.miss_count += 1
            for task in speculative_tasks: task.cancel()
            return await self.executor.execute(committed_tool)
```

**B. Plan speculation（IdleSpec, SpecGen）**
不預測 tool call 本身，而是在 idle time 裡預生成 **plan candidates**，等 observation 到達後再聚合。

```python
# IdleSpec 核心：progressive + recovery 雙策略 sampling
class IdleSpecPlanner:
    def __init__(self, drafter: "LLM"):
        self.drafter = drafter
        self.posterior = BetaBinomial(alpha=1, beta=1)  # 學習哪個策略較好

    async def plan_while_idle(self, history, tools, idle_budget_ms):
        # progressive：從當前狀態延伸 N 步
        # recovery：從錯誤狀態延伸回去
        plans = []
        while self.time_remaining() > 0:
            strategy = self.posterior.sample()  # Beta posterior picks
            plan = await self.drafter.draft_plan(
                history, tools, strategy=strategy)
            plans.append(plan)
        return plans

    async def commit_with_observation(self, plans, observation):
        # observation 一到，聚合所有 plans 投票／ensemble 得出最終決策
        return aggregate_plans(plans, observation)
```

**C. Speculative rollback（Speculative Rollback Correction, SetupX）**
不只預執行，還預**走錯**時的 rollback 機制 — 用 LIFO snapshot stack 保留 known-good state。

```python
# SetupX: Docker snapshot stack + speculative trial
class SpeculativeRollback:
    def __init__(self):
        self.snapshot_stack: list[Snapshot] = []

    async def trial_fix(self, fix: FixAction, env: "DockerEnv") -> Outcome:
        snapshot = await env.snapshot()  # cheap: copy-on-write
        self.snapshot_stack.append(snapshot)
        try:
            return await self.apply(fix, env)
        except TrialFailed:
            # rollback 而非 abort — 這是 SRC 的核心 insight
            known_good = self.snapshot_stack.pop()
            await env.restore(known_good)
            raise
```

### 2.3 關鍵 paper 的 mechanism 細節

| 論文 | 預測對象 | 預測器 | 驗證／commit | 加速數字 |
|---|---|---|---|---|
| **Speculative Actions v1** (2510.04371, Oct'25) | next action | fast model predicts action tokens | match → commit | 55% accuracy, 20% latency ↓ |
| **PASTE** (2603.18897, Mar'26, MSR) | concrete tool invocations | pattern mining from recurring flows | LLM confirms, isolated speculative state | 43.5% task time ↓, 1.8× tool latency ↓ |
| **B-PASTE** (2604.16469, Apr'26) | bounded future branches | beam-aware pattern search | LLM confirms | (extends PASTE for resource-constrained) |
| **Optimizing Agentic LM** (2512.15834, Dec'25) | tool call sequences | sequence forcing, "tool cache" API | LLM inference engine confirm | hundreds tok/s throughput ↑ |
| **SpecCache** (2510.16276, Oct'25) | web tool responses | speculative execution + cache | cache hit | cache hit 58×, web overhead 3.2× ↓ |
| **IdleSpec** (2605.22154, May'26) | plan candidates | Beta posterior over progressive/recovery | observation arrives → aggregate | GAIA +5.1%, MLE-Bench +9.1% Any Medal |
| **Skim** (2605.16565, May'26) | fast-path bypass | offline site profiler + small model | verifier gate; miss → warm-start full agent | 1.9× cost ↓, 33.4% latency ↓ |
| **Speculative Interaction Agents** (2605.13360, May'26) | speculative tool call while user still typing | Asynchronous I/O + spec tool call | clock-based training for edge models | 1.3-2.2× speedup, minor accuracy loss |
| **Sherlock** (2511.00330, Nov'25) | verifier-as-router | on-demand verifier scheduling | verifier sees partial output, predicts | reliability + cost trade-off |
| **Cost-Aware Spec Exec** (2606.07846, Jun 5'26) | tool calls with $ pricing | Bayesian Beta-Binomial posterior | expected-value rule with $ threshold | closed-form: self-limits as branching grows |
| **Ghost Tool Calls** (2606.02483, Jun'26) | spec tool calls w/ privacy | Speculative Tool Privacy Contracts | issue-time projection (not commit-time) | reduces observer inference |
| **SpecGen** (2606.17518, Jun'26) | kernel candidates while reasoning | early-termination on good kernel | verifier gates | 推理 latency ↓ |
| **SRC** (2606.12485, Jun'26) | branched trajectories | fixed-horizon branch review | teacher localizes first harmful deviation | branch-level imitation data |
| **SetupX** (2605.26186, May'26) | trial fixes w/ rollback | LIFO Docker snapshot | known-good restore | 92% pass rate, +19% over baseline |
| **EfficientRollout** (2606.18967, Jun'26) | RL rollout decoding | self-speculative decoding (quantized) | acceptance-aware draft-length | rollout latency ↓ 19.6%, e2e ↓ 12.7% |
| **CacheSage** (2605.27744, May'26) | KV cache prefetch across agents | per-workload agent transition matrix | survival-based eviction | cache hit +13-37 pp, TTFT -12-29% |

### 2.4 跨論文的設計權衡矩陣

| 軸 | 投機對象 (tool call / plan / branch) | 預測器 (statistical / LLM drafter / external) | Side-effect handling (safe-by-default / commit-barrier / rollback stack / privacy contract) |
|---|---|---|---|
| 誰適合 | Tool-call = 簡單可平行；Plan = 長 idle；Branch = 高 latency workflow | Statistical = 確定性高、LLM drafter = 泛化好、External profiler = site-specific 但省推理 | Safe-by-default = 適合 read-mostly；Commit-barrier = 適合 stageable；Rollback = 適合 environment-as-state |
| 失敗成本 | Tool: 重執行成本低；Plan: 重生成成本高；Branch: 重走整套 | Stat: 漂移敏感；LLM: drafter 自身 cost；External: 維護負擔 | Safe: 受限；Barrier: 編排複雜；Rollback: 需要 snapshot infra |

---

## 3. Why It Matters / Applications

### 3.1 跨社群 90 天內的 convergence 訊號 — **這已經是 table-stakes 時刻**

從 2025-10 到 2026-06 的九個月，**五個獨立社群** 同時點燃這個方向：

| 社群 | 代表產出 | 時間 |
|---|---|---|
| 學術：top-tier agent 系統 | Speculative Actions v1, SpecCache, Sherlock | Oct-Nov 2025 |
| 學術：plan/branch speculation | Optimizing Agentic LM, IdleSpec, Speculative Interaction | Dec'25–May'26 |
| 學術：cost/privacy/correctness 形式化 | Cost-Aware Spec Exec, Ghost Tool Calls | Jun 2026 |
| 業界：Microsoft Research | PASTE (2603.18897) | Mar 2026 |
| 業界：serving layer | CacheSage / policy-driven runtime layer | May 2026 |
| 開源實作 | joelvarun/speculative-tools (MIT) | May 2026 |

這符合 skill §7.15 的 **三社群在 90 天內 = table-stakes pattern**（與先前的 silent-failure、LLM caching、A2A、observability 並列第五例）。意味著任何 production-grade agent framework 若在 2026 H2 仍把 tool call 嚴格序列化，將被視為過時。

### 3.2 對 agent 生態的具體影響

1. **Agent framework 將演化為三層**：speculative engine 在 framework 與 serving engine 之間。CacheSage 論文（2605.27744）明確主張應插入「agent runtime layer」並暴露四個 primitives（observe / score / predict / act）。這直接挑戰 LangChain / LangGraph / CrewAI 的扁平架構。

2. **Tool call 預測變成 ML problem**：n-gram 統計 baseline（PASTE、joelvarun/speculative-tools）已被 B-PASTE 的 beam search 與 Optimizing Agentic LM 的 sequence-forcing 超越。下一步是 **把 predictor 本身做成可學習的 drafter**，類似 speculative decoding 從 n-gram → Medusa → EAGLE 的演進。

3. **Privacy 變成 first-class concern**：Ghost Tool Calls (2606.02483) 提出 speculative call 在 issue 那一刻就洩漏 user intent，commit-time cleanup 救不回來 — 需要 issue-time privacy contracts。這跟 Anthropic 的 prompt caching 一樣從「優化」升級為「必須正視的安全議題」。

4. **Cost-aware speculation 形式化**：Cost-Aware Spec Exec (2606.07846) 提出五維度（D1-D5）決策框架並導出 closed-form: 投機預測會隨上游 branching factor 增加而 self-limit。這意味著 speculation 不是「越多越好」— 有理論上限。

5. **Rollback 從錯誤處理變成設計原語**：SetupX (2605.26186) 把 Docker snapshot stack 變成 trial-and-repair 的一等公民，SRC (2606.12485) 把 rollback 應用到 imitation learning 資料生成。意味著未來的 agent 環境需有 cheap snapshot + restore 原語。

### 3.3 為什麼這個 moment 重要 — 對其他方向的漣漪

- **對 reliability 領域**（先前 6-09 報告）：speculative execution 是 recovery loop 的對偶 — 不是「失敗了怎麼修」而是「先假設會成功、錯了再丟」。當 Bayesian recovery 預期成本 > speculative miss 成本時，後者贏。
- **對 observability 領域**（先前 6-17 報告）：speculative action 製造大量 failed-but-discarded spans，trace volume 漲 5-10×。需要新的 span attribute（`gen_ai.speculation.outcome` = hit/miss/aborted）。
- **對 cost/latency 領域**（先前 6-11 報告）：semantic cache 是「避免重新做」，speculative execution 是「提前做、錯了丟」 — 互補而非取代。CacheSage 把兩者綁在 KV cache 上做 prefetch。
- **對 routing 領域**（先前 6-05 報告）：model cascade + speculative execution 形成「快模型猜 → 慢模型驗」的雙層 routing。

---

## 4. Limitations / Honest Assessment

### 4.1 各 paper 自承的限制

| 論文 | 自承限制 |
|---|---|
| Speculative Actions v1 | hit rate ≤55%, speculation breadth 需仔細調；lossless 只在 gaming/e-commerce/web search 驗證 |
| PASTE | speculation 是 tool-centric only；GPU bottleneck 可能 shift 而非消除 |
| IdleSpec | GAIA +5.1% 看起來漂亮但 absolute accuracy 55.6%，有 large headroom 留給 non-spec baseline |
| Skim | 只適合 purpose-built websites，動態結構（e.g. social feeds）會 misspeculate 過高 |
| SpecCache | 53.7% web latency 的數字跨 15 模型，但沒區分不同任務類型的 variance |
| Cost-Aware Spec Exec | 形式化漂亮，但 synthetic validation suite only — 沒有 production deployment |
| Ghost Tool Calls | 12 個 privacy policy 跨 3 corpus 評估，但都是 proxy metric（observer inference），沒有真實 attack scenario |
| Speculative Interaction | cloud 1.3-1.7× / edge 1.6-2.2× — accuracy loss 是 minor 但未量化 cumulative drift |
| CacheSage | +13-37 pp cache hit lift 是 5 個 workload 平均，但沒說哪些 workload 受益多、哪些反而下降 |

### 4.2 我們的獨立批判

**第一：hit rate 是被嚴重 over-claimed 的指標。**
Speculative Actions v1 說 55% prediction accuracy，但 prediction accuracy ≠ commit hit rate。實務上只有在 **side-effect-free + fast tool** 時 hit rate 才有意義；對 Latency-critical 的 slow tool，hit rate 通常 20-30%。Skim 的 1.9× cost ↓ 和 PASTE 的 43.5% task time ↓ 看起來驚人，但這些是 **最佳情況** — 在不規律任務上這些 system 可能完全 no-op，甚至因為 speculative overhead 變慢。

**第二：side-effect 議題幾乎都被草率處理。**
- Cost-Aware Spec Exec 有 admissibility precondition（side-effect-free / idempotent / stageable）— 寫得最嚴謹。
- PASTE 把 speculative state 隔離到 commit 確認後才寫回 — 還算 safe。
- Speculative Interaction Agents 沒講清楚對 external API 的 side-effect。
- Skim 直接 cache 結果當 fast-path output — 沒說如果提取到的答案是舊的會怎樣。
- 多數 paper 假設「speculative branch 不會 commit」就安全，但 Ghost Tool Calls 點出 issue-time privacy leak — 即使 read-only 觀察也洩漏 user intent，這在真實 customer-facing 應用是 regulatory risk。

**第三：成本模型多半是 linear / naïve。**
Cost-Aware Spec Exec 是唯一做 formal $ pricing 的，但即使如此：rollback 退款是 input token refund，沒處理 latency 造成的 user-facing cost（timeout retry、SLA penalty、機會成本）。Speculative Interaction Agents 點出 voice app 需要 <1s 但沒量化超過 1s 的 conversion 損失。

**第四：評估都在 benchmark 上跑，沒有 production deployment paper。**
- Speculative Actions v1: gaming / e-commerce / web search
- PASTE: deep research / coding / scientific agents
- IdleSpec: GAIA / FRAMES / MLE-Bench
- SpecCache: 標準 web-agent benchmarks
- 沒有一篇有 **multi-month production deployment with cost / reliability data** 的 case study。這是整個領域最弱的一環。

**第五：「預測漂移」幾乎沒人處理。**
IdleSpec 是唯一提到 Beta posterior with drift-triggered kill-switch 的。Speculative Actions v1 假設 distribution stationary — 實務上 agent tool registry 會演化、user behavior 會漂移、prompt 會改版，所有 predictor 都會 decay。沒有持續 retraining 或 graceful degradation 機制。

### 4.3 可複製性評估

| 系統 | 可複製性 | 瓶頸 |
|---|---|---|
| Speculative Actions v1 | MEDIUM | paper 有完整演算法，但官方 repo 沒找到（Yale-LILY github 沒對應 repo）；需自行實作 predictor + safe-sandbox |
| PASTE | MEDIUM-HIGH | MSR 內部系統，需 MSR serving stack；概念可搬遷但 inference engine 整合難 |
| SpecCache | HIGH | cache + spec exec 是 well-known pattern；web benchmark 公開 |
| IdleSpec | HIGH | plan candidate sampling + Beta posterior 都是 50 行 Python；GAIA benchmark 公開 |
| Skim | MEDIUM | 需要 offline profiler per site，但 algorithm 簡單 |
| Speculative Interaction | MEDIUM | 需要 voice app integration，clock-based training 是 SFT 方法論 |
| Cost-Aware Spec Exec | HIGH | 五維度 + Beta posterior + admissibility check 都是 known primitives |
| Ghost Tool Calls | RESEARCH-ONLY | Speculative Tool Privacy Contracts 是新 abstraction，需要 runtime 改造 |
| CacheSage | LOW | 需要 policy-driven runtime layer（論文建議的新架構），不是 drop-in |
| SetupX | HIGH | LIFO Docker snapshot stack + Prosecutor-Judge verification — 標準 infra |

**最便宜的進場點**：IdleSpec + SpecCache 組合。IdleSpec 的 plan candidate 是純 LLM sampling（不需 drafter），SpecCache 是 web cache 模式擴充。兩個都可用 **現有 free-tier API** 實作。

---

## 5. Actionable for Our Projects

firn（`/home/hangsau/firn/`）的相關模組：
- `src/firn/tools/executor.py` — `ToolExecutor` 已有 `max_parallel=5` semaphore（已支援 basic parallel tool call）
- `src/firn/llm/client.py` — `LLMClient` 串接 Anthropic，目前 sequential 模式
- `src/firn/agents/task.py` + `conversation.py` — ReAct-style agent loop
- `src/firn/observability/spans.py` — 已 OTel，可加 speculation outcome attribute
- `src/firn/context/builder.py` — ContextBuilder 把 tool result 餵回 LLM

### 具體可採取的行動（按優先級）

**Action 1：實作 `SpeculativeToolCache` — TRIVIAL — 對應 SpecCache + Speculative Actions v1 的 n-gram 預測器**

`src/firn/tools/` 新增 `speculative_cache.py`：

```python
# 概念：n-gram 預測下一個 tool call，預執行 read-only tool
from collections import Counter, defaultdict
from dataclasses import dataclass

@dataclass
class ToolNgram:
    history: tuple[str, ...]  # 最近 N 個 tool names
    next_tool: str
    confidence: float
    is_safe: bool  # side-effect-free check

class SpeculativeToolCache:
    def __init__(self, max_n: int = 3, min_confidence: float = 0.6):
        self.ngram_counts: dict[tuple, Counter] = defaultdict(Counter)
        self.max_n = max_n
        self.min_confidence = min_confidence
        self._safe_tools = frozenset()  # configured by registry

    def observe(self, tool_sequence: list[str]) -> None:
        for n in range(1, self.max_n + 1):
            for i in range(len(tool_sequence) - n):
                hist = tuple(tool_sequence[i:i+n])
                nxt = tool_sequence[i+n]
                self.ngram_counts[hist][nxt] += 1

    def predict(self, recent: list[str]) -> list[ToolNgram]:
        predictions = []
        for n in range(min(self.max_n, len(recent)), 0, -1):
            hist = tuple(recent[-n:])
            if hist not in self.ngram_counts:
                continue
            counter = self.ngram_counts[hist]
            total = sum(counter.values())
            for tool, count in counter.most_common(3):
                conf = count / total
                if conf >= self.min_confidence and tool in self._safe_tools:
                    predictions.append(ToolNgram(hist, tool, conf, True))
        return predictions
```

然後在 `ToolExecutor.execute_all()` 裡面，**在等 LLM 確認下一個 tool call 時**，先並行 spawn `predict()` 出來的高 confidence safe tool。當 LLM 確認走這條分支就直接 cache hit — 否則 cancel + 正常執行。

困難度：TRIVIAL（200 行內）
付費 API：免費 — n-gram 是本地統計
瓶頸：需要工具分類（safe / unsafe），可以用 `tools/schemas/` 加 metadata

**Action 2：在 `LLMClient` 加 `cache_control` prefix — TRIVIAL — 對應 CacheSage 的 KV cache prefetch**

`src/firn/llm/client.py` 的 `complete()` 已經送 request 到 Anthropic，但沒用 `cache_control` ephemeral marker。改成：

```python
# 在 system prompt + 對話歷史最後一筆 user message 加 cache_control: ephemeral
# 這是 Anthropic 2024 Q4 推出的 prefix cache，0.1× cost
# CacheSage 論文的 +13-37pp cache hit lift 主要就靠這個
```

對應 `LLMClient.__init__` 新增 `enable_prefix_cache: bool = True`，API call 時把所有 system + 對話歷史標記為 `cache_control: {"type": "ephemeral"}`。預期成本 ↓ 80-90%（cache hit），latency ↓ 30-50%（TTFT）。

困難度：TRIVIAL（10 行 patch）
付費 API：免費 — 是 Anthropic built-in feature
預期效果：成本立即降到 1/5 到 1/10（取決於 context 穩定度）

**Action 3：實作 `IdleSpec`-style plan candidate sampling — MODERATE**

在 `TaskAgent`（`src/firn/agents/task.py`）的 ReAct loop 中，每次 `await tool_result` 的 idle time，平行生成 N 個 plan candidates（用更小更便宜的 LLM），等 observation 到達時聚合。

```python
# 偽碼：在 conversation.py 的 agent loop
async def think_with_idle_planning(self, observation):
    # 同時做兩件事：
    # 1. 正常 next-action prediction（給 LLM 推理）
    # 2. idle-time 平行生成 plan candidates
    plan_task = asyncio.create_task(
        self._sample_plans(observation, n=3, budget_ms=500))
    # 等 observation 處理完成時，plans 已經好了
    plans = await plan_task
    return self._aggregate_plans(observation, plans)
```

困難度：MODERATE（需要 plan candidate 的 prompt template + aggregation logic）
付費 API：用 free-tier Gemini-2.5-Flash 或本地 Ollama 做 plan sampling
預期效果：long-horizon task 5-10% accuracy ↑

**Action 4：加 `gen_ai.speculation.outcome` span attribute — TRIVIAL — 對應 observability 需求**

`src/firn/observability/spans.py` 加：

```python
class FIRN_SPECULATION_OUTCOME:
    name = "firn.speculation.outcome"
    values = ("hit", "miss", "aborted", "disabled")
```

在 `SpeculativeToolCache` 的每個 speculative call 結束時 set 這個 attribute（hit / miss / aborted）。這樣在 Langfuse / Arize Phoenix trace 裡能直接看到 speculation 的 ROI。

困難度：TRIVIAL（5 行 patch）
付費 API：免費 — 是 observability 屬性
瓶頸：無

**Action 5：實作 Admissibility Check — MODERATE — 對應 Cost-Aware Spec Exec 的 side-effect 安全網**

`src/firn/tools/schemas/` 加 metadata：

```yaml
# tool schema example
search_web:
  side_effect: none  # safe to speculate
  idempotent: true
  cost_per_call_usd: 0.001
  typical_latency_ms: 300
send_email:
  side_effect: external_mutation  # NEVER speculate
  idempotent: false
```

然後 `SpeculativeToolCache` 在 `predict()` 時只挑 `side_effect: none` 的 tool 做 speculative execution。這是 Cost-Aware Spec Exec 論文 D1-D5 中 D1 的 admissibility precondition。

困難度：MODERATE（需要 enum + migration + 所有現有 tool schema 加 metadata）
付費 API：免費 — 是 metadata 配置
瓶頸：需要逐個 tool 標記，啟動成本中等

### 短期實作順序建議（1-2 週）

1. **Action 2**（cache_control）— 1 小時，立即省 80% 成本
2. **Action 4**（span attribute）— 1 小時，建立可觀測性基礎
3. **Action 1**（SpeculativeToolCache）— 2-3 天，要 n-gram predictor + integration 測試
4. **Action 5**（admissibility check）— 1 天，要 schema migration
5. **Action 3**（idle planning）— 1 週，要 prompt engineering + 評估

### 不要做的事

- **不要直接抄 joelvarun/speculative-tools** — 它 0 星、5 月才 release、生產驗證不足；當參考實作讀就好。
- **不要先做 Ghost Tool Calls 的 privacy contracts** — 太早期，標準還沒成型；先把 lossless speculation 做對。
- **不要試圖做 full CacheSage policy-driven runtime layer** — 那是 framework 級重構，firn 不是 vLLM serving engine 的改造對象；等業界先證明這個抽象值得。

---

## 6. Follow-up Questions

1. **Speculative action 的 trace volume 爆炸**：當 speculative engine 啟用，每次 LLM turn 會 spawn 3-5 個 speculative spans，即使全部 miss 也會進 trace storage。OTel semantic conventions 是否需要新的 attribute 來壓縮（e.g. `gen_ai.speculation.bundle`）？下一次可研究：GenAI semconv 對 speculative execution 的最新規範（[github.com/open-telemetry/semantic-conventions-genai](https://github.com/open-telemetry/semantic-conventions-genai) 應追蹤）。

2. **Predictor drift detection**：所有 paper 都假設 predictor 隨時間 decay，但沒有 formal drift detector 設計。可研究：online change-point detection（如 Bayesian online changepoint detection, Adams & MacKay 2007）能否應用於 speculation hit rate 序列。

3. **Speculative execution + RL training 的互動**：EfficientRollout (2606.18967) 處理 RL rollout decoding 加速，但若 RL 訓練的 agent 本身使用 speculative execution，訓練資料分佈會 shift。下次可研究：spec-exec-enabled agent 的 RL fine-tuning 效果。

4. **跨 agent 的 speculation**：單 agent 內部 spec exec 已成熟，但 multi-agent 場景（如 A2A protocol 的 sub-agent call）能否做跨 agent speculation？CacheSage 觸及這個問題但沒展開。

5. **Privacy-preserving speculation 標準**：Ghost Tool Calls 點出 issue-time privacy leak，但沒提出 standard contract。可追蹤 W3C / IETF 是否有 working group 處理 speculative action 的 privacy。

6. **Empirical deployment study**：整個領域缺一個 multi-month production deployment paper — hit rate 隨時間變化、cost saving 真實數字、reliability regression。下次可研究：哪家公司公開了這樣的 case study。

7. **Speculative execution 對 agent 自我反思的影響**：agent 在 spec exec miss 時是否應該記住這次 miss 並反思「為什麼猜錯」？與 6-30/31 的 self-correction 領域交叉。

8. **Simulator / Benchmark**：現有 benchmark（GAIA、FRAMES、MLE-Bench、WebArena）對 speculation-aware agent 沒特別設計，benchmark 上的 spec exec 加速是真實的還是過擬合？需要 spec-aware benchmark。

---

### 原始來源

1. https://arxiv.org/abs/2510.04371 — 論文 — HIGH — Speculative Actions: A Lossless Framework for Faster Agentic Systems (Ye et al., Yale-LILY, Oct 2025)
2. https://arxiv.org/abs/2603.18897 — 論文 — HIGH — Parallelizing Tool Execution and LLM Generation for Low-Latency Agent Serving (PASTE, Microsoft Research, Mar 2026)
3. https://arxiv.org/abs/2604.16469 — 論文 — HIGH — B-PASTE: Beam-Aware Pattern-Guided Speculative Execution for Resource-Constrained LLM Agents (Apr 2026)
4. https://arxiv.org/abs/2512.15834 — 論文 — MEDIUM-HIGH — Optimizing Agentic Language Model Inference via Speculative Tool Calls (Dec 2025)
5. https://arxiv.org/abs/2510.16276 — 論文 — HIGH — What Limits Agentic Systems Efficiency? + SpecCache (Oct 2025)
6. https://arxiv.org/abs/2511.00330 — 論文 — MEDIUM-HIGH — Sherlock: Reliable and Efficient Agentic Workflow Execution (Nov 2025)
7. https://arxiv.org/abs/2605.22154 — 論文 — HIGH — IdleSpec: Exploiting Idle Time via Speculative Planning for LLM Agents (May 2026)
8. https://arxiv.org/abs/2605.16565 — 論文 — MEDIUM-HIGH — Skim: Speculative Execution for Fast and Efficient Web Agents (May 2026)
9. https://arxiv.org/abs/2605.13360 — 論文 — HIGH — Speculative Interaction Agents: Building Real-Time Agents with Asynchronous I/O and Speculative Tool Calling (Adobe Research, May 2026)
10. https://arxiv.org/abs/2605.27744 — 論文 — HIGH — A Policy-Driven Runtime Layer for Agentic LLM Serving (CacheSage, May 2026)
11. https://arxiv.org/abs/2605.26186 — 論文 — HIGH — SetupX: LLM Agents with Experience-Augmented Speculative Execution + LIFO Docker snapshot (May 2026)
12. https://arxiv.org/abs/2606.07846 — 論文 — MEDIUM — Cost-Aware Speculative Execution for LLM-Agent Workflows: An Integrated Five-Dimension Method (Jun 5, 2026)
13. https://arxiv.org/abs/2606.02483 — 論文 — HIGH — Ghost Tool Calls: Issue-Time Privacy for Speculative Agent Tools (Jun 2026)
14. https://arxiv.org/abs/2606.17518 — 論文 — MEDIUM — SpecGen: Accelerating Agentic Kernel Optimization with Speculative Generation (Jun 2026)
15. https://arxiv.org/abs/2606.12485 — 論文 — HIGH — Speculative Rollback Correction for Quality-Diverse Web Agent Imitation (SRC, Jun 2026) — code: https://github.com/LongkunHao/SRC_gui_agent
16. https://github.com/joelvarun/speculative-tools — 開源實作 — MEDIUM — Speculative execution engine for LLM agent tool calls, MIT license, May 2026 (0★ 但 README 引用 Speculative Actions / PASTE / Optimizing Agentic LM, production-quality 設計)

---

下一個工作日排程執行本指令。
