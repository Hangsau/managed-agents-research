"""Unit tests for the Playbook system."""
import json
import os
import sys
import tempfile
from pathlib import Path

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from core.v2 import playbook as pb
from core.v2.playbook import Step, Playbook, resolve_args, _evaluate_condition, load_playbook, run_playbook


# ---------------------------------------------------------------------------
# resolve_args
# ---------------------------------------------------------------------------
def test_resolve_args_simple():
    assert resolve_args({"path": "/root/{{topic}}.txt"}, {"topic": "hello"}) == {"path": "/root/hello.txt"}


def test_resolve_args_missing_var_left_as_placeholder():
    assert resolve_args({"path": "/root/{{missing}}.txt"}, {}) == {"path": "/root/{{missing}}.txt"}


def test_resolve_args_nested():
    args = {
        "items": ["{{a}}", "{{b}}"],
        "meta": {"name": "{{name}}"},
    }
    out = resolve_args(args, {"a": "1", "b": "2", "name": "test"})
    assert out == {"items": ["1", "2"], "meta": {"name": "test"}}


def test_resolve_args_non_string_unchanged():
    assert resolve_args({"count": 42, "flag": True}, {"count": 99}) == {"count": 42, "flag": True}


# ---------------------------------------------------------------------------
# _evaluate_condition
# ---------------------------------------------------------------------------
def test_condition_empty_string_skips():
    assert _evaluate_condition("{{var}}", {"var": ""}) is False


def test_condition_null_skips():
    assert _evaluate_condition("{{var}}", {"var": "null"}) is False


def test_condition_false_skips():
    assert _evaluate_condition("{{var}}", {"var": "false"}) is False


def test_condition_truthy_runs():
    assert _evaluate_condition("{{var}}", {"var": "hello"}) is True


def test_condition_none_always_runs():
    assert _evaluate_condition(None, {}) is True


# ---------------------------------------------------------------------------
# load_playbook
# ---------------------------------------------------------------------------
def test_load_playbook_roundtrip():
    data = {
        "name": "Test Playbook",
        "vars": {"topic": "ai"},
        "steps": [
            {"name": "step1", "action": "bash", "args": {"cmd": "echo {{topic}}"}, "condition": "{{topic}}"},
            {"name": "step2", "action": "complete", "args": {"summary": "done"}},
        ],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".playbook", delete=False) as f:
        json.dump(data, f)
        path = f.name
    try:
        loaded = load_playbook(path)
        assert loaded.name == "Test Playbook"
        assert loaded.vars == {"topic": "ai"}
        assert len(loaded.steps) == 2
        assert loaded.steps[0].action == "bash"
        assert loaded.steps[0].condition == "{{topic}}"
        assert loaded.steps[1].action == "complete"
        assert loaded.steps[1].condition is None
    finally:
        os.unlink(path)


def test_load_playbook_missing_file():
    result = load_playbook("/nonexistent/foo.playbook")
    assert result is None, "Missing playbook should return None"


# ---------------------------------------------------------------------------
# run_playbook — mocked executor
# ---------------------------------------------------------------------------
class FakeExecutor:
    """Records calls and returns canned responses."""
    def __init__(self, responses: list[dict] | None = None):
        self.calls: list[tuple] = []
        self.responses = responses or []
        self._idx = 0

    def run(self, action: str, args: dict, session_id: str) -> dict:
        self.calls.append((action, args, session_id))
        resp = self.responses[self._idx] if self._idx < len(self.responses) else {"status": "ok"}
        self._idx += 1
        return resp


