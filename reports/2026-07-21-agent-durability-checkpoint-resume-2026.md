# 研究報告：Agent State Recovery, Idempotency & Crash-Consistency in Long-Horizon Workflows

**日期**：2026-07-21
**來源數**：9 | **標籤**：#agent-architecture #durability #crash-recovery #idempotency

---

## 1. The Problem

**為什麼這個問題重要？**

長時執行（long-horizon）AI agent workflow 是 2026 年 agent 系統最大的 reliability gap。naive loop `while not done: step = llm(); tool(step)` 在 notebook 沒事，但在 production 一定爆炸：

- **OOM kill**：20 分鐘的 run 到第 12 分鐘被 systemd OOM-kill → 從頭開始 → 燒光 token budget
- **重複副作用**：retry 把同一封信寄兩次、Stripe 扣兩次款
- **Poison job**：一個壞 payload 永遠失敗，clog 整個 queue，worker 也跟著卡住
- **Silent hang**：LLM call 卡住 40 分鐘，沒人通知、沒 progress
- **Double-claim**：兩個 worker 同時搶同一個 job，concurrent 跑
- **Stuck `running`**：worker segfault 但 job 永遠停在 `running`，沒人 reclaim
- **Human-in-the-loop 沒地方等**：需要人 approve 才能寄的 email，沒有「parking lot」就會直接寄出去

**誰在解決？**

四股力量 2026 年 Q1–Q2 都在做：

1. **Infrastructure 派**：Temporal（21,778 ⭐）、Microsoft pg_durable（2,666 ⭐，Postgres 內建）— 試圖把整個 durable execution 變成 SQL 或 event sourcing 平台
2. **Framework 派**：LangGraph、AWS Durable Functions、OpenAI Agents SDK + Temporal 整合
3. **Library 派**：agent-resume、durable-agents、FlowKeeper、agent-resume、Sutram、Runback、go-agent-reliability — 一個檔案 / 幾千行 Python，提供「不需要 broker 的 durability」
4. **Meta-skill 派**：create-loop 試圖讓 agent 自己寫 resumable loop.plan 而不是手寫 prompt

**目前進展到哪？**

到 2026-07，durable execution 已經是 **industry-standard pattern**（pg_durable README 直接這樣說），不是新點子。但 AI agent 領域的鴻溝在於：

- Temporal 太重（需要 server cluster，雖然 OpenAI Agents SDK 整合做了一些 simplify）
- LangGraph 的 checkpointer 只管 graph state、不管 **side effect idempotency**
- Library 派各有擅場但生態零碎（agent-resume 只做「list of items」、durable-agents 是 SQLite + 完整 worker、FlowKeeper 是 Python decorator）

**這份報告的選擇**：把焦點放在 Library 派，特別是「個人開發者能在單機用 stdlib 跑得起來」的 pattern — 這才是 firn / managed-agents 真正能用的層級。

---

## 2. Core Mechanism

### 2.1 三層模型（從 9 個來源提煉）

整個 durability 機制可以拆成三個獨立層：

```
┌─────────────────────────────────────────────────────────┐
│ Layer 1: STATE PERSISTENCE（checkpoint 本身）            │
│   - 每步 / 每 turn / 每完成一個 work item 寫一次         │
│   - 寫入格式：JSONL append + fsync（agent-resume）       │
│            SQLite row + WAL（durable-agents）            │
│            Postgres table + event log（pg_durable, Temporal）│
│   - 核心原則：寫必須 atomic + ordered + replayable       │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ Layer 2: CLAIM & RECOVERY（誰能跑、誰能 reclaim）         │
│   - Atomic claim：BEGIN IMMEDIATE + UPDATE..RETURNING    │
│     或 Postgres advisory lock（pg_durable）             │
│   - Heartbeat + visibility timeout：                     │
│     worker 每 N 秒 ping heartbeat_at；若超時 → 別人 reclaim │
│   - Crash detection：                                    │
│     runlock + pidfile（go-agent-reliability）；或        │
│     比對「最後一個 state mutation 的時間 vs now」         │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ Layer 3: SIDE-EFFECT IDEMPOTENCY（不可重複的動作）         │
│   - `once()` ledger：key + payload 寫 DB，committed 才執行  │
│   - Idempotency key = hash(step_name + job_id + inputs)  │
│   - 即使 retry / replay 也不會重複執行                   │
│   - 必須發生在 checkpoint 之後、副作用之前                │
└─────────────────────────────────────────────────────────┘
```

