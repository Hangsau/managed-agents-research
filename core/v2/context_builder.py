"""Build OpenAI-style message lists from event history."""
import json
from .config import get_system_prompt, MAX_HISTORY_EVENTS, MAX_TOOL_RESULT_CHARS


def build_messages(history: list[dict], correction: str = "") -> list[dict]:
    """Convert event history into OpenAI chat messages.

    Rules:
      - System prompt first.
      - Only last MAX_HISTORY_EVENTS events included.
      - Skip unparseable planner_decision.
      - Skip error events entirely.
      - read_file results get a compact summary.
      - Other tool_result payloads are JSON-truncated to MAX_TOOL_RESULT_CHARS.
      - Optional correction appended as final user message.
    """
    messages = [{"role": "system", "content": get_system_prompt()}]

    # Slice to last N events
    recent = history[-MAX_HISTORY_EVENTS:] if len(history) > MAX_HISTORY_EVENTS else history

    for ev in recent:
        etype = ev.get("type")
        payload = ev.get("payload", {})

        if etype == "user_goal":
            goal = payload.get("goal", "")
            messages.append({"role": "user", "content": f"GOAL: {goal}"})

        elif etype == "planner_decision":
            content = payload.get("content") or payload.get("raw")
            tool_calls = payload.get("tool_calls")
            if tool_calls:
                msg = {"role": "assistant", "content": content, "tool_calls": tool_calls}
                messages.append(msg)
            elif content:
                messages.append({"role": "assistant", "content": content})
            else:
                # Skip empty planner decisions
                continue

        elif etype == "tool_result":
            action = payload.get("action", "")
            result = payload.get("result", {})
            tool_call_id = payload.get("tool_call_id")

            if action == "read_file" and isinstance(result, dict) and "content" in result:
                summary = {
                    "action": "read_file",
                    "path": payload.get("args", {}).get("path", "unknown"),
                    "lines": result.get("lines", "?"),
                    "bytes": result.get("bytes", "?"),
                    "truncated": result.get("truncated", False),
                    "preview": (
                        result["content"][:100] + "..."
                        if len(result["content"]) > 100
                        else result["content"]
                    ),
                }
                content = json.dumps(summary, ensure_ascii=False)
            else:
                # Emit payload JSON truncated to max chars
                payload_json = json.dumps(payload, ensure_ascii=False)
                if len(payload_json) > MAX_TOOL_RESULT_CHARS:
                    payload_json = payload_json[:MAX_TOOL_RESULT_CHARS] + "..."
                content = payload_json

            if tool_call_id:
                messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": content})
            else:
                messages.append({"role": "user", "content": f"RESULT: {content}"})

        elif etype == "error":
            # Errors are logged to DB only; do not feed back to LLM context.
            continue

        # Unknown event types are silently ignored.

    if correction:
        messages.append({"role": "user", "content": correction})

    return messages
