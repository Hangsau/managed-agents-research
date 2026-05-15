# WS-013: Session Timestamp Cache Buster — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** DeepSeek prefix cache 跨新 session 能命中 system prompt——從 ~0% 提升至大部分情況 ~100%（memory 未更新時）。

**Architecture:** 把必定變動的 `Conversation started` timestamp 從 system prompt（volatile tier）移到第一條 user message 前綴。system prompt 變成 byte-stable 跨 session（memory/profile 未變時），讓 provider prefix caching 生效。timestamp 以 `self._session_timestamp` 存為 instance attribute，由 `run_conversation` 讀取並注入。

**Tech Stack:** Python, pytest, `run_agent.py` 內部 refactor

## Planning Quality Checklist (MANDATORY — fill every field)

├── **目標（一句話）**
│   └── 兩個獨立 AIAgent instance（同 config、skip_memory）的 `_build_system_prompt()` 產出 byte-identical；「Conversation started」出現在第一條 user message 而非 system prompt

├── **前置條件檢查（3–5 項 yes/no）**
│   ├── [x] volatile_parts 盤點完成（plan-check v2 步驟 0）——timestamp 是唯一每次都變的
│   ├── [x] `conversation_history` signature 確認為 `List[Dict] = None`
│   ├── [x] injection anchor 確認為 line 12003-12004（`# Add user message`）
│   └── [x] test file anchor 確認為 line 987-990（`test_includes_datetime`）

├── **步驟清單（每步 ≤15 字）**
│   ├── 1. 改寫 behavioral test
│   ├── 2. 改寫 structural test（datetime）
│   ├── 3. 新增 session resume guard test
│   ├── 4. 建 `_session_timestamp`，從 volatile 移除
│   ├── 5. 在 run_conversation inject timestamp
│   ├── 6. 跑 test suite + gateway smoke

├── **每步的驗證方式（怎麼知道該步做完了）**
│   ├── Step 1: behavioral test FAIL（新 session system prompt ≠ 舊）
│   ├── Step 2: structural test FAIL（"Conversation started" not in user msg）
│   ├── Step 3: guard test FAIL（用 history 的 session 仍 inject）
│   ├── Step 4-5: all tests PASS
│   └── Step 6: `pytest tests/run_agent/ -x` PASS + curl gateway 200

├── **潛在卡點（至少 2 個，含對策）**
│   ├── behavioral test mock 讓 `_memory_store` 不同 → 用 `skip_memory=True` 關掉整個 volatile tier
│   └── `_session_timestamp` 沒在 `__init__` 初始化 → 加 `self._session_timestamp = None`
│   └── patch anchor 不夠 unique → 用 comment `# Add user message` + 上下文確保 uniqueness

└── **失敗時的退路**
    └── 如果 behavioral test 持續 fail（byte 不穩定），先 grep 比對 diff 找出哪段不一致 → 可能是 context tier 的 `system_message` 參數變動。退路：只移除 timestamp 不做 behavioral test，仍保留 structural test + session resume guard。

---

## STATUS

| 欄位 | 值 |
|------|-----|
| **狀態** | 🟢 設計中 |
| **目前階段** | 設計 → 實作 |
| **最後行動** | 2026-05-15: writing-plans 產出 |
| **下一步** | 交由 implement 執行 Task 1-6 |
| **阻擋** | 無 |

---

## 現況評估：原提案 vs 實際已實現

| 項目 | 狀態 | 位置 |
|------|------|------|
| timestamp 在 system prompt | ✅ 現況 | `run_agent.py:6092-6099`（volatile_parts） |
| timestamp 建構邏輯 | 保留，移位置 | 同上 → `self._session_timestamp` |
| user message injection point | — | `run_agent.py:12003-12005` |
| test_includes_datetime | 需改寫 | `tests/run_agent/test_run_agent.py:987-990` |
| behavioral test | 需新增 | 同上 |

## 分散點掃描

| 邏輯項目 | 分散位置 | 本次處理 |
|---------|---------|---------|
| `Conversation started` 字串 | `run_agent.py:6092`, `tests/.../test_run_agent.py:989-990` | 全部同步改 |
| timestamp 建構 | `run_agent.py:6090-6098` | 保留建構邏輯，只改 append target |

---

## Task 1: 寫 behavioral test（先 fail）

