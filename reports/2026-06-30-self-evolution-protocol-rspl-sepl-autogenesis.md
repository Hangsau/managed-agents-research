# 研究報告：Self-Evolution Protocol Layer — Autogenesis / RSPL / SEPL  
**日期**：2026-06-30  
**來源數**：7 | **標籤**：#self-evolution #protocol-layer #agent-architecture #registry #versioning

## 1. The Problem

到 2026 H1，self-improving agent 領域撞上一個結構性問題：**evolution 是 hack 而不是 protocol**。

過去 12 個月我們看到的 self-improvement 機制，幾乎都是 ad-hoc 的：Reflection loop、TextGrad optimization、SE-Agent 的 trajectory pool、GRPO trainer、rejection-sampling fine-tune。每個都不錯，但有一個共同的痛點——

> 「哪些東西進化」跟「怎麼進化」混在一起，讓 monotonic 版本控制、lineage 追蹤、safe rollback 無法存在。

實際後果：

| 痛點 | 當前狀況 |
|------|---------|
| **不能回答「prompt v3 比 v2 好在哪」** | 沒有 prompt versioning，只有 git diff |
| **不能 audit 「誰、何時、為什麼改了 tool schema」** | 沒有 tool/MCP-server evolution log |
| **不能 rollback 一個 agent 升級到上一版本** | 只有整個 codebase git revert |
| **optimizer 換 TextGrad→GRPO 要重寫 glue** | 每個 optimizer 都自己管 state |

SkyworkAI/DeepResearchAgent（3,475★）跟 arXiv 2604.15034（Autogenesis paper, DVampire/Autogenesis 62★）在 2026 Q1–Q2 同步提出一個新抽象：**把 prompts / agents / tools / environments / memory 全部 model 成 protocol-registered resources**，再把 evolution 本身做成 protocol layer。RSPL 跟 SEPL 是核心兩個 protocol layer。

這個角度跟 2026 之前所有 framework 的「reflection loop」「trajectory pool」「RL fine-tune」都不同——它不是改進某一種 evolution 算法，**它是把 evolution 當 first-class protocol** 治理。

誰在解決：
- **SkyworkAI/DeepResearchAgent** — production-grade agent framework with explicit `Registry` + `VersionManager` infra（基於 MMEngine，534K 月下載）
- **arXiv 2604.15034** — Autogenesis paper（2026-04），RSPL + SEPL formalization
- **EvoFSM (arXiv 2601.09465, 2026-01)** — 批評 free-form rewriting 帶來不穩定，倡議 FSM-based evolution
- **Inference-Time Scaling of Verification (arXiv 2601.15808, 2026-01)** — 另一條線：rubric-guided verification 而非 protocol-based versioning

## 2. Core Mechanism

核心概念是把 **self-evolution 拆成兩層**：Resource Substrate Protocol Layer (RSPL) 管「什麼東西可以被進化」，Self-Evolution Protocol Layer (SEPL) 管「怎麼進化」。兩層用 protocol-mediated interface 解耦。

### 2.1 RSPL — Resource Substrate Protocol Layer

把五種 first-class resource 用同一套 registry 介面管理。每個 resource 都有：

- **State** — 當前 snapshot
- **Lifecycle** — create / read / update / delete（全部 versioned）
- **Versioned Interface** — 任何讀取都指定 `component_type` + `name` + `version`，不存在「最新版」這種模糊語意

五種 resources：

```
prompts        # 系統指令、user prompt template
agents         # agent 定義（plan + tools + persona）
tools          # callable capabilities
environments   # filesystem / browser / trading backtest
memory         # session/event memory + long-term memory
```

直接從 SkyworkAI/DeepResearchAgent `src/registry.py` 跟 `src/version/server.py` 抽出來的核心介面：

