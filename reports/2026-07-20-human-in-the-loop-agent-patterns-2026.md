# 研究報告：Human-in-the-Loop Agent Patterns 2026 — 從 Interrupt 原語到 Action Firewall

**日期**：2026-07-20
**來源數**：12 | **標籤**：#agent-architecture #human-in-the-loop #approval #gate #interrupt #safety #mcp

---

## 1. The Problem

過去兩年 AI agent 架構主流走「autonomy-first」路線：ReAct loop、AutoGPT-style planner、LangGraph state machine，模型自己規劃、自己呼叫工具、自己完成任務。但到了 2025-2026 production 部署，這條路線撞牆了：

1. **Risk gap** — Gartner 數據：74% 企業把 AI agent 視為新攻擊向量；>40% 的 agentic AI 專案會因風險控管不足而被取消（Cordum README 引用）。
2. **Destructive tool calls without oversight** — 沒有 governance layer，agent 可能在沒人注意時 `rm -rf`、`git push --force`、`ALTER TABLE DROP COLUMN`、發送不當 email、執行外部 API 扣款。
3. **Verification bottleneck** — 即使 agent 自己有反思機制（Reflexion, self-refine），「模型評估自己」在 high-stakes 場景下可信度不足。需要真人或獨立 verifier。
4. **Audit / compliance** — 金融、醫療、SOC2、HIPAA 場景需要「可重建的決策鏈」，純 autonomous agent 無法提供。

誰在解決這個問題：

- **業界 (production-grade)**：
  - Cordum (491 stars) — enterprise-grade action firewall with 3-verdict (ALLOW/DENY/REQUIRE_APPROVAL) + provenance gate
  - Phantasm (191 stars) — 開源 HITL approval layer, "approve-with-modification" pattern
  - Polos (35 stars) — AI agent runtime with Slack/UI approval
  - LangGraph (LangChain) — interrupt() + Command(resume=) 原語
  - OpenAI Agents SDK — needs_approval + interruptions + RunState
  - Claude Code (Anthropic) — PermissionRequest hook + Elicitation + permission modes
  - MCP Elicitation — 標準化 JSON-schema HITL 介面
- **學術界**：相對冷門。2026 arXiv 搜「human-in-the-loop + LLM agent」幾乎沒有專門論文，HITL 是純產業驅動的領域。學術焦點反而在 supervisory control（RL-based）、scalable oversight（debate/weak-to-strong）等更抽象問題。

**目前進展到哪？** 已從「prompt-level 詢問」演進到「typed interruption 原語 + stateful approval store + 多通道通知 + 結構化 verdict」四條並行路線；可觀察到的趨勢是 **HITL 從 prompt engineering 升級成 framework-level first-class concept**，並且 **MCP Elicitation 試圖把它標準化**。

---

## 2. Core Mechanism

四種 2026 HITL 主流實作，差別在「gate 在哪裡」、「decision 如何持久化」、「如何防 replay attack」：

### 2.1 Interrupt 原語 (LangGraph `interrupt()`)

**問題**：在 graph 中某個 node 想「暫停等真人輸入」，但又不能丟失執行狀態。

**機制**：
```python
from langgraph.types import interrupt, Command

def approval_node(state: State):
    # 1. 暫停 + 序列化 state via checkpointer
    approved = interrupt("Approve this $5000 refund?")
    # 2. resume 時 Command(resume=...) 變成 approved 的值
    return {"approved": approved}

# Resume（從 Telegram / web UI / CLI 收到人類回應後）
config = {"configurable": {"thread_id": "refund-123"}}
graph.invoke(Command(resume=True), config=config)
```

**關鍵 insight**：`interrupt()` 把「等待」變成 framework 的 first-class 概念，state 由 checkpointer 持久化（Postgres/SQLite），同一個 `thread_id` resume 就是「繼續那一段對話」，不需要重跑前面的 node。

**致命 pitfall（LangGraph 官方明示）**：**node 在 interrupt() 前不能有副作用**，因為 resume 時整個 node 會從頭重跑：