def test_run_playbook_happy_path():
    fake = FakeExecutor([{"stdout": "hello"}, {"status": "completed"}])
    original = pb.action_executor
    pb.action_executor = fake
    try:
        pl = Playbook(
            name="happy",
            vars={"topic": "world"},
            steps=[
                Step(name="greet", action="bash", args={"cmd": "echo {{topic}}"}),
                Step(name="finish", action="complete", args={"summary": "done"}),
            ],
        )
        results = run_playbook(pl, "sess_1", llm_context={})
        assert len(results) == 2
        assert results[0]["step_name"] == "greet"
        assert results[0]["result"]["stdout"] == "hello"
        assert results[0]["error"] is False
        assert results[1]["step_name"] == "finish"
        assert results[1]["error"] is False
        # args were interpolated
        assert fake.calls[0][1]["cmd"] == "echo world"
    finally:
        pb.action_executor = original


def test_run_playbook_skips_on_condition():
    fake = FakeExecutor([{"status": "ok"}])
    original = pb.action_executor
    pb.action_executor = fake
    try:
        pl = Playbook(
            name="skipper",
            vars={"run_optional": ""},
            steps=[
                Step(name="always", action="bash", args={"cmd": "date"}),
                Step(name="optional", action="bash", args={"cmd": "rm -rf /"}, condition="{{run_optional}}"),
            ],
        )
        results = run_playbook(pl, "sess_2")
        assert len(results) == 2
        assert results[0]["skipped"] is False
        assert results[1]["skipped"] is True
        assert results[1]["result"] is None
        assert len(fake.calls) == 1
    finally:
        pb.action_executor = original


def test_run_playbook_stops_on_error():
    fake = FakeExecutor([{"error": "boom"}, {"status": "ok"}])
    original = pb.action_executor
    pb.action_executor = fake
    try:
        pl = Playbook(
            name="failfast",
            steps=[
                Step(name="bad", action="bash", args={"cmd": "false"}),
                Step(name="never", action="bash", args={"cmd": "true"}),
            ],
        )
        results = run_playbook(pl, "sess_3", stop_on_error=True)
        assert len(results) == 1
        assert results[0]["error"] is True
        assert len(fake.calls) == 1
    finally:
        pb.action_executor = original


def test_run_playbook_continues_on_error_when_configured():
    fake = FakeExecutor([{"error": "boom"}, {"status": "ok"}])
    original = pb.action_executor
    pb.action_executor = fake
    try:
        pl = Playbook(
            name="resilient",
            steps=[
                Step(name="bad", action="bash", args={"cmd": "false"}),
                Step(name="ok", action="bash", args={"cmd": "true"}),
            ],
        )
        results = run_playbook(pl, "sess_4", stop_on_error=False)
        assert len(results) == 2
        assert results[0]["error"] is True
        assert results[1]["error"] is False
        assert len(fake.calls) == 2
    finally:
        pb.action_executor = original


def test_run_playbook_propagates_results_to_context():
    fake = FakeExecutor([{"stdout": "42"}, {"status": "ok"}])
    original = pb.action_executor
    pb.action_executor = fake
    try:
        pl = Playbook(
            name="chain",
            steps=[
                Step(name="get_num", action="bash", args={"cmd": "echo 42"}),
                Step(name="use_num", action="bash", args={"cmd": "echo {{get_num_stdout}}"}),
            ],
        )
        results = run_playbook(pl, "sess_5")
        assert len(results) == 2
        # second step should see the stdout from the first step
        assert fake.calls[1][1]["cmd"] == "echo 42"
    finally:
        pb.action_executor = original


if __name__ == "__main__":
    test_resolve_args_simple()
    test_resolve_args_missing_var_left_as_placeholder()
    test_resolve_args_nested()
    test_resolve_args_non_string_unchanged()
    test_condition_empty_string_skips()
    test_condition_null_skips()
    test_condition_false_skips()
    test_condition_truthy_runs()
    test_condition_none_always_runs()
    test_load_playbook_roundtrip()
    test_load_playbook_missing_file()
    test_run_playbook_happy_path()
    test_run_playbook_skips_on_condition()
    test_run_playbook_stops_on_error()
    test_run_playbook_continues_on_error_when_configured()
    test_run_playbook_propagates_results_to_context()
    print("\nAll playbook tests passed.")