```python
# src/registry.py — 5 種 resources 都用 mmengine.Registry
TOOL = Registry("tool", locations=["src.tool"])
ENVIRONMENT = Registry("environment", locations=["src.environment"])
AGENT = Registry("agent", locations=["src.agent"])
PROMPT = Registry("prompt", locations=["src.prompt"])
MEMORY_SYSTEM = Registry("memory_system", locations=["src.memory"])
SKILL = Registry("skill", locations=["src.skill"])

# src/version/server.py — 每個 component 都有 version history
class VersionManager(BaseModel):
    _version_histories: Dict[str, Dict[str, ComponentVersionHistory]] = {
        "tool": {}, "environment": {}, "agent": {},
        "prompt": {}, "memory": {}, "benchmark": {}, "skill": {}
    }

    async def register_version(self, component_type, name, version,
                                description=None, metadata=None):
        # 寫 JSON line 到 version.json，append-only，支援 rollback
        ...
```

**Key insight**：這不是一般的「git tags on prompts」。它要求 **每個 component 必須自我描述自己的 state**——一個 tool 必須能回答「我這個版本能做什麼」，一個 agent 必須能回答「我這個版本的 plan 是什麼」。git 版本控制只能追蹤程式碼，沒辦法語意化地回答「prompt v3 改了哪個字段」。

### 2.2 SEPL — Self-Evolution Protocol Layer

在 RSPL 之上，定義三個閉環 operator：

```
┌────────────┐    ┌────────────┐    ┌────────────┐
│  PROPOSE   │ →  │   ASSESS   │ →  │   COMMIT   │
│ 提出修改    │    │ 評估品質    │    │ 寫入版本    │
│ proposal   │    │  + lineage │    │  + rollback│
│ + diff     │    │  + rubric  │    │  + log     │
└────────────┘    └────────────┘    └────────────┘
```

每個 operator 是 **副作用可追蹤** 的——commit 一個 prompt v3 必須附帶 trace 跟 rubric 通過證據。

Skywork 直接 implement 了 4 種 Optimizer 物件（`src/optimizer/__init__.py`）：

```python
from .textgrad_optimizer import TextGradOptimizer
from .reflection_optimizer import ReflectionOptimizer
from .grpo_optimizer import GrpoOptimizer
from .reinforce_plus_plus_optimizer import ReinforcePlusPlusOptimizer
```

每個 Optimizer 透過同樣的 protocol interface 對 prompt 做修改——interchangeable。換 optimizer 不需要重寫任何 glue code，因為 protocol 介面穩定。

### 2.3 Act-Observe-Optimize-Remember outer loop

每一次 evolution iteration 走完同一個 outer loop（從 README 抽出）：

```
Act        # agent 產出 actions/outputs with current resource versions
Observe    # capture traces, intermediate reasoning, environment feedback
Optimize    # optimizer 把 feedback 翻成 component 升級
Remember    # write summary/insight to memory for next session
```

關鍵：**每輪 loop 都會 bump 至少一個 component 的 version**。這個版本歷史能讓你 trace「agent v3 在 prompt v5 + tool v2 上失敗了，rollback 到 v2.4 prompt 之後成功」。

### 2.4 Code 範例：怎麼對 prompt 做 ReflectionOptimizer commit

```python
# 加了 iteration，對 prompt v1 升級到 v2
optimizer = ReflectionOptimizer(agent)
result = await agent.execute(task="summarize Q3 earnings")
verdict, feedback = optimizer.assess(result)
if verdict == "needs_improvement":
    new_version = await version_manager.generate_next_version(
        component_type="prompt",
        name="system_summarizer",
        version_type="minor"  # 1.0.0 → 1.1.0
    )
    await version_manager.register_version(
        component_type="prompt",
        name="system_summarizer",
        version=new_version,
        description=feedback.summary,
        metadata={"rubric_scores": feedback.scores}
    )
```

跟「git commit + push」是不同物——這是 **lineage-aware, semantically-described, recoverable** 的版本。

### 2.5 EvoFSM — 對比設計：FSM-based evolution 而非 free-form rewrite

EvoFSM（arXiv 2601.09465, 2026-01）是同期相近方向的另一個 proposal：它不認同 free-form rewrite，認為那會帶來「hallucination、instruction drift」，主張用 **explicit Finite State Machine** 來控制 evolution 邊界。

