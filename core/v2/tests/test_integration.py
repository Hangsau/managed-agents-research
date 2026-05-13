"""Integration tests for batch runner: queue + dispatch + results."""
import json, os, sys, tempfile

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_CORE_DIR = os.path.join(_PROJECT_ROOT, "core")
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

from core.v2 import db
from core.v2.dispatcher import submit_batch, collect_results


def setup_module():
    db.ensure_schema()
    db.ensure_queue_schema()


def test_enqueue_and_claim():
    batch_id = submit_batch([
        {"session_id": "test_s1", "playbook_name": "research", "vars": {"topic": "AI", "angle": "ethics"}},
        {"session_id": "test_s2", "playbook_name": "collect", "vars": {"url": "https://example.com"}},
    ])

    status = db.get_batch_status(batch_id)
    assert status["total"] == 2
    assert status["pending"] == 2
    assert status["done"] == 0

    # Claim one
    task = db.claim_next_pending()
    assert task is not None
    assert task["batch_id"] == batch_id
    assert task["playbook_name"] == "research"

    # Status should show running
    status = db.get_batch_status(batch_id)
    assert status["pending"] == 1
    assert status["running"] == 1

    # Complete it
    db.complete_task(task["id"], result_path="/tmp/test_result.json")

    # Claim second
    task2 = db.claim_next_pending()
    assert task2 is not None
    assert task2["playbook_name"] == "collect"
    db.complete_task(task2["id"], error="network timeout")

    # Final status
    status = db.get_batch_status(batch_id)
    assert status["pending"] == 0
    assert status["running"] == 0
    assert status["done"] == 1
    assert status["failed"] == 1

    print("test_enqueue_and_claim OK")


def test_load_playbook_builtin():
    from core.v2.playbook import load_playbook

    pb = load_playbook("research")
    assert pb is not None
    assert pb.name == "web_research"
    assert "topic" in pb.vars or any("topic" in str(s.args) for s in pb.steps)

    pb2 = load_playbook("collect")
    assert pb2 is not None

    pb3 = load_playbook("nonexistent")
    assert pb3 is None

    print("test_load_playbook_builtin OK")


def test_playbook_with_vars():
    from core.v2.playbook import Playbook

    pb = Playbook(
        name="test",
        vars={"a": 1},
        steps=[],
    )
    pb2 = pb.with_vars({"b": 2})
    assert pb2.vars == {"a": 1, "b": 2}
    assert pb.vars == {"a": 1}  # original unchanged

    print("test_playbook_with_vars OK")


def test_collect_results():
    # Create a temp result file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({"answer": 42}, f)
        temp_path = f.name

    batch_id = submit_batch([
        {"session_id": "col_s1", "playbook_name": "research", "vars": {}},
    ])

    task = db.claim_next_pending()
    db.complete_task(task["id"], result_path=temp_path)

    results = collect_results(batch_id)
    assert len(results) == 1
    assert results[0]["session_id"] == "col_s1"
    assert results[0]["result"]["answer"] == 42

    # Test merge mode
    merged = collect_results(batch_id, merge=True)
    assert isinstance(merged, dict)
    assert merged["total"] == 1
    assert merged["success"] == 1
    assert merged["failed"] == 0
    assert "col_s1" in merged["results"]

    os.unlink(temp_path)
    print("test_collect_results OK")


def test_retry():
    batch_id = submit_batch([
        {"session_id": "retry_s1", "playbook_name": "research", "vars": {}},
    ], max_retries=2)

    task = db.claim_next_pending()
    assert task["max_retries"] == 2
    assert task["retries"] == 0

    # First failure -> should retry (retries=0 < max_retries=2)
    retried = db.complete_task(task["id"], error="network error")
    assert retried is True

    # Claim again (retry attempt 1)
    task2 = db.claim_next_pending()
    assert task2["retries"] == 1
    retried2 = db.complete_task(task2["id"], error="still broken")
    assert retried2 is True

    # Claim again (retry attempt 2)
    task3 = db.claim_next_pending()
    assert task3["retries"] == 2
    retried3 = db.complete_task(task3["id"], error="final fail")
    assert retried3 is False  # no more retries

    status = db.get_batch_status(batch_id)
    assert status["failed"] == 1
    print("test_retry OK")


def test_schema_validation():
    from core.v2.playbook import _validate_schema

    schema = {
        "type": "object",
        "required": ["name"],
        "properties": {
            "name": {"type": "string"},
            "count": {"type": "integer"},
        }
    }

    errors = _validate_schema({"name": "test", "count": 5}, schema)
    assert errors == []

    errors = _validate_schema({"count": 5}, schema)
    assert any("missing required field 'name'" in e for e in errors)

    errors = _validate_schema({"name": "test", "count": "five"}, schema)
    assert any("expected integer" in e for e in errors)

    print("test_schema_validation OK")


def test_playbook_goto():
    from core.v2.playbook import Playbook, Step, run_playbook

    pb = Playbook(
        name="goto_test",
        steps=[
            Step(action="bash", name="check", args={"cmd": "echo ok"}),
            Step(action="complete", name="branch", args={}, goto="end"),
            Step(action="bash", name="skipped", args={"cmd": "echo should_not_run"}),
            Step(action="complete", name="end", args={}, label="end"),
        ]
    )

    results = run_playbook(pb, session_id="goto_test_session", stop_on_error=False)
    step_names = [r["step_name"] for r in results if not r["skipped"]]
    assert step_names == ["check", "branch", "end"]
    print("test_playbook_goto OK")


if __name__ == "__main__":
    setup_module()
    test_enqueue_and_claim()
    test_load_playbook_builtin()
    test_playbook_with_vars()
    test_collect_results()
    test_retry()
    test_schema_validation()
    test_playbook_goto()
    print("\nAll integration tests passed.")