```python
# ❌ Bad — 創建 audit_log 後 interrupt → resume 時重複創建
def bad_node(state):
    audit_id = db.create_audit_log({...})  # 重複跑
    approved = interrupt("Approve?")
    return {"approved": approved, "audit_id": audit_id}

# ✅ Good — interrupt 之後才做副作用
def good_node(state):
    approved = interrupt("Approve?")
    if approved:
        db.create_audit_log({...})  # 只跑一次
    return {"approved": approved}
```

**Four rules of interrupts**（LangGraph 官方）：
1. Don't wrap `interrupt()` in try/except
2. Don't reorder `interrupt()` calls within a node
3. Don't return complex values in `interrupt()` calls（要 JSON-serializable）
4. Side effects called before interrupt must be idempotent

> **對 firn 的含意**：firn 的 turn loop 還沒實作 checkpoint 持久化（看 `agents/task.py`），如果要實作 interrupt-based HITL，**必須先解決 state persistence + idempotency** 兩件事，否則會落入同樣坑。

### 2.2 Per-Tool Approval (OpenAI Agents SDK)

**問題**：不是每個 tool call 都要人批准，但要能在「危險 tool 上」自動加 gate，且支援 programmatic approval。

**機制**：
```python
from agents import Agent, function_tool

@function_tool(needs_approval=True)
async def cancel_order(order_id: int) -> str:
    return f"Cancelled order {order_id}"

@function_tool(needs_approval=requires_review)  # callable per call
async def send_email(subject: str, body: str) -> str:
    return f"Sent {subject}"

# Runner 自動偵測 → pause → RunResult.interruptions 包含 ToolApprovalItem
result = await Runner.run(agent, "Cancel order 123")
if result.interruptions:
    state = result.to_state()
    state.approve(result.interruptions[0])  # 或 state.reject(...)
    final = await Runner.run(agent, state)
```

**四大設計選擇**：

1. **`needs_approval=True` (always)** vs **`needs_approval=callable`**（per-call 動態判斷）— 例如 `requires_review` 只在 subject 含 "refund" 時觸發批准。
2. **Manual interruptions** vs **automatic approval callbacks** — ShellTool 的 `on_approval` 可以直接在程式內批准，不暴露給人（適合 CI/CD 場景）。
3. **RunState serialize/deserialize** — `state.to_json()` / `state.from_json()`，可以把 paused run 寫進 DB，下次從任何地方 resume。**比 LangGraph 的 thread_id 更明確**。
4. **Sticky decisions** — `state.approve(item, always_approve=True)` 把這個批准綁定到該 tool 在這個 run 的未來呼叫，避免逐次確認。

**MCP integration**：
- Local MCP servers: `MCPServerStdio(require_approval=...)`
- Hosted MCP servers: `HostedMCPTool(tool_config={"require_approval": "always"}, on_approval_request=...)`

> **對 firn 的含意**：firn 的 MCP registry（`firn/mcp/registry.py`）目前沒有 `require_approval` 概念。GAP-MCP-001 (2026-06-06) 已經標記 MCP defense layer 缺失，這個 pattern 是具體實作指引。

### 2.3 Before/During/Across 三階段框架 (Cordum)

**問題**：HITL 不是只有「執行前批准」，要覆蓋 agent 整個 lifecycle 才有效。

**機制**：

| 階段 | 內容 | Cordum 實作 |
|------|------|-------------|
| **BEFORE** | Policy evaluation + safety gating + human approval | Declarative YAML/JSON policies，policy engine 評估每個 tool call request |
| **DURING** | Real-time monitoring + circuit breaker + live approvals | Safety kernel 即時監控 agent run，可在 step-level 中途批准/打斷 |
| **ACROSS** | Fleet health + audit trail + optimization | Audit log 含完整 chain of thought、capability-based routing、fleet dashboard |

**Cordum 的 3 verdict**：

```yaml
# Example workflow
- topic: job.demo-quickstart.delete-all
  verdict: DENY  # 自動拒絕危險操作
- topic: job.demo-quickstart.greet
  verdict: ALLOW  # 自動通過
- topic: job.demo-quickstart.admin
  verdict: REQUIRE_APPROVAL  # 標記給人類批准
```

**ProvenanceGate — 防止 replay attack**：