### 2.2 兩個具體實作範例（直接程式碼）

#### A. agent-resume（最簡版本 — 純 stdlib）

```python
from agent_resume import JsonlStore, resume_or_start

store = JsonlStore("agent.ckpt")  # append-only, fsync'd

run = resume_or_start(
    store=store,
    initial_state={"results": {}},
    work_items=list(range(1, 101)),
)

for issue_id in run:
    new_state = process_issue(issue_id, run.state)
    run.checkpoint(new_state)   # one JSONL row, fsync'd
```

Crash 在第 47 個 → 下次跑從第 48 個開始。**Zero deps**、**zero broker**。但這個 pattern 只處理「list of items」，不管 DAG、不管 side effect、不管 atomic claim。

#### B. durable-agents（完整版 — SQLite + worker + heartbeat + idempotency）

State machine：
```
pending → running (atomic claim)
running → done (pipeline finished)
running → paused (approval gate)
paused  → pending (approve or reject)
running → pending (fail then backoff retry)
running → dead (attempts exhausted)
running → pending (crash then visibility timeout reclaim)
dead    → pending (retry-dead)
```

關鍵程式碼片段（從 README 推導）：

```python
@step("classify")
def classify(ctx):
    return {"label": "invoice"}    # persisted to checkpoint

@step("notify")
def notify(ctx):
    key = idempotency_key("notify", ctx.job_id, ctx.result("classify")["label"])
    return once(ctx, key, lambda: send_email(...), kind="email")
    # ↑ side effect only fires once across retries/resumes

@pipeline("triage")
def triage(ctx):
    classify(ctx)
    approval_gate(ctx, "send", summary="Approve outbound email", timeout_hours=12)
    notify(ctx)
```

Crash mid-draft → worker kill → 10 秒後 visibility timeout → 另一個 worker reclaim → `step_cached` 跳過前 3 個 step → 重跑 draft → 完成。

### 2.3 為什麼 Temporal / pg_durable 不是這份報告的主軸

兩個原因：

1. **太重**：Temporal 要起 server cluster；pg_durable 要 Postgres + extension + 你願意把 workflow 寫成 SQL
2. **不是 fire-and-forget**：個人 agent 框架的目的是「下班前 enqueue，明天早上看結果」——不需要 cross-region HA

但**設計 pattern 完全一樣**：checkpoint per step、claim with timeout、event-sourced replay、deterministic re-execution。Temporal 的 SDK 模式就是 durable-agents / pg_durable 在做的事，只是規模不同。

---

## 3. Why It Matters / Applications

### 3.1 對 AI agent 領域的影響

**理論影響**：把「agent reliability」從「prompt engineering + retry」推進到「formal durability layer」。agent 變成可以**長期跑**而不會燒光預算。

**實務影響**：

1. **Cost ceiling 被打破**：沒 durability 就沒人敢讓 agent 跑 30 分鐘以上（怕 crash 浪費 token）；有 durability 後 24-hour autonomous run 變可行
2. **HITL 終於能 scale**：approval gate 的「parking lot」是 durable execution 真正讓 HITL 落地的關鍵基礎設施（呼應 2026-07-20 HITL 報告）
3. **Multi-agent dispatch 變可信**：worker pool 模式（durable-agents 的 `run_worker`）讓 sub-agent 不會搶同一個任務
4. **Cost attribution 變精準**：每個 step 都有 `started_at / finished_at / token_cost / duration_ms`，可以算 agent 的單位經濟學

**生態指標（2026-07 確認）**：