**Objective:** 證明兩個獨立 AIAgent 的 system prompt 目前不同（因為 timestamp），為後續 code 改動建立 RED baseline

**Files:**
- Modify: `tests/run_agent/test_run_agent.py`（在 `TestBuildSystemPrompt` class 內新增 method）

**Step 1: 新增 test**

在 `TestBuildSystemPrompt` class 內部（`test_includes_datetime` 之後，約 line 991），加入：

```python
    def test_system_prompt_stable_across_sessions(self):
        """Two agents with same config produce byte-identical system prompts."""
        with (
            patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("web_search")),
            patch("run_agent.check_toolset_requirements", return_value={}),
            patch("run_agent.OpenAI"),
        ):
            a1 = AIAgent(
                api_key="test-key-1234567890",
                base_url="https://openrouter.ai/api/v1",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )
            a2 = AIAgent(
                api_key="test-key-1234567890",
                base_url="https://openrouter.ai/api/v1",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )
            p1 = a1._build_system_prompt()
            p2 = a2._build_system_prompt()
            assert p1 == p2, f"System prompts differ!\n=== P1 ===\n{p1}\n=== P2 ===\n{p2}"
```

**Step 2: 跑 test 確認 fail**

```bash
pytest tests/run_agent/test_run_agent.py::TestBuildSystemPrompt::test_system_prompt_stable_across_sessions -xvs
```

預期: **FAIL** — timestamp 不同 → `p1 != p2`

---

## Task 2: 改寫 structural test `test_includes_datetime`

**Objective:** 改寫現有 test：assert timestamp 在 user message 而非 system prompt

**Files:**
- Modify: `tests/run_agent/test_run_agent.py:987-990`

**Step 1: 改寫 test**

Replace line 987-990:

```python
    def test_includes_datetime(self, agent):
        prompt = agent._build_system_prompt()
        # Should contain current date info like "Conversation started:"
        assert "Conversation started:" in prompt
```

→ 改為：

```python
    def test_includes_datetime(self, agent):
        """Timestamp should NOT be in system prompt; should be available via _get_session_timestamp()."""
        prompt = agent._build_system_prompt()
        assert "Conversation started:" not in prompt, \
            "Timestamp should not be in system prompt"
        ts = agent._get_session_timestamp()
        assert ts is not None, "Agent should return a valid timestamp"
        assert "Conversation started:" in ts
```

**Step 2: 跑 test 確認 fail**

```bash
pytest tests/run_agent/test_run_agent.py::TestBuildSystemPrompt::test_includes_datetime -xvs
```

預期: **FAIL** — 目前 timestamp 還在 system prompt 中

---

## Task 3: 新增 session resume guard test

**Objective:** session 恢復時不應在第一條 user message 注入 timestamp

**Files:**
- Modify: `tests/run_agent/test_run_agent.py`（在 Task 1 的 test 之後）

**Step 1: 新增 test**

```python
    def test_no_duplicate_timestamp_on_resume(self):
        """Session with conversation_history should NOT inject timestamp into user message."""
        with (
            patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("web_search")),
            patch("run_agent.check_toolset_requirements", return_value={}),
            patch("run_agent.OpenAI"),
            patch.object(AIAgent, "_api_chat", return_value={
                "choices": [{"message": {"role": "assistant", "content": "ok"}}]
            }),
        ):
            agent = AIAgent(
                api_key="test-key-1234567890",
                base_url="https://openrouter.ai/api/v1",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )
            # Simulate session resume with existing history
            history = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
            result = agent.run_conversation(
                user_message="继续",
                conversation_history=history,
            )
            # The user_message content should NOT contain a timestamp prefix
            # It should be the original message
            msgs = result.get("messages", [])
            first_user = next((m for m in msgs if m["role"] == "user"), None)
            assert first_user is not None
            # On resume, the user message should be clean (no timestamp injected)
            assert "Conversation started:" not in first_user["content"], \
                f"Timestamp should not be in resumed session user message: {first_user['content'][:200]}"
```

**Step 2: 跑 test 確認 fail**

```bash
pytest tests/run_agent/test_run_agent.py::TestBuildSystemPrompt::test_no_duplicate_timestamp_on_resume -xvs
```

預期: **FAIL** — 目前沒有 guard，timestamp 仍在 system prompt 不在 user message。但這個 test 測的是 run_conversation 層，要等 Task 5 實作後才會真正 pass。

---