跟 Autogenesis 的 RSPL/SEPL 對照：
- Autogenesis：resource versioning + protocol-mediated commit。廣覆蓋，但 version metadata 要靠人工/optimizer 提供。
- EvoFSM：FSM 約束 state 轉換，安全性高但靈活度低。

Inference-Time Scaling of Verification（arXiv 2601.15808, 2026-01）走第三條路：用 rubric-guided verification 取代 protocol layer，所有進化都靠「rubric 通過與否」決定，沒有顯式 version。

**三者共識**：2026 H1 整個 self-evolution 領域都在試圖把原本的「野生 reflection loop」結構化。Autogenesis 走最遠——protocol 層；EvoFSM 走中間——FSM 邊界；rubric verfication 走最淺——quality gate，但都比裸 reflection loop 強。

## 3. Why It Matters / Applications

這個 protocol-layer evolution 模式有三個破壞性含意：

**對開源 agent framework**：2026 多數 framework（LangChain、AutoGen、CrewAI）的 self-improvement 都是 ad-hoc reflection loop 或 RLAIF fine-tune，沒有 protocol layer。RSPL/SEPL 提供一個「框架中立」的 lingua franca：未來出現的 optimizer 只要 implement 同樣 protocol interface 就能 plug-in，不需要每家 framework 各自 port。

**對 production reliability**：當你第一次遇到「昨天的 prompt 跟今天的 prompt 哪裡不同」這種 audit 需求，git diff 幾乎沒用。protocol-managed version + rubric metadata 直接給法務/ML eval team 一份 audit log。

**對 multi-agent coordination**：6/22 swarm 那篇說 handoff 是 primitive——但沒有 versioning 的 handoff 等於不存在的 primitive。RSPL 補上「agent v2 用了 swarm-skill v1 而非 v0.9」這種 lineage trace 才能讓 swarm 真正測試跟迭代。

跨領域印證（§7.15 type signal）：
- **academic**：Autogenesis paper 引用 CRL 跟 EvolveML，近 6 個月三篇獨立 paper（2601.09465、2601.15808、2604.15034）都用「結構化 evolution」對「ad-hoc evolution」
- **industry**：Skywork 已經在 productionized，3475★ ranking
- **infra layer**：MMEngine registry 534K monthly downloads，protocol 抽象有 actual adoption base

**預測**：未來 6 個月會看到至少 1 個現有 framework（LangChain 或 AutoGen）整合「registry + version」的 resource-layer 抽象，雖然可能不會用 RSPL/SEPL 這個名字，但概念會出現。

## 4. Limitations / Honest Assessment

作者坦承的限制：

1. **「protocol-managed = safe evolved」是 false-equivalence**：SEPL 只保證 commit 跟 rollback 能 audit，但不保證 quality。garbage-in garbage-out 仍然存在。沒有驗證，新 version 可能比舊版更糟但都 commit 進去。
2. **5 種 resources 不涵蓋 emergent state**：runtime 時建立的 intermediate artifacts（compiled scratchpad、drafted-but-not-acted-on tool calls）不屬於 5 種。要嘛丟失、要嘛拿 memory 頂替，模糊化 protocol 邊界。
3. **VersionManager 對 multi-process 是 single source of truth**：JSON file lock 同步，scale 超過 single machine 就退化。Multi-host 場景需要額外實作（Redis/Postgres）。

我們的獨立評估：