| 專案 | Stars | 模式 | 規模 |
|---|---|---|---|
| Temporal | 21,778 | Event-sourced workflow server | Enterprise |
| Microsoft pg_durable | 2,666 | SQL + Postgres extension | Postgres teams |
| LangGraph | (官方框架) | Graph state + checkpointer | All LangChain agents |
| durable-agents | 2 | SQLite + stdlib | Solo developer |
| FlowKeeper | 0 | Python decorator + SQLite | Solo developer |
| Sutram | 2 | Postgres + Redis + Celery | Mid-stage startup |
| agent-resume | 0 | JSONL + stdlib | Minimalist |
| Runback | 0 | Claude Code wrapper + FastAPI + Next.js | Claude-Code-specific |
| go-agent-reliability | 0 | Go stdlib primitives | Go-ecosystem |

### 3.2 兩個最值得偷的 pattern

**Pattern A — visibility timeout + reclaim（durable-agents）**

```
worker 開始跑 job → 同時起 heartbeat thread → 每 N 秒 UPDATE heartbeat_at
                                                        ↓
若另一個 worker 看到 `last_heartbeat_at < now - 10s` → 接管
```

這比 systemd 的「process restart」聰明：systemd 只知道「process 死了」，不知道「這個 job 跑到 step 4 of 6」。visibility timeout 知道。

**Pattern B — `once()` ledger（durable-agents + Runback）**

```python
def once(ctx, key, produce, kind):
    # 1. SELECT existing entry by key
    # 2. if exists → return cached
    # 3. if not → INSERT key + pending
    # 4. execute produce()
    # 5. UPDATE with result
    # 6. (on crash mid-3/5 → next call sees pending → skip or retry)
```

這是 idempotency 的「無 retry 雙執行」保證。比純粹「retry with backoff」更強，因為：
- `send_email` 即使在同一個 crash-and-replay cycle 也不會寄兩次
- 跨 process restart 也保證
- 可以在 ledger 上看到「誰、何時、被什麼 key 觸發」

---

## 4. Limitations / Honest Assessment

### 4.1 各來源的自我揭露

**Temporal**（from blog + docs）：不是 agent framework，需要 SDK 包裝；event history 變大會需要 retention policy；deterministic re-execution 要求「code 是 deterministic 的」，對 LLM（天生 stochastic）來說是 tension。

**Microsoft pg_durable**：workflow logic 必須 map 到 SQL；不是給 heterogeneous system 用的；extension 安裝需要 DBA 同意。

**LangGraph**（from docs）：MemorySaver 不跨 process restart；PostgresSaver thread_id 限制 255 chars；checkpoints 會 unbounded 增長。

**durable-agents**：claim 用 `BEGIN IMMEDIATE` 在 SQLite 上**只能 single-writer**；多機需要 migrate 到 Postgres；step output 必須 JSON-serializable（不能存 binary）。

**agent-resume**：純 append-only，**不做 atomic claim**（README 自己寫 "Process-local lock only. If two processes write to the same path you need a file lock or a different store"）；不適合多 worker。

**FlowKeeper**：SQLite 同樣 single-writer 限制；不支援 distributed deployment；decorator-based，runtime introspection 有限。

**Runback**：依賴 Claude Code CLI（不是 generic agent）；MVP 階段；demo fixtures 都是假的。

**go-agent-reliability**：是 library 不是 framework；你自己負責「state mutation 要在 checkpoint.Save 之後」這種 ordering 紀律；recovery.Classify + Synthesize 是 best-effort。

**Sutram**：整個 stack 太複雜（Postgres + Redis + Celery + FastAPI），不是「單機就跑得起來」的東西。

### 4.2 我們的獨立批判