## Task 4: 重構 timestamp — 從 volatile_parts 移到 lazy method

**Objective:** timestamp 不再留在 `_build_system_prompt_parts` 的 volatile tier，改為獨立 lazy method `_get_session_timestamp()`，由 `run_conversation` 在使用前呼叫。這樣 injection 發生在 user_msg 建構時就能拿到 timestamp。

> ⚠️ **順序修正（plan-review）：** 原設計在 `_build_system_prompt_parts` 中設定 `_session_timestamp`，但 `_build_system_prompt()` 在 line 12040 才呼叫，晚於 line 12003 的 user_msg injection。改為獨立 lazy method，在 injection 前呼叫。

**Files:**
- Modify: `run_agent.py:__init__` — 加 `self._session_timestamp = None`（搜 `_cached_system_prompt` 附近）
- Modify: `run_agent.py:6090-6099` — 移除 `volatile_parts.append(timestamp_line)`
- Modify: `run_agent.py` — 在 class 內新增 `_get_session_timestamp()` method（放 `_build_system_prompt_parts` 之後）

**Step 1: 在 `__init__` 初始化新 attribute**

搜 `self._cached_system_prompt` 的初始化行，在附近加一行：

```python
        self._cached_system_prompt = None
        self._session_timestamp = None  # WS-013: lazy-built, injected into first user msg
```

**Step 2: 從 `_build_system_prompt_parts` 移除 timestamp**

Line 6099 `volatile_parts.append(timestamp_line)` → 刪除該行，改為注釋：

```python
        timestamp_line = f"Conversation started: {now.strftime('%A, %B %d, %Y %I:%M %p')}"
        if self.pass_session_id and self.session_id:
            timestamp_line += f"\nSession ID: {self.session_id}"
        if self.model:
            timestamp_line += f"\nModel: {self.model}"
        if self.provider:
            timestamp_line += f"\nProvider: {self.provider}"
        # WS-013: timestamp is NO LONGER in volatile_parts.
        # Use self._get_session_timestamp() instead — keeps system prompt byte-stable.
```

**Step 3: 新增 `_get_session_timestamp()` method**

在 `_build_system_prompt_parts` method 之後（約 line 6105 之後），新增：

```python
    def _get_session_timestamp(self) -> Optional[str]:
        """Lazy-build the session timestamp string.

        Built once per AIAgent instance, then cached.  Returns None if
        essential fields (model/provider) aren't set yet.

        WS-013: Extracted from _build_system_prompt_parts so it can be
        called before user_msg construction in run_conversation, keeping
        the system prompt (which is built later) byte-stable.
        """
        if self._session_timestamp is not None:
            return self._session_timestamp
        from hermes_time import now as _hermes_now
        now = _hermes_now()
        ts = f"Conversation started: {now.strftime('%A, %B %d, %Y %I:%M %p')}"
        if self.pass_session_id and self.session_id:
            ts += f"\nSession ID: {self.session_id}"
        if self.model:
            ts += f"\nModel: {self.model}"
        if self.provider:
            ts += f"\nProvider: {self.provider}"
        self._session_timestamp = ts
        return ts
```

**Step 4: 跑 behavioral test**

```bash
pytest tests/run_agent/test_run_agent.py::TestBuildSystemPrompt::test_system_prompt_stable_across_sessions -xvs
```

預期: **PASS** ✓ — 兩個 agent 的 system prompt 相同（timestamp 不在 system prompt 中）

**Step 5: 跑 structural test**

```bash
pytest tests/run_agent/test_run_agent.py::TestBuildSystemPrompt::test_includes_datetime -xvs
```

預期: **PASS** ✓ — system prompt 不含 timestamp，`_get_session_timestamp()` 回傳有效字串

---

## Task 5: `run_conversation` 注入 timestamp 到 user message

**Objective:** 新 session 時，呼叫 `_get_session_timestamp()` 並把結果 prepend 到第一條 user message。Session resume（有 history）時不注入。

> ⚠️ **順序修正（plan-review）：** 注入行現在**先**呼叫 `_get_session_timestamp()`（lazy method，不依賴 `_build_system_prompt`），再建 user_msg。解決了原設計中 timestamp 在 user_msg 之後才設定的 ordering bug。

**Files:**
- Modify: `run_agent.py:12003-12005`

**Step 1: 修改 injection**

將 line 12003-12005：