> "Approval provenance is **resolved-only**: destructive retries must have a matching approved approval record and a canonical resolved approval audit event for the same tenant/ref/hash. Requested-only audit rows are lifecycle context, **not proof that the action was approved**."

這是一個 production-grade 的關鍵細節：**「request approval」≠「approval approved」**。如果只用 `requested` 狀態作為 allow 依據，攻擊者可以偽造 approval request 來 bypass gate。Cordum 強制要求 approval **resolve 到 audit event + tenant + ref + hash 四元組匹配**。

**Cordum Edge — Claude Code 的 client-side hook**：

```bash
cordumctl edge claude
# 啟動 Claude Code 時自動注入 PreToolUse hook
# 所有 tool call 經過 cordum-agentd 評估
# Read → ALLOW
# Edit/Write → REQUIRE_APPROVAL
# Bash(rm *) → DENY
```

> 對 firn 的含意：Cordum Edge 是「在外部 agent client 加 governance layer」的成功範例。firn 也可以對外部 CLI agent（Claude Code, Aider, Codex CLI）包一層 interceptor。

### 2.4 "Approved With Modification" Pattern (Phantasm)

**問題**：現實中很多時候人類不想「拒絕」整個 action，只是想「改一個參數」再批准 — 例如 agent 要發 email 但收件人寫錯、想取消 order 但 order_id 打錯。

**機制**（Phantasm README）：

```python
# Agent 送出 approval request
phantasm.request_approval(
    action="send_email",
    params={"to": "all@company.com", "subject": "Q3 Report", "body": "..."}
)

# Human approver 在 dashboard 看到後可以：
# - approve as-is
# - reject
# - ✅ approved with modifications: 改成 to="exec@company.com" 後批准
```

**Fallback 機制**（Phantasm 文件，列出實務必備）：

1. Set timeout for approval request（依 action urgency 決定 5 分鐘 / 1 小時 / 24 小時）
2. Create fall-back actions for timed-out / rejected requests（abort / retry / escalate to senior approver）
3. Retry if approver unavailable
4. Notify via email if no approver available

> 對 firn 的含意：firn 目前沒有「approval timeout + fallback action」的概念。如果未來 Telegram approval 卡住（Hestia 睡覺、手機沒電），agent 會無限等待 — 必須設 timeout + fallback。

### 2.5 MCP Elicitation — 標準化 HITL 介面

**問題**：HITL 介面各家自搞 — LangGraph 用 interrupt(), OpenAI 用 interruptions, Anthropic 用 PermissionRequest hook, MCP servers 各自不同。沒有標準。

**MCP 2026 spec 提出的標準介面**：

```json
// Server → Client request
{
  "jsonrpc": "2.0",
  "method": "elicitation/create",
  "params": {
    "message": "Please provide your GitHub username",
    "requestedSchema": {
      "type": "object",
      "properties": {"name": {"type": "string"}},
      "required": ["name"]
    }
  }
}

// User response
{
  "result": {"action": "accept", "content": {"name": "octocat"}}
}
// or {"action": "decline"}  // 完全拒絕
// or {"action": "cancel"}   // 撤銷整個 request
```

**為何這對未來重要**：

- **Schema validation** — `requestedSchema` 是 restricted JSON Schema，client UI 可以自動產生表單欄位
- **Trust & Safety boundary** — Spec 明確禁止 server 用 elicitation 詢問 sensitive info（password、SSN、API key）
- **Capability declaration** — Client 必須在 init 時宣告 `"capabilities": {"elicitation": {}}` 才能接收
- **3-way action** — accept / decline / cancel 區分「拒絕這個問題」vs「取消整個請求」，比 simple yes/no 更細緻

> 對 firn 的含意：firn 已經是 MCP client + 支援 MCP servers（`firn/mcp/registry.py`）。如果 firn 要讓 MCP server 在 tool call 時請求使用者輸入，應該實作 elicitation client side — 不是自己搞一套。

---

## 3. Why It Matters / Applications

這個進步代表 AI agent 領域從 **「能不能完成任務」** 進入 **「能不能被信任地部署」** 的階段：