| 質疑 | 細節 |
|---|---|
| **「deterministic replay」對 LLM agent 是 marketing** | LLM 本身是 stochastic，即使你把整個 state 還原，下一輪 `llm(prompt)` 的結果可能完全不一樣。所以 checkpoint 的價值不是「完全重現」，是「不要再花 token 算前面已經算過的東西」+「副作用保險」 |
| **「zero deps」的代價是被迫自己寫原語** | agent-resume / FlowKeeper 寫起來很爽，但 production-grade 觀測性 / audit / dashboard 全部要自己接。durable-agents 把這部分包了，但用 SQLite → scale-up 痛苦 |
| **approval gate 不解決「誰來 approve」的問題** | durable-agents 把 job park 在 `paused`，但審核者必須**已經知道要看 CLI / dashboard**。如果你的 agent 跑在背景沒人盯，parking lot 就變成 stuck graveyard |
| **visibility timeout 是猜的** | 10s 太短（LLM thinking 經常 > 10s）；600s 太長（worker 真的 crash 後要等 10 分鐘才能 reclaim）。需要根據 LLM p95 latency 自適應 |
| **idempotency key 不能包含 LLM output** | 因為 LLM output 不 deterministic。如果你 `idempotency_key("send", msg_id, llm_output)` 會出現「同樣 msg_id 配不同 llm_output」的兩個 key — 失去意義。實務上 key 只能基於 input side |
| **沒有 source 在量化「真實 replay 率」** | 大家都說「crash-safe resume」，但沒看到 benchmark 說「在 100 次隨機 kill 後，有多少次真的成功從對的 step 接續」。這是 open measurement 問題 |

### 4.3 與既有方案對比

| 維度 | ReAct | LangChain AgentExecutor | AutoGPT | Temporal | durable-agents / agent-resume |
|---|---|---|---|---|---|
| 跨 crash resume | ❌ | ❌ | ❌（最差） | ✅ | ✅ |
| Side-effect idempotency | ❌ | ❌ | ❌ | 需手寫 | 內建 `once()` |
| 單機零依賴 | ✅ | ❌ | ✅ | ❌ | ✅ |
| HITL parking | ❌ | ❌ | ❌ | ✅ | ✅（approval gate） |
| DAG 表達 | ❌ | ❌ | ❌ | ✅ | FlowKeeper 有；durable-agents 沒有 |
| Multi-machine claim | ❌ | ❌ | ❌ | ✅ | ❌（SQLite single-writer） |
| Observability | ❌ | LangSmith | ❌ | ✅ | 需自接 |

**結論**：durable-agents / agent-resume / FlowKeeper 填補的 niche 是「**單機 / 個人 agent / 不要 broker**」這塊。這塊 Temporal 太重、LangGraph 太 framework-y。

---

## 5. Actionable for Our Projects

> 注意：firn 已經有 I5-I7 的 tasks service（含 heartbeat + zombie detection + resume_task）— 下面 4 個 action 是**補完 durability 缺口**，不是從零開始。

### 5.1 firn — `once()` ledger 模組（HIGH priority, MODERATE）

**問題**：firn 的 TaskAgent 跑 step 時如果 retry / resume，副作用（寄信、寫檔、發 PR）會重複。

**做法**：在 `src/firn/tasks/` 新增 `idempotency.py`：

```python
# src/firn/tasks/idempotency.py

@dataclass
class IdempotencyEntry:
    key: str
    kind: str           # "email" / "file_write" / "http_post"
    payload_hash: str
    status: str         # "pending" / "committed" / "failed"
    result: str | None
    created_at: float
    committed_at: float | None

class IdempotencyLedger:
    """Per-job idempotency ledger. Persists to SQLite in same DB as tasks."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._ensure_schema()

    def once(self, key: str, kind: str, payload: Any, produce: Callable[[], Any]) -> Any:
        """Execute produce() at most once per (job, key). Crash-safe."""
        existing = self._conn.execute(
            "SELECT status, result FROM idempotency WHERE key=?",
            (key,),
        ).fetchone()
        if existing:
            if existing["status"] == "committed":
                return existing["result"]
            elif existing["status"] == "pending":
                raise PendingEffectError(key)  # crash mid-execute; let caller retry
            # failed → allow retry

        self._conn.execute(
            "INSERT OR IGNORE INTO idempotency (key, kind, payload_hash, status, created_at)"
            " VALUES (?, ?, ?, 'pending', ?)",
            (key, kind, hash_payload(payload), time.time()),
        )
        try:
            result = produce()
            self._conn.execute(
                "UPDATE idempotency SET status='committed', result=?, committed_at=?"
                " WHERE key=?",
                (json.dumps(result), time.time(), key),
            )
            return result
        except Exception:
            self._conn.execute(
                "UPDATE idempotency SET status='failed' WHERE key=?", (key,)
            )
            raise
```