```python
        # Add user message
        user_msg = {"role": "user", "content": user_message}
        messages.append(user_msg)
```

→ 改為：

```python
        # Add user message — prepend session timestamp on new sessions (WS-013)
        _ts = self._get_session_timestamp()
        _content = f"{_ts}\n\n{user_message}" if (not conversation_history and _ts) else (user_message or "")
        user_msg = {"role": "user", "content": _content}
        messages.append(user_msg)
```

**Step 2: 驗證注入順序**

- `_get_session_timestamp()` 是 lazy method，第一次呼叫時建 timestamp 並 cache 到 `self._session_timestamp`
- 新 session（`conversation_history=None`）→ guard 通過 → timestamp 注入
- 恢復 session（`conversation_history` 有值）→ guard 跳過 → 原始 user_message 不變
- 空 user_message → `user_message or ""` 確保不會出現 `"None"` 字串

**Step 3: 跑所有 test**

```bash
pytest tests/run_agent/test_run_agent.py::TestBuildSystemPrompt -xvs
```

預期: ALL PASS——
- `test_system_prompt_stable_across_sessions` PASS ✓
- `test_includes_datetime` PASS ✓
- `test_no_duplicate_timestamp_on_resume` PASS ✓
- 其他現有 test 不應受影響

---

## Task 6: Full test suite + gateway smoke

**Objective:** 確認沒有 regression，gateway 正常運作

**Step 1: 跑完整 test suite**

```bash
pytest tests/run_agent/ -x --timeout=120
```

預期: ALL PASS

**Step 2: 檢查 coverage（現有 test 不該有 functional regression）**

```bash
pytest tests/run_agent/ -q
```

確認 test count 沒有減少，所有現有 test 仍通過。

**Step 3: Gateway restart + smoke**

```bash
systemctl restart hermes-gateway
sleep 2
curl -s http://localhost:8080/health
```

預期: `{"status": "ok"}`

**Step 4: commit**

```bash
cd /root/hermes-agent
git add run_agent.py tests/run_agent/test_run_agent.py
git commit -m "fix: move Conversation started timestamp from system prompt to first user message

WS-013 — timestamp was the only volatile part that changed every session,
busting DeepSeek prefix cache.  Move it to first user message so the
system prompt stays byte-stable across sessions when memory/profile
haven't changed.

- _build_system_prompt_parts: store timestamp as self._session_timestamp
- run_conversation: prepend to first user message on new sessions only
- Tests: behavioral cross-session stability + session resume guard"
```

---

## 結構風險掃描

### 並發
兩個 process 同時跑 `_build_system_prompt_parts`？Hermes 的 AIAgent 是 per-session 的，不存在跨 process 共用 instance 的情況。
→ **回答：** 不適用。`_session_timestamp` 是 instance attribute，每個 session 獨立。

### 邊界
- **空 user_message**：`f"{timestamp}\n\n{None}"` → Python implicit conversion to `"None"` 字串。修正：用 `user_message or ""`
- **大量輸入**：prepend timestamp 只增加 ~100 chars，不影響 token limit
→ **回答：** 空 user_message 要加 `or ""` guard，已在 Task 5 code 中處理。大量輸入無影響。

### 持久化
- SQLite 中已存的 system_prompt 欄位可能包含舊格式（有 timestamp）。不會自動 migration。
- 新 session 產生的 system_prompt 不包含 timestamp。
→ **回答：** 不改 schema。舊 session 自然過期，不處理 migration。這是預期行為。

### 外部輸入驗證
`conversation_history` 來自 DB/用戶，但只用於 boolean guard（`if not conversation_history`），不 parse 內容。
→ **回答：** 不適用。timestamp 由 `hermes_time.now()` 產生，非外部輸入。

### 命令注入
不改 shell command / SQL / regex。
→ **回答：** 不適用。

### 跨狀態一致性
沒有新增 status 值或 state 欄位。
→ **回答：** 不適用。

---

## 驗收對應

| 檢出風險 | 驗收測試 |
|---------|---------|
| 邊界：空 user_message | Task 5 code 已包含 `user_message or ""`，可加 boundary test（optional） |
| 並發／持久化／外部輸入／命令注入／跨狀態 | 不適用，無對應測試 |

---

## Independent Plan Review

> Reviewed by: plan-review skill v1.3.0 | 2026-05-15T23:01 UTC | Model: deepseek-v4-pro

