"""Smoke tests for v2 modules."""
import sys, os
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from core.v2 import context_builder, db, action_executor

def test_context_builder():
    history = [
        {"type": "user_goal", "payload": {"goal": "test"}},
        {"type": "planner_decision", "payload": {"content": '{"action":"bash"}'}},
        {"type": "tool_result", "payload": {"action": "read_file", "args": {"path": "/tmp/x"}, "result": {"content": "hello", "lines": 1, "bytes": 5, "truncated": False}}},
        {"type": "error", "payload": {"msg": "something failed"}},
    ]
    msgs = context_builder.build_messages(history)
    roles = [m["role"] for m in msgs]
    assert roles[0] == "system"
    assert "user" in roles
    assert "assistant" in roles
    for m in msgs:
        content = m.get("content", "")
        assert "something failed" not in content, "error event leaked into context"
        if "read_file" in content:
            assert "use bash" not in content.lower(), "misleading bash hint found"
    print("context_builder OK")

def test_context_builder_with_tool_calls():
    history = [
        {"type": "planner_decision", "payload": {"tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "bash", "arguments": '{"cmd":"ls"}'}}]}},
        {"type": "tool_result", "payload": {"action": "bash", "args": {"cmd": "ls"}, "result": {"stdout": "file.txt"}, "tool_call_id": "call_1"}},
    ]
    msgs = context_builder.build_messages(history)
    roles = [m["role"] for m in msgs]
    assert "assistant" in roles
    assert "tool" in roles
    print("context_builder_with_tool_calls OK")

def test_db():
    db.ensure_schema()
    db.log_event("test_session_999", "user_goal", {"goal": "unit test"})
    events = db.get_events("test_session_999")
    assert len(events) >= 1
    assert events[-1]["type"] == "user_goal"
    print("db OK")

def test_action_dispatch():
    result = action_executor.run("ask_user", {"question": "?"}, "test")
    assert "status" in result or "error" in result
    result = action_executor.run("nonexistent", {}, "test")
    assert result.get("error") == "unknown action"
    print("action_executor OK")

def test_tool_schemas():
    assert len(action_executor.TOOL_SCHEMAS) > 0
    for schema in action_executor.TOOL_SCHEMAS:
        assert schema["type"] == "function"
        assert "name" in schema["function"]
    print("tool_schemas OK")

def test_dispatch():
    tool_call = {
        "id": "call_123",
        "type": "function",
        "function": {
            "name": "ask_user",
            "arguments": '{"question": "hello?"}'
        }
    }
    result = action_executor.dispatch(tool_call, "test")
    assert "status" in result or "error" in result
    # Invalid JSON
    bad_tool_call = {
        "id": "call_124",
        "type": "function",
        "function": {
            "name": "ask_user",
            "arguments": "not json"
        }
    }
    result = action_executor.dispatch(bad_tool_call, "test")
    assert "error" in result
    print("dispatch OK")

if __name__ == "__main__":
    test_context_builder()
    test_context_builder_with_tool_calls()
    test_db()
    test_action_dispatch()
    test_tool_schemas()
    test_dispatch()
    print("\nAll smoke tests passed.")