4. **「從 free-form 變 protocol-managed」真的是進步嗎？** 想想看：當前 Reflexion / Self-Refine 不就是「LLM 自己重寫 prompt 的 free-form rewrite」嗎？把它包進 RSPL 後**只是把 free-form 的範圍縮小到 metadata + rubric + commit 步驟**，核心 LLM-as-optimizer 的不穩定性沒解決。要真的證明 protocol layer 升級效果，需要 ablation：protocol-managed vs identical optimizer 但 no protocol。
5. **跟 EvoFSM 對照的缺席**：Autogenesis paper 只跟 ad-hoc reflection / RLAIF baseline 比，沒跟 EvoFSM 這類有 formal boundary 的方法比，難以確認「protocol layer」這個抽象值的。
6. **MMEngine lineage 包袱**：version tracking 跟 Registry config 都直接繼承 MMEngine（OpenMMLab 訓練 framework）。如果 framework 沒有事先引入 MMEngine，整套 protocol abstraction 要重寫。沒有 mmengine 的 codebase 會覺得「這個 protocol layer 是給特別大的 codebase 用的，跟我無關」。
7. **non-text evolution**：SKILL.md 對 binary model checkpoints 的 versioning 怎麼處理？5 種 resources 沒涵蓋 deployed weights。
8. **Schema 變更問題**：一個 tool schema 從 `v1: {url: string}` 改成 `v2: {url: string, method: str}` 後，舊 prompt 可能還在呼叫 v1，這是 **version skew**，protocol 沒明說怎麼 handle。EvoFSM 的 FSM 對此較有利。

## 5. Actionable for Our Projects

> 對 firn 的具體改進。**每個改動獨立標記 PR 數量跟難度**。

### F-SEP-1: 在 firn 加 Registry + VersionManager 抽象 — MODERATE

firn 已經有 `skills/loader.py`、`tools/registry.py`（registry 沒 versioning）、`memory/`（multiple backends），但 **沒有一個統一的 protocol 介面**處理「所有 component 都被登錄為 resource，都有 version」。

**建議檔案**：
- 新建 `src/firn/protocol/__init__.py`
- 新建 `src/firn/protocol/registry.py`（5 種 resources 的 thin wrapper，不引入 MMEngine 依賴——直接用 Python `@dataclass + dict`）
- 新建 `src/firn/protocol/version.py`（Pydantic model + JSON file storage，async API）

**不要做**：完整照抄 MMEngine Registry——firn 是單人 framework，引入大 dependency 換 protocol layer 過重。**做對的事**是 thin layer（≤150 LOC）+ 對現有 modules（`tools/registry.py`, `skills/loader.py`, `memory/`）做 patch 讓它們輸出 `ResourceRef`（含 version）。

**不需付費 API**。Day-1 zero-cost。

### F-SEP-2: 在 Skills/loader 加 versioning — TRIVIAL

現在 `skills/loader.py` 把 SKILL.md `name + description + platforms + tags` load 成 `SkillMeta`，但**沒 track version**。SKILL.md frontmatter 加一個 `version:` 欄位；`SkillMeta` 加一個 `version: str = "1.0.0"`；`SkillService.get_skill()` 支援 `name="foo", version="1.1.0"` 選擇性載入。

**2-3 小時工作量**。直接讓 skill system upgrade 不再是「覆寫 SKILL.md」而是「可審計的 1.0.0 → 1.1.0」。

### F-SEP-3: Memory blocks 加 lineage tag — MODERATE

firn `memory/long_term.py` 用 block-based storage（v1 架構 I1）。每個 block 加 `parent_block_id: UUID | None` 跟 `derived_from_version: int` 欄位——方便 trace「這個 summary block 是從哪幾條 message 用哪個 prompt 總結出來的」。

**好處**：當 ontology evolution（換一套記憶分類）後能 roll back，能 audit 哪次 model upgrade 導致了哪個記憶錯誤。

**2-3 天工作量**（要 migration），但是長期 reliability 槓桿極高。

### F-SEP-4: Tool schema versioning — TRIVIAL

`tools/schemas/` 已是 Pydantic 風格定義。為每個 schema 加 `@versioned("1.0.0")` decorator；`tools/executor.py` 在 dispatch 前把 `tool_result.schema_version` 加到 response metadata，方便 client 知道 caller 用的哪個版本。

### F-SEP-5: Optimizer-protocol interface — HARD（research-only）

完整移植 SEPL 的 propose-assess-commit loop 到 firn 是一個 sizeable 改動。它需要：
- 把現有 reflection 機制（可能在 CronAgent 或 ConversationAgent 裡）refactor 成 `Optimizer` ABC
- 新增 `CommitLog` Pydantic model + persistent storage
- 跟現有 `CircuitBreaker`（`llm/circuit_breaker.py`）整合做 rubric gate