1. **Enterprise adoption blocker 解除** — Gartner 報告 40% agentic AI 專案取消的主因是 risk control 不足。Cordum/Polos/Phantasm 這類框架把「把 agent 放進 production」的最後一塊拼圖補上。
2. **HITL 從 prompt hack 變 framework primitive** — 2022 時期 HITL 是「在 prompt 裡寫『如果使用者說 stop 就停』」；2026 HITL 是 framework-level first-class concept（LangGraph `interrupt()`, OpenAI `interruptions`, Claude Code `PermissionRequest` hook, MCP `elicitation/create`）。
3. **MCP 標準化跨框架 HITL** — 2026 MCP spec 加入 Elicitation 後，**不同 framework 的 agent 都可以用同一個介面向人類請求輸入**，大幅降低整合成本。
4. **Security-by-architecture 範式** — ProvenanceGate（resolved-only audit event + tenant/ref/hash matching）證明 HITL 不只是 UX 問題，更是 security 問題。Cordum 把這個概念具體化。
5. **Cost / time 效率** — Polos 強調 "Paused agents consume zero compute" — 不是「等待人類批准時還在燒 API quota」，是真的 pause、不消耗 token。這對長跑 agent 很重要。

對 firn / managed-agents / Hermes 的具體衝擊：

- **firn** 目前 turn loop 是「連續跑直到任務完成」模型，沒有 pause-for-human 原語。如果要支援長時間任務（多步驟跨日）或「destroy action 需要 approval」，必須加 interrupt primitive。
- **managed-agents** 是 batch runner，本身不需要 HITL（沒有「等真人批准」場景），但如果未來要支援「批次中某些高風險 step 需要人類批准」，可以借鏡 Cordum 的 policy engine。
- **Hermes OTP gate** 已經實作 Step 0-2（`otp_gate.py` + `/otp` command + `resolve_gateway_approval` 串接），但 Step 3（`@require_otp` decorator 應用於高風險 tool）延期待辦 — 這是 Hermes 自己的 HITL 缺口。

---

## 4. Limitations / Honest Assessment

每個機制都有坑，誠實列出：

### 4.1 Idempotency 仍是大坑（LangGraph 自己承認）

官方明示：interrupt 前不能有副作用。但實務上很多 agent node 本質就是「call API → 用結果決策」，把 API call 移到 interrupt 後會破壞原本邏輯。解法是「把副作用搬到另一個 node」，但這需要改寫整個 graph 結構。

**我們的獨立評估**：firn 目前沒有 checkpoint 機制，要做 interrupt-based HITL 必須先解決：(a) state persistence、(b) node 重跑的冪等性、(c) 跨 resume 的 context 一致性。三件事缺一不可。

### 4.2 "Approved with modifications" 的 trust boundary

Phantasm 的 approve-with-edit 模式很靈活，但 **approver 改的參數不會經過原本 policy 重新驗證**。例如 agent 送出 `email to: all@company.com`，approver 改成 `to: ceo@company.com` — 後者可能正好在 DPO 名單上、是 OK 的；但改成 `to: all@external.com` 就 leak 資料了。

**我們的獨立評估**：Phantasm 沒有 proof 顯示 modified-approval 會重新跑 policy 評估。firn 如果實作這個 pattern，必須在 approval handler 裡 **重新跑 safety check** — 不能信任 approver 改過的參數。

### 4.3 Replay attack 防禦 (Cordum ProvenanceGate) 是必要 not optional

很多 HITL 系統把「approval request 發出」視為「approval granted」，這是嚴重漏洞。Cordum 強制 resolved-only audit event + tenant + ref + hash 四元組匹配是必要設計。

**我們的獨立評估**：Hermes OTP gate 目前只有 in-memory `_pending` dict（`otp_gate.py:11`），沒有 audit log。如果重啟 gateway，pending approval 全部遺失 — 對 short-lived approval 沒事，但對 long-running 任務會出問題。需要補 disk-backed store。

### 4.4 MCP Elicitation 的限制（官方 spec 明示）

> "Servers **MUST NOT** use elicitation to request sensitive information."

但這個 spec rule 無法強制執行 — 惡意 server 還是會要求 user 輸入 API key 或 password。Elicitation 的 trust boundary 仍依賴 **client UI 顯示「which server is requesting」** — 沒實作這個 UI 就是 zero defense。