### Overall Assessment: 🟡 Needs Work

**Raw Score:** 75/100

**Summary:** 這個 plan 結構清晰、TDD 流程正確、6-field header 完整且 substantive。但存在一個關鍵的 correctness 問題：Task 5 在 line 12003 注入 timestamp，而 plan 本身明示 `_build_system_prompt()`（用來設定 `self._session_timestamp`）在 line 12040 才呼叫——注入發生在 timestamp 被設定之前，導致新 session 的 guard `if self._session_timestamp` 永遠為 None，timestamp 永遠不會進入 user message。此外 `user_message or ""` 的 guard 在風險掃描中聲稱已處理，但 Task 5 實際 code 並未包含。這兩個問題必須修正後方可執行。

---

### Dimension Scores

| Dimension | Score | Issue Count |
|-----------|-------|-------------|
| Completeness | 🟡 | 3 |
| Correctness | 🔴 | 2 |
| Coherence | 🟢 | 1 |
| Robustness | 🟡 | 3 |
| Efficiency | 🟢 | 0 |
| Spec Alignment | 🟢 | 0 |

---

### Critical Issues (must fix before execution)

1. **Correctness — injection ordering bug** (ref: Task 5, Step 1–2)
   → Plan states injection at line 12003, but `_build_system_prompt()` (which sets `self._session_timestamp`) is called at line 12040. On a new session, `self._session_timestamp` is `None` at injection time → guard `if not conversation_history and self._session_timestamp:` silently skips → timestamp never reaches the user message. The feature is dead on arrival.
   → **Fix:** Either (a) move injection to AFTER `_build_system_prompt()` is called, or (b) explicitly call `_build_system_prompt()` before the injection block, or (c) if `_build_system_prompt()` is already called elsewhere before `run_conversation` in the normal flow, document that call site in the plan.
   → **Affected tasks:** Task 5 (injection), Task 6 (gate smoke won't catch this — only an actual chat test would)

2. **Correctness/Robustness — `user_message or ""` guard claimed but missing** (ref: 結構風險掃描 → 邊界, Task 5 code)
   → Plan says "已在 Task 5 code 中處理" but Task 5 code has `_content = user_message` with no `or ""`. If `user_message` is `None` (unlikely in practice but possible in edge cases), f-string produces `"timestamp\n\nNone"`.
   → **Fix:** Change `_content = user_message` → `_content = user_message or ""` in Task 5 Step 1.
   → **Affected tasks:** Task 5

---

### Recommendations (improve but don't block)

1. **Completeness — gate smoke is too shallow.** Task 6 Step 3 only hits `/health`. An actual chat call (e.g., `curl -s -X POST localhost:8080/v1/chat/completions -d '{...}'`) would verify the timestamp appears in the user message, not the system prompt. Consider adding a one-shot functional smoke test.

2. **Completeness — no rollback instructions.** If gateway smoke fails after restart, what does the implementer do? Add a revert step: `git stash && systemctl restart hermes-gateway`.

3. **Robustness — `conversation_history` as empty list `[]`.** Guard `if not conversation_history` treats `[]` as falsy → injects timestamp. Is this correct? An empty history means "no prior messages" → injection is probably right, but document this intent explicitly.

4. **Coherence — guard test class placement.** Task 3's `test_no_duplicate_timestamp_on_resume` tests `run_conversation()` behavior but is placed in `TestBuildSystemPrompt`. Consider placing it in a `TestRunConversation` class or noting that `TestBuildSystemPrompt` is the pragmatic home for now since no such class exists.

5. **Efficiency — Tasks 1–3 can be written in parallel.** All three are test-only additions before any code changes. If using subagents, they could be written concurrently and merged before Task 4. Not required, but worth noting for multi-agent execution.

---

### Revised by Plan Author

[The original planner fills this in after addressing the critique]

- [ ] Critical Issue 1 addressed: [How — move injection after `_build_system_prompt()` call OR document earlier call site]
- [ ] Critical Issue 2 addressed: [How — add `or ""` guard to Task 5 code]
- [ ] Recommendation 1: [Accepted/Rejected — reason]
- [ ] Recommendation 2: [Accepted/Rejected — reason]
- [ ] Recommendation 3: [Accepted/Rejected — reason]
- [ ] Recommendation 4: [Accepted/Rejected — reason]
- [ ] Recommendation 5: [Accepted/Rejected — reason]