**這是 P3+ 才考慮的工作**。先做 F-SEP-2/3/4 三個 trivial 改動，把 raw material 準備好。

### NEGATIVE-SPACE：不要做這些

- **不要引入 MMEngine 作為 dependency**——太多 transitive deps。寫 ~150 LOC 自家 registry 即可。
- **不要把 binary model checkpoint 放進同個 resource registry**——protocol 沒設計這個。要的話另開 `weights/` 模組。
- **不要把整個 git history 強行 encapsulate 到 VersionManager**——version skew 處理不來。讓 git 跟 protocol 各管各的，git 管 source code、VersionManager 管 deployed resource state。

### 是否需要付費 API？

全部不需要。MMEngine 是 MIT, 自家協議約 150 LOC, 純 stdlib + Pydantic。

## 6. Follow-up Questions

下次研究可追蹤的方向：

1. **有沒有真的 ablation study 證明 protocol-managed 比 ad-hoc reflection 強**？Autogenesis paper 沒做這個。如果 firn 想抄，先等一個獨立的 third-party benchmark 出來。
2. **MMEngine 之外的 registry 抽象**——同樣概念是否出現在 pytorch-lightning（可能有）、ray serve（很可能有）、甚至 LangChain 的「versioned tool」概念？哪些是 1:1 對應、哪些是 different name for same thing。
3. **跟 6/22 swarm 的 handoff primitive 怎麼整合**？handoff 是** runtime primitive**，RSPL 是** evolution primitive**，兩者相交處在哪？要不要做「swarm-orchestrator v2 在 handoff-protocol v1.2 上跑」這種 lineage？
4. **EvoFSM 的 FSM boundary 跟 RSPL 的 version rollback 對 reliability 的相對增益**——能否做個 minimal 在 firn 內對照的小實驗？
5. **Schema evolution**（issue #7）— 任何 protocol-managed resource 在 schema-breaking change 後要怎麼跑 migration？這是 protocol-layer 最大的 open frontier。etcd 有 protobuf migration pattern 可以借鏡。
6. **Eval pipeline 對 protocol-managed resource 的支持**：怎麼自動驗證「agent v3 + prompt v2 在 benchmark X 上比 v2+v1 好」？每次 commit 跑一次完整 eval 不切實際。要不要做 PR-time canary eval？

---

### 原始來源

- https://arxiv.org/abs/2604.15034v5 — Autogenesis: A Self-Evolving Agent Protocol（論文）— HIGH — RSPL + SEPL formal definition，v5 修訂版已 2026-04-16 發表
- https://github.com/SkyworkAI/DeepResearchAgent — Production framework（程式庫）— HIGH — 3475★, 5 commits in last 90 days, 基于 MMEngine Registry + 自家 VersionManager。Resource-level abstraction 已成熟到 production
- https://github.com/DVampire/Autogenesis — Paper reference impl（程式庫）— MEDIUM-HIGH — 62★, 最後 push 2026-06-20。配合 paper 的最直接讀物
- https://arxiv.org/abs/2601.09465v2 — EvoFSM: Controllable Self-Evolution for Deep Research with FSM（論文）— HIGH — 直接對比向：FSM-bounded evolution vs free-form rewrite；驗證「結構化 evolution」這個主題不只是 Autogenesis 一家
- https://arxiv.org/abs/2601.15808v2 — Inference-Time Scaling of Verification via Test-Time Rubric-Guided（論文）— HIGH — 第三條路：rubric-guided verification。交叉驗證「2026 H1 結構化 self-evolution」是熱點而非 Autogenesis 孤鳴
- https://pypi.org/project/mmengine/ — MMEngine infrastructure（套件）— HIGH — 534K monthly downloads（2026-06 驗證），Autogenesis/Skywork 整套 protocol abstraction 的底層依賴
- https://github.com/open-mmlab/mmengine — MMEngine source（程式庫）— HIGH — Registry/Config/Runner 三件套，reference impl 看 `mmengine/registry/registry.py` + `mmengine/config/config.py`