**我們的獨立評估**：firn 應該在每次收到 elicitation request 時清楚標明「這個請求來自哪個 MCP server」，並提供「decline all future elicitation from this server」選項。

### 4.5 HITL 在 autonomous agent 生態是退潮而非主流

有個反主流觀察：**真正成功的 autonomous agent 反而是不需要 HITL 的 agent**（Computer Use 2.0、Agentic Coding agent、CI/CD auto-fix），HITL 是「**還沒信心完全 autonomous 的中間態**」。當 agent reliability 達到某個 threshold，HITL overhead 反而會是競爭劣勢。

**我們的獨立評估**：firn 應該 dual-track：
- Track A: 加 HITL gate 讓「目前還不信任」的 tool（rm, push --force, email）有 safety net
- Track B: 持續推進 self-verification、reducing human oversight 的依賴（不要把 HITL 當 default path）

### 4.6 Phantasm 的 approver modify 機制有 UX 漏洞

Phantasm README 顯示 approver 可以「approve with modifications」但沒有說 **modify 後的 audit log 是否區分「original request」vs「modified approval」**。實務上如果出事，audit log 必須清楚標記哪個 field 被誰改了，否則 compliance 會失敗。

### 4.7 學術界冷門 ≠ 不重要

2026 arXiv 對「human-in-the-loop LLM agent」幾乎沒有專門論文，這個現象本身值得反思。可能原因：
1. HITL 是「應用導向」問題，學術界不發這類 paper
2. HITL 在 RL 領域早已研究（interactive RL, TAMER），學術界認為「agent + HITL」只是應用
3. 學術界更關注 scalable oversight（用弱監督者監督超人類 AI），HITL 是 subset

**我們的獨立評估**：firn 開發時不應該期待學術 paper 給指引，**產業 framework（LangGraph / OpenAI / Claude Code / MCP）是真正的 source of truth**。

---

## 5. Actionable for Our Projects

### 5.1 firn 改進（直接對應 6/6 architectural debt + 6/14 A2A 報告的缺口）

| 優先級 | 工作 | 難度 | 具體步驟 |
|--------|------|------|---------|
| **P0** | **Interrupt primitive + checkpoint persistence** | HARD | (1) 在 `firn/agents/task.py` 加 `interrupt(payload)` 函數 + state snapshot via SQLite；(2) 實作 `resume(thread_id, value)` 經 gateway；(3) 套用 LangGraph 四 rules（idempotency、no try/except、JSON-serializable、no reorder）。 |
| **P0** | **Per-tool approval gate** | MODERATE | 在 `firn/tools/schemas/*.py` 加 `requires_approval: bool` 欄位；`firn/tools/executor.py` 在執行前檢查 → 若需要則 raise `ApprovalRequired` exception → gateway 攔截 → 顯示 approval UI → resume。對應 GAP-MCP-001。 |
| **P1** | **MCP Elicitation client support** | MODERATE | `firn/mcp/registry.py` 偵測 server 是否有 `capabilities.elicitation`；有則 forward `elicitation/create` 到 gateway；UI 顯示 server name + request payload + accept/decline/cancel。 |
| **P1** | **ProvenanceGate — approval audit log** | MODERATE | 在 SQLite 加 `approval_log` table：`tenant_id, action_ref, action_hash, requested_at, resolved_at, approver_id, decision, payload`；所有 allow decision 必須對應 resolved row；對應 Cordum ProvenanceGate 模式。 |
| **P1** | **Approval timeout + fallback** | MODERATE | gateway 維護 `pending_approvals: Dict[token, deadline]`；定時掃描過期 → 觸發 fallback policy（abort / retry / auto-deny）；fallback policy 在 `firn/config.py` 設。對應 Phantasm 實務建議。 |
| **P2** | **Approve-with-modification + re-validate** | HARD | approval UI 讓 approver 改 action params → 修改後重新跑 safety check → 通過才真的執行；audit log 區分 `original_payload` vs `modified_payload` vs `modifier_id`。對應 Phantasm 模式但加強 trust boundary。 |
| **P2** | **"before/during/across" three-stage logging** | MODERATE | 區分 `before_action_log` (policy eval 結果)、`during_action_log` (live monitoring events)、`across_action_log` (full trace)；dashboard 顯示三層視圖。對應 Cordum framework。 |
| **P3** | **NEGATIVE-SPACE：不要做的事** | — | 不做 complete policy DSL（YAML/JSON 太複雜，先 hardcode Python function）；不做 cross-tenant approval routing（單用戶 firn 不需要）；不做 model-based approval suggestion（會繞過 human override 的意義）。 |

