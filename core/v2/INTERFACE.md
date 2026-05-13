# v2 Module Interface Contract

All modules live under `core/v2/`.

## config.py
- Exports: `DB_PATH`, `API_KEY`, `API_URL`, `MODEL`, `MODEL_FALLBACKS`, `MAX_TURNS`, `MAX_HISTORY_EVENTS`, `MAX_TOOL_RESULT_CHARS`, `MAX_THOUGHT_CHARS`, `MAX_READ_FILE_BYTES`
- Function: `get_system_prompt() -> str`

## db.py
- Function: `ensure_schema()`
- Function: `log_event(session_id: str, etype: str, payload: dict)`
- Function: `get_events(session_id: str, since_seq: int = 0, limit: int = 0) -> list[dict]`
- Function: `get_recent_tool_results(session_id: str, n: int = 4) -> list[dict]`
  - Returns last n tool_result payloads, oldest first.

## llm.py
- Function: `call_llm(messages: list[dict], max_tokens: int = 1000, tools: list[dict] | None = None) -> dict | None`
  - Uses config.MODEL + MODEL_FALLBACKS.
  - Returns raw API response dict (with `choices`, `finish_reason`, etc.) or None on total failure.

## guard.py
- Function: `check_guard(guard_script: str, args_list: list[str]) -> dict`
  - Returns `{"blocked": bool, "reason": str}`.

## actions/*.py
Each action module exposes:
- Function: `run(args: dict, session_id: str) -> dict`

Actions: bash, read_file, write_file, complete, ask_user, web_search, search_files

## context_builder.py
- Function: `build_messages(history: list[dict], correction: str = "") -> list[dict]`
  - Returns OpenAI-style messages list.
  - Rules:
    - System prompt first.
    - Include only last MAX_HISTORY_EVENTS events.
    - Skip unparseable planner_decision.
    - For planner_decision with `tool_calls`: emit assistant message with `tool_calls`.
    - For planner_decision with `content` or `raw`: emit assistant message with content.
    - For read_file tool_result: emit compact summary (action, path, lines, bytes, truncated, preview). **Do NOT suggest using bash for truncated files.**
    - For other tool_result with `tool_call_id`: emit `role: "tool"` message.
    - For other tool_result without `tool_call_id`: emit JSON truncated to MAX_TOOL_RESULT_CHARS as user message.
    - For error events: **omit from messages** (do NOT feed errors back into LLM context). Log only.
    - Append correction if provided.

## action_executor.py
- Export: `TOOL_SCHEMAS: list[dict]`
  - OpenAI-compatible function schemas for all available actions.
- Function: `run(action: str, args: dict, session_id: str) -> dict`
  - Routes action name to handler module.
- Function: `dispatch(tool_call: dict, session_id: str) -> dict`
  - Accepts a tool_call object (with `.function.name` and `.function.arguments`).
  - Parses arguments via `json.loads` and delegates to `run()`.

## turn_loop.py
- Function: `run_turn(session_id: str, goal: str | None = None) -> dict`
  - Uses db, context_builder, llm, action_executor.
  - Logic:
    1. Load history.
    2. Build messages via context_builder.
    3. Call LLM with `tools=action_executor.TOOL_SCHEMAS`.
    4. Check `finish_reason`:
       - `stop`: return content as final response.
       - `tool_calls`: dispatch first tool call via `action_executor.dispatch()`.
       - Other: log error and return error dict.
    5. Detect stuck loops (duplicate signatures, same-path dups).
    6. Execute action with exp-backoff retry.
    7. Log tool_result (including `tool_call_id`).
    8. Return status dict.

## harness_v2.py
- CLI entry. Imports turn_loop.run_turn.