**Hook 到 TaskAgent**：`TaskAgent.run_step()` 包進 `once()` wrapper，step name + job_id + tool input → idempotency key。

**難度**：MODERATE。~150 LOC + schema migration（firn 的 `db.py` 已用 SQLite，加一張 `idempotency` 表 + index on `key`）。

**付費 API**：不需要。純 SQLite + stdlib。

### 5.2 firn — 自適應 visibility timeout（HIGH priority, TRIVIAL）

**問題**：firn 的 zombie detection 用固定 cutoff，但 LLM thinking p95 變化大。

**做法**：在 `src/firn/tasks/dispatcher.py` 加 `adaptive_cutoff()`：

```python
def adaptive_cutoff(p95_latency_sec: float | None = None) -> float:
    """Return heartbeat cutoff for zombie detection.

    Strategy: max(60s, 3 * p95_latency_sec).
    Falls back to 120s if no latency data.
    """
    if p95_latency_sec is None:
        return 120.0
    return max(60.0, 3.0 * p95_latency_sec)
```

把 dispatcher 的 `cutoff` 參數從 config 改為呼叫 `adaptive_cutoff()`，並把 `TurnsLogger` 的 step duration 接成 sliding window 更新 p95。

**難度**：TRIVIAL。~30 LOC。

**付費 API**：不需要。

### 5.3 firn — `step_cached` skip pattern（MEDIUM priority, MODERATE）

**問題**：firn 目前沒有「step 級 checkpoint」概念。TaskAgent 整個 step 跑完才寫 event log，crash 後**整個 step 要重跑**（包括 LLM call）。durable-agents 用 `step_cached` 讓已完成 step 跳過。

**做法**：擴充 `_append_event` 加 `event_type='step_checkpoint'`：

```python
# 在 TaskAgent.run_step() 中：
def run_step(self, task_id, step_name, fn):
    ckpt = self._conn.execute(
        "SELECT output_json FROM step_checkpoints"
        " WHERE task_id=? AND step_name=? AND completed_at IS NOT NULL",
        (task_id, step_name),
    ).fetchone()
    if ckpt:
        logger.info("step_cached", extra={"step": step_name, "task": task_id})
        return json.loads(ckpt["output_json"])

    result = fn()  # actual work, may include LLM call + tool calls
    self._conn.execute(
        "INSERT OR REPLACE INTO step_checkpoints"
        " (task_id, step_name, output_json, completed_at) VALUES (?, ?, ?, ?)",
        (task_id, step_name, json.dumps(result), time.time()),
    )
    return result
```

**Schema**：加 `step_checkpoints(task_id, step_name, output_json, completed_at)` 表 + `PRIMARY KEY (task_id, step_name)`。

**Trade-off**：要權衡「存 step output 的 cost」vs「省下重跑的 token」。可以加 `firn.yaml` 設定 `step_cache: "all" | "side-effecting" | "none"`。

**難度**：MODERATE。~80 LOC + schema + 設定 hook。

**付費 API**：不需要。

### 5.4 firn — 終端用戶文件補完（LOW priority, TRIVIAL）

**問題**：firn README 沒解釋「如果你的 task 在跑到一半時被 kill 會怎樣」。

**做法**：在 `README.md` 加「Durability」段落，引用現有 heartbeat + zombie detection（I5-I7 已實作）+ 5.1-5.3 的未來補完藍圖。

**難度**：TRIVIAL。文件。