### 5.2 managed-agents 改進（不直接需要，但可借鏡）

managed-agents 是 batch runner，HITL 不是核心需求，但以下可考慮：

| 優先級 | 工作 | 難度 | 具體步驟 |
|--------|------|------|---------|
| **P2** | **Batch 內 destructive step 標記** | TRIVIAL | 在 `core/v2/actions/*.py` 加 `RISK_LEVEL: Literal["safe", "modify", "destructive"]`；batch config 可設 `require_approval_for: ["destructive"]`；啟動 batch 時若有 destructive step 先 summary 等使用者確認。 |
| **P3** | **Checkpoint partial resume** | MODERATE | 借用 LangGraph thread_id 概念；batch run 中斷後可從某個 step resume；對應 Phantasm "approved with modifications" 精神（不是重頭跑）。 |

### 5.3 Hermes OTP gate 補完（對應 5/28 WS-028 部分完成）

| 優先級 | 工作 | 難度 | 具體步驟 |
|--------|------|------|---------|
| **P1** | **完成 Step 3 — `@require_otp` decorator** | MODERATE | 找 3-5 個高風險 tool (e.g., `delete_database_record`, `send_external_email`, `push_to_main`) 加 decorator；trigger OTP flow → blocked until verify。延宕 2 個月，應該補完。 |
| **P1** | **OTP store 從 in-memory 升級 disk-backed** | TRIVIAL | `_pending` dict 加 JSON file fallback；`~/.hermes/state/otp_pending.json`；boot 時 load；對應 Cordum ProvenanceGate 精神（不能重啟就掉）。 |
| **P2** | **Approval 統一 audit trail** | MODERATE | 把 OTP approval + tool exec event 串到 single audit log；對齊 7/3 OTel GenAI semantic conventions。 |

### 5.4 學習 / 知識庫

- 寫一篇 `references/human-in-the-loop-patterns-2026-07-20.md` 整理 LangGraph `interrupt()`, OpenAI `interruptions`, Claude Code `PermissionRequest`, MCP `elicitation/create` 四大介面的 schema 對照表（給未來 debug HITL issue 時快速查）。
- 把 Cordum Before/During/Across 框架納入 firn observability 章節。

---

## 6. Follow-up Questions

下次研究可追蹤的方向：

1. **MCP Elicitation 2026 H2 採用率** — 目前還是 spec 階段（"newly introduced in this version... design may evolve"），等 6 個月看哪些 MCP server / client 真的實作。
2. **Scalable oversight 對 self-supervised HITL** — Anthropic 2024 weak-to-strong paper 顯示可以用弱模型監督強模型，這對 HITL 是另一條路線（不是人類而是 AI supervisor）。研究「AI-supervised AI」對 firn 的含意。
3. **HITL in agent benchmarks** — 目前 SWE-Bench、GAIA、BrowseComp 全部是 fully-autonomous evaluation。HITL 對 agent 表現的 marginal lift 沒人量化過（hit by 5%? 20%? regression -10% if human confusing?）。
4. **Cordum 等 enterprise framework 是否提供 self-hosted / open-core 版本給個人開發者用** — 目前 Cordum 是 BUSL-1.1 license（source-available 但非 OSI），個人 / 小團隊用可能有商業限制。
5. **HITL 的 UX 設計** — Telegram / Slack approval 適合小決策，但長 context（>1000 token payload）人類無法在 IM 介面 review。需要 web-based diff viewer。哪些 framework 提供這個？
6. **Approval fatigue** — 真人每天 approve/reject 50+ 次會麻木，可能 click through 危險 action。是否有 best practice 設計減少 fatigue？Phantasm 提到「load balancer for multiple approvers」但沒細節。
7. **Audit log 與 7/3 OTel GenAI semantic conventions 的整合** — 7/3 報告的 OTel convention 還沒定義 HITL-specific span（approval_requested, approval_resolved）。值得研究 OTel 是否會在 2026 H2 加入這些 attribute。

