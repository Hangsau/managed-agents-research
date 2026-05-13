"""Main turn loop: plan -> execute -> persist."""
import json, time
from datetime import datetime, timezone

from . import config, db, llm, context_builder, action_executor


def _signature(action: str, args: dict) -> str:
    return json.dumps({"action": action, "args": args}, sort_keys=True)


def _extract_path(action: str, args: dict) -> str | None:
    if action in ("read_file", "write_file") and "path" in args:
        return args["path"]
    return None


def _detect_stuck(history: list, action: str, args: dict) -> dict | None:
    """Return error dict if stuck, else None."""
    recent_tools = [e for e in history if e.get("type") == "tool_result"][-4:]
    current_sig = _signature(action, args)
    dup_count = sum(
        1
        for e in recent_tools
        if _signature(
            e["payload"].get("action", ""), e["payload"].get("args", {})
        )
        == current_sig
    )
    if dup_count >= 2:
        return {
            "error": "stuck loop",
            "msg": f"Repeated {action} too many times",
        }

    current_path = _extract_path(action, args)
    if current_path:
        path_dups = sum(
            1
            for e in recent_tools
            if _extract_path(
                e["payload"].get("action", ""), e["payload"].get("args", {})
            )
            == current_path
        )
        if path_dups >= 2:
            return {
                "error": "stuck loop",
                "msg": f"Repeated access to {current_path}",
            }
    return None


def run_turn(session_id: str, goal: str | None = None) -> dict:
    history = db.get_events(session_id)

    if goal and not history:
        db.log_event(session_id, "user_goal", {"goal": goal})
        history = [{"seq": 1, "type": "user_goal", "payload": {"goal": goal}}]

    messages = context_builder.build_messages(history)
    print(f"[{session_id}] Calling planner...")

    response = llm.call_llm(messages, tools=action_executor.TOOL_SCHEMAS)
    if response is None:
        db.log_event(session_id, "error", {"msg": "LLM returned None (likely API failure)"})
        return {"error": "llm timeout or failure"}

    choice = response.get("choices", [{}])[0]
    finish_reason = choice.get("finish_reason")
    message = choice.get("message", {})

    # Log planner decision
    planner_payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "finish_reason": finish_reason,
    }
    if message.get("content"):
        planner_payload["content"] = message["content"]
    if message.get("tool_calls"):
        planner_payload["tool_calls"] = message["tool_calls"]
    db.log_event(session_id, "planner_decision", planner_payload)

    if finish_reason == "stop":
        content = message.get("content", "")
        return {"status": "done", "summary": content} if not content.strip() else {"status": "responded", "content": content}

    if finish_reason != "tool_calls":
        db.log_event(session_id, "error", {"msg": f"Unexpected finish_reason: {finish_reason}", "response": response})
        return {"error": f"Unexpected finish_reason: {finish_reason}"}

    tool_calls = message.get("tool_calls", [])
    if not tool_calls:
        db.log_event(session_id, "error", {"msg": "finish_reason=tool_calls but no tool_calls found"})
        return {"error": "No tool calls in response"}

    # Handle the first tool call per turn (matching original single-action behavior)
    tool_call = tool_calls[0]
    action = tool_call.get("function", {}).get("name")
    args = json.loads(tool_call.get("function", {}).get("arguments", "{}"))

    # Stuck detection
    stuck = _detect_stuck(history, action, args)
    if stuck:
        db.log_event(session_id, "error", {"msg": stuck["msg"]})
        return stuck

    print(f"[{session_id}] Action: {action} | Args: {list(args.keys())}")

    # Execute with exp-backoff retry
    result = None
    max_retries = 2
    for attempt in range(max_retries + 1):
        result = action_executor.dispatch(tool_call, session_id)
        if "error" not in result or attempt == max_retries:
            break
        if result.get("blocked") or result.get("error") == "stuck loop":
            break
        wait = 2 ** attempt
        print(
            f"[{session_id}] Action {action} failed (attempt {attempt + 1}/{max_retries + 1}), "
            f"retrying in {wait}s..."
        )
        time.sleep(wait)

    db.log_event(
        session_id,
        "tool_result",
        {"action": action, "args": args, "result": result, "tool_call_id": tool_call.get("id")},
    )

    if action == "complete":
        return {"status": "done", "summary": result.get("summary", "done")}
    elif action == "ask_user":
        return {
            "status": "error",
            "message": "ask_user is not available in autonomous mode. Continue with best effort using available tools.",
        }
    else:
        return {"status": "continue", "action": action, "result_preview": str(result)[:200]}