**付費 API**：不需要。

### 5.5 managed-agents — `pending_results/` 已是 append-only JSONL

managed-agents 的 `pending_results/` 目錄事實上就是天然的 agent-resume 風格 store。如果 harness_v2 重啟，可以從 `pending_results/*.jsonl` 讀回 in-flight 任務的狀態。

**建議**（未排程，先記下）：寫一個 `recovery.py` 模組，啟動時掃描 `pending_results/`，對每個 `status=in_flight` 的 task 重新 enqueue。**MODERATE** 難度，但目前沒有明確的需求 signal，先不開工。

---

## 6. Follow-up Questions

1. **真實 replay 成功率**有沒有人量過？把 100 個 run 中途 SIGKILL，量「從對的 step 接續的比例」是 100% 嗎？這是 open measurement question。
2. **跨機 distributed claim** 有沒有 SQLite 之外的輕量方案？Postgres advisory lock 是 production 答案，但對 personal agent 太重。有沒有人做過 SQLite + LiteFS / rqlite？
3. **approval gate 的 UX**：durable-agents 的 CLI approval 看起來 engineer-friendly，但 Telegram / Discord bot 介面呢？如果 agent 跑在背景 8 小時沒人盯 CLI，HITL 就失效。
4. **LLM stochastic + deterministic replay 的 tension**：當 LLM output 不可重現，「step output cache」真的有價值嗎？還是只對 tool call 有價值？需要把 LLM step 從 durable cache 排除。
5. **durable-agents 是否能接 OTEL**：2026-07-03 OTEL GenAI semantic conventions 報告剛 cover 了 tracing，durable-agents 的 JSONL event log 能不能 emit 成 OTEL spans？這條路打通後，durability + observability 就一體了。
6. **Sutram 的「type-specific recency decay」記憶衰退**有沒有 benchmark？跟 Letta / Mem0 比起來孰優？
7. **pg_durable 的 SQL DSL** 在 production 寫久了會不會變「PL/SQL hell」？需要 6-12 個月等真實用戶痛點浮現才知道。

---

### 原始來源

1. `https://github.com/temporalio/temporal` — REPO — HIGH — Industry standard durable execution platform, 21,778 ⭐, event sourcing + workflow server
2. `https://github.com/microsoft/pg_durable` — REPO — HIGH — Microsoft 2026 Postgres extension, 2,666 ⭐, "durable execution now an industry-standard pattern"
3. `https://docs.langchain.com/oss/python/langgraph/persistence` — DOCS — HIGH — LangGraph official docs on checkpointer vs store; explicit limitations (MemorySaver 不持久、PostgresSaver thread_id 限制)
4. `https://github.com/AleBrito124356/durable-agents` — REPO — HIGH — 完整 SQLite + stdlib 實作範本, ~1,000 LOC, approval gate + visibility timeout + heartbeat + idempotency + dead-letter 一次到位
5. `https://github.com/MukundaKatta/agent-resume` — REPO — HIGH — 最簡 agent-resume pattern: JSONL + fsync + 60-second quickstart, zero deps, 限制清楚寫出 (process-local lock only)
6. `https://github.com/gitstq/FlowKeeper` — REPO — MEDIUM — Python decorator 風格 + SQLite/JSON/in-memory stores, 與 pg_durable 對比表清楚
7. `https://github.com/Assylzhan-a/go-agent-reliability` — REPO — MEDIUM — Go stdlib primitives: watchdog + stuck detection + atomic checkpoint + runlock + recovery.classify, 完整 demo + transcript
8. `https://github.com/prit3010/Runback` — REPO — MEDIUM — Claude Code-specific: DAG replay + side-effect ledger, MVP 階段但設計文件完整
9. `https://github.com/ayushduttatreya/Sutram` — REPO — LOW (太複雜) — Postgres + Redis + Celery + FastAPI 全端, 對單人 agent over-engineered, 但 architecture 章節有教學價值

---

**結束語**：下一個工作日排程執行本指令。