---

### 原始來源

1. https://github.com/cordum-io/cordum (491 ⭐) — REPO — HIGH — Enterprise Agent Control Plane, 3-verdict (ALLOW/DENY/REQUIRE_APPROVAL), Before/During/Across framework, ProvenanceGate for replay attack defense.
2. https://github.com/edwinkys/phantasm (191 ⭐) — REPO — HIGH — Open-source HITL approval layer with "approve with modifications" pattern, load balancer for approvers, web dashboard.
3. https://github.com/hyf020908/langgraph-agentops-studio (108 ⭐) — REPO — HIGH — LangGraph-native reference implementation with StateGraph + interrupt + checkpoint + policy governance + HITL approval gate + reviewer/rework/escalate workflow.
4. https://github.com/polos-dev/polos (35 ⭐) — REPO — HIGH — Open-source AI agent runtime; sandboxed + durable + HITL approvals + OTel tracing; "Paused agents consume zero compute".
5. https://github.com/deepset-ai/hitl-hayhooks-redis-openwebui (9 ⭐) — REPO — MEDIUM — Redis-based HITL implementation for Haystack Agents integrated with Open WebUI.
6. https://github.com/gbFinch/agentic-orchestration (13 ⭐) — REPO — MEDIUM — Deterministic agentic workflow with critic-based quality gates + human approvals + resumable execution.
7. https://github.com/anikamin940/hitl-agent-ts (10 ⭐) — REPO — MEDIUM — TypeScript HITL: pause for approval, multi-approver gates, timeouts, audit-friendly stores, Slack/webhook notify.
8. https://docs.langchain.com/oss/python/langgraph/interrupts — OFFICIAL DOCS — HIGH — LangGraph `interrupt()` primitive, `Command(resume=)` API, four rules of interrupts (idempotency critical), 5 HITL patterns (approve/reject, multiple interrupts, review-and-edit, tool interrupt, validation).
9. https://openai.github.io/openai-agents-python/human_in_the_loop/ — OFFICIAL DOCS — HIGH — OpenAI Agents SDK HITL: `needs_approval` per-tool, `interruptions` unified interface, `RunState` serialize/deserialize, sticky decisions, programmatic approval callbacks, MCP integration.
10. https://docs.claude.com/en/docs/claude-code/hooks — OFFICIAL DOCS — HIGH — Claude Code hook lifecycle: PreToolUse/PostToolUse/PermissionRequest/Elicitation/TaskCompleted. PermissionRequest hook can modify input (`updatedInput`), add permission rules, change mode (plan/auto/acceptEdits).
11. https://docs.claude.com/en/docs/claude-code/permissions — OFFICIAL DOCS — HIGH — Tiered permission system: deny > ask > allow precedence; Bash risk level (Low/Med/High via Ctrl+E); PreToolUse hook as override; permission modes (default/auto/acceptEdits/dontAsk/bypassPermissions/plan).
12. https://modelcontextprotocol.io/docs/concepts/elicitation — OFFICIAL SPEC — HIGH — MCP Elicitation standard: server → client `elicitation/create` with `requestedSchema` (restricted JSON Schema), 3-way response (accept/decline/cancel), trust boundary (no sensitive info), capability declaration.
13. ~/.hermes/skills/automation/hermes-otp-human-in-the-loop/SKILL.md — INTERNAL — HIGH — Hermes WS-028 OTP gate: in-memory `_pending` dict + Telegram `/otp` command + `resolve_gateway_approval` integration; Step 3 (`@require_otp` decorator) 延期待辦.
14. ~/.hermes/scripts/otp_gate.py — INTERNAL CODE — HIGH — `generate/verify/approve_token/cleanup/pending_count` API; 6-hex-digit OTP, 5-min TTL, single-use; 缺 disk-backed store + audit log.

---

**下一個工作日排程執行本指令。